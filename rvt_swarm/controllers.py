from __future__ import annotations

from typing import Dict

import numpy as np

from .config import Config
from .utils import clip01, soft_clip, unit, vec_norm


def _clearance_term(diff: np.ndarray, active_distance: float) -> np.ndarray:
    d = vec_norm(diff)
    if d <= 1e-6 or d >= active_distance:
        return np.zeros(2, dtype=np.float32)
    scale = clip01(1.0 - d / max(active_distance, 1e-6)) / d
    return (diff * scale).astype(np.float32)


def _ttc_term(diff: np.ndarray, rel_vel: np.ndarray, horizon: float) -> np.ndarray:
    d = vec_norm(diff)
    if d <= 1e-6:
        return np.zeros(2, dtype=np.float32)
    normal = diff / d
    closing_speed = float(-np.dot(rel_vel, normal))
    if closing_speed <= 0.0:
        return np.zeros(2, dtype=np.float32)
    ttc = d / max(closing_speed, 1e-6)
    scale = clip01(1.0 - ttc / max(horizon, 1e-6)) / d
    return (diff * scale).astype(np.float32)


def _mean_vector(terms: list[np.ndarray]) -> np.ndarray:
    if not terms:
        return np.zeros(2, dtype=np.float32)
    acc = np.zeros(2, dtype=np.float32)
    for term in terms:
        acc += term
    return acc / float(len(terms))


def _sum_group_means(*groups: list[np.ndarray]) -> np.ndarray:
    total = np.zeros(2, dtype=np.float32)
    used = False
    for group in groups:
        if not group:
            continue
        total += _mean_vector(group)
        used = True
    return total if used else np.zeros(2, dtype=np.float32)


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
    max_speed = max(cfg.env.max_speed, 1e-6)
    rr_active = max(cfg.env.nominal_spacing, cfg.env.min_rr_distance)
    ro_active = max(cfg.env.nominal_spacing, cfg.env.min_ro_distance)
    horizon = max(cfg.env.dt, cfg.env.sensing_radius / max(cfg.env.max_speed, 1e-6))
    subteam_ids = obs.get("subteam_ids")
    if subteam_ids is None or len(subteam_ids) != n:
        subteam_ids = np.zeros((n,), dtype=np.int64)
    obs_vel = obs.get("obstacle_velocities")
    if obs_vel is None:
        obs_vel = np.zeros_like(obstacles)
    for i in range(n):
        base_terms = [
            progress_dir,
            form_err[i] / spacing,
            -vel[i] / max_speed,
        ]
        rr_clear_terms: list[np.ndarray] = []
        rr_ttc_terms: list[np.ndarray] = []
        ro_clear_terms: list[np.ndarray] = []
        ro_ttc_terms: list[np.ndarray] = []
        if topology_action == 2:
            along = np.dot(form_err[i], corridor)
            base_terms.append(corridor * (along / spacing))
        elif topology_action == 3:
            lane_sign = -1.0 if subteam_ids[i] == 0 else 1.0
            base_terms.append(lane_sign * lateral)
            base_terms.append(progress_dir)
        elif topology_action == 1:
            base_terms.append(form_err[i] / spacing)
        elif topology_action == 4:
            base_terms.append(form_err[i] / spacing)
            base_terms.append(-vel[i] / max_speed)
        for j in range(n):
            if i == j:
                continue
            diff = pos[i] - pos[j]
            rr_clear_terms.append(_clearance_term(diff, rr_active))
            rr_ttc_terms.append(_ttc_term(diff, vel[i] - vel[j], horizon))
        for k, o in enumerate(obstacles):
            diff = pos[i] - o
            ov_k = obs_vel[k] if k < len(obs_vel) else np.zeros(2, dtype=np.float32)
            ro_clear_terms.append(_clearance_term(diff, ro_active))
            ro_ttc_terms.append(_ttc_term(diff, vel[i] - ov_k, horizon))
        action_vec = _sum_group_means(
            base_terms,
            rr_clear_terms,
            rr_ttc_terms,
            ro_clear_terms,
            ro_ttc_terms,
        )
        actions[i] = soft_clip(action_vec, cfg.env.max_accel)
    return actions
