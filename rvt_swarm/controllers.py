from __future__ import annotations

from typing import Dict

import numpy as np

from .config import Config
from .utils import clip01, soft_clip, unit, vec_norm


def _subteam_assignments(pos: np.ndarray, corridor: np.ndarray) -> np.ndarray:
    lateral = np.array([corridor[1], -corridor[0]], dtype=np.float32)
    lat = pos @ lateral
    order = np.argsort(lat)
    split = np.zeros((len(pos),), dtype=np.int64)
    half = int(np.ceil(len(pos) / 2))
    split[order[half:]] = 1
    return split


def _project_topology_state(obs: Dict, cfg: Config, topology_action: int) -> tuple[int, float, np.ndarray]:
    mode = int(obs.get("topology_mode", 0))
    scale = float(obs.get("formation_scale", 1.0))
    bottleneck = clip01(float(obs.get("bottleneck", 0.0)))
    open_space = clip01(1.0 - bottleneck)
    split_active = clip01(float(obs.get("split_active", 0.0)))
    adaptive_scale = bool(cfg.method.use_adaptive_formation_scale)
    min_scale = clip01(cfg.env.min_rr_distance / max(cfg.env.nominal_spacing, 1e-6))
    corridor = np.array([obs.get("corridor_dx", 1.0), obs.get("corridor_dy", 0.0)], dtype=np.float32)
    subteam_ids = np.asarray(obs.get("subteam_ids"), dtype=np.int64)
    if subteam_ids.shape[0] != len(obs["positions"]):
        subteam_ids = np.zeros((len(obs["positions"]),), dtype=np.int64)

    if topology_action == 1:  # compress
        mode = 0
        target_scale = max(min_scale, 1.0 - bottleneck * (1.0 - min_scale))
        if adaptive_scale:
            scale = float(np.clip(scale + (target_scale - scale) * bottleneck, min_scale, 1.0))
        split_active = clip01(split_active * open_space)
    elif topology_action == 2:  # line
        mode = 2
        target_scale = max(min_scale, min(scale, 1.0 - bottleneck * (1.0 - min_scale)))
        blend = max(bottleneck, split_active)
        if adaptive_scale:
            scale = float(np.clip(scale + (target_scale - scale) * blend, min_scale, 1.0))
        split_active = clip01(split_active * open_space)
    elif topology_action == 3:  # split
        mode = 3
        subteam_ids = _subteam_assignments(obs["positions"], corridor)
        if adaptive_scale:
            scale = float(np.clip(scale + bottleneck * (1.0 - scale), min_scale, 1.0))
        split_active = clip01(split_active + bottleneck)
    elif topology_action == 4:  # recover
        mode = 0
        if adaptive_scale:
            scale = float(np.clip(scale + (1.0 - scale) * max(open_space, split_active), min_scale, 1.0))
        split_active = clip01(split_active * bottleneck)
        subteam_ids = np.zeros_like(subteam_ids)
    else:  # keep
        mode = mode if bottleneck > open_space else 0
        target_scale = max(min_scale, 1.0 - bottleneck * (1.0 - min_scale))
        if adaptive_scale:
            scale = float(np.clip(scale + (target_scale - scale) * bottleneck, min_scale, 1.0))
        split_active = clip01(split_active * open_space)

    if not adaptive_scale:
        scale = 1.0
    return mode, scale, subteam_ids


def _desired_offsets(obs: Dict, cfg: Config, mode: int, scale: float, subteam_ids: np.ndarray) -> np.ndarray:
    pos = obs["positions"]
    n = len(pos)
    spacing = cfg.env.nominal_spacing * scale
    corridor = np.array([obs.get("corridor_dx", 1.0), obs.get("corridor_dy", 0.0)], dtype=np.float32)
    lateral = np.array([corridor[1], -corridor[0]], dtype=np.float32)

    if mode == 2:
        order = np.argsort(pos @ corridor)
        offsets = np.zeros((n, 2), dtype=np.float32)
        for rank, robot_idx in enumerate(order):
            offsets[robot_idx] = corridor * ((rank - (n - 1) / 2) * spacing)
        return offsets

    if mode == 3:
        counts = [max(1, int(np.sum(subteam_ids == 0))), max(1, int(np.sum(subteam_ids == 1)))]
        lane_gap = max(cfg.env.nominal_spacing, spacing + cfg.env.min_rr_distance)
        offsets = np.zeros((n, 2), dtype=np.float32)
        for team_id in (0, 1):
            members = np.flatnonzero(subteam_ids == team_id)
            if members.size == 0:
                continue
            order = members[np.argsort(pos[members] @ corridor)]
            for rank, robot_idx in enumerate(order):
                longitudinal = (rank - (counts[team_id] - 1) / 2) * spacing
                lane_offset = -lateral if team_id == 0 else lateral
                offsets[robot_idx] = corridor * longitudinal + lane_offset * (0.5 * lane_gap)
        return offsets

    cols = max(2, int(np.ceil(np.sqrt(n))))
    rows = int(np.ceil(n / cols))
    offsets = []
    for i in range(n):
        r, c = divmod(i, cols)
        offsets.append(
            lateral * ((c - (cols - 1) / 2) * spacing)
            + corridor * ((r - (rows - 1) / 2) * spacing)
        )
    return np.array(offsets, dtype=np.float32)


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
    obstacles = obs["obstacles"]
    n = len(pos)
    actions = np.zeros((n, 2), dtype=np.float32)
    centroid = pos.mean(axis=0)
    progress_dir = unit(goal - centroid)
    corridor = np.array([obs.get("corridor_dx", 1.0), obs.get("corridor_dy", 0.0)], dtype=np.float32)
    lateral = np.array([corridor[1], -corridor[0]], dtype=np.float32)
    mode, scale, subteam_ids = _project_topology_state(obs, cfg, topology_action)
    offsets = _desired_offsets(obs, cfg, mode, scale, subteam_ids)
    target_positions = centroid + offsets
    form_err = target_positions - pos
    spacing = max(cfg.env.nominal_spacing, 1e-6)
    max_speed = max(cfg.env.max_speed, 1e-6)
    rr_active = max(cfg.env.nominal_spacing, cfg.env.min_rr_distance)
    ro_active = max(cfg.env.nominal_spacing, cfg.env.min_ro_distance)
    horizon = max(cfg.env.dt, cfg.env.sensing_radius / max(cfg.env.max_speed, 1e-6))
    obs_vel = obs.get("obstacle_velocities")
    if obs_vel is None:
        obs_vel = np.zeros_like(obstacles)
    for i in range(n):
        progress_weight = 1.0
        if topology_action == 2:
            lateral_err = abs(float(np.dot(form_err[i], lateral)))
            progress_weight = clip01(1.0 - lateral_err / spacing)
        elif topology_action == 3:
            progress_weight = clip01(1.0 - vec_norm(form_err[i]) / spacing)
        base_terms = [
            progress_dir * progress_weight,
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
