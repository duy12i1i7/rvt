"""Formation Recovery Metric V3 — offline evaluator only.

Replaces the max-over-pairwise metric of
`reconfiguration_metrics.pairwise_formation_error`, which was applied with
`epsilon_form = 0.55 m` — a tolerance calibrated for *per-robot* error. A
pairwise residual accumulates two robots' deviations, so that criterion was
roughly twice as strict as intended and no policy could satisfy it, including
one that never left the nominal formation.

V3 compares each robot against its persistent-role template in the shared
mission frame, after removing the common translation:

    c(t)     = (1/N) sum_i p_i(t)
    e_i^tau  = || [p_i(t) - c(t)] - R(psi_goal) r_i^tau ||
    E_inf    = max_i e_i^tau          <- tube membership
    E_rms    = sqrt(mean_i e_i^tau^2) <- descriptive only

**The centroid appears here and nowhere else.** This module is an offline
evaluator: it reads the joint state after the fact, which is an explicitly
permitted use. `guards.OFFLINE_MODULES` records that, and
`test_formation_recovery_metric_v3.py` asserts the deployable controller never
receives a centroid.
"""

from __future__ import annotations

from typing import Dict, Optional, Sequence, Tuple

import numpy as np

from ..runtime_configuration import DEFAULT_RUNTIME_CONFIG, steps_from_seconds
from .roles import RoleAssignment, rotation
from .system_model import KEEP, LINE

# Unchanged from the environment configuration. NOT recalibrated using rerun
# results; any change would need its own predeclaration.
EPSILON_FORM: float = (
    DEFAULT_RUNTIME_CONFIG.formation.formation_tolerance_ratio
    * DEFAULT_RUNTIME_CONFIG.formation.nominal_spacing_meters
)

# Consecutive in-tube steps required for a recovery to count (3.0 s at dt=0.15).
L_RECOVER: int = steps_from_seconds(
    DEFAULT_RUNTIME_CONFIG.mission.recovery_dwell_seconds,
    DEFAULT_RUNTIME_CONFIG.physical.control_period_seconds,
)


def role_errors(positions: np.ndarray, roles: RoleAssignment, mode: int,
                mission_dir: Tuple[float, float]) -> np.ndarray:
    """e_i^tau for every robot. Returns (N,).

    `positions[i]` must be robot i's position under the SAME persistent role
    mapping the evaluator uses, i.e. row order is robot id order. Storage order
    is therefore semantically meaningful and must not be permuted independently
    of the role table.
    """
    p = np.asarray(positions, dtype=np.float64)
    if p.ndim != 2 or p.shape[1] != 2:
        raise ValueError("positions must be (N, 2)")
    T = np.asarray(roles.coords(mode), dtype=np.float64)
    if len(T) != len(p):
        raise ValueError(f"role table has {len(T)} rows, positions has {len(p)}")
    # Centre the template. Most templates already sum to zero, but the keep
    # grid does not when N does not fill its rows -- at N=3 the 2x2 grid leaves
    # a hole and the offsets sum to (-0.45, +0.45). Without centring, an exact
    # template would score a non-zero error purely from that offset. Centring
    # is a common translation, so it leaves every pairwise offset d_ij (and
    # therefore the deployable controller) completely unchanged.
    T = T - T.mean(axis=0)
    c = p.mean(axis=0)
    R = rotation(mission_dir).astype(np.float64)
    target = (R @ T.T).T                      # rotate the template into the frame
    return np.linalg.norm((p - c) - target, axis=1)


def e_inf(positions: np.ndarray, roles: RoleAssignment, mode: int,
          mission_dir: Tuple[float, float]) -> float:
    """Primary tube metric: max per-robot role error."""
    return float(role_errors(positions, roles, mode, mission_dir).max())


def e_rms(positions: np.ndarray, roles: RoleAssignment, mode: int,
          mission_dir: Tuple[float, float]) -> float:
    """Descriptive only. Never used for tube membership."""
    e = role_errors(positions, roles, mode, mission_dir)
    return float(np.sqrt(np.mean(e ** 2)))


def in_keep_tube(positions: np.ndarray, roles: RoleAssignment,
                 mission_dir: Tuple[float, float],
                 epsilon: float = EPSILON_FORM) -> bool:
    return e_inf(positions, roles, KEEP, mission_dir) <= epsilon


def in_line_tube(positions: np.ndarray, roles: RoleAssignment,
                 mission_dir: Tuple[float, float],
                 epsilon: float = EPSILON_FORM) -> bool:
    return e_inf(positions, roles, LINE, mission_dir) <= epsilon


def nominal_keep_recovered(traj: Sequence[np.ndarray], roles: RoleAssignment,
                           mission_dir: Tuple[float, float],
                           t_cross: Optional[int],
                           epsilon: float = EPSILON_FORM,
                           l_recover: int = L_RECOVER,
                           downstream_ok: Optional[Sequence[bool]] = None
                           ) -> Optional[int]:
    """First step t >= t_cross with `l_recover` consecutive in-tube steps.

    Returns the step index, or None. `downstream_ok[t]` optionally requires the
    team to also be inside the recovery region at step t.
    """
    if t_cross is None:
        return None
    T = len(traj)
    for t in range(t_cross, T - l_recover + 1):
        ok = True
        for u in range(t, t + l_recover):
            if not in_keep_tube(traj[u], roles, mission_dir, epsilon):
                ok = False
                break
            if downstream_ok is not None and not downstream_ok[u]:
                ok = False
                break
        if ok:
            return t
    return None


def delta_n(roles: RoleAssignment) -> float:
    """delta_N = max_i || r_i^KEEP - r_i^LINE ||, the separation certificate.

    Under the translation-aligned per-robot max metric, a configuration lies in
    BOTH tubes iff delta_N <= 2 * epsilon:

      (=>) if X is in both, then for every i the triangle inequality gives
           ||r_i^K - r_i^L|| <= 2 eps, so delta_N <= 2 eps.
      (<=) if delta_N <= 2 eps, the explicit midpoint configuration
           p_i - c = R (r_i^K + r_i^L) / 2 lies in both, and it is a valid
           configuration because both templates sum to zero so the offsets do
           too.

    The condition is therefore necessary AND sufficient, not merely a bound.
    """
    K = np.asarray(roles.coords(KEEP), dtype=np.float64)
    L = np.asarray(roles.coords(LINE), dtype=np.float64)
    K = K - K.mean(axis=0)          # same centring the evaluator applies
    L = L - L.mean(axis=0)
    return float(np.linalg.norm(K - L, axis=1).max())


def midpoint_configuration(roles: RoleAssignment,
                           mission_dir: Tuple[float, float]) -> np.ndarray:
    """The configuration that is in both tubes when delta_N <= 2*epsilon.

    A constructive counterexample, used to certify the failure of separation
    rather than merely reporting that a bound was not met.
    """
    K = np.asarray(roles.coords(KEEP), dtype=np.float64)
    L = np.asarray(roles.coords(LINE), dtype=np.float64)
    K = K - K.mean(axis=0)
    L = L - L.mean(axis=0)
    R = rotation(mission_dir).astype(np.float64)
    return (R @ ((K + L) / 2.0).T).T


def _centred_gap(roles: RoleAssignment) -> np.ndarray:
    K = np.asarray(roles.coords(KEEP), dtype=np.float64)
    L = np.asarray(roles.coords(LINE), dtype=np.float64)
    return np.linalg.norm((K - K.mean(axis=0)) - (L - L.mean(axis=0)), axis=1)


def separation_report(spacing: float, team_sizes: Sequence[int] = (3, 4, 6),
                      epsilon: float = EPSILON_FORM) -> Dict[int, Dict[str, object]]:
    out: Dict[int, Dict[str, object]] = {}
    for n in team_sizes:
        roles = RoleAssignment.from_index(n, spacing)
        d = delta_n(roles)
        out[n] = {"delta_n": d, "threshold": 2.0 * epsilon,
                  "disjoint": bool(d > 2.0 * epsilon),
                  "per_robot": _centred_gap(roles).tolist()}
    return out
