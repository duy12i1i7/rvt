"""Formal system model for the fully decentralized keep/line selector.

This module is the single source of truth for the decentralization contract.
Every other module in `rvt_swarm.decentralized` imports its parameters and its
permitted/prohibited field lists from here; nothing re-declares them.

The contract in one sentence: at runtime robot *i* may touch only its own state,
its own offline-configured role and parameters, obstacles it sensed itself,
messages that arrived from one-hop communication neighbours, and the shared
mission constants -- never any quantity that requires knowing the joint state.

Global state remains available for simulation, Recovery Event V2 label
generation, offline metric computation, and explicitly-labelled centralized
diagnostic references. It must never enter a deployable code path.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, FrozenSet, Sequence, Tuple

# ---------------------------------------------------------------------------
# Modes. Unchanged from the binary pilot: split remains removed.
# ---------------------------------------------------------------------------
KEEP = 0
LINE = 2
MODES: Tuple[int, int] = (KEEP, LINE)
MODE_NAME: Dict[int, str] = {KEEP: "keep", LINE: "line"}


# ---------------------------------------------------------------------------
# Communication and sensing parameters
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class CommParams:
    """Runtime communication/sensing parameters.

    Values are justified against the existing environment constants
    (`EnvConfig`: dt=0.15 s, nominal_spacing=0.9 m, sensing_radius=4.0 m,
    lidar_range=3.0 m, max_speed=0.9 m/s).
    """

    # Peer-to-peer communication radius. A robot pair may exchange messages
    # only within this range.
    #
    # Justification for 3.0 m: an N=6 line at nominal spacing spans
    # 5 x 0.9 = 4.5 m end to end, so R_comm = 3.0 m leaves the line connected
    # but *genuinely multi-hop* -- the two end robots (4.5 m apart) cannot hear
    # each other and must be reached through intermediate robots. Consensus is
    # therefore not a disguised one-hop broadcast in the mode that matters most.
    # An N=6 keep grid (3x2, spacing 0.9) has maximum pairwise distance
    # ~2.01 m < 3.0 m, so keep is one-hop complete. The contrast between the two
    # regimes is deliberate and is measured, not assumed.
    r_comm: float = 3.0

    # Radius within which robot i can sense other robots directly. Sensing is
    # NOT used to populate the neighbour set in the nominal configuration --
    # neighbours come from communication only, which is the stricter and more
    # testable choice. Retained so the assumption is explicit and auditable.
    r_sense: float = 4.0

    # Obstacle observation radius. Matches the existing lidar_range so the
    # decentralized obstacle view is exactly what the robot's own sensor sees.
    r_obs: float = 3.0

    # Maximum accepted message age, in control steps. A neighbour whose newest
    # message is older than this is marked stale and excluded from N_i.
    # 3 steps = 0.45 s; at max_speed 0.9 m/s a neighbour can move at most
    # 0.405 m in that window, well inside nominal_spacing 0.9 m.
    delta_stale_steps: int = 3

    # Communication period and control period, in seconds. One beacon per
    # control step in the nominal configuration.
    t_comm: float = 0.15
    t_ctrl: float = 0.15

    # --- Link model. Nominal values; the stress test overrides them. ---
    symmetric: bool = True
    packet_loss: float = 0.0
    delay_steps: int = 0
    async_offset_steps: int = 0

    @property
    def delta_stale_seconds(self) -> float:
        return self.delta_stale_steps * self.t_ctrl


# Nominal link assumptions, stated once so documents and tests agree.
LINK_ASSUMPTIONS: Dict[str, str] = {
    "symmetric": (
        "Nominal: yes. (i,j) in E_c iff (j,i) in E_c. Justified because a "
        "single radio range gates both directions and the Metropolis-Hastings "
        "weight rule needs symmetry for the consensus average to be preserved. "
        "The stress test breaks symmetry only through independent per-direction "
        "packet loss, which is handled as message loss, not as a directed graph."
    ),
    "directed": (
        "Not assumed nominally. Asymmetric loss is modelled per-direction, so "
        "the *delivered* message graph can be transiently directed even though "
        "the link graph is symmetric."
    ),
    "time_varying": (
        "Yes. E_c^t is recomputed every communication period from current "
        "positions; robots enter and leave R_comm as the formation deforms."
    ),
    "lossy": (
        "Nominally lossless; the stress test sweeps 0/10/30/50 % independent "
        "per-message Bernoulli loss."
    ),
    "delayed": (
        "Nominally zero delay; the stress test sweeps 0/1/2/5 control steps of "
        "delivery latency. Delayed messages are accepted only while their age "
        "is <= delta_stale_steps."
    ),
    "connectivity": (
        "NOT assumed globally. Agreement claims are made only per connected "
        "component of G_c. Swarm-wide agreement is claimed only when G_c is "
        "connected, and that condition is measured per episode, never assumed."
    ),
}


# ---------------------------------------------------------------------------
# Decision-epoch / consensus parameters
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ConsensusParams:
    """Finite-round leaderless consensus parameters.

    `k_score` is selected on validation data only, from the predeclared grid
    below. The grid is fixed here *before* any run so the choice cannot be
    rationalised after seeing results.
    """

    k_score: int = 4
    # G6 REPAIR, Option A. Max-consensus propagates exactly one hop per round,
    # so covering a component of diameter D needs D rounds. The literal 4 was
    # unsound for N = 6, whose worst-case (chain) diameter is 5. The value is
    # DERIVED from ProtocolParams.max_team_size by
    # `parameters.derived_k_trigger`; the default below is a placeholder that
    # `ConsensusParams.for_protocol` overrides.
    k_trigger: int = 5          # max-consensus rounds for trigger propagation
    # Min/max confirmation propagates one hop per round exactly as the trigger
    # does, so the same diameter argument applies: leaving it at 4 would
    # under-cover the worst-case N=6 chain and a robot could be committed
    # without ever having heard the confirmation bounds.
    k_confirm: int = 5          # min/max-consensus rounds for mode confirmation
    h_commit: int = 10          # must match recovery_v2.rollout(h_commit=10)
    decision_interval: int = 25  # forced epoch cadence, control steps
    confirm_margin: float = 0.0  # minimum |z_keep - z_line| to accept a commit


# Predeclared before any run. Selection on validation layouts only.
K_SCORE_GRID: Tuple[int, ...] = (0, 1, 2, 3, 4, 6)

# Diameter note: for the N=6 line at nominal spacing with R_comm=3.0 the
# communication graph has diameter 2, so k_score >= 2 is the minimum that can
# propagate information end-to-end; the grid spans well past it in both
# directions so the validation choice is informative rather than forced.


# ---------------------------------------------------------------------------
# The decentralization contract
# ---------------------------------------------------------------------------
PERMITTED_LOCAL_SOURCES: FrozenSet[str] = frozenset({
    "self_state",              # own position, velocity
    "self_id_and_role",        # persistent ID, offline-configured formation role
    "local_obstacles",         # obstacles observed within r_obs by own sensor
    "one_hop_messages",        # beacons/consensus messages from N_i
    "shared_goal",             # mission goal / goal direction, same on all robots
    "shared_frame",            # shared coordinate frame (explicit assumption)
    "local_memory",            # own history, epoch counter, committed mode
    "committed_mode",          # own current committed mode
    "model_parameters",        # common offline-trained weights
    "controller_parameters",   # common fixed-controller gains
})

# Any deployable tensor/feature/callable touching one of these is a violation.
# `guards.py` enforces this list executably; it is not documentation only.
PROHIBITED_GLOBAL_SOURCES: FrozenSet[str] = frozenset({
    "joint_state",
    "full_swarm_graph",
    "out_of_range_robot_state",
    "swarm_centroid",
    "global_formation_error",
    "global_min_distance",
    "global_min_ttc",
    "global_obstacle_centroid",
    "global_map",
    "global_graph_pooling",
    "global_all_reduce",
    "centralized_mode_decision",
    "leader_selected_mode",
    "central_assignment_service",
    "joint_action_function",
    "oracle_rollout_outcome",
    "future_trajectory",
})

# Concrete observation keys that are global-state-derived and must never reach
# a deployable feature builder. Checked by name in guards.py and by the ego
# graph feature audit.
PROHIBITED_OBS_KEYS: FrozenSet[str] = frozenset({
    "positions",            # joint state
    "velocities",           # joint state
    "formation_error",      # derived from the swarm centroid
    "obstacles",            # full obstacle array, unbounded by sensor range
    "obstacle_velocities",
    "subteam_ids",          # split-mode remnant
    "bottleneck",           # computed from the joint state
    "progress",             # computed from the swarm centroid
    "topology_switches",
    "formation_scale_motion",
    "stall_counter",
})

# Observation keys that ARE permitted as shared mission constants, because they
# are identical on every robot and loaded before the mission rather than
# reconstructed at runtime. Each requires an explicit stated assumption.
SHARED_MISSION_CONSTANTS: FrozenSet[str] = frozenset({
    "goal",          # shared mission goal
    "corridor_dx",   # shared mission-frame direction
    "corridor_dy",
    "scenario",
})

# ---------------------------------------------------------------------------
# Disclosed information channel: neighbour degree
# ---------------------------------------------------------------------------
# An adversarial audit established that robot i is NOT strictly insulated from
# two-hop robots. A neighbour j transmits its own degree (required by the
# Metropolis-Hastings weight rule, and permitted by the protocol
# specification), and deg_j counts robots that may lie outside robot i's own
# communication range. If a two-hop robot enters or leaves j's range, deg_j
# changes, and w_ij = 1/(1 + max(deg_i, deg_j)) changes with it -- 1/3 -> 1/2 in
# the audited case. That is a real, deployable path by which a robot outside
# N_i influences robot i.
#
# It is recorded here rather than argued away. The channel is:
#   - one scalar per neighbour per message, never an identity or a state;
#   - a count, so it cannot be inverted to recover who or where;
#   - unavoidable for ANY degree-weighted consensus rule (Metropolis-Hastings,
#     Laplacian, maximum-degree), and the alternatives are worse: a fixed global
#     weight would require knowing N, and an unweighted rule can diverge.
#
# The consequence for claims: "robot i accesses only one-hop information" is
# true of state, and false of this single aggregate. Documents and tests must
# say "except through neighbour degree", and the test asserting two-hop
# invariance pins the exception instead of choosing a case that avoids it.
DISCLOSED_AGGREGATE_CHANNELS: Dict[str, str] = {
    "neighbour_degree": (
        "deg_j in the beacon and the consensus message is a scalar count over "
        "robot j's one-hop set, which may include robots outside N_i. Changing "
        "a two-hop robot can therefore change w_ij. Bounded to one integer per "
        "neighbour per message; carries no identity, position, or state."
    ),
}

# Information that may be used ONLY during training / offline analysis.
TRAINING_ONLY_SOURCES: FrozenSet[str] = frozenset({
    "recovery_event_v2_label",   # team-level y_tau; supervision target only
    "oracle_mode",
    "global_episode_metrics",
    "centralized_diagnostic_selector",
})


@dataclass(frozen=True)
class RuntimeFlags:
    """Runtime enforcement switch.

    `strict_decentralized_runtime` must be True for every decentralized
    validation and test run. When enabled, any attempt to read a prohibited
    global source from a deployable path raises `CentralizedAccessError`.
    """

    strict_decentralized_runtime: bool = True


class CentralizedAccessError(RuntimeError):
    """Raised when deployable code touches prohibited global information."""

    __test__ = False  # never collected as a pytest class


@dataclass(frozen=True)
class RobotView:
    """Everything robot i is allowed to know at one control step.

    Deliberately a closed container: if a quantity is not a field here, no
    deployable function can obtain it. Constructed by `comms.py` from the
    robot's own sensors and its neighbour table -- never by slicing the joint
    state directly in a deployable path.
    """

    robot_id: int
    position: Tuple[float, float]
    velocity: Tuple[float, float]
    role_keep: Tuple[float, float]
    role_line: Tuple[float, float]
    committed_mode: int
    epoch_id: int
    steps_since_decision: int
    local_progress: float
    goal: Tuple[float, float]
    mission_dir: Tuple[float, float]
    neighbours: Sequence["NeighbourRecord"] = field(default_factory=tuple)
    obstacles: Sequence[Tuple[float, float, float]] = field(default_factory=tuple)

    def neighbour_ids(self) -> Tuple[int, ...]:
        return tuple(nb.robot_id for nb in self.neighbours)

    @property
    def degree(self) -> int:
        return len(self.neighbours)


@dataclass(frozen=True)
class NeighbourRecord:
    """One-hop neighbour entry, always ego-relative.

    Positions are stored as `rel_position` (p_j - p_i) rather than absolute, so
    a neighbour's absolute coordinates never survive into a feature builder.
    """

    robot_id: int
    rel_position: Tuple[float, float]
    rel_velocity: Tuple[float, float]
    role_keep: Tuple[float, float]
    role_line: Tuple[float, float]
    committed_mode: int
    epoch_id: int
    message_age_steps: int
    degree: int
    link_valid: bool
    packet_loss_estimate: float = 0.0

    @property
    def distance(self) -> float:
        dx, dy = self.rel_position
        return float((dx * dx + dy * dy) ** 0.5)


def describe_contract() -> Dict[str, object]:
    """Machine-readable contract, consumed by docs and by the guard tests."""
    return {
        "modes": {"keep": KEEP, "line": LINE},
        "comm": CommParams(),
        "consensus": ConsensusParams(),
        "k_score_grid": K_SCORE_GRID,
        "permitted": sorted(PERMITTED_LOCAL_SOURCES),
        "prohibited": sorted(PROHIBITED_GLOBAL_SOURCES),
        "prohibited_obs_keys": sorted(PROHIBITED_OBS_KEYS),
        "shared_mission_constants": sorted(SHARED_MISSION_CONSTANTS),
        "training_only": sorted(TRAINING_ONLY_SOURCES),
        "link_assumptions": LINK_ASSUMPTIONS,
    }
