"""Snapshot/restore (RB-7), candidate clones (RB-8), candidate executor (RB-13)
and the Target V4 runtime evaluator (RB-14).

Snapshot design
---------------
Two artefacts, because they answer different questions:

* `canonical_execution_state(session)` enumerates every execution-relevant
  mutable field as plain JSON data. It is what gets hashed and compared, and
  its explicitness is what makes the snapshot *auditable* -- a reader can see
  which subsystems are covered.
* `EpisodeSnapshot` additionally carries a deep copy of the live session. That
  is what `restore()` returns, and it is what guarantees completeness: nothing
  can be forgotten, because the whole object graph is copied.

Relying on the canonical dict alone would risk a silently omitted field;
relying on the deep copy alone would make the coverage unauditable. Both are
kept, and `test_phase9c_state_snapshot_round_trip.py` checks they agree.

Isolation
---------
`copy.deepcopy` gives true mutation isolation between clones. The counter-keyed
streams are frozen dataclasses holding only `(seed, process)` -- there is no
mutable RNG object anywhere -- so two clones deriving from one snapshot draw
identical exogenous realizations without sharing state, and neither can advance
the other's stream.
"""

from __future__ import annotations

import copy
import hashlib
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from ..phase8.common import canonical_json_bytes
from ..phase8e.target import (
    TargetV4EvaluationResult, TargetV4ExecutionSummary, TargetV4PredicateValues,
    evaluate_target_v4,
)
from ..topology_registry import COMPACT, LINE

GENERATION_INVALID_CAUSES = frozenset({
    "INITIALIZATION_INVALID", "GEOMETRY_INVALID", "NUMERICAL_INVALID",
    "SCHEDULE_INVALID", "EXECUTOR_EXCEPTION",
})

# Kept separate on purpose: the frozen contract gives them the same disposition,
# but a solver defect must remain countable apart from genuine infeasibility.
SAFETY_CAUSES = ("SAFETY_INFEASIBLE", "SAFETY_SOLVER_FAILURE")


def canonical_sha256(document: object) -> str:
    return hashlib.sha256(canonical_json_bytes(document)).hexdigest()


def _vec(value: Sequence[float]) -> List[float]:
    return [float(value[0]), float(value[1])]


def canonical_execution_state(session) -> Dict[str, object]:
    """Every execution-relevant mutable field, as canonical JSON data."""
    robots: List[Dict[str, object]] = []
    for robot in session.robots:
        node = robot.protocol_node
        intent = node.active_intent
        robots.append({
            "robot_id": robot.robot_id,
            "role_id": robot.role_id,
            "position_meters": _vec(robot.position),
            "velocity_meters_per_second": _vec(robot.velocity),
            "acceleration_meters_per_second_squared": _vec(robot.acceleration),
            "committed_topology": int(robot.committed_topology),
            "compact_role_offset": _vec(robot.compact_offset),
            "line_role_offset": _vec(robot.line_offset),
            "transition_progress": float(robot.transition_progress),
            "steps_since_decision": int(robot.steps_since_decision),
            "local_progress": float(robot.local_progress),
            "safety_unresolved": bool(robot.safety_unresolved),
            "safety_infeasible_seen": bool(robot.safety_infeasible_seen),
            "safety_solver_failure_seen": bool(robot.safety_solver_failure_seen),
            "projection_intervened_count": int(robot.projection_intervened_count),
            "policy_state": {str(k): v for k, v in sorted(robot.policy_state.items())},
            "protocol": {
                "state": node.state,
                "committed_topology": int(node.committed_topology),
                "mode_epoch_count": int(node.mode_epoch_count),
                "duplicate_intent_count": int(node.duplicate_intent_count),
                "abort_cause": node.abort_cause,
                "state_entered_seconds": float(node.state_entered_seconds),
                "active_intent": None if intent is None else {
                    "lifecycle_id": int(intent.lifecycle_id),
                    "epoch_id": int(intent.epoch_id),
                    "originator_robot_id": int(intent.originator_robot_id),
                    "source_topology": int(intent.source_topology),
                    "candidate_topology": int(intent.candidate_topology),
                    "event_type": intent.event_type,
                    "event_timestamp": float(intent.event_timestamp),
                    "token_hash": intent.token_hash,
                },
            },
            "neighbour_table": {
                str(peer): {
                    "position": _vec(entry["position"]),
                    "velocity": _vec(entry["velocity"]),
                    "committed_topology": int(entry["committed_topology"]),
                    "epoch_id": int(entry["epoch_id"]),
                    "degree": int(entry["degree"]),
                    "timestamp": float(entry["timestamp"]),
                }
                for peer, entry in sorted(robot.neighbour_table.items())
            },
        })

    policy = session.source_policy
    policy_state: Dict[str, object] = {
        "policy_id": getattr(policy, "policy_id", "UNSPECIFIED"),
        "fired": {str(k): bool(v) for k, v in sorted(getattr(policy, "fired", {}).items())},
    }
    if hasattr(policy, "dispositions"):
        policy_state["dispositions"] = list(policy.dispositions)
    if hasattr(policy, "evidence_seconds"):
        policy_state["evidence_seconds"] = {
            str(k): float(v) for k, v in sorted(policy.evidence_seconds.items())}
    if hasattr(policy, "last_request_time"):
        policy_state["last_request_time"] = {
            str(k): float(v) for k, v in sorted(policy.last_request_time.items())}
    if hasattr(policy, "applied"):
        policy_state["s5_applied"] = bool(policy.applied)
    if hasattr(policy, "target_robot_id"):
        policy_state["s5_target_robot_id"] = int(policy.target_robot_id)
    if hasattr(policy, "evidence"):
        inner = policy.evidence
        policy_state["s4_evidence_seconds"] = {
            str(k): float(v) for k, v in sorted(inner.evidence_seconds.items())}
        policy_state["s4_last_request_time"] = {
            str(k): float(v) for k, v in sorted(inner.last_request_time.items())}

    termination = session.termination
    return {
        "schema_version": "rvt-phase9c-episode-snapshot/v1",
        "simulator": {
            "time_seconds": float(session.time_seconds),
            "control_step": int(session.control_step),
            "control_period_seconds": float(session.control_period),
            "horizon_seconds": float(session.horizon_seconds),
            "initial_topology": int(session.initial_topology),
            "termination": None if termination is None else {
                "cause": termination.cause,
                "control_step": int(termination.control_step),
                "time_seconds": float(termination.time_seconds),
                "detail": termination.detail,
            },
        },
        "robots": robots,
        "communication": session.channel.snapshot(),
        "dynamic_obstacles": list(session.dynamic_world.snapshot(session.time_seconds)),
        "disturbance": {
            "stream": (None if session.disturbance_stream is None
                       else list(session.disturbance_stream.identity())),
            "maximum_magnitude": float(session.disturbance_max_magnitude),
        },
        "seed_streams": {
            "initial_position": list(session.position_stream.identity()),
            "initial_velocity": list(session.velocity_stream.identity()),
            "s5_acceleration": list(session.s5_stream.identity()),
        },
        "mission_and_evaluator": {
            "max_longitudinal_progress": float(session.max_longitudinal_progress),
            "irreversible_loss_open": bool(session.irreversible_loss_open),
            "collision_detected": bool(session.collision_detected),
            "deadlock_detected": bool(session.deadlock_detected),
            "deadlock_window_start_progress": float(session.deadlock_window_start_progress),
            "deadlock_window_elapsed": float(session.deadlock_window_elapsed),
            "numerically_valid": bool(session.numerically_valid),
            "initialization_valid": bool(session.initialization_valid),
            "lifecycle_counter": int(session.lifecycle_counter),
            "metric_v3_dwell_seconds": {str(k): float(v)
                                        for k, v in sorted(session.metric_v3_dwell.items())},
        },
        "source_policy": policy_state,
        "event_log": list(session.event_log),
    }


def canonical_execution_hash(session) -> str:
    return canonical_sha256(canonical_execution_state(session))


@dataclass
class EpisodeSnapshot:
    """A complete, restorable episode state plus its auditable canonical form."""

    canonical_state: Dict[str, object]
    canonical_hash: str
    _session: Any

    def restore(self):
        """A fresh, fully independent session at the snapshot instant."""
        return copy.deepcopy(self._session)


def snapshot(session) -> EpisodeSnapshot:
    state = canonical_execution_state(session)
    return EpisodeSnapshot(canonical_state=state,
                           canonical_hash=canonical_sha256(state),
                           _session=copy.deepcopy(session))


def clone_pair(source: EpisodeSnapshot) -> Tuple[Any, Any]:
    """Two independent deep clones with byte-identical canonical hashes."""
    first, second = source.restore(), source.restore()
    if canonical_execution_hash(first) != canonical_execution_hash(second):
        raise ValueError("clone hashes diverge before candidate injection")
    return first, second


# ---------------------------------------------------------------------------
# RB-14 -- Target V4 runtime evaluator
# ---------------------------------------------------------------------------
def build_execution_summary(session, candidate_topology: int) -> TargetV4ExecutionSummary:
    """Map a finished session onto the frozen typed summary.

    Polarity is the point of this function: collision, deadlock, protocol abort,
    transition timeout, safety infeasibility, solver failure and irreversible
    progress loss are all *predicate failures* on a generation-valid record, so
    they become valid task-negatives. Only the frozen invalid-execution causes
    make a record generation-invalid.
    """
    termination = session.termination
    cause = termination.cause if termination is not None else "HORIZON_COMPLETE"

    initialization_valid = bool(session.initialization_valid
                                and cause != "INITIALIZATION_INVALID")
    geometry_valid = cause != "GEOMETRY_INVALID"
    schedule_conformant = cause != "SCHEDULE_INVALID"
    executor_completed = cause != "EXECUTOR_EXCEPTION"

    collision_free = not session.collision_detected and cause not in (
        "COLLISION", "WORLD_BOUNDARY_EXIT")
    no_deadlock = not session.deadlock_detected and cause != "PERSISTENT_DEADLOCK"

    states = [robot.protocol_node.state for robot in session.robots]
    committed = [int(robot.committed_topology) for robot in session.robots]
    success_states = set(session.target_contract["conditions"]["protocol_resolved"]
                         ["success_states"])
    candidate_equals_current = all(value == int(candidate_topology) for value in committed)

    partial_commitment = len(set(committed)) > 1
    protocol_resolved = (all(state in success_states for state in states)
                         and not partial_commitment
                         and cause not in ("PROTOCOL_ABORT", "PROTOCOL_TIMEOUT"))
    commitment_valid = candidate_equals_current and not partial_commitment
    transition_valid = (candidate_equals_current
                        and cause not in ("TRANSITION_ABORT", "TRANSITION_TIMEOUT"))

    dwell_required = float(session.target_contract["conditions"]
                           ["target_metric_v3_dwell_complete"]["duration_seconds"])
    dwell_complete = float(
        session.metric_v3_dwell.get(int(candidate_topology), 0.0)) >= dwell_required - 1e-9

    goal_complete = cause == "GOAL_COMPLETE"

    safety_resolved = not any(robot.safety_unresolved for robot in session.robots) and (
        cause not in SAFETY_CAUSES)
    no_irreversible_loss = not session.irreversible_loss_open and (
        cause != "IRREVERSIBLE_PROGRESS_LOSS")

    predicates = TargetV4PredicateValues(
        collision_free_complete_horizon=collision_free,
        no_persistent_deadlock=no_deadlock,
        candidate_commitment_valid=commitment_valid,
        transition_execution_valid=transition_valid,
        target_metric_v3_dwell_complete=dwell_complete,
        downstream_goal_complete=goal_complete,
        protocol_resolved=protocol_resolved,
        safety_projection_resolved=safety_resolved,
        numerically_valid=bool(session.numerically_valid) and cause != "NUMERICAL_INVALID",
        no_irreversible_progress_loss=no_irreversible_loss,
    )
    return TargetV4ExecutionSummary(
        termination_cause=cause, predicates=predicates,
        initialization_valid=initialization_valid, geometry_valid=geometry_valid,
        schedule_conformant=schedule_conformant, executor_completed=executor_completed)


@dataclass(frozen=True)
class CandidateReplicaResult:
    """One replica trace. Never merged away by the aggregate."""

    candidate_topology: int
    replica_index: int
    termination_cause: str
    disposition: str
    label: Optional[int]
    failed_predicates: Tuple[str, ...]
    control_steps: int
    safety_infeasible_robots: int
    safety_solver_failure_robots: int
    created_lifecycle: bool
    initial_clone_hash: str
    final_state_hash: str


@dataclass(frozen=True)
class CandidateResult:
    candidate_topology: int
    replicas: Tuple[CandidateReplicaResult, ...]

    @property
    def aggregate_label(self) -> Optional[int]:
        """Frozen `all_success` aggregation, applied only after every replica ran."""
        if any(r.disposition == "GENERATION_INVALID" for r in self.replicas):
            return None
        return 1 if all(r.label == 1 for r in self.replicas) else 0


def execute_candidate(source: EpisodeSnapshot, candidate_topology: int, *,
                      replica_index: int = 0,
                      disturbance_seed: Optional[int] = None,
                      max_steps: int = 4000) -> CandidateReplicaResult:
    """Run one candidate rollout from a decision-state snapshot.

    Case A -- candidate equals the committed topology: hold and continue. No
    request is issued, so no source-equals-target lifecycle can be created.

    Case B -- candidate differs: the request is injected through the actual
    Phase 7 protocol. Nothing here commits a topology centrally.
    """
    if candidate_topology not in (COMPACT, LINE):
        raise ValueError(f"candidate {candidate_topology} is not admitted")

    session = source.restore()
    initial_hash = canonical_execution_hash(session)

    if disturbance_seed is not None:
        from .streams import STREAM_ROBOT_ACCELERATION, CounterStream
        contract = dict(session.binding.disturbance_contract)
        magnitude = 0.05 * float(
            session.runtime_config.physical.maximum_acceleration_meters_per_second_squared)
        session.disturbance_stream = CounterStream(
            int(disturbance_seed), f"{STREAM_ROBOT_ACCELERATION}:replica-{replica_index}")
        session.disturbance_max_magnitude = magnitude

    # The source policy must not keep originating during a counterfactual.
    from .policies import SourcePolicy
    session.source_policy = SourcePolicy({}, 0, session.horizon_seconds, session.team_size)

    lifecycles_before = len(session.event_log)
    created_lifecycle = False
    origin_robot = session.robots[0]
    if int(candidate_topology) != int(origin_robot.committed_topology):
        created_lifecycle = session.request_candidate(
            origin_robot, int(candidate_topology), "externally_forced_diagnostic")

    steps = 0
    while session.termination is None and steps < max_steps:
        session.step()
        steps += 1

    summary = build_execution_summary(session, candidate_topology)
    result = evaluate_target_v4(summary)
    return CandidateReplicaResult(
        candidate_topology=int(candidate_topology),
        replica_index=int(replica_index),
        termination_cause=result.termination_cause,
        disposition=result.disposition,
        label=result.label,
        failed_predicates=tuple(result.failed_predicates),
        control_steps=int(session.control_step),
        safety_infeasible_robots=sum(1 for r in session.robots if r.safety_infeasible_seen),
        safety_solver_failure_robots=sum(
            1 for r in session.robots if r.safety_solver_failure_seen),
        created_lifecycle=bool(created_lifecycle)
        or len(session.event_log) > lifecycles_before,
        initial_clone_hash=initial_hash,
        final_state_hash=canonical_execution_hash(session),
    )


def replica_count_for_family(family_id: str) -> int:
    """Frozen: three matched replicas for F8 and F9, one elsewhere."""
    return 3 if family_id in ("F8", "F9") else 1


def execute_candidate_pair(source: EpisodeSnapshot, family_id: str, *,
                           matched_disturbance_seed: Optional[int] = None,
                           max_steps: int = 4000) -> Dict[int, CandidateResult]:
    """Both admitted candidates from one snapshot, with matched replica counts."""
    replicas = replica_count_for_family(family_id)
    results: Dict[int, CandidateResult] = {}
    for candidate in (COMPACT, LINE):
        traces = tuple(
            execute_candidate(source, candidate, replica_index=index,
                              disturbance_seed=matched_disturbance_seed,
                              max_steps=max_steps)
            for index in range(replicas))
        results[candidate] = CandidateResult(candidate_topology=candidate, replicas=traces)
    return results
