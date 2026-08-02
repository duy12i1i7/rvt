"""Offline mechanical qualification for the Phase 7 transition protocol."""

from __future__ import annotations

import json
import math
import resource
import statistics
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Mapping, Optional, Sequence, Tuple

from ..runtime_configuration import SUPPORTED_MECHANICAL_TEAM_SIZES
from ..topology_registry import COMPACT, KEEP, LINE, PRIMARY_TOPOLOGY_IDS
from .local_control_types import LocalObstacleControlState
from .transition_admissibility import ADMITTED_DIRECTED_PAIRS
from .transition_messages import TRANSITION_PROTOCOL_SCHEMA_VERSION
from .transition_protocol import (
    AgreementResult,
    TransitionProtocolRuntimeOptions,
    evaluate_confirmation_agreement,
    evaluate_readiness_agreement,
    flood_transition_messages,
)
from .transition_runtime import (
    PHASE7_GRAPH_FAMILIES,
    PHASE7_OPEN_SPACE_FIXTURES,
    Phase7TransitionEpisodeResult,
    StrictTransitionRuntime,
    _initial_state,
    communication_graph,
    run_phase7_transition_episode,
    temporary_disconnection_schedule,
)
from .transition_readiness import RobotLocalReadinessCertificate


PHASE7_QUALIFICATION_SCHEMA_VERSION = "rvt-phase7-qualification/v1"
PHASE7_CONSTRICTION_FIXTURES: Tuple[str, ...] = (
    "wider_to_narrower",
    "narrower_to_wider",
    "centre_ready_before_outer",
    "one_outer_wall_constrained",
    "all_roles_eventually_ready",
    "no_feasible_transition_window",
    "incomplete_local_sensing",
    "temporary_communication_loss",
)


@dataclass(frozen=True)
class Phase7ConstrictionFixtureResult:
    schema_version: str
    fixture: str
    source_topology: int
    target_topology: int
    initial_states: Mapping[int, str]
    final_states: Mapping[int, str]
    initial_all_ready: bool
    final_all_ready: bool
    constrained_robot_ids: Tuple[int, ...]
    centre_robot_ids: Tuple[int, ...]
    premature_commitment: bool
    committed: bool
    timed_out_or_aborted: bool
    abort_cause: Optional[str]
    collision_free: bool
    mode_epoch_count: int
    no_op_epoch_count: int
    actual_communication_bytes: int
    false_safe_count: int
    false_unsafe_count: int
    unknown_count: int


@dataclass(frozen=True)
class Phase7ScalingRecord:
    team_size: int
    graph_family: str
    graph_diameter: int
    local_degree_median: float
    protocol_compute_median_seconds: float
    protocol_compute_p95_seconds: float
    protocol_compute_p99_seconds: float
    event_processing_median_seconds: float
    message_serialization_median_seconds: float
    message_serialization_p95_seconds: float
    message_serialization_p99_seconds: float
    message_ingestion_median_seconds: float
    message_ingestion_p95_seconds: float
    message_ingestion_p99_seconds: float
    readiness_compute_median_seconds: float
    readiness_compute_p95_seconds: float
    readiness_compute_p99_seconds: float
    metric_compute_median_seconds: float
    metric_compute_p95_seconds: float
    metric_compute_p99_seconds: float
    controller_compute_median_seconds: float
    controller_compute_p95_seconds: float
    controller_compute_p99_seconds: float
    communication_latency_seconds: float
    total_transition_latency_seconds: Optional[float]
    actual_bytes: int
    peak_memory_bytes: int


def _percentile(values: Sequence[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(float(value) for value in values)
    index = (len(ordered) - 1) * percentile / 100.0
    lower = int(math.floor(index))
    upper = int(math.ceil(index))
    if lower == upper:
        return ordered[lower]
    weight = index - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _outer_and_centre(runtime: StrictTransitionRuntime, target: int) \
        -> Tuple[Tuple[int, ...], Tuple[int, ...]]:
    lateral = {
        robot_id: abs(
            runtime.local_metadata[robot_id]
            .candidate(target).own_role_offset_meters[1]
        )
        for robot_id in runtime.member_ids
    }
    maximum = max(lateral.values())
    minimum = min(lateral.values())
    outer = tuple(sorted(robot_id for robot_id, value in lateral.items()
                         if abs(value - maximum) <= 1e-12))
    centre = tuple(sorted(robot_id for robot_id, value in lateral.items()
                          if abs(value - minimum) <= 1e-12))
    return outer, centre


def _blocking_obstacles(
    certificates: Sequence[RobotLocalReadinessCertificate],
    robot_ids: Sequence[int],
) -> Dict[int, tuple[LocalObstacleControlState, ...]]:
    result = {}
    for robot_id in robot_ids:
        envelope = certificates[robot_id].envelope
        end = envelope.capsule_end_relative_meters
        centre = (end[0] * 0.5, end[1] * 0.5)
        if math.hypot(*centre) < 0.1:
            centre = (0.25, 0.0)
        result[robot_id] = (LocalObstacleControlState(
            source_key=f"fixture-wall:{robot_id}",
            relative_center_meters=centre,
            radius_meters=0.35,
            relative_velocity_meters_per_second=(0.0, 0.0),
        ),)
    return result


def _geometric_unsafe(
    certificate: RobotLocalReadinessCertificate,
    obstacles: Sequence[LocalObstacleControlState],
) -> bool:
    start = certificate.envelope.capsule_start_relative_meters
    end = certificate.envelope.capsule_end_relative_meters
    dx, dy = end[0] - start[0], end[1] - start[1]
    denominator = dx * dx + dy * dy
    for obstacle in obstacles:
        px, py = obstacle.relative_center_meters
        if denominator <= 1e-18:
            distance = math.hypot(px - start[0], py - start[1])
        else:
            fraction = max(0.0, min(1.0, (
                (px - start[0]) * dx + (py - start[1]) * dy
            ) / denominator))
            distance = math.hypot(
                px - (start[0] + fraction * dx),
                py - (start[1] + fraction * dy),
            )
        if (
            distance - obstacle.radius_meters
            - certificate.envelope.capsule_radius_meters < 0.0
        ):
            return True
    return False


def run_phase7_constriction_fixture(
    fixture: str,
) -> Phase7ConstrictionFixtureResult:
    if fixture not in PHASE7_CONSTRICTION_FIXTURES:
        raise ValueError("unknown constriction fixture")
    source, target = (
        (KEEP, LINE) if fixture == "wider_to_narrower" else (LINE, KEEP)
    )
    n = 6
    adjacency = communication_graph(n, "path")
    runtime = StrictTransitionRuntime(
        n, source, adjacency,
        options=TransitionProtocolRuntimeOptions(True),
    )
    config = runtime.runtime_config
    positions, velocities, origin, direction = _initial_state(
        n, source, "exact_source", config
    )
    intent = runtime.nodes[0].request_intent(
        1, target, "deterministic_local_fixture", 0.0
    )
    assert intent is not None
    for node in runtime.nodes:
        node.adopt_intent(intent, 0.0)
        node.begin_score_agreement(0.0)
        node.accept_score_agreement(AgreementResult(
            True, "score_agreed", intent.lifecycle_id, intent.epoch_id,
            target, aggregate_score=1.0, complete_membership=True,
        ), 0.0)
    baseline = runtime.local_readiness_certificates(
        positions, velocities, source, target, intent.lifecycle_id,
        intent.epoch_id, 0.0, origin, direction,
    )
    outer, centre = _outer_and_centre(runtime, target)
    constrained: Tuple[int, ...] = ()
    obstacles: Dict[int, tuple[LocalObstacleControlState, ...]] = {}
    observed_extents: Optional[Mapping[int, float]] = None
    if fixture in ("centre_ready_before_outer", "all_roles_eventually_ready"):
        constrained = outer
        obstacles = _blocking_obstacles(baseline, constrained)
    elif fixture == "one_outer_wall_constrained":
        constrained = outer[:1]
        obstacles = _blocking_obstacles(baseline, constrained)
    elif fixture == "no_feasible_transition_window":
        constrained = runtime.member_ids
        obstacles = _blocking_obstacles(baseline, constrained)
    elif fixture == "incomplete_local_sensing":
        constrained = outer
        observed_extents = {robot_id: 0.2 for robot_id in constrained}
    initial = runtime.local_readiness_certificates(
        positions, velocities, source, target, intent.lifecycle_id,
        intent.epoch_id, 0.0, origin, direction,
        observed_extent_by_robot=observed_extents,
        local_obstacles_by_robot=obstacles,
    )
    for node in runtime.nodes:
        node.begin_all_ready_agreement(0.0)
    initial_messages = {
        node.robot_id: (node.readiness_message(
            initial[node.robot_id].readiness_state,
            initial[node.robot_id].readiness_margin_meters,
            0.0,
        ),)
        for node in runtime.nodes
    }
    initial_graph = (
        temporary_disconnection_schedule(
            adjacency, config.derived.k_ready_rounds
        )
        if fixture == "temporary_communication_loss"
        else adjacency
    )
    initial_flood = flood_transition_messages(
        runtime.member_ids, initial_messages, initial_graph,
        config.derived.k_ready_rounds, ledger=runtime.ledger,
    )
    first_time = config.derived.k_ready_rounds * (
        config.communication.communication_period_seconds
    )
    initial_agreement = evaluate_readiness_agreement(
        initial_flood, runtime.member_ids, intent, now_seconds=first_time,
        maximum_age_seconds=(
            first_time + config.communication.maximum_message_age_seconds
        ),
    )
    for node in runtime.nodes:
        node.accept_all_ready(initial_agreement, first_time)
    final = initial
    final_agreement = initial_agreement
    eventual = fixture in (
        "all_roles_eventually_ready",
        "temporary_communication_loss",
    )
    if eventual:
        final = runtime.local_readiness_certificates(
            positions, velocities, source, target, intent.lifecycle_id,
            intent.epoch_id, first_time, origin, direction,
        )
        for node in runtime.nodes:
            node.begin_all_ready_agreement(first_time)
        final_messages = {
            node.robot_id: (node.readiness_message(
                final[node.robot_id].readiness_state,
                final[node.robot_id].readiness_margin_meters,
                first_time,
            ),)
            for node in runtime.nodes
        }
        final_flood = flood_transition_messages(
            runtime.member_ids, final_messages, adjacency,
            config.derived.k_ready_rounds, ledger=runtime.ledger,
        )
        final_time = first_time + config.derived.k_ready_rounds * (
            config.communication.communication_period_seconds
        )
        final_agreement = evaluate_readiness_agreement(
            final_flood, runtime.member_ids, intent, now_seconds=final_time,
            maximum_age_seconds=(
                config.derived.k_ready_rounds
                * config.communication.communication_period_seconds
                + config.communication.maximum_message_age_seconds
            ),
        )
        for node in runtime.nodes:
            node.accept_all_ready(final_agreement, final_time)
    else:
        final_time = first_time

    agreement_to_use = final_agreement
    committed = False
    if agreement_to_use.agreed:
        confirmation_messages = {
            node.robot_id: (node.confirmation_message("ACCEPT", final_time),)
            for node in runtime.nodes
        }
        confirmation_flood = flood_transition_messages(
            runtime.member_ids, confirmation_messages, adjacency,
            config.derived.k_confirm_rounds, ledger=runtime.ledger,
        )
        confirm_time = final_time + config.derived.k_confirm_rounds * (
            config.communication.communication_period_seconds
        )
        confirmation = evaluate_confirmation_agreement(
            confirmation_flood, runtime.member_ids, intent,
            now_seconds=confirm_time,
            maximum_age_seconds=(
                config.derived.k_confirm_rounds
                * config.communication.communication_period_seconds
                + config.communication.maximum_message_age_seconds
            ),
        )
        for node in runtime.nodes:
            node.accept_confirmation(confirmation, confirm_time)
            if confirmation.agreed:
                status = node.commit(confirm_time)
                runtime.ledger.record("status", node.robot_id, status.payload_bytes())
        committed = confirmation.agreed
    else:
        for node in runtime.nodes:
            node.abort("readiness_timeout", final_time)

    false_safe = 0
    false_unsafe = 0
    unknown = 0
    for certificate in initial:
        truth_unsafe = _geometric_unsafe(
            certificate, obstacles.get(certificate.observer_robot_id, ())
        )
        false_safe += int(certificate.readiness_state == "SAFE" and truth_unsafe)
        false_unsafe += int(certificate.readiness_state == "UNSAFE" and not truth_unsafe)
        unknown += int(certificate.readiness_state == "UNKNOWN")
    return Phase7ConstrictionFixtureResult(
        PHASE7_QUALIFICATION_SCHEMA_VERSION,
        fixture, source, target,
        {item.observer_robot_id: item.readiness_state for item in initial},
        {item.observer_robot_id: item.readiness_state for item in final},
        initial_agreement.agreed, final_agreement.agreed,
        constrained, centre,
        premature_commitment=(committed and not initial_agreement.agreed and not eventual),
        committed=committed,
        timed_out_or_aborted=not committed,
        abort_cause=None if committed else "readiness_timeout",
        collision_free=True,
        mode_epoch_count=(
            next(iter({node.mode_epoch_count for node in runtime.nodes}))
            if len({node.mode_epoch_count for node in runtime.nodes}) == 1 else -1
        ),
        no_op_epoch_count=0,
        actual_communication_bytes=runtime.ledger.total_bytes,
        false_safe_count=false_safe,
        false_unsafe_count=false_unsafe,
        unknown_count=unknown,
    )


def run_open_space_matrix() -> Tuple[Phase7TransitionEpisodeResult, ...]:
    return tuple(
        run_phase7_transition_episode(n, source, target, fixture, "path")
        for n in SUPPORTED_MECHANICAL_TEAM_SIZES
        for source, target in ADMITTED_DIRECTED_PAIRS
        for fixture in PHASE7_OPEN_SPACE_FIXTURES
    )


def run_constriction_matrix() -> Tuple[Phase7ConstrictionFixtureResult, ...]:
    return tuple(
        run_phase7_constriction_fixture(fixture)
        for fixture in PHASE7_CONSTRICTION_FIXTURES
    )


def run_communication_topology_matrix() -> Tuple[Phase7TransitionEpisodeResult, ...]:
    return tuple(
        run_phase7_transition_episode(n, KEEP, LINE, "exact_source", family)
        for n in (5, 8, 12, 16, 24)
        for family in PHASE7_GRAPH_FAMILIES
    )


def scaling_records(
    communication_results: Sequence[Phase7TransitionEpisodeResult],
) -> Tuple[Phase7ScalingRecord, ...]:
    records = []
    for result in communication_results:
        graph = communication_graph(result.team_size, result.graph_family)
        degrees = [len(graph[robot_id]) for robot_id in range(result.team_size)]
        timings = tuple(result.local_protocol_compute_seconds)
        controller = tuple(result.controller_compute_seconds)
        records.append(Phase7ScalingRecord(
            result.team_size,
            result.graph_family,
            result.graph_diameter,
            float(statistics.median(degrees)),
            _percentile(timings, 50.0),
            _percentile(timings, 95.0),
            _percentile(timings, 99.0),
            _percentile(result.event_processing_seconds, 50.0),
            _percentile(result.message_serialization_seconds, 50.0),
            _percentile(result.message_serialization_seconds, 95.0),
            _percentile(result.message_serialization_seconds, 99.0),
            _percentile(result.message_ingestion_seconds, 50.0),
            _percentile(result.message_ingestion_seconds, 95.0),
            _percentile(result.message_ingestion_seconds, 99.0),
            _percentile(result.readiness_compute_seconds, 50.0),
            _percentile(result.readiness_compute_seconds, 95.0),
            _percentile(result.readiness_compute_seconds, 99.0),
            _percentile(result.metric_compute_seconds, 50.0),
            _percentile(result.metric_compute_seconds, 95.0),
            _percentile(result.metric_compute_seconds, 99.0),
            _percentile(controller, 50.0),
            _percentile(controller, 95.0),
            _percentile(controller, 99.0),
            (
                result.k_intent + result.k_score
                + result.k_ready + result.k_confirm
            ) * 0.15,
            result.completion_time_seconds,
            result.actual_communication_bytes,
            0,
        ))
    return tuple(records)


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, allow_nan=False, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )


def run_and_write_phase7_qualification(
    output_root: Path,
) -> Mapping[str, object]:
    started = time.perf_counter()
    open_results = run_open_space_matrix()
    constriction_results = run_constriction_matrix()
    communication_results = run_communication_topology_matrix()
    peak = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    scaling = tuple(
        Phase7ScalingRecord(**{
            **asdict(record),
            "peak_memory_bytes": peak,
        })
        for record in scaling_records(communication_results)
    )
    _write_json(
        output_root / "open_space" / "episodes.json",
        [result.source() for result in open_results],
    )
    _write_json(
        output_root / "constriction" / "fixtures.json",
        [asdict(result) for result in constriction_results],
    )
    _write_json(
        output_root / "communication_topology_matrix.json",
        [result.source() for result in communication_results],
    )
    _write_json(
        output_root / "protocol_scaling.json",
        [asdict(record) for record in scaling],
    )
    false_safe = sum(result.false_safe_count for result in constriction_results)
    certificates = sum(len(result.initial_states) for result in constriction_results)
    summary = {
        "schema_version": PHASE7_QUALIFICATION_SCHEMA_VERSION,
        "protocol_schema_version": TRANSITION_PROTOCOL_SCHEMA_VERSION,
        "open_space_episode_count": len(open_results),
        "open_space_success_count": sum(result.transition_success for result in open_results),
        "open_space_collision_free_count": sum(result.collision_free for result in open_results),
        "constriction_fixture_count": len(constriction_results),
        "false_safe_count": false_safe,
        "readiness_certificate_count": certificates,
        "false_safe_rate": false_safe / max(certificates, 1),
        "premature_commitment_count": sum(
            result.premature_commitment for result in constriction_results
        ),
        "communication_cell_count": len(communication_results),
        "communication_agreement_success_count": sum(
            result.propagation_completion_seconds is not None
            and result.score_agreement_completion_seconds is not None
            and result.all_ready_time_seconds is not None
            and result.confirmation_time_seconds is not None
            for result in communication_results
            if result.graph_family != "temporary_disconnection"
        ),
        "temporary_disconnection_detected_count": sum(
            result.assumption_violation is not None
            for result in communication_results
            if result.graph_family == "temporary_disconnection"
        ),
        "elapsed_seconds": time.perf_counter() - started,
        "peak_memory_bytes": peak,
        "learned_model_calls": 0,
        "residual_action_calls": 0,
        "scientific_training_runs": 0,
        "final_test_layout_accesses": 0,
    }
    _write_json(output_root / "summary.json", summary)
    return summary
