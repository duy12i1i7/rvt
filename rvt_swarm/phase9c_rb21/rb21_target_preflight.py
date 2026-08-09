"""Positive and negative operational preflight for qualified RB21 target jobs."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Mapping

from ..phase8.common import canonical_json_bytes
from ..phase9.preflight import build_preflight_audit
from .rb21_manifest import (
    RB19_PROVENANCE_ROOT,
    RB20_REPRODUCTION_HASH,
    RB21P_PORTABILITY_ARTIFACT_HASH,
    RB21P_QUALIFIED_IMAGE,
    RB21P_REQUALIFICATION_ROOT,
    RB21P_SOURCE_CHECKPOINT,
    TARGET_V4_HASH,
)
from .rb21_preflight import AUTHORIZATION_SCOPES


IMAGE_SOURCE_COMMIT = "8bfabd48969f1fa1e13a0a268a6df1cb366e90cc"


def _canonical_hash_valid(path: Path, field: str, expected: str) -> bool:
    try:
        document = json.loads(path.read_text(encoding="ascii"))
        observed = document[field]
    except (FileNotFoundError, KeyError, json.JSONDecodeError):
        return False
    body = {key: value for key, value in document.items() if key != field}
    return observed == expected == hashlib.sha256(canonical_json_bytes(body)).hexdigest()


def target_operational_checks(
        root: Path, environment: Mapping[str, Any], contract: Mapping[str, Any],
        authorization: Mapping[str, str], job_manifest: Mapping[str, Any]) -> list:
    def check(name: str, passed: bool, observed: Any) -> Dict[str, Any]:
        return {"name": name, "passed": bool(passed), "observed": observed}

    result_root = root / "results/rvt_fd24"
    scientific = build_preflight_audit(root)
    references = contract.get("references", {})
    threads = contract.get("nested_thread_settings", {})
    isolation = job_manifest.get("isolation", {})
    h4 = job_manifest.get("h4_classification")
    checks = [
        check("scientific_preflight", scientific.get("status") == "PASS",
              scientific.get("status")),
        check("portability_artifact",
              _canonical_hash_valid(
                  result_root / "rb21_cross_platform_numeric_portability_v1.json",
                  "rb21_cross_platform_numeric_portability_sha256",
                  RB21P_PORTABILITY_ARTIFACT_HASH),
              RB21P_PORTABILITY_ARTIFACT_HASH),
        check("portability_requalification_root",
              _canonical_hash_valid(
                  result_root / "rb21_portability_requalification_v1.json",
                  "rb21_portability_requalification_sha256",
                  RB21P_REQUALIFICATION_ROOT),
              RB21P_REQUALIFICATION_ROOT),
        check("target_host", environment.get("qualification_result") == "QUALIFIED"
              and environment.get("windows", {}).get("hostname") == "AVIS"
              and environment.get("wsl", {}).get("cpus") == 24,
              {"status": environment.get("qualification_result"),
               "windows": environment.get("windows"), "wsl": environment.get("wsl")}),
        check("qualified_image", environment.get("docker", {}).get("image_digest")
              == RB21P_QUALIFIED_IMAGE
              and contract.get("qualified_docker_image") == RB21P_QUALIFIED_IMAGE,
              contract.get("qualified_docker_image")),
        check("source_commits", contract.get("scientific_source_checkpoint")
              == RB21P_SOURCE_CHECKPOINT
              and contract.get("qualified_image_source_commit") == IMAGE_SOURCE_COMMIT,
              {"checkpoint": contract.get("scientific_source_checkpoint"),
               "image_source": contract.get("qualified_image_source_commit")}),
        check("scientific_roots", references.get("rb19_current_provenance_root")
              == RB19_PROVENANCE_ROOT
              and references.get("rb20_reproduction") == RB20_REPRODUCTION_HASH
              and references.get("target_v4") == TARGET_V4_HASH,
              references),
        check("portability_root_referenced", references.get("rb21p_portability_root")
              == RB21P_REQUALIFICATION_ROOT, references.get("rb21p_portability_root")),
        check("worker_count", isinstance(contract.get("process_worker_count"), int)
              and not isinstance(contract.get("process_worker_count"), bool)
              and contract["process_worker_count"] > 0,
              contract.get("process_worker_count")),
        check("nested_threads", set(threads) == {
                  "OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS",
                  "NUMEXPR_NUM_THREADS", "torch_num_threads",
                  "torch_num_interop_threads"}
              and set(threads.values()) == {1}, threads),
        check("chunk_sizes", all(isinstance(contract.get(name), int)
                                  and not isinstance(contract.get(name), bool)
                                  and contract[name] > 0 for name in (
                                      "residual_chunk_size_atomic_units",
                                      "recoverability_chunk_size_atomic_units")),
              {name: contract.get(name) for name in (
                  "residual_chunk_size_atomic_units",
                  "recoverability_chunk_size_atomic_units")}),
        check("timeout", isinstance(contract.get("infrastructure_timeout_seconds"),
                                    (int, float))
              and not isinstance(contract.get("infrastructure_timeout_seconds"), bool)
              and contract["infrastructure_timeout_seconds"] > 0
              and contract["infrastructure_timeout_seconds"] != 1800
              and contract.get("timeout_classification") == "INFRASTRUCTURE_FAILURE"
              and contract.get("timeout_changes_scientific_horizon") is False,
              contract.get("infrastructure_timeout_seconds")),
        check("resume", contract.get("resume_granularity")
              == "ATOMIC_SCIENTIFIC_UNIT_IDENTITY"
              and contract.get("semantic_retries") == 0,
              contract.get("resume_granularity")),
        check("writer_staging", contract.get("writer_mode")
              == "STAGING_VALIDATE_ATOMIC_PROMOTION"
              and contract.get("partial_staging_is_completed_dataset") is False,
              contract.get("writer_mode")),
        check("authorization_scopes", set(authorization) == set(AUTHORIZATION_SCOPES),
              sorted(authorization)),
        check("h4_authorization", h4 != "H4_OPERATIONALLY_INFEASIBLE"
              or not authorization.get("RESIDUAL_V2_GENERATION", "").startswith(
                  "AUTHORIZED"),
              {"h4": h4, "residual": authorization.get("RESIDUAL_V2_GENERATION")}),
        check("study_a_n24_sealed", authorization.get("STUDY_A_N24_ZERO_SHOT")
              == "SEALED_NOT_AUTHORIZED", authorization.get("STUDY_A_N24_ZERO_SHOT")),
        check("final_test_sealed", authorization.get("FINAL_TEST")
              == "SEALED_NOT_AUTHORIZED", authorization.get("FINAL_TEST")),
        check("no_broad_authorization", "generation_authorized" not in authorization
              and "generation_authorized" not in job_manifest,
              sorted(job_manifest)),
        check("low_vs_production_projection", job_manifest.get(
              "low_vs_production_scientific_projection_equal") is True,
              job_manifest.get("low_vs_production_scientific_projection_equal")),
        check("no_official_execution", all(isolation.get(name) == 0 for name in (
                  "official_recoverability_rows", "official_residual_rows",
                  "official_scientific_shards", "checkpoints", "optimizer_states",
                  "training_operations", "study_a_n24_runtime_accesses",
                  "final_test_runtime_accesses")), isolation),
        check("sealed_commands_absent",
              job_manifest.get("study_a_n24_command") == "NOT_CREATED_SEALED"
              and job_manifest.get("final_test_command") == "NOT_CREATED_SEALED",
              {"n24": job_manifest.get("study_a_n24_command"),
               "final": job_manifest.get("final_test_command")}),
    ]
    return checks


def build_target_operational_preflight(
        root: Path, environment: Mapping[str, Any], contract: Mapping[str, Any],
        authorization: Mapping[str, str], job_manifest: Mapping[str, Any]) -> Dict[str, Any]:
    checks = target_operational_checks(
        root, environment, contract, authorization, job_manifest)
    failures = [row["name"] for row in checks if not row["passed"]]
    return {
        "schema_version": "rvt-rb21-target-operational-preflight/v2",
        "checks": checks,
        "check_count": len(checks),
        "failures": failures,
        "status": "PASS" if not failures else "BLOCKED",
        "study_a_n24_outcomes_loaded": False,
        "final_test_geometry_loaded": False,
    }


def run_target_negative_matrix(
        root: Path, environment: Mapping[str, Any], contract: Mapping[str, Any],
        authorization: Mapping[str, str], job_manifest: Mapping[str, Any]) -> Dict[str, Any]:
    cases = []

    def add(name: str, mutate) -> None:
        env = deepcopy(environment)
        con = deepcopy(contract)
        auth = deepcopy(authorization)
        job = deepcopy(job_manifest)
        mutate(env, con, auth, job)
        checks = target_operational_checks(root, env, con, auth, job)
        cases.append({
            "case": name,
            "rejected": any(not row["passed"] for row in checks),
            "failed_checks": [row["name"] for row in checks if not row["passed"]],
        })

    add("wrong host", lambda e, c, a, j: e["windows"].update(hostname="OTHER"))
    add("wrong image digest", lambda e, c, a, j:
        c.update(qualified_docker_image="sha256:" + "0" * 64))
    add("wrong source commit", lambda e, c, a, j:
        c.update(scientific_source_checkpoint="0" * 40))
    add("wrong worker count", lambda e, c, a, j: c.update(process_worker_count=0))
    add("nested oversubscription", lambda e, c, a, j:
        c["nested_thread_settings"].update(OMP_NUM_THREADS=8))
    add("wrong chunk", lambda e, c, a, j:
        c.update(residual_chunk_size_atomic_units=0))
    add("stale 1800 second timeout", lambda e, c, a, j:
        c.update(infrastructure_timeout_seconds=1800))
    add("missing resume contract", lambda e, c, a, j: c.pop("resume_granularity"))
    add("wrong staging mode", lambda e, c, a, j: c.update(writer_mode="DIRECT_FINAL"))
    add("Study A N24 enabled", lambda e, c, a, j:
        a.update(STUDY_A_N24_ZERO_SHOT="AUTHORIZED"))
    add("final test enabled", lambda e, c, a, j: a.update(FINAL_TEST="AUTHORIZED"))
    add("H4 enabled while infeasible", lambda e, c, a, j: (
        j.update(h4_classification="H4_OPERATIONALLY_INFEASIBLE"),
        a.update(RESIDUAL_V2_GENERATION="AUTHORIZED")))
    add("stale scientific root", lambda e, c, a, j:
        c["references"].update(rb19_current_provenance_root="0" * 64))
    add("missing portability root", lambda e, c, a, j:
        c["references"].pop("rb21p_portability_root"))
    add("broad authorization flag", lambda e, c, a, j:
        j.update(generation_authorized=True))
    return {
        "cases": cases,
        "case_count": len(cases),
        "escapes": sum(not row["rejected"] for row in cases),
    }
