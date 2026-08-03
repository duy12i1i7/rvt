"""Exact machine-readable budget frozen by the Phase 9B addendum."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Mapping, Sequence, Tuple

from ..phase8.common import attach_canonical_hash, file_sha256, verify_canonical_hash
from ..phase8.splits import load_nonfinal_split_manifest
from ..phase9.common import (
    EXPERIMENT_PROTOCOL_SHA256,
    FINAL_TEST_SPLIT_COMMITMENT_SHA256,
    ONLINE_SCOPE_SHA256,
    PHASE8_SOURCE_COMMIT,
    TRAIN_SPLIT_SHA256,
    VALIDATION_SPLIT_SHA256,
)


GENERATION_BUDGET_SCHEMA_VERSION = "rvt-generation-budget/v1"
COMPOSITE_PROTOCOL_SCHEMA_VERSION = "rvt-dataset-generation-protocol/v1"
GENERATION_SEED_DERIVATION_VERSION = "rvt-generation-seed-sha256-uint32/v1"
GENERATION_JOB_ID_SCHEMA_VERSION = "rvt-generation-job-identity/v1"
DENSE_SELECTION_VERSION = "rvt-dense-row-hash-ranking/v1"

STUDY_A_TRAIN = "study_a_train"
STUDY_A_VALIDATION = "study_a_validation"
STUDY_A_N24_EVALUATION = "study_a_n24_evaluation"
STUDY_B_TRAIN = "study_b_train"
STUDY_B_VALIDATION = "study_b_validation"
DATASET_IDS: Tuple[str, ...] = (
    STUDY_A_TRAIN,
    STUDY_A_VALIDATION,
    STUDY_A_N24_EVALUATION,
    STUDY_B_TRAIN,
    STUDY_B_VALIDATION,
)

SOURCE_CLASSES: Tuple[str, ...] = (
    "S0_SCRIPTED_DIAGNOSTIC",
    "S1_ALWAYS_COMPACT",
    "S2_ALWAYS_LINE",
    "S3_FROZEN_LOCAL_GEOMETRIC_SELECTOR",
    "S4_FROZEN_TRANSITION_PROTOCOL",
    "S5_BOUNDED_PERTURBATION",
)
EVENT_TIMESTAMP_SCHEDULES: Mapping[int, Tuple[float, ...]] = {
    4: (0.15, 0.40, 0.65, 0.90),
    5: (0.10, 0.30, 0.50, 0.70, 0.90),
}
COUNTERFACTUAL_REPLICAS_BY_FAMILY: Mapping[str, int] = {
    **{f"F{index}": 1 for index in range(1, 8)},
    "F8": 3,
    "F9": 3,
    "F10": 1,
}
WALL_CLOCK_TIMEOUT_SECONDS: Mapping[str, int] = {
    "source_trajectory_episode_job": 600,
    "counterfactual_candidate_replica_job": 900,
    "residual_action_cell_generation_job": 1800,
    "shard_finalization_job": 600,
}
INFRASTRUCTURE_RETRY_REASONS: Tuple[str, ...] = (
    "process_interruption",
    "worker_crash",
    "temporary_storage_failure",
    "machine_interruption",
)


@dataclass(frozen=True)
class DatasetBudgetSpec:
    dataset_id: str
    study: str
    split: str
    layout_source_split: str
    purpose: str
    layout_count: int
    team_sizes: Tuple[int, ...]
    source_episodes_per_cell: int
    decision_events_per_cell: int
    dense_records_per_cell: int
    expected_source_episodes: int
    expected_decision_events: int
    expected_candidate_replica_rollouts: int
    expected_recoverability_records: int
    expected_dense_records: int
    sealed_from_model_selection: bool = False


DATASET_BUDGETS: Tuple[DatasetBudgetSpec, ...] = (
    DatasetBudgetSpec(
        STUDY_A_TRAIN, "study_a_zero_shot", "train", "train", "training",
        20, (5, 6, 8, 12, 16), 12, 60, 2000,
        1200, 6000, 16800, 112800, 200000,
    ),
    DatasetBudgetSpec(
        STUDY_A_VALIDATION, "study_a_zero_shot", "validation", "validation",
        "checkpoint_selection_validation", 10, (5, 6, 8, 12, 16), 6, 30, 800,
        300, 1500, 4200, 28200, 40000,
    ),
    DatasetBudgetSpec(
        STUDY_A_N24_EVALUATION, "study_a_zero_shot", "n24_evaluation",
        "validation", "zero_shot_size_evaluation_only", 10, (24,), 6, 30, 800,
        60, 300, 840, 14400, 8000, True,
    ),
    DatasetBudgetSpec(
        STUDY_B_TRAIN, "study_b_with_n24", "train", "train", "training",
        20, (5, 6, 8, 12, 16, 24), 10, 50, 2000,
        1200, 6000, 16800, 142000, 240000,
    ),
    DatasetBudgetSpec(
        STUDY_B_VALIDATION, "study_b_with_n24", "validation", "validation",
        "checkpoint_selection_validation", 10, (5, 6, 8, 12, 16, 24), 6, 25, 800,
        360, 1500, 4200, 35500, 48000,
    ),
)
_SPEC_BY_ID = {item.dataset_id: item for item in DATASET_BUDGETS}


def dataset_budget(dataset_id: str) -> DatasetBudgetSpec:
    try:
        return _SPEC_BY_ID[dataset_id]
    except KeyError as exc:
        raise ValueError(f"unknown Phase 9B dataset {dataset_id!r}") from exc


def _layout_records(root: Path, split: str) -> Sequence[Mapping[str, object]]:
    if split not in ("train", "validation"):
        raise PermissionError("Phase 9B can load train or validation layouts only")
    manifest = load_nonfinal_split_manifest(
        root / f"results/rvt_fd24/splits/{split}_layouts.json"
    )
    records = manifest.get("layout_records")
    if not isinstance(records, list):
        raise ValueError("split manifest has no layout records")
    return records


def derive_dataset_totals(root: Path, spec: DatasetBudgetSpec) -> Dict[str, object]:
    layouts = _layout_records(root, spec.layout_source_split)
    if len(layouts) != spec.layout_count:
        raise ValueError(f"{spec.dataset_id} layout count differs from the frozen budget")
    family_layouts = Counter(str(item["family_id"]) for item in layouts)
    if set(family_layouts) != {f"F{index}" for index in range(1, 11)}:
        raise ValueError("the approved split no longer contains F1-F10")
    cells = spec.layout_count * len(spec.team_sizes)
    family_events = {
        family: count * len(spec.team_sizes) * spec.decision_events_per_cell
        for family, count in sorted(family_layouts.items())
    }
    rollouts = sum(
        events * 2 * COUNTERFACTUAL_REPLICAS_BY_FAMILY[family]
        for family, events in family_events.items()
    )
    records = sum(
        spec.layout_count * spec.decision_events_per_cell * 2 * team_size
        for team_size in spec.team_sizes
    )
    return {
        "cell_count": cells,
        "source_episodes": cells * spec.source_episodes_per_cell,
        "decision_events": cells * spec.decision_events_per_cell,
        "candidate_replica_rollouts": rollouts,
        "recoverability_robot_candidate_records": records,
        "dense_residual_action_records": cells * spec.dense_records_per_cell,
        "decision_events_by_family": family_events,
    }


def _assert_expected(spec: DatasetBudgetSpec, totals: Mapping[str, object]) -> None:
    expected = {
        "source_episodes": spec.expected_source_episodes,
        "decision_events": spec.expected_decision_events,
        "candidate_replica_rollouts": spec.expected_candidate_replica_rollouts,
        "recoverability_robot_candidate_records": spec.expected_recoverability_records,
        "dense_residual_action_records": spec.expected_dense_records,
    }
    observed = {name: totals[name] for name in expected}
    if observed != expected:
        raise ValueError(f"{spec.dataset_id} totals conflict with the approved addendum")


def _source_allocation_contract() -> Dict[str, object]:
    return {
        STUDY_A_TRAIN: {"episodes_per_source_per_cell": [2, 2, 2, 2, 2, 2]},
        STUDY_A_VALIDATION: {"episodes_per_source_per_cell": [1, 1, 1, 1, 1, 1]},
        STUDY_A_N24_EVALUATION: {"episodes_per_source_per_cell": [1, 1, 1, 1, 1, 1]},
        STUDY_B_TRAIN: {
            "episodes_per_source_multiset": [2, 2, 2, 2, 1, 1],
            "rotation": "canonical_cell_hash_rank_then_balanced_cyclic_four_source_window",
            "required_global_episode_count_per_source": 200,
        },
        STUDY_B_VALIDATION: {"episodes_per_source_per_cell": [1, 1, 1, 1, 1, 1]},
    }


def build_generation_budget_manifest(root: Path) -> Dict[str, object]:
    datasets = []
    aggregate = Counter()
    for spec in DATASET_BUDGETS:
        totals = derive_dataset_totals(root, spec)
        _assert_expected(spec, totals)
        aggregate.update({
            "source_episodes": int(totals["source_episodes"]),
            "decision_events": int(totals["decision_events"]),
            "candidate_replica_rollouts": int(totals["candidate_replica_rollouts"]),
            "recoverability_robot_candidate_records": int(
                totals["recoverability_robot_candidate_records"]
            ),
            "dense_residual_action_records": int(totals["dense_residual_action_records"]),
        })
        spec_document = asdict(spec)
        spec_document["team_sizes"] = list(spec.team_sizes)
        datasets.append({**spec_document, "derived_totals": totals})
    exact_totals = {
        "source_episodes": 3120,
        "decision_events": 15300,
        "candidate_replica_rollouts": 42840,
        "recoverability_robot_candidate_records": 332900,
        "dense_residual_action_records": 536000,
    }
    if dict(aggregate) != exact_totals:
        raise ValueError("aggregate Phase 9B totals do not match the approved addendum")
    document: Dict[str, object] = {
        "schema_version": GENERATION_BUDGET_SCHEMA_VERSION,
        "references": {
            "phase8_protocol_sha256": EXPERIMENT_PROTOCOL_SHA256,
            "phase8_source_commit": PHASE8_SOURCE_COMMIT,
            "blocked_phase9_commit": "b7edc024eeb3d76f0827f23f3fc9a0aa34a461ae",
            "online_topology_scope_sha256": ONLINE_SCOPE_SHA256,
            "train_split_sha256": TRAIN_SPLIT_SHA256,
            "validation_split_sha256": VALIDATION_SPLIT_SHA256,
            "sealed_final_test_commitment_sha256": FINAL_TEST_SPLIT_COMMITMENT_SHA256,
        },
        "candidate_topologies": [5, 2],
        "datasets": datasets,
        "exact_total_budget": exact_totals,
        "scenario_family_contract": {
            "family_ids": [f"F{index}" for index in range(1, 11)],
            "equal_event_budget_within_each_dataset": True,
            "replicas_by_family": dict(COUNTERFACTUAL_REPLICAS_BY_FAMILY),
            "candidate_rollouts_per_deterministic_event": 2,
            "candidate_replica_rollouts_per_f8_f9_event": 6,
            "aggregation": "all_success",
        },
        "source_trajectory_contract": {
            "source_classes": list(SOURCE_CLASSES),
            "allocation_by_dataset": _source_allocation_contract(),
            "outcome_conditioned_source_selection": False,
        },
        "event_timestamp_contract": {
            "normalized_horizon_positions_by_slot_count": {
                str(count): list(values)
                for count, values in EVENT_TIMESTAMP_SCHEDULES.items()
            },
            "step_mapping": "ceil(normalized_position * horizon_seconds / control_period_seconds)",
            "early_termination": "mark_unavailable_preserve_denominator_no_replacement",
            "episode_slot_allocation_by_dataset": {
                STUDY_A_TRAIN: "12_episodes_each_with_5_slots",
                STUDY_A_VALIDATION: "6_episodes_each_with_5_slots",
                STUDY_A_N24_EVALUATION: "6_episodes_each_with_5_slots",
                STUDY_B_TRAIN: "10_episodes_each_with_5_slots",
                STUDY_B_VALIDATION: (
                    "6_episodes_one_with_5_slots_and_five_with_4_slots;"
                    "five_slot_source_index=int(canonical_cell_sha256,16)%6"
                ),
            },
        },
        "seed_contract": {
            "derivation_version": GENERATION_SEED_DERIVATION_VERSION,
            "canonical_encoding": "sorted_ascii_json_without_nan",
            "digest": "SHA-256",
            "approved_seed_width_bits": 32,
            "digest_truncation": "first_4_bytes_big_endian",
            "model_seed_namespace_is_separate": True,
        },
        "dense_row_contract": {
            "selection_version": DENSE_SELECTION_VERSION,
            "canonical_order": [
                "episode_id", "timestep", "robot_id", "topology_id", "graph_fingerprint"
            ],
            "selection": "deterministic_hash_rank_without_replacement_up_to_cell_quota",
            "prohibited_rank_inputs": [
                "residual_magnitude", "expert_improvement", "safety_intervention",
                "label", "success", "scenario_outcome",
            ],
            "shortfall": "preserve_and_report_no_replacement_no_duplication",
        },
        "retry_contract": {
            "semantic_generation_retries": 0,
            "maximum_infrastructure_retries": 1,
            "allowed_infrastructure_reasons": list(INFRASTRUCTURE_RETRY_REASONS),
            "identity_rule": "same_job_seed_input_configuration_destination",
            "attempt_logging": "both_attempts",
            "scientific_denominator_delta": 0,
        },
        "timeout_contract": {
            "simulator_semantic_timeout": "frozen_phase8_family_horizon",
            "wall_clock_seconds": dict(WALL_CLOCK_TIMEOUT_SECONDS),
            "wall_clock_timeout_classification": "infrastructure_generation_failure",
            "label_policy": "no_label_unless_simulator_semantic_timeout_was_reached_normally",
        },
        "invalid_record_contract": {
            "recoverability_pair": (
                "invalid_pair_preserve_traces_no_training_rows_keep_audit_denominator_no_replacement"
            ),
            "valid_task_failure": "legitimate_negative_label",
            "residual_expert_invalid": (
                "preserve_base_and_failure_metadata_no_target_row_keep_invalid_denominator_no_replacement"
            ),
        },
        "job_identity_contract": {
            "schema_version": GENERATION_JOB_ID_SCHEMA_VERSION,
            "source_episode": [
                "study", "split", "family", "layout_sha256", "team_size",
                "source_class", "episode_index",
            ],
            "decision_event": ["source_episode_job_id", "event_slot_index"],
            "candidate_replica": [
                "decision_event_id", "candidate_topology", "replica_index",
            ],
            "residual_cell": [
                "study", "split", "family", "layout_sha256", "team_size",
            ],
            "shard": [
                "dataset_type", "study", "split", "family", "team_size",
                "shard_index",
            ],
            "duplicate_semantic_identity_policy": "reject",
            "worker_order_participates_in_identity": False,
            "permitted_layout_source_splits": ["train", "validation"],
            "final_test_job_construction": "prohibited",
        },
        "study_a_n24_access": {
            "purpose": "zero_shot_size_evaluation_only",
            "requires_frozen_checkpoint_sha256": True,
            "requires_validation_selection_audit_sha256": True,
            "requires_explicit_authorization": True,
            "requires_access_log": True,
            "prohibited_consumers": [
                "training", "early_stopping", "hyperparameter_search", "checkpoint_selection"
            ],
        },
        "post_observation_budget_change_permitted": False,
        "scientific_dataset_records_generated": 0,
        "rollout_jobs_executed": 0,
        "training_operations": 0,
        "final_test_runtime_access_count": 0,
    }
    return attach_canonical_hash(document, "generation_budget_sha256")


def build_generation_protocol_manifest(
    root: Path, generation_budget: Mapping[str, object] | None = None,
) -> Dict[str, object]:
    budget = (
        build_generation_budget_manifest(root)
        if generation_budget is None else dict(generation_budget)
    )
    if not verify_canonical_hash(budget, "generation_budget_sha256"):
        raise ValueError("generation-budget manifest hash is invalid")
    document: Dict[str, object] = {
        "schema_version": COMPOSITE_PROTOCOL_SCHEMA_VERSION,
        "phase8_protocol_sha256": EXPERIMENT_PROTOCOL_SHA256,
        "generation_budget_sha256": budget["generation_budget_sha256"],
        "source_commit": PHASE8_SOURCE_COMMIT,
        "online_topology_scope_sha256": ONLINE_SCOPE_SHA256,
        "split_sha256": {
            "train": TRAIN_SPLIT_SHA256,
            "validation": VALIDATION_SPLIT_SHA256,
            "final_test_sealed_commitment": FINAL_TEST_SPLIT_COMMITMENT_SHA256,
        },
        "seed_derivation_version": GENERATION_SEED_DERIVATION_VERSION,
        "event_timestamp_schedule": budget["event_timestamp_contract"],
        "retry_policy": budget["retry_contract"],
        "timeout_policy": budget["timeout_contract"],
        "invalid_record_policy": budget["invalid_record_contract"],
        "exact_expected_totals": budget["exact_total_budget"],
        "study_a_n24_access": budget["study_a_n24_access"],
        "future_dataset_required_hashes": [
            EXPERIMENT_PROTOCOL_SHA256,
            budget["generation_budget_sha256"],
        ],
        "blocked_phase9_audit": {
            "path": "results/rvt_fd24/datasets/phase9_generation_budget.json",
            "sha256": file_sha256(
                root / "results/rvt_fd24/datasets/phase9_generation_budget.json"
            ),
            "can_authorize_generation": False,
        },
        "execution_scope": {
            "scientific_dataset_records_generated": 0,
            "rollout_jobs_executed": 0,
            "residual_expert_jobs_executed": 0,
            "training_operations": 0,
            "final_test_geometry_loaded": False,
            "final_test_runtime_access_count": 0,
        },
    }
    return attach_canonical_hash(document, "dataset_generation_protocol_sha256")
