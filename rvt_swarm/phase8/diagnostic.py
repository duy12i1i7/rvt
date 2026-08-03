"""Predeclared tiny target non-vacuity diagnostic; never a scientific dataset."""

from __future__ import annotations

import math
from collections import Counter
from typing import Dict, Tuple

from ..fd24.configuration import FD24ModelConfig
from ..runtime_configuration import RuntimeConfig
from ..topology_registry import COMPACT, LINE
from .common import PHASE8_APPROVED_BASE_COMMIT, sha256_document
from .scenario import (
    BOTH_FAIL,
    BOTH_SUCCESS,
    COMPACT_ONLY_SUCCESS,
    LINE_ONLY_SUCCESS,
    TRAIN_SPLIT,
    VALIDATION_SPLIT,
    ScenarioLayout,
    generate_layouts,
)
from .seeds import derive_seed
from .targets import (
    COUNTERFACTUAL_ROLLOUT_SCHEMA_VERSION,
    RESIDUAL_EXPERT_ID,
    CounterfactualRolloutTrace,
    LocalActionEvaluation,
    MatchedCounterfactualPair,
    TaskRecoveryConditions,
    build_residual_action_target,
    evaluate_candidate_recoverability,
    joint_outcome_category,
    rollout_configuration_hash,
    select_counterfactual_local_action,
    verify_matched_counterfactual_pair,
)


TINY_DIAGNOSTIC_SCHEMA_VERSION = "rvt-phase8-target-diagnostic/v1"
TINY_DECISION_EVENT_BUDGET = 8
TINY_CANDIDATE_ROLLOUT_BUDGET = 16
TINY_RESIDUAL_SAMPLE_BUDGET = 16

_CATEGORY_FAMILY = {
    BOTH_SUCCESS: "F1",
    LINE_ONLY_SUCCESS: "F2",
    COMPACT_ONLY_SUCCESS: "F6",
    BOTH_FAIL: "F10",
}


def _selected_layouts() -> Tuple[ScenarioLayout, ...]:
    selected = []
    for split in (TRAIN_SPLIT, VALIDATION_SPLIT):
        layouts = generate_layouts(split)
        selected.extend(
            next(item for item in layouts if item.family_id == family)
            for family in _CATEGORY_FAMILY.values()
        )
    return tuple(selected)


def _candidate_success(category: str, candidate: int) -> bool:
    if category == BOTH_SUCCESS:
        return True
    if category == BOTH_FAIL:
        return False
    if category == COMPACT_ONLY_SUCCESS:
        return candidate == COMPACT
    if category == LINE_ONLY_SUCCESS:
        return candidate == LINE
    raise ValueError(f"tiny diagnostic does not support category {category!r}")


def _conditions(success: bool) -> TaskRecoveryConditions:
    if success:
        return TaskRecoveryConditions(*(True for _ in range(10)))
    return TaskRecoveryConditions(
        collision_free_complete_horizon=True,
        no_persistent_deadlock=False,
        candidate_commitment_valid=True,
        transition_execution_valid=True,
        target_metric_v3_dwell_complete=False,
        downstream_goal_complete=False,
        protocol_resolved=True,
        safety_projection_resolved=True,
        numerically_valid=True,
        no_irreversible_progress_loss=False,
    )


def _trace(
    layout: ScenarioLayout,
    category: str,
    candidate: int,
    event_index: int,
) -> CounterfactualRolloutTrace:
    success = _candidate_success(category, candidate)
    event_id = f"tiny-{layout.split}-{layout.family_id}-{event_index:02d}"
    disturbance_seed = derive_seed(
        "counterfactual_rollout",
        event_id,
        0,
        split=layout.split,
    )
    rollout_config = {
        "controller": "frozen_phase6",
        "safety": "frozen_robot_local_projection",
        "protocol": "frozen_transition_protocol_v1",
        "aggregation": "all_success",
        "replicas": 1,
        "horizon_seconds": layout.episode_horizon_seconds,
    }
    return CounterfactualRolloutTrace(
        COUNTERFACTUAL_ROLLOUT_SCHEMA_VERSION,
        f"episode-{event_id}",
        event_id,
        candidate,
        0,
        sha256_document({"layout": layout.geometry_sha256(), "state": 0}),
        sha256_document({"source_topology": COMPACT, "lifecycle": "stable"}),
        disturbance_seed,
        sha256_document(layout.communication_profile),
        rollout_configuration_hash(rollout_config),
        layout.episode_horizon_seconds,
        _conditions(success),
        None if success else "diagnostic_task_failure",
        int(round(layout.episode_horizon_seconds / 0.15)),
    )


def _action_evaluations(
    sample_index: int,
    runtime_config: RuntimeConfig,
    model_config: FD24ModelConfig,
) -> Tuple[Tuple[float, float], Tuple[LocalActionEvaluation, ...]]:
    base = (0.10 + 0.005 * (sample_index % 3), 0.02 * ((sample_index % 2) * 2 - 1))
    residual_limit = (
        runtime_config.physical.maximum_acceleration_meters_per_second_squared
        * model_config.residual_limit_fractions_of_maximum_acceleration[0]
    )
    if sample_index % 4 == 0:
        delta = (0.0, 0.0)
    elif sample_index % 4 == 1:
        delta = (0.05, -0.03)
    elif sample_index % 4 == 2:
        delta = (-0.04, 0.06)
    else:
        delta = (residual_limit, 0.0)
    improved = (base[0] + delta[0], base[1] + delta[1])
    baseline = LocalActionEvaluation(
        base, True, True, True, 0.40, 0.35, 0.30, 0.0
    )
    expert = LocalActionEvaluation(
        improved, True, True, True,
        0.65 if delta != (0.0, 0.0) else 0.40,
        0.50 if delta != (0.0, 0.0) else 0.35,
        0.20 if delta != (0.0, 0.0) else 0.30,
        math.hypot(*delta) / max(residual_limit, 1e-12),
    )
    rejected_global = LocalActionEvaluation(
        (base[0], base[1] + 0.01), True, True, False, 1.0, 1.0, 0.0, 0.1
    )
    return base, (baseline, expert, rejected_global)


def run_tiny_target_diagnostic() -> Dict[str, object]:
    layouts = _selected_layouts()
    if len(layouts) != TINY_DECISION_EVENT_BUDGET:
        raise RuntimeError("tiny diagnostic layout budget changed")
    candidate_labels = Counter()
    joint_categories = Counter()
    matched_issues = []
    rollout_costs = []
    for event_index, layout in enumerate(layouts):
        category = layout.headroom_for(5)
        compact_trace = _trace(layout, category, COMPACT, event_index)
        line_trace = _trace(layout, category, LINE, event_index)
        pair = MatchedCounterfactualPair(
            compact_trace.decision_event_id,
            (compact_trace,),
            (line_trace,),
        )
        matched_issues.extend(verify_matched_counterfactual_pair(pair))
        compact_target = evaluate_candidate_recoverability((compact_trace,))
        line_target = evaluate_candidate_recoverability((line_trace,))
        candidate_labels[(COMPACT, compact_target.label)] += 1
        candidate_labels[(LINE, line_target.label)] += 1
        joint_categories[joint_outcome_category(compact_target, line_target)] += 1
        rollout_costs.extend((
            compact_target.average_rollout_cost_steps,
            line_target.average_rollout_cost_steps,
        ))

    runtime_config = RuntimeConfig.for_team_size(5)
    model_config = FD24ModelConfig()
    residual_targets = []
    candidate_distribution = Counter()
    role_distribution = Counter()
    topology_distribution = Counter()
    transition_direction_distribution = Counter()
    for sample_index in range(TINY_RESIDUAL_SAMPLE_BUDGET):
        base, evaluations = _action_evaluations(
            sample_index, runtime_config, model_config
        )
        expert = select_counterfactual_local_action(
            base, evaluations, runtime_config, model_config
        )
        target = build_residual_action_target(
            base, expert, runtime_config, model_config
        )
        residual_targets.append(target)
        candidate_distribution[COMPACT if sample_index % 2 == 0 else LINE] += 1
        role_distribution[f"role_{sample_index % 5}"] += 1
        source_topology = COMPACT if sample_index % 2 == 0 else LINE
        topology_distribution[source_topology] += 1
        transition_direction_distribution[
            "COMPACT_TO_LINE" if source_topology == COMPACT else "LINE_TO_COMPACT"
        ] += 1

    finite_count = sum(item.finite for item in residual_targets)
    nonzero_count = sum(item.nonzero for item in residual_targets)
    saturation_count = sum(item.saturated for item in residual_targets)
    safety_count = sum(item.safety_projection_compatible for item in residual_targets)
    document: Dict[str, object] = {
        "schema_version": TINY_DIAGNOSTIC_SCHEMA_VERSION,
        "source_commit": PHASE8_APPROVED_BASE_COMMIT,
        "declared_budget": {
            "decision_events": TINY_DECISION_EVENT_BUDGET,
            "candidate_rollouts": TINY_CANDIDATE_ROLLOUT_BUDGET,
            "residual_action_samples": TINY_RESIDUAL_SAMPLE_BUDGET,
        },
        "recoverability": {
            "candidate_positive_counts": {
                "COMPACT": candidate_labels[(COMPACT, 1)],
                "LINE": candidate_labels[(LINE, 1)],
            },
            "candidate_negative_counts": {
                "COMPACT": candidate_labels[(COMPACT, 0)],
                "LINE": candidate_labels[(LINE, 0)],
            },
            "joint_outcome_counts": dict(sorted(joint_categories.items())),
            "invalid_rollout_count": 0,
            "unstable_target_count": 0,
            "matched_rollout_issues": sorted(set(matched_issues)),
            "average_rollout_cost_steps": sum(rollout_costs) / len(rollout_costs),
        },
        "residual_action": {
            "expert_source": RESIDUAL_EXPERT_ID,
            "valid_sample_count": len(residual_targets),
            "finite_count": finite_count,
            "nonzero_residual_count": nonzero_count,
            "nonzero_residual_fraction": nonzero_count / len(residual_targets),
            "saturation_count": saturation_count,
            "saturation_fraction": saturation_count / len(residual_targets),
            "safety_compatible_count": safety_count,
            "candidate_distribution": {
                "COMPACT": candidate_distribution[COMPACT],
                "LINE": candidate_distribution[LINE],
            },
            "committed_topology_distribution": {
                "COMPACT": topology_distribution[COMPACT],
                "LINE": topology_distribution[LINE],
            },
            "transition_direction_distribution": dict(
                sorted(transition_direction_distribution.items())
            ),
            "role_distribution": dict(sorted(role_distribution.items())),
            "maximum_residual_magnitude_mps2": max(
                math.hypot(*item.residual_target_world_acceleration)
                for item in residual_targets
            ),
        },
        "scientific_dataset_generated": False,
        "model_training_runs": 0,
        "dagger_rounds": 0,
        "final_test_runtime_access_count": 0,
    }
    document["diagnostic_sha256"] = sha256_document(document)
    return document
