from __future__ import annotations

from typing import Dict, Tuple

import numpy as np

from .config import Config
from .environment import expert_action
from .utils import soft_clip, unit


def orca_like(obs: Dict, cfg: Config) -> Tuple[np.ndarray, int]:
    pos = obs["positions"]
    vel = obs["velocities"]
    goal = obs["goal"]
    n = len(pos)
    actions = np.zeros((n, 2), dtype=np.float32)
    centroid = pos.mean(axis=0)
    desired = unit(goal - centroid)
    for i in range(n):
        a = 0.7 * desired - 0.2 * vel[i]
        for j in range(n):
            if i == j:
                continue
            diff = pos[i] - pos[j]
            d = np.linalg.norm(diff)
            if d < 1.3:
                a += 0.8 * unit(diff) * max(0.0, 1.3 - d)
        for o in obs["obstacles"]:
            diff = pos[i] - o
            d = np.linalg.norm(diff)
            if d < 1.2:
                a += 0.7 * unit(diff) * max(0.0, 1.2 - d)
        actions[i] = soft_clip(a, cfg.env.max_accel)
    return actions, 0


def adaptive_formation(obs: Dict, cfg: Config) -> Tuple[np.ndarray, int]:
    if obs["bottleneck"] > 0.5:
        topo = 2 if len(obs["positions"]) <= 8 else 3
    else:
        topo = 4 if obs["progress"] > 0.82 else (1 if obs["progress"] < 0.35 else 0)
    actions = expert_action(obs, cfg, topo)
    return actions, topo


def cbf_qp_like(obs: Dict, cfg: Config) -> Tuple[np.ndarray, int]:
    actions = expert_action(obs, cfg, 0)
    pos = obs["positions"]
    for i in range(len(pos)):
        repel = np.zeros(2, dtype=np.float32)
        for j in range(len(pos)):
            if i == j:
                continue
            diff = pos[i] - pos[j]
            d = np.linalg.norm(diff)
            if d < 1.1:
                repel += unit(diff) * (1.1 - d)
        for o in obs["obstacles"]:
            diff = pos[i] - o
            d = np.linalg.norm(diff)
            if d < 1.0:
                repel += 1.6 * unit(diff) * (1.0 - d)
        actions[i] = soft_clip(actions[i] + 0.6 * repel, cfg.env.max_accel)
    return actions, 0


def centralized_mpc_proxy(obs: Dict, cfg: Config) -> Tuple[np.ndarray, int]:
    topo = 2 if obs["bottleneck"] > 0.5 else (4 if obs["progress"] > 0.8 else 0)
    actions = expert_action(obs, cfg, topo)
    centroid = obs["positions"].mean(axis=0)
    goal_dir = unit(obs["goal"] - centroid)
    actions += 0.08 * goal_dir[None, :]
    return np.array([soft_clip(a, cfg.env.max_accel) for a in actions], dtype=np.float32), topo


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
