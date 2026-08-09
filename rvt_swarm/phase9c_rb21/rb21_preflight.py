"""Operational preflight layered on the unchanged scientific preflight."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Mapping

from ..phase9.preflight import build_preflight_audit
from .rb21_manifest import RB19_PROVENANCE_ROOT, RB20_REPRODUCTION_HASH, TARGET_V4_HASH

PENDING = "PENDING_TARGET_ENVIRONMENT"

AUTHORIZATION_SCOPES = (
    "RECOVERABILITY_GENERATION",
    "RESIDUAL_V2_GENERATION",
    "STUDY_A_TRAIN_VALIDATION",
    "STUDY_A_N24_ZERO_SHOT",
    "STUDY_B",
    "FINAL_TEST",
)


def pending_operational_contract(environment_hash: str,
                                 benchmark_manifest_hash: str) -> Dict[str, Any]:
    return {
        "schema_version": "rvt-rb21-operational-execution-contract/v1",
        "status": "PROPOSAL_PENDING_TARGET_ENVIRONMENT",
        "references": {
            "rb19_current_provenance_root": RB19_PROVENANCE_ROOT,
            "rb20_reproduction": RB20_REPRODUCTION_HASH,
            "target_v4": TARGET_V4_HASH,
            "target_environment_qualification": environment_hash,
            "benchmark_manifest": benchmark_manifest_hash,
        },
        "target_environment_id": PENDING,
        "process_worker_count": PENDING,
        "nested_thread_settings": {
            "OMP_NUM_THREADS": 1, "MKL_NUM_THREADS": 1,
            "OPENBLAS_NUM_THREADS": 1, "torch_num_threads": 1,
            "torch_num_interop_threads": 1,
        },
        "atomic_units": {
            "residual": "ONE_DECISION_ONE_ROBOT_ALL_NINE_CANDIDATES",
            "recoverability": "ONE_DECISION_ONE_CANDIDATE_ALL_FROZEN_REPLICAS",
        },
        "residual_chunk_size_atomic_units": PENDING,
        "recoverability_chunk_size_atomic_units": PENDING,
        "infrastructure_timeout_seconds": PENDING,
        "timeout_classification": "INFRASTRUCTURE_FAILURE",
        "timeout_changes_scientific_horizon": False,
        "semantic_retries": 0,
        "infrastructure_retries": 1,
        "resume_granularity": "ATOMIC_SCIENTIFIC_UNIT_IDENTITY",
        "writer_mode": "STAGING_VALIDATE_ATOMIC_PROMOTION",
        "writer_buffer_settings": PENDING,
        "partial_staging_is_completed_dataset": False,
        "completion_policy": {
            "all_scheduled_source_tasks_accounted_for": True,
            "every_legitimate_attempt_has_terminal_disposition": True,
            "unresolved_infrastructure_failures": 0,
            "unexpected_duplicates": 0,
            "shard_index_hashes_validate": True,
            "denominator_counts_reconcile": True,
            "sealed_domain_violations": 0,
        },
        "promotion_policy": "STAGING_THEN_VALIDATE_THEN_ATOMIC_FINAL_PROMOTION",
        "scientific_contracts_redefined": False,
    }


def pending_authorization() -> Dict[str, str]:
    return {
        "RECOVERABILITY_GENERATION": "NOT_AUTHORIZED_TARGET_ENVIRONMENT_PENDING",
        "RESIDUAL_V2_GENERATION": "NOT_AUTHORIZED_TARGET_ENVIRONMENT_AND_H4_PENDING",
        "STUDY_A_TRAIN_VALIDATION": "NOT_AUTHORIZED",
        "STUDY_A_N24_ZERO_SHOT": "SEALED_NOT_AUTHORIZED",
        "STUDY_B": "NOT_AUTHORIZED",
        "FINAL_TEST": "SEALED_NOT_AUTHORIZED",
    }


def operational_checks(scientific: Mapping[str, Any], environment: Mapping[str, Any],
                       contract: Mapping[str, Any], authorization: Mapping[str, str],
                       job_manifest: Mapping[str, Any]) -> list:
    def check(name: str, passed: bool, observed: Any) -> Dict[str, Any]:
        return {"name": name, "passed": bool(passed), "observed": observed}

    threads = contract.get("nested_thread_settings", {})
    worker = contract.get("process_worker_count")
    residual_chunk = contract.get("residual_chunk_size_atomic_units")
    recoverability_chunk = contract.get("recoverability_chunk_size_atomic_units")
    timeout = contract.get("infrastructure_timeout_seconds")
    checks = [
        check("scientific_preflight", scientific.get("status") == "PASS",
              scientific.get("status")),
        check("target_environment", environment.get("qualification_result") == "QUALIFIED",
              environment.get("qualification_result")),
        check("worker_count", isinstance(worker, int) and not isinstance(worker, bool)
              and worker > 0, worker),
        check("nested_threads", set(threads.values()) == {1}, threads),
        check("chunk_sizes", all(isinstance(value, int) and not isinstance(value, bool)
                                 and value > 0
                                 for value in (residual_chunk, recoverability_chunk)),
              [residual_chunk, recoverability_chunk]),
        check("timeout", isinstance(timeout, (int, float)) and not isinstance(timeout, bool)
              and timeout > 0 and contract.get("timeout_classification")
              == "INFRASTRUCTURE_FAILURE"
              and contract.get("timeout_changes_scientific_horizon") is False, timeout),
        check("resume_contract", contract.get("resume_granularity")
              == "ATOMIC_SCIENTIFIC_UNIT_IDENTITY", contract.get("resume_granularity")),
        check("writer_staging", contract.get("writer_mode")
              == "STAGING_VALIDATE_ATOMIC_PROMOTION"
              and contract.get("partial_staging_is_completed_dataset") is False,
              contract.get("writer_mode")),
        check("scientific_roots",
              contract.get("references", {}).get("rb19_current_provenance_root")
              == RB19_PROVENANCE_ROOT
              and contract.get("references", {}).get("rb20_reproduction")
              == RB20_REPRODUCTION_HASH
              and contract.get("references", {}).get("target_v4") == TARGET_V4_HASH,
              contract.get("references")),
        check("authorization_scopes", set(authorization) == set(AUTHORIZATION_SCOPES),
              sorted(authorization)),
        check("residual_h4_authorization",
              not authorization.get("RESIDUAL_V2_GENERATION", "").startswith("AUTHORIZED")
              or job_manifest.get("h4_classification")
              == "H4_OPERATIONALLY_FEASIBLE",
              {"residual": authorization.get("RESIDUAL_V2_GENERATION"),
               "h4": job_manifest.get("h4_classification")}),
        check("no_broad_authorization", "generation_authorized" not in authorization
              and "generation_authorized" not in job_manifest,
              sorted(job_manifest)),
        check("study_a_n24_sealed",
              authorization.get("STUDY_A_N24_ZERO_SHOT") == "SEALED_NOT_AUTHORIZED",
              authorization.get("STUDY_A_N24_ZERO_SHOT")),
        check("final_test_sealed",
              authorization.get("FINAL_TEST") == "SEALED_NOT_AUTHORIZED",
              authorization.get("FINAL_TEST")),
        check("job_manifest_roots",
              job_manifest.get("rb19_current_provenance_root") == RB19_PROVENANCE_ROOT
              and job_manifest.get("rb20_reproduction") == RB20_REPRODUCTION_HASH,
              {"rb19": job_manifest.get("rb19_current_provenance_root"),
               "rb20": job_manifest.get("rb20_reproduction")}),
    ]
    return checks


def build_operational_preflight(root: Path, environment: Mapping[str, Any],
                                contract: Mapping[str, Any],
                                authorization: Mapping[str, str],
                                job_manifest: Mapping[str, Any]) -> Dict[str, Any]:
    scientific = build_preflight_audit(root)
    checks = operational_checks(scientific, environment, contract,
                                authorization, job_manifest)
    failures = [item["name"] for item in checks if not item["passed"]]
    return {
        "schema_version": "rvt-rb21-operational-preflight/v1",
        "scientific_preflight_status": scientific["status"],
        "scientific_check_count": len(scientific["checks"]),
        "scientific_failures": [item["name"] for item in scientific["checks"]
                                if not item["passed"]],
        "operational_checks": checks,
        "operational_failures": failures,
        "status": "PASS" if not failures else "BLOCKED_TARGET_ENVIRONMENT",
        "final_test_geometry_loaded": False,
        "study_a_n24_outcomes_loaded": False,
    }


def run_negative_matrix(root: Path, environment: Mapping[str, Any],
                        contract: Mapping[str, Any], authorization: Mapping[str, str],
                        job_manifest: Mapping[str, Any]) -> Mapping[str, Any]:
    """Mutations must fail; this never reads sealed data or executes science."""
    cases = []

    qualified_environment = deepcopy(environment)
    qualified_environment["qualification_result"] = "QUALIFIED"
    qualified_contract = deepcopy(contract)
    qualified_contract.update({
        "target_environment_id": qualified_environment["current_environment_id"],
        "process_worker_count": 2,
        "residual_chunk_size_atomic_units": 2,
        "recoverability_chunk_size_atomic_units": 2,
        "infrastructure_timeout_seconds": 900,
    })

    def add(name: str, mutate) -> None:
        env = deepcopy(qualified_environment)
        con = deepcopy(qualified_contract)
        auth = deepcopy(authorization)
        job = deepcopy(job_manifest)
        mutate(env, con, auth, job)
        scientific = build_preflight_audit(root)
        checks = operational_checks(scientific, env, con, auth, job)
        cases.append({"case": name, "rejected": any(not row["passed"] for row in checks)})

    add("wrong target environment", lambda e, c, a, j: e.update(
        qualification_result="TARGET_ENVIRONMENT_NOT_QUALIFIED"))
    add("wrong worker count", lambda e, c, a, j: c.update(process_worker_count=0))
    add("nested-thread oversubscription", lambda e, c, a, j:
        c["nested_thread_settings"].update(torch_num_threads=8))
    add("wrong chunk size", lambda e, c, a, j:
        c.update(residual_chunk_size_atomic_units=0))
    add("stale timeout", lambda e, c, a, j:
        c.update(infrastructure_timeout_seconds=1800,
                 timeout_classification="VALID_TASK_NEGATIVE"))
    add("missing resume contract", lambda e, c, a, j: c.pop("resume_granularity"))
    add("wrong writer staging mode", lambda e, c, a, j:
        c.update(writer_mode="DIRECT_FINAL_WRITE"))
    add("residual enabled despite H4 unresolved", lambda e, c, a, j:
        a.update(RESIDUAL_V2_GENERATION="AUTHORIZED"))
    add("Study A N24 enabled", lambda e, c, a, j:
        a.update(STUDY_A_N24_ZERO_SHOT="AUTHORIZED"))
    add("final-test enabled", lambda e, c, a, j: a.update(FINAL_TEST="AUTHORIZED"))
    add("stale scientific root", lambda e, c, a, j:
        c["references"].update(rb19_current_provenance_root="0" * 64))
    add("missing RB20 reproduction", lambda e, c, a, j:
        j.update(rb20_reproduction=None))
    add("unauthorized broad execution state", lambda e, c, a, j:
        j.update(generation_authorized=True))
    return {
        "cases": cases,
        "case_count": len(cases),
        "escapes": sum(not item["rejected"] for item in cases),
    }
