"""Disabled-by-default strict diagnostic runtime for Phase 7 transitions."""

from __future__ import annotations

import math
import time
from dataclasses import asdict, dataclass, replace
from typing import Callable, Dict, Iterable, Mapping, Optional, Sequence, Tuple

import numpy as np

from ..runtime_configuration import ProtocolConfig, RuntimeConfig
from ..topology_registry import (
    PRIMARY_TOPOLOGY_IDS,
    construct_topology,
    generate_persistent_roles,
    rotate_template_vector,
    template_world_positions,
)
from .ego_graph_v2 import prepare_robot_local_topology_metadata
from .forced_topology_runtime import ForcedTopologyRuntimeAdapter
from .formation_metric_v3 import EPSILON_FORM, e_inf
from .phase6_qualification import (
    semi_implicit_acceleration_step,
    simulate_received_robot_views,
)
from .local_control_types import RobotLocalControllerInput, RobotLocalControllerOutput
from .roles import RoleAssignment
from .transition_admissibility import assess_transition_admissibility
from .transition_messages import TransitionByteLedger
from .transition_protocol import (
    AgreementResult,
    TransitionProtocolNode,
    TransitionProtocolRuntimeOptions,
    communication_graph_diameter,
    evaluate_confirmation_agreement,
    evaluate_intent_propagation,
    evaluate_lifecycle_status_agreement,
    evaluate_readiness_agreement,
    evaluate_score_agreement,
    flood_transition_messages,
)
from .transition_readiness import (
    RobotLocalReadinessCertificate,
    RobotLocalTransitionInput,
    evaluate_robot_local_transition_readiness,
)
from .transition_execution import (
    RobotLocalTransitionExecutor,
    TransitionMotionProfile,
    derive_transition_motion_profile,
    prepare_robot_local_role_space_path,
)


PHASE7_RUNTIME_SCHEMA_VERSION = "rvt-phase7-strict-transition-runtime/v1"
PHASE7_OPEN_SPACE_FIXTURES: Tuple[str, ...] = (
    "exact_source",
    "bounded_source_perturbation",
    "translated_mission",
    "rotated_mission",
)
PHASE7_GRAPH_FAMILIES: Tuple[str, ...] = (
    "path",
    "ring",
    "star",
    "bounded_degree_geometric",
    "sparse_random_connected",
    "complete",
    "temporary_disconnection",
)
TRANSITION_EXECUTION_STRATEGIES: Tuple[str, ...] = (
    "immediate_target_switch",
    "generic_role_space_profile",
)


@dataclass(frozen=True)
class LocalProjectionExecutionObservation:
    """One robot-local projection call exposed to an offline trace sink."""

    execution_step: int
    transition_progress: float
    controller_input: RobotLocalControllerInput
    controller_output: RobotLocalControllerOutput


@dataclass(frozen=True)
class Phase7TransitionEpisodeResult:
    schema_version: str
    team_size: int
    source_topology: int
    target_topology: int
    fixture: str
    graph_family: str
    graph_diameter: int
    configured_diameter_bound: int
    k_intent: int
    k_score: int
    k_ready: int
    k_confirm: int
    intent_time_seconds: float
    propagation_completion_seconds: Optional[float]
    score_agreement_completion_seconds: Optional[float]
    first_readiness_state_by_robot: Mapping[int, str]
    readiness_margin_by_robot: Mapping[int, float]
    last_robot_to_become_safe: Optional[int]
    all_ready_time_seconds: Optional[float]
    confirmation_time_seconds: Optional[float]
    commit_time_seconds: Optional[float]
    target_tube_entry_step: Optional[int]
    dwell_completion_step: Optional[int]
    collision_free: bool
    minimum_robot_robot_clearance_meters: float
    minimum_robot_obstacle_clearance_meters: Optional[float]
    projection_intervention_count: int
    projection_infeasible_count: int
    solver_failure_count: int
    completion_time_seconds: Optional[float]
    abort_or_timeout: Optional[str]
    mode_epoch_count: int
    no_op_epoch_count: int
    retry_epoch_count: int
    actual_communication_bytes: int
    bytes_by_phase: Mapping[str, int]
    retransmission_bytes: int
    protocol_instance_count: int
    partial_commitment: bool
    strict_guard_violations: Tuple[str, ...]
    learned_model_calls: int
    controller_calls: int
    local_protocol_compute_seconds: Tuple[float, ...]
    controller_compute_seconds: Tuple[float, ...]
    state_trace_by_robot: Mapping[int, Tuple[str, ...]]
    assumption_violation: Optional[str]
    event_processing_seconds: Tuple[float, ...] = ()
    message_serialization_seconds: Tuple[float, ...] = ()
    message_ingestion_seconds: Tuple[float, ...] = ()
    readiness_compute_seconds: Tuple[float, ...] = ()
    metric_compute_seconds: Tuple[float, ...] = ()

    @property
    def transition_success(self) -> bool:
        return bool(
            self.abort_or_timeout is None
            and self.collision_free
            and self.dwell_completion_step is not None
            and self.mode_epoch_count == 1
            and not self.partial_commitment
        )

    def source(self) -> Dict[str, object]:
        result = asdict(self)
        result["transition_success"] = self.transition_success
        timing_fields = (
            "local_protocol_compute_seconds",
            "controller_compute_seconds",
            "event_processing_seconds",
            "message_serialization_seconds",
            "message_ingestion_seconds",
            "readiness_compute_seconds",
            "metric_compute_seconds",
        )
        timing_summary = {}
        for field_name in timing_fields:
            values = tuple(float(value) for value in result.pop(field_name))
            ordered = tuple(sorted(values))

            def percentile(percent: float) -> float:
                if not ordered:
                    return 0.0
                index = (len(ordered) - 1) * percent / 100.0
                lower = int(math.floor(index))
                upper = int(math.ceil(index))
                if lower == upper:
                    return ordered[lower]
                weight = index - lower
                return ordered[lower] * (1.0 - weight) + ordered[upper] * weight

            timing_summary[field_name] = {
                "sample_count": len(ordered),
                "median": percentile(50.0),
                "p95": percentile(95.0),
                "p99": percentile(99.0),
            }
        result["timing_summary_seconds"] = timing_summary
        return result


def communication_graph(
    team_size: int,
    family: str,
    *,
    seed: int = 7001,
) -> Dict[int, Tuple[int, ...]]:
    if family not in PHASE7_GRAPH_FAMILIES:
        raise ValueError("unknown Phase 7 communication graph family")
    if team_size <= 0:
        raise ValueError("team size must be positive")
    adjacency: Dict[int, set[int]] = {robot_id: set() for robot_id in range(team_size)}

    def connect(a: int, b: int) -> None:
        if a != b:
            adjacency[a].add(b)
            adjacency[b].add(a)

    base_family = "path" if family == "temporary_disconnection" else family
    if base_family == "path":
        for robot_id in range(team_size - 1):
            connect(robot_id, robot_id + 1)
    elif base_family == "ring":
        for robot_id in range(team_size):
            connect(robot_id, (robot_id + 1) % team_size)
    elif base_family == "star":
        for robot_id in range(1, team_size):
            connect(0, robot_id)
    elif base_family == "complete":
        for first in range(team_size):
            for second in range(first + 1, team_size):
                connect(first, second)
    elif base_family == "bounded_degree_geometric":
        for robot_id in range(team_size):
            connect(robot_id, (robot_id + 1) % team_size)
            if team_size >= 6:
                connect(robot_id, (robot_id + 2) % team_size)
    elif base_family == "sparse_random_connected":
        for robot_id in range(team_size - 1):
            connect(robot_id, robot_id + 1)
        rng = np.random.default_rng(seed + team_size)
        candidates = [
            (first, second)
            for first in range(team_size)
            for second in range(first + 2, team_size)
            if not (first == 0 and second == team_size - 1)
        ]
        rng.shuffle(candidates)
        for first, second in candidates[:max(1, team_size // 3)]:
            connect(first, second)
    return {
        robot_id: tuple(sorted(neighbours))
        for robot_id, neighbours in adjacency.items()
    }


def runtime_config_for_transition_graph(
    team_size: int,
    adjacency: Mapping[int, Iterable[int]],
) -> RuntimeConfig:
    members = tuple(range(team_size))
    diameter = communication_graph_diameter(members, adjacency)
    declared = team_size - 1 if diameter < 0 else diameter
    base = RuntimeConfig.for_team_size(team_size, "path")
    return replace(
        base,
        protocol=replace(
            base.protocol,
            declared_maximum_component_diameter_hops=declared,
        ),
    )


def temporary_disconnection_schedule(
    adjacency: Mapping[int, Iterable[int]],
    rounds: int,
) -> Tuple[Mapping[int, Tuple[int, ...]], ...]:
    if rounds <= 0:
        return ()
    disconnected = {robot_id: set(peers) for robot_id, peers in adjacency.items()}
    n = len(disconnected)
    if n > 1:
        left = n // 2 - 1
        right = left + 1
        disconnected[left].discard(right)
        disconnected[right].discard(left)
    broken = {
        robot_id: tuple(sorted(peers))
        for robot_id, peers in disconnected.items()
    }
    # Break the middle causal round, when endpoint records have reached the cut.
    # With k equal to the static diameter this costs one required hop; an extra
    # retry round can recover after the link returns.
    cut_round = rounds // 2
    return tuple(
        broken if round_index == cut_round else adjacency
        for round_index in range(rounds)
    )


def _minimum_pair_distance(positions: np.ndarray) -> float:
    minimum = float("inf")
    for first in range(len(positions)):
        for second in range(first + 1, len(positions)):
            minimum = min(
                minimum,
                float(np.linalg.norm(positions[first] - positions[second])),
            )
    return minimum


def _initial_state(
    team_size: int,
    source_topology: int,
    fixture: str,
    runtime_config: RuntimeConfig,
) -> Tuple[np.ndarray, np.ndarray, Tuple[float, float], Tuple[float, float]]:
    if fixture not in PHASE7_OPEN_SPACE_FIXTURES:
        raise ValueError("unknown Phase 7 open-space fixture")
    heading = math.pi / 3.0 if fixture == "rotated_mission" else 0.0
    direction = (math.cos(heading), math.sin(heading))
    origin = (2.0, -1.25) if fixture == "translated_mission" else (0.0, 0.0)
    roles = generate_persistent_roles(team_size)
    template = construct_topology(
        source_topology, runtime_config.formation, role_set=roles
    )
    positions = np.asarray(
        template_world_positions(template, origin, direction), dtype=np.float64
    )
    velocities = np.zeros_like(positions)
    if fixture == "bounded_source_perturbation":
        rng = np.random.default_rng(71000 + 100 * team_size + source_topology)
        positions += rng.uniform(
            -runtime_config.formation.spacing_margin_meters,
            runtime_config.formation.spacing_margin_meters,
            size=positions.shape,
        )
        velocity_bound = (
            runtime_config.physical.maximum_speed_meters_per_second
            * runtime_config.physical.control_period_seconds
        )
        velocities += rng.uniform(-velocity_bound, velocity_bound, size=velocities.shape)
    return positions, velocities, origin, direction


class StrictTransitionRuntime:
    """Centralized delivery boundary containing independent protocol nodes."""

    def __init__(
        self,
        team_size: int,
        source_topology: int,
        adjacency: Mapping[int, Iterable[int]],
        *,
        options: TransitionProtocolRuntimeOptions = TransitionProtocolRuntimeOptions(),
    ) -> None:
        if not options.transition_protocol_v1_enabled:
            raise RuntimeError("strict transition runtime is disabled by default")
        self.member_ids = tuple(range(team_size))
        self.adjacency = {
            robot_id: tuple(sorted(int(peer) for peer in adjacency[robot_id]))
            for robot_id in self.member_ids
        }
        self.runtime_config = runtime_config_for_transition_graph(
            team_size, self.adjacency
        )
        self.role_set = generate_persistent_roles(team_size)
        self.local_metadata = tuple(
            prepare_robot_local_topology_metadata(
                self.role_set, robot_id, self.runtime_config.formation
            )
            for robot_id in self.member_ids
        )
        self.nodes = tuple(
            TransitionProtocolNode(
                robot_id,
                self.member_ids,
                self.runtime_config,
                source_topology,
                options,
            )
            for robot_id in self.member_ids
        )
        if len({id(node) for node in self.nodes}) != team_size:
            raise RuntimeError("protocol nodes share a mutable lifecycle instance")
        self.ledger = TransitionByteLedger()
        self.readiness_compute_seconds: list[float] = []
        self.serialization_compute_seconds: list[float] = []
        self.ingestion_compute_seconds: list[float] = []

    def record_flood_timings(self, flood: object) -> None:
        self.serialization_compute_seconds.extend(
            getattr(flood, "serialization_compute_seconds")
        )
        self.ingestion_compute_seconds.extend(
            getattr(flood, "ingestion_compute_seconds")
        )

    def local_readiness_certificates(
        self,
        positions: np.ndarray,
        velocities: np.ndarray,
        source_topology: int,
        target_topology: int,
        lifecycle_id: int,
        epoch_id: int,
        timestamp_seconds: float,
        goal_origin: Tuple[float, float],
        mission_direction: Tuple[float, float],
        *,
        observed_extent_by_robot: Optional[Mapping[int, float]] = None,
        local_obstacles_by_robot: Optional[Mapping[int, tuple]] = None,
    ) -> Tuple[RobotLocalReadinessCertificate, ...]:
        roles = RoleAssignment.from_index(
            len(self.member_ids), self.runtime_config.formation.nominal_spacing_meters
        )
        views = simulate_received_robot_views(
            positions,
            velocities,
            roles,
            source_topology,
            goal_origin,
            mission_direction,
            self.runtime_config,
        )
        source_adapters = tuple(
            ForcedTopologyRuntimeAdapter(
                self.runtime_config,
                self.local_metadata[robot_id],
                source_topology,
            )
            for robot_id in self.member_ids
        )
        certificates = []
        for robot_id in self.member_ids:
            controller_input = source_adapters[robot_id].build_input(
                views[robot_id], timestamp_seconds
            )
            obstacles = (
                tuple(local_obstacles_by_robot.get(robot_id, ()))
                if local_obstacles_by_robot is not None
                else controller_input.obstacle_states
            )
            local_input = RobotLocalTransitionInput(
                observer_robot_id=robot_id,
                observer_role_id=self.local_metadata[robot_id].observer_role_id,
                team_size=len(self.member_ids),
                timestamp_seconds=timestamp_seconds,
                lifecycle_id=lifecycle_id,
                epoch_id=epoch_id,
                committed_topology_id=self.nodes[robot_id].committed_topology,
                source_topology_id=source_topology,
                candidate_topology_id=target_topology,
                mission_direction=mission_direction,
                own_position_meters=tuple(map(float, positions[robot_id])),
                own_velocity_meters_per_second=tuple(map(float, velocities[robot_id])),
                source_topology=self.local_metadata[robot_id].candidate(source_topology),
                target_topology=self.local_metadata[robot_id].candidate(target_topology),
                peer_states=controller_input.peer_states,
                obstacle_states=obstacles,
                observed_extent_meters=(
                    observed_extent_by_robot.get(
                        robot_id,
                        self.runtime_config.sensing.obstacle_sensing_range_meters,
                    )
                    if observed_extent_by_robot is not None
                    else self.runtime_config.sensing.obstacle_sensing_range_meters
                ),
            )
            started = time.perf_counter()
            certificate = evaluate_robot_local_transition_readiness(
                local_input, self.runtime_config
            )
            self.readiness_compute_seconds.append(time.perf_counter() - started)
            certificates.append(certificate)
        return tuple(certificates)


def _failure_result(
    runtime: StrictTransitionRuntime,
    source: int,
    target: int,
    fixture: str,
    graph_family: str,
    trace: Dict[int, list[str]],
    reason: str,
    intent_time: float,
    *,
    propagation: Optional[float] = None,
    score: Optional[float] = None,
    readiness: Tuple[RobotLocalReadinessCertificate, ...] = (),
    all_ready: Optional[float] = None,
    confirmation: Optional[float] = None,
    assumption_violation: Optional[str] = None,
) -> Phase7TransitionEpisodeResult:
    config = runtime.runtime_config
    ledger_report = runtime.ledger.report()
    return Phase7TransitionEpisodeResult(
        PHASE7_RUNTIME_SCHEMA_VERSION,
        len(runtime.member_ids), source, target, fixture, graph_family,
        communication_graph_diameter(runtime.member_ids, runtime.adjacency),
        config.derived.component_diameter_bound_hops,
        config.derived.k_intent_rounds, config.derived.k_score_rounds,
        config.derived.k_ready_rounds, config.derived.k_confirm_rounds,
        intent_time, propagation, score,
        {cert.observer_robot_id: cert.readiness_state for cert in readiness},
        {cert.observer_robot_id: cert.readiness_margin_meters for cert in readiness},
        None, all_ready, confirmation, None, None, None, True,
        config.formation.nominal_spacing_meters, None, 0, 0, 0, None, reason,
        sum(node.mode_epoch_count for node in runtime.nodes) // len(runtime.nodes),
        0, 0, int(ledger_report["total_bytes"]),
        ledger_report["bytes_by_phase"], int(ledger_report["retransmission_bytes"]),
        len(runtime.nodes), False, (), 0, 0, (), (),
        {robot_id: tuple(states) for robot_id, states in trace.items()},
        assumption_violation,
    )


def run_phase7_transition_episode(
    team_size: int,
    source_topology: int,
    target_topology: int,
    fixture: str = "exact_source",
    graph_family: str = "path",
    *,
    execution_strategy: str = "immediate_target_switch",
    projection_observer: Optional[
        Callable[[LocalProjectionExecutionObservation], None]
    ] = None,
) -> Phase7TransitionEpisodeResult:
    if source_topology not in PRIMARY_TOPOLOGY_IDS or target_topology not in PRIMARY_TOPOLOGY_IDS:
        raise ValueError("Phase 7 episode requires primary topology IDs")
    if execution_strategy not in TRANSITION_EXECUTION_STRATEGIES:
        raise ValueError("unknown transition execution strategy")
    adjacency = communication_graph(team_size, graph_family)
    options = TransitionProtocolRuntimeOptions(transition_protocol_v1_enabled=True)
    runtime = StrictTransitionRuntime(
        team_size, source_topology, adjacency, options=options
    )
    config = runtime.runtime_config
    admissibility = assess_transition_admissibility(
        source_topology, target_topology, source_topology,
        runtime.role_set, config,
    )
    trace: Dict[int, list[str]] = {
        robot_id: [runtime.nodes[robot_id].state]
        for robot_id in runtime.member_ids
    }
    if not admissibility.admitted:
        return _failure_result(
            runtime, source_topology, target_topology, fixture, graph_family,
            trace, "inadmissible:" + ",".join(admissibility.reasons), 0.0,
        )
    positions, velocities, goal_origin, direction = _initial_state(
        team_size, source_topology, fixture, config
    )
    period = config.communication.communication_period_seconds
    protocol_latencies: list[float] = []
    t = 0.0
    started = time.perf_counter()
    intent = runtime.nodes[0].request_intent(
        1, target_topology, "externally_forced_diagnostic", t
    )
    protocol_latencies.append(time.perf_counter() - started)
    if intent is None:
        return _failure_result(
            runtime, source_topology, target_topology, fixture, graph_family,
            trace, "source_equals_target", t,
        )
    intent_schedule = runtime.adjacency
    intent_flood = flood_transition_messages(
        runtime.member_ids, {0: (intent,)}, intent_schedule,
        config.derived.k_intent_rounds, ledger=runtime.ledger,
    )
    runtime.record_flood_timings(intent_flood)
    t += config.derived.k_intent_rounds * period
    intent_result = evaluate_intent_propagation(
        intent_flood, runtime.member_ids, now_seconds=t,
        maximum_age_seconds=(
            config.protocol.evidence_persistence_seconds
            + config.derived.k_intent_rounds * period
        ),
    )
    if not intent_result.agreed:
        return _failure_result(
            runtime, source_topology, target_topology, fixture, graph_family,
            trace, intent_result.reason, 0.0, assumption_violation=(
                "communication_contract" if graph_family == "temporary_disconnection" else None
            ),
        )
    propagation_time = t
    for node in runtime.nodes:
        node.adopt_intent(intent, t)
        trace[node.robot_id].append(node.state)
        node.begin_score_agreement(t)
        trace[node.robot_id].append(node.state)
    score_messages = {
        node.robot_id: (node.score_message(1.0, "bounded_diagnostic", t),)
        for node in runtime.nodes
    }
    score_flood = flood_transition_messages(
        runtime.member_ids, score_messages, runtime.adjacency,
        config.derived.k_score_rounds, ledger=runtime.ledger,
    )
    runtime.record_flood_timings(score_flood)
    t += config.derived.k_score_rounds * period
    score_result = evaluate_score_agreement(
        score_flood, runtime.member_ids, intent, now_seconds=t,
        maximum_age_seconds=(
            config.derived.k_score_rounds * period
            + config.communication.maximum_message_age_seconds
        ),
        threshold=options.deterministic_score_threshold,
    )
    for node in runtime.nodes:
        node.accept_score_agreement(score_result, t)
        trace[node.robot_id].append(node.state)
    if not score_result.agreed:
        return _failure_result(
            runtime, source_topology, target_topology, fixture, graph_family,
            trace, score_result.reason, 0.0, propagation=propagation_time,
            score=t,
        )
    score_time = t
    started = time.perf_counter()
    certificates = runtime.local_readiness_certificates(
        positions, velocities, source_topology, target_topology,
        intent.lifecycle_id, intent.epoch_id, t, goal_origin, direction,
    )
    protocol_latencies.append(time.perf_counter() - started)
    for node in runtime.nodes:
        node.begin_all_ready_agreement(t)
        trace[node.robot_id].append(node.state)
    readiness_messages = {
        node.robot_id: (
            node.readiness_message(
                certificates[node.robot_id].readiness_state,
                certificates[node.robot_id].readiness_margin_meters,
                t,
            ),
        )
        for node in runtime.nodes
    }
    readiness_adjacency: Mapping[int, Iterable[int]] | Sequence[Mapping[int, Iterable[int]]]
    if graph_family == "temporary_disconnection":
        readiness_adjacency = temporary_disconnection_schedule(
            runtime.adjacency, config.derived.k_ready_rounds
        )
    else:
        readiness_adjacency = runtime.adjacency
    readiness_flood = flood_transition_messages(
        runtime.member_ids, readiness_messages, readiness_adjacency,
        config.derived.k_ready_rounds, ledger=runtime.ledger,
    )
    runtime.record_flood_timings(readiness_flood)
    t += config.derived.k_ready_rounds * period
    readiness_result = evaluate_readiness_agreement(
        readiness_flood, runtime.member_ids, intent, now_seconds=t,
        maximum_age_seconds=(
            config.derived.k_ready_rounds * period
            + config.communication.maximum_message_age_seconds
        ),
    )
    for node in runtime.nodes:
        node.accept_all_ready(readiness_result, t)
        trace[node.robot_id].append(node.state)
    if not readiness_result.agreed:
        reason = (
            "readiness_timeout:" + readiness_result.reason
            if graph_family == "temporary_disconnection"
            else readiness_result.reason
        )
        for node in runtime.nodes:
            node.abort(reason, t)
            trace[node.robot_id].append(node.state)
        return _failure_result(
            runtime, source_topology, target_topology, fixture, graph_family,
            trace, reason, 0.0, propagation=propagation_time,
            score=score_time, readiness=certificates,
            assumption_violation=(
                "temporary_disconnection_exceeded_round_contract"
                if graph_family == "temporary_disconnection" else None
            ),
        )
    all_ready_time = t
    # Recompute local readiness immediately before confirmation. A robot whose
    # local condition changed emits DISSENT; no stale SAFE is promoted.
    fresh_certificates = runtime.local_readiness_certificates(
        positions, velocities, source_topology, target_topology,
        intent.lifecycle_id, intent.epoch_id, t, goal_origin, direction,
    )
    confirmation_messages = {
        node.robot_id: (
            node.confirmation_message(
                "ACCEPT" if fresh_certificates[node.robot_id].readiness_state == "SAFE"
                else "DISSENT",
                t,
            ),
        )
        for node in runtime.nodes
    }
    confirmation_flood = flood_transition_messages(
        runtime.member_ids, confirmation_messages, runtime.adjacency,
        config.derived.k_confirm_rounds, ledger=runtime.ledger,
    )
    runtime.record_flood_timings(confirmation_flood)
    t += config.derived.k_confirm_rounds * period
    confirmation_result = evaluate_confirmation_agreement(
        confirmation_flood, runtime.member_ids, intent, now_seconds=t,
        maximum_age_seconds=(
            config.derived.k_confirm_rounds * period
            + config.communication.maximum_message_age_seconds
        ),
    )
    for node in runtime.nodes:
        node.accept_confirmation(confirmation_result, t)
    if not confirmation_result.agreed:
        for node in runtime.nodes:
            node.abort(confirmation_result.reason, t)
            trace[node.robot_id].append(node.state)
        return _failure_result(
            runtime, source_topology, target_topology, fixture, graph_family,
            trace, confirmation_result.reason, 0.0,
            propagation=propagation_time, score=score_time,
            readiness=certificates, all_ready=all_ready_time,
            confirmation=t,
        )
    confirmation_time = t
    commit_time = math.ceil(
        t / config.physical.control_period_seconds - 1e-12
    ) * config.physical.control_period_seconds
    commit_messages = []
    for node in runtime.nodes:
        commit_messages.append(node.commit(commit_time))
        trace[node.robot_id].append(node.state)
    committed_ids = {node.committed_topology for node in runtime.nodes}
    partial_commitment = (
        len(committed_ids) != 1
        or committed_ids != {target_topology}
        or len({node.mode_epoch_count for node in runtime.nodes}) != 1
    )
    for message in commit_messages:
        runtime.ledger.record("status", message.robot_id, message.payload_bytes())
    for node in runtime.nodes:
        node.begin_execution(commit_time)
        trace[node.robot_id].append(node.state)

    adapters = tuple(
        ForcedTopologyRuntimeAdapter(
            config, runtime.local_metadata[robot_id], target_topology
        )
        for robot_id in runtime.member_ids
    )
    motion_profile: Optional[TransitionMotionProfile] = None
    executors: Tuple[RobotLocalTransitionExecutor, ...] = ()
    if execution_strategy == "generic_role_space_profile":
        motion_profile = derive_transition_motion_profile(
            admissibility.maximum_displacement_meters, config
        )
        executors = tuple(
            RobotLocalTransitionExecutor(
                config,
                runtime.local_metadata[robot_id],
                prepare_robot_local_role_space_path(
                    runtime.role_set,
                    robot_id,
                    config.formation,
                    source_topology,
                    target_topology,
                ),
                motion_profile,
                commit_time,
            )
            for robot_id in runtime.member_ids
        )
    roles = RoleAssignment.from_index(
        team_size, config.formation.nominal_spacing_meters
    )
    duration_seconds = (
        motion_profile.duration_seconds
        if motion_profile is not None
        else 2.0 * admissibility.maximum_displacement_meters
        / config.physical.maximum_speed_meters_per_second
    ) + 4.0 * config.mission.recovery_dwell_seconds
    execution_steps = int(math.ceil(
        duration_seconds / config.physical.control_period_seconds
    ))
    metric_history: list[bool] = []
    target_tube_entry: Optional[int] = None
    dwell_completion: Optional[int] = None
    minimum_distance = _minimum_pair_distance(positions)
    collision_free = (
        minimum_distance > config.derived.robot_robot_required_clearance_meters
    )
    intervention_count = 0
    infeasible_count = 0
    solver_failure_count = 0
    controller_calls = 0
    controller_latencies: list[float] = []
    metric_latencies: list[float] = []
    completion_agreement_time: Optional[float] = None
    for step in range(execution_steps):
        timestamp = commit_time + step * config.physical.control_period_seconds
        transition_progress = (
            motion_profile.progress(timestamp - commit_time)
            if motion_profile is not None
            else 1.0
        )
        views = simulate_received_robot_views(
            positions, velocities, roles, target_topology,
            goal_origin, direction, config,
        )
        actions = []
        for robot_id, adapter in enumerate(adapters):
            started = time.perf_counter()
            if executors:
                controller_input = executors[robot_id].build_input(
                    views[robot_id], timestamp
                )
            else:
                controller_input = adapter.build_input(views[robot_id], timestamp)
            output = adapter.controller.evaluate(controller_input)
            controller_latencies.append(time.perf_counter() - started)
            if projection_observer is not None:
                projection_observer(LocalProjectionExecutionObservation(
                    execution_step=step,
                    transition_progress=transition_progress,
                    controller_input=controller_input,
                    controller_output=output,
                ))
            actions.append(output.projected_action)
            controller_calls += 1
            intervention_count += int(output.projection_intervened)
            infeasible_count += int(output.projection_infeasible)
            solver_failure_count += int(output.projection_solver_failed)
        if infeasible_count or solver_failure_count:
            now = commit_time + step * config.physical.control_period_seconds
            for node in runtime.nodes:
                node.abort("safety_projection_failure", now)
                trace[node.robot_id].append(node.state)
            break
        next_positions = np.zeros_like(positions)
        next_velocities = np.zeros_like(velocities)
        for robot_id, action in enumerate(actions):
            next_position, next_velocity = semi_implicit_acceleration_step(
                tuple(map(float, positions[robot_id])),
                tuple(map(float, velocities[robot_id])),
                action,
                config,
            )
            next_positions[robot_id] = next_position
            next_velocities[robot_id] = next_velocity
        positions, velocities = next_positions, next_velocities
        if not np.isfinite(positions).all() or not np.isfinite(velocities).all():
            for node in runtime.nodes:
                node.abort("numerical_failure", commit_time + (step + 1) * config.physical.control_period_seconds)
            break
        current_distance = _minimum_pair_distance(positions)
        minimum_distance = min(minimum_distance, current_distance)
        collision_free = collision_free and (
            current_distance > config.derived.robot_robot_required_clearance_meters
        )
        started = time.perf_counter()
        profile_complete = (
            motion_profile is None
            or motion_profile.progress(
                (step + 1) * config.physical.control_period_seconds
            ) >= 1.0
        )
        inside_metric = profile_complete and e_inf(
            positions, roles, target_topology, direction
        ) <= EPSILON_FORM
        metric_latencies.append(time.perf_counter() - started)
        metric_history.append(inside_metric)
        if inside_metric and target_tube_entry is None:
            target_tube_entry = step + 1
        now = commit_time + (step + 1) * config.physical.control_period_seconds
        for robot_id, node in enumerate(runtime.nodes):
            own_offset = rotate_template_vector(
                runtime.local_metadata[robot_id].candidate(target_topology).own_role_offset_meters,
                direction,
            )
            own_target = np.asarray(goal_origin) + np.asarray(own_offset)
            local_inside = (
                float(np.linalg.norm(positions[robot_id] - own_target)) <= EPSILON_FORM
            )
            previous_state = node.state
            completed = node.observe_target_tube(local_inside, now)
            if node.state != previous_state:
                trace[robot_id].append(node.state)
        dwell_steps = config.derived.recovery_dwell_steps
        if (
            len(metric_history) >= dwell_steps
            and all(metric_history[-dwell_steps:])
            and all(node.local_dwell_complete for node in runtime.nodes)
        ):
            dwell_completion = step + 1
            completion_messages = {
                node.robot_id: (
                    node.status_message("COMPLETE", "local_target_dwell", now),
                )
                for node in runtime.nodes
            }
            completion_flood = flood_transition_messages(
                runtime.member_ids, completion_messages, runtime.adjacency,
                config.derived.k_confirm_rounds, ledger=runtime.ledger,
            )
            runtime.record_flood_timings(completion_flood)
            completion_agreement_time = (
                now + config.derived.k_confirm_rounds
                * config.communication.communication_period_seconds
            )
            completion_agreement = evaluate_lifecycle_status_agreement(
                completion_flood, runtime.member_ids, intent, "COMPLETE",
                now_seconds=completion_agreement_time,
                maximum_age_seconds=(
                    config.derived.k_confirm_rounds
                    * config.communication.communication_period_seconds
                    + config.communication.maximum_message_age_seconds
                ),
            )
            if completion_agreement.agreed:
                for node in runtime.nodes:
                    node.mark_complete(completion_agreement_time)
                    trace[node.robot_id].append(node.state)
                break
            for node in runtime.nodes:
                node.abort(completion_agreement.reason, completion_agreement_time)
                trace[node.robot_id].append(node.state)
            break
    ledger_report = runtime.ledger.report()
    abort = None
    if not collision_free:
        abort = "collision"
    elif infeasible_count or solver_failure_count:
        abort = "safety_projection_failure"
    elif dwell_completion is None:
        abort = "transition_or_dwell_timeout"
    mode_counts = {node.mode_epoch_count for node in runtime.nodes}
    mode_epochs = next(iter(mode_counts)) if len(mode_counts) == 1 else -1
    completion_time = completion_agreement_time if dwell_completion is not None else None
    return Phase7TransitionEpisodeResult(
        PHASE7_RUNTIME_SCHEMA_VERSION,
        team_size, source_topology, target_topology, fixture, graph_family,
        communication_graph_diameter(runtime.member_ids, runtime.adjacency),
        config.derived.component_diameter_bound_hops,
        config.derived.k_intent_rounds, config.derived.k_score_rounds,
        config.derived.k_ready_rounds, config.derived.k_confirm_rounds,
        0.0, propagation_time, score_time,
        {cert.observer_robot_id: cert.readiness_state for cert in certificates},
        {cert.observer_robot_id: cert.readiness_margin_meters for cert in certificates},
        max(certificates, key=lambda cert: cert.observer_robot_id).observer_robot_id,
        all_ready_time, confirmation_time, commit_time,
        target_tube_entry, dwell_completion, collision_free,
        float(minimum_distance), None, intervention_count, infeasible_count,
        solver_failure_count, completion_time, abort, mode_epochs, 0, 0,
        int(ledger_report["total_bytes"]), ledger_report["bytes_by_phase"],
        int(ledger_report["retransmission_bytes"]), len(runtime.nodes),
        partial_commitment, (), 0, controller_calls,
        tuple(runtime.readiness_compute_seconds), tuple(controller_latencies),
        {robot_id: tuple(states) for robot_id, states in trace.items()},
        None,
        tuple(protocol_latencies[:1]),
        tuple(runtime.serialization_compute_seconds),
        tuple(runtime.ingestion_compute_seconds),
        tuple(runtime.readiness_compute_seconds),
        tuple(metric_latencies),
    )
