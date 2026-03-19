from __future__ import annotations

from typing import Dict

import numpy as np

from .config import Config
from .utils import clip01, normalized_mean, soft_clip, unit


def _clearance_term(diff: np.ndarray, active_distance: float) -> np.ndarray:
    d = np.linalg.norm(diff)
    if d <= 1e-6 or d >= active_distance:
        return np.zeros(2, dtype=np.float32)
    return unit(diff) * clip01(1.0 - d / max(active_distance, 1e-6))


def _ttc_term(diff: np.ndarray, rel_vel: np.ndarray, horizon: float) -> np.ndarray:
    d = np.linalg.norm(diff)
    if d <= 1e-6:
        return np.zeros(2, dtype=np.float32)
    normal = diff / d
    closing_speed = float(-np.dot(rel_vel, normal))
    if closing_speed <= 0.0:
        return np.zeros(2, dtype=np.float32)
    ttc = d / max(closing_speed, 1e-6)
    return unit(diff) * clip01(1.0 - ttc / max(horizon, 1e-6))


def _mean_vector(terms: list[np.ndarray]) -> np.ndarray:
    if not terms:
        return np.zeros(2, dtype=np.float32)
    return np.mean(np.stack(terms, axis=0), axis=0).astype(np.float32)


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
    spacing = max(cfg.env.nominal_spacing, 1e-6)
    rr_active = max(cfg.env.nominal_spacing, cfg.env.min_rr_distance)
    ro_active = max(cfg.env.nominal_spacing, cfg.env.min_ro_distance)
    horizon = max(cfg.env.dt, cfg.env.sensing_radius / max(cfg.env.max_speed, 1e-6))
    for i in range(n):
        base_terms = [
            progress_dir,
            form_err[i] / spacing,
            -vel[i] / max(cfg.env.max_speed, 1e-6),
        ]
        if topology_action == 2:
            along = np.dot(form_err[i], corridor)
            base_terms.append(corridor * (along / spacing))
        elif topology_action == 3:
            lane_sign = -1.0 if obs.get("subteam_ids", np.zeros((n,)))[i] == 0 else 1.0
            base_terms.append(lane_sign * lateral)
            base_terms.append(progress_dir)
        elif topology_action == 1:
            base_terms.append(form_err[i] / spacing)
        elif topology_action == 4:
            base_terms.append(form_err[i] / spacing)
            base_terms.append(-vel[i] / max(cfg.env.max_speed, 1e-6))
        for j in range(n):
            if i == j:
                continue
            diff = pos[i] - pos[j]
            base_terms.append(_clearance_term(diff, rr_active))
            base_terms.append(_ttc_term(diff, vel[i] - vel[j], horizon))
        obs_vel = obs.get("obstacle_velocities", np.zeros_like(obstacles))
        for k, o in enumerate(obstacles):
            diff = pos[i] - o
            ov_k = obs_vel[k] if k < len(obs_vel) else np.zeros(2, dtype=np.float32)
            base_terms.append(_clearance_term(diff, ro_active))
            base_terms.append(_ttc_term(diff, vel[i] - ov_k, horizon))
        actions[i] = soft_clip(_mean_vector(base_terms), cfg.env.max_accel)
    return actions
