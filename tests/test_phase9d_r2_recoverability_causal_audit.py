from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.audit_phase9d_r2_recoverability_causal import (
    MATRIX_SCHEMA_VERSION,
    build_event_record,
    candidate_evidence,
    infer_root_cause,
)
from rvt_swarm.phase9g0r.contracts import (
    CandidateAggregateDisposition,
    Phase9G0RContractError,
    reconcile_candidate_pair,
)
from rvt_swarm.phase9g0r.producer import produce_recoverability_candidate
from rvt_swarm.topology_registry import COMPACT, LINE


ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "results/rvt_fd24/phase9d_r2_recoverability_event_causal_matrix_v1.jsonl"
SUMMARY = ROOT / "results/rvt_fd24/phase9d_r2_recoverability_causal_summary_v1.json"


@pytest.fixture(scope="module")
def causal_records() -> list[dict]:
    return [json.loads(line) for line in MATRIX.read_text(encoding="ascii").splitlines()]


@pytest.fixture(scope="module")
def causal_summary() -> dict:
    return json.loads(SUMMARY.read_text(encoding="ascii"))


def test_event_matrix_has_one_record_per_frozen_source_event(
    causal_records: list[dict], causal_summary: dict,
) -> None:
    assert len(causal_records) == len({record["event_id"] for record in causal_records}) == 7500
    assert {record["schema_version"] for record in causal_records} == {MATRIX_SCHEMA_VERSION}
    assert causal_summary["accounting_by_split"] == [
        {
            "candidate_aggregates_absent_from_publication": 11114,
            "candidate_aggregates_attempted": 886,
            "candidate_aggregates_removed_only_due_to_partner_invalid": 0,
            "candidate_aggregates_scheduled": 12000,
            "dropped_pairs": 5557,
            "not_evaluated_no_source_snapshot_candidates": 11114,
            "published_rows": 8340,
            "producer_pre_pair_generation_invalid": 11114,
            "raw_candidate_invalid": 0,
            "realized_events": 443,
            "retained_pairs": 443,
            "robot_local_rows_prevented_from_publication": 104460,
            "scheduled_events": 6000,
            "source_event_not_reached": 5557,
            "source_events": 6000,
            "split": "train",
        },
        {
            "candidate_aggregates_absent_from_publication": 2760,
            "candidate_aggregates_attempted": 240,
            "candidate_aggregates_removed_only_due_to_partner_invalid": 0,
            "candidate_aggregates_scheduled": 3000,
            "dropped_pairs": 1380,
            "not_evaluated_no_source_snapshot_candidates": 2760,
            "published_rows": 2294,
            "producer_pre_pair_generation_invalid": 2760,
            "raw_candidate_invalid": 0,
            "realized_events": 120,
            "retained_pairs": 120,
            "robot_local_rows_prevented_from_publication": 25906,
            "scheduled_events": 1500,
            "source_event_not_reached": 1380,
            "source_events": 1500,
            "split": "validation",
        },
    ]


def test_source_event_not_reached_is_not_a_raw_candidate_failure(
    causal_records: list[dict],
) -> None:
    dropped = [
        record for record in causal_records
        if record["inferred_root_cause_category"] == "SOURCE_EVENT_NOT_REACHED"
    ]
    assert len(dropped) == 6937
    assert all(record["source_terminal_before_event"] for record in dropped)
    assert all(not record["source_snapshot_exists"] for record in dropped)
    assert all(not record["compact_attempted"] and not record["line_attempted"] for record in dropped)
    assert {
        (record["compact_raw_disposition"], record["line_raw_disposition"])
        for record in dropped
    } == {("NOT_EVALUATED_NO_SOURCE_SNAPSHOT", "NOT_EVALUATED_NO_SOURCE_SNAPSHOT")}
    assert {
        (
            record["compact_producer_disposition_before_pair"],
            record["line_producer_disposition_before_pair"],
        )
        for record in dropped
    } == {("GENERATION_INVALID", "GENERATION_INVALID")}


def test_raw_candidate_disposition_is_classified_before_pair_reconciliation() -> None:
    compact_audit = {
        COMPACT: {
            "aggregate": {
                "disposition": "GENERATION_INVALID",
                "aggregate_label": None,
            },
            "replicas": [{
                "disposition": "GENERATION_INVALID",
                "termination_cause": "NUMERICAL_INVALID",
                "failed_predicates": ["numerically_valid"],
            }],
        }
    }
    evidence = candidate_evidence(compact_audit, COMPACT)
    assert evidence["compact_attempted"] is True
    assert evidence["compact_raw_disposition"] == "GENERATION_INVALID"
    assert evidence["compact_producer_disposition_before_pair"] == "GENERATION_INVALID"
    record = {
        "source_snapshot_exists": True,
        "compact_raw_disposition": "GENERATION_INVALID",
        "line_raw_disposition": "VALID_TASK_NEGATIVE",
        "pair_reconciliation_result": "SCIENTIFICALLY_RECONCILED_GENERATION_INVALID",
    }
    assert infer_root_cause(record) == "COMPACT_ONLY_INVALID"


@dataclass(frozen=True)
class _Termination:
    cause: str
    control_step: int
    time_seconds: float
    detail: str = ""


class _Task:
    event_id = "diagnostic-event"
    resolved_control_step = 10
    replicas_per_candidate = 1
    source = SimpleNamespace(team_size=5)

    @staticmethod
    def replica_jobs(candidate: int):
        del candidate
        return ()


def test_terminal_before_event_skips_snapshot_and_candidate_execution(monkeypatch) -> None:
    session = SimpleNamespace(
        termination=_Termination("COLLISION", 9, 1.35),
        control_step=9,
        robots=(),
    )
    monkeypatch.setattr(
        "rvt_swarm.phase9g0r.producer._run_source_to_step",
        lambda root, source, control_step: session,
    )
    snapshot_calls = []
    monkeypatch.setattr(
        "rvt_swarm.phase9g0r.producer.snapshot",
        lambda value: snapshot_calls.append(value),
    )
    result = produce_recoverability_candidate(ROOT, _Task(), COMPACT)
    assert result["source_terminated_before_event"] is True
    assert result["source_snapshot_sha256"] is None
    assert result["candidate_audit"] is None
    assert result["disposition"]["disposition"] == "GENERATION_INVALID"
    assert snapshot_calls == []


def test_same_step_terminal_is_snapshotted_and_not_lost(monkeypatch) -> None:
    session = SimpleNamespace(
        termination=_Termination("GOAL_COMPLETE", 10, 1.5),
        control_step=10,
        robots=(),
    )
    monkeypatch.setattr(
        "rvt_swarm.phase9g0r.producer._run_source_to_step",
        lambda root, source, control_step: session,
    )
    snapshot_calls = []

    def capture(value):
        snapshot_calls.append(value)
        return SimpleNamespace(canonical_hash="a" * 64)

    monkeypatch.setattr("rvt_swarm.phase9g0r.producer.snapshot", capture)
    result = produce_recoverability_candidate(ROOT, _Task(), COMPACT)
    assert result["source_terminated_before_event"] is False
    assert result["source_snapshot_sha256"] == "a" * 64
    assert snapshot_calls == [session]


def test_existing_same_step_terminal_events_were_published(
    causal_records: list[dict],
) -> None:
    same_step = [record for record in causal_records if record["source_terminal_same_step"]]
    assert len(same_step) == 2
    assert all(record["source_snapshot_exists"] for record in same_step)
    assert all(record["pair_reconciliation_result"] == "SCIENTIFICALLY_RECONCILED_LABELABLE"
               for record in same_step)
    assert all(record["published_robot_rows"] == 2 * record["team_size"] for record in same_step)


def test_pair_reconciliation_is_all_or_none_and_infrastructure_stays_pending() -> None:
    compact_invalid = CandidateAggregateDisposition(
        "event", COMPACT, "GENERATION_INVALID", None, 1
    )
    compact_valid = CandidateAggregateDisposition(
        "event", COMPACT, "RECOVERABLE_POSITIVE", 1, 1
    )
    line_valid = CandidateAggregateDisposition(
        "event", LINE, "VALID_TASK_NEGATIVE", 0, 1
    )
    line_infra = CandidateAggregateDisposition(
        "event", LINE, "INFRASTRUCTURE_FAILURE", None, 1
    )
    invalid = reconcile_candidate_pair(
        compact_invalid,
        line_valid,
        team_size=5,
        compact_rows=tuple({"robot": index} for index in range(5)),
        line_rows=tuple({"robot": index} for index in range(5)),
    )
    assert invalid.status == "SCIENTIFICALLY_RECONCILED_GENERATION_INVALID"
    assert invalid.rows == ()
    assert invalid.training_rows_committable is False

    infra = reconcile_candidate_pair(compact_valid, line_infra, team_size=5)
    assert infra.status == "PENDING_INFRASTRUCTURE_RESOLUTION"
    assert infra.scientifically_reconciled is False
    assert infra.rows == ()


def test_labelable_pair_requires_exactly_two_n_rows() -> None:
    compact = CandidateAggregateDisposition(
        "event", COMPACT, "RECOVERABLE_POSITIVE", 1, 1
    )
    line = CandidateAggregateDisposition(
        "event", LINE, "VALID_TASK_NEGATIVE", 0, 1
    )
    rows = tuple({"robot": index} for index in range(5))
    complete = reconcile_candidate_pair(
        compact, line, team_size=5, compact_rows=rows, line_rows=rows
    )
    assert complete.actual_row_count == complete.expected_row_count == 10
    with pytest.raises(Phase9G0RContractError, match="exactly N rows"):
        reconcile_candidate_pair(
            compact, line, team_size=5, compact_rows=rows[:-1], line_rows=rows
        )


def test_matrix_has_no_partial_publication_or_infrastructure_contamination(
    causal_records: list[dict], causal_summary: dict,
) -> None:
    assert all(
        record["published_robot_rows"] in (0, 2 * record["team_size"])
        for record in causal_records
    )
    assert causal_summary["infrastructure"] == {
        "infra_attempted": 1410,
        "infra_failed": 0,
        "retried": 0,
        "resolved": 0,
        "unresolved": 0,
    }
    assert causal_summary["matched_randomness"] == {
        "clone_hash_mismatches": 0,
        "replica_pairs_checked": 705,
        "seed_mismatches": 0,
    }
