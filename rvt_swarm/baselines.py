from __future__ import annotations

from typing import Dict, Tuple

import numpy as np

from .config import Config
from .controllers import expert_action
from .utils import clip01, soft_clip, unit


def _repulsion(diff: np.ndarray, active_distance: float) -> np.ndarray:
    d = np.linalg.norm(diff)
    if d <= 1e-6 or d >= active_distance:
        return np.zeros(2, dtype=np.float32)
    return unit(diff) * clip01(1.0 - d / max(active_distance, 1e-6))


def orca_like(obs: Dict, cfg: Config) -> Tuple[np.ndarray, int]:
    pos = obs["positions"]
    vel = obs["velocities"]
    goal = obs["goal"]
    n = len(pos)
    actions = np.zeros((n, 2), dtype=np.float32)
    centroid = pos.mean(axis=0)
    desired = unit(goal - centroid)
    rr_active = max(cfg.env.nominal_spacing, cfg.env.min_rr_distance)
    ro_active = max(cfg.env.nominal_spacing, cfg.env.min_ro_distance)
    for i in range(n):
        terms = [
            desired,
            -vel[i] / max(cfg.env.max_speed, 1e-6),
        ]
        for j in range(n):
            if i == j:
                continue
            terms.append(_repulsion(pos[i] - pos[j], rr_active))
        for o in obs["obstacles"]:
            terms.append(_repulsion(pos[i] - o, ro_active))
        actions[i] = soft_clip(np.mean(np.stack(terms, axis=0), axis=0), cfg.env.max_accel)
    return actions, 0


def adaptive_formation(obs: Dict, cfg: Config) -> Tuple[np.ndarray, int]:
    open_space = clip01(1.0 - float(obs["bottleneck"]))
    if obs["bottleneck"] > open_space:
        topo = 2 if len(obs["positions"]) <= 8 else 3
    else:
        topo = 4 if float(obs.get("recovery_progress", 0.0)) < float(obs["progress"]) else 0
    actions = expert_action(obs, cfg, topo)
    return actions, topo


def cbf_qp_like(obs: Dict, cfg: Config) -> Tuple[np.ndarray, int]:
    actions = expert_action(obs, cfg, 0)
    pos = obs["positions"]
    rr_active = max(cfg.env.nominal_spacing, cfg.env.min_rr_distance)
    ro_active = max(cfg.env.nominal_spacing, cfg.env.min_ro_distance)
    for i in range(len(pos)):
        repel = np.zeros(2, dtype=np.float32)
        for j in range(len(pos)):
            if i == j:
                continue
            repel += _repulsion(pos[i] - pos[j], rr_active)
        for o in obs["obstacles"]:
            repel += _repulsion(pos[i] - o, ro_active)
        actions[i] = soft_clip(actions[i] + repel, cfg.env.max_accel)
    return actions, 0


def centralized_mpc_proxy(obs: Dict, cfg: Config) -> Tuple[np.ndarray, int]:
    open_space = clip01(1.0 - float(obs["bottleneck"]))
    topo = 2 if obs["bottleneck"] > open_space else (4 if float(obs.get("recovery_progress", 0.0)) < float(obs["progress"]) else 0)
    actions = expert_action(obs, cfg, topo)
    centroid = obs["positions"].mean(axis=0)
    goal_dir = unit(obs["goal"] - centroid)
    mixed = []
    for a in actions:
        terms = [a / max(cfg.env.max_accel, 1e-6), goal_dir]
        mixed.append(soft_clip(np.mean(np.stack(terms, axis=0), axis=0), cfg.env.max_accel))
    return np.array(mixed, dtype=np.float32), topo


def historical_baseline(name: str, obs: Dict, cfg: Config) -> Tuple[np.ndarray, int]:
    if name == "adaptive_formation":
        return adaptive_formation(obs, cfg)
    if name == "cbf_qp_like":
        return cbf_qp_like(obs, cfg)
    if name == "orca_like":
        return orca_like(obs, cfg)
    if name == "centralized_mpc":
        return centralized_mpc_proxy(obs, cfg)
    raise ValueError(name)
