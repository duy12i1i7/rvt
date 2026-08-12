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
