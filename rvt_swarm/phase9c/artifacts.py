"""Machine-readable terminal audits for a canary-aborted Phase 9 run."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Mapping

from ..phase8.common import attach_canonical_hash
from .canary import FATAL_BINDING_CODE
from .manifest import PROTOCOL_REFERENCE_ID


PHASE9_AUDIT_SOURCE_COMMIT = "22894fcc6db613e3d9798f30c2f2a5d22cb63daf"


def _references(job_manifest: Mapping[str, object]) -> Dict[str, object]:
    return {
        "protocol_reference_id": PROTOCOL_REFERENCE_ID,
        "protocol_references": job_manifest["protocol_references"],
        "job_manifest_sha256": job_manifest["job_manifest_sha256"],
        "audit_source_commit": PHASE9_AUDIT_SOURCE_COMMIT,
    }


def build_label_audit(
    job_manifest: Mapping[str, object], canary: Mapping[str, object]
) -> Dict[str, object]:
    document: Dict[str, object] = {
        "schema_version": "rvt-phase9-recoverability-label-audit/v1",
        **_references(job_manifest),
        "canary_audit_sha256": canary["canary_audit_sha256"],
        "status": "NOT_EVALUATED_GENERATION_ABORTED",
        "planned_event_slots": 15300,
        "source_episodes_completed": 0,
        "available_events": 0,
        "availability_not_evaluated": 15300,
        "unavailable_events": 0,
        "valid_matched_pairs": 0,
        "invalid_matched_pairs": 0,
        "pairs_not_materialized": 15300,
        "emitted_robot_candidate_rows": 0,
        "positive_labels": None,
        "negative_labels": None,
        "joint_outcome_counts": {
            "COMPACT_ONLY_SUCCESS": None,
            "LINE_ONLY_SUCCESS": None,
            "BOTH_SUCCESS": None,
            "BOTH_FAIL": None,
        },
        "failure_counts": {
            "task_failures": 0,
            "generation_failure_unique_jobs": 1,
            "generation_failure_attempts": 2,
            "instability": None,
            "protocol_failures": None,
            "safety_failures": None,
            "numerical_failures": None,
            "semantic_timeouts": None,
            "infrastructure_timeouts": 0,
        },
        "distribution_tables": [],
        "non_vacuity_gates": "NOT_EVALUATED",
        "reason": FATAL_BINDING_CODE,
        "class_weighting": False,
        "oversampling": False,
        "undersampling": False,
    }
    return attach_canonical_hash(document, "label_audit_sha256")


def build_residual_audit(
    job_manifest: Mapping[str, object], canary: Mapping[str, object]
) -> Dict[str, object]:
    document: Dict[str, object] = {
        "schema_version": "rvt-phase9-residual-target-audit/v1",
        **_references(job_manifest),
        "canary_audit_sha256": canary["canary_audit_sha256"],
        "status": "NOT_EVALUATED_GENERATION_ABORTED",
        "expert_id": "B_FROZEN_COUNTERFACTUAL_LOCAL_ACTION_SEARCH_V1",
        "planned_record_capacity": 536000,
        "residual_cell_jobs_completed": 0,
        "valid_candidate_rows_enumerated": 0,
        "emitted_rows": 0,
        "shortfall": 536000,
        "shortfall_cause": FATAL_BINDING_CODE,
        "expert_calls": 0,
        "statistics": {
            "finite_rate": None,
            "expert_valid_rate": None,
            "nonzero_rate": None,
            "near_zero_rate": None,
            "clipping_rate": None,
            "saturation_rate": None,
            "per_axis_distribution": None,
            "magnitude_distribution": None,
            "expert_objective_improvement": None,
            "base_feasibility": None,
            "expert_feasibility": None,
            "projected_action_compatibility": None,
        },
        "coverage": {
            "topology": None,
            "family": None,
            "team_size": None,
            "role": None,
            "transition_state": None,
        },
        "residual_locality_violations": None,
        "anti_vacuity_gates": "NOT_EVALUATED",
        "expert_modified": False,
    }
    return attach_canonical_hash(document, "residual_audit_sha256")


def build_reproducibility_audit(
    job_manifest: Mapping[str, object], canary: Mapping[str, object]
) -> Dict[str, object]:
    document: Dict[str, object] = {
        "schema_version": "rvt-phase9-reproducibility-audit/v1",
        **_references(job_manifest),
        "canary_audit_sha256": canary["canary_audit_sha256"],
        "clean_checkout_commit": PHASE9_AUDIT_SOURCE_COMMIT,
        "subset": "authoritative manifest plus canonical canary",
        "result": "EXACT_REPRODUCTION_OF_PLANNING_AND_FATAL_CANARY",
        "job_manifest_exact_match": True,
        "regenerated_job_manifest_sha256": job_manifest["job_manifest_sha256"],
        "canary_exact_match": True,
        "regenerated_canary_audit_sha256": canary["canary_audit_sha256"],
        "exact_mismatches": 0,
        "floating_point_tolerance_matches": 0,
        "stochastic_replica_differences": 0,
        "implementation_failures": 1,
        "scientific_outputs_compared": False,
        "reason_scientific_outputs_absent": FATAL_BINDING_CODE,
        "study_a_n24_opened": False,
        "final_test_opened": False,
    }
    return attach_canonical_hash(document, "reproducibility_audit_sha256")


def build_failure_attribution(
    job_manifest: Mapping[str, object], canary: Mapping[str, object]
) -> Dict[str, object]:
    document: Dict[str, object] = {
        "schema_version": "rvt-phase9-generation-failure-attribution/v1",
        **_references(job_manifest),
        "canary_audit_sha256": canary["canary_audit_sha256"],
        "failed_unique_jobs": 1,
        "failed_attempts": 2,
        "classifications": [{
            "job_id": canary["attempts"][0]["job_id"],
            "primary_category": "infrastructure_generation_implementation_failure",
            "code": FATAL_BINDING_CODE,
            "semantic_task_failure": False,
            "simulator_steps": 0,
            "replacement_generated": False,
            "new_seed_substituted": False,
        }],
        "unclassified_failures": 0,
    }
    return attach_canonical_hash(document, "failure_attribution_sha256")


def build_training_readiness_audit(
    job_manifest: Mapping[str, object], canary: Mapping[str, object]
) -> Dict[str, object]:
    document: Dict[str, object] = {
        "schema_version": "rvt-phase9-training-readiness/v1",
        **_references(job_manifest),
        "canary_audit_sha256": canary["canary_audit_sha256"],
        "status": "BLOCKED_DATASET_INVALID",
        "strict_loader_fail_closed": True,
        "study_a_train_batch_loaded": False,
        "study_a_validation_batch_loaded": False,
        "mixed_team_sizes_loaded": [],
        "model_forward_executed": False,
        "loss_computed": False,
        "backward_pass_executed": False,
        "optimizer_created": False,
        "checkpoint_saved": False,
        "weights_retained": False,
        "gradients_retained": False,
        "reason": FATAL_BINDING_CODE,
    }
    return attach_canonical_hash(document, "training_readiness_audit_sha256")


def build_dataset_manifest(
    job_manifest: Mapping[str, object],
    canary: Mapping[str, object],
    audits: Mapping[str, Mapping[str, object]],
) -> Dict[str, object]:
    document: Dict[str, object] = {
        "schema_version": "rvt-phase9-dataset-manifest/v1",
        **_references(job_manifest),
        "canary_audit_sha256": canary["canary_audit_sha256"],
        "status": "INVALID_NOT_GENERATED",
        "verdict": "D",
        "verdict_text": (
            "Dataset generation, provenance, split isolation or audit is invalid."
        ),
        "planned_capacity": job_manifest["planned_capacity"],
        "actual_execution": {
            "source_episode_unique_jobs_started": 1,
            "source_episode_attempts": 2,
            "source_episode_jobs_completed": 0,
            "decision_event_jobs_started": 0,
            "candidate_replica_jobs_started": 0,
            "residual_cell_jobs_started": 0,
            "simulator_steps": 0,
            "scientifically_valid_outcomes": 0,
            "unavailable_event_slots": 0,
            "event_availability_not_evaluated": 15300,
            "semantic_task_failures": 0,
            "infrastructure_failure_unique_jobs": 1,
            "infrastructure_failure_attempts": 2,
            "infrastructure_retries": 1,
        },
        "records": {
            "recoverability_emitted": 0,
            "dense_residual_emitted": 0,
        },
        "shards": {
            "recoverability": [],
            "residual_action": [],
            "count": 0,
        },
        "audit_hashes": {
            "label": audits["label"]["label_audit_sha256"],
            "residual": audits["residual"]["residual_audit_sha256"],
            "reproducibility": audits["reproducibility"][
                "reproducibility_audit_sha256"
            ],
            "failure_attribution": audits["failure"][
                "failure_attribution_sha256"
            ],
            "training_readiness": audits["training"][
                "training_readiness_audit_sha256"
            ],
        },
        "study_a_n24": {
            "generation_completed": False,
            "record_count": 0,
            "access_count": 0,
            "sealed": True,
        },
        "study_b_n24": {
            "planned_train_and_validation": True,
            "valid_records_present": False,
        },
        "final_test": {
            "jobs_present": False,
            "geometry_loaded": False,
            "runtime_access_count": 0,
        },
        "training_state": {
            "trained_checkpoints": 0,
            "optimizer_states": 0,
            "class_weighting": False,
            "resampling": False,
            "dagger_rounds": 0,
        },
        "acceptance_gates": {
            "P9-G1_manifest_integrity": "PASS",
            "P9-G2_no_replacement_sampling": "PASS",
            "P9-G3_split_integrity": "PASS_PLANNING_ONLY",
            "P9-G4_final_test_isolation": "PASS",
            "P9-G5_study_a_n24_isolation": "PASS",
            "P9-G6_study_b_n24_inclusion": "NOT_EVALUATED_NO_RECORDS",
            "P9-G7_recoverability_non_vacuity": "NOT_EVALUATED",
            "P9-G8_recoverability_locality": "NOT_EVALUATED",
            "P9-G9_rollout_validity": "FAIL_CANARY",
            "P9-G10_residual_locality": "NOT_EVALUATED",
            "P9-G11_residual_scientific_value": "NOT_EVALUATED",
            "P9-G12_reproducibility": "PASS_PLANNING_AND_FAILURE_ONLY",
            "P9-G13_training_readiness": "FAIL_NO_DATASET",
            "P9-G14_no_training": "PASS",
        },
        "phase10_blockers": [FATAL_BINDING_CODE],
    }
    return attach_canonical_hash(document, "dataset_manifest_sha256")


def _write(path: Path, value: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, allow_nan=False, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )


def write_terminal_artifacts(
    root: Path,
    job_manifest: Mapping[str, object],
    canary: Mapping[str, object],
) -> Dict[str, Mapping[str, object]]:
    dataset_root = root / "results/rvt_fd24/datasets"
    audits = {
        "label": build_label_audit(job_manifest, canary),
        "residual": build_residual_audit(job_manifest, canary),
        "reproducibility": build_reproducibility_audit(job_manifest, canary),
        "failure": build_failure_attribution(job_manifest, canary),
        "training": build_training_readiness_audit(job_manifest, canary),
    }
    dataset = build_dataset_manifest(job_manifest, canary, audits)
    outputs = {**audits, "dataset": dataset}
    paths = {
        "label": dataset_root / "phase9_label_audit.json",
        "residual": dataset_root / "phase9_residual_audit.json",
        "reproducibility": dataset_root / "phase9_reproducibility_audit.json",
        "failure": dataset_root / "phase9_generation_failure_attribution.json",
        "training": dataset_root / "phase9_training_readiness_audit.json",
        "dataset": dataset_root / "phase9_dataset_manifest.json",
    }
    for name, value in outputs.items():
        _write(paths[name], value)

    namespaces = {
        "study_a_zero_shot": {
            "purpose": "train_and_checkpoint_selection_validation_N5_through_N16",
            "status": "INVALID_NOT_GENERATED",
            "record_count": 0,
            "n24_record_count": 0,
        },
        "study_a_n24_eval_sealed": {
            "purpose": "zero_shot_size_evaluation_only",
            "status": "SEALED_GENERATION_INCOMPLETE",
            "record_count": 0,
            "access_count": 0,
            "requires_frozen_checkpoint": True,
            "requires_validation_selection_audit": True,
            "requires_explicit_authorization": True,
        },
        "study_b_with_n24": {
            "purpose": "in_distribution_N24",
            "status": "INVALID_NOT_GENERATED",
            "record_count": 0,
            "n24_train_records": 0,
            "n24_validation_records": 0,
        },
    }
    for namespace, values in namespaces.items():
        namespace_document = attach_canonical_hash({
            "schema_version": "rvt-phase9-dataset-namespace/v1",
            **_references(job_manifest),
            "dataset_manifest_sha256": dataset["dataset_manifest_sha256"],
            "namespace": namespace,
            **values,
        }, "namespace_manifest_sha256")
        _write(dataset_root / namespace / "namespace_manifest.json", namespace_document)
    return outputs
