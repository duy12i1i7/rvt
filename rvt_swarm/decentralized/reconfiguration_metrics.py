"""Offline scoring of the V2 reconfiguration task.

Implements the events and success definition of
`docs/DECENTRALIZED_RECONFIGURATION_TASK_V2.md`. Everything here reads the
joint state, which is an explicitly permitted use: offline metric computation.
No robot computes any of it, and `guards.OFFLINE_MODULES` records that.

Formation error is the PAIRWISE quantity the local controller regulates, not a
centroid-referenced one, so the metric and the controller agree on what
"in formation" means.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from .roles import RoleAssignment, rotation
from .system_model import KEEP, LINE

L_RECOVER = 20          # control steps the keep tube must be held (3.0 s)
RECOVERY_MARGIN = 0.5   # m past the exit plane before recovery may be scored


def pairwise_formation_error(pos: np.ndarray, roles: RoleAssignment,
                             mode: int, mission_dir: Tuple[float, float]) -> float:
    """E_tau = max over pairs of ||(p_j - p_i) - d_ij^tau||."""
    R = rotation(mission_dir)
    T = roles.coords(mode)
    n = len(pos)
    worst = 0.0
    for i in range(n):
        for j in range(i + 1, n):
            d = R @ (T[j] - T[i])
            worst = max(worst, float(np.linalg.norm((pos[j] - pos[i]) - d)))
    return worst


@dataclass
class Regions:
    entry_x: float
    exit_x: float
    axis: np.ndarray

    def along(self, pos: np.ndarray) -> np.ndarray:
        return pos @ self.axis


def build_regions(obstacles: np.ndarray, obstacle_radius: float,
                  robot_radius: float, min_ro: float,
                  mission_dir: Tuple[float, float]) -> Optional[Regions]:
    """Entry/exit planes from the obstacle structure. None if no structure."""
    if obstacles is None or len(obstacles) == 0:
        return None
    axis = np.asarray(mission_dir, dtype=np.float64)
    axis = axis / max(np.linalg.norm(axis), 1e-9)
    s = obstacles @ axis
    pad = robot_radius + min_ro
    return Regions(entry_x=float(s.min()) - pad,
                   exit_x=float(s.max()) + pad, axis=axis)


def score_episode(result: Dict[str, object], roles: RoleAssignment,
                  cfg, n: int) -> Dict[str, object]:
    """Compute every Task-4 quantity from one traced episode."""
    traj: List[np.ndarray] = result["position_trace"]
    modes: List[int] = result["mode_per_step"]
    mission = result["mission_dir"]
    if not traj:
        return {"scored": False}

    reg = build_regions(result["obstacles"], cfg.env.obstacle_radius,
                        cfg.env.robot_radius, cfg.env.min_ro_distance, mission)
    tol = cfg.env.formation_tolerance
    T = len(traj)

    e_keep = np.array([pairwise_formation_error(p, roles, KEEP, mission) for p in traj])
    e_line = np.array([pairwise_formation_error(p, roles, LINE, mission) for p in traj])

    # -- events ----------------------------------------------------------
    t_entry = t_cross = None
    if reg is not None:
        for t, p in enumerate(traj):
            s = reg.along(p)
            if t_entry is None and float(s.max()) >= reg.entry_x:
                t_entry = t
            if t_cross is None and float(s.min()) >= reg.exit_x:
                t_cross = t
                break

    # -- nominal formation recovery, held for L_RECOVER ------------------
    t_rec = None
    if t_cross is not None:
        need = reg.exit_x + RECOVERY_MARGIN
        for t in range(t_cross, T - L_RECOVER + 1):
            window = range(t, t + L_RECOVER)
            if all(e_keep[u] <= tol and float(reg.along(traj[u]).min()) >= need
                   for u in window):
                t_rec = t
                break

    # -- formation RMS by phase ------------------------------------------
    def seg(lo, hi):
        lo = max(0, lo if lo is not None else 0)
        hi = min(T, hi if hi is not None else T)
        return float(np.sqrt(np.mean(e_keep[lo:hi] ** 2))) if hi > lo else float("nan")

    rms_before = seg(0, t_entry)
    rms_inside = seg(t_entry, t_cross)
    rms_after = seg(t_cross, T)

    transitions = [(t, modes[t]) for t in range(1, T) if modes[t] != modes[t - 1]]
    time_in_line = float(np.mean([m == LINE for m in modes]))

    full = bool(
        result["goal_reached"] > 0.5
        and result["collision_free"] > 0.5
        and result["deadlock"] < 0.5
        and result["irreversible_collapse"] < 0.5
        and (reg is None or t_cross is not None)
        and t_rec is not None
    )

    return {
        "scored": True,
        "initial_keep_valid": bool(e_keep[0] <= tol),
        "initial_keep_error": float(e_keep[0]),
        "corridor_entry": t_entry is not None,
        "t_entry": t_entry,
        "bottleneck_crossed": t_cross is not None,
        "t_cross": t_cross,
        "exit_plane_crossed": t_cross is not None,
        "keep_recovered": t_rec is not None,
        "t_recover": t_rec,
        "recovery_dwell_complete": t_rec is not None,
        "goal_reached": float(result["goal_reached"]),
        "collision_free": float(result["collision_free"]),
        "deadlock": float(result["deadlock"]),
        "formation_rms_before": rms_before,
        "formation_rms_inside": rms_inside,
        "formation_rms_after": rms_after,
        "min_keep_error_after_cross": (float(e_keep[t_cross:].min())
                                       if t_cross is not None else float("nan")),
        "min_line_error": float(e_line.min()),
        "transition_count": len(transitions),
        "transition_steps": [t for t, _ in transitions],
        "time_in_line": time_in_line,
        "completion_steps": T,
        "full_reconfiguration_success": full,
    }
