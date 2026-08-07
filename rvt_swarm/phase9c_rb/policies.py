"""Source policies S0-S5 (RB-12).

One typed interface. Every policy receives a robot-local view, its own lifecycle
state, immutable local topology metadata, the shared mission clock, the
source-job seed and the horizon -- and nothing else. Headroom, family id, future
outcomes, future obstacle or disturbance state, the global task result and
final-test metadata are absent from the type, so they cannot be read even by
accident.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Mapping, Optional, Sequence, Tuple

from ..phase8e.protocol import s3_local_geometric_decision
from ..topology_registry import COMPACT, LINE

Vec2 = Tuple[float, float]

S0 = "S0_SCRIPTED_DIAGNOSTIC"
S1 = "S1_ALWAYS_COMPACT"
S2 = "S2_ALWAYS_LINE"
S3 = "S3_FROZEN_LOCAL_GEOMETRIC_SELECTOR"
S4 = "S4_FROZEN_TRANSITION_PROTOCOL"
S5 = "S5_BOUNDED_PERTURBATION"

ALL_SOURCE_POLICIES: Tuple[str, ...] = (S0, S1, S2, S3, S4, S5)


class SourcePolicy:
    """Typed base. Subclasses override only what their contract specifies."""

    policy_id = "UNSPECIFIED"
    offline_collection_only = False

    def __init__(self, contract: Mapping[str, object], seed: int, horizon_seconds: float,
                 team_size: int) -> None:
        self.contract = contract
        self.seed = int(seed)
        self.horizon_seconds = float(horizon_seconds)
        self.team_size = int(team_size)
        self.fired: Dict[object, bool] = {}

    def observe(self, session, robot, view, controller_input) -> None:
        """Called once per robot per control step with robot-local data only."""

    def acceleration_disturbance(self, session, robot) -> Vec2:
        return (0.0, 0.0)

    def initial_topology_override(self) -> Optional[int]:
        return None


class ScriptedDiagnosticPolicy(SourcePolicy):
    """S0 -- offline collection only. Bypasses agreement, never safety.

    Event timing follows the Phase 8E-PC-ET addendum: each declared event is
    anchored to a **mission landmark**, specifically the earliest nominal local
    observability of the corresponding physical feature. The superseded
    fraction-of-horizon table is not used, and no absolute event time in seconds
    exists in this class.

    S0 may read the offline compiled landmark because it is explicitly an
    offline scripted collection policy; robot-local deployment claims do not
    apply to it. It still never sets the topology directly -- every event enters
    the real Phase 7 protocol.
    """

    policy_id = S0
    offline_collection_only = True

    def __init__(self, contract, seed, horizon_seconds, team_size, family_id: str,
                 event_plan=()) -> None:
        super().__init__(contract, seed, horizon_seconds, team_size)
        # `event_plan` is a tuple of SourceEvent from
        # `phase8e.event_timing.build_family_event_plan`. It carries landmark
        # trigger positions, never times.
        self.event_plan = tuple(event_plan)

    def observe(self, session, robot, view, controller_input) -> None:
        if robot.robot_id != 0:
            return                      # one scripted origination, not N duplicates
        progress = session._longitudinal_progress()
        for index, event in enumerate(self.event_plan):
            if self.fired.get(index):
                continue
            if index > 0 and not self.fired.get(index - 1):
                break                   # declared sequence order is preserved
            trigger = event.trigger_longitudinal_meters
            if trigger is None:
                continue
            if progress + 1e-12 < trigger:
                continue
            self.fired[index] = True    # one-shot: skipped, never moved
            if event.candidate_topology != robot.committed_topology:
                session.request_candidate(robot, event.candidate_topology,
                                          event.event_type)


class FixedTopologyPolicy(SourcePolicy):
    """S1 / S2 -- hold one topology, issue no request, create no epoch."""

    def __init__(self, contract, seed, horizon_seconds, team_size, topology_id: int) -> None:
        super().__init__(contract, seed, horizon_seconds, team_size)
        self.topology_id = int(topology_id)
        self.policy_id = S1 if topology_id == COMPACT else S2
        self.offline_collection_only = topology_id == LINE

    def initial_topology_override(self) -> Optional[int]:
        # S2 is the sole initialization specialisation: LINE role targets at
        # t=0 through the offline forced-topology interface, with no epoch.
        return LINE if self.topology_id == LINE else None


class LocalGeometricSelectorPolicy(SourcePolicy):
    """S3 -- the only deployable selector. Local observations only.

    Thresholds come from topology geometry and physical configuration through
    the frozen `s3_local_geometric_decision`; this class supplies the *width
    statistic*, measured from the robot's own ego-relative support discs in the
    role-dependent lookahead sector. It never sees a global corridor width, a
    family id, a headroom category or any future value.
    """

    policy_id = S3

    def __init__(self, contract, seed, horizon_seconds, team_size, runtime_config) -> None:
        super().__init__(contract, seed, horizon_seconds, team_size)
        self.runtime_config = runtime_config
        self.evidence_seconds: Dict[int, float] = {}
        self.last_request_time: Dict[int, float] = {}

    def _required_width(self, session, robot, topology_id: int) -> float:
        surface_margin = 0.02
        span = _lateral_role_span(session, topology_id)
        return span + 2.0 * (float(self.runtime_config.physical.robot_radius_meters)
                             + surface_margin)

    def observe(self, session, robot, view, controller_input) -> None:
        lookahead = float(self.runtime_config.derived.lookahead_distance_meters)
        direction = view.mission_dir
        lateral = (-direction[1], direction[0])

        left = right = None
        complete_open = True
        for (ox, oy, radius) in view.obstacles:
            longitudinal = ox * direction[0] + oy * direction[1]
            offset = ox * lateral[0] + oy * lateral[1]
            if not (0.0 <= longitudinal <= lookahead):
                continue
            complete_open = False
            inner = abs(offset) - radius
            if offset >= 0.0:
                left = inner if left is None else min(left, inner)
            else:
                right = inner if right is None else min(right, inner)

        width: Optional[float] = None
        complete_observation = complete_open or (left is not None and right is not None)
        if left is not None and right is not None:
            width = left + right

        elapsed = self.evidence_seconds.get(robot.robot_id, 0.0) + session.control_period
        self.evidence_seconds[robot.robot_id] = elapsed

        decision = s3_local_geometric_decision(
            robot.committed_topology,
            measured_width_meters=width,
            complete_open_observation=complete_open,
            complete_observation=complete_observation,
            line_required_width_meters=self._required_width(session, robot, LINE),
            compact_required_width_meters=self._required_width(session, robot, COMPACT),
            spacing_margin_meters=float(self.runtime_config.formation.spacing_margin_meters),
            evidence_duration_seconds=elapsed,
            evidence_persistence_seconds=float(
                self.runtime_config.protocol.evidence_persistence_seconds),
        )
        if decision in ("REQUEST_LINE", "REQUEST_COMPACT"):
            commitment = float(self.runtime_config.protocol.commitment_seconds)
            last = self.last_request_time.get(robot.robot_id)
            if last is not None and session.time_seconds - last < commitment:
                return
            candidate = LINE if decision == "REQUEST_LINE" else COMPACT
            # Frozen event vocabulary: constriction drives COMPACT->LINE,
            # opening drives LINE->COMPACT.
            event_type = "local_constriction" if candidate == LINE else "local_opening"
            if session.request_candidate(robot, candidate, event_type):
                self.last_request_time[robot.robot_id] = session.time_seconds
                self.evidence_seconds[robot.robot_id] = 0.0


class FrozenTransitionProtocolPolicy(SourcePolicy):
    """S4 -- offline collection only; exercises the real Phase 7 protocol.

    Phase 8E-PC-ET replaced the `0.25H` / `0.65H` horizon-fraction trigger with
    **local evidence origination**: a robot originates at the first eligible
    control step at which the frozen local geometric evidence predicate enters
    `LOCAL_LINE_REQUIRED` (while COMPACT is committed) or
    `LOCAL_OPENING_FOR_COMPACT` (while LINE is committed).

    The detecting robot is not a leader -- any robot may detect first, the event
    propagates neighbour-only through the real leaderless protocol, and
    detection does not imply authorization: readiness still gates commitment.
    If local evidence never occurs, S4 correctly produces no transition.

    The predicate is the *same* frozen `s3_local_geometric_decision` S3 uses; no
    second threshold system exists. The candidate score remains exactly 1.0, so
    Phase 5 output cannot leak in.
    """

    policy_id = S4
    offline_collection_only = True

    def __init__(self, contract, seed, horizon_seconds, team_size, runtime_config) -> None:
        super().__init__(contract, seed, horizon_seconds, team_size)
        self.evidence = LocalGeometricSelectorPolicy(
            contract, seed, horizon_seconds, team_size, runtime_config)

    def observe(self, session, robot, view, controller_input) -> None:
        # Delegates to the shared local evidence interface. Whichever robot
        # crosses its own threshold first originates; there is no fixed
        # originator and no clock term.
        self.evidence.observe(session, robot, view, controller_input)


class BoundedPerturbationPolicy(SourcePolicy):
    """S5 -- S1 base plus exactly one bounded acceleration impulse.

    Seed modulo N picks the robot without reference to any outcome; the impulse
    starts at the first control tick at or after 0.40H and lasts one control
    period. It is never regenerated, repeated, or moved toward a decision slot.
    """

    policy_id = S5
    offline_collection_only = True

    def __init__(self, contract, seed, horizon_seconds, team_size, maximum_acceleration) -> None:
        super().__init__(contract, seed, horizon_seconds, team_size)
        self.target_robot_id = self.seed % max(1, team_size)
        self.start_seconds = 0.40 * horizon_seconds
        self.magnitude = 0.25 * float(maximum_acceleration)
        self.applied = False

    def acceleration_disturbance(self, session, robot) -> Vec2:
        if self.applied or robot.robot_id != self.target_robot_id:
            return (0.0, 0.0)
        if session.time_seconds + 1e-12 < self.start_seconds:
            return (0.0, 0.0)
        self.applied = True
        vector = session.s5_stream.uniform_disk(
            self.magnitude, "s5", robot.robot_id, session.control_step)
        direction = session.mission_direction
        lateral = (-direction[1], direction[0])
        return (vector[0] * direction[0] + vector[1] * lateral[0],
                vector[0] * direction[1] + vector[1] * lateral[1])


def _lateral_role_span(session, topology_id: int) -> float:
    """Lateral extent of the role template, from local topology metadata."""
    offsets = [robot.role_offset(topology_id)[1] for robot in session.robots]
    return float(max(offsets) - min(offsets)) if offsets else 0.0


def build_source_policy(policy_id: str, *, contracts: Mapping[str, object], seed: int,
                        horizon_seconds: float, team_size: int, family_id: str,
                        runtime_config, event_plan=()) -> SourcePolicy:
    contract = dict(contracts["policies"])[policy_id]            # type: ignore[index]
    if policy_id == S0:
        return ScriptedDiagnosticPolicy(
            contract, seed, horizon_seconds, team_size, family_id, event_plan or ())
    if policy_id == S1:
        return FixedTopologyPolicy(contract, seed, horizon_seconds, team_size, COMPACT)
    if policy_id == S2:
        return FixedTopologyPolicy(contract, seed, horizon_seconds, team_size, LINE)
    if policy_id == S3:
        return LocalGeometricSelectorPolicy(
            contract, seed, horizon_seconds, team_size, runtime_config)
    if policy_id == S4:
        return FrozenTransitionProtocolPolicy(
            contract, seed, horizon_seconds, team_size, runtime_config)
    if policy_id == S5:
        return BoundedPerturbationPolicy(
            contract, seed, horizon_seconds, team_size,
            runtime_config.physical.maximum_acceleration_meters_per_second_squared)
    raise ValueError(f"unknown source policy {policy_id!r}")
