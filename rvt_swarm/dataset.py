from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

import numpy as np

from .config import Config, LEARNED_TOPOLOGY_IDS
from .controllers import expert_action
from .environment import SwarmFormationEnv
from .recoverability import classify_recoverability, recoverability_targets
from .utils import configure_worker_runtime, dot2, heading_features, limit_child_threads, pairwise_dist, unit


@dataclass
class GraphSample:
    node_x: torch.Tensor
    edge_index: torch.Tensor
    edge_attr: torch.Tensor
    action_target_all: torch.Tensor
    action_target_best: torch.Tensor
    action_target_keep: torch.Tensor
    recover_target: torch.Tensor
    recover_scores_target: torch.Tensor
    topology_target: torch.Tensor
    topology_target_dist: torch.Tensor
    aux_target: torch.Tensor


class SwarmDataset:
    def __init__(self, cfg: Config, samples: List[GraphSample]):
        self.cfg = cfg
        self.samples = samples

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> GraphSample:
        return self.samples[idx]


NODE_DIM = 68  # 32 original + 36 LiDAR rays (added min_ttc)
EDGE_DIM = 11


def topology_target_distribution(score_targets: np.ndarray) -> np.ndarray:
    scores = np.asarray(score_targets, dtype=np.float32).reshape(-1)
    if scores.size == 0:
        return scores.astype(np.float32)

    # Conservative soft target: only allocate probability mass away from the
    # structural anchor `keep` when another topology has a positive advantage
    # over it. This reduces gratuitous switching without hard-coded margins.
    keep_score = float(scores[0])
    weights = np.zeros_like(scores, dtype=np.float32)
    if scores.shape[0] == 1:
        weights[0] = 1.0
        return weights

    weights[1:] = np.maximum(scores[1:] - keep_score, 0.0)
    weights[0] = float(np.maximum(keep_score - scores[1:], 0.0).sum())
    total = float(np.sum(weights))
    if total <= 0.0 or not np.isfinite(total):
        weights[0] = 1.0
        return weights
    return weights / total


def _ensure_2d_float32(arr, width: int, name: str) -> np.ndarray:
    """Normalize observation arrays to contiguous float32 matrices."""
    out = np.asarray(arr, dtype=np.float32)
    if out.size == 0:
        return np.zeros((0, width), dtype=np.float32)
    if out.ndim == 1:
        if out.size % width != 0:
            raise ValueError(f"{name} has incompatible size {out.size} for width {width}")
        out = out.reshape(-1, width)
    if out.ndim != 2 or out.shape[1] != width:
        raise ValueError(f"{name} must have shape (N, {width}), got {out.shape}")
    return np.ascontiguousarray(out, dtype=np.float32)


def _obs_float(obs: Dict, key: str, default: float) -> float:
    """Read scalar observation fields with a backward-compatible default."""
    value = obs.get(key, default)
    arr = np.asarray(value, dtype=np.float32)
    if arr.size == 0:
        return float(default)
    scalar = float(arr.reshape(-1)[0])
    if not np.isfinite(scalar):
        return float(default)
    return scalar


def _obs_int(obs: Dict, key: str, default: int) -> int:
    return int(round(_obs_float(obs, key, float(default))))


def build_graph_arrays(obs: Dict, cfg: Config):
    pos = _ensure_2d_float32(obs["positions"], 2, "positions")
    vel = _ensure_2d_float32(obs["velocities"], 2, "velocities")
    goal_vec = _ensure_2d_float32(obs["goal_vec"], 2, "goal_vec")
    n = len(pos)
    centroid = pos.mean(axis=0)
    obs_pos = _ensure_2d_float32(obs["obstacles"], 2, "obstacles")
    obstacle_centroid = obs_pos.mean(axis=0) if len(obs_pos) else np.zeros(2, dtype=np.float32)
    formation_scale = _obs_float(obs, "formation_scale", 1.0)
    bottleneck = _obs_float(obs, "bottleneck", 0.0)
    progress = _obs_float(obs, "progress", 0.0)
    split_active = _obs_float(obs, "split_active", 0.0)
    corridor = np.array([
        _obs_float(obs, "corridor_dx", 1.0),
        _obs_float(obs, "corridor_dy", 0.0),
    ], dtype=np.float32)
    if np.linalg.norm(corridor) < 1e-6:
        corridor = np.array([1.0, 0.0], dtype=np.float32)
    else:
        corridor = unit(corridor).astype(np.float32)
    lateral = np.array([corridor[1], -corridor[0]], dtype=np.float32)
    topo_onehot = np.zeros((5,), dtype=np.float32)
    topo_onehot[int(np.clip(_obs_int(obs, "topology_mode", 0), 0, topo_onehot.size - 1))] = 1.0

    # LiDAR scans: (n, lidar_num_rays), normalised to [0, 1]
    lidar_raw = obs.get("lidar_scans", None)
    lidar_range = cfg.env.lidar_range
    if lidar_raw is None:
        lidar_norm = np.ones((n, cfg.env.lidar_num_rays), dtype=np.float32)
    else:
        lidar_norm = _ensure_2d_float32(lidar_raw, cfg.env.lidar_num_rays, "lidar_scans")
        if len(lidar_norm) != n:
            raise ValueError(f"lidar_scans expected {n} rows, got {len(lidar_norm)}")
        lidar_norm = np.clip(lidar_norm / lidar_range, 0.0, 1.0)

    node_features = []
    obs_vel = _ensure_2d_float32(obs.get("obstacle_velocities", np.zeros((0, 2), dtype=np.float32)), 2, "obstacle_velocities")
    formation_error = _ensure_2d_float32(obs["formation_error"], 2, "formation_error")
    if len(formation_error) != n:
        raise ValueError(f"formation_error expected {n} rows, got {len(formation_error)}")

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
            aq = dot2(dv, dv)
            bq = 2.0 * dot2(dp, dv)
            cq = dot2(dp, dp) - r_safe_rr ** 2
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
            aq = dot2(dv, dv)
            bq = 2.0 * dot2(dp, dv)
            cq = dot2(dp, dp) - r_safe_ro ** 2
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
        ferr = formation_error[i]
        dyn_obs = np.zeros(2, dtype=np.float32)
        local_window = max(cfg.env.nominal_spacing * 2.0, cfg.env.min_ro_distance)
        if len(obs_pos):
            obs_delta = obs_pos - pos[i]
            obs_d2 = np.sum(obs_delta * obs_delta, axis=1, dtype=np.float32)
            local_bottleneck = float((obs_d2 < (local_window * local_window)).sum()) / float(len(obs_d2))
            nearest_idx = 0
            nearest_d2 = float(obs_d2[0])
            for idx in range(1, len(obs_d2)):
                candidate = float(obs_d2[idx])
                if candidate < nearest_d2:
                    nearest_d2 = candidate
                    nearest_idx = idx
            min_obs = float(np.sqrt(nearest_d2))
            if nearest_idx < len(obs_vel):
                dyn_obs = obs_vel[nearest_idx]
        else:
            local_bottleneck = 0.0
            min_obs = float(cfg.env.lidar_range)
        node = [
            pos[i, 0], pos[i, 1],
            vel[i, 0], vel[i, 1],
            c1, s1,
            goal_vec[i, 0], goal_vec[i, 1],
            gc[0], gc[1],
            relc[0], relc[1],
            ferr[0], ferr[1],
            ro[0], ro[1],
            dot2(relc, corridor), dot2(relc, lateral),
            formation_scale, bottleneck, progress,
            local_bottleneck, min_obs,
            dyn_obs[0], dyn_obs[1],
            split_active,
            topo_onehot[0], topo_onehot[1], topo_onehot[2], topo_onehot[3], topo_onehot[4],
            min(float(min_ttc_per_robot[i]) / max(ttc_horizon, 1e-6), 1.0),  # normalised min TTC
        ]
        # Append 36 normalised LiDAR distances
        node.extend(lidar_norm[i].tolist())
        node_features.append(node)
    node_x = np.asarray(node_features, dtype=np.float32)

    d = pairwise_dist(pos, pos)
    edge_src, edge_dst, edge_attr = [], [], []
    for i in range(n):
        dist_row = np.asarray(d[i], dtype=np.float32).reshape(-1)
        nbrs = sorted(range(n), key=lambda j: float(dist_row[j]))[: cfg.train.graph_k + 1]
        for j in nbrs:
            if i == j:
                continue
            rel = pos[j] - pos[i]
            rv = vel[j] - vel[i]
            corridor_proj = dot2(rel, corridor)
            lateral_proj = dot2(rel, lateral)
            desired_spacing_error = abs(np.linalg.norm(rel) - cfg.env.nominal_spacing * formation_scale)
            # Proper TTC via quadratic formula for circular agents
            dp_e = rel; dv_e = rv
            aq_e = dot2(dv_e, dv_e)
            bq_e = 2.0 * dot2(dp_e, dv_e)
            cq_e = dot2(dp_e, dp_e) - r_safe_rr ** 2
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
                bottleneck, progress,
            ])
    edge_index = np.asarray([edge_src, edge_dst], dtype=np.int64)
    edge_attr = np.asarray(edge_attr, dtype=np.float32)
    return node_x, edge_index, edge_attr


def build_graph(obs: Dict, cfg: Config):
    import torch

    node_x, edge_index, edge_attr = build_graph_arrays(obs, cfg)
    return (
        torch.from_numpy(node_x),
        torch.from_numpy(edge_index),
        torch.from_numpy(edge_attr),
    )


def _generate_episode_impl(args):
    ep, cfg, seed = args
    rng = np.random.default_rng(seed)
    env = SwarmFormationEnv(cfg)
    n = int(rng.choice(cfg.env.team_sizes))
    scenario = str(rng.choice(cfg.env.scenarios))
    obs = env.reset(n, scenario, seed=seed)
    done = False
    prev_topology = 0
    episode_samples = []
    while not done:
        recover_margin, best_topology, score_vec, keep_recover_margin = recoverability_targets(
            env,
            cfg,
            obs=obs,
            previous_topology=prev_topology,
        )
        candidate_actions = [expert_action(obs, cfg, topo) for topo in LEARNED_TOPOLOGY_IDS]
        action_all = np.stack(candidate_actions, axis=1).astype(np.float32)
        best_idx = LEARNED_TOPOLOGY_IDS.index(best_topology)
        action_best = action_all[:, best_idx, :]
        action_keep = action_all[:, 0, :]
        node_x, edge_index, edge_attr = build_graph_arrays(obs, cfg)
        aux = np.array([[
            _obs_float(obs, "formation_scale", 1.0),
            _obs_float(obs, "bottleneck", 0.0),
            _obs_float(obs, "progress", 0.0),
            _obs_float(obs, "split_active", 0.0),
        ]], dtype=np.float32)
        topo_dist = topology_target_distribution(score_vec)
        # Store as numpy to avoid torch FD issues in multiprocessing
        # Keep-topology targets are used by methods that never switch topology at runtime.
        # RVT gets supervision for the full action bank across all topology choices,
        # which keeps control/topology coupling aligned with the docs' counterfactual view.
        sample = {
            'node_x': node_x,
            'edge_index': edge_index,
            'edge_attr': edge_attr,
            'action_target_all': np.asarray(action_all / cfg.env.max_accel, dtype=np.float32),
            'action_target_best': np.asarray(action_best / cfg.env.max_accel, dtype=np.float32),
            'action_target_keep': np.asarray(action_keep / cfg.env.max_accel, dtype=np.float32),
            'recover_target': np.array([[keep_recover_margin]], dtype=np.float32),
            'recover_scores_target': np.asarray(score_vec[None, :], dtype=np.float32),
            'topology_target': np.array([best_idx], dtype=np.int64),
            'topology_target_dist': np.asarray(topo_dist[None, :], dtype=np.float32),
            'aux_target': aux,
        }
        episode_samples.append(sample)
        if classify_recoverability(recover_margin) <= 0.0 and obs["bottleneck"] > obs["progress"]:
            noise_scale = float(np.clip(1.0 - recover_margin, 0.0, 1.0))
            noise = noise_scale * rng.normal(size=action_best.shape).astype(np.float32) * cfg.env.max_accel
            noisy_action_all = np.clip(action_all + noise[:, None, :], -cfg.env.max_accel, cfg.env.max_accel)
            sample_noisy = {
                'node_x': sample['node_x'].copy(),
                'edge_index': sample['edge_index'].copy(),
                'edge_attr': sample['edge_attr'].copy(),
                'action_target_all': np.asarray(noisy_action_all / cfg.env.max_accel, dtype=np.float32),
                'action_target_best': np.asarray(noisy_action_all[:, best_idx, :] / cfg.env.max_accel, dtype=np.float32),
                'action_target_keep': np.asarray(noisy_action_all[:, 0, :] / cfg.env.max_accel, dtype=np.float32),
                'recover_target': sample['recover_target'].copy(),
                'recover_scores_target': sample['recover_scores_target'].copy(),
                'topology_target': sample['topology_target'].copy(),
                'topology_target_dist': sample['topology_target_dist'].copy(),
                'aux_target': sample['aux_target'].copy(),
            }
            episode_samples.append(sample_noisy)
        obs, _, done, _ = env.step(action_best, best_topology)
        prev_topology = best_topology
    return episode_samples


def _generate_episode(args):
    """Generate samples for a single episode (worker function for multiprocessing).

    Returns plain numpy dicts (not torch tensors) to avoid file-descriptor-heavy
    torch serialisation over multiprocessing IPC.
    """
    return _generate_episode_impl(args)


def _append_episode_samples(samples: List[GraphSample], ep_samples: List[Dict[str, np.ndarray]]) -> None:
    import torch

    for d in ep_samples:
        samples.append(GraphSample(
            node_x=torch.from_numpy(d['node_x']),
            edge_index=torch.from_numpy(d['edge_index']),
            edge_attr=torch.from_numpy(d['edge_attr']),
            action_target_all=torch.from_numpy(d['action_target_all']),
            action_target_best=torch.from_numpy(d['action_target_best']),
            action_target_keep=torch.from_numpy(d['action_target_keep']),
            recover_target=torch.from_numpy(d['recover_target']),
            recover_scores_target=torch.from_numpy(d['recover_scores_target']),
            topology_target=torch.from_numpy(d['topology_target']),
            topology_target_dist=torch.from_numpy(d['topology_target_dist']),
            aux_target=torch.from_numpy(d['aux_target']),
        ))


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

    samples: List[GraphSample] = []
    if n_workers > 1:
        try:
            with limit_child_threads(True):
                ctx = mp.get_context("spawn")
                with ctx.Pool(n_workers, initializer=configure_worker_runtime) as pool:
                    for ep_samples in pool.imap(_generate_episode, args_list):
                        _append_episode_samples(samples, ep_samples)
        except Exception as exc:
            print(
                f"[warn] Parallel dataset generation failed ({exc.__class__.__name__}: {exc}). "
                "Falling back to sequential generation."
            )
            samples = []
            for args in args_list:
                _append_episode_samples(samples, _generate_episode_impl(args))
    else:
        for args in args_list:
            _append_episode_samples(samples, _generate_episode_impl(args))
    print(f"  Dataset: {len(samples)} samples from {episodes} episodes")
    return SwarmDataset(cfg, samples)


def collate_graphs(batch: List[GraphSample]) -> Dict[str, torch.Tensor]:
    import torch

    node_x, edge_attr = [], []
    edge_index = []
    action_all_t, action_best_t, action_keep_t = [], [], []
    recover_t, recover_scores_t, topo_t, topo_dist_t, aux_t = [], [], [], [], []
    batch_index = []
    offset = 0
    for b, sample in enumerate(batch):
        n = sample.node_x.shape[0]
        node_x.append(sample.node_x)
        edge_attr.append(sample.edge_attr)
        edge_index.append(sample.edge_index + offset)
        action_all_t.append(sample.action_target_all)
        action_best_t.append(sample.action_target_best)
        action_keep_t.append(sample.action_target_keep)
        recover_t.append(sample.recover_target)
        recover_scores_t.append(sample.recover_scores_target)
        topo_t.append(sample.topology_target)
        topo_dist_t.append(sample.topology_target_dist)
        aux_t.append(sample.aux_target)
        batch_index.append(torch.full((n,), b, dtype=torch.long))
        offset += n
    return {
        "node_x": torch.cat(node_x, dim=0),
        "edge_index": torch.cat(edge_index, dim=1),
        "edge_attr": torch.cat(edge_attr, dim=0),
        "action_target_all": torch.cat(action_all_t, dim=0),
        "action_target_best": torch.cat(action_best_t, dim=0),
        "action_target_keep": torch.cat(action_keep_t, dim=0),
        "recover_target": torch.cat(recover_t, dim=0),
        "recover_scores_target": torch.cat(recover_scores_t, dim=0),
        "topology_target": torch.cat(topo_t, dim=0),
        "topology_target_dist": torch.cat(topo_dist_t, dim=0),
        "aux_target": torch.cat(aux_t, dim=0),
        "batch_index": torch.cat(batch_index, dim=0),
    }
