from __future__ import annotations

import math
from typing import Dict

import numpy as np
import torch

from .config import Config, LEARNED_TOPOLOGY_IDS, TOPOLOGY_IDS
from .utils import clip01, unit


def shield_risk_threshold(cfg: Config) -> float:
    return clip01(1.0 - (cfg.env.max_speed * cfg.env.dt) / max(cfg.env.nominal_spacing, 1e-6))


def time_to_collision(
    p1: np.ndarray, v1: np.ndarray,
    p2: np.ndarray, v2: np.ndarray,
    r_safe: float,
) -> float:
    """Compute time-to-collision for two circular agents.

    Solves the quadratic equation:
        ||p1 + v1*t - p2 - v2*t|| = r_safe
    for the smallest positive t.  Returns inf if no collision is predicted
    on the current linear trajectories.
    """
    dp = p2 - p1
    dv = v2 - v1
    a = float(np.dot(dv, dv))
    b = 2.0 * float(np.dot(dp, dv))
    c = float(np.dot(dp, dp)) - r_safe ** 2
    if c < 0.0:          # already overlapping
        return 0.0
    if a < 1e-12:         # negligible relative motion
        return float('inf')
    disc = b * b - 4.0 * a * c
    if disc < 0.0:        # trajectories never intersect
        return float('inf')
    t = (-b - np.sqrt(disc)) / (2.0 * a)
    return float(t) if t > 0.0 else float('inf')


def collision_risk(obs: Dict, cfg: Config, horizon: float | None = None) -> float:
    """Compute collision risk using both proximity AND predicted TTC.

    Predictive: uses relative velocities to anticipate future collisions,
    not just current distances.  Risk is high when TTC is short, even if
    agents are currently far apart.
    """
    horizon = horizon or max(cfg.env.dt, cfg.env.sensing_radius / max(cfg.env.max_speed, 1e-6))
    pos = obs["positions"]
    vel = obs["velocities"]
    obs_pos = obs["obstacles"]
    obs_vel = obs.get("obstacle_velocities", np.zeros_like(obs_pos))
    risk = 0.0
    rr_buffer = max(cfg.env.min_rr_distance, cfg.env.nominal_spacing)
    ro_buffer = max(cfg.env.min_ro_distance, cfg.env.robot_radius + cfg.env.obstacle_radius)
    for i in range(len(pos)):
        for j in range(i + 1, len(pos)):
            d = np.linalg.norm(pos[i] - pos[j])
            dist_risk = clip01(1.0 - d / max(rr_buffer, 1e-6))
            ttc = time_to_collision(pos[i], vel[i], pos[j], vel[j], rr_buffer)
            ttc_risk = clip01(1.0 - ttc / horizon) if ttc < horizon else 0.0
            predictive_risk = ttc_risk / (1.0 + d / max(rr_buffer, 1e-6))
            risk = max(risk, dist_risk, predictive_risk)
        for k, o in enumerate(obs_pos):
            d = np.linalg.norm(pos[i] - o)
            dist_risk = clip01(1.0 - d / max(ro_buffer, 1e-6))
            ov = obs_vel[k] if k < len(obs_vel) else np.zeros(2, dtype=np.float32)
            ttc = time_to_collision(pos[i], vel[i], o, ov, ro_buffer)
            ttc_risk = clip01(1.0 - ttc / horizon) if ttc < horizon else 0.0
            predictive_risk = ttc_risk / (1.0 + d / max(ro_buffer, 1e-6))
            risk = max(risk, dist_risk, predictive_risk)
    return float(risk)


def progress_direction(obs: Dict) -> np.ndarray:
    centroid = obs["positions"].mean(axis=0)
    return unit(obs["goal"] - centroid)


def estimated_form_rms(obs: Dict) -> float:
    formation_error = obs.get("formation_error")
    if formation_error is None or len(formation_error) == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.sum(np.square(formation_error), axis=1))))


def projected_adjustment_ratio(actions: np.ndarray, safe: np.ndarray, cfg: Config) -> float:
    delta = np.linalg.norm(safe - actions, axis=1)
    return clip01(float(np.mean(delta)) / max(cfg.env.max_accel, 1e-6))


def simple_recover_shield(
    actions: np.ndarray,
    obs: Dict,
    cfg: Config,
    recoverability: float | None = None,
    topo: int = 0,
    recoverability_scores: np.ndarray | None = None,
) -> np.ndarray:
    """Progress-preserving safety shield via per-robot CBF-QP.

    Implements the docs spec:
      • Shield only intervenes when collision risk is high OR when *all*
        topology options have negative recoverability (full crisis).
      • When triggered, solves a small per-robot QP:
            min_u  ||u - u_learned||²  -  w · (u · progress_dir)
            s.t.   CBF constraints  ∧  ||u|| ≤ max_accel
        to minimise constraint violation while preserving progress.
    """
    if not cfg.method.use_progress_shield:
        return actions
    threshold = shield_risk_threshold(cfg)
    risk = collision_risk(obs, cfg)

    # Recoverability is treated as a conservative warning signal only.
    # Positive scores should not "explain away" geometric collision risk.
    all_negative = False
    if recoverability_scores is not None:
        all_negative = bool(np.all(recoverability_scores < 0.0))
    if recoverability is not None:
        recover_value = float(recoverability)
        if recover_value < 0.0:
            neg_level = clip01(-recover_value)
            risk = max(risk, threshold + (1.0 - threshold) * neg_level)
    # Docs: "chỉ can thiệp nếu tất cả lựa chọn có recoverability âm"
    if all_negative:
        risk = max(risk, threshold)
    if risk < threshold:
        return actions

    # --- QP-based intervention ---
    progress_dir = progress_direction(obs)
    progress_w = cfg.env.max_accel * clip01(1.0 - risk)
    safe = actions.copy()
    for i in range(len(safe)):
        constraints = _build_cbf_constraints(i, obs, cfg)
        if not constraints:
            continue
        safe[i] = _solve_per_robot_qp(
            safe[i], constraints, progress_dir, cfg.env.max_accel, progress_w,
        )
    # Blend by the actual projected correction magnitude rather than a fixed cap.
    # This keeps the intervention scale-free across environments.
    adjustment = projected_adjustment_ratio(actions, safe, cfg)
    denom = max(1e-6, 1.0 - threshold)
    severity = float(np.clip((risk - threshold) / denom, 0.0, 1.0))
    blend = max(severity, adjustment)
    if all_negative and recoverability is not None:
        blend = max(blend, clip01(-float(recoverability)))
    return (1.0 - blend) * actions + blend * safe


# ── CBF-QP helpers ──────────────────────────────────────────────────

def _build_cbf_constraints(
    robot_idx: int, obs: Dict, cfg: Config,
) -> list:
    """Build linear CBF half-plane constraints for robot *robot_idx*.

    Each constraint is ``(a, b)`` meaning  ``a^T u >= b``.
    Derived from first-order CBF:  dh/dt + α h >= 0
    with barrier  h = ||p_i - p_j||² - d_safe².
    """
    pos = obs["positions"]
    vel = obs["velocities"]
    dt = cfg.env.dt
    pi, vi = pos[robot_idx], vel[robot_idx]
    constraints: list = []

    # Robot-robot
    d_safe_rr = max(cfg.env.min_rr_distance, 2.0 * cfg.env.robot_radius)
    active_rr = max(d_safe_rr, cfg.env.nominal_spacing)
    for j in range(len(pos)):
        if j == robot_idx:
            continue
        diff = pi - pos[j]
        dist_sq = float(np.dot(diff, diff))
        h = dist_sq - d_safe_rr ** 2
        if dist_sq > active_rr ** 2:
            continue
        rel_v = vi - vel[j]
        a = (2.0 * dt * diff).astype(np.float32)
        b = float(max(0.0, -h) - 2.0 * np.dot(diff, rel_v))
        constraints.append((a, b))

    # Robot-obstacle
    obs_pos = obs["obstacles"]
    obs_vel = obs.get("obstacle_velocities", np.zeros_like(obs_pos))
    d_safe_ro = max(cfg.env.min_ro_distance, cfg.env.robot_radius + cfg.env.obstacle_radius)
    active_ro = max(d_safe_ro, cfg.env.nominal_spacing)
    for k in range(len(obs_pos)):
        diff = pi - obs_pos[k]
        dist_sq = float(np.dot(diff, diff))
        h = dist_sq - d_safe_ro ** 2
        if dist_sq > active_ro ** 2:
            continue
        ov = obs_vel[k] if k < len(obs_vel) else np.zeros(2, dtype=np.float32)
        rel_v = vi - ov
        a = (2.0 * dt * diff).astype(np.float32)
        b = float(max(0.0, -h) - 2.0 * np.dot(diff, rel_v))
        constraints.append((a, b))

    return constraints


def _solve_per_robot_qp(
    u_nom: np.ndarray,
    constraints: list,
    progress_dir: np.ndarray,
    max_accel: float,
    progress_weight: float,
) -> np.ndarray:
    """Solve the 2D shield QP exactly by enumerating active-set candidates.

        min_u  ||u - u*||²
        s.t.   a_j^T u >= b_j   ∀ j   (CBF half-planes)
               ||u|| <= max_accel

    where  u* = u_nom + w · progress_dir  biases toward goal progress.
    In 2D, the optimum lies either:
      - in the interior,
      - on one active boundary,
      - or at the intersection of two active boundaries.
    We enumerate those candidates directly, so no iteration budget is needed.
    """
    u_target = np.asarray(u_nom + progress_weight * progress_dir, dtype=np.float64)
    target_x = float(u_target[0])
    target_y = float(u_target[1])
    radius = float(max_accel)
    machine_tol = np.finfo(np.float64).eps
    feasibility_tol = machine_tol * max(1.0, radius, math.hypot(target_x, target_y))

    processed_constraints: list[tuple[tuple[float, float], float]] = []
    for a, b_val in constraints:
        a64 = np.asarray(a, dtype=np.float64)
        ax = float(a64[0])
        ay = float(a64[1])
        a_sq = ax * ax + ay * ay
        if a_sq <= machine_tol:
            continue
        processed_constraints.append(((ax, ay), float(b_val)))

    def is_feasible(u: np.ndarray) -> bool:
        ux = float(u[0])
        uy = float(u[1])
        if ux * ux + uy * uy > radius * radius + feasibility_tol:
            return False
        for (ax, ay), b_val in processed_constraints:
            if ax * ux + ay * uy - b_val < -feasibility_tol:
                return False
        return True

    candidates: list[np.ndarray] = []

    def maybe_add(u: np.ndarray) -> None:
        ux = float(u[0])
        uy = float(u[1])
        if not (math.isfinite(ux) and math.isfinite(uy)):
            return
        candidate = np.array([ux, uy], dtype=np.float64)
        if is_feasible(candidate):
            candidates.append(candidate)

    def clip_to_ball(u: np.ndarray) -> np.ndarray:
        ux = float(u[0])
        uy = float(u[1])
        norm = math.hypot(ux, uy)
        if norm <= radius:
            return np.array([ux, uy], dtype=np.float64)
        scale = radius / max(norm, machine_tol)
        return np.array([ux * scale, uy * scale], dtype=np.float64)

    # Interior / ball-only candidate
    maybe_add(clip_to_ball(u_target.copy()))

    # Single active half-space boundary candidates
    for (ax, ay), b_val in processed_constraints:
        a_sq = ax * ax + ay * ay
        dot_target = ax * target_x + ay * target_y
        offset = (b_val - dot_target) / a_sq
        proj = np.array([target_x + offset * ax, target_y + offset * ay], dtype=np.float64)
        maybe_add(proj)

        # Line-circle intersections for cases where both a half-space and the ball are active
        norm_a = math.sqrt(a_sq)
        closest = np.array([(b_val / a_sq) * ax, (b_val / a_sq) * ay], dtype=np.float64)
        cx = float(closest[0])
        cy = float(closest[1])
        dist_sq = cx * cx + cy * cy
        if dist_sq <= radius * radius + feasibility_tol:
            tangent_sq = max(radius * radius - dist_sq, 0.0)
            tangent_dir = np.array([-ay / max(norm_a, machine_tol), ax / max(norm_a, machine_tol)], dtype=np.float64)
            tangent_mag = math.sqrt(tangent_sq)
            maybe_add(closest + tangent_mag * tangent_dir)
            maybe_add(closest - tangent_mag * tangent_dir)

    # Pairwise active half-space boundary intersections
    for i, ((a1x, a1y), b1) in enumerate(processed_constraints):
        for (a2x, a2y), b2 in processed_constraints[i + 1:]:
            det = a1x * a2y - a1y * a2x
            col_norm = max(abs(a1x) + abs(a2x), abs(a1y) + abs(a2y))
            row_norm = max(abs(a1x) + abs(a1y), abs(a2x) + abs(a2y))
            cond_scale = col_norm * row_norm
            if abs(det) <= machine_tol * max(cond_scale, 1.0):
                continue
            intersection = np.array(
                [
                    (b1 * a2y - a1y * b2) / det,
                    (a1x * b2 - b1 * a2x) / det,
                ],
                dtype=np.float64,
            )
            maybe_add(intersection)

    if not candidates:
        return clip_to_ball(u_target).astype(np.float32)

    best = min(
        candidates,
        key=lambda u: (float(u[0]) - target_x) ** 2 + (float(u[1]) - target_y) ** 2,
    )
    return best.astype(np.float32)


def _candidate_topology_ids(candidate_topologies: list[int] | None = None) -> list[int]:
    return list(candidate_topologies) if candidate_topologies is not None else list(TOPOLOGY_IDS)


def choose_topology_from_logits(
    topology_logits: torch.Tensor,
    candidate_topologies: list[int] | None = None,
) -> int:
    topology_ids = _candidate_topology_ids(candidate_topologies)
    return topology_ids[int(torch.argmax(topology_logits, dim=-1).item())]


def stable_topology_anchor(topology: int) -> int:
    # Only line/split are persistent topology modes in the environment.
    # keep/compress/recover all collapse back to mode 0 after one step.
    return topology if topology in (2, 3) else 0


def topology_context_features(
    obs: Dict,
    cfg: Config,
    previous_topology: int,
    candidate_topologies: list[int] | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    topology_ids = _candidate_topology_ids(candidate_topologies)
    previous_topology = stable_topology_anchor(previous_topology)
    form_rms = estimated_form_rms(obs)
    form_tol = max(cfg.env.formation_tolerance, 1e-6)
    bottleneck = clip01(float(obs["bottleneck"]))
    progress = clip01(float(obs["progress"]))
    split_active = clip01(float(obs.get("split_active", 0.0)))
    n_agents = int(len(obs["positions"]))
    # Use only the observed team size, not the configured training/eval roster.
    team_factor = clip01(1.0 - 1.0 / max(float(n_agents), 1.0))
    form_ratio = form_rms / form_tol
    form_stretch = clip01(max(form_ratio - 1.0, 0.0))
    form_quality = clip01(1.0 - form_stretch)
    open_space = clip01(1.0 - bottleneck)

    allowed = np.ones(len(topology_ids), dtype=bool)
    context = np.zeros((len(topology_ids), 4), dtype=np.float32)
    idx_by_topology = {topo: idx for idx, topo in enumerate(topology_ids)}

    keep_idx = idx_by_topology.get(0)
    compress_idx = idx_by_topology.get(1)
    line_idx = idx_by_topology.get(2)
    split_idx = idx_by_topology.get(3)
    recover_idx = idx_by_topology.get(4)

    if split_idx is not None and n_agents < 4:
        allowed[split_idx] = False
    if keep_idx is not None:
        context[keep_idx] = np.array([open_space, form_quality, progress, 1.0 - split_active], dtype=np.float32)
    if compress_idx is not None:
        context[compress_idx] = np.array([bottleneck, 1.0 - split_active, 1.0 - progress, form_stretch], dtype=np.float32)
    if line_idx is not None:
        context[line_idx] = np.array([bottleneck, team_factor, 1.0 - split_active, progress], dtype=np.float32)
    if split_idx is not None:
        context[split_idx] = np.array([bottleneck, split_active, team_factor, progress], dtype=np.float32)
    if recover_idx is not None:
        context[recover_idx] = np.array([split_active, form_stretch, open_space, 1.0 - bottleneck], dtype=np.float32)

    if previous_topology in (2, 3):
        if recover_idx is not None:
            context[recover_idx, 2] = max(float(context[recover_idx, 2]), open_space)
        if keep_idx is not None:
            context[keep_idx, 1] = max(float(context[keep_idx, 1]), form_quality)

    return allowed, context


def topology_switch_readiness(
    obs: Dict,
    previous_topology: int,
    candidate_topologies: list[int] | None = None,
) -> np.ndarray:
    topology_ids = _candidate_topology_ids(candidate_topologies)
    previous_topology = stable_topology_anchor(previous_topology)
    time_since_switch = max(float(obs.get("time_since_switch", 0.0)), 0.0)
    switch_ready = np.ones(len(topology_ids), dtype=np.float32)
    for idx, topo in enumerate(topology_ids):
        if topo != previous_topology:
            switch_ready[idx] = float(time_since_switch / (1.0 + time_since_switch))
    return switch_ready


def select_topology_from_score_signal(
    score_signal: np.ndarray,
    allowed: np.ndarray,
    context: np.ndarray,
    previous_topology: int = 0,
    prior: np.ndarray | None = None,
    uncertainty: np.ndarray | None = None,
    switch_ready: np.ndarray | None = None,
    candidate_topologies: list[int] | None = None,
) -> int:
    topology_ids = _candidate_topology_ids(candidate_topologies)
    previous_topology = stable_topology_anchor(previous_topology)
    if previous_topology not in topology_ids:
        previous_topology = 0 if 0 in topology_ids else topology_ids[0]
    current_idx = topology_ids.index(previous_topology)
    keep_idx = topology_ids.index(0) if 0 in topology_ids else current_idx
    prior_arr = np.asarray(prior, dtype=np.float32) if prior is not None else np.zeros_like(score_signal, dtype=np.float32)
    uncert_arr = (
        np.asarray(uncertainty, dtype=np.float32)
        if uncertainty is not None
        else np.zeros_like(score_signal, dtype=np.float32)
    )
    switch_arr = (
        np.asarray(switch_ready, dtype=np.float32)
        if switch_ready is not None
        else np.ones_like(score_signal, dtype=np.float32)
    )

    recoverable = np.flatnonzero(allowed & (score_signal >= 0.0))
    candidates = recoverable if recoverable.size else np.flatnonzero(allowed)
    if candidates.size == 0:
        return topology_ids[current_idx]

    current_score = float(score_signal[current_idx])
    keep_score = float(score_signal[keep_idx])
    if bool(allowed[current_idx]) and current_score >= 0.0:
        # Persistent structural modes should not churn while they remain inside
        # the recoverable set. Exit back to keep only when keep is itself
        # recoverable and no worse, which gives a zero-margin, score-based
        # return path without hand-tuned dwell times.
        if current_idx != keep_idx and bool(allowed[keep_idx]) and keep_score >= current_score:
            return topology_ids[keep_idx]
        return topology_ids[current_idx]

    if keep_idx in candidates.tolist():
        if not np.any(score_signal[candidates] > keep_score):
            return topology_ids[keep_idx]

    def candidate_key(idx: int) -> tuple[float, ...]:
        stay_pref = 1.0 if topology_ids[idx] == previous_topology else 0.0
        keep_pref = 1.0 if topology_ids[idx] == 0 else 0.0
        return (
            float(score_signal[idx] >= 0.0),
            float(score_signal[idx]),
            keep_pref,
            stay_pref,
            float(switch_arr[idx]),
            -float(uncert_arr[idx]),
            float(context[idx, 0]),
            float(context[idx, 1]),
            float(context[idx, 2]),
            float(context[idx, 3]),
            float(prior_arr[idx]),
        )

    best_idx = max(candidates.tolist(), key=candidate_key)
    return topology_ids[best_idx]


def choose_counterfactual_topology(
    obs: Dict,
    topology_logits: torch.Tensor,
    recoverability_scores: torch.Tensor | None,
    cfg: Config,
    previous_topology: int = 0,
    uncertainty: torch.Tensor | None = None,
) -> int:
    logit_choice = choose_topology_from_logits(topology_logits, candidate_topologies=LEARNED_TOPOLOGY_IDS)
    if not cfg.method.use_counterfactual_topology:
        return logit_choice
    if recoverability_scores is None or not cfg.method.use_recoverability:
        return logit_choice

    scores = recoverability_scores.squeeze(0).detach().cpu().numpy().astype(np.float32)
    # When the recoverability score map is available, topology selection should
    # be driven by that map directly. Keep the classifier prior neutral here so
    # it cannot override the recoverability-margin ordering.
    prior = np.zeros_like(scores, dtype=np.float32)
    uncert = uncertainty.squeeze(0).detach().cpu().numpy().astype(np.float32) if uncertainty is not None else np.zeros_like(scores)
    score_signal = np.tanh(scores)
    allowed, context = topology_context_features(
        obs,
        cfg,
        previous_topology,
        candidate_topologies=LEARNED_TOPOLOGY_IDS,
    )
    switch_ready = topology_switch_readiness(
        obs,
        previous_topology,
        candidate_topologies=LEARNED_TOPOLOGY_IDS,
    )
    return select_topology_from_score_signal(
        score_signal,
        allowed,
        context,
        previous_topology=previous_topology,
        prior=prior,
        uncertainty=uncert,
        switch_ready=switch_ready,
        candidate_topologies=LEARNED_TOPOLOGY_IDS,
    )
