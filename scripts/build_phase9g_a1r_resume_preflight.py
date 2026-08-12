#!/usr/bin/env python3
"""Reconcile the zero-escape Phase 9G-A1R official-resume preflight."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from rvt_swarm.phase8.common import attach_canonical_hash, sha256_document


def _canonical(path: Path, field: str) -> dict:
    document = json.loads(path.read_text(encoding="ascii"))
    body = dict(document)
    expected = str(body.pop(field, ""))
    if len(expected) != 64 or sha256_document(body) != expected:
        raise ValueError(f"canonical artifact mismatch: {path.name}")
    return document


def _file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _test_result(path: Path, command: str) -> dict:
    text = path.read_text(encoding="utf-8")
    matches = re.findall(r"(?m)^(\d+) passed(?:[^\n]*)$", text)
    if not matches or " failed" in text or " error" in text.lower():
        raise ValueError(f"test log is not a clean pass: {path}")
    xfailed = re.findall(r"(\d+) xfailed", text)
    return {
        "command": command,
        "passed": int(matches[-1]),
        "failed": 0,
        "errors": 0,
        "publication_required_xfailed": int(xfailed[-1]) if xfailed else 0,
        "log_file_sha256": _file_sha(path),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--target-observation", type=Path, required=True)
    parser.add_argument("--checkpoint-recheck", type=Path, required=True)
    parser.add_argument("--resolve-output", type=Path, required=True)
    parser.add_argument("--focused-test-log", type=Path, required=True)
    parser.add_argument("--full-test-log", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    results = root / "results/rvt_fd24"
    observation = _canonical(
        args.target_observation,
        "phase9g_a1r_target_preflight_observation_sha256",
    )
    initial = _canonical(
        results / "phase9g_a1r_staging_checkpoint_v1.json",
        "phase9g_a1r_staging_checkpoint_sha256",
    )
    recheck = _canonical(
        args.checkpoint_recheck,
        "phase9g_a1r_staging_checkpoint_sha256",
    )
    amendment = _canonical(
        results / "phase9g_a1r_operational_contract_amendment_v1.json",
        "phase9g_a1r_operational_contract_amendment_sha256",
    )
    authorization = _canonical(
        results / "phase9g_a1r_authorization_continuation_v1.json",
        "phase9g_a1r_authorization_continuation_sha256",
    )
    run = _canonical(
        results / "phase9g_a1r_continuation_run_identity_v1.json",
        "phase9g_a1r_continuation_run_identity_sha256",
    )
    failure = _canonical(
        results / "phase9g_a1r_timeout_failure_injection_result_v1.json",
        "phase9g_a1r_timeout_failure_injection_result_sha256",
    )
    resolution = json.loads(args.resolve_output.read_text(encoding="ascii"))
    if initial["staging_checkpoint_preimage_sha256"] != recheck[
        "staging_checkpoint_preimage_sha256"
    ]:
        raise ValueError("target staging checkpoint changed before preflight")
    if initial["phase9g_a1r_staging_checkpoint_sha256"] != recheck[
        "phase9g_a1r_staging_checkpoint_sha256"
    ]:
        raise ValueError("target staging checkpoint artifact changed before preflight")
    expected_resolution = {
        "total_event_identities": 6000,
        "completed_event_identities_reused": 127,
        "unresolved_event_identities_scheduled": 5873,
        "existing_rows_reemitted": 0,
        "scientific_retry_count": 0,
        "workers": 12,
        "numeric_threads": 1,
        "chunk_size_atomic_units": 1,
        "infrastructure_timeout_seconds": 243.0,
        "official_generation_execution_authorized": True,
    }
    if any(resolution.get(key) != value for key, value in expected_resolution.items()):
        raise ValueError("resolve-only continuation output differs from contract")
    if observation["production_image"] != run["production_image"]:
        raise ValueError("target image differs from run identity")
    if observation["staging"]["train_writable"]:
        raise ValueError("staging became writable before the preflight gate")
    if observation["active_or_stopped_phase9g_containers"]:
        raise ValueError("phase generation container exists before resume")
    if failure["status"] != "PASS":
        raise ValueError("timeout failure injection is not qualified")
    if resolution["sealed_scope"] != run["sealed_scope"]:
        raise ValueError("resolve-only sealed counters differ from run identity")
    if any(resolution["sealed_scope"].values()):
        raise ValueError("sealed-scope escape is nonzero")

    focused = _test_result(
        args.focused_test_log,
        (
            "PYTHONPATH=. pytest -q tests/test_phase9g_a1r_checkpoint.py "
            "tests/test_phase9g_a1r_continuation.py tests/test_phase9c_timeout_path.py "
            "tests/test_phase9g0p_operational.py "
            "tests/test_phase9g0r_official_binding.py "
            "tests/test_phase9g_a1_authorization.py tests/test_phase9_preflight.py"
        ),
    )
    full = _test_result(args.full_test_log, "PYTHONPATH=. pytest -q")
    if focused["publication_required_xfailed"] or full[
        "publication_required_xfailed"
    ]:
        raise ValueError("publication-required test remains xfailed")
    document = {
        "schema_version": "rvt-phase9g-a1r-resume-preflight/v1",
        "status": "PASS_ZERO_ESCAPES",
        "target": {
            "endpoint": observation["target_endpoint"],
            "hostname": observation["hostname"],
            "wsl_distribution": observation["wsl_distribution"],
            "production_image": observation["production_image"],
            "qualified_checkout_commit": observation["checkout_commit"],
            "qualified_checkout_clean": (
                observation["checkout_status_porcelain"] == ""
            ),
            "continuation_wrapper_sha256": observation["deploy_file_sha256"][
                "scripts/run_phase9g_a1r_recoverability_continuation.py"
            ],
            "active_phase_containers": 0,
        },
        "scientific_bindings": {
            "source_commit": run["source_commit"],
            "generation_provenance_root": authorization["bindings"][
                "generation_provenance_root"
            ],
            "scientific_addendum_sha256": authorization["bindings"][
                "scientific_addendum_sha256"
            ],
            "job_manifest_sha256": authorization["bindings"][
                "job_manifest_sha256"
            ],
            "frozen_science_changed": amendment["frozen_science_changed"],
        },
        "run_lineage": {
            "parent_run_id": run["parent_run_id"],
            "continuation_run_id": run["run_id"],
            "same_staging_namespace": run["same_staging_namespace_as_parent"],
            "logically_independent_dataset": run[
                "logically_independent_dataset"
            ],
            "run_identity_sha256": run[
                "phase9g_a1r_continuation_run_identity_sha256"
            ],
            "authorization_continuation_sha256": authorization[
                "phase9g_a1r_authorization_continuation_sha256"
            ],
            "operational_amendment_sha256": amendment[
                "phase9g_a1r_operational_contract_amendment_sha256"
            ],
        },
        "staging": {
            "read_only_during_preflight": True,
            "initial_rows": initial["scientific_row_count"],
            "initial_transactions": initial["transaction_count"],
            "initial_completed_atomic_units": initial[
                "completed_atomic_unit_count"
            ],
            "checkpoint_preimage_sha256": initial[
                "staging_checkpoint_preimage_sha256"
            ],
            "checkpoint_exact_recheck": True,
            "duplicate_rows": initial["duplicate_scientific_row_identities"],
            "partial_transactions": initial[
                "partial_candidate_pair_publications"
            ],
            "partial_files": initial["partial_writer_files"],
        },
        "resume_boundary": expected_resolution,
        "profile": amendment["recoverability_profile"],
        "timeout_failure_injection_sha256": failure[
            "phase9g_a1r_timeout_failure_injection_result_sha256"
        ],
        "tests": {"focused": focused, "full_suite": full},
        "sealed_domains": {
            "study_a_n24_all_manifest_jobs_sealed": observation[
                "frozen_manifest_scope"
            ]["study_a_n24_all_sealed"],
            "study_a_n24_accesses": 0,
            "study_b_accesses": 0,
            "final_test_accesses": 0,
            "residual_operations": 0,
            "training_operations": 0,
        },
        "storage_free_bytes": observation["storage"]["free_bytes"],
        "staging_write_permission_transition": {
            "occurred_before_preflight": False,
            "authorized_after_this_gate": True,
            "scope": "existing Study-A train Recoverability staging directory only",
        },
        "official_resume_authorized": True,
    }
    document = attach_canonical_hash(
        document, "phase9g_a1r_resume_preflight_sha256"
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(document, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )


if __name__ == "__main__":
    main()
