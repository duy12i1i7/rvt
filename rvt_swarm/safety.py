from __future__ import annotations

from typing import Dict

import numpy as np
import torch

from .config import Config, TOPOLOGY_IDS
from .utils import soft_clip, unit


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


def collision_risk(obs: Dict, horizon: float = 2.0) -> float:
    """Compute collision risk using both proximity AND predicted TTC.

    Predictive: uses relative velocities to anticipate future collisions,
    not just current distances.  Risk is high when TTC is short, even if
    agents are currently far apart.
    """
    pos = obs["positions"]
    vel = obs["velocities"]
    obs_pos = obs["obstacles"]
    obs_vel = obs.get("obstacle_velocities", np.zeros_like(obs_pos))
    risk = 0.0
    for i in range(len(pos)):
        for j in range(i + 1, len(pos)):
            d = np.linalg.norm(pos[i] - pos[j])
            dist_risk = max(0.0, 0.9 - d)
            ttc = time_to_collision(pos[i], vel[i], pos[j], vel[j], 0.9)
            ttc_risk = max(0.0, 1.0 - ttc / horizon) if ttc < horizon else 0.0
            risk = max(risk, dist_risk, 0.45 * ttc_risk)
        for k, o in enumerate(obs_pos):
            d = np.linalg.norm(pos[i] - o)
            dist_risk = max(0.0, 0.95 - d)
            ov = obs_vel[k] if k < len(obs_vel) else np.zeros(2, dtype=np.float32)
            ttc = time_to_collision(pos[i], vel[i], o, ov, 0.95)
            ttc_risk = max(0.0, 1.0 - ttc / horizon) if ttc < horizon else 0.0
            risk = max(risk, dist_risk, 0.45 * ttc_risk)
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
    risk = collision_risk(obs)
    form_rms = estimated_form_rms(obs)

    # Recoverability is treated as a conservative warning signal only.
    # Positive scores should not "explain away" geometric collision risk.
    all_negative = False
    if recoverability_scores is not None:
        all_negative = bool(np.all(recoverability_scores < 0.0))
    if recoverability is not None:
        recover_value = float(recoverability)
        if recover_value < -0.10:
            risk = max(risk, 0.52 + 0.12 * min(-recover_value, 1.0))
    # Docs: "chỉ can thiệp nếu tất cả lựa chọn có recoverability âm"
    if all_negative:
        risk = max(risk, 0.55)

    threshold = getattr(cfg.method, 'shield_risk_threshold', 0.85)
    if not all_negative:
        if obs.get("time_since_switch", 999) < 4:
            threshold += 0.05
        if topo in (2, 3, 4) and form_rms > 0.85 * cfg.env.formation_tolerance:
            threshold += 0.03
    if risk < threshold:
        return actions

    # --- QP-based intervention ---
    progress_dir = progress_direction(obs)
    progress_w = 0.02 if all_negative else 0.008
    safe = actions.copy()
    for i in range(len(safe)):
        constraints = _build_cbf_constraints(i, obs, cfg)
        if not constraints:
            continue
        safe[i] = _solve_per_robot_qp(
            safe[i], constraints, progress_dir, cfg.env.max_accel, progress_w,
        )
    max_blend = float(getattr(cfg.method, "max_shield_blend", 0.06))
    # Soft blend avoids over-damping learned policy when shield activates.
    if all_negative:
        blend = min(max_blend, 0.8 * max_blend)
    else:
        if obs.get("time_since_switch", 999) < 4:
            max_blend *= 0.75
        denom = max(1e-6, 1.0 - threshold)
        severity = float(np.clip((risk - threshold) / denom, 0.0, 1.0))
        blend = severity * max_blend
    return (1.0 - blend) * actions + blend * safe


# ── CBF-QP helpers ──────────────────────────────────────────────────

def _build_cbf_constraints(
    robot_idx: int, obs: Dict, cfg: Config,
    alpha_rr: float = 1.0, alpha_ro: float = 1.5,
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
    d_safe_rr = cfg.env.min_rr_distance + 0.03
    for j in range(len(pos)):
        if j == robot_idx:
            continue
        diff = pi - pos[j]
        dist_sq = float(np.dot(diff, diff))
        h = dist_sq - d_safe_rr ** 2
        if h > 0.9:              # far enough → no constraint needed
            continue
        rel_v = vi - vel[j]
        a = (2.0 * dt * diff).astype(np.float32)
        b = float(-alpha_rr * h - 2.0 * np.dot(diff, rel_v))
        constraints.append((a, b))

    # Robot-obstacle
    obs_pos = obs["obstacles"]
    obs_vel = obs.get("obstacle_velocities", np.zeros_like(obs_pos))
    d_safe_ro = cfg.env.min_ro_distance + 0.02
    for k in range(len(obs_pos)):
        diff = pi - obs_pos[k]
        dist_sq = float(np.dot(diff, diff))
        h = dist_sq - d_safe_ro ** 2
        if h > 0.9:
            continue
        ov = obs_vel[k] if k < len(obs_vel) else np.zeros(2, dtype=np.float32)
        rel_v = vi - ov
        a = (2.0 * dt * diff).astype(np.float32)
        b = float(-alpha_ro * h - 2.0 * np.dot(diff, rel_v))
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
    bottleneck = float(obs["bottleneck"])
    progress = float(obs["progress"])
    split_active = float(obs.get("split_active", 0.0))
    n_agents = int(len(obs["positions"]))

    allowed = np.ones(len(TOPOLOGY_IDS), dtype=bool)
    context = np.zeros(len(TOPOLOGY_IDS), dtype=np.float32)

    keep_idx = TOPOLOGY_IDS.index(0)
    compress_idx = TOPOLOGY_IDS.index(1)
    line_idx = TOPOLOGY_IDS.index(2)
    split_idx = TOPOLOGY_IDS.index(3)
    recover_idx = TOPOLOGY_IDS.index(4)

    if bottleneck < 0.44:
        allowed[line_idx] = False
    if bottleneck < 0.60 or n_agents < 12:
        allowed[split_idx] = False
    if progress < 0.65 and split_active < 0.28 and form_rms < 1.00 * form_tol:
        allowed[recover_idx] = False

    if bottleneck > 0.50:
        context[compress_idx] += 0.05
        context[line_idx] += 0.14
    if bottleneck > 0.65 and n_agents >= 12:
        context[split_idx] += 0.10
    if bottleneck < 0.28:
        context[keep_idx] += 0.14
        context[compress_idx] -= 0.05
    if progress > 0.76 and bottleneck < 0.26 and form_rms > 0.80 * form_tol:
        context[recover_idx] += 0.14
        context[keep_idx] += 0.06
    if split_active > 0.28 or form_rms > 1.10 * form_tol:
        context[recover_idx] += 0.12
        context[keep_idx] -= 0.04
    if previous_topology == 3 and bottleneck < 0.35:
        context[keep_idx] += 0.10
        if split_active > 0.30 or form_rms > form_tol:
            context[recover_idx] += 0.08
    if previous_topology in (2, 3) and bottleneck < 0.30:
        context[keep_idx] += 0.12
        if split_active > 0.24 or form_rms > 1.02 * form_tol:
            context[recover_idx] += 0.06

    return allowed, context


def choose_counterfactual_topology(
    obs: Dict,
    topology_logits: torch.Tensor,
    recoverability_scores: torch.Tensor | None,
    cfg: Config,
    previous_topology: int = 0,
    uncertainty: torch.Tensor | None = None,
) -> int:
    topo_prior = torch.softmax(topology_logits / max(cfg.method.topology_temperature, 1e-6), dim=-1).squeeze(0)
    logit_choice = choose_topology_from_logits(topology_logits)
    if recoverability_scores is None or not cfg.method.use_counterfactual_topology:
        return logit_choice

    scores = recoverability_scores.squeeze(0).detach().cpu().numpy().astype(np.float32)
    prior = topo_prior.detach().cpu().numpy().astype(np.float32)
    uncert = uncertainty.squeeze(0).detach().cpu().numpy().astype(np.float32) if uncertainty is not None else np.zeros_like(scores)
    score_signal = np.tanh(0.9 * scores)
    mean_uncert = float(np.mean(uncert))
    allowed, context = topology_context_mask(obs, cfg, previous_topology)
    invalid_penalty = np.where(allowed, 0.0, -1.5).astype(np.float32)

    switch_penalty = np.zeros_like(scores)
    bottleneck = float(obs["bottleneck"])
    cooldown = float(getattr(cfg.method, "topology_cooldown", 5))
    time_since_switch = float(obs.get("time_since_switch", 999.0))
    cooldown_frac = float(np.clip((cooldown - time_since_switch) / max(cooldown, 1.0), 0.0, 1.0))
    for idx, topo in enumerate(TOPOLOGY_IDS):
        if topo != previous_topology:
            switch_penalty[idx] += 0.08 + 0.08 * cooldown_frac
        if previous_topology == 0 and topo in (2, 3, 4):
            switch_penalty[idx] += 0.04
        if topo == 3:  # Split is most disruptive
            switch_penalty[idx] += 0.16
        if topo == 4 and bottleneck > 0.40:
            switch_penalty[idx] += 0.07
        if topo == 0 and bottleneck > 0.55:
            switch_penalty[idx] += 0.06

    current_idx = TOPOLOGY_IDS.index(previous_topology)
    logit_idx = TOPOLOGY_IDS.index(logit_choice)
    if not allowed[logit_idx]:
        allowed_scores = prior + context + invalid_penalty
        logit_idx = int(np.argmax(allowed_scores))

    combined = 0.48 * prior + 0.30 * score_signal + context - 0.06 * uncert - switch_penalty + invalid_penalty
    best_idx = int(np.argmax(combined))
    candidate_idx = logit_idx

    current_invalid = not allowed[current_idx]
    score_gain_over_logits = float(score_signal[best_idx] - score_signal[logit_idx])
    combined_gain_over_logits = float(combined[best_idx] - combined[logit_idx])
    override_margin = 0.24 + 0.08 * max(0.0, mean_uncert - 0.35)
    if TOPOLOGY_IDS[best_idx] in (2, 3, 4):
        override_margin += 0.05
    if previous_topology == 0 and TOPOLOGY_IDS[best_idx] in (2, 3, 4):
        override_margin += 0.04
    if allowed[best_idx] and score_gain_over_logits > override_margin and combined_gain_over_logits > 0.03:
        candidate_idx = best_idx

    if candidate_idx == current_idx:
        return previous_topology

    score_gain_over_current = float(score_signal[candidate_idx] - score_signal[current_idx])
    prior_gain_over_current = float(prior[candidate_idx] - prior[current_idx])
    combined_gain_over_current = float(combined[candidate_idx] - combined[current_idx])
    if time_since_switch < cooldown:
        if not current_invalid and (score_gain_over_current < 0.34 or combined_gain_over_current < 0.10):
            return previous_topology

    if candidate_idx != logit_idx and not current_invalid:
        if score_gain_over_current < 0.26 and prior_gain_over_current < 0.10:
            return previous_topology

    candidate_topology = TOPOLOGY_IDS[candidate_idx]
    specialist_margin = 0.0
    if candidate_topology in (2, 3, 4):
        specialist_margin += 0.04
    if previous_topology == 0 and candidate_topology in (2, 3, 4):
        specialist_margin += 0.03
    required_margin = cfg.method.switch_hysteresis + specialist_margin + 0.06 * max(0.0, mean_uncert - 0.35)
    if not current_invalid and combined[candidate_idx] < combined[current_idx] + required_margin:
        return previous_topology
    return TOPOLOGY_IDS[candidate_idx]
