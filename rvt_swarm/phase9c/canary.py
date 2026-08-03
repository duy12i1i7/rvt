"""Deterministic Phase 9 canary selection and fatal execution-binding audit."""

from __future__ import annotations

import inspect
import json
from pathlib import Path
from typing import Dict, Mapping, Sequence

from ..config import Config
from ..decentralized.runtime import simulate_decentralized_episode
from ..decentralized.system_model import MODES
from ..decentralized.transition_runtime import run_phase7_transition_episode
from ..phase8.common import attach_canonical_hash
from ..phase8.scenario import generate_layouts
from ..phase9b.budget import SOURCE_CLASSES
from ..topology_registry import COMPACT, LINE
from .manifest import PROTOCOL_REFERENCE_ID


PHASE9_CANARY_AUDIT_SCHEMA_VERSION = "rvt-phase9-execution-canary/v1"
CANARY_SELECTION_VERSION = "rvt-phase9-canary-constrained-prefix/v1"
FATAL_BINDING_CODE = "PHASE8_SCENARIO_TO_ACTIVE_RUNTIME_BINDING_ABSENT"


def _first(items: Sequence[Mapping[str, object]], predicate) -> Mapping[str, object]:
    for item in sorted(items, key=lambda value: str(value["job_id"])):
        if predicate(item):
            return item
    raise ValueError("canonical canary constraint cannot be satisfied")


def select_canonical_canary(manifest: Mapping[str, object]) -> Dict[str, object]:
    """Select the smallest declared coverage set without reading outcomes."""
    sources = manifest["source_episode_jobs"]
    required_datasets = (
        "study_a_train",
        "study_a_validation",
        "study_b_train",
        "study_b_validation",
    )
    selected_sources = [
        _first(
            sources,
            lambda item, dataset_id=dataset_id: (
                item["dataset_id"] == dataset_id
                and item["source_class"] == "S1_ALWAYS_COMPACT"
                and not item["sealed"]
            ),
        )
        for dataset_id in required_datasets
    ]
    selected_sizes = {int(item["team_size"]) for item in selected_sources}
    if len(selected_sizes) < 2:
        alternate_size_source = _first(
            sources,
            lambda item: (
                item["dataset_id"] == "study_a_train"
                and item["source_class"] == "S1_ALWAYS_COMPACT"
                and int(item["team_size"]) not in selected_sizes
                and not item["sealed"]
            ),
        )
        selected_sources.append(alternate_size_source)
    stochastic_event = _first(
        manifest["decision_event_jobs"],
        lambda item: (
            item["family_id"] in ("F8", "F9")
            and item["source_class"] == "S1_ALWAYS_COMPACT"
            and not item["sealed"]
        ),
    )
    source_by_id = {item["job_id"]: item for item in sources}
    stochastic_source = source_by_id[stochastic_event["source_episode_job_id"]]
    if stochastic_source["job_id"] not in {
        item["job_id"] for item in selected_sources
    }:
        selected_sources.append(stochastic_source)
    replicas = [
        item for item in manifest["candidate_replica_jobs"]
        if item["decision_event_job_id"] == stochastic_event["job_id"]
    ]
    replicas.sort(key=lambda item: str(item["job_id"]))
    residual = _first(
        manifest["residual_cell_jobs"],
        lambda item: not item["sealed"],
    )
    return {
        "selection_version": CANARY_SELECTION_VERSION,
        "selection_uses_outcomes_or_labels": False,
        "source_episode_job_ids": [item["job_id"] for item in selected_sources],
        "candidate_replica_job_ids": [item["job_id"] for item in replicas],
        "stochastic_event_job_id": stochastic_event["job_id"],
        "residual_cell_job_id": residual["job_id"],
        "coverage": {
            "datasets": sorted({item["dataset_id"] for item in selected_sources}),
            "studies": sorted({item["study"] for item in selected_sources}),
            "splits": sorted({item["split"] for item in selected_sources}),
            "families": sorted({item["family_id"] for item in selected_sources}),
            "team_sizes": sorted({item["team_size"] for item in selected_sources}),
            "candidates": sorted({item["candidate_topology"] for item in replicas}),
            "replicas_per_candidate": {
                str(candidate): sum(
                    item["candidate_topology"] == candidate for item in replicas
                )
                for candidate in (COMPACT, LINE)
            },
            "study_a_n24_opened": False,
        },
    }


def _layout_for_job(job: Mapping[str, object]):
    split = str(job["layout_source_split"])
    return next(
        layout for layout in generate_layouts(split)
        if layout.geometry_sha256() == job["layout_sha256"]
    )


def _attempt_actual_source_job(job: Mapping[str, object]) -> Dict[str, object]:
    """Use the repository's only full closed-loop decentralized entrypoint."""
    layout = _layout_for_job(job)
    try:
        simulate_decentralized_episode(
            Config(),
            layout,
            int(job["team_size"]),
            int(job["seeds"]["initial_condition"]),
            forced_mode=COMPACT,
        )
    except Exception as exc:  # The exact failure is the canary evidence.
        return {
            "job_id": job["job_id"],
            "attempted_entrypoint": (
                "rvt_swarm.decentralized.runtime.simulate_decentralized_episode"
            ),
            "attempt_status": "INFRASTRUCTURE_FAILURE",
            "scientific_rollout_started": False,
            "exception_type": type(exc).__name__,
            "exception_message": str(exc),
            "retry_permitted": True,
            "retry_reason": "worker_crash",
            "semantic_task_failure": False,
        }
    return {
        "job_id": job["job_id"],
        "attempted_entrypoint": (
            "rvt_swarm.decentralized.runtime.simulate_decentralized_episode"
        ),
        "attempt_status": "UNEXPECTED_COMPLETION",
        "scientific_rollout_started": True,
        "exception_type": None,
        "exception_message": None,
        "retry_permitted": False,
        "retry_reason": None,
        "semantic_task_failure": False,
    }


def _execution_binding_evidence() -> Dict[str, object]:
    transition_parameters = tuple(
        inspect.signature(run_phase7_transition_episode).parameters
    )
    return {
        "legacy_closed_loop_runtime": {
            "declared_topology_modes": list(MODES),
            "active_phase8_candidates": [COMPACT, LINE],
            "compact_supported": COMPACT in MODES,
            "scenario_layout_fields_expected_by_environment": [
                "start_center", "goal", "obstacle_array"
            ],
            "phase8_scenario_layout_fields": [
                "start_center_meters", "goal_center_meters", "static_obstacles",
                "dynamic_obstacle_paths", "corridor_centerline_meters"
            ],
        },
        "qualified_transition_runtime": {
            "entrypoint": (
                "rvt_swarm.decentralized.transition_runtime."
                "run_phase7_transition_episode"
            ),
            "accepted_parameters": list(transition_parameters),
            "accepts_phase8_layout": "layout" in transition_parameters,
            "accepts_cloned_source_state": "source_state" in transition_parameters,
            "accepts_disturbance_state": "disturbance_state" in transition_parameters,
            "accepts_dynamic_obstacle_state": (
                "dynamic_obstacle_state" in transition_parameters
            ),
        },
        "source_trajectory_bindings": {
            source_class: None for source_class in SOURCE_CLASSES
        },
    }


def build_phase9_canary_audit(
    root: Path,
    manifest: Mapping[str, object],
) -> Dict[str, object]:
    """Attempt the frozen prefix and stop on the first fatal binding defect."""
    selection = select_canonical_canary(manifest)
    source_by_id = {
        item["job_id"]: item for item in manifest["source_episode_jobs"]
    }
    attempted_job = source_by_id[selection["source_episode_job_ids"][0]]
    first_attempt = _attempt_actual_source_job(attempted_job)
    infrastructure_retry = _attempt_actual_source_job(attempted_job)
    retry_identical = first_attempt == infrastructure_retry
    fatal = (
        first_attempt["exception_type"] == "AttributeError"
        and "ScenarioLayout" in str(first_attempt["exception_message"])
        and "start_center" in str(first_attempt["exception_message"])
    )
    binding = _execution_binding_evidence()
    fatal = fatal and not binding["legacy_closed_loop_runtime"]["compact_supported"]
    remaining = (
        len(selection["source_episode_job_ids"]) - 1
        + len(selection["candidate_replica_job_ids"])
        + 1
    )
    document: Dict[str, object] = {
        "schema_version": PHASE9_CANARY_AUDIT_SCHEMA_VERSION,
        "protocol_reference_id": PROTOCOL_REFERENCE_ID,
        "protocol_references": manifest["protocol_references"],
        "job_manifest_sha256": manifest["job_manifest_sha256"],
        "selection": selection,
        "attempts": [first_attempt, infrastructure_retry],
        "infrastructure_retry": {
            "performed": True,
            "same_job_id": True,
            "same_seed": True,
            "same_input_configuration": True,
            "byte_identical_deterministic_result": retry_identical,
        },
        "execution_binding_evidence": binding,
        "fatal_findings": [{
            "code": FATAL_BINDING_CODE,
            "confirmed": fatal,
            "classification": "infrastructure_generation_implementation_failure",
            "explanation": (
                "The Phase 8 ScenarioLayout cannot enter the repository's only "
                "full decentralized closed-loop harness, and that harness is "
                "limited to KEEP/LINE rather than the frozen COMPACT/LINE scope. "
                "The Phase 7 transition fixture has no scenario or cloned-state "
                "interface, and no executable S0-S5 source bindings exist."
            ),
            "repair_scope_assessment": (
                "A repair would require defining a Phase 8 geometry compiler, "
                "six source-policy executions, dynamic/communication state "
                "semantics, and a COMPACT/LINE scenario runtime. Those are new "
                "scientific execution semantics, not a local Phase 9 defect fix."
            ),
        }],
        "corrections_applied": [{
            "correction_id": "CANARY-SELECTION-001",
            "defect": (
                "The initial lexicographic constrained prefix covered four "
                "study/split namespaces but selected N=12 for all four."
            ),
            "repair": (
                "Add the first identity-ordered nonsealed Study A train source "
                "job whose team size differs from the existing prefix."
            ),
            "scientific_inputs_changed": False,
            "budget_changed": False,
            "seed_changed": False,
            "outcome_or_label_inspected": False,
        }],
        "canary_status": "FAIL_FATAL_EXECUTION_BINDING" if fatal else "FAIL_UNKNOWN",
        "abort_generation": True,
        "scientific_source_episodes_completed": 0,
        "scientific_candidate_replicas_completed": 0,
        "recoverability_records_emitted": 0,
        "residual_records_emitted": 0,
        "selected_jobs_not_run_due_fatal_canary": remaining,
        "normal_completion_observed": False,
        "semantic_failure_observed": False,
        "resume_behavior_verified": False,
        "interrupted_job_recovery_verified": False,
        "counterfactual_matching_verified": False,
        "residual_expert_locality_verified": False,
        "deterministic_sharding_verified": False,
        "clean_checkout_regeneration_verified": False,
        "study_a_n24_access_count": 0,
        "final_test_runtime_access_count": 0,
        "model_weights_retained": 0,
        "optimizer_states_retained": 0,
        "note": (
            "Downstream canary requirements are NOT_RUN, not passes. The frozen "
            "no-replacement rule prohibits substituting a diagnostic headroom "
            "label or another runtime for the failed source job."
        ),
    }
    return attach_canonical_hash(document, "canary_audit_sha256")


def write_phase9_canary_audit(
    root: Path,
    manifest: Mapping[str, object],
    destination: Path,
) -> Dict[str, object]:
    audit = build_phase9_canary_audit(root, manifest)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(audit, allow_nan=False, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )
    return audit
