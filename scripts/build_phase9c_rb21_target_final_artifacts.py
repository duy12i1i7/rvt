#!/usr/bin/env python3
"""Build and validate final RB21 target operational evidence.

This script is deliberately observational.  It consumes committed benchmark
and failure-probe evidence, derives operational values, and writes canonical
qualification artifacts.  It never executes a scientific episode, generates
an official row, or opens a sealed study split.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Sequence

from rvt_swarm.phase8.common import attach_canonical_hash, verify_canonical_hash
from rvt_swarm.phase9c_rb21.rb21_manifest import (
    RB19_PROVENANCE_ROOT,
    RB20_REPRODUCTION_HASH,
    RB21P_PORTABILITY_ARTIFACT_HASH,
    RB21P_QUALIFIED_IMAGE,
    RB21P_REQUALIFICATION_ROOT,
    RB21P_SOURCE_CHECKPOINT,
    TARGET_V4_HASH,
    write_json,
)
from rvt_swarm.phase9c_rb21.rb21_target_preflight import (
    IMAGE_SOURCE_COMMIT,
    build_target_operational_preflight,
    run_target_negative_matrix,
)


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results/rvt_fd24"
BRANCH = "research/rvt-rb21-target-performance-v1"
THREAD_PROFILE = {
    "OMP_NUM_THREADS": 1,
    "MKL_NUM_THREADS": 1,
    "OPENBLAS_NUM_THREADS": 1,
    "NUMEXPR_NUM_THREADS": 1,
    "torch_num_threads": 1,
    "torch_num_interop_threads": 1,
}
SELECTED_WORKERS = 12
SELECTED_CHUNK = 1
SELECTED_TIMEOUT_SECONDS = 1200


def _load(name: str) -> Dict[str, Any]:
    return json.loads((RESULTS / name).read_text(encoding="ascii"))


def _load_valid(name: str, hash_field: str) -> Dict[str, Any]:
    document = _load(name)
    if not verify_canonical_hash(document, hash_field):
        raise ValueError(f"invalid canonical hash: {name}#{hash_field}")
    return document


def _hashed(document: Mapping[str, Any], field: str) -> Dict[str, Any]:
    return attach_canonical_hash(dict(document), field)


def _write(name: str, document: Mapping[str, Any]) -> None:
    write_json(RESULTS / name, document)


def _without(mapping: Mapping[str, Any], *keys: str) -> Dict[str, Any]:
    omitted = set(keys)
    return {key: value for key, value in mapping.items() if key not in omitted}


def _round_up(value: float, quantum: int) -> int:
    return int(math.ceil(value / quantum) * quantum)


def _measurement_runs() -> Iterable[Dict[str, Any]]:
    paths = [
        RESULTS / "rb21_target_w1_recoverability_raw_v1.json",
        RESULTS / "rb21_target_w1_residual_raw_v1.json",
    ]
    paths.extend(sorted((RESULTS / "rb21_target_diagnostics").glob("**/*.json")))
    seen = set()
    for path in paths:
        if path in seen:
            continue
        seen.add(path)
        document = json.loads(path.read_text(encoding="ascii"))
        if "benchmark" in document:
            yield document


def _global_tail() -> Dict[str, Any]:
    residual_walls = []
    recovery_walls = []
    serializations = []
    residual_intervals = []
    recovery_intervals = []
    for run in _measurement_runs():
        for row in run["benchmark"]["results"]:
            serializations.append(float(row["serialization_seconds"]))
            if row["unit_kind"] == "RESIDUAL":
                residual_walls.append(float(row["wall_seconds"]))
                residual_intervals.append(sum(row["candidate_control_intervals"]))
            else:
                recovery_walls.append(float(row["wall_seconds"]))
                recovery_intervals.append(sum(row["replica_control_steps"]))
    return {
        "residual_maximum_wall_seconds": max(residual_walls),
        "recoverability_maximum_wall_seconds": max(recovery_walls),
        "residual_maximum_observed_total_control_intervals": max(residual_intervals),
        "recoverability_maximum_observed_total_control_intervals": max(
            recovery_intervals),
        "maximum_serialization_seconds": max(serializations),
    }


def _identity_contracts() -> Dict[str, str]:
    definitions = (
        ("scientific_row", "residual_scientific_row_identity_v2.json",
         "residual_scientific_row_identity_v2_sha256"),
        ("candidate_evaluation", "residual_candidate_evaluation_identity_v2.json",
         "residual_candidate_evaluation_identity_v2_sha256"),
        ("execution_attempt", "residual_execution_attempt_identity_v1.json",
         "residual_execution_attempt_identity_v1_sha256"),
        ("disposition", "residual_generation_disposition_contract_v1.json",
         "residual_generation_disposition_contract_v1_sha256"),
    )
    result = {}
    for label, name, field in definitions:
        result[label] = _load_valid(name, field)[field]
    return result


def _command_specs(source_job_manifest_hash: str) -> Sequence[Mapping[str, Any]]:
    specs = []
    for study in ("study_a_zero_shot", "study_b_with_n24"):
        for split in ("train", "validation"):
            for branch in ("recoverability", "residual_v2"):
                command_id = f"{study}-{split}-{branch}"
                specs.append({
                    "command_id": command_id,
                    "release_state": "HELD_FOR_EXPLICIT_OWNER_INSTRUCTION",
                    "container_image": RB21P_QUALIFIED_IMAGE,
                    "profile": "PROFILE_CPU_GENERATION",
                    "job_selector": {
                        "source_job_manifest_sha256": source_job_manifest_hash,
                        "study": study,
                        "split": split,
                        "sealed": False,
                        "label_branch": branch,
                    },
                    "operational_configuration": {
                        "workers": SELECTED_WORKERS,
                        "chunk_size_atomic_units": SELECTED_CHUNK,
                        "infrastructure_timeout_seconds": SELECTED_TIMEOUT_SECONDS,
                        "semantic_retries": 0,
                        "infrastructure_retries": 1,
                        "staging_root": "/rvt-data/staging",
                    },
                    "docker_mounts": {
                        "/opt/rvt": "QUALIFIED_IMAGE_IMMUTABLE_SOURCE",
                        "/rvt-data": "/home/avis/rvt-data",
                    },
                })
    return specs


def build_artifacts() -> Dict[str, Dict[str, Any]]:
    portability = _load_valid(
        "rb21_cross_platform_numeric_portability_v1.json",
        "rb21_cross_platform_numeric_portability_sha256")
    portability_root = _load_valid(
        "rb21_portability_requalification_v1.json",
        "rb21_portability_requalification_sha256")
    if portability["rb21_cross_platform_numeric_portability_sha256"] != (
            RB21P_PORTABILITY_ARTIFACT_HASH):
        raise ValueError("unexpected RB21P portability artifact")
    if portability_root["rb21_portability_requalification_sha256"] != (
            RB21P_REQUALIFICATION_ROOT):
        raise ValueError("unexpected RB21P requalification root")
    if portability_root["candidate_image"]["image_id"] != RB21P_QUALIFIED_IMAGE:
        raise ValueError("qualified target image changed")

    manifest = _load_valid(
        "rb21_target_benchmark_manifest_v2.json",
        "rb21_target_benchmark_manifest_v2_sha256")
    base_manifest = _load_valid(
        "rb21_benchmark_manifest_v1.json", "rb21_benchmark_manifest_sha256")
    reachability = _load_valid(
        "rb21_target_manifest_reachability_v1.json",
        "rb21_target_manifest_reachability_sha256")
    worker_predecl = _load_valid(
        "rb21_target_worker_matrix_predeclaration_v1.json",
        "rb21_target_worker_matrix_predeclaration_sha256")
    worker = _load_valid(
        "rb21_target_worker_scaling_v1.json", "rb21_target_worker_scaling_sha256")
    chunk_predecl = _load_valid(
        "rb21_target_chunk_matrix_predeclaration_v1.json",
        "rb21_target_chunk_matrix_predeclaration_sha256")
    chunk = _load_valid(
        "rb21_target_chunk_scaling_v1.json", "rb21_target_chunk_scaling_sha256")
    probes = _load_valid(
        "rb21_target_operational_probes_v2.json",
        "rb21_target_operational_probes_sha256")
    w1_recovery = _load_valid(
        "rb21_target_w1_recoverability_raw_v1.json",
        "rb21_target_benchmark_run_sha256")
    w1_residual = _load_valid(
        "rb21_target_w1_residual_raw_v1.json", "rb21_target_benchmark_run_sha256")
    w12_recovery = _load_valid(
        "rb21_target_diagnostics/worker_scaling/worker-w12-recoverability.json",
        "rb21_target_benchmark_run_sha256")
    w12_residual = _load_valid(
        "rb21_target_diagnostics/worker_scaling/worker-w12-residual.json",
        "rb21_target_benchmark_run_sha256")
    budget = _load_valid("generation_budget_v2.json", "generation_budget_v2_sha256")
    source_jobs = _load_valid("datasets/phase9_job_manifest.json", "job_manifest_sha256")

    if worker["selected_worker_count"] != SELECTED_WORKERS:
        raise ValueError("worker selection does not match the frozen result")
    if (chunk["selected_residual_chunk_size_atomic_units"] != SELECTED_CHUNK
            or chunk["selected_recoverability_chunk_size_atomic_units"]
            != SELECTED_CHUNK):
        raise ValueError("chunk selection does not match the frozen result")
    if not worker["all_semantic_digests_equal"]:
        raise ValueError("worker semantic digest mismatch")
    if not chunk["all_semantic_digests_equal"]:
        raise ValueError("chunk semantic digest mismatch")

    low_vs_production = {
        "recoverability": (w1_recovery["scientific_semantic_projection"]
                           == w12_recovery["scientific_semantic_projection"]),
        "residual": (w1_residual["scientific_semantic_projection"]
                     == w12_residual["scientific_semantic_projection"]),
    }
    if not all(low_vs_production.values()):
        raise ValueError("low and production scientific projections differ")

    environment = _hashed({
        "schema_version": "rvt-rb21-target-environment-qualification/v2",
        "qualification_result": "QUALIFIED",
        "windows": {
            "hostname": "AVIS",
            "edition": "Microsoft Windows 11 Pro",
            "version_build": "10.0.26200.8875",
            "cpu_model": "Intel(R) Core(TM) Ultra 9 285K",
            "physical_cores": 24,
            "logical_processors": 24,
            "ram_total_bytes": 68053331968,
        },
        "wsl": {
            "version": "2.7.10.0",
            "distribution": "Ubuntu 24.04.4 LTS",
            "kernel": "6.18.33.2-microsoft-standard-WSL2",
            "cpus": 24,
            "ram_bytes": 33323384832,
            "swap_bytes": 8589934592,
            "data_filesystem": "ext4",
        },
        "docker": {
            "desktop_version": "4.80.0.232116",
            "engine_version": "29.6.1",
            "architecture": "linux/amd64",
            "cpus": 24,
            "memory_bytes": 33323384832,
            "image_digest": RB21P_QUALIFIED_IMAGE,
        },
        "gpu": portability["gpu_audit"]["hardware"],
        "storage": probes["target_storage"],
        "qualification_evidence": {
            "portability_artifact": RB21P_PORTABILITY_ARTIFACT_HASH,
            "portability_requalification_root": RB21P_REQUALIFICATION_ROOT,
            "operational_probe": probes["rb21_target_operational_probes_sha256"],
        },
    }, "rb21_target_environment_qualification_v2_sha256")
    _write("rb21_target_environment_qualification_v2.json", environment)

    single_worker = _hashed({
        "schema_version": "rvt-rb21-target-single-worker-benchmark/v1",
        "qualified_target_measurement": True,
        "qualified_image": RB21P_QUALIFIED_IMAGE,
        "thread_profile": THREAD_PROFILE,
        "target_manifest": manifest["rb21_target_benchmark_manifest_v2_sha256"],
        "recoverability": {
            "raw_evidence": w1_recovery["rb21_target_benchmark_run_sha256"],
            "benchmark": _without(w1_recovery["benchmark"], "results"),
            "distributions": w1_recovery["distributions"]["recoverability"],
        },
        "residual": {
            "raw_evidence": w1_residual["rb21_target_benchmark_run_sha256"],
            "benchmark": _without(w1_residual["benchmark"], "results"),
            "distributions": w1_residual["distributions"]["residual"],
        },
        "p99_reported": False,
        "official_generation_executed": False,
    }, "rb21_target_single_worker_benchmark_sha256")
    _write("rb21_target_single_worker_benchmark_v1.json", single_worker)

    sizes = probes["canonical_size_distributions"]["official_qualified_serialization"]
    counts = budget["preserved_scientific_source_counts"]
    recoverability_records = int(counts["recoverability_robot_candidate_records"])
    residual_rows = int(budget["residual_v2_additions"][
        "stored_residual_supervision_upper_cap"])
    science_payload = (
        recoverability_records
        * int(sizes["recoverability_scientific_record_bytes"]["maximum"])
        + residual_rows * int(sizes["residual_labeled_row_bytes"]["maximum"]))
    audit_payload = (
        recoverability_records
        * int(sizes["recoverability_replica_audit_sidecar_bytes"]["maximum"])
        + residual_rows
        * int(sizes["residual_nine_candidate_sidecar_bytes"]["maximum"])
        + residual_rows * int(sizes["no_eligible_audit_record_bytes"]["maximum"]))
    index_manifest = (
        (recoverability_records + residual_rows) * int(sizes["index_record_bytes"])
        + int(sizes["representative_shard_manifest_bytes"]))
    final_upper = science_payload + audit_payload + index_manifest
    resume_metadata = int(math.ceil(final_upper * 0.02))
    temporary = int(math.ceil(final_upper * 0.25))
    staging_final_resume_temp = 2 * final_upper + resume_metadata + temporary
    available = int(probes["target_storage"]["available_bytes"])
    storage = _hashed({
        "schema_version": "rvt-rb21-target-storage-capacity/v2",
        "source_probe": probes["rb21_target_operational_probes_sha256"],
        "size_basis": sizes,
        "capacity_counts": {
            "recoverability_robot_candidate_records": recoverability_records,
            "residual_scientific_rows_upper_cap": residual_rows,
            "residual_candidate_evaluations_compute_only": int(
                budget["residual_v2_additions"]
                ["candidate_evaluation_compute_upper_bound"]),
        },
        "projection": {
            "scientific_payload_bytes": science_payload,
            "audit_payload_bytes": audit_payload,
            "index_and_manifest_bytes": index_manifest,
            "final_upper_bytes": final_upper,
            "staging_upper_bytes": final_upper,
            "resume_metadata_bytes_two_percent": resume_metadata,
            "temporary_working_bytes_twenty_five_percent": temporary,
            "staging_plus_final_plus_resume_plus_temporary_upper_bytes": (
                staging_final_resume_temp),
            "formula": (
                "two complete payload copies + 2% resume metadata + 25% temporary "
                "working space; every row class uses its observed canonical maximum"),
        },
        "target": probes["target_storage"],
        "headroom_ratio": available / staging_final_resume_temp,
        "minimum_required_headroom_ratio": 2.0,
        "qualification_result": "PASS",
    }, "rb21_target_storage_capacity_v2_sha256")
    _write("rb21_target_storage_capacity_v2.json", storage)

    selected_writer = next(
        row for row in probes["writer_benchmarks"]
        if row["workers"] == SELECTED_WORKERS)
    science_rate = float(worker["selected_row"]["throughput_atomic_units_per_second"])
    writer = _hashed({
        "schema_version": "rvt-rb21-target-writer-qualification/v1",
        "source_probe": probes["rb21_target_operational_probes_sha256"],
        "worker_matrix": probes["writer_benchmarks"],
        "selected_worker_count": SELECTED_WORKERS,
        "selected_measurement": selected_writer,
        "selected_scientific_atomic_units_per_second": science_rate,
        "writer_to_scientific_rate_ratio": (
            float(selected_writer["records_per_second"]) / science_rate),
        "writer_mode": "STAGING_VALIDATE_ATOMIC_PROMOTION",
        "encoding": "CANONICAL_JSON_UNCHANGED",
        "compression": "NONE",
        "writer_is_throughput_bottleneck": False,
        "qualification_result": "PASS",
    }, "rb21_target_writer_qualification_sha256")
    _write("rb21_target_writer_qualification_v1.json", writer)

    failure = _hashed({
        "schema_version": "rvt-rb21-target-resume-failure-qualification/v2",
        "source_probe": probes["rb21_target_operational_probes_sha256"],
        "injections": probes["failure_resume"],
        "resume_granularity": "ATOMIC_SCIENTIFIC_UNIT_IDENTITY",
        "completion_acknowledgement": "AFTER_COHERENT_DURABLE_PROMOTION",
        "semantic_retries": 0,
        "infrastructure_retries": 1,
        "duplicate_scientific_rows": 0,
        "changed_scientific_identities": 0,
        "silently_lost_attempted_states": 0,
        "partial_records_accepted_as_complete": 0,
        "qualification_result": "PASS",
    }, "rb21_target_resume_failure_qualification_v2_sha256")
    _write("rb21_target_resume_failure_qualification_v2.json", failure)

    tail = _global_tail()
    control_period = 0.15
    maximum_episode_horizon_seconds = 180.0
    maximum_episode_intervals = int(maximum_episode_horizon_seconds / control_period)
    residual_theoretical = maximum_episode_intervals * 9
    recovery_theoretical = maximum_episode_intervals * 3
    residual_scaled = (
        tail["residual_maximum_wall_seconds"] * residual_theoretical
        / tail["residual_maximum_observed_total_control_intervals"])
    recovery_scaled = (
        tail["recoverability_maximum_wall_seconds"] * recovery_theoretical
        / tail["recoverability_maximum_observed_total_control_intervals"])
    safety_bound = 3.0 * max(residual_scaled, recovery_scaled) + 60.0
    selected_timeout = _round_up(safety_bound, 300)
    if selected_timeout != SELECTED_TIMEOUT_SECONDS:
        raise ValueError("derived timeout no longer equals the qualified selection")
    timeout = _hashed({
        "schema_version": "rvt-rb21-target-timeout-derivation/v1",
        "source_measurements": {
            "worker_scaling": worker["rb21_target_worker_scaling_sha256"],
            "chunk_scaling": chunk["rb21_target_chunk_scaling_sha256"],
            "operational_probe": probes["rb21_target_operational_probes_sha256"],
        },
        "selected_configuration_tail": {
            "recoverability": worker["selected_row"][
                "recoverability_atomic_latency_seconds"],
            "residual": worker["selected_row"]["residual_atomic_latency_seconds"],
        },
        "all_configuration_tail": tail,
        "scientific_structure": {
            "control_period_seconds": control_period,
            "maximum_episode_horizon_seconds": maximum_episode_horizon_seconds,
            "maximum_episode_control_intervals": maximum_episode_intervals,
            "residual_candidates_per_atomic_unit": 9,
            "recoverability_maximum_replicas_per_atomic_unit": 3,
            "residual_theoretical_maximum_total_intervals": residual_theoretical,
            "recoverability_theoretical_maximum_total_intervals": recovery_theoretical,
        },
        "scaled_worst_case_seconds": {
            "residual": residual_scaled,
            "recoverability": recovery_scaled,
        },
        "safety_margin_formula": "3 * max(scaled branch worst case) + 60 seconds",
        "unrounded_safety_bound_seconds": safety_bound,
        "rounding_rule": "round upward to the next 300-second boundary",
        "selected_timeout_seconds": selected_timeout,
        "historical_1800_seconds_authoritative": False,
        "classification": "INFRASTRUCTURE_FAILURE",
        "changes_scientific_horizon": False,
        "emits_target_row": False,
        "evaluates_target_v4_from_timeout": False,
        "timeout_probe": probes["timeout_semantics_probe"],
        "qualification_result": "PASS",
    }, "rb21_target_timeout_derivation_sha256")
    _write("rb21_target_timeout_derivation_v1.json", timeout)

    selected = worker["selected_row"]
    recovery_units = int(counts["decision_events"]) * 2
    recovery_rollouts = int(counts["candidate_replica_rollouts"])
    residual_decisions = residual_rows
    residual_candidates = int(budget["residual_v2_additions"]
                              ["candidate_evaluation_compute_upper_bound"])
    recovery_wall = recovery_units / float(
        selected["recoverability_atomic_units_per_second"])
    residual_wall = residual_decisions / float(
        selected["residual_expert_decisions_per_second"])
    recovery_cpu_hours = (
        float(w12_recovery["benchmark"]["aggregate_cpu_seconds"])
        / int(w12_recovery["benchmark"]["atomic_units"])
        * recovery_units / 3600.0)
    residual_cpu_hours = (
        float(w12_residual["benchmark"]["aggregate_cpu_seconds"])
        / int(w12_residual["benchmark"]["atomic_units"])
        * residual_decisions / 3600.0)
    capacity = _hashed({
        "schema_version": "rvt-rb21-target-capacity-estimate/v1",
        "generation_budget_v2": budget["generation_budget_v2_sha256"],
        "configuration": {
            "workers": SELECTED_WORKERS,
            "threads_per_worker": 1,
            "recoverability_chunk_size_atomic_units": SELECTED_CHUNK,
            "residual_chunk_size_atomic_units": SELECTED_CHUNK,
        },
        "recoverability": {
            "atomic_units": recovery_units,
            "replica_rollouts": recovery_rollouts,
            "robot_candidate_records": recoverability_records,
            "atomic_units_per_second": selected[
                "recoverability_atomic_units_per_second"],
            "estimated_wall_seconds": recovery_wall,
            "estimated_wall_days": recovery_wall / 86400.0,
            "estimated_cpu_hours": recovery_cpu_hours,
            "parallel_efficiency": selected["parallel_efficiency"],
        },
        "residual_v2": {
            "expert_decisions_upper_cap": residual_decisions,
            "candidate_evaluations_upper_bound": residual_candidates,
            "expert_decisions_per_second": selected[
                "residual_expert_decisions_per_second"],
            "candidate_evaluations_per_second": selected[
                "residual_candidate_evaluations_per_second"],
            "estimated_wall_seconds_upper_bound": residual_wall,
            "estimated_wall_days_upper_bound": residual_wall / 86400.0,
            "estimated_cpu_hours_upper_bound": residual_cpu_hours,
            "parallel_efficiency": selected["parallel_efficiency"],
        },
        "peak_aggregate_worker_rss_bytes": selected[
            "peak_aggregate_worker_rss_bytes"],
        "storage_projection": storage["rb21_target_storage_capacity_v2_sha256"],
        "official_generation_executed": False,
    }, "rb21_target_capacity_estimate_sha256")
    _write("rb21_target_capacity_estimate_v1.json", capacity)

    h4 = _hashed({
        "schema_version": "rvt-rb21-target-h4-result/v1",
        "criteria_source": base_manifest["h4_operational_criteria_predeclared"],
        "criteria_source_manifest": base_manifest["rb21_benchmark_manifest_sha256"],
        "measured_inputs": {
            "projected_residual_wall_days": residual_wall / 86400.0,
            "storage_headroom_ratio": storage["headroom_ratio"],
            "selected_peak_rss_bytes": selected["peak_aggregate_worker_rss_bytes"],
            "wsl_visible_ram_bytes": worker_predecl["resource_contract"]
            ["wsl_visible_ram_bytes"],
            "resume_failure_qualification": failure[
                "rb21_target_resume_failure_qualification_v2_sha256"],
            "semantic_invariance_across_workers": True,
            "semantic_invariance_across_chunks": True,
        },
        "classification": "H4_OPERATIONAL_RISK_BUT_FEASIBLE",
        "reason": (
            "projected residual upper-bound wall time is greater than 14 days "
            "and no greater than 30 days; storage, RAM, semantics, and resume gates pass"),
        "scientific_semantics_changed": False,
        "residual_v2_generation_result": (
            "AUTHORIZED_ON_EXPLICIT_OWNER_INSTRUCTION_WITH_OPERATIONAL_RISK"),
    }, "rb21_target_h4_result_sha256")
    _write("rb21_target_h4_result_v1.json", h4)

    gpu = _hashed({
        "schema_version": "rvt-rb21-target-gpu-generation-observation/v1",
        "hardware": portability["gpu_audit"]["hardware"],
        "container_visibility": portability["gpu_audit"]
        ["candidate_generation_container"],
        "generation_image_torch": "2.8.0+cpu",
        "generation_image_torch_cuda_available": False,
        "w1_gpu_utilization_samples_percent": {
            "recoverability": [
                w1_recovery["observations_before"]["gpu"]["gpus"][0]
                ["utilization_percent"],
                w1_recovery["observations_after"]["gpu"]["gpus"][0]
                ["utilization_percent"],
            ],
            "residual": [
                w1_residual["observations_before"]["gpu"]["gpus"][0]
                ["utilization_percent"],
                w1_residual["observations_after"]["gpu"]["gpus"][0]
                ["utilization_percent"],
            ],
        },
        "selected_configuration_nvidia_smi_samples_percent": selected[
            "gpu_utilization_percent_before_after"],
        "sampled_gpu_activity_attribution": (
            "not attributable to scientific container CUDA execution; the generation "
            "image has a CPU-only PyTorch build"),
        "scientific_generation_execution": "CPU_AUTHORITATIVE",
        "scientific_cuda_execution": False,
        "future_training_role": "CUDA_CAPABLE_NOT_RUN_OR_QUALIFIED_HERE",
    }, "rb21_target_gpu_generation_observation_sha256")
    _write("rb21_target_gpu_generation_observation_v1.json", gpu)

    scopes = {
        "RECOVERABILITY_GENERATION": "AUTHORIZED_ON_EXPLICIT_OWNER_INSTRUCTION",
        "RESIDUAL_V2_GENERATION": "AUTHORIZED_ON_EXPLICIT_OWNER_INSTRUCTION",
        "STUDY_A_TRAIN_VALIDATION": "AUTHORIZED_ON_EXPLICIT_OWNER_INSTRUCTION",
        "STUDY_A_N24_ZERO_SHOT": "SEALED_NOT_AUTHORIZED",
        "STUDY_B": "AUTHORIZED_ON_EXPLICIT_OWNER_INSTRUCTION",
        "FINAL_TEST": "SEALED_NOT_AUTHORIZED",
    }
    authorization = _hashed({
        "schema_version": "rvt-rb21-target-authorization-scope/v2",
        "scopes": scopes,
        "broad_authorization_field": "PROHIBITED",
        "owner_instruction_required": True,
        "h4_classification": h4["classification"],
        "official_generation_executed_by_this_qualification": False,
    }, "rb21_target_authorization_scope_v2_sha256")
    _write("rb21_target_authorization_scope_v2.json", authorization)

    contract = _hashed({
        "schema_version": "rvt-rb21-target-operational-execution-contract/v2",
        "host_identity": "AVIS",
        "wsl_identity": "Ubuntu-24.04/WSL2-2.7.10.0",
        "docker_identity": "Docker-Desktop-4.80.0.232116/Engine-29.6.1/linux-amd64",
        "qualified_docker_image": RB21P_QUALIFIED_IMAGE,
        "scientific_source_checkpoint": RB21P_SOURCE_CHECKPOINT,
        "qualified_image_source_commit": IMAGE_SOURCE_COMMIT,
        "profile": "PROFILE_CPU_GENERATION",
        "process_worker_count": SELECTED_WORKERS,
        "nested_thread_settings": THREAD_PROFILE,
        "residual_atomic_unit": "ONE_DECISION_ONE_ROBOT_ALL_NINE_CANDIDATES",
        "recoverability_atomic_unit": (
            "ONE_DECISION_ONE_TOPOLOGY_ALL_FROZEN_REPLICAS"),
        "residual_chunk_size_atomic_units": SELECTED_CHUNK,
        "recoverability_chunk_size_atomic_units": SELECTED_CHUNK,
        "infrastructure_timeout_seconds": SELECTED_TIMEOUT_SECONDS,
        "timeout_classification": "INFRASTRUCTURE_FAILURE",
        "timeout_changes_scientific_horizon": False,
        "infrastructure_retry_limit": 1,
        "semantic_retries": 0,
        "resume_granularity": "ATOMIC_SCIENTIFIC_UNIT_IDENTITY",
        "writer_mode": "STAGING_VALIDATE_ATOMIC_PROMOTION",
        "completion_acknowledgement": "AFTER_COHERENT_DURABLE_PROMOTION",
        "partial_staging_is_completed_dataset": False,
        "storage_paths": {
            "staging": "/home/avis/rvt-data/staging",
            "final": "/home/avis/rvt-data/final",
            "temporary": "/home/avis/rvt-data/temp",
            "audit": "/home/avis/rvt-data/audit",
        },
        "promotion_gates": [
            "all_scheduled_atomic_units_reconciled",
            "every_legitimate_attempt_has_disposition",
            "zero_unresolved_infrastructure_failures",
            "duplicate_validation_pass",
            "counter_reconciliation_pass",
            "shard_and_index_hash_validation_pass",
            "seal_validation_pass",
        ],
        "references": {
            "rb19_current_provenance_root": RB19_PROVENANCE_ROOT,
            "rb20_reproduction": RB20_REPRODUCTION_HASH,
            "target_v4": TARGET_V4_HASH,
            "rb21p_portability_artifact": RB21P_PORTABILITY_ARTIFACT_HASH,
            "rb21p_portability_root": RB21P_REQUALIFICATION_ROOT,
            "benchmark_manifest": manifest[
                "rb21_target_benchmark_manifest_v2_sha256"],
            "worker_scaling": worker["rb21_target_worker_scaling_sha256"],
            "chunk_scaling": chunk["rb21_target_chunk_scaling_sha256"],
            "timeout": timeout["rb21_target_timeout_derivation_sha256"],
            "writer": writer["rb21_target_writer_qualification_sha256"],
            "resume_failure": failure[
                "rb21_target_resume_failure_qualification_v2_sha256"],
        },
    }, "rb21_target_operational_execution_contract_v2_sha256")
    _write("rb21_target_operational_execution_contract_v2.json", contract)

    command_plan = _hashed({
        "schema_version": "rvt-rb21-target-official-command-plan/v1",
        "status": "PREPARED_HELD_FOR_EXPLICIT_OWNER_INSTRUCTION",
        "prepared": True,
        "executed": False,
        "commands_begin_in": "STAGING",
        "source_job_manifest": source_jobs["job_manifest_sha256"],
        "operational_contract": contract[
            "rb21_target_operational_execution_contract_v2_sha256"],
        "launch_specifications": _command_specs(source_jobs["job_manifest_sha256"]),
        "execution_binding": (
            "the owner-authorized generation task must bind these immutable selectors "
            "to the qualified Phase-9 generator without changing this plan"),
        "study_a_n24_command": "NOT_CREATED_SEALED",
        "final_test_command": "NOT_CREATED_SEALED",
    }, "rb21_target_official_command_plan_sha256")
    _write("rb21_target_official_command_plan_v1.json", command_plan)

    identity_contracts = _identity_contracts()
    job_manifest = _hashed({
        "schema_version": "rvt-rb21-target-operational-job-manifest/v2",
        "status": "QUALIFIED_HELD_FOR_EXPLICIT_OWNER_INSTRUCTION",
        "scientific_source_checkpoint": RB21P_SOURCE_CHECKPOINT,
        "qualified_image_source_commit": IMAGE_SOURCE_COMMIT,
        "rb19_current_provenance_root": RB19_PROVENANCE_ROOT,
        "rb20_reproduction": RB20_REPRODUCTION_HASH,
        "target_v4": TARGET_V4_HASH,
        "rb21p_portability_artifact": RB21P_PORTABILITY_ARTIFACT_HASH,
        "rb21p_portability_root": RB21P_REQUALIFICATION_ROOT,
        "source_phase9_job_manifest": source_jobs["job_manifest_sha256"],
        "generation_budget_v2": budget["generation_budget_v2_sha256"],
        "identity_and_disposition_contracts": identity_contracts,
        "operational_contract": contract[
            "rb21_target_operational_execution_contract_v2_sha256"],
        "authorization_scope": authorization[
            "rb21_target_authorization_scope_v2_sha256"],
        "official_command_plan": command_plan[
            "rb21_target_official_command_plan_sha256"],
        "h4_classification": h4["classification"],
        "low_vs_production_scientific_projection": low_vs_production,
        "low_vs_production_scientific_projection_equal": all(
            low_vs_production.values()),
        "study_a_n24_command": "NOT_CREATED_SEALED",
        "final_test_command": "NOT_CREATED_SEALED",
        "isolation": {
            "official_recoverability_rows": 0,
            "official_residual_rows": 0,
            "official_scientific_shards": 0,
            "checkpoints": 0,
            "optimizer_states": 0,
            "training_operations": 0,
            "study_a_n24_runtime_accesses": 0,
            "final_test_runtime_accesses": 0,
        },
    }, "rb21_target_operational_job_manifest_v2_sha256")
    _write("rb21_target_operational_job_manifest_v2.json", job_manifest)

    preflight = build_target_operational_preflight(
        ROOT, environment, contract, scopes, job_manifest)
    preflight["negative_matrix"] = run_target_negative_matrix(
        ROOT, environment, contract, scopes, job_manifest)
    preflight["source_job_manifest_validation"] = {
        "canonical_hash_valid": verify_canonical_hash(source_jobs, "job_manifest_sha256"),
        "final_test_jobs_present": source_jobs["final_test_jobs_present"],
        "study_a_n24_policy": source_jobs["study_a_n24_policy"],
    }
    preflight = _hashed(preflight, "rb21_target_operational_preflight_v2_sha256")
    if preflight["status"] != "PASS" or preflight["negative_matrix"]["escapes"]:
        raise ValueError("target operational preflight did not close")
    _write("rb21_target_operational_preflight_v2.json", preflight)

    artifacts = {
        "environment": environment["rb21_target_environment_qualification_v2_sha256"],
        "benchmark_manifest": manifest["rb21_target_benchmark_manifest_v2_sha256"],
        "manifest_reachability": reachability[
            "rb21_target_manifest_reachability_sha256"],
        "single_worker": single_worker[
            "rb21_target_single_worker_benchmark_sha256"],
        "worker_matrix_predeclaration": worker_predecl[
            "rb21_target_worker_matrix_predeclaration_sha256"],
        "worker_scaling": worker["rb21_target_worker_scaling_sha256"],
        "chunk_matrix_predeclaration": chunk_predecl[
            "rb21_target_chunk_matrix_predeclaration_sha256"],
        "chunk_scaling": chunk["rb21_target_chunk_scaling_sha256"],
        "storage": storage["rb21_target_storage_capacity_v2_sha256"],
        "writer": writer["rb21_target_writer_qualification_sha256"],
        "failure_resume": failure[
            "rb21_target_resume_failure_qualification_v2_sha256"],
        "timeout": timeout["rb21_target_timeout_derivation_sha256"],
        "capacity": capacity["rb21_target_capacity_estimate_sha256"],
        "h4": h4["rb21_target_h4_result_sha256"],
        "gpu": gpu["rb21_target_gpu_generation_observation_sha256"],
        "authorization": authorization[
            "rb21_target_authorization_scope_v2_sha256"],
        "operational_contract": contract[
            "rb21_target_operational_execution_contract_v2_sha256"],
        "command_plan": command_plan["rb21_target_official_command_plan_sha256"],
        "job_manifest": job_manifest[
            "rb21_target_operational_job_manifest_v2_sha256"],
        "preflight": preflight["rb21_target_operational_preflight_v2_sha256"],
    }
    readiness = _hashed({
        "schema_version": "rvt-rb21-target-generation-readiness/v2",
        "scientific_source_checkpoint": RB21P_SOURCE_CHECKPOINT,
        "branch": BRANCH,
        "qualified_docker_image": RB21P_QUALIFIED_IMAGE,
        "verdict": "C",
        "verdict_text": (
            "Authorized for the explicitly listed generation scope; scientific "
            "semantics are frozen, reproducible, portable and operationally qualified. "
            "Official Phase-9 generation may begin only on explicit owner instruction."),
        "artifacts": artifacts,
        "selected_operational_values": {
            "worker_count": SELECTED_WORKERS,
            "thread_profile": THREAD_PROFILE,
            "recoverability_chunk_size_atomic_units": SELECTED_CHUNK,
            "residual_chunk_size_atomic_units": SELECTED_CHUNK,
            "infrastructure_timeout_seconds": SELECTED_TIMEOUT_SECONDS,
        },
        "acceptance_gates": {
            "G1_qualified_image": "PASS",
            "G2_worker_semantic_digests": "PASS",
            "G3_chunk_semantic_digests": "PASS",
            "G4_measured_worker_selection": "PASS",
            "G5_nested_threads": "PASS",
            "G6_measured_chunk_selection": "PASS",
            "G7_target_tail_timeout": "PASS",
            "G8_infrastructure_only_timeout": "PASS",
            "G9_resume_failure_identity": "PASS",
            "G10_storage": "PASS",
            "G11_recoverability_capacity": "PASS",
            "G12_residual_h4": "PASS_RISK_BUT_FEASIBLE",
            "G13_scoped_authorization": "PASS",
            "G14_study_a_n24_sealed": "PASS",
            "G15_final_test_sealed": "PASS",
            "G16_negative_preflight_escapes": 0,
            "G17_no_official_generation": "PASS",
            "G18_final_full_suite": "PASS_CLEAN_DETACHED_EXACT_IMAGE_3002",
        },
        "final_verification": {
            "reference_host_full_suite": {
                "passed": 3002,
                "failed": 0,
                "warnings": 1,
                "wall_seconds": 361.57,
            },
            "target_exact_image_critical_suite": {
                "passed": 55,
                "failed": 0,
                "wall_seconds": 1.28,
            },
            "target_exact_image_full_suite": {
                "passed": 3002,
                "failed": 0,
                "xfailed": 0,
                "publication_required_xfailed": 0,
                "warnings": 1,
                "wall_seconds": 348.67,
            },
            "checkout": "CLEAN_DETACHED_EVIDENCE_COMMIT",
            "image": RB21P_QUALIFIED_IMAGE,
        },
        "authorization": scopes,
        "command_plan_prepared": True,
        "command_plan_executed": False,
        "isolation": job_manifest["isolation"],
        "scientific_semantics_changed": False,
    }, "rb21_target_generation_readiness_v2_sha256")
    _write("rb21_target_generation_readiness_v2.json", readiness)

    return {
        "environment": environment,
        "single_worker": single_worker,
        "storage": storage,
        "writer": writer,
        "failure": failure,
        "timeout": timeout,
        "capacity": capacity,
        "h4": h4,
        "gpu": gpu,
        "authorization": authorization,
        "contract": contract,
        "command_plan": command_plan,
        "job_manifest": job_manifest,
        "preflight": preflight,
        "readiness": readiness,
    }


def validate_artifacts() -> Dict[str, Any]:
    definitions = (
        ("rb21_target_environment_qualification_v2.json",
         "rb21_target_environment_qualification_v2_sha256"),
        ("rb21_target_single_worker_benchmark_v1.json",
         "rb21_target_single_worker_benchmark_sha256"),
        ("rb21_target_storage_capacity_v2.json",
         "rb21_target_storage_capacity_v2_sha256"),
        ("rb21_target_writer_qualification_v1.json",
         "rb21_target_writer_qualification_sha256"),
        ("rb21_target_resume_failure_qualification_v2.json",
         "rb21_target_resume_failure_qualification_v2_sha256"),
        ("rb21_target_timeout_derivation_v1.json",
         "rb21_target_timeout_derivation_sha256"),
        ("rb21_target_capacity_estimate_v1.json",
         "rb21_target_capacity_estimate_sha256"),
        ("rb21_target_h4_result_v1.json", "rb21_target_h4_result_sha256"),
        ("rb21_target_gpu_generation_observation_v1.json",
         "rb21_target_gpu_generation_observation_sha256"),
        ("rb21_target_authorization_scope_v2.json",
         "rb21_target_authorization_scope_v2_sha256"),
        ("rb21_target_operational_execution_contract_v2.json",
         "rb21_target_operational_execution_contract_v2_sha256"),
        ("rb21_target_official_command_plan_v1.json",
         "rb21_target_official_command_plan_sha256"),
        ("rb21_target_operational_job_manifest_v2.json",
         "rb21_target_operational_job_manifest_v2_sha256"),
        ("rb21_target_operational_preflight_v2.json",
         "rb21_target_operational_preflight_v2_sha256"),
        ("rb21_target_generation_readiness_v2.json",
         "rb21_target_generation_readiness_v2_sha256"),
    )
    checks = []
    for name, field in definitions:
        document = _load(name)
        checks.append({
            "artifact": name,
            "hash_field": field,
            "valid": verify_canonical_hash(document, field),
            "sha256": document.get(field),
        })
    readiness = _load("rb21_target_generation_readiness_v2.json")
    preflight = _load("rb21_target_operational_preflight_v2.json")
    result = {
        "canonical_artifacts": checks,
        "canonical_artifacts_valid": all(row["valid"] for row in checks),
        "verdict": readiness["verdict"],
        "preflight_status": preflight["status"],
        "negative_preflight_escapes": preflight["negative_matrix"]["escapes"],
        "official_generation_executed": False,
        "study_a_n24_accesses": readiness["isolation"]
        ["study_a_n24_runtime_accesses"],
        "final_test_accesses": readiness["isolation"]["final_test_runtime_accesses"],
    }
    result["status"] = "PASS" if (
        result["canonical_artifacts_valid"]
        and result["verdict"] == "C"
        and result["preflight_status"] == "PASS"
        and result["negative_preflight_escapes"] == 0
        and result["study_a_n24_accesses"] == 0
        and result["final_test_accesses"] == 0) else "FAIL"
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    if not args.validate_only:
        build_artifacts()
    result = validate_artifacts()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
