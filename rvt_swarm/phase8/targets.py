"""Task-recoverability and robot-local residual-action target contracts."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Dict, Iterable, Optional, Sequence, Tuple

from ..decentralized.ego_graph_v2 import EGO_GRAPH_SCHEMA_VERSION
from ..fd24.configuration import FD24ModelConfig, residual_action_limits
from ..runtime_configuration import RuntimeConfig
from ..topology_registry import COMPACT, LINE
from .common import sha256_document


RECOVERABILITY_TARGET_SCHEMA_VERSION = "rvt-task-recoverability-target/v4"
COUNTERFACTUAL_ROLLOUT_SCHEMA_VERSION = "rvt-counterfactual-rollout/v1"
LOCAL_VIEW_LABEL_SCHEMA_VERSION = "rvt-local-view-task-label/v1"
RESIDUAL_ACTION_TARGET_SCHEMA_VERSION = "rvt-residual-action-target/v1"
DENSE_ACTION_SAMPLE_SCHEMA_VERSION = "rvt-dense-action-sample/v1"
RESIDUAL_EXPERT_ID = "B_FROZEN_COUNTERFACTUAL_LOCAL_ACTION_SEARCH_V1"
PRIMARY_CANDIDATES: Tuple[int, ...] = (COMPACT, LINE)
STOCHASTIC_ROLLOUT_REPLICAS = 3
DETERMINISTIC_ROLLOUT_REPLICAS = 1
ROLLOUT_AGGREGATION = "all_success"


@dataclass(frozen=True)
class TaskRecoveryConditions:
    collision_free_complete_horizon: bool
    no_persistent_deadlock: bool
    candidate_commitment_valid: bool
    transition_execution_valid: bool
    target_metric_v3_dwell_complete: bool
    downstream_goal_complete: bool
    protocol_resolved: bool
    safety_projection_resolved: bool
    numerically_valid: bool
    no_irreversible_progress_loss: bool

    def succeeded(self) -> bool:
        return all(asdict(self).values())


@dataclass(frozen=True)
class CounterfactualRolloutTrace:
    schema_version: str
    episode_id: str
    decision_event_id: str
    candidate_topology: int
    replica_index: int
    initial_state_sha256: str
    source_lifecycle_sha256: str
    disturbance_seed: int
    communication_condition_sha256: str
    rollout_configuration_sha256: str
    horizon_seconds: float
    conditions: TaskRecoveryConditions
    abort_reason: Optional[str]
    rollout_cost_steps: int

    def __post_init__(self) -> None:
        if self.schema_version != COUNTERFACTUAL_ROLLOUT_SCHEMA_VERSION:
            raise ValueError("unknown counterfactual rollout schema")
        if self.candidate_topology not in PRIMARY_CANDIDATES:
            raise ValueError("rollout candidate must be COMPACT or LINE")
        if self.replica_index < 0 or self.rollout_cost_steps <= 0:
            raise ValueError("rollout replica and cost are invalid")
        if not math.isfinite(self.horizon_seconds) or self.horizon_seconds <= 0.0:
            raise ValueError("rollout horizon must be finite and positive")


@dataclass(frozen=True)
class CandidateRecoverabilityTarget:
    schema_version: str
    decision_event_id: str
    candidate_topology: int
    label: int
    aggregation: str
    replica_count: int
    unstable: bool
    invalid: bool
    failure_reasons: Tuple[str, ...]
    average_rollout_cost_steps: float


@dataclass(frozen=True)
class MatchedCounterfactualPair:
    decision_event_id: str
    compact_traces: Tuple[CounterfactualRolloutTrace, ...]
    line_traces: Tuple[CounterfactualRolloutTrace, ...]


def _matching_key(trace: CounterfactualRolloutTrace) -> Tuple[object, ...]:
    return (
        trace.episode_id,
        trace.decision_event_id,
        trace.replica_index,
        trace.initial_state_sha256,
        trace.source_lifecycle_sha256,
        trace.disturbance_seed,
        trace.communication_condition_sha256,
        trace.rollout_configuration_sha256,
        trace.horizon_seconds,
    )


def verify_matched_counterfactual_pair(
    pair: MatchedCounterfactualPair,
) -> Tuple[str, ...]:
    issues = []
    compact = tuple(sorted(pair.compact_traces, key=lambda item: item.replica_index))
    line = tuple(sorted(pair.line_traces, key=lambda item: item.replica_index))
    if not compact or len(compact) != len(line):
        issues.append("candidate_rollout_budget_mismatch")
        return tuple(issues)
    if any(item.candidate_topology != COMPACT for item in compact):
        issues.append("compact_trace_has_wrong_candidate")
    if any(item.candidate_topology != LINE for item in line):
        issues.append("line_trace_has_wrong_candidate")
    for compact_trace, line_trace in zip(compact, line):
        if _matching_key(compact_trace) != _matching_key(line_trace):
            issues.append(f"unmatched_replica:{compact_trace.replica_index}")
    return tuple(sorted(set(issues)))


def evaluate_candidate_recoverability(
    traces: Sequence[CounterfactualRolloutTrace],
) -> CandidateRecoverabilityTarget:
    items = tuple(traces)
    if not items:
        raise ValueError("candidate target requires at least one rollout")
    candidate = items[0].candidate_topology
    decision_event_id = items[0].decision_event_id
    if any(
        item.candidate_topology != candidate
        or item.decision_event_id != decision_event_id
        for item in items
    ):
        raise ValueError("candidate target traces have mixed identity")
    expected_replicas = (
        STOCHASTIC_ROLLOUT_REPLICAS
        if len(items) > DETERMINISTIC_ROLLOUT_REPLICAS
        else DETERMINISTIC_ROLLOUT_REPLICAS
    )
    if len(items) != expected_replicas:
        raise ValueError("rollout replica count violates the frozen aggregation contract")
    valid = tuple(item.conditions.numerically_valid for item in items)
    outcomes = tuple(item.conditions.succeeded() for item in items)
    invalid = not all(valid)
    label = int(not invalid and all(outcomes))
    reasons = tuple(sorted(set(
        item.abort_reason
        for item in items
        if item.abort_reason is not None
    )))
    return CandidateRecoverabilityTarget(
        RECOVERABILITY_TARGET_SCHEMA_VERSION,
        decision_event_id,
        candidate,
        label,
        ROLLOUT_AGGREGATION,
        len(items),
        len(set(outcomes)) > 1,
        invalid,
        reasons,
        sum(item.rollout_cost_steps for item in items) / len(items),
    )


def joint_outcome_category(
    compact_target: CandidateRecoverabilityTarget,
    line_target: CandidateRecoverabilityTarget,
) -> str:
    if compact_target.decision_event_id != line_target.decision_event_id:
        raise ValueError("joint outcome requires one decision event")
    if compact_target.candidate_topology != COMPACT or line_target.candidate_topology != LINE:
        raise ValueError("joint outcome requires ordered COMPACT and LINE targets")
    outcomes = (compact_target.label, line_target.label)
    return {
        (1, 0): "COMPACT_ONLY_SUCCESS",
        (0, 1): "LINE_ONLY_SUCCESS",
        (1, 1): "BOTH_SUCCESS",
        (0, 0): "BOTH_FAIL",
    }[outcomes]


@dataclass(frozen=True)
class LocalViewRecoverabilitySample:
    schema_version: str
    episode_id: str
    decision_event_id: str
    robot_id: int
    candidate_topology: int
    ego_graph_schema_version: str
    feature_sha256: str
    source_topology: int
    team_size: int
    scenario_family: str
    layout_sha256: str
    split: str
    rollout_configuration_sha256: str
    label: int
    joint_outcome_category: str
    sample_timestamp_seconds: float
    message_condition: str
    source_commit: str

    def __post_init__(self) -> None:
        if self.schema_version != LOCAL_VIEW_LABEL_SCHEMA_VERSION:
            raise ValueError("unknown local-view label schema")
        if self.ego_graph_schema_version != EGO_GRAPH_SCHEMA_VERSION:
            raise ValueError("local-view label has wrong ego-graph schema")
        if self.candidate_topology not in PRIMARY_CANDIDATES:
            raise ValueError("KEEP cannot enter primary recoverability samples")
        if self.label not in (0, 1):
            raise ValueError("recoverability label must be binary")
        if not math.isfinite(self.sample_timestamp_seconds):
            raise ValueError("sample timestamp must be finite")


def validate_local_view_grouping(
    samples: Iterable[LocalViewRecoverabilitySample],
) -> Tuple[str, ...]:
    split_by_event: Dict[str, str] = {}
    label_by_event_candidate: Dict[Tuple[str, int], int] = {}
    issues = []
    for sample in samples:
        prior_split = split_by_event.setdefault(sample.decision_event_id, sample.split)
        if prior_split != sample.split:
            issues.append(f"event_split_leak:{sample.decision_event_id}")
        key = (sample.decision_event_id, sample.candidate_topology)
        prior_label = label_by_event_candidate.setdefault(key, sample.label)
        if prior_label != sample.label:
            issues.append(f"shared_label_conflict:{sample.decision_event_id}")
    return tuple(sorted(set(issues)))


@dataclass(frozen=True)
class LocalActionEvaluation:
    action_world_acceleration: Tuple[float, float]
    locally_feasible: bool
    safety_projection_compatible: bool
    robot_local_information_only: bool
    normalized_progress: float
    normalized_clearance_margin: float
    normalized_formation_error: float
    normalized_action_deviation: float

    def utility(self) -> float:
        return (
            self.normalized_progress
            + 0.50 * self.normalized_clearance_margin
            - 0.25 * self.normalized_formation_error
            - 0.05 * self.normalized_action_deviation
        )


@dataclass(frozen=True)
class ResidualActionTarget:
    schema_version: str
    expert_source: str
    base_action_world_acceleration: Tuple[float, float]
    expert_action_world_acceleration: Tuple[float, float]
    residual_target_world_acceleration: Tuple[float, float]
    residual_bounds_world_acceleration: Tuple[float, float]
    finite: bool
    nonzero: bool
    saturated: bool
    safety_projection_compatible: bool


@dataclass(frozen=True)
class DenseActionSample:
    schema_version: str
    ego_graph_schema_version: str
    feature_sha256: str
    candidate_or_committed_topology: int
    base_action_world_acceleration: Tuple[float, float]
    expert_action_world_acceleration: Tuple[float, float]
    residual_target_world_acceleration: Tuple[float, float]
    projected_base_action_world_acceleration: Tuple[float, float]
    safety_projection_metadata: Tuple[Tuple[str, str], ...]
    robot_role_id: str
    team_size: int
    scenario_family: str
    layout_sha256: str
    split: str
    episode_id: str
    timestep: int
    source_commit: str
    configuration_sha256: Tuple[Tuple[str, str], ...]

    def __post_init__(self) -> None:
        if self.schema_version != DENSE_ACTION_SAMPLE_SCHEMA_VERSION:
            raise ValueError("unknown dense-action sample schema")
        if self.ego_graph_schema_version != EGO_GRAPH_SCHEMA_VERSION:
            raise ValueError("dense-action sample has wrong ego-graph schema")
        if self.candidate_or_committed_topology not in PRIMARY_CANDIDATES:
            raise ValueError("primary dense-action topology must be COMPACT or LINE")
        for name, value in (
            ("base action", self.base_action_world_acceleration),
            ("expert action", self.expert_action_world_acceleration),
            ("residual target", self.residual_target_world_acceleration),
            ("projected base action", self.projected_base_action_world_acceleration),
        ):
            _finite_vec2(value, name)
        if self.team_size <= 0 or self.timestep < 0:
            raise ValueError("dense-action sample indices are invalid")
        if not self.robot_role_id or not self.episode_id or not self.configuration_sha256:
            raise ValueError("dense-action sample provenance is incomplete")


def _finite_vec2(value: Sequence[float], name: str) -> Tuple[float, float]:
    if len(value) != 2:
        raise ValueError(f"{name} must have two world-frame acceleration components")
    result = (float(value[0]), float(value[1]))
    if not all(math.isfinite(item) for item in result):
        raise ValueError(f"{name} must be finite")
    return result


def select_counterfactual_local_action(
    base_action: Sequence[float],
    evaluations: Sequence[LocalActionEvaluation],
    runtime_config: RuntimeConfig,
    model_config: FD24ModelConfig,
) -> LocalActionEvaluation:
    base = _finite_vec2(base_action, "base action")
    limits = residual_action_limits(model_config, runtime_config)
    physical_limit = runtime_config.physical.maximum_acceleration_meters_per_second_squared
    eligible = []
    for item in evaluations:
        action = _finite_vec2(item.action_world_acceleration, "expert candidate action")
        within_residual = all(
            abs(action[index] - base[index]) <= limits[index] + 1e-12
            for index in range(2)
        )
        within_physical = math.hypot(*action) <= physical_limit + 1e-12
        if (
            item.locally_feasible
            and item.safety_projection_compatible
            and item.robot_local_information_only
            and within_residual
            and within_physical
        ):
            eligible.append(item)
    if not eligible:
        raise ValueError("local action search has no eligible robot-local candidate")
    return max(
        eligible,
        key=lambda item: (
            item.utility(),
            -item.normalized_action_deviation,
            item.action_world_acceleration,
        ),
    )


def build_residual_action_target(
    base_action: Sequence[float],
    expert: LocalActionEvaluation,
    runtime_config: RuntimeConfig,
    model_config: FD24ModelConfig,
) -> ResidualActionTarget:
    base = _finite_vec2(base_action, "base action")
    expert_action = _finite_vec2(
        expert.action_world_acceleration,
        "expert action",
    )
    limits = residual_action_limits(model_config, runtime_config)
    raw = tuple(expert_action[index] - base[index] for index in range(2))
    clipped = tuple(
        max(-limits[index], min(limits[index], raw[index]))
        for index in range(2)
    )
    finite = all(math.isfinite(item) for item in clipped)
    tolerance = 1e-12
    nonzero = math.hypot(*clipped) > tolerance
    saturated = any(
        abs(clipped[index]) >= limits[index] - tolerance
        for index in range(2)
    )
    return ResidualActionTarget(
        RESIDUAL_ACTION_TARGET_SCHEMA_VERSION,
        RESIDUAL_EXPERT_ID,
        base,
        expert_action,
        clipped,
        tuple(float(item) for item in limits),
        finite,
        nonzero,
        saturated,
        expert.safety_projection_compatible,
    )


def rollout_configuration_hash(document: object) -> str:
    return sha256_document(document)
