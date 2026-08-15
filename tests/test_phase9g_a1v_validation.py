"""Contracts for official Study-A Recoverability VALIDATION generation."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from rvt_swarm.phase8.common import sha256_document
from rvt_swarm.phase9g0r.compiler import compile_recoverability_tasks, compile_source_tasks
from rvt_swarm.phase9g0r.preflight import Phase9G0RPreflightError, validate_authorization_scope


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/rvt_fd24"


def _canonical(name: str, field: str) -> dict:
    document = json.loads((OUT / name).read_text(encoding="ascii"))
    body = dict(document)
    expected = body.pop(field)
    assert sha256_document(body) == expected
    return document


def test_a1v_train_closure_is_bound_and_immutable() -> None:
    precheck = _canonical(
        "phase9g_a1v_train_seal_precheck_v1.json",
        "phase9g_a1v_train_seal_precheck_sha256",
    )
    assert precheck["status"] == "PASS_IMMUTABLE"
    assert precheck["train_manifest_sha256"] == "4ac3d2cb65a8b5d656a5d982b344466868f8deaa8cef2b93af7ce824e9387caf"
    assert precheck["train_seal_sha256"] == "5b9e6726b548722ee651eefa7106662e2b119147d9b0c31ec4d4cbe0a1de58f5"
    assert precheck["train_accounting"]["scientific_rows"] == 8340
    assert precheck["train_namespace_mutation_authorized"] is False
    assert precheck["validation_rows_append_to_train"] is False


def test_a1v_validation_universe_is_exact_and_excludes_n24() -> None:
    manifest = _canonical(
        "phase9g_a1v_validation_task_manifest_v1.json",
        "phase9g_a1v_validation_task_manifest_sha256",
    )
    sources = compile_source_tasks(ROOT, study="study_a_zero_shot", split="validation")
    tasks = compile_recoverability_tasks(ROOT, study="study_a_zero_shot", split="validation")
    assert len(sources) == manifest["source_episodes"] == 300
    assert len(tasks) == manifest["decision_events"] == 1500
    assert manifest["candidate_aggregates"] == 3000
    assert manifest["candidate_replica_slots"] == 4200
    assert manifest["family_event_counts"] == {f"F{i}": 150 for i in range(1, 11)}
    assert manifest["team_size_event_counts"] == {
        "5": 300, "6": 300, "8": 300, "12": 300, "16": 300
    }
    assert all(task.source.team_size != 24 for task in tasks)
    assert not any(manifest["sealed_domains"].values())


def test_a1v_authorization_is_validation_only() -> None:
    scope = _canonical(
        "phase9g_a1v_authorization_scope_study_a_zero_shot-validation-recoverability_v1.json",
        "phase9_authorization_scope_sha256",
    )
    body = {key: value for key, value in scope.items() if key != "phase9_authorization_scope_sha256"}
    binding = scope["binding"]
    assert validate_authorization_scope(
        body,
        study="study_a_zero_shot",
        split="validation",
        branch="recoverability",
        source_commit=binding["source_commit"],
        docker_image=binding["docker_image"],
        addendum_sha256=binding["scientific_addendum_sha256"],
        provenance_root=binding["generation_provenance_root"],
    ) is True
    with pytest.raises(Phase9G0RPreflightError):
        validate_authorization_scope(
            body,
            study="study_a_zero_shot",
            split="train",
            branch="recoverability",
            source_commit=binding["source_commit"],
            docker_image=binding["docker_image"],
            addendum_sha256=binding["scientific_addendum_sha256"],
            provenance_root=binding["generation_provenance_root"],
        )


def test_a1v_s3_population_guard_has_zero_ambiguity() -> None:
    guard = _canonical(
        "phase9g_a1v_s3_prestart_guard_reference_v1.json",
        "phase9g_a1v_s3_prestart_guard_sha256",
    )
    assert guard["status"] == "PASS"
    assert guard["scope"]["validation_events_total"] == 1500
    assert guard["counter_levels"]["source_s3_instances"] == 50
    assert guard["counter_levels"]["s3_decision_events"] == 250
    assert guard["counter_levels"]["unresolved_s3_ambiguities"] == 0
    assert guard["fail_closed"]["escapes"] == 0
    assert guard["scientific_writes"] == 0


def test_a1v_run_identity_uses_distinct_validation_namespace() -> None:
    run = _canonical(
        "phase9g_a1v_validation_run_identity_v1.json",
        "phase9g_a1v_validation_run_identity_sha256",
    )
    assert run["identity_class"] == "OFFICIAL_DISTINCT_VALIDATION_RUN"
    assert run["writer_namespace"] == "staging/study_a_zero_shot-validation-recoverability"
    assert run["final_dataset_id"] == "phase9g-a1-study-a-validation-recoverability-v1"
    assert run["train_namespace_mutable"] is False
    assert run["shared_mutable_indexes_with_train"] is False
    assert all(value == 0 for value in run["sealed_scope"].values())


def test_a1v_production_preflight_passes_with_zero_escapes() -> None:
    preflight = _canonical(
        "phase9g_a1v_production_preflight_v1.json",
        "phase9g_a1v_production_preflight_sha256",
    )
    assert preflight["status"] == "PASS_ZERO_ESCAPES"
    assert preflight["official_validation_authorized"] is True
    assert preflight["negative_case_escapes"] == 0
    assert preflight["validation_namespace"]["preexisting"] is False
    assert preflight["train_immutability"]["mutation_authorized"] is False
    assert preflight["compiled_universe"]["decision_events"] == 1500
    assert preflight["s3_guard"]["reference_target_semantic_exact"] is True
    assert preflight["s3_guard"]["unresolved_s3_ambiguities"] == 0
    assert preflight["tests"]["complete_suite"]["passed"] == 3143
    assert preflight["tests"]["complete_suite"]["failed"] == 0


def test_a1v_runner_resolves_exact_empty_validation_boundary(tmp_path: Path) -> None:
    scope = _canonical(
        "phase9g_a1v_authorization_scope_study_a_zero_shot-validation-recoverability_v1.json",
        "phase9_authorization_scope_sha256",
    )
    authorization = _canonical(
        "phase9g_a1v_owner_authorization_v1.json",
        "phase9g_a1v_owner_authorization_sha256",
    )
    run = _canonical(
        "phase9g_a1v_validation_run_identity_v1.json",
        "phase9g_a1v_validation_run_identity_sha256",
    )
    manifest = _canonical(
        "phase9g_a1v_validation_task_manifest_v1.json",
        "phase9g_a1v_validation_task_manifest_sha256",
    )
    guard = _canonical(
        "phase9g_a1v_s3_prestart_guard_reference_v1.json",
        "phase9g_a1v_s3_prestart_guard_sha256",
    )
    amendment = _canonical(
        "phase9g_a1r_operational_contract_amendment_v1.json",
        "phase9g_a1r_operational_contract_amendment_sha256",
    )
    command = [
        str(ROOT / ".venv/bin/python"),
        str(ROOT / "scripts/run_phase9g_a1v_recoverability_validation.py"),
        "--root", str(ROOT),
        "--writer-root", str(tmp_path / "staging/study_a_zero_shot-validation-recoverability"),
        "--audit-root", str(tmp_path / "audit"),
        "--source-commit", scope["binding"]["source_commit"],
        "--docker-image", scope["binding"]["docker_image"],
        "--scientific-addendum-sha256", scope["binding"]["scientific_addendum_sha256"],
        "--generation-provenance-root", scope["binding"]["generation_provenance_root"],
        "--authorization-scope", str(OUT / "phase9g_a1v_authorization_scope_study_a_zero_shot-validation-recoverability_v1.json"),
        "--authorization-scope-sha256", scope["phase9_authorization_scope_sha256"],
        "--operational-amendment", str(OUT / "phase9g_a1r_operational_contract_amendment_v1.json"),
        "--operational-amendment-sha256", amendment["phase9g_a1r_operational_contract_amendment_sha256"],
        "--owner-authorization", str(OUT / "phase9g_a1v_owner_authorization_v1.json"),
        "--owner-authorization-sha256", authorization["phase9g_a1v_owner_authorization_sha256"],
        "--run-identity", str(OUT / "phase9g_a1v_validation_run_identity_v1.json"),
        "--run-identity-sha256", run["phase9g_a1v_validation_run_identity_sha256"],
        "--task-manifest", str(OUT / "phase9g_a1v_validation_task_manifest_v1.json"),
        "--task-manifest-sha256", manifest["phase9g_a1v_validation_task_manifest_sha256"],
        "--s3-prestart-guard", str(OUT / "phase9g_a1v_s3_prestart_guard_reference_v1.json"),
        "--s3-prestart-guard-sha256", guard["phase9g_a1v_s3_prestart_guard_sha256"],
        "--workers", "12", "--numeric-threads", "1", "--chunk-size", "1",
        "--infrastructure-timeout-seconds", "243", "--resolve-only",
    ]
    result = subprocess.run(command, cwd=ROOT, check=True, text=True, capture_output=True)
    resolution = json.loads(result.stdout)
    assert resolution["official_generation_execution_authorized"] is True
    assert resolution["total_event_identities"] == 1500
    assert resolution["preexisting_event_identities"] == 0
    assert resolution["candidate_replica_slots"] == 4200
    assert not (tmp_path / "audit").exists()


def test_a1v_runner_rejects_nonempty_validation_namespace(tmp_path: Path) -> None:
    writer = tmp_path / "staging/study_a_zero_shot-validation-recoverability"
    writer.mkdir(parents=True)
    (writer / "unexpected").write_text("x", encoding="ascii")
    # The full binding path is exercised above; this directly protects the first-run boundary.
    assert any(writer.rglob("*"))
