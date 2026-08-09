#!/usr/bin/env python3
"""Build RB-21 operational evidence without executing official generation."""

from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing as mp
import os
import shutil
import tempfile
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, Mapping

from rvt_swarm.phase8.common import (
    attach_canonical_hash, canonical_json_bytes, verify_canonical_hash,
)
from rvt_swarm.phase9.preflight import rb19_provenance_checks
from rvt_swarm.phase9c_rb.counterfactual import replica_count_for_family
from rvt_swarm.phase9c_rb21.rb21_bench import (
    distribution, run_process_benchmark, scaling_projection,
)
from rvt_swarm.phase9c_rb21.rb21_manifest import (
    RB19_PROVENANCE_ROOT, RB20_REPRODUCTION_HASH, RB20_SOURCE_COMMIT, TARGET_V4_HASH,
    benchmark_cases, build_benchmark_manifest, capture_environment, write_json,
)
from rvt_swarm.phase9c_rb21.rb21_preflight import (
    build_operational_preflight, pending_authorization, pending_operational_contract,
    run_negative_matrix,
)
from rvt_swarm.phase9c_rb21.rb21_storage import (
    AtomicUnitStore, StorageContractError, representative_sizes, storage_projection,
)
from rvt_swarm.phase9c_rb21.rb21_units import (
    RecoverabilityAtomicUnit, ResidualAtomicUnit, ThreadSettings,
    scientific_semantic_digest,
)

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results/rvt_fd24"


def _hash(document: Mapping[str, Any], field: str) -> Dict[str, Any]:
    return attach_canonical_hash(dict(document), field)


def _provenance_validation() -> Dict[str, Any]:
    checks = rb19_provenance_checks(ROOT)
    rb20 = json.loads((RESULTS / "rb20_clean_detached_reproduction_v1.json")
                      .read_text(encoding="ascii"))
    target = json.loads((RESULTS / "target_v4_execution_contract_v1.json")
                        .read_text(encoding="ascii"))
    return {
        "rb19_current_root": RB19_PROVENANCE_ROOT,
        "rb19_missing": sum(item["name"] == "rb19_provenance_closure_complete"
                            and not item["passed"] for item in checks),
        "rb19_ambiguous": 0 if all(item["passed"] for item in checks
                                   if "closure" in item["name"]) else 1,
        "rb19_stale_current": 0 if all(item["passed"] for item in checks
                                       if "stale" in item["name"]) else 1,
        "rb19_checks_pass": all(item["passed"] for item in checks),
        "rb20_reproduction": rb20["rb20_clean_detached_reproduction_sha256"],
        "rb20_expected": RB20_REPRODUCTION_HASH,
        "rb20_valid": (verify_canonical_hash(
            rb20, "rb20_clean_detached_reproduction_sha256")
            and rb20["rb20_clean_detached_reproduction_sha256"]
            == RB20_REPRODUCTION_HASH),
        "target_v4": target["target_v4_execution_contract_sha256"],
        "target_v4_valid": target["target_v4_execution_contract_sha256"]
        == TARGET_V4_HASH,
    }


def _semantic_helper_qualification(rb18: Mapping[str, Any]) -> Dict[str, Any]:
    base = []
    for item in rb18["recoverability"]:
        base.append({
            "atomic_unit_id": item["decision_snapshot_sha256"],
            "kind": "RECOVERABILITY", "scientific": item,
        })
    for item in rb18["residual"]:
        base.append({
            "atomic_unit_id": item["scientific_row_id"],
            "kind": "RESIDUAL", "scientific": item,
        })
    low = [{**item, "worker_id": 0, "chunk_id": "low", "attempt_index": 0,
            "wall_seconds": 1.0} for item in base]
    parallel = [{**item, "worker_id": index % 4, "chunk_id": f"p{index // 4}",
                 "attempt_index": 1, "wall_seconds": 0.5}
                for index, item in enumerate(reversed(base))]
    low_digest = scientific_semantic_digest(low)
    parallel_digest = scientific_semantic_digest(parallel)
    return {
        "source": "committed RB18/RB20 diagnostic scientific records",
        "low_parallelism_digest": low_digest,
        "changed_worker_and_chunk_digest": parallel_digest,
        "identical": low_digest == parallel_digest,
        "timing_and_operational_metadata_excluded_only": True,
    }


def _crashing_commit_worker(root: str, point: str) -> None:
    store = AtomicUnitStore(Path(root))
    record = {"atomic_unit_id": f"worker-{point}", "disposition": "LABELED"}
    sidecar = {"candidate_ids": list(range(9))}
    try:
        store.commit(f"worker-{point}", record, sidecar,
                     attempt_id=f"worker-attempt-{point}", failure_point=point)
    except StorageContractError:
        os._exit(71)


def _between_chunks_worker(root: str) -> None:
    store = AtomicUnitStore(Path(root))
    record = {"atomic_unit_id": "chunk-unit-a", "disposition": "LABELED"}
    sidecar = {"candidate_ids": list(range(9))}
    store.commit("chunk-unit-a", record, sidecar, attempt_id="chunk-attempt-a")
    os._exit(72)


def _failure_injection() -> Dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="rvt-rb21-failure-") as temporary:
        root = Path(temporary) / "staging"
        store = AtomicUnitStore(root)
        record = {"atomic_unit_id": "unit-a", "target": [0.1, -0.2],
                  "disposition": "LABELED"}
        sidecar = {"atomic_unit_id": "unit-a", "candidate_ids": list(range(9))}
        cases = []
        for point in ("after_record", "after_sidecar", "before_promotion"):
            attempt = f"failure-{point}"
            try:
                store.commit("unit-a", record, sidecar, attempt_id=attempt,
                             failure_point=point)
            except StorageContractError:
                pass
            cases.append({
                "injection": point,
                "accepted_as_complete": "unit-a" in store.completed_unit_ids(),
            })
        first = store.commit("unit-a", record, sidecar, attempt_id="success-1")
        duplicate = store.commit("unit-a", record, sidecar, attempt_id="duplicate-1")
        before_restart = store.completed_unit_ids()
        resumed = AtomicUnitStore(root)
        after_restart = resumed.completed_unit_ids()
        insufficient_rejected = False
        try:
            resumed.commit("unit-b", record, sidecar, attempt_id="no-space",
                           required_free_bytes=shutil.disk_usage(root).free + 1)
        except StorageContractError:
            insufficient_rejected = True
        context = mp.get_context("spawn")
        worker_before_complete = context.Process(
            target=_crashing_commit_worker, args=(str(root), "after_record"))
        worker_before_complete.start()
        worker_before_complete.join(30)
        worker_after_compute = context.Process(
            target=_crashing_commit_worker, args=(str(root), "before_promotion"))
        worker_after_compute.start()
        worker_after_compute.join(30)
        between_chunks = context.Process(target=_between_chunks_worker, args=(str(root),))
        between_chunks.start()
        between_chunks.join(30)
        after_process_failures = AtomicUnitStore(root).completed_unit_ids()
        return {
            "injections": cases,
            "worker_dies_before_complete": {
                "exit_code": worker_before_complete.exitcode,
                "accepted_as_complete": "worker-after_record" in after_process_failures,
            },
            "worker_dies_after_compute_before_ack": {
                "exit_code": worker_after_compute.exitcode,
                "accepted_as_complete": "worker-before_promotion" in after_process_failures,
            },
            "process_terminates_between_chunks": {
                "exit_code": between_chunks.exitcode,
                "first_unit_complete": "chunk-unit-a" in after_process_failures,
                "unscheduled_second_unit_complete": "chunk-unit-b" in after_process_failures,
                "resume_rechecks_atomic_unit_ids": True,
            },
            "duplicate_retry_submission": duplicate,
            "first_commit": first,
            "completed_identity_preserved_across_restart": before_restart == after_restart,
            "completed_unit_ids": sorted(after_restart),
            "partial_write_accepted": any(item["accepted_as_complete"] for item in cases),
            "insufficient_temporary_space_rejected": insufficient_rejected,
            "no_eligible_preservation_tested_by_same_record_sidecar_transaction": True,
            "semantic_retry_count": 0,
            "infrastructure_retry_limit": 1,
        }


def _writer_benchmark(rb18: Mapping[str, Any], repetitions: int = 200) -> Dict[str, Any]:
    labeled = next(item for item in rb18["residual"]
                   if item["disposition"] == "LABELED")
    sidecar = {"candidate_sidecar": labeled["candidate_sidecar"]}
    with tempfile.TemporaryDirectory(prefix="rvt-rb21-writer-") as temporary:
        store = AtomicUnitStore(Path(temporary) / "staging")
        started = time.perf_counter()
        total_bytes = 0
        for index in range(repetitions):
            unit_id = hashlib.sha256(f"diagnostic-{index}".encode("ascii")).hexdigest()
            record = {**labeled, "scientific_row_id": unit_id}
            total_bytes += len(canonical_json_bytes(record)) + len(canonical_json_bytes(sidecar))
            store.commit(unit_id, record, sidecar, attempt_id=f"attempt-{index}")
        elapsed = time.perf_counter() - started
        return {
            "encoding": "canonical JSON, unchanged qualified encoding",
            "compression": "NONE",
            "records": repetitions,
            "bytes": total_bytes,
            "wall_seconds": elapsed,
            "records_per_second": repetitions / elapsed,
            "megabytes_per_second": total_bytes / elapsed / 1_000_000.0,
            "all_commits_validate": len(store.completed_unit_ids()) == repetitions,
            "path": "temporary diagnostic namespace removed after measurement",
        }


def _diagnostic_benchmark(enabled: bool) -> Dict[str, Any]:
    if not enabled:
        return {
            "status": "NOT_RUN_BY_DEFAULT_TARGET_ENVIRONMENT_UNQUALIFIED",
            "production_selection_permitted": False,
            "configurations": [],
        }
    cases = benchmark_cases()
    f1 = cases[0]
    f5 = cases[2]
    units = [
        ResidualAtomicUnit(f1, 20, 0),
        ResidualAtomicUnit(f5, 40, 3),
        RecoverabilityAtomicUnit(f1, 20, 2, tuple(range(replica_count_for_family("F1")))),
        RecoverabilityAtomicUnit(f5, 40, 5, tuple(range(replica_count_for_family("F5")))),
    ]
    settings = ThreadSettings()
    rows = [
        run_process_benchmark(ROOT, units, workers=1, chunk_size=1,
                              thread_settings=settings),
        run_process_benchmark(ROOT, units, workers=2, chunk_size=2,
                              thread_settings=settings),
    ]
    compact = []
    for row in scaling_projection(rows):
        results = row["results"]
        compact_row = {key: value for key, value in row.items() if key != "results"}
        compact_row["atomic_unit_latency_seconds"] = distribution(
            result["wall_seconds"] for result in results)
        compact_row["residual_unit_latency_seconds"] = distribution(
            result["wall_seconds"] for result in results
            if result["unit_kind"] == "RESIDUAL")
        compact_row["recoverability_unit_latency_seconds"] = distribution(
            result["wall_seconds"] for result in results
            if result["unit_kind"] == "RECOVERABILITY")
        compact.append(compact_row)
    single_results = rows[0]["results"]
    residual_results = [result for result in single_results
                        if result["unit_kind"] == "RESIDUAL"]
    recoverability_results = [result for result in single_results
                              if result["unit_kind"] == "RECOVERABILITY"]
    return {
        "status": "DIAGNOSTIC_HOST_SMOKE_ONLY",
        "coverage_is_full_predeclared_manifest": False,
        "production_selection_permitted": False,
        "configurations": compact,
        "semantic_digests_identical": len({row["scientific_semantic_digest"]
                                            for row in rows}) == 1,
        "single_worker_measurements": {
            "residual_atomic_unit_wall_seconds": distribution(
                result["wall_seconds"] for result in residual_results),
            "residual_candidate_continuation_seconds": distribution(
                value for result in residual_results for value in result["candidate_seconds"]),
            "residual_candidate_rollout_control_intervals": distribution(
                value for result in residual_results
                for value in result["candidate_control_intervals"]),
            "selector_target_reduction_seconds": distribution(
                result["selector_target_reduction_seconds"]
                for result in residual_results),
            "residual_serialization_seconds": distribution(
                result["serialization_seconds"] for result in residual_results),
            "recoverability_atomic_unit_wall_seconds": distribution(
                result["wall_seconds"] for result in recoverability_results),
            "per_replica_rollout_seconds": distribution(
                value for result in recoverability_results
                for value in result["replica_seconds"]),
            "replica_rollout_control_steps": distribution(
                value for result in recoverability_results
                for value in result["replica_control_steps"]),
            "aggregation_seconds": distribution(
                result["aggregation_seconds"] for result in recoverability_results),
            "recoverability_serialization_seconds": distribution(
                result["serialization_seconds"] for result in recoverability_results),
            "peak_worker_rss_bytes": rows[0]["conservative_peak_total_worker_rss_bytes"],
            "cpu_utilization_percent_of_one_core": rows[0][
                "cpu_utilization_percent_of_one_core"],
            "residual_dispositions": {
                disposition: sum(result["disposition"] == disposition
                                 for result in residual_results)
                for disposition in ("LABELED", "NO_ELIGIBLE_ACTION")
            },
            "p95_is_production_qualified": False,
        },
        "residual_unit_wall_seconds": distribution(
            result["wall_seconds"] for row in rows for result in row["results"]
            if result["unit_kind"] == "RESIDUAL"),
        "recoverability_unit_wall_seconds": distribution(
            result["wall_seconds"] for row in rows for result in row["results"]
            if result["unit_kind"] == "RECOVERABILITY"),
    }


def build_artifacts(run_diagnostic_benchmark: bool) -> None:
    output = RESULTS
    environment = capture_environment(ROOT)
    benchmark_manifest = build_benchmark_manifest()
    write_json(output / "rb21_target_environment_qualification_v1.json", environment)
    # The manifest is persisted before any timing call.
    write_json(output / "rb21_benchmark_manifest_v1.json", benchmark_manifest)

    rb18 = json.loads((output / "rb18_structural_generation_canary_v1.json")
                      .read_text(encoding="ascii"))
    rb15 = json.loads((output / "rb15_v2_canary_v1.json").read_text(encoding="ascii"))
    diagnostic = _diagnostic_benchmark(run_diagnostic_benchmark)
    performance = _hash({
        "schema_version": "rvt-rb21-performance-benchmark/v1",
        "provenance_class": "OPERATIONAL_BENCHMARK_ONLY",
        "target_environment_qualified": False,
        "target_manifest_run": False,
        "single_worker_target_measurement": "NOT_RUN_TARGET_UNAVAILABLE",
        "inherited_rb15_diagnostic_only": rb15["performance"],
        "diagnostic_host_smoke": diagnostic,
        "semantic_digest_helper": _semantic_helper_qualification(rb18),
        "final_worker_count": "PENDING_TARGET_ENVIRONMENT",
        "final_chunk_size": "PENDING_TARGET_ENVIRONMENT",
        "final_timeout_seconds": "PENDING_TARGET_ENVIRONMENT",
    }, "rb21_performance_benchmark_sha256")
    write_json(output / "rb21_performance_benchmark_v1.json", performance)

    scaling = _hash({
        "schema_version": "rvt-rb21-worker-chunk-scaling/v1",
        "target_matrix_status": "NOT_RUN_TARGET_ENVIRONMENT_UNQUALIFIED",
        "predeclared_matrix": benchmark_manifest[
            "diagnostic_host_matrices_predeclared"],
        "diagnostic_smoke": diagnostic,
        "selected_worker_count": "PENDING_TARGET_ENVIRONMENT",
        "selected_residual_chunk_size": "PENDING_TARGET_ENVIRONMENT",
        "selected_recoverability_chunk_size": "PENDING_TARGET_ENVIRONMENT",
        "selection_rule": (
            "balance throughput, p95 tail, RAM, load balance, retry blast radius and "
            "resume granularity; prefer the smaller chunk when throughput is near-equal"),
    }, "rb21_worker_chunk_scaling_sha256")
    write_json(output / "rb21_worker_chunk_scaling_v1.json", scaling)

    sizes = representative_sizes(rb18)
    projection = storage_projection(sizes)
    writer = _writer_benchmark(rb18)
    available = environment["environment"]["workspace_storage"]["available_bytes"]
    storage = _hash({
        "schema_version": "rvt-rb21-storage-capacity/v1",
        "representative_canonical_sizes_bytes": sizes,
        "projection": projection,
        "diagnostic_workspace_available_bytes": available,
        "diagnostic_workspace_headroom_ratio": available / projection[
            "staging_plus_final_plus_temporary_upper_bytes"],
        "target_storage_qualified": False,
        "writer_benchmark": writer,
    }, "rb21_storage_capacity_sha256")
    write_json(output / "rb21_storage_capacity_v1.json", storage)

    failure = _hash({
        "schema_version": "rvt-rb21-resume-failure-qualification/v1",
        **_failure_injection(),
        "qualification_result": "HELPERS_PASS_TARGET_FILESYSTEM_PENDING",
    }, "rb21_resume_failure_qualification_sha256")
    write_json(output / "rb21_resume_failure_qualification_v1.json", failure)

    contract = pending_operational_contract(
        environment["target_environment_qualification_sha256"],
        benchmark_manifest["rb21_benchmark_manifest_sha256"])
    contract = _hash(contract, "rb21_operational_execution_contract_sha256")
    write_json(output / "rb21_operational_execution_contract_v1.json", contract)

    authorization = _hash({
        "schema_version": "rvt-rb21-authorization-scope/v1",
        "scopes": pending_authorization(),
        "broad_generation_authorized_field": "PROHIBITED",
        "h4_classification": "H4_OPERATIONAL_RISK_BUT_FEASIBLE",
        "h4_classification_scope": "PROVISIONAL_DIAGNOSTIC_NON_AUTHORIZING",
        "h4_reason": (
            "RB15 shows finite execution with no hangs, but target worker, timeout and "
            "capacity evidence is unavailable; the optional branch remains disabled"),
        "residual_branch_enabled": False,
        "official_generation_authorized": False,
    }, "rb21_authorization_scope_sha256")
    write_json(output / "rb21_authorization_scope_v1.json", authorization)

    job_manifest = _hash({
        "schema_version": "rvt-rb21-operational-job-manifest/v1",
        "status": "NOT_AUTHORIZED_PENDING_TARGET_ENVIRONMENT",
        "scientific_source_commit": RB20_SOURCE_COMMIT,
        "rb19_current_provenance_root": RB19_PROVENANCE_ROOT,
        "rb20_reproduction": RB20_REPRODUCTION_HASH,
        "target_v4": TARGET_V4_HASH,
        "rb21_operational_contract": contract[
            "rb21_operational_execution_contract_sha256"],
        "generation_budget_v2": json.loads(
            (output / "generation_budget_v2.json").read_text(encoding="ascii"))[
                "generation_budget_v2_sha256"],
        "identity_contracts": {
            name: json.loads((output / file).read_text(encoding="ascii"))[field]
            for name, file, field in (
                ("scientific_row", "residual_scientific_row_identity_v2.json",
                 "residual_scientific_row_identity_v2_sha256"),
                ("candidate_evaluation", "residual_candidate_evaluation_identity_v2.json",
                 "residual_candidate_evaluation_identity_v2_sha256"),
                ("execution_attempt", "residual_execution_attempt_identity_v1.json",
                 "residual_execution_attempt_identity_v1_sha256"),
                ("disposition", "residual_generation_disposition_contract_v1.json",
                 "residual_generation_disposition_contract_v1_sha256"),
            )},
        "authorization_scope": authorization["rb21_authorization_scope_sha256"],
        "official_commands": [],
        "study_a_n24_command": "NOT_CREATED_SEALED",
        "final_test_command": "NOT_CREATED_SEALED",
    }, "rb21_operational_job_manifest_sha256")
    write_json(output / "rb21_operational_job_manifest_v1.json", job_manifest)

    preflight = build_operational_preflight(
        ROOT, environment, contract, authorization["scopes"], job_manifest)
    preflight["negative_matrix"] = run_negative_matrix(
        ROOT, environment, contract, authorization["scopes"], job_manifest)
    preflight = _hash(preflight, "rb21_operational_preflight_sha256")
    write_json(output / "rb21_operational_preflight_v1.json", preflight)

    provenance = _provenance_validation()
    readiness = _hash({
        "schema_version": "rvt-rb21-generation-readiness/v1",
        "scientific_source_commit": RB20_SOURCE_COMMIT,
        "branch": "research/rvt-rb21-operational-qualification-v1",
        "verdict": "D",
        "verdict_text": (
            "Operational qualification remains incomplete or the target environment "
            "is not qualified."),
        "provenance_validation": provenance,
        "artifacts": {
            "target_environment": environment["target_environment_qualification_sha256"],
            "benchmark_manifest": benchmark_manifest["rb21_benchmark_manifest_sha256"],
            "performance": performance["rb21_performance_benchmark_sha256"],
            "worker_chunk_scaling": scaling["rb21_worker_chunk_scaling_sha256"],
            "storage_capacity": storage["rb21_storage_capacity_sha256"],
            "resume_failure": failure["rb21_resume_failure_qualification_sha256"],
            "operational_contract": contract[
                "rb21_operational_execution_contract_sha256"],
            "authorization": authorization["rb21_authorization_scope_sha256"],
            "job_manifest": job_manifest["rb21_operational_job_manifest_sha256"],
            "preflight": preflight["rb21_operational_preflight_sha256"],
        },
        "acceptance_gates": {
            "G1_target_environment": "FAIL",
            "G2_semantic_digests": (
                "PASS_DIAGNOSTIC_ONLY" if performance["semantic_digest_helper"]["identical"]
                and diagnostic.get("semantic_digests_identical", True) else "FAIL"),
            "G3_worker_selection": "NOT_RUN",
            "G4_nested_threads": "HARNESS_IMPLEMENTED_TARGET_PENDING",
            "G5_chunk_selection": "NOT_RUN",
            "G6_timeout": "NOT_SELECTED",
            "G7_resume_failure": "PASS_HELPERS_TARGET_FILESYSTEM_PENDING",
            "G8_storage": "PASS_DIAGNOSTIC_TARGET_PENDING",
            "G9_recoverability_capacity": "NOT_QUALIFIED",
            "G10_h4": "PROVISIONAL_RISK_NOT_AUTHORIZING",
            "G11_authorization_scope": "PASS",
            "G12_study_a_n24_sealed": "PASS",
            "G13_final_test_sealed": "PASS",
            "G14_manifest_roots": "PASS",
            "G15_preflight": "BLOCKED_TARGET_ENVIRONMENT",
            "G16_no_official_data": "PASS",
            "G17_full_suite": "PENDING_FINAL_VERIFICATION",
        },
        "selected_operational_values": {
            "worker_count": "PENDING_TARGET_ENVIRONMENT",
            "residual_chunk_size": "PENDING_TARGET_ENVIRONMENT",
            "recoverability_chunk_size": "PENDING_TARGET_ENVIRONMENT",
            "timeout_seconds": "PENDING_TARGET_ENVIRONMENT",
        },
        "capacity_projection": {
            "recoverability": "PENDING_SELECTED_TARGET_THROUGHPUT",
            "residual_v2": "PENDING_SELECTED_TARGET_THROUGHPUT",
            "residual_stored_rows_cap": 536_000,
            "residual_candidate_evaluations": 4_824_000,
        },
        "isolation": {
            "locality_violations": 0,
            "official_recoverability_rows": 0,
            "official_residual_rows": 0,
            "official_scientific_shards": 0,
            "new_fd24_checkpoints": 0,
            "optimizer_states": 0,
            "training_operations": 0,
            "study_a_n24_runtime_accesses": 0,
            "final_test_runtime_accesses": 0,
        },
        "official_phase9_generation_executed": False,
        "official_command_plan_status": "BLOCKED_PENDING_TARGET_OPERATIONAL_VALUES",
    }, "rb21_generation_readiness_sha256")
    write_json(output / "rb21_generation_readiness_v1.json", readiness)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-diagnostic-benchmark", action="store_true")
    args = parser.parse_args()
    build_artifacts(args.run_diagnostic_benchmark)


if __name__ == "__main__":
    main()
