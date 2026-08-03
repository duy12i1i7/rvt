"""Authoritative deterministic Phase 9 scientific job manifest."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Dict, Mapping, Sequence, Tuple

from ..phase8.common import attach_canonical_hash, sha256_document
from ..phase8.splits import load_nonfinal_split_manifest
from ..phase9.common import EXPERIMENT_PROTOCOL_SHA256
from ..phase9b.budget import (
    COUNTERFACTUAL_REPLICAS_BY_FAMILY,
    DATASET_BUDGETS,
    STUDY_A_N24_EVALUATION,
    DatasetBudgetSpec,
)
from ..phase9b.identity import (
    CandidateReplicaIdentity,
    DecisionEventIdentity,
    SourceEpisodeIdentity,
    build_dataset_cells,
    derive_generation_seed,
    event_slot_count,
    map_event_slots,
    reject_duplicate_semantic_identities,
    source_episode_identities,
)
from ..runtime_configuration import RuntimeConfig
from ..topology_registry import COMPACT, LINE


PHASE9_JOB_MANIFEST_SCHEMA_VERSION = "rvt-phase9-job-manifest/v1"
PHASE9_EXECUTION_GENERATOR_VERSION = "rvt-phase9-execution-planner/v1"
PHASE9_EXECUTION_SOURCE_COMMIT = "20a7541a4ae946c2ca051cde0c353c396d2c1241"
GENERATION_BUDGET_SHA256 = (
    "3853b8ad4484d733de9be7d0e27bf273f33e14054f3089f6b5454cc17815846e"
)
COMPOSITE_GENERATION_PROTOCOL_SHA256 = (
    "d928a7f614434b4d99395c5b75398b6277ec407cbf206e332a621f553022be57"
)
PROTOCOL_REFERENCE_ID = "phase8-plus-phase9b-frozen"
_CANDIDATES: Tuple[int, int] = (COMPACT, LINE)


def _load_layout_lookup(root: Path, split: str) -> Dict[str, Mapping[str, object]]:
    manifest = load_nonfinal_split_manifest(
        root / f"results/rvt_fd24/splits/{split}_layouts.json"
    )
    return {
        str(record["geometry_sha256"]): record
        for record in manifest["layout_records"]
    }


def _protocol_reference() -> Dict[str, str]:
    return {
        "phase8_experiment_protocol_sha256": EXPERIMENT_PROTOCOL_SHA256,
        "phase9b_generation_budget_sha256": GENERATION_BUDGET_SHA256,
        "composite_generation_protocol_sha256": (
            COMPOSITE_GENERATION_PROTOCOL_SHA256
        ),
        "source_commit": PHASE9_EXECUTION_SOURCE_COMMIT,
    }


def _source_seeds(identity: SourceEpisodeIdentity) -> Dict[str, int]:
    cell = identity.cell
    common = {
        "study": cell.study,
        "split": cell.split,
        "scenario_family": cell.family_id,
        "layout_sha256": cell.layout_sha256,
        "team_size": cell.team_size,
        "source_class": identity.source_class,
        "episode_index": identity.episode_index,
    }
    return {
        namespace: derive_generation_seed(namespace, **common)
        for namespace in (
            "initial_condition",
            "communication",
            "dynamic_obstacle",
            "data_sampling",
        )
    }


def _replica_seeds(
    identity: CandidateReplicaIdentity,
) -> Dict[str, int]:
    source = identity.decision_event.source_episode
    cell = source.cell
    common = {
        "study": cell.study,
        "split": cell.split,
        "scenario_family": cell.family_id,
        "layout_sha256": cell.layout_sha256,
        "team_size": cell.team_size,
        "source_class": source.source_class,
        "episode_index": source.episode_index,
        "event_slot_index": identity.decision_event.event_slot_index,
        "replica_index": identity.replica_index,
    }
    return {
        # The approved job seed includes candidate identity. The matched
        # disturbance seed deliberately does not, because Phase 8 requires the
        # two candidates in one replica pair to receive the same realization.
        "candidate_replica_job_seed": derive_generation_seed(
            "counterfactual_rollout",
            candidate_topology=identity.candidate_topology,
            **common,
        ),
        "matched_disturbance_seed": derive_generation_seed(
            "counterfactual_rollout",
            candidate_topology=None,
            **common,
        ),
    }


def _residual_job_id(spec: DatasetBudgetSpec, cell: object) -> str:
    return "/".join((
        "rvt-generation-job-identity/v1",
        "residual_cell",
        spec.study,
        spec.split,
        cell.family_id,
        cell.layout_sha256,
        f"N{cell.team_size}",
    ))


def _accounting(planned: int, executable: int | None = None) -> Dict[str, int]:
    return {
        "planned_slots": int(planned),
        "executable_jobs": int(planned if executable is None else executable),
        "completed_jobs": 0,
        "scientifically_valid_outcomes": 0,
        "emitted_training_records": 0,
        "unavailable_slots": 0,
        "infrastructure_failures": 0,
        "semantic_task_failures": 0,
    }


def build_phase9_job_manifest(root: Path) -> Dict[str, object]:
    """Build every frozen source, event, candidate-replica and residual job."""
    root = root.resolve()
    layouts = {
        "train": _load_layout_lookup(root, "train"),
        "validation": _load_layout_lookup(root, "validation"),
    }
    protocol_ref = _protocol_reference()
    source_jobs = []
    event_jobs = []
    replica_jobs = []
    residual_jobs = []
    source_ids = []
    event_ids = []
    replica_ids = []
    residual_ids = []
    source_counts = Counter()
    family_events = Counter()

    for spec in DATASET_BUDGETS:
        cells = build_dataset_cells(root, spec.dataset_id)
        for cell in cells:
            layout = layouts[spec.layout_source_split][cell.layout_sha256]
            geometry = layout["geometry"]
            horizon = float(geometry["episode_horizon_seconds"])
            control_period = RuntimeConfig.for_team_size(
                cell.team_size
            ).physical.control_period_seconds
            residual_id = _residual_job_id(spec, cell)
            residual_ids.append(residual_id)
            residual_jobs.append({
                "job_id": residual_id,
                "protocol_reference_id": PROTOCOL_REFERENCE_ID,
                "dataset_id": spec.dataset_id,
                "study": spec.study,
                "split": spec.split,
                "family_id": cell.family_id,
                "layout_id": layout["layout_id"],
                "layout_sha256": cell.layout_sha256,
                "team_size": cell.team_size,
                "planned_dense_record_quota": spec.dense_records_per_cell,
                "selection_commitment_sha256": sha256_document({
                    "protocol": protocol_ref,
                    "cell_sha256": cell.canonical_hash(),
                    "quota": spec.dense_records_per_cell,
                }),
                "sealed": spec.dataset_id == STUDY_A_N24_EVALUATION,
                "status": "PLANNED",
            })
            for source in source_episode_identities(cell, cells):
                source_id = source.job_id()
                source_ids.append(source_id)
                source_counts[(spec.dataset_id, source.source_class)] += 1
                count = event_slot_count(cell, source.source_class)
                slots = map_event_slots(
                    horizon_seconds=horizon,
                    control_period_seconds=control_period,
                    slot_count=count,
                )
                source_jobs.append({
                    "job_id": source_id,
                    "protocol_reference_id": PROTOCOL_REFERENCE_ID,
                    "dataset_id": spec.dataset_id,
                    "study": spec.study,
                    "split": spec.split,
                    "layout_source_split": spec.layout_source_split,
                    "family_id": cell.family_id,
                    "layout_id": layout["layout_id"],
                    "layout_sha256": cell.layout_sha256,
                    "team_size": cell.team_size,
                    "source_class": source.source_class,
                    "episode_index": source.episode_index,
                    "episode_horizon_seconds": horizon,
                    "control_period_seconds": control_period,
                    "communication_condition": geometry["communication_profile"],
                    "initial_topology_id": geometry["initial_topology_id"],
                    "seeds": _source_seeds(source),
                    "planned_event_slots": count,
                    "sealed": spec.dataset_id == STUDY_A_N24_EVALUATION,
                    "status": "PLANNED",
                })
                for slot in slots:
                    event = DecisionEventIdentity(source, slot.slot_index)
                    event_id = event.job_id()
                    event_ids.append(event_id)
                    family_events[(spec.dataset_id, cell.family_id)] += 1
                    replicas = COUNTERFACTUAL_REPLICAS_BY_FAMILY[cell.family_id]
                    event_jobs.append({
                        "job_id": event_id,
                        "protocol_reference_id": PROTOCOL_REFERENCE_ID,
                        "source_episode_job_id": source_id,
                        "dataset_id": spec.dataset_id,
                        "study": spec.study,
                        "split": spec.split,
                        "family_id": cell.family_id,
                        "layout_sha256": cell.layout_sha256,
                        "team_size": cell.team_size,
                        "source_class": source.source_class,
                        "event_slot_index": slot.slot_index,
                        "scheduled_normalized_time": slot.normalized_horizon_position,
                        "scheduled_physical_time_seconds": slot.requested_timestamp_seconds,
                        "resolved_control_step": slot.scheduled_control_step,
                        "resolved_timestamp_seconds": slot.scheduled_timestamp_seconds,
                        "availability": "PENDING_SOURCE_EXECUTION",
                        "source_episode_state_sha256": None,
                        "lifecycle_state": "PENDING_SOURCE_EXECUTION",
                        "source_topology": "PENDING_SOURCE_EXECUTION",
                        "candidate_topologies": list(_CANDIDATES),
                        "replicas_per_candidate": replicas,
                        "planned_recoverability_record_capacity": (
                            2 * cell.team_size
                        ),
                        "sealed": spec.dataset_id == STUDY_A_N24_EVALUATION,
                        "status": "PLANNED",
                    })
                    for candidate in _CANDIDATES:
                        for replica_index in range(replicas):
                            replica = CandidateReplicaIdentity(
                                event, candidate, replica_index
                            )
                            replica_id = replica.job_id()
                            replica_ids.append(replica_id)
                            replica_jobs.append({
                                "job_id": replica_id,
                                "protocol_reference_id": PROTOCOL_REFERENCE_ID,
                                "decision_event_job_id": event_id,
                                "dataset_id": spec.dataset_id,
                                "study": spec.study,
                                "split": spec.split,
                                "family_id": cell.family_id,
                                "layout_sha256": cell.layout_sha256,
                                "team_size": cell.team_size,
                                "candidate_topology": candidate,
                                "replica_index": replica_index,
                                "seeds": _replica_seeds(replica),
                                "sealed": (
                                    spec.dataset_id == STUDY_A_N24_EVALUATION
                                ),
                                "status": "PLANNED",
                            })

    reject_duplicate_semantic_identities(source_ids)
    reject_duplicate_semantic_identities(event_ids)
    reject_duplicate_semantic_identities(replica_ids)
    reject_duplicate_semantic_identities(residual_ids)

    planned = {
        "source_episode_slots": len(source_jobs),
        "decision_event_slots": len(event_jobs),
        "candidate_replica_rollout_slots": len(replica_jobs),
        "recoverability_record_capacity": sum(
            int(item["planned_recoverability_record_capacity"])
            for item in event_jobs
        ),
        "dense_residual_record_capacity": sum(
            int(item["planned_dense_record_quota"])
            for item in residual_jobs
        ),
        "residual_cell_jobs": len(residual_jobs),
    }
    expected = {
        "source_episode_slots": 3120,
        "decision_event_slots": 15300,
        "candidate_replica_rollout_slots": 42840,
        "recoverability_record_capacity": 332900,
        "dense_residual_record_capacity": 536000,
        "residual_cell_jobs": 340,
    }
    if planned != expected:
        raise ValueError(f"job manifest totals differ: {planned!r}")

    document: Dict[str, object] = {
        "schema_version": PHASE9_JOB_MANIFEST_SCHEMA_VERSION,
        "generator_version": PHASE9_EXECUTION_GENERATOR_VERSION,
        "protocol_reference_id": PROTOCOL_REFERENCE_ID,
        "protocol_references": {PROTOCOL_REFERENCE_ID: protocol_ref},
        "ordering_contract": (
            "canonical dataset order, canonical cell hash, frozen source order, "
            "event slot, candidate order [COMPACT,LINE], replica index"
        ),
        "identity_order_independent": True,
        "duplicate_semantic_jobs_rejected": True,
        "final_test_jobs_present": False,
        "study_a_n24_policy": {
            "generation_namespace": "study_a_n24_eval_sealed",
            "sealed": True,
            "training_visible": False,
            "checkpoint_selection_visible": False,
            "phase9_record_access_count": 0,
        },
        "planned_capacity": planned,
        "execution_accounting": {
            "source_episodes": _accounting(planned["source_episode_slots"]),
            "decision_events": _accounting(planned["decision_event_slots"]),
            "candidate_replicas": _accounting(
                planned["candidate_replica_rollout_slots"]
            ),
            "recoverability_records": _accounting(
                planned["recoverability_record_capacity"], executable=0
            ),
            "dense_residual_records": _accounting(
                planned["dense_residual_record_capacity"], executable=0
            ),
            "residual_cells": _accounting(planned["residual_cell_jobs"]),
        },
        "validation_summary": {
            "source_class_counts_by_dataset": {
                dataset_id: {
                    source_class: source_counts[(dataset_id, source_class)]
                    for source_class in sorted({
                        key[1] for key in source_counts if key[0] == dataset_id
                    })
                }
                for dataset_id in sorted({key[0] for key in source_counts})
            },
            "decision_events_by_dataset_family": {
                dataset_id: {
                    family: family_events[(dataset_id, family)]
                    for family in sorted({
                        key[1] for key in family_events if key[0] == dataset_id
                    })
                }
                for dataset_id in sorted({key[0] for key in family_events})
            },
            "study_a_train_team_sizes": [5, 6, 8, 12, 16],
            "study_a_validation_team_sizes": [5, 6, 8, 12, 16],
            "study_a_n24_evaluation_team_sizes": [24],
            "study_b_train_and_validation_team_sizes": [5, 6, 8, 12, 16, 24],
        },
        "source_episode_jobs": source_jobs,
        "decision_event_jobs": event_jobs,
        "candidate_replica_jobs": replica_jobs,
        "residual_cell_jobs": residual_jobs,
    }
    return attach_canonical_hash(document, "job_manifest_sha256")


def write_phase9_job_manifest(root: Path, destination: Path) -> Dict[str, object]:
    manifest = build_phase9_job_manifest(root)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(
            manifest,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ) + "\n",
        encoding="ascii",
    )
    return manifest
