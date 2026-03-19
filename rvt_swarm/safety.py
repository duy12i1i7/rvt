from __future__ import annotations

from typing import Dict

import numpy as np
import torch

from .config import Config, TOPOLOGY_IDS
from .utils import clip01, normalized_mean, soft_clip, unit


def selector_temperature(cfg: Config) -> float:
    spacing_ratio = cfg.env.nominal_spacing / max(cfg.env.sensing_radius, 1e-6)
    motion_ratio = (cfg.env.max_speed * cfg.env.dt) / max(cfg.env.min_rr_distance, 1e-6)
    return max(1.0, 1.0 + spacing_ratio + motion_ratio)


def selector_cooldown(cfg: Config) -> int:
    horizon_ratio = (
        cfg.train.recover_horizon
        * cfg.env.max_speed
        * cfg.env.dt
        / max(cfg.env.min_rr_distance, 1e-6)
    )
    return max(1, int(round(horizon_ratio + len(cfg.env.team_sizes))))


def switch_hysteresis_margin(cfg: Config) -> float:
    return clip01(cfg.env.min_rr_distance / max(cfg.env.sensing_radius, 1e-6))


def shield_risk_threshold(cfg: Config) -> float:
    return clip01(1.0 - (cfg.env.max_speed * cfg.env.dt) / max(cfg.env.nominal_spacing, 1e-6))


def shield_blend_limit(cfg: Config) -> float:
    progress_ratio = (cfg.env.max_speed * cfg.env.dt) / max(cfg.env.nominal_spacing, 1e-6)
    clearance_ratio = cfg.env.min_rr_distance / max(cfg.env.nominal_spacing, 1e-6)
    return clip01(progress_ratio * clearance_ratio)


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
    form_rms = estimated_form_rms(obs)
    form_ratio = form_rms / max(cfg.env.formation_tolerance, 1e-6)

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
    if not all_negative:
        cooldown = max(float(selector_cooldown(cfg)), 1.0)
        time_since_switch = float(obs.get("time_since_switch", cooldown))
        switch_guard = clip01((cooldown - time_since_switch) / cooldown)
        threshold = min(1.0, threshold + (1.0 - threshold) * switch_guard * clip01(1.0 - form_ratio))
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
    max_blend = shield_blend_limit(cfg)
    # Soft blend avoids over-damping learned policy when shield activates.
    denom = max(1e-6, 1.0 - threshold)
    severity = float(np.clip((risk - threshold) / denom, 0.0, 1.0))
    blend = severity * max_blend
    if all_negative and recoverability is not None:
        blend = max(blend, max_blend * clip01(-float(recoverability)))
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
    progress_weight: float = 0.05,
    n_iters: int = 25,
) -> np.ndarray:
    """Solve a small QP via iterative half-plane projection (Dykstra).

        min_u  ||u - u*||²
        s.t.   a_j^T u >= b_j   ∀ j   (CBF half-planes)
               ||u|| <= max_accel

    where  u* = u_nom + w · progress_dir  biases toward goal progress.
    Converges for convex feasible sets (all constraints are half-planes + ball).
    """
    u_target = u_nom + progress_weight * progress_dir
    u = u_target.copy().astype(np.float64)

    for _ in range(n_iters):
        # Project onto each CBF half-plane
        for a, b_val in constraints:
            a = a.astype(np.float64)
            margin = np.dot(a, u) - b_val
            if margin < 0.0:
                a_sq = np.dot(a, a)
                if a_sq > 1e-12:
                    u += (-margin / a_sq) * a
        # Project onto acceleration ball
        norm = np.linalg.norm(u)
        if norm > max_accel:
            u *= max_accel / norm

    return u.astype(np.float32)


def choose_topology_from_logits(topology_logits: torch.Tensor) -> int:
    return TOPOLOGY_IDS[int(torch.argmax(topology_logits, dim=-1).item())]


def topology_context_mask(obs: Dict, cfg: Config, previous_topology: int) -> tuple[np.ndarray, np.ndarray]:
    form_rms = estimated_form_rms(obs)
    form_tol = max(cfg.env.formation_tolerance, 1e-6)
    bottleneck = clip01(float(obs["bottleneck"]))
    progress = clip01(float(obs["progress"]))
    split_active = clip01(float(obs.get("split_active", 0.0)))
    n_agents = int(len(obs["positions"]))
    team_factor = clip01(n_agents / max(cfg.env.team_sizes))
    form_ratio = form_rms / form_tol
    form_stretch = clip01(max(form_ratio - 1.0, 0.0))
    form_quality = clip01(1.0 - form_stretch)
    open_space = clip01(1.0 - bottleneck)

    allowed = np.ones(len(TOPOLOGY_IDS), dtype=bool)
    context = np.zeros(len(TOPOLOGY_IDS), dtype=np.float32)

    keep_idx = TOPOLOGY_IDS.index(0)
    compress_idx = TOPOLOGY_IDS.index(1)
    line_idx = TOPOLOGY_IDS.index(2)
    split_idx = TOPOLOGY_IDS.index(3)
    recover_idx = TOPOLOGY_IDS.index(4)

    if n_agents < 4:
        allowed[split_idx] = False
    keep_signal = open_space * normalized_mean([form_quality, progress])
    compress_signal = bottleneck * normalized_mean([1.0 - split_active, 1.0 - progress])
    line_signal = bottleneck * normalized_mean([1.0, team_factor, 1.0 - split_active])
    split_signal = bottleneck * split_active * team_factor
    recover_signal = normalized_mean([open_space, split_active, form_stretch])

    context[keep_idx] += keep_signal
    context[compress_idx] += compress_signal
    context[line_idx] += line_signal
    context[split_idx] += split_signal
    context[recover_idx] += recover_signal

    if previous_topology in (2, 3):
        context[recover_idx] += open_space * split_active
        context[keep_idx] += open_space * form_quality

    return allowed, context


def choose_counterfactual_topology(
    obs: Dict,
    topology_logits: torch.Tensor,
    recoverability_scores: torch.Tensor | None,
    cfg: Config,
    previous_topology: int = 0,
    uncertainty: torch.Tensor | None = None,
) -> int:
    topo_prior = torch.softmax(topology_logits / selector_temperature(cfg), dim=-1).squeeze(0)
    logit_choice = choose_topology_from_logits(topology_logits)
    if recoverability_scores is None or not cfg.method.use_counterfactual_topology:
        return logit_choice

    scores = recoverability_scores.squeeze(0).detach().cpu().numpy().astype(np.float32)
    prior = topo_prior.detach().cpu().numpy().astype(np.float32)
    uncert = uncertainty.squeeze(0).detach().cpu().numpy().astype(np.float32) if uncertainty is not None else np.zeros_like(scores)
    score_signal = np.tanh(scores)
    mean_uncert = float(np.mean(uncert))
    allowed, context = topology_context_mask(obs, cfg, previous_topology)
    invalid_penalty = np.where(allowed, 0.0, -1.0).astype(np.float32)

    switch_penalty = np.zeros_like(scores)
    bottleneck = clip01(float(obs["bottleneck"]))
    split_active = clip01(float(obs.get("split_active", 0.0)))
    cooldown = float(selector_cooldown(cfg))
    time_since_switch = float(obs.get("time_since_switch", 999.0))
    cooldown_frac = float(np.clip((cooldown - time_since_switch) / max(cooldown, 1.0), 0.0, 1.0))
    for idx, topo in enumerate(TOPOLOGY_IDS):
        if topo != previous_topology:
            switch_penalty[idx] += normalized_mean([1.0, cooldown_frac])
        if topo in (2, 3, 4):
            switch_penalty[idx] += normalized_mean([bottleneck, split_active])
        if topo == 0:
            switch_penalty[idx] += bottleneck * split_active

    current_idx = TOPOLOGY_IDS.index(previous_topology)
    logit_idx = TOPOLOGY_IDS.index(logit_choice)
    if not allowed[logit_idx]:
        allowed_scores = prior + context + invalid_penalty
        logit_idx = int(np.argmax(allowed_scores))

    uncert_penalty = uncert / (1.0 + mean_uncert) if mean_uncert > 0.0 else uncert
    combined = prior + score_signal + context - uncert_penalty - switch_penalty + invalid_penalty
    best_idx = int(np.argmax(combined))
    candidate_idx = logit_idx

    current_invalid = not allowed[current_idx]
    score_gain_over_logits = float(score_signal[best_idx] - score_signal[logit_idx])
    combined_gain_over_logits = float(combined[best_idx] - combined[logit_idx])
    override_margin = clip01(mean_uncert / (1.0 + mean_uncert))
    if allowed[best_idx] and score_gain_over_logits > override_margin and combined_gain_over_logits > 0.0:
        candidate_idx = best_idx

    if candidate_idx == current_idx:
        return previous_topology

    score_gain_over_current = float(score_signal[candidate_idx] - score_signal[current_idx])
    combined_gain_over_current = float(combined[candidate_idx] - combined[current_idx])
    if time_since_switch < cooldown:
        if not current_invalid and combined_gain_over_current <= score_gain_over_current:
            return previous_topology

    candidate_topology = TOPOLOGY_IDS[candidate_idx]
    specialist_margin = switch_penalty[candidate_idx] / (1.0 + switch_penalty[candidate_idx])
    required_margin = switch_hysteresis_margin(cfg) * (
        1.0 + specialist_margin + clip01(mean_uncert / (1.0 + mean_uncert))
    )
    if not current_invalid and combined[candidate_idx] < combined[current_idx] + required_margin:
        return previous_topology
    return TOPOLOGY_IDS[candidate_idx]
