"""Operational-only exact-resume tests for Phase 9G-A1R."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rvt_swarm.phase8.common import attach_canonical_hash
from rvt_swarm.phase9g0r.compiler import (
    OfficialDecisionEventTask,
    OfficialSourceTask,
)
from scripts.run_phase9g_a1r_recoverability_continuation import (
    ContinuationError,
    completed_event_ids,
    unresolved_tasks,
)


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results/rvt_fd24"


def _canonical(name: str, field: str):
    path = RESULTS / name
    document = json.loads(path.read_text(encoding="ascii"))
    body = dict(document)
    expected = body.pop(field)
    from rvt_swarm.phase8.common import sha256_document

    assert sha256_document(body) == expected
    return document


def _task(event_id: str) -> OfficialDecisionEventTask:
    source = OfficialSourceTask(
        job_id=f"source-{event_id}",
        dataset_id="study_a_train",
        study="study_a_zero_shot",
        split="train",
        layout_source_split="train",
        family="F1",
        layout_id="layout",
        layout_sha256="a" * 64,
        team_size=5,
        source_class="S0_SCRIPTED_DIAGNOSTIC",
        episode_index=0,
        horizon_seconds=90.0,
        seeds={},
    )
    return OfficialDecisionEventTask(
        event_id=event_id,
        source=source,
        event_slot_index=0,
        resolved_control_step=60,
        resolved_timestamp_seconds=9.0,
        replicas_per_candidate=1,
        candidate_replica_jobs=(),
    )


def _write_transaction(root: Path, event_id: str) -> None:
    destination = root / "recoverability" / f"event-{event_id}.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    document = attach_canonical_hash({
        "schema_version": "rvt-recoverability-candidate-pair-transaction/v1",
        "writer_mode": "OFFICIAL_STAGING",
        "decision_event_id": event_id,
        "status": "SCIENTIFICALLY_RECONCILED_GENERATION_INVALID",
        "scientifically_reconciled": True,
        "training_rows_committable": False,
        "expected_row_count": 10,
        "actual_row_count": 0,
        "rows": [],
        "audit": {},
        "scientific_completion_marker": True,
    }, "canonical_record_sha256")
    destination.write_text(
        json.dumps(document, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="ascii",
    )


def test_completed_prefix_is_reused_and_never_rescheduled(tmp_path: Path) -> None:
    tasks = (_task("event-a"), _task("event-b"), _task("event-c"))
    root = tmp_path / "staging" / "recoverability-train"
    _write_transaction(root, "event-a")
    _write_transaction(root, "event-c")
    completed = completed_event_ids(root, tasks)
    assert completed == frozenset({"event-a", "event-c"})
    assert [task.event_id for task in unresolved_tasks(tasks, completed)] == [
        "event-b"
    ]


def test_partial_candidate_pair_blocks_continuation(tmp_path: Path) -> None:
    tasks = (_task("event-a"),)
    root = tmp_path / "staging" / "recoverability-train"
    partial = root / "recoverability/event-a.json.partial"
    partial.parent.mkdir(parents=True)
    partial.write_text("partial", encoding="ascii")
    with pytest.raises(ContinuationError, match="partial candidate-pair"):
        completed_event_ids(root, tasks)


@pytest.mark.parametrize(
    "field,value,message",
    (
        ("scientifically_reconciled", False, "unresolved transaction"),
        ("scientific_completion_marker", False, "completion marker"),
        ("writer_mode", "DIAGNOSTIC", "non-official transaction"),
        ("actual_row_count", 1, "row count mismatch"),
    ),
)
def test_invalid_durable_transaction_blocks_resume(
    tmp_path: Path, field: str, value, message: str
) -> None:
    task = _task("event-a")
    root = tmp_path / "staging" / "recoverability-train"
    _write_transaction(root, task.event_id)
    path = next((root / "recoverability").glob("*.json"))
    document = json.loads(path.read_text(encoding="ascii"))
    document.pop("canonical_record_sha256")
    document[field] = value
    document = attach_canonical_hash(document, "canonical_record_sha256")
    path.write_text(json.dumps(document, sort_keys=True), encoding="ascii")
    with pytest.raises(ContinuationError, match=message):
        completed_event_ids(root, (task,))


def test_out_of_scope_event_blocks_resume(tmp_path: Path) -> None:
    root = tmp_path / "staging" / "recoverability-train"
    _write_transaction(root, "event-outside")
    with pytest.raises(ContinuationError, match="out-of-scope"):
        completed_event_ids(root, (_task("event-a"),))


def test_operational_amendment_changes_only_timeout_and_resume_selection() -> None:
    amendment = _canonical(
        "phase9g_a1r_operational_contract_amendment_v1.json",
        "phase9g_a1r_operational_contract_amendment_sha256",
    )
    assert amendment["amendment_scope"] == "RECOVERABILITY_ONLY"
    assert amendment["recoverability_profile"] == {
        "profile_id": "PROFILE_RECOVERABILITY_A1R_V1",
        "workers": 12,
        "numeric_threads": 1,
        "chunk_size_atomic_units": 1,
        "old_infrastructure_timeout_seconds": 60.0,
        "infrastructure_timeout_seconds": 243,
    }
    assert {item["field"] for item in amendment["field_changes"]} == {
        "profiles.recoverability.infrastructure_timeout_seconds",
        "common.resume.scheduler_selection",
    }
    assert amendment["residual_profile_changed"] is False
    assert amendment["frozen_science_changed"] is False


def test_authorization_continuation_is_narrower_than_parent() -> None:
    authorization = _canonical(
        "phase9g_a1r_authorization_continuation_v1.json",
        "phase9g_a1r_authorization_continuation_sha256",
    )
    assert authorization["authorized_scope"] == {
        "study": "study_a_zero_shot",
        "splits": ["train", "validation"],
        "branch": "recoverability",
        "operation": "OFFICIAL_STAGING_CONTINUATION",
        "train_before_validation": True,
    }
    assert authorization["parent_authorization"][
        "binds_old_operational_contract"
    ] is True
    assert authorization["broadens_parent_scientific_scope"] is False
    assert authorization["scope_status"]["RESIDUAL_V2"] == (
        "NOT_AUTHORIZED_IN_PHASE_9G_A1R"
    )
    assert authorization["scope_status"]["TRAINING"] == "NOT_AUTHORIZED"


def test_successor_run_reuses_same_dataset_and_exact_prefix() -> None:
    run = _canonical(
        "phase9g_a1r_continuation_run_identity_v1.json",
        "phase9g_a1r_continuation_run_identity_sha256",
    )
    assert run["logically_independent_dataset"] is False
    assert run["same_staging_namespace_as_parent"] is True
    assert run["scientific_row_identity_includes_run_id"] is False
    assert run["initial_staging_checkpoint"]["completed_train_events"] == 127
    assert run["initial_staging_checkpoint"]["scientific_rows"] == 318
    assert run["frozen_universe"] == {
        "train_events": 6000,
        "train_candidate_aggregates": 12000,
        "validation_events": 1500,
        "validation_candidate_aggregates": 3000,
        "total_events": 7500,
        "total_candidate_aggregates": 15000,
        "initial_unresolved_train_events": 5873,
    }
    assert run["resume_semantics"]["existing_rows_reemitted"] == 0
    assert run["resume_semantics"][
        "completed_candidate_pair_transactions_rescheduled"
    ] == 0
    assert run["required_order"] == ["train", "validation", "stop"]
    assert all(value == 0 for value in run["sealed_scope"].values())


def test_resume_preflight_passes_with_zero_escapes() -> None:
    preflight = _canonical(
        "phase9g_a1r_resume_preflight_v1.json",
        "phase9g_a1r_resume_preflight_sha256",
    )
    assert preflight["status"] == "PASS_ZERO_ESCAPES"
    assert preflight["official_resume_authorized"] is True
    assert preflight["staging"]["read_only_during_preflight"] is True
    assert preflight["staging"]["checkpoint_exact_recheck"] is True
    assert preflight["staging"]["initial_rows"] == 318
    assert preflight["resume_boundary"]["completed_event_identities_reused"] == 127
    assert preflight["resume_boundary"]["unresolved_event_identities_scheduled"] == 5873
    assert preflight["resume_boundary"]["existing_rows_reemitted"] == 0
    assert preflight["tests"]["focused"]["passed"] == 63
    assert preflight["tests"]["full_suite"]["passed"] == 3080
    assert preflight["tests"]["full_suite"]["failed"] == 0
    assert preflight["tests"]["full_suite"]["publication_required_xfailed"] == 0
    sealed = dict(preflight["sealed_domains"])
    assert sealed.pop("study_a_n24_all_manifest_jobs_sealed") is True
    assert all(value == 0 for value in sealed.values())


def test_worker_failure_identity_has_no_scientific_effect() -> None:
    failure = _canonical(
        "phase9g_a1r_worker_failure_identity_v1.json",
        "phase9g_a1r_worker_failure_identity_sha256",
    )
    unit = failure["failed_atomic_unit"]
    assert unit["scientific_atomic_unit_id"] == (
        "7d7f2859e7f863031676d5c972dca4e03a4a5dd84ba438cdc7753bb26896b65b"
    )
    assert unit["family"] == "F3"
    assert unit["team_size"] == 12
    assert unit["source_class"] == "S3_FROZEN_LOCAL_GEOMETRIC_SELECTOR"
    assert unit["decision_timestep"] == 90
    assert unit["candidate_topology_id"] == 5
    effect = failure["failure"]
    assert effect["exception_message"] == (
        "S3 measured width must be finite and nonnegative"
    )
    assert effect["candidate_result_created"] is False
    assert effect["scientific_disposition_created"] is False
    assert effect["scientific_row_created"] is False
    assert effect["candidate_pair_transaction_created"] is False
    assert effect["partial_candidate_pair_transaction_created"] is False


def test_worker_failure_replays_are_deterministic_and_nonofficial() -> None:
    replays = [
        _canonical(
            f"phase9g_a1r_worker_failure_replays/replay-{index}.json",
            "phase9g_a1r_worker_failure_diagnostic_replay_sha256",
        )
        for index in (1, 2, 3)
    ]
    assert [item["candidate_topology_id"] for item in replays] == [5, 5, 2]
    assert {
        item["first_negative_measured_width_call"]["measured_width_meters"]
        for item in replays
    } == {-0.6143634774571596}
    assert {
        item["termination"]["exception_message"] for item in replays
    } == {"S3 measured width must be finite and nonnegative"}
    assert all(item["mode"] == "NON_OFFICIAL_DIAGNOSTIC" for item in replays)
    assert all(item["candidate_result_created"] is False for item in replays)
    assert all(
        item["scientific_disposition_created"] is False for item in replays
    )
    assert all(item["official_staging_writes"] == 0 for item in replays)
    assert all(
        all(value == 0 for value in item["sealed_scope"].values())
        for item in replays
    )


def test_continuation_stop_audit_preserves_exact_durable_boundary() -> None:
    stop = _canonical(
        "phase9g_a1r_continuation_stop_audit_v1.json",
        "phase9g_a1r_continuation_stop_audit_sha256",
    )
    assert stop["status"] == "STOPPED_FROZEN_SOURCE_EXCEPTION"
    assert stop["verdict"] == "A"
    progress = stop["official_progress"]
    assert progress["train_events_completed"] == 210
    assert progress["validation_events_completed"] == 0
    assert progress["candidate_aggregates_completed"] == 420
    assert progress["scientific_rows"] == 342
    assert progress["initial_rows_reused"] == 318
    assert progress["new_rows_committed"] == 24
    assert progress["aggregate_dispositions"] == {
        "GENERATION_INVALID": 380,
        "RECOVERABLE_POSITIVE": 30,
        "VALID_TASK_NEGATIVE": 10,
    }
    assert progress["duplicate_scientific_row_identities"] == 0
    assert progress["partial_candidate_pair_publications"] == 0
    assert progress["unresolved_worker_failures"] == 1
    monitoring = progress["operational_monitoring"]
    assert monitoring["telemetry_events"] == 83
    assert monitoring["candidate_aggregates"] == 166
    assert monitoring["observed_peak_worker_rss_bytes"] == 294920192
    assert monitoring["separate_writer_latency_available"] is False
    timeout = stop["timeout_requalification_outcome"]
    assert timeout["previously_timed_out_unit_completed_officially"] is True
    assert timeout["new_timeout_exceeded"] is False
    assert timeout["timeout_semantics_remain_infrastructure_only"] is True
    assert stop["data_integrity"]["all_initial_rows_preserved"] is True
    assert stop["data_integrity"]["all_transactions_complete"] is True
    assert stop["downstream"]["final_dataset_manifest_created"] is False
    assert stop["downstream"]["residual_started"] is False
    assert stop["downstream"]["training_operations"] == 0
    assert all(value == 0 for value in stop["sealed_domains"].values())


def test_frozen_source_stop_summary_binds_verdict_a() -> None:
    summary = _canonical(
        "phase9g_a1r_frozen_source_stop_v1.json",
        "phase9g_a1r_frozen_source_stop_sha256",
    )
    assert summary["classification"] == "FROZEN_SCIENTIFIC_SOURCE_DEFECT"
    assert summary["diagnostic_reproduction"]["replay_count"] == 3
    assert summary["diagnostic_reproduction"][
        "candidate_independent_source_failure"
    ] is True
    assert summary["scientific_effect"] == {
        "candidate_result_created": False,
        "scientific_disposition_created": False,
        "scientific_row_created": False,
        "candidate_pair_transaction_created": False,
        "partial_candidate_pair_transaction_created": False,
        "official_staging_writes_from_diagnostics": 0,
        "scientific_retry_count": 0,
    }
    assert summary["verdict"] == "A"
    assert summary["scope_decision"]["frozen_science_changed_in_phase9g_a1r"] is False
    assert summary["scope_decision"]["residual_started"] is False
    assert summary["scope_decision"]["training_operations"] == 0
