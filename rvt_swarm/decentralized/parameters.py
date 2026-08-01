"""Typed configuration contract and derived quantities (Tasks G1–G7).

Four classes, strictly separated:

  A  PlatformParams  — physical properties of the robot and its sensors
  B  MissionParams   — what the mission requires, in SI units
  C  ProtocolParams  — assumptions the distributed protocol needs to be correct
  D  derived_*       — computed from A–C, never independently configurable

Every deployable decision threshold must come from one of these. The generality
audit found four constants that came from none of them and gated mode
selection; each is repaired here with a stated geometric or temporal meaning,
not with a different constant.

Time is specified in SECONDS and converted to control steps by
`steps_from_seconds`, so behaviour is invariant to control frequency.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Optional, Sequence, Tuple

import numpy as np

Vec2 = Tuple[float, float]


# ===========================================================================
# A — PHYSICAL PLATFORM PARAMETERS
# ===========================================================================
@dataclass(frozen=True)
class PlatformParams:
    """Properties of the hardware. Not choices; measurements."""

    robot_radius: float                 # m
    collision_clearance_obstacle: float  # m, robot centre to obstacle CENTRE
    collision_clearance_robot: float    # m, robot centre to robot centre
    max_speed: float                    # m/s
    max_accel: float                    # m/s^2
    obstacle_sensor_range: float        # m  (R_obs)
    communication_range: float          # m  (R_comm)
    control_period: float               # s  (T_ctrl)
    communication_period: float         # s  (T_comm)

    @classmethod
    def from_env_config(cls, env) -> "PlatformParams":
        """Bind to the simulator's own constants; never restate them."""
        return cls(
            robot_radius=float(env.robot_radius),
            collision_clearance_obstacle=float(env.min_ro_distance),
            collision_clearance_robot=float(env.min_rr_distance),
            max_speed=float(env.max_speed),
            max_accel=float(env.max_accel),
            obstacle_sensor_range=float(env.lidar_range),
            communication_range=3.0,          # see ProtocolParams.comm_range_ratio
            control_period=float(env.dt),
            communication_period=float(env.dt),
        )


# ===========================================================================
# B — MISSION SPECIFICATION
# ===========================================================================
@dataclass(frozen=True)
class MissionParams:
    """What the mission demands, in SI units. Frozen for this study."""

    nominal_spacing: float = 0.9          # m, formation lattice pitch
    formation_tolerance: float = 0.55     # m, epsilon_form (FROZEN)
    recovery_dwell_seconds: float = 3.0   # s, L_recover = 20 steps at dt=0.15
    safety_margin: float = 0.0            # m, added to every clearance requirement

    @property
    def formation_tolerance_ratio(self) -> float:
        return self.formation_tolerance / self.nominal_spacing


# ===========================================================================
# C — PROTOCOL ASSUMPTIONS
# ===========================================================================
@dataclass(frozen=True)
class ProtocolParams:
    """Assumptions the distributed protocol requires in order to be correct.

    These are *claims about the deployment*, not tuning knobs. Violating one
    invalidates a correctness guarantee rather than degrading a score.
    """

    max_team_size: int = 6
    # Maximum diameter of any connected communication component. With no
    # tighter assumption than "connected", the worst case for N robots is a
    # chain, whose diameter is N - 1. See derived_k_trigger.
    max_component_diameter: Optional[int] = None
    max_message_age_seconds: float = 0.45      # s, Delta_stale
    evidence_persistence_seconds: float = 0.45  # s, L_TRIGGER
    event_collection_seconds: float = 0.0       # s, arming and propagation share a step
    commitment_seconds: float = 1.5             # s, h_commit
    # Duration the trigger condition must be continuously INACTIVE before the
    # same physical event may re-arm (Task G4).
    rearm_inactive_seconds: float = 3.75        # s
    connectivity_assumption: str = (
        "Each connected component of G_c is internally connected for the "
        "duration of an epoch. Swarm-wide agreement is claimed only when G_c "
        "is connected; otherwise results are reported per component."
    )


# ===========================================================================
# D — DERIVED VALUES
# ===========================================================================
def steps_from_seconds(seconds: float, period: float) -> int:
    """ceil(seconds / period). The single time conversion used everywhere."""
    if period <= 0.0:
        raise ValueError("period must be positive")
    return int(math.ceil(seconds / period - 1e-12))


def derived_recovery_dwell_steps(m: MissionParams, p: PlatformParams) -> int:
    return steps_from_seconds(m.recovery_dwell_seconds, p.control_period)


def derived_evidence_persistence_steps(c: ProtocolParams, p: PlatformParams) -> int:
    return steps_from_seconds(c.evidence_persistence_seconds, p.control_period)


def derived_event_collection_steps(c: ProtocolParams, p: PlatformParams) -> int:
    return steps_from_seconds(c.event_collection_seconds, p.communication_period)


def derived_commitment_steps(c: ProtocolParams, p: PlatformParams) -> int:
    return steps_from_seconds(c.commitment_seconds, p.control_period)


def derived_max_message_age_steps(c: ProtocolParams, p: PlatformParams) -> int:
    return steps_from_seconds(c.max_message_age_seconds, p.control_period)


def derived_rearm_inactive_steps(c: ProtocolParams, p: PlatformParams) -> int:
    return steps_from_seconds(c.rearm_inactive_seconds, p.control_period)


def derived_component_diameter(c: ProtocolParams) -> int:
    """D_max. With only a connectivity assumption, the worst case is a chain."""
    if c.max_component_diameter is not None:
        return int(c.max_component_diameter)
    return int(c.max_team_size) - 1


def derived_k_trigger(c: ProtocolParams) -> int:
    """Task G6, Option A: k_trigger >= D_max.

    Max-consensus propagates exactly one hop per round, so covering a component
    of diameter D needs D rounds. `k_trigger = 4` was unsound for N = 6, whose
    worst-case (chain) diameter is 5. The integer is DERIVED, never written down.
    """
    return derived_component_diameter(c)


# ---------------------------------------------------------------------------
# G2 — forward sector half-width
# ---------------------------------------------------------------------------
def derived_forward_sector_half_width(
    own_keep_role: Vec2, own_line_role: Vec2,
    platform: PlatformParams, mission: MissionParams,
) -> float:
    """Half-width of the lateral band robot i searches ahead for wall material.

    SEMANTIC ROLE, established by auditing the predicate rather than the
    comment. `forward_opening_evidence` rejects the opening when any obstacle
    satisfies `ox > 0 and |oy| <= W`. So W is the band, measured across the
    mission direction, in which the presence of obstacle returns ahead means
    "the passage has not ended yet".

    The band that matters is exactly the region robot i's own KEEP role will
    occupy once it expands, plus the clearance it must keep from any obstacle
    centre:

        W_i = |lateral component of r_i^KEEP - r_i^LINE| + clearance + margin

    Failure modes this fixes, both real:

      * W too SMALL -> the robot declares an opening while wall material still
        lies in the band it is about to move into, and expands prematurely
        inside the passage. The audited literal 1.2 m under-covers the N = 6
        outer roles, which need 1.450 m -- a 0.25 m shortfall, and precisely
        the alpha 0.25 premature-expansion mechanism.
      * W too LARGE -> distant obstacles that are not part of the passage keep
        the sector occupied and the event never fires.

    The value is ROLE-DEPENDENT by construction: a centre robot in the KEEP grid
    barely moves laterally and needs a narrow band, while an outer robot needs
    the full offset. Nothing here comes from a corridor, a step number or a
    success rate.
    """
    lateral_displacement = abs(float(own_keep_role[1]) - float(own_line_role[1]))
    return (lateral_displacement
            + platform.collision_clearance_obstacle
            + mission.safety_margin)


def forward_sector_observable(half_width: float, platform: PlatformParams) -> bool:
    """The band must lie inside the sensor range, or it cannot be evaluated."""
    return 0.0 < half_width <= platform.obstacle_sensor_range


# ---------------------------------------------------------------------------
# G5 — lookahead distance
# ---------------------------------------------------------------------------
def derived_lookahead_distance(platform: PlatformParams, mission: MissionParams,
                               protocol: ProtocolParams,
                               speed: Optional[float] = None) -> float:
    """How far ahead a robot must notice a constriction to react in time.

    The audited `2.0 * nominal_spacing` conflated a lookahead distance with the
    formation pitch; the factor 2.0 had no stated meaning. The requirement is
    temporal, not geometric: the robot must detect the constriction early
    enough to (a) run the distributed protocol to a commitment and (b) stop or
    deform before reaching it.

        lookahead = min(sensor_range,
                        reaction_distance + protocol_latency_distance + margin)

    with `reaction_distance = v^2 / (2 a)` the braking distance at the current
    (or maximum) speed, and `protocol_latency_distance = v * T_protocol` the
    ground covered while the epoch runs.
    """
    v = platform.max_speed if speed is None else float(speed)
    braking = v * v / (2.0 * platform.max_accel)
    latency_steps = (derived_evidence_persistence_steps(protocol, platform)
                     + derived_event_collection_steps(protocol, platform)
                     + derived_k_trigger(protocol))
    latency_distance = v * latency_steps * platform.control_period
    required = braking + latency_distance + mission.safety_margin
    return min(platform.obstacle_sensor_range, required)


# ---------------------------------------------------------------------------
# Supported-configuration check (variable team size)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ConfigurationSupport:
    supported: bool
    team_size: int
    reasons: Tuple[str, ...]
    delta_n: float
    k_trigger: int


def check_team_size(n: int, platform: PlatformParams, mission: MissionParams,
                    protocol: ProtocolParams) -> ConfigurationSupport:
    """Explicit unsupported-configuration result rather than a silent special case."""
    from .formation_metric_v3 import delta_n as _delta_n
    from .roles import RoleAssignment

    reasons = []
    if n < 2:
        reasons.append(f"team size {n} < 2")
    roles = RoleAssignment.from_index(max(n, 2), mission.nominal_spacing)
    d = _delta_n(roles)
    if d <= 2.0 * mission.formation_tolerance:
        reasons.append(
            f"KEEP/LINE tubes not disjoint: delta_N={d:.4f} <= "
            f"2*eps={2*mission.formation_tolerance:.2f}")
    if n > protocol.max_team_size:
        reasons.append(f"team size {n} exceeds protocol max_team_size "
                       f"{protocol.max_team_size}")
    K = np.asarray(roles.coords(0), dtype=np.float64)
    L = np.asarray(roles.coords(2), dtype=np.float64)
    K = K - K.mean(0); L = L - L.mean(0)
    widest = max(abs(float(K[i][1]) - float(L[i][1])) for i in range(len(K)))
    w = widest + platform.collision_clearance_obstacle + mission.safety_margin
    if not forward_sector_observable(w, platform):
        reasons.append(f"forward sector {w:.3f} m exceeds sensor range "
                       f"{platform.obstacle_sensor_range:.3f} m")
    return ConfigurationSupport(
        supported=not reasons, team_size=n, reasons=tuple(reasons),
        delta_n=d, k_trigger=derived_k_trigger(protocol))


# ---------------------------------------------------------------------------
# Normalized reporting (G7)
# ---------------------------------------------------------------------------
def normalized_ratios(platform: PlatformParams, mission: MissionParams
                      ) -> Dict[str, float]:
    s = mission.nominal_spacing
    return {
        "formation_tolerance_ratio": mission.formation_tolerance / s,
        "sensor_range_ratio": platform.obstacle_sensor_range / s,
        "communication_range_ratio": platform.communication_range / s,
        "collision_clearance_ratio": platform.collision_clearance_obstacle / s,
        "robot_radius_ratio": platform.robot_radius / s,
    }


def default_parameters(env=None):
    from ..config import Config
    env = env or Config().env
    p = PlatformParams.from_env_config(env)
    return p, MissionParams(), ProtocolParams()
