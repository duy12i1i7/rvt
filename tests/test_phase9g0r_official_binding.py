"""Executable official task/compiler/producer/writer binding for Phase 9G0-R."""

from __future__ import annotations

import inspect
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from rvt_swarm.phase8.common import sha256_document
from rvt_swarm.phase9g0r.compiler import (
    OfficialTaskCompilerError,
    compile_recoverability_tasks,
    compile_residual_tasks,
    compile_source_tasks,
    compile_task_summary,
)
from rvt_swarm.phase9g0r.contracts import (
    CandidateAggregateDisposition,
    reconcile_candidate_pair,
)
from rvt_swarm.phase9g0r.producer import (
    _execute_candidate_with_one_infrastructure_retry,
    plan_residual_retained_states,
    produce_recoverability_event,
    produce_residual_state,
)
from rvt_swarm.phase9g0r.preflight import positive_preflight, run_negative_preflight
from rvt_swarm.phase9g0r.writer import (
    DIAGNOSTIC,
    OFFICIAL_STAGING,
    CanonicalGenerationWriter,
)
from rvt_swarm.topology_registry import COMPACT, LINE


ROOT = Path(__file__).resolve().parents[1]
ADDENDUM_SHA256 = "523d865cf04b7a5bd2a9cec8cb9a105fd5ef1f1476f6acec34e8cd47cf0dcad0"
ADDENDUM_COMMIT = "9f33bda26af6ccce3f196a7a69ba0942e9785d86"


@pytest.fixture(scope="module")
def f1_n5_event():
    return next(
        task
        for task in compile_recoverability_tasks(
            ROOT, study="study_a_zero_shot", split="train"
        )
        if task.source.family == "F1" and task.source.team_size == 5
    )


@pytest.fixture(scope="module")
def f1_n5_recoverability_result(f1_n5_event):
    return produce_recoverability_event(ROOT, f1_n5_event)


@pytest.fixture(scope="module")
def f1_n5_residual_source(f1_n5_event):
    return next(
        task.source
        for task in compile_residual_tasks(
            ROOT, study="study_a_zero_shot", split="train"
        )
        if task.source.job_id == f1_n5_event.source.job_id
    )


@pytest.fixture(scope="module")
def f1_n5_retained_plan(f1_n5_residual_source):
    return plan_residual_retained_states(ROOT, f1_n5_residual_source)


@pytest.fixture(scope="module")
def f1_n5_residual_result(f1_n5_residual_source, f1_n5_retained_plan):
    return produce_residual_state(
        ROOT,
        f1_n5_residual_source,
        robot_id=0,
        timestep=f1_n5_retained_plan[0][0],
        source_commit=ADDENDUM_COMMIT,
        scientific_addendum_sha256=ADDENDUM_SHA256,
    )


def test_compiler_reconciles_every_nonsealed_scientific_level() -> None:
    summary = compile_task_summary(ROOT)
    assert summary == {
        "source_episodes": 3060,
        "decision_events": 15000,
        "candidate_aggregates": 30000,
        "candidate_replica_executions": 42000,
        "recoverability_robot_local_row_capacity": 318500,
        "residual_robot_episodes": 32560,
        "residual_retained_attempted_state_strict_upper_bound": 520960,
        "residual_candidate_evaluation_strict_upper_bound": 4688640,
        "study_a_n24_tasks": 0,
        "final_test_tasks": 0,
    }


def test_every_family_and_authorized_study_namespace_compiles() -> None:
    all_tasks = []
    for study in ("study_a_zero_shot", "study_b_with_n24"):
        for split in ("train", "validation"):
            source = compile_source_tasks(ROOT, study=study, split=split)
            recoverability = compile_recoverability_tasks(
                ROOT, study=study, split=split
            )
            residual = compile_residual_tasks(ROOT, study=study, split=split)
            assert len(source) == len(residual)
            assert recoverability
            all_tasks.extend(recoverability)
    assert {task.source.family for task in all_tasks} == {
        f"F{index}" for index in range(1, 11)
    }
    assert any(
        task.source.study == "study_b_with_n24" and task.source.team_size == 24
        for task in all_tasks
    )


def test_study_a_n24_final_test_and_unknown_namespaces_fail_closed() -> None:
    with pytest.raises(PermissionError, match="Study A N24"):
        compile_source_tasks(
            ROOT, study="study_a_zero_shot", split="n24_evaluation"
        )
    with pytest.raises(PermissionError, match="final-test"):
        compile_source_tasks(ROOT, study="study_a_zero_shot", split="final_test")
    with pytest.raises(OfficialTaskCompilerError, match="unsupported"):
        compile_source_tasks(ROOT, study="study_c", split="train")


def test_task_identity_has_no_operational_scheduler_inputs() -> None:
    source = inspect.getsource(__import__(
        "rvt_swarm.phase9g0r.compiler", fromlist=["compile_source_tasks"]
    ))
    for prohibited in ("worker_id", "chunk_id", "attempt_index", "execution_order"):
        assert prohibited not in source


def test_official_recoverability_producer_emits_exactly_two_n_local_rows(
    f1_n5_event, f1_n5_recoverability_result,
) -> None:
    reconciliation = f1_n5_recoverability_result["reconciliation"]
    rows = reconciliation["rows"]
    assert reconciliation["status"] == "SCIENTIFICALLY_RECONCILED_LABELABLE"
    assert reconciliation["training_rows_committable"] is True
    assert reconciliation["expected_row_count"] == len(rows) == 10
    assert len({row["scientific_row_id"] for row in rows}) == 10
    assert {(row["candidate_topology_id"], row["scientific_identity"]["robot_id"])
            for row in rows} == {
        (candidate, robot)
        for candidate in (COMPACT, LINE)
        for robot in range(f1_n5_event.source.team_size)
    }
    for row in rows:
        assert row["graph_payload"]["metadata"]["observer_robot_id"] == (
            row["scientific_identity"]["robot_id"]
        )
        assert "candidate_topology_id" not in row["graph_payload"]["metadata"]
        serialized = json.dumps(row["graph_payload"], sort_keys=True).lower()
        for prohibited in ("global_centroid", "full_swarm", "future_outcome"):
            assert prohibited not in serialized
        assert row["graph_fingerprint"] == sha256_document(row["graph_payload"])


def test_recoverability_producer_preserves_matched_seed_authority(
    f1_n5_recoverability_result,
) -> None:
    audits = f1_n5_recoverability_result["audit"]["candidate_audits"]
    by_candidate = {audit["candidate_topology_id"]: audit for audit in audits}
    compact = by_candidate[COMPACT]["replicas"]
    line = by_candidate[LINE]["replicas"]
    assert len(compact) == len(line) == 1
    assert compact[0]["matched_disturbance_seed"] == line[0]["matched_disturbance_seed"]
    assert compact[0]["initial_clone_hash"] == line[0]["initial_clone_hash"]


def test_residual_planner_retains_original_timesteps_per_robot(
    f1_n5_retained_plan,
) -> None:
    assert set(f1_n5_retained_plan) == set(range(5))
    for timesteps in f1_n5_retained_plan.values():
        assert len(timesteps) == 16
        assert timesteps == tuple(sorted(timesteps))
        assert timesteps[0] == 0
        assert timesteps[-1] > 16
        assert len(set(timesteps)) == 16


def test_official_residual_producer_runs_nine_candidates_and_v2_row(
    f1_n5_residual_result,
) -> None:
    audit = f1_n5_residual_result["audit"]
    assert audit["candidate_evaluations"] == 9
    assert len(audit["candidate_sidecars"]) == 9
    assert len({item["candidate_evaluation_id"]
                for item in audit["candidate_sidecars"]}) == 9
    assert audit["disposition"] in {"LABELED", "NO_ELIGIBLE_ACTION"}
    if audit["disposition"] == "LABELED":
        row = f1_n5_residual_result["row"]
        assert row["schema_version"] == "rvt-residual-supervision-row/v2"
        assert len(row["dense_row"]["residual_target_world_acceleration"]) == 2
        assert row["selected_candidate_index"] in range(9)
    else:
        assert f1_n5_residual_result["row"] is None


def test_writer_is_diagnostic_or_staging_only_and_never_partial(tmp_path) -> None:
    writer = CanonicalGenerationWriter(tmp_path / "diagnostic", mode=DIAGNOSTIC)
    compact = CandidateAggregateDisposition(
        "event", COMPACT, "RECOVERABLE_POSITIVE", 1, 1
    )
    line = CandidateAggregateDisposition(
        "event", LINE, "VALID_TASK_NEGATIVE", 0, 1
    )
    rows = tuple({"robot_id": robot} for robot in range(4))
    transaction = reconcile_candidate_pair(
        compact, line, team_size=4,
        compact_rows=rows, line_rows=rows,
    )
    result = writer.write_recoverability_transaction(transaction, {"audit": True})
    persisted = json.loads(Path(result["path"]).read_text(encoding="ascii"))
    assert persisted["scientific_completion_marker"] is True
    assert persisted["actual_row_count"] == 8
    assert result["official_counter_delta"] == 0
    assert not list((tmp_path / "diagnostic").rglob("*.partial"))
    with pytest.raises(PermissionError, match="staging"):
        CanonicalGenerationWriter(tmp_path / "diagnostic", mode=OFFICIAL_STAGING)
    with pytest.raises(PermissionError, match="authorized"):
        CanonicalGenerationWriter(tmp_path / "staging", mode=OFFICIAL_STAGING)
    with pytest.raises(PermissionError, match="FINAL"):
        CanonicalGenerationWriter(tmp_path / "final", mode=DIAGNOSTIC)


def test_candidate_replica_gets_one_byte_identical_infrastructure_retry(
    monkeypatch,
) -> None:
    calls = []

    def execute(source, candidate, *, replica_index, disturbance_seed):
        calls.append((source, candidate, replica_index, disturbance_seed))
        if len(calls) == 1:
            raise RuntimeError("worker interruption")
        return "completed"

    monkeypatch.setattr("rvt_swarm.phase9g0r.producer.execute_candidate", execute)
    replica = {
        "replica_index": 2,
        "seeds": {"matched_disturbance_seed": 91},
    }
    result, audit = _execute_candidate_with_one_infrastructure_retry(
        "snapshot", COMPACT, replica
    )
    assert result == "completed"
    assert calls == [
        ("snapshot", COMPACT, 2, 91),
        ("snapshot", COMPACT, 2, 91),
    ]
    assert [item["attempt_index"] for item in audit] == [0, 1]
    assert [item["status"] for item in audit] == [
        "INFRASTRUCTURE_EXCEPTION", "COMPLETED"
    ]


def test_positive_and_negative_preflight_have_zero_escapes() -> None:
    assert positive_preflight(ROOT)["status"] == "PASS"
    result = run_negative_preflight(ROOT)
    assert result["case_count"] >= 30
    assert result["escapes"] == 0
    assert all(item["rejected"] for item in result["cases"])


def test_command_resolve_binds_manifest_and_narrow_authorization(
    tmp_path,
) -> None:
    source_commit = os.environ.get("RVT_SOURCE_COMMIT")
    if source_commit is None:
        source_commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip()
    docker_image = (
        "sha256:30e6dea61d67eb255e814996cf737140a3b47eac62fb74ecf303df58e280138b"
    )
    provenance = "1" * 64
    scope = {
        "schema_version": "rvt-phase9-authorization-scope/v2",
        "broad_authorization": False,
        "official_generation_execution_authorized": False,
        "binding": {
            "study": "study_a_zero_shot",
            "split": "train",
            "branch": "recoverability",
            "source_commit": source_commit,
            "docker_image": docker_image,
            "scientific_addendum_sha256": ADDENDUM_SHA256,
            "generation_provenance_root": provenance,
        },
    }
    scope_hash = sha256_document(scope)
    scope["phase9_authorization_scope_sha256"] = scope_hash
    scope_path = tmp_path / "authorization.json"
    scope_path.write_text(json.dumps(scope), encoding="ascii")
    command = [
        sys.executable,
        str(ROOT / "scripts/run_phase9_official_generation.py"),
        "--root", str(ROOT),
        "--study", "study_a_zero_shot",
        "--split", "train",
        "--branch", "recoverability",
        "--mode", "DIAGNOSTIC",
        "--writer-root", str(tmp_path / "diagnostic"),
        "--source-commit", source_commit,
        "--docker-image", docker_image,
        "--job-manifest-sha256",
        "801fe4e2bd694da0dda7c310226906e59d9bc5435d657fab2e3f132432aa2dc3",
        "--scientific-addendum-sha256", ADDENDUM_SHA256,
        "--generation-provenance-root", provenance,
        "--authorization-scope-sha256", scope_hash,
        "--authorization-scope", str(scope_path),
        "--run-id", "resolve-test",
        "--resolve-only",
    ]
    completed = subprocess.run(
        command, cwd=ROOT, check=True, text=True, capture_output=True
    )
    resolution = json.loads(completed.stdout)
    assert resolution["task_count"] == 6000
    assert resolution["scientific_execution"] is False
    assert resolution["official_generation_execution_authorized"] is False
