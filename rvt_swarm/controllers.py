from __future__ import annotations

from typing import Dict

import numpy as np

from .config import Config
from .utils import soft_clip, unit


def expert_action(obs: Dict, cfg: Config, topology_action: int = 0) -> np.ndarray:
    pos = obs["positions"]
    vel = obs["velocities"]
    goal = obs["goal"]
    form_err = obs["formation_error"]
    obstacles = obs["obstacles"]
    n = len(pos)
    actions = np.zeros((n, 2), dtype=np.float32)
    centroid = pos.mean(axis=0)
    progress_dir = unit(goal - centroid)
    corridor = np.array([obs.get("corridor_dx", 1.0), obs.get("corridor_dy", 0.0)], dtype=np.float32)
    lateral = np.array([corridor[1], -corridor[0]], dtype=np.float32)
    form_gain = 0.98 if topology_action in [0, 4] else 0.6
    if topology_action == 1:
        form_gain = 0.72
    elif topology_action == 2:
        form_gain = 0.48
    elif topology_action == 3:
        form_gain = 0.42
    for i in range(n):
        a = 0.75 * progress_dir + form_gain * form_err[i] - 0.32 * vel[i]
        if topology_action == 2:
            along = np.dot(form_err[i], corridor)
            a += 0.15 * along * corridor
        elif topology_action == 3:
            lane_sign = -1.0 if obs.get("subteam_ids", np.zeros((n,)))[i] == 0 else 1.0
            a += 0.18 * lane_sign * lateral + 0.08 * progress_dir
        elif topology_action == 1:
            a += 0.06 * progress_dir
        elif topology_action == 4:
            a += 0.22 * form_err[i] - 0.10 * vel[i] + 0.05 * progress_dir
        for j in range(n):
            if i == j:
                continue
            diff = pos[i] - pos[j]
            d = np.linalg.norm(diff)
            if d < 1.0:
                a += 0.32 * unit(diff) * max(0.0, 1.0 - d)
            if d > 1e-6 and d < 2.5:
                n_hat = diff / d
                dd_dt = np.dot(vel[i] - vel[j], n_hat)
                if dd_dt < -0.05:
                    ttc_approx = d / (-dd_dt)
                    if ttc_approx < 2.5:
                        urgency = max(0.0, 1.0 - ttc_approx / 2.5)
                        a += 0.35 * urgency * unit(diff)
        obs_vel = obs.get("obstacle_velocities", np.zeros_like(obstacles))
        for k, o in enumerate(obstacles):
            diff = pos[i] - o
            d = np.linalg.norm(diff)
            if d < 1.3:
                a += 0.9 * unit(diff) * max(0.0, 1.3 - d)
            if d > 1e-6 and d < 2.5:
                ov_k = obs_vel[k] if k < len(obs_vel) else np.zeros(2, dtype=np.float32)
                n_hat = diff / d
                dd_dt = np.dot(vel[i] - ov_k, n_hat)
                if dd_dt < -0.05:
                    ttc_approx = d / (-dd_dt)
                    if ttc_approx < 2.5:
                        urgency = max(0.0, 1.0 - ttc_approx / 2.5)
                        a += 0.5 * urgency * unit(diff)
        actions[i] = soft_clip(a, cfg.env.max_accel)
    return actions
