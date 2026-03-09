from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

import numpy as np
import torch
from torch.utils.data import Dataset

from .config import Config, TOPOLOGY_IDS
from .environment import SwarmFormationEnv, expert_action
from .recoverability import classify_recoverability, recoverability_targets
from .utils import heading_features, pairwise_dist, unit


@dataclass
class GraphSample:
    node_x: torch.Tensor
    edge_index: torch.Tensor
    edge_attr: torch.Tensor
    action_target: torch.Tensor
    recover_target: torch.Tensor
    recover_scores_target: torch.Tensor
    topology_target: torch.Tensor
    aux_target: torch.Tensor


class SwarmDataset(Dataset):
    def __init__(self, cfg: Config, samples: List[GraphSample]):
        self.cfg = cfg
        self.samples = samples

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> GraphSample:
        return self.samples[idx]


NODE_DIM = 31
EDGE_DIM = 11


def build_graph(obs: Dict, cfg: Config):
    pos = obs["positions"]
    vel = obs["velocities"]
    goal_vec = obs["goal_vec"]
    n = len(pos)
    centroid = pos.mean(axis=0)
    obstacle_centroid = obs["obstacles"].mean(axis=0) if len(obs["obstacles"]) else np.zeros(2, dtype=np.float32)
    corridor = np.array([obs.get("corridor_dx", 1.0), obs.get("corridor_dy", 0.0)], dtype=np.float32)
    lateral = np.array([corridor[1], -corridor[0]], dtype=np.float32)
    topo_onehot = np.zeros((5,), dtype=np.float32)
    topo_onehot[int(obs["topology_mode"])] = 1.0

    node_features = []
    obs_pos = obs["obstacles"]
    obs_vel = obs.get("obstacle_velocities", np.zeros((0, 2), dtype=np.float32))
    for i in range(n):
        c1, s1 = heading_features(vel[i])
        gnorm = np.linalg.norm(goal_vec[i])
        gc = goal_vec[i] / max(gnorm, 1e-8)
        relc = pos[i] - centroid
        ro = pos[i] - obstacle_centroid
        ferr = obs["formation_error"][i]
        local_bottleneck = float(np.mean(np.linalg.norm(obs_pos - pos[i], axis=1) < 1.5)) if len(obs_pos) else 0.0
        min_obs = float(np.min(np.linalg.norm(obs_pos - pos[i], axis=1))) if len(obs_pos) else 4.0
        dyn_obs = np.zeros(2, dtype=np.float32)
        if len(obs_pos):
            j = int(np.argmin(np.linalg.norm(obs_pos - pos[i], axis=1)))
            if len(obs_vel):
                dyn_obs = obs_vel[j]
        node = [
            pos[i, 0], pos[i, 1],
            vel[i, 0], vel[i, 1],
            c1, s1,
            goal_vec[i, 0], goal_vec[i, 1],
            gc[0], gc[1],
            relc[0], relc[1],
            ferr[0], ferr[1],
            ro[0], ro[1],
            float(np.dot(relc, corridor)), float(np.dot(relc, lateral)),
            obs["formation_scale"], obs["bottleneck"], obs["progress"],
            local_bottleneck, min_obs,
            dyn_obs[0], dyn_obs[1],
            float(obs.get("split_active", 0.0)),
            topo_onehot[0], topo_onehot[1], topo_onehot[2], topo_onehot[3], topo_onehot[4],
        ]
        node_features.append(node)
    node_x = torch.tensor(np.asarray(node_features, dtype=np.float32))

    d = pairwise_dist(pos, pos)
    edge_src, edge_dst, edge_attr = [], [], []
    for i in range(n):
        nbrs = np.argsort(d[i])[: cfg.train.graph_k + 1]
        for j in nbrs:
            if i == j:
                continue
            rel = pos[j] - pos[i]
            rv = vel[j] - vel[i]
            corridor_proj = float(np.dot(rel, corridor))
            lateral_proj = float(np.dot(rel, lateral))
            desired_spacing_error = abs(np.linalg.norm(rel) - cfg.env.nominal_spacing * obs["formation_scale"])
            ttc_proxy = np.linalg.norm(rel) / max(1e-3, abs(float(np.dot(unit(rel), rv))))
            edge_src.append(i)
            edge_dst.append(j)
            edge_attr.append([
                rel[0], rel[1], rv[0], rv[1], d[i, j],
                corridor_proj, lateral_proj,
                desired_spacing_error,
                min(ttc_proxy, 10.0),
                obs["bottleneck"], obs["progress"],
            ])
    edge_index = torch.tensor(np.asarray([edge_src, edge_dst], dtype=np.int64))
    edge_attr = torch.tensor(np.asarray(edge_attr, dtype=np.float32))
    return node_x, edge_index, edge_attr


def generate_dataset(cfg: Config, episodes: int | None = None) -> SwarmDataset:
    episodes = episodes or cfg.train.expert_episodes
    env = SwarmFormationEnv(cfg)
    samples: List[GraphSample] = []
    rng = np.random.default_rng(cfg.train.seed)
    for ep in range(episodes):
        n = int(rng.choice(cfg.env.team_sizes))
        scenario = str(rng.choice(cfg.env.scenarios, p=np.array([0.18, 0.28, 0.30, 0.24])))
        obs = env.reset(n, scenario)
        done = False
        while not done:
            recover_margin, best_topology, score_vec = recoverability_targets(env, cfg)
            action = expert_action(obs, cfg, best_topology)
            node_x, edge_index, edge_attr = build_graph(obs, cfg)
            aux = np.array([[obs["formation_scale"], obs["bottleneck"], obs["progress"], obs.get("split_active", 0.0)]], dtype=np.float32)
            samples.append(GraphSample(
                node_x=node_x,
                edge_index=edge_index,
                edge_attr=edge_attr,
                action_target=torch.tensor(action, dtype=torch.float32),
                recover_target=torch.tensor([[recover_margin]], dtype=torch.float32),
                recover_scores_target=torch.tensor(score_vec[None, :], dtype=torch.float32),
                topology_target=torch.tensor([TOPOLOGY_IDS.index(best_topology)], dtype=torch.long),
                aux_target=torch.tensor(aux, dtype=torch.float32),
            ))
            # hard-negative oversampling around boundary states
            if classify_recoverability(recover_margin) <= 0.0 and obs["bottleneck"] > 0.35:
                noisy_action = 0.75 * action + 0.25 * rng.normal(size=action.shape).astype(np.float32) * cfg.env.max_accel
                samples.append(GraphSample(
                    node_x=node_x.clone(),
                    edge_index=edge_index.clone(),
                    edge_attr=edge_attr.clone(),
                    action_target=torch.tensor(noisy_action, dtype=torch.float32),
                    recover_target=torch.tensor([[recover_margin]], dtype=torch.float32),
                    recover_scores_target=torch.tensor(score_vec[None, :], dtype=torch.float32),
                    topology_target=torch.tensor([TOPOLOGY_IDS.index(best_topology)], dtype=torch.long),
                    aux_target=torch.tensor(aux, dtype=torch.float32),
                ))
            obs, _, done, _ = env.step(action, best_topology)
    return SwarmDataset(cfg, samples)


def collate_graphs(batch: List[GraphSample]) -> Dict[str, torch.Tensor]:
    node_x, edge_attr, action_t = [], [], []
    edge_index = []
    recover_t, recover_scores_t, topo_t, aux_t = [], [], [], []
    batch_index = []
    offset = 0
    for b, sample in enumerate(batch):
        n = sample.node_x.shape[0]
        node_x.append(sample.node_x)
        edge_attr.append(sample.edge_attr)
        edge_index.append(sample.edge_index + offset)
        action_t.append(sample.action_target)
        recover_t.append(sample.recover_target)
        recover_scores_t.append(sample.recover_scores_target)
        topo_t.append(sample.topology_target)
        aux_t.append(sample.aux_target)
        batch_index.append(torch.full((n,), b, dtype=torch.long))
        offset += n
    return {
        "node_x": torch.cat(node_x, dim=0),
        "edge_index": torch.cat(edge_index, dim=1),
        "edge_attr": torch.cat(edge_attr, dim=0),
        "action_target": torch.cat(action_t, dim=0),
        "recover_target": torch.cat(recover_t, dim=0),
        "recover_scores_target": torch.cat(recover_scores_t, dim=0),
        "topology_target": torch.cat(topo_t, dim=0),
        "aux_target": torch.cat(aux_t, dim=0),
        "batch_index": torch.cat(batch_index, dim=0),
    }
