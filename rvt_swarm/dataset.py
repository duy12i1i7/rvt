from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

import numpy as np
import torch
from torch.utils.data import Dataset

from .config import Config, TOPOLOGY_IDS
from .controllers import expert_action
from .environment import SwarmFormationEnv
from .recoverability import classify_recoverability, recoverability_targets
from .utils import configure_worker_runtime, heading_features, limit_child_threads, pairwise_dist, unit


@dataclass
class GraphSample:
    node_x: torch.Tensor
    edge_index: torch.Tensor
    edge_attr: torch.Tensor
    action_target_best: torch.Tensor
    action_target_keep: torch.Tensor
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


NODE_DIM = 68  # 32 original + 36 LiDAR rays (added min_ttc)
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

    # LiDAR scans: (n, lidar_num_rays), normalised to [0, 1]
    lidar_raw = obs.get("lidar_scans", None)
    lidar_range = cfg.env.lidar_range
    if lidar_raw is None:
        lidar_norm = np.ones((n, cfg.env.lidar_num_rays), dtype=np.float32)
    else:
        lidar_norm = np.clip(lidar_raw / lidar_range, 0.0, 1.0)

    node_features = []
    obs_pos = obs["obstacles"]
    obs_vel = obs.get("obstacle_velocities", np.zeros((0, 2), dtype=np.float32))

    # ── Precompute min time-to-collision per robot (predictive feature) ──
    r_safe_rr = max(cfg.env.min_rr_distance, 2.0 * cfg.env.robot_radius)
    r_safe_ro = max(cfg.env.min_ro_distance, cfg.env.robot_radius + cfg.env.obstacle_radius)
    ttc_horizon = max(cfg.env.dt, cfg.env.sensing_radius / max(cfg.env.max_speed, 1e-6))
    min_ttc_per_robot = np.full(n, ttc_horizon, dtype=np.float32)
    for i in range(n):
        for j in range(n):
            if j == i:
                continue
            dp = pos[j] - pos[i]
            dv = vel[j] - vel[i]
            aq = float(np.dot(dv, dv))
            bq = 2.0 * float(np.dot(dp, dv))
            cq = float(np.dot(dp, dp)) - r_safe_rr ** 2
            if cq < 0:
                min_ttc_per_robot[i] = 0.0
                break
            if aq > 1e-12:
                disc = bq * bq - 4.0 * aq * cq
                if disc >= 0:
                    t_hit = (-bq - np.sqrt(disc)) / (2.0 * aq)
                    if t_hit > 0:
                        min_ttc_per_robot[i] = min(min_ttc_per_robot[i], t_hit)
        for k in range(len(obs_pos)):
            dp = obs_pos[k] - pos[i]
            ov_k = obs_vel[k] if k < len(obs_vel) else np.zeros(2, dtype=np.float32)
            dv = ov_k - vel[i]
            aq = float(np.dot(dv, dv))
            bq = 2.0 * float(np.dot(dp, dv))
            cq = float(np.dot(dp, dp)) - r_safe_ro ** 2
            if cq < 0:
                min_ttc_per_robot[i] = 0.0
            elif aq > 1e-12:
                disc = bq * bq - 4.0 * aq * cq
                if disc >= 0:
                    t_hit = (-bq - np.sqrt(disc)) / (2.0 * aq)
                    if t_hit > 0:
                        min_ttc_per_robot[i] = min(min_ttc_per_robot[i], t_hit)

    for i in range(n):
        c1, s1 = heading_features(vel[i])
        gnorm = np.linalg.norm(goal_vec[i])
        gc = goal_vec[i] / max(gnorm, 1e-8)
        relc = pos[i] - centroid
        ro = pos[i] - obstacle_centroid
        ferr = obs["formation_error"][i]
        local_window = max(cfg.env.nominal_spacing * 2.0, cfg.env.min_ro_distance)
        local_bottleneck = float(np.mean(np.linalg.norm(obs_pos - pos[i], axis=1) < local_window)) if len(obs_pos) else 0.0
        min_obs = float(np.min(np.linalg.norm(obs_pos - pos[i], axis=1))) if len(obs_pos) else float(cfg.env.lidar_range)
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
            min(float(min_ttc_per_robot[i]) / max(ttc_horizon, 1e-6), 1.0),  # normalised min TTC
        ]
        # Append 36 normalised LiDAR distances
        node.extend(lidar_norm[i].tolist())
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
            # Proper TTC via quadratic formula for circular agents
            dp_e = rel; dv_e = rv
            aq_e = float(np.dot(dv_e, dv_e))
            bq_e = 2.0 * float(np.dot(dp_e, dv_e))
            cq_e = float(np.dot(dp_e, dp_e)) - r_safe_rr ** 2
            ttc_edge = ttc_horizon
            if cq_e < 0:
                ttc_edge = 0.0
            elif aq_e > 1e-12:
                disc_e = bq_e ** 2 - 4.0 * aq_e * cq_e
                if disc_e >= 0:
                    t_e = (-bq_e - np.sqrt(disc_e)) / (2.0 * aq_e)
                    if t_e > 0:
                        ttc_edge = min(ttc_horizon, t_e)
            edge_src.append(i)
            edge_dst.append(j)
            edge_attr.append([
                rel[0], rel[1], rv[0], rv[1], d[i, j],
                corridor_proj, lateral_proj,
                desired_spacing_error,
                ttc_edge,
                obs["bottleneck"], obs["progress"],
            ])
    edge_index = torch.tensor(np.asarray([edge_src, edge_dst], dtype=np.int64))
    edge_attr = torch.tensor(np.asarray(edge_attr, dtype=np.float32))
    return node_x, edge_index, edge_attr


def _generate_episode(args):
    """Generate samples for a single episode (worker function for multiprocessing).

    Returns plain numpy dicts (not torch tensors) to avoid file-descriptor-heavy
    torch serialisation over multiprocessing IPC.
    """
    configure_worker_runtime()
    ep, cfg, seed = args
    rng = np.random.default_rng(seed)
    env = SwarmFormationEnv(cfg)
    n = int(rng.choice(cfg.env.team_sizes))
    scenario = str(rng.choice(cfg.env.scenarios))
    obs = env.reset(n, scenario, seed=seed)
    done = False
    episode_samples = []
    while not done:
        recover_margin, best_topology, score_vec, keep_recover_margin = recoverability_targets(env, cfg)
        action_best = expert_action(obs, cfg, best_topology)
        action_keep = expert_action(obs, cfg, 0)
        node_x, edge_index, edge_attr = build_graph(obs, cfg)
        aux = np.array([[obs["formation_scale"], obs["bottleneck"], obs["progress"], obs.get("split_active", 0.0)]], dtype=np.float32)
        # Store as numpy to avoid torch FD issues in multiprocessing
        # Keep-topology targets are used by methods that never switch topology at runtime.
        # Normalize actions to [-1, 1] so Tanh output matches target scale.
        sample = {
            'node_x': node_x.numpy(),
            'edge_index': edge_index.numpy(),
            'edge_attr': edge_attr.numpy(),
            'action_target_best': np.asarray(action_best / cfg.env.max_accel, dtype=np.float32),
            'action_target_keep': np.asarray(action_keep / cfg.env.max_accel, dtype=np.float32),
            'recover_target': np.array([[keep_recover_margin]], dtype=np.float32),
            'recover_scores_target': np.asarray(score_vec[None, :], dtype=np.float32),
            'topology_target': np.array([TOPOLOGY_IDS.index(best_topology)], dtype=np.int64),
            'aux_target': aux,
        }
        episode_samples.append(sample)
        if classify_recoverability(recover_margin) <= 0.0 and obs["bottleneck"] > obs["progress"]:
            noise_scale = float(np.clip(1.0 - recover_margin, 0.0, 1.0))
            noise = noise_scale * rng.normal(size=action_best.shape).astype(np.float32) * cfg.env.max_accel
            noisy_action_best = np.clip(action_best + noise, -cfg.env.max_accel, cfg.env.max_accel)
            noisy_action_keep = np.clip(action_keep + noise, -cfg.env.max_accel, cfg.env.max_accel)
            sample_noisy = {
                'node_x': sample['node_x'].copy(),
                'edge_index': sample['edge_index'].copy(),
                'edge_attr': sample['edge_attr'].copy(),
                'action_target_best': np.asarray(noisy_action_best / cfg.env.max_accel, dtype=np.float32),
                'action_target_keep': np.asarray(noisy_action_keep / cfg.env.max_accel, dtype=np.float32),
                'recover_target': sample['recover_target'].copy(),
                'recover_scores_target': sample['recover_scores_target'].copy(),
                'topology_target': sample['topology_target'].copy(),
                'aux_target': sample['aux_target'].copy(),
            }
            episode_samples.append(sample_noisy)
        obs, _, done, _ = env.step(action_best, best_topology)
    return episode_samples


def generate_dataset(cfg: Config, episodes: int | None = None) -> SwarmDataset:
    import multiprocessing as mp
    import os

    episodes = episodes or cfg.train.expert_episodes
    # Each episode gets a unique seed derived from base seed
    base_rng = np.random.default_rng(cfg.train.seed)
    seeds = base_rng.integers(0, 2**31, size=episodes)
    args_list = [(ep, cfg, int(seeds[ep])) for ep in range(episodes)]

    auto = max(1, (os.cpu_count() * 3) // 4)
    n_workers = min(episodes, cfg.train.n_workers or auto)
    print(f"  Generating {episodes} episodes with {n_workers} workers...")

    if n_workers > 1:
        with limit_child_threads(True):
            ctx = mp.get_context("spawn")
            with ctx.Pool(n_workers) as pool:
                results = pool.map(_generate_episode, args_list)
    else:
        results = [_generate_episode(a) for a in args_list]

    # Convert numpy dicts back to GraphSample with torch tensors (main process)
    samples: List[GraphSample] = []
    for ep_samples in results:
        for d in ep_samples:
            samples.append(GraphSample(
                node_x=torch.from_numpy(d['node_x']),
                edge_index=torch.from_numpy(d['edge_index']),
                edge_attr=torch.from_numpy(d['edge_attr']),
                action_target_best=torch.from_numpy(d['action_target_best']),
                action_target_keep=torch.from_numpy(d['action_target_keep']),
                recover_target=torch.from_numpy(d['recover_target']),
                recover_scores_target=torch.from_numpy(d['recover_scores_target']),
                topology_target=torch.from_numpy(d['topology_target']),
                aux_target=torch.from_numpy(d['aux_target']),
            ))
    print(f"  Dataset: {len(samples)} samples from {episodes} episodes")
    return SwarmDataset(cfg, samples)


def collate_graphs(batch: List[GraphSample]) -> Dict[str, torch.Tensor]:
    node_x, edge_attr = [], []
    edge_index = []
    action_best_t, action_keep_t = [], []
    recover_t, recover_scores_t, topo_t, aux_t = [], [], [], []
    batch_index = []
    offset = 0
    for b, sample in enumerate(batch):
        n = sample.node_x.shape[0]
        node_x.append(sample.node_x)
        edge_attr.append(sample.edge_attr)
        edge_index.append(sample.edge_index + offset)
        action_best_t.append(sample.action_target_best)
        action_keep_t.append(sample.action_target_keep)
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
        "action_target_best": torch.cat(action_best_t, dim=0),
        "action_target_keep": torch.cat(action_keep_t, dim=0),
        "recover_target": torch.cat(recover_t, dim=0),
        "recover_scores_target": torch.cat(recover_scores_t, dim=0),
        "topology_target": torch.cat(topo_t, dim=0),
        "aux_target": torch.cat(aux_t, dim=0),
        "batch_index": torch.cat(batch_index, dim=0),
    }
