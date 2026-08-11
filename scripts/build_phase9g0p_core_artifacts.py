#!/usr/bin/env python3
"""Build post-benchmark operational artifacts without enabling execution."""

from __future__ import annotations

import argparse
import json
import math
import shlex
from pathlib import Path
from typing import Any, Mapping

from rvt_swarm.phase8.common import attach_canonical_hash, sha256_document
from rvt_swarm.phase9g0r.compiler import (
    compile_recoverability_tasks,
    compile_residual_tasks,
)


SCIENTIFIC_SOURCE_COMMIT = "8cf64481cd17b2c44f7007d3722a8110e53cae46"
EXECUTION_COMMIT = "6818d8aa07aeb55a43dc42741499d9a24d540332"
PRODUCTION_IMAGE = "sha256:88ecf1aac7cd95b5ba50811950090c13f78362274e5c5cdaeafaafde29a115f4"
QUALIFIED_BASE_IMAGE = "sha256:5e13c21aaa20f2ac02eff36172aea467720b9c925d13882708e3e90686655d9c"
ADDENDUM_SHA256 = "523d865cf04b7a5bd2a9cec8cb9a105fd5ef1f1476f6acec34e8cd47cf0dcad0"
PROVENANCE_ROOT = "452ea2d37b8a9b09db88f337423bc6ee9261863ca22fe609293fa11e2acb486c"
JOB_MANIFEST_SHA256 = "801fe4e2bd694da0dda7c310226906e59d9bc5435d657fab2e3f132432aa2dc3"
ROW_BINDING_SHA256 = "90ebdba981997ea43176d5ab49c6ad72306445d6054b5ce742cfad3abfebb142"
BASE_COMMAND_PLAN_SHA256 = "473fc5243e3a11afbb44df868a0d3c814f7e534bb57439b85a2e79d27c4856f0"


def _load(path: Path, field: str) -> Mapping[str, Any]:
    document = json.loads(path.read_text(encoding="ascii"))
    expected = str(document.get(field, ""))
    body = dict(document)
    body.pop(field, None)
    if len(expected) != 64 or sha256_document(body) != expected:
        raise RuntimeError(f"canonical artifact hash mismatch: {path}")
    return document


def _write(path: Path, body: Mapping[str, Any], field: str) -> str:
    document = attach_canonical_hash(dict(body), field)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(document, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )
    return str(document[field])


def _chunk_entry(document: Mapping[str, Any]) -> Mapping[str, Any]:
    return {
        "workers": int(document["workers"]),
        "chunk_size_atomic_units": int(document["chunk_size_atomic_units"]),
        "wall_seconds": float(document["wall_seconds"]),
        "atomic_units_per_second": float(
            document["throughput"]["atomic_units_per_second"]
        ),
        "scheduler_parent_overhead_seconds": float(
            document["scheduler_parent_overhead_seconds"]
        ),
        "chunk_runtime_seconds": document["chunk_runtime_seconds"],
        "peak_aggregate_rss_upper_bound_bytes": int(
            document["memory"]["peak_aggregate_rss_upper_bound_bytes"]
        ),
        "load_balance_maximum_to_mean_worker_load_ratio": float(
            document["load_balance"]["maximum_to_mean_worker_load_ratio"]
        ),
        "writer_throughput_per_second": float(document["throughput"][
            "writer_transactions_per_second"
            if document["branch"] == "recoverability"
            else "writer_attempts_per_second"
        ]),
        "resume_granularity_atomic_units": int(document["chunk_size_atomic_units"]),
        "retry_blast_radius_atomic_units": int(document["chunk_size_atomic_units"]),
        "scientific_semantic_digest": str(document["scientific_semantic_digest"]),
        "raw_target_result_sha256": str(document["phase9g0p_benchmark_result_sha256"]),
    }


def _task_counts(root: Path) -> Mapping[str, Any]:
    result: dict[str, Any] = {}
    for study in ("study_a_zero_shot", "study_b_with_n24"):
        for split in ("train", "validation"):
            key = f"{study}/{split}"
            recoverability = compile_recoverability_tasks(root, study=study, split=split)
            residual = compile_residual_tasks(root, study=study, split=split)
            result[key] = {
                "source_episodes": len(residual),
                "recoverability_events": len(recoverability),
                "candidate_aggregates": 2 * len(recoverability),
                "replica_executions": sum(
                    2 * task.replicas_per_candidate for task in recoverability
                ),
                "recoverability_robot_candidate_row_capacity": sum(
                    2 * task.source.team_size for task in recoverability
                ),
                "residual_robot_episodes": sum(
                    task.source.team_size for task in residual
                ),
                "residual_retained_state_strict_upper_bound": sum(
                    task.source.team_size * 16 for task in residual
                ),
            }
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--chunk-root", type=Path, required=True)
    parser.add_argument("--failure-resume", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    results = root / "results/rvt_fd24"
    benchmark_root = results / "phase9g0p_benchmarks"
    worker_scaling = _load(
        benchmark_root / "worker_scaling_target_v1.json",
        "phase9g0p_worker_scaling_sha256",
    )
    chunks: dict[str, list[Mapping[str, Any]]] = {
        "recoverability": [], "residual": [],
    }
    for branch, workers, values in (
        ("recoverability", 12, (1, 2, 4)),
        ("residual", 8, (1, 2, 3)),
    ):
        for chunk in values:
            document = _load(
                args.chunk_root / f"{branch}_w{workers}_c{chunk}.json",
                "phase9g0p_benchmark_result_sha256",
            )
            chunks[branch].append(_chunk_entry(document))
        if len({item["scientific_semantic_digest"] for item in chunks[branch]}) != 1:
            raise RuntimeError(f"{branch} chunking changed scientific semantics")
    chunk_summary = {
        "schema_version": "rvt-phase9g0p-chunk-scaling/v1",
        "chunk_matrix_predeclaration_sha256": (
            "d5ba4204842f1d20c013323ed4de2d09bf6b166ec4b6f9c3d8cb8fa888b0d678"
        ),
        "recoverability": {
            "entries": chunks["recoverability"],
            "selected_chunk_size_atomic_units": 1,
            "selection_reason": (
                "chunk=1 has maximum throughput, best load balance, smallest retry "
                "blast radius and finest resume granularity"
            ),
            "semantic_digest_equal_all_chunks": True,
        },
        "residual": {
            "entries": chunks["residual"],
            "selected_chunk_size_atomic_units": 1,
            "selection_reason": (
                "chunk=1 has maximum throughput, lower p95/max chunk runtime, "
                "better load balance and minimum retry blast radius"
            ),
            "semantic_digest_equal_all_chunks": True,
        },
        "official_staging_writes": 0,
    }
    chunk_hash = _write(
        benchmark_root / "chunk_scaling_target_v1.json",
        chunk_summary,
        "phase9g0p_chunk_scaling_sha256",
    )

    failure = _load(
        args.failure_resume, "phase9g0p_failure_resume_qualification_sha256"
    )
    if failure["failures"] != 0:
        raise RuntimeError("failure/resume qualification did not pass")
    failure_hash = _write(
        benchmark_root / "failure_resume_target_v1.json",
        {key: value for key, value in failure.items()
         if key != "phase9g0p_failure_resume_qualification_sha256"},
        "phase9g0p_failure_resume_qualification_sha256",
    )

    rec_selected = _load(
        args.chunk_root / "recoverability_w12_c1.json",
        "phase9g0p_benchmark_result_sha256",
    )
    res_selected = _load(
        args.chunk_root / "residual_w8_c1.json",
        "phase9g0p_benchmark_result_sha256",
    )
    rec_max = float(rec_selected["atomic_unit_latency_seconds"]["max"])
    res_max = float(res_selected["atomic_unit_latency_seconds"]["max"])
    timeout = {
        "schema_version": "rvt-phase9g0p-timeout-derivation/v1",
        "recoverability": {
            "observed_p95_atomic_seconds": rec_selected["atomic_unit_latency_seconds"]["p95"],
            "observed_max_atomic_seconds": rec_max,
            "observed_p95_writer_seconds": rec_selected["stage_seconds"]["writer"]["p95"],
            "frozen_long_horizon_and_three_replica_cases_present": True,
            "formula": "max(60 s floor, ceil(3 * observed_max / 60 s) * 60 s)",
            "infrastructure_timeout_seconds": max(60.0, math.ceil(3 * rec_max / 60) * 60.0),
        },
        "residual": {
            "observed_p95_atomic_seconds": res_selected["atomic_unit_latency_seconds"]["p95"],
            "observed_max_atomic_seconds": res_max,
            "observed_p95_writer_seconds": res_selected["stage_seconds"]["writer"]["p95"],
            "frozen_long_horizon_cases_present": True,
            "formula": "max(300 s floor, ceil(2.5 * observed_max / 60 s) * 60 s)",
            "infrastructure_timeout_seconds": max(300.0, math.ceil(2.5 * res_max / 60) * 60.0),
        },
        "timeout_is_infrastructure_only": True,
        "timeout_never_maps_to_scientific_disposition": True,
        "legacy_1200_seconds_inherited": False,
    }
    if timeout["recoverability"]["infrastructure_timeout_seconds"] != 60.0:
        raise RuntimeError("recoverability timeout derivation changed")
    if timeout["residual"]["infrastructure_timeout_seconds"] != 360.0:
        raise RuntimeError("residual timeout derivation changed")
    timeout_hash = _write(
        results / "phase9g0p_timeout_derivation_v1.json",
        timeout,
        "phase9g0p_timeout_derivation_sha256",
    )

    task_counts = _task_counts(root)
    total = {
        key: sum(int(value[key]) for value in task_counts.values())
        for key in next(iter(task_counts.values()))
    }
    rec_storage = rec_selected["storage"]
    res_storage = res_selected["storage"]
    rec_rows_bytes = (
        total["recoverability_robot_candidate_row_capacity"]
        * float(rec_storage["recoverability_row_bytes"]["mean"])
    )
    rec_audit_bytes = (
        total["candidate_aggregates"]
        * float(rec_storage["candidate_aggregate_audit_bytes"]["mean"])
        + total["replica_executions"]
        * float(rec_storage["replica_audit_bytes"]["mean"])
        + total["recoverability_events"]
        * float(rec_storage["pair_transaction_metadata_bytes"]["mean"])
    )
    residual_attempts = total["residual_retained_state_strict_upper_bound"]
    labeled_ratio = (
        res_selected["counts"]["labeled_rows"]
        / res_selected["counts"]["retained_state_units"]
    )
    projected_labeled = round(residual_attempts * labeled_ratio)
    projected_noeligible = residual_attempts - projected_labeled
    residual_rows_bytes = projected_labeled * float(
        res_storage["residual_row_bytes"]["mean"]
    )
    residual_audit_bytes = (
        residual_attempts
        * float(res_storage["residual_nine_candidate_sidecar_bytes"]["mean"])
        + projected_noeligible
        * float(res_storage["no_eligible_audit_bytes"]["mean"])
    )
    rec_cpu_hours = (
        float(rec_selected["worker_cpu_seconds"])
        / rec_selected["counts"]["candidate_aggregates"]
        * total["candidate_aggregates"] / 3600
    )
    res_cpu_hours = (
        float(res_selected["worker_cpu_seconds"])
        / res_selected["counts"]["retained_state_units"]
        * residual_attempts / 3600
    )
    res_direct_hours = (
        residual_attempts
        / float(res_selected["throughput"]["atomic_units_per_second"]) / 3600
    )
    res_balanced_hours = (
        res_cpu_hours / 8
        + float(res_selected["source_planning_seconds"])
        / res_selected["counts"]["source_episodes_planned"]
        * total["source_episodes"] / 8 / 3600
    )
    capacity = {
        "schema_version": "rvt-phase9g0p-storage-capacity/v1",
        "exact_authorized_task_counts_by_scope": task_counts,
        "exact_authorized_totals": total,
        "recoverability": {
            "profile_id": "PROFILE_RECOVERABILITY_V1",
            "projected_wall_hours": (
                total["candidate_aggregates"]
                / float(rec_selected["throughput"]["atomic_units_per_second"]) / 3600
            ),
            "projected_cpu_hours": rec_cpu_hours,
            "peak_ram_bytes": rec_selected["memory"]["peak_aggregate_rss_upper_bound_bytes"],
            "projected_dataset_bytes_at_row_capacity": round(rec_rows_bytes),
            "projected_audit_bytes": round(rec_audit_bytes),
            "staging_requirement_bytes_2x_plus_20_percent": math.ceil(
                (rec_rows_bytes + rec_audit_bytes) * 2.2
            ),
        },
        "residual": {
            "profile_id": "PROFILE_RESIDUAL_V2_V1",
            "retention_k": 16,
            "strict_retained_state_upper_bound": residual_attempts,
            "capacity_provisioning_attempt_projection": residual_attempts,
            "candidate_evaluations_upper_bound": residual_attempts * 9,
            "projected_labeled_rows_from_frozen_benchmark_ratio": projected_labeled,
            "projected_no_eligible_audits_from_frozen_benchmark_ratio": projected_noeligible,
            "projected_wall_hours_large_workload_cpu_balance": res_balanced_hours,
            "projected_wall_hours_direct_small_manifest_conservative": res_direct_hours,
            "projected_cpu_hours": res_cpu_hours,
            "peak_ram_bytes": res_selected["memory"]["peak_aggregate_rss_upper_bound_bytes"],
            "projected_dataset_bytes": round(residual_rows_bytes),
            "projected_audit_bytes": round(residual_audit_bytes),
            "staging_requirement_bytes_2x_plus_20_percent": math.ceil(
                (residual_rows_bytes + residual_audit_bytes) * 2.2
            ),
            "historical_536000_attempts_reused": False,
        },
        "index_and_manifest_bytes_are_negligible_relative_to_projected_records": True,
        "official_data_generated": False,
    }
    capacity_hash = _write(
        results / "phase9g0p_storage_capacity_v1.json",
        capacity,
        "phase9g0p_storage_capacity_sha256",
    )

    gpu = {
        "schema_version": "rvt-phase9g0p-gpu-execution-boundary/v1",
        "gpu": {
            "model": "NVIDIA RTX 5000 Ada Generation",
            "uuid": "GPU-262a5f7e-fa85-a213-98ed-2761941b4e9a",
            "container_nvidia_smi_visible": True,
            "production_torch_cuda_available": False,
            "production_torch_cuda_device_count": 0,
            "generation_utilization": "NONE",
        },
        "components": {
            "source_simulator": "CPU",
            "phase6_controller": "CPU",
            "local_safety_projection": "CPU",
            "transition_protocol": "CPU",
            "target_v4": "CPU",
            "recoverability_counterfactual_generation": "CPU",
            "residual_expert_v2_counterfactual_generation": "CPU",
            "ego_graph_construction": "CPU",
            "fd24_model_forward_during_generation": "NOT_EXECUTED",
            "future_fd24_training": "CUDA_PERMITTED_IN_SEPARATELY_QUALIFIED_TRAINING_IMAGE",
        },
        "recoverability_labels_are_simulator_target_v4_outputs_not_predictions": True,
        "residual_labels_are_frozen_expert_selector_target_outputs_not_model_predictions": True,
        "scientific_generation_path_moved_to_cuda": False,
    }
    gpu_hash = _write(
        results / "phase9g0p_gpu_execution_boundary_v1.json",
        gpu,
        "phase9g0p_gpu_execution_boundary_sha256",
    )

    h4 = {
        "schema_version": "rvt-phase9g0p-h4-operational-classification/v1",
        "classification": "H4_OPERATIONAL_RISK_BUT_FEASIBLE",
        "basis": {
            "strict_attempt_upper_bound": residual_attempts,
            "candidate_evaluation_upper_bound": residual_attempts * 9,
            "projected_wall_hours_range": [res_balanced_hours, res_direct_hours],
            "projected_cpu_hours": res_cpu_hours,
            "projected_staging_requirement_bytes": capacity["residual"][
                "staging_requirement_bytes_2x_plus_20_percent"
            ],
            "target_storage_available_bytes": 422363889664,
        },
        "risk": (
            "multi-week CPU-authoritative generation and heavy-tailed residual units"
        ),
        "feasibility_basis": (
            "qualified resume/idempotency, bounded RAM and storage, and no frozen "
            "scientific contract change required"
        ),
        "k_changed": False,
        "candidate_count_changed": False,
        "horizon_changed": False,
    }
    h4_hash = _write(
        results / "phase9g0p_h4_operational_classification_v1.json",
        h4,
        "phase9g0p_h4_operational_classification_sha256",
    )

    sequence = {
        "schema_version": "rvt-phase9g0p-study-sequence-audit/v1",
        "contamination_risk": (
            "human-visible Study B N24 outcomes before Study A checkpoint freeze "
            "could influence Study A zero-shot decisions"
        ),
        "required_sequence": [
            "Study A train/validation generation",
            "Study A model selection and checkpoint freeze",
            "Study A N24 zero-shot evaluation and immutable recording",
            "Study B train/validation generation or human-visible N24 inspection",
            "final-test remains separately sealed",
        ],
        "study_a_n24_status": "SEALED_NOT_AUTHORIZED",
        "study_b_status": "HELD_SEQUENCE_NOT_AUTHORIZED",
        "final_test_status": "SEALED_NOT_AUTHORIZED",
        "scientific_scope_changed": False,
    }
    sequence_hash = _write(
        results / "phase9g0p_study_sequence_audit_v1.json",
        sequence,
        "phase9g0p_study_sequence_audit_sha256",
    )

    contract = {
        "schema_version": "rvt-phase9g0p-operational-production-contract/v2",
        "profiles": {
            "recoverability": {
                "profile_id": "PROFILE_RECOVERABILITY_V1",
                "workers": 12,
                "numeric_threads": 1,
                "chunk_size_atomic_units": 1,
                "infrastructure_timeout_seconds": 60.0,
                "semantic_digest": chunks["recoverability"][0]["scientific_semantic_digest"],
            },
            "residual": {
                "profile_id": "PROFILE_RESIDUAL_V2_V1",
                "workers": 8,
                "numeric_threads": 1,
                "chunk_size_atomic_units": 1,
                "infrastructure_timeout_seconds": 360.0,
                "semantic_digest": chunks["residual"][0]["scientific_semantic_digest"],
            },
        },
        "common": {
            "target_host": "100.71.102.9",
            "wsl_distribution": "Ubuntu-24.04",
            "qualified_base_image": QUALIFIED_BASE_IMAGE,
            "production_image": PRODUCTION_IMAGE,
            "execution_code_commit": EXECUTION_COMMIT,
            "scientific_source_commit": SCIENTIFIC_SOURCE_COMMIT,
            "scientific_addendum_sha256": ADDENDUM_SHA256,
            "recoverability_row_binding_sha256": ROW_BINDING_SHA256,
            "writer": "rvt_swarm.phase9g0r.writer.CanonicalGenerationWriter",
            "writer_parent_process_only": True,
            "resume": "replay incomplete atomic units; canonical duplicates are no-ops",
            "retry": "one byte-identical candidate retry plus durable run-level resume",
            "staging": "branch/study/split scoped OFFICIAL_STAGING namespace",
            "finalization": "separate post-generation validated operation; direct FINAL prohibited",
            "gpu_generation": False,
        },
        "evidence": {
            "worker_scaling_sha256": worker_scaling["phase9g0p_worker_scaling_sha256"],
            "chunk_scaling_sha256": chunk_hash,
            "timeout_derivation_sha256": timeout_hash,
            "failure_resume_sha256": failure_hash,
            "storage_capacity_sha256": capacity_hash,
            "gpu_execution_boundary_sha256": gpu_hash,
            "h4_classification_sha256": h4_hash,
        },
        "official_execution_authorized": False,
    }
    contract_hash = _write(
        results / "phase9g0p_operational_production_contract_v2.json",
        contract,
        "phase9g0p_operational_contract_sha256",
    )

    base_plan = _load(
        results / "phase9_official_command_plan_v2.json",
        "phase9_official_command_plan_sha256",
    )
    if base_plan["phase9_official_command_plan_sha256"] != BASE_COMMAND_PLAN_SHA256:
        raise RuntimeError("base Command Plan V2 changed")
    authorization_scopes = []
    launches = []
    for launch in base_plan["launch_specifications"]:
        command_id = str(launch["command_id"])
        branch = str(launch["branch"])
        profile = contract["profiles"][branch]
        scope = {
            "schema_version": "rvt-phase9g0p-authorization-scope-proposal/v1",
            "broad_authorization": False,
            "official_generation_execution_authorized": False,
            "status": "PROPOSED_NOT_ENABLED",
            "binding": {
                "study": launch["study"], "split": launch["split"],
                "branch": branch, "source_commit": SCIENTIFIC_SOURCE_COMMIT,
                "docker_image": PRODUCTION_IMAGE,
                "scientific_addendum_sha256": ADDENDUM_SHA256,
                "generation_provenance_root": PROVENANCE_ROOT,
            },
        }
        scope_name = f"phase9g0p_authorization_scope_proposal_{command_id}_v1.json"
        scope_hash = _write(
            results / scope_name, scope, "phase9_authorization_scope_sha256"
        )
        authorization_scopes.append({
            "command_id": command_id,
            "artifact": scope_name,
            "sha256": scope_hash,
            "enabled": False,
        })
        profile_path = "/rvt-data/authorization/phase9g0p_operational_production_contract_v2.json"
        scope_path = f"/rvt-data/authorization/{scope_name}"
        writer_root = f"/rvt-data/staging/{command_id}"
        command = [
            "python", "/opt/rvt/scripts/run_phase9_official_generation.py",
            "--root", "/opt/rvt", "--study", str(launch["study"]),
            "--split", str(launch["split"]), "--branch", branch,
            "--mode", "OFFICIAL_STAGING", "--writer-root", writer_root,
            "--source-commit", SCIENTIFIC_SOURCE_COMMIT,
            "--docker-image", PRODUCTION_IMAGE,
            "--job-manifest-sha256", JOB_MANIFEST_SHA256,
            "--scientific-addendum-sha256", ADDENDUM_SHA256,
            "--generation-provenance-root", PROVENANCE_ROOT,
            "--authorization-scope-sha256", scope_hash,
            "--authorization-scope", scope_path,
            "--run-id", f"OWNER_MUST_ASSIGN_{command_id}",
            "--operational-profile", profile_path,
            "--operational-profile-sha256", contract_hash,
            "--workers", str(profile["workers"]),
            "--numeric-threads", str(profile["numeric_threads"]),
            "--chunk-size", str(profile["chunk_size_atomic_units"]),
            "--infrastructure-timeout-seconds", str(
                profile["infrastructure_timeout_seconds"]
            ),
        ]
        launches.append({
            "command_id": command_id,
            "study": launch["study"], "split": launch["split"],
            "branch": branch, "task_count": launch["task_count"],
            "scientific_selector_unchanged": True,
            "scientific_source_commit": SCIENTIFIC_SOURCE_COMMIT,
            "production_image": PRODUCTION_IMAGE,
            "operational_profile_id": profile["profile_id"],
            "writer_namespace": writer_root,
            "authorization_scope_artifact": scope_name,
            "authorization_scope_sha256": scope_hash,
            "execution_authorized": False,
            "executed": False,
            "official_command": shlex.join(command),
            "resolution_command": shlex.join([*command, "--resolve-only"]),
        })
    authorization = {
        "schema_version": "rvt-phase9g0p-scoped-authorization-proposal/v1",
        "statuses": {
            "RECOVERABILITY_GENERATION": "PROPOSED_SCOPED_NOT_AUTHORIZED",
            "RESIDUAL_V2_GENERATION": "PROPOSED_SCOPED_NOT_AUTHORIZED",
            "STUDY_A_TRAIN_VALIDATION": "PROPOSED_SCOPED_NOT_AUTHORIZED",
            "STUDY_A_N24_ZERO_SHOT": "SEALED_NOT_AUTHORIZED",
            "STUDY_B": "HELD_SEQUENCE_NOT_AUTHORIZED",
            "FINAL_TEST": "SEALED_NOT_AUTHORIZED",
        },
        "broad_authorization": False,
        "scope_proposals": authorization_scopes,
        "enabled_scope_count": 0,
        "study_sequence_audit_sha256": sequence_hash,
    }
    authorization_hash = _write(
        results / "phase9g0p_scoped_authorization_proposal_v1.json",
        authorization,
        "phase9g0p_scoped_authorization_proposal_sha256",
    )
    command_addendum = {
        "schema_version": "rvt-phase9-official-command-plan/v2-operational-addendum/v1",
        "base_command_plan_sha256": BASE_COMMAND_PLAN_SHA256,
        "additive_only": True,
        "scientific_selectors_changed": False,
        "operational_contract_sha256": contract_hash,
        "production_image": PRODUCTION_IMAGE,
        "launch_specifications": launches,
        "executable_command_count": len(launches),
        "all_commands_prepared": True,
        "authorization_proposal_sha256": authorization_hash,
        "authorization_remains_false": True,
        "executed": False,
        "study_a_n24_command": "NOT_CREATED_SEALED",
        "final_test_command": "NOT_CREATED_SEALED",
    }
    plan_hash = _write(
        results / "phase9_official_command_plan_v2_operational_addendum_v1.json",
        command_addendum,
        "phase9g0p_command_plan_operational_addendum_sha256",
    )
    print(json.dumps({
        "chunk_scaling": chunk_hash,
        "failure_resume": failure_hash,
        "timeout": timeout_hash,
        "capacity": capacity_hash,
        "gpu": gpu_hash,
        "h4": h4_hash,
        "sequence": sequence_hash,
        "operational_contract": contract_hash,
        "authorization_proposal": authorization_hash,
        "command_plan_addendum": plan_hash,
        "production_image": PRODUCTION_IMAGE,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
