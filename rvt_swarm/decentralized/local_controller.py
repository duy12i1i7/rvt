"""Robot-local mode-conditioned formation controller.

Every robot runs this code on its own `RobotView` and produces only its own
acceleration. There is no function here that accepts the joint state and
returns a joint action; `controllers.expert_action` (which does exactly that,
and which reads the swarm centroid at `controllers.py:168`) is not called.

Correspondence with the centralized controller
----------------------------------------------
The centralized formation term is

    form_err_i = centroid + offset_i - p_i

The decentralized term is the mean over one-hop neighbours of the pairwise
displacement residual

    e_i = (1/|N_i|) * sum_{j in N_i} [ (p_j - p_i) - d_ij ]

These are *identical* when N_i is the whole team, because

    (p_j - p_i) - (offset_j - offset_i) = (p_j - offset_j) - (p_i - offset_i)

and the template offsets sum to zero, so the mean of (p_j - offset_j) over the
whole team is the centroid. So the decentralized law is not an approximation of
the centralized one under full connectivity -- it reproduces it exactly, and
differs only through (a) which neighbours are visible and (b) the group-mean
denominators. Both differences are measured, not assumed:
`test_robot_local_controller.py` asserts the exact-equality property directly.

Three deliberate substitutions, each documented because each is a real change:

1. progress direction: centralized uses unit(goal - centroid); local uses
   unit(goal - p_i). Robot i has no centroid. Identical for a tight formation,
   divergent for a stretched one.
2. avoidance denominators: centralized averages robot-robot terms over all
   n-1 robots and obstacle terms over *every* obstacle in the world; local
   averages over one-hop neighbours and locally sensed obstacles only. The
   clearance kernels are already zero beyond `rr_active`/`ro_active` (0.9 m),
   so no *non-zero* clearance contribution is lost -- but the denominator
   shrinks, so the local controller reacts more strongly to a near obstacle
   than the centralized one, which dilutes it across the whole obstacle field.
   This makes the local controller different, not merely restricted.
3. time-to-collision terms have a longer effective range than the clearance
   kernels, so gating at r_comm/r_obs does drop some far-field TTC
   contributions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from ..controllers import _clearance_term, _ttc_term
from ..runtime_configuration import (
    DEFAULT_RUNTIME_CONFIG,
    RuntimeConfig,
    runtime_config_from_legacy,
)
from ..utils import soft_clip, unit, vec_norm
from .roles import desired_offset_for_neighbour
from .system_model import KEEP, LINE, CentralizedAccessError, RobotView


@dataclass(frozen=True)
class LocalGains:
    """Fixed controller parameters, identical on every robot.

    Mirrors the centralized expert's implicit unit weights: it forms the mean
    of each term group and sums the group means. Keeping the gains at 1.0
    preserves that structure exactly, so any performance difference is
    attributable to locality rather than to retuning.
    """

    k_goal: float = DEFAULT_RUNTIME_CONFIG.controller.goal_gain
    k_formation: float = DEFAULT_RUNTIME_CONFIG.controller.formation_gain
    k_damping: float = DEFAULT_RUNTIME_CONFIG.controller.damping_gain
    k_rr_clearance: float = DEFAULT_RUNTIME_CONFIG.controller.robot_clearance_gain
    k_rr_ttc: float = DEFAULT_RUNTIME_CONFIG.controller.robot_ttc_gain
    k_ro_clearance: float = DEFAULT_RUNTIME_CONFIG.controller.obstacle_clearance_gain
    k_ro_ttc: float = DEFAULT_RUNTIME_CONFIG.controller.obstacle_ttc_gain
    # Velocity-consensus damping sum_j k_v (v_j - v_i). Available locally
    # (relative velocity rides in the beacon) and part of the specified
    # controller structure, but it has no centralized counterpart -- so it is
    # its own term group, leaving the exact-correspondence property intact, and
    # setting it to 0.0 recovers a controller that mirrors the centralized one
    # term for term.
    k_velocity_consensus: float = (
        DEFAULT_RUNTIME_CONFIG.controller.velocity_consensus_gain
    )

    @classmethod
    def from_runtime_config(cls, config: RuntimeConfig) -> "LocalGains":
        source = config.controller
        return cls(
            k_goal=source.goal_gain,
            k_formation=source.formation_gain,
            k_damping=source.damping_gain,
            k_rr_clearance=source.robot_clearance_gain,
            k_rr_ttc=source.robot_ttc_gain,
            k_ro_clearance=source.obstacle_clearance_gain,
            k_ro_ttc=source.obstacle_ttc_gain,
            k_velocity_consensus=source.velocity_consensus_gain,
        )


def _mean(vs: Sequence[np.ndarray]) -> np.ndarray:
    if not len(vs):
        return np.zeros(2, dtype=np.float32)
    return np.mean(np.stack(vs), axis=0).astype(np.float32)


def local_formation_error(view: RobotView, mode: int) -> np.ndarray:
    """e_i -- robot i's estimate of its own formation error, from neighbours only.

    Normalised by (|N_i| + 1), not |N_i|: robot i counts itself as a member of
    its own formation neighbourhood, contributing a residual that is trivially
    zero. That choice is what makes the correspondence exact rather than merely
    proportional. Writing s_k = p_k - offset_k and summing over j != i,

        sum_j [(p_j - p_i) - d_ij] = sum_j (s_j - s_i) = S - n * s_i

    where S = sum_k s_k = n * centroid (the template offsets sum to zero).
    Dividing by n = |N_i| + 1 under full connectivity gives

        S/n - s_i = centroid + offset_i - p_i = form_err_i

    exactly. Dividing by |N_i| = n - 1 instead would inflate it by n/(n-1)
    (a 20 % error at N = 6), so the denominator is load-bearing, not cosmetic.

    Returns zero when robot i has no valid neighbours: with nothing to be in
    formation *with*, the formation term is undefined rather than zero-error,
    and the goal/avoidance terms carry the robot until a neighbour reappears.
    """
    terms: List[np.ndarray] = []
    for nb in view.neighbours:
        if not nb.link_valid:
            continue
        rel = np.asarray(nb.rel_position, dtype=np.float32)
        d_ij = desired_offset_for_neighbour(view, nb, mode)
        terms.append((rel - d_ij).astype(np.float32))
    if not terms:
        return np.zeros(2, dtype=np.float32)
    return (np.sum(np.stack(terms), axis=0) / (len(terms) + 1.0)).astype(np.float32)


def local_controller(
    view: RobotView,
    cfg: object,
    committed_mode: int,
    gains: Optional[LocalGains] = None,
) -> np.ndarray:
    """u_i for robot i alone. Returns a (2,) acceleration.

    Reads only: robot i's own state, its own role, its one-hop neighbour
    records, its locally sensed obstacles, the shared goal, and constant gains.
    """
    if committed_mode not in (KEEP, LINE):
        raise ValueError(f"committed_mode must be KEEP(0) or LINE(2), got {committed_mode}")
    if not isinstance(view, RobotView):
        raise CentralizedAccessError(
            "local_controller accepts a RobotView only; passing an obs dict or a "
            "joint-state array is a centralization violation"
        )
    runtime_config = runtime_config_from_legacy(cfg)
    derived = runtime_config.derived
    g = gains or LocalGains.from_runtime_config(runtime_config)

    p_i = np.asarray(view.position, dtype=np.float32)
    v_i = np.asarray(view.velocity, dtype=np.float32)
    goal = np.asarray(view.goal, dtype=np.float32)
    mission = unit(np.asarray(view.mission_dir, dtype=np.float32))
    lateral = np.array([mission[1], -mission[0]], dtype=np.float32)

    spacing = max(runtime_config.formation.nominal_spacing_meters, 1e-6)
    max_speed = max(
        runtime_config.physical.maximum_speed_meters_per_second, 1e-6
    )
    rr_active = max(
        runtime_config.formation.nominal_spacing_meters,
        derived.robot_robot_required_clearance_meters,
    )
    ro_active = max(
        runtime_config.formation.nominal_spacing_meters,
        derived.robot_obstacle_required_clearance_meters,
    )
    horizon = max(
        runtime_config.physical.control_period_seconds,
        runtime_config.sensing.peer_sensing_range_meters / max_speed,
    )

    # -- formation error from pairwise neighbour residuals only --------------
    e_i = local_formation_error(view, committed_mode)

    # -- goal term. unit(goal - p_i): robot i has no centroid. ---------------
    progress_dir = unit(goal - p_i).astype(np.float32)
    progress_weight = 1.0
    if committed_mode == LINE:
        # Hold station laterally before pushing along the corridor, exactly as
        # the centralized controller does -- but with the locally estimated
        # formation error in place of the centroid-derived one.
        lateral_err = abs(float(np.dot(e_i, lateral)))
        progress_weight = float(np.clip(1.0 - lateral_err / spacing, 0.0, 1.0))

    base_terms: List[np.ndarray] = [
        (progress_dir * progress_weight * g.k_goal).astype(np.float32),
        (e_i / spacing * g.k_formation).astype(np.float32),
        (-v_i / max_speed * g.k_damping).astype(np.float32),
    ]
    if committed_mode == LINE:
        along = float(np.dot(e_i, mission))
        base_terms.append((mission * (along / spacing)).astype(np.float32))

    # -- robot-robot avoidance and damping, one-hop neighbours only ----------
    rr_clear: List[np.ndarray] = []
    rr_ttc: List[np.ndarray] = []
    damping: List[np.ndarray] = []
    for nb in view.neighbours:
        if not nb.link_valid:
            continue
        rel_p = np.asarray(nb.rel_position, dtype=np.float32)   # p_j - p_i
        rel_v = np.asarray(nb.rel_velocity, dtype=np.float32)   # v_j - v_i
        diff = (-rel_p).astype(np.float32)                      # p_i - p_j
        rr_clear.append(_clearance_term(diff, rr_active))
        rr_ttc.append(_ttc_term(diff, (-rel_v).astype(np.float32), horizon))
        damping.append(rel_v.astype(np.float32))

    # -- obstacle avoidance, locally sensed obstacles only -------------------
    ro_clear: List[np.ndarray] = []
    ro_ttc: List[np.ndarray] = []
    for ox, oy, _radius in view.obstacles:
        diff = (-np.array([ox, oy], dtype=np.float32)).astype(np.float32)  # p_i - o
        ro_clear.append(_clearance_term(diff, ro_active))
        # Obstacles are static in these layouts; relative velocity is -v_i.
        ro_ttc.append(_ttc_term(diff, (-v_i).astype(np.float32), horizon))

    # Sum of per-group MEANS, exactly matching controllers._sum_group_means.
    # Empty groups contribute nothing (not a zero that would dilute a mean).
    total = np.zeros(2, dtype=np.float32)
    for group, gain in (
        (base_terms, 1.0),
        (rr_clear, g.k_rr_clearance),
        (rr_ttc, g.k_rr_ttc),
        (ro_clear, g.k_ro_clearance),
        (ro_ttc, g.k_ro_ttc),
        (damping, g.k_velocity_consensus / max_speed),
    ):
        if len(group):
            total = total + _mean(group) * gain

    return soft_clip(
        total,
        runtime_config.physical.maximum_acceleration_meters_per_second_squared,
    ).astype(np.float32)


def controller_signature() -> Dict[str, object]:
    """Evidence that every robot runs identical code with identical gains."""
    import hashlib
    import inspect

    src = inspect.getsource(local_controller) + inspect.getsource(local_formation_error)
    return {
        "code_sha256": hashlib.sha256(src.encode()).hexdigest(),
        "gains": LocalGains().__dict__,
        "accepts": "RobotView",
        "returns": "own action (2,)",
        "joint_action_function": False,
    }
