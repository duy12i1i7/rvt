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

    # Recoverability-aware risk modulation
    all_negative = False
    if recoverability_scores is not None:
        all_negative = bool(np.all(recoverability_scores < 0.0))
    if recoverability is not None:
        risk = max(0.0, risk - 0.15 * float(recoverability))
    # Docs: "chỉ can thiệp nếu tất cả lựa chọn có recoverability âm"
    if all_negative:
        risk = max(risk, 0.55)

    threshold = getattr(cfg.method, 'shield_risk_threshold', 0.85)
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


def choose_counterfactual_topology(
    obs: Dict,
    topology_logits: torch.Tensor,
    recoverability_scores: torch.Tensor | None,
    cfg: Config,
    previous_topology: int = 0,
    uncertainty: torch.Tensor | None = None,
) -> int:
    # Cooldown: don't switch if recently switched — let formation converge
    cooldown = getattr(cfg.method, 'topology_cooldown', 5)
    if obs.get("time_since_switch", 999) < cooldown:
        return previous_topology

    topo_prior = torch.softmax(topology_logits / max(cfg.method.topology_temperature, 1e-6), dim=-1).squeeze(0)
    if recoverability_scores is None or not cfg.method.use_counterfactual_topology:
        return choose_topology_from_logits(topology_logits)
    scores = recoverability_scores.squeeze(0).detach().cpu().numpy().astype(np.float32)
    prior = topo_prior.detach().cpu().numpy().astype(np.float32)
    uncert = uncertainty.squeeze(0).detach().cpu().numpy().astype(np.float32) if uncertainty is not None else np.zeros_like(scores)

    # Use uncertainty as a soft penalty. A hard gate froze topology selection
    # in practice because the uncertainty head often stayed above the old
    # threshold even when one topology was clearly more recoverable.
    mean_uncert = float(np.mean(uncert))

    # Context bonuses for situationally appropriate topologies
    context = np.zeros_like(scores)
    bottleneck = obs["bottleneck"] > 0.50
    if bottleneck:
        context[TOPOLOGY_IDS.index(1)] += 0.08
        context[TOPOLOGY_IDS.index(2)] += 0.18
        context[TOPOLOGY_IDS.index(3)] += 0.10
    if obs["progress"] > 0.75 and obs["bottleneck"] < 0.30:
        context[TOPOLOGY_IDS.index(4)] += 0.18
    # Mild preference for keep in easy situations
    if obs["bottleneck"] < 0.35:
        context[TOPOLOGY_IDS.index(0)] += 0.10

    # Preserve inertia, but do not suppress switching entirely.
    switch_penalty = np.zeros_like(scores)
    for idx, topo in enumerate(TOPOLOGY_IDS):
        if topo != previous_topology:
            switch_penalty[idx] = 0.08
        if topo == 3:  # Split is most disruptive
            switch_penalty[idx] += 0.12
        if topo == 4 and obs["bottleneck"] > 0.45:
            switch_penalty[idx] += 0.05
        if topo == 0 and bottleneck:
            switch_penalty[idx] += 0.04

    combined = 0.62 * scores + 0.22 * prior + context - 0.08 * uncert - switch_penalty
    best_idx = int(np.argmax(combined))
    current_idx = TOPOLOGY_IDS.index(previous_topology)
    if best_idx == current_idx:
        return previous_topology

    recover_gap = float(scores[best_idx] - scores[current_idx])
    if recover_gap > 0.35 and combined[best_idx] >= combined[current_idx] - 0.02:
        return TOPOLOGY_IDS[best_idx]

    required_margin = cfg.method.switch_hysteresis + 0.05 * max(0.0, mean_uncert - 0.45)
    if combined[best_idx] < combined[current_idx] + required_margin:
        return previous_topology
    return TOPOLOGY_IDS[best_idx]
