"""Canonical Phase 9G-A1R stopped-STAGING and timeout-unit evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results/rvt_fd24"


def _sha(value) -> str:
    return hashlib.sha256(json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")).hexdigest()


def _canonical(name: str, field: str):
    document = json.loads((RESULTS / name).read_text(encoding="ascii"))
    body = dict(document)
    expected = body.pop(field)
    assert _sha(body) == expected
    return document


def test_staging_checkpoint_preserves_exact_stopped_prefix() -> None:
    checkpoint = _canonical(
        "phase9g_a1r_staging_checkpoint_v1.json",
        "phase9g_a1r_staging_checkpoint_sha256",
    )
    assert checkpoint["status"] == "PASS_READ_ONLY"
    assert checkpoint["run_id"] == (
        "phase9g-a1-study-a-train-validation-recoverability-20260812T042359Z"
    )
    assert checkpoint["transaction_count"] == 127
    assert checkpoint["completed_candidate_pair_count"] == 127
    assert checkpoint["completed_atomic_unit_count"] == 254
    assert checkpoint["scientific_row_count"] == 318
    assert len(set(checkpoint["completed_event_ids"])) == 127
    assert len(set(checkpoint["completed_atomic_unit_ids"])) == 254
    assert len(set(checkpoint["scientific_row_ids"])) == 318
    assert checkpoint["duplicate_scientific_row_identities"] == 0
    assert checkpoint["partial_candidate_pair_publications"] == 0
    assert checkpoint["partial_writer_files"] == 0


def test_all_generation_invalid_aggregates_have_frozen_scientific_causes() -> None:
    checkpoint = _canonical(
        "phase9g_a1r_staging_checkpoint_v1.json",
        "phase9g_a1r_staging_checkpoint_sha256",
    )
    assert checkpoint["generation_invalid_aggregate_reason_distribution"] == {
        "SOURCE_TERMINATED_BEFORE_EVENT:COLLISION": 70,
        "SOURCE_TERMINATED_BEFORE_EVENT:GOAL_COMPLETE": 146,
    }
    assert sum(
        checkpoint["generation_invalid_aggregate_reason_distribution"].values()
    ) == 216
    assert checkpoint["infrastructure_converted_to_generation_invalid"] is False


def test_timeout_attempts_resolve_to_one_unpublished_atomic_unit() -> None:
    timeout = _canonical(
        "phase9g_a1r_timeout_unit_v1.json",
        "phase9g_a1r_timeout_unit_sha256",
    )
    unit = timeout["timed_out_unit"]
    checkpoint = _canonical(
        "phase9g_a1r_staging_checkpoint_v1.json",
        "phase9g_a1r_staging_checkpoint_sha256",
    )
    assert timeout["both_timeouts_same_scientific_atomic_unit"] is True
    assert unit["family"] == "F2"
    assert unit["team_size"] == 12
    assert unit["decision_timestep"] == 400
    assert unit["candidate_topology_name"] == "COMPACT"
    assert unit["matched_disturbance_seed_identities"] == [3531133071]
    assert unit["scientific_atomic_unit_id"] not in checkpoint[
        "completed_atomic_unit_ids"
    ]
    assert set(timeout["timeout_scientific_effect_audit"].values()) == {
        False,
        "UNRESOLVED",
    }
    assert timeout["evidence_method"]["canonical_task_metadata_used"] is True
    assert timeout["evidence_method"]["log_text_used_to_select_identity"] is False


def test_timeout_diagnostic_plan_is_predeclared_and_non_official() -> None:
    plan = _canonical(
        "phase9g_a1r_timeout_diagnostic_plan_v1.json",
        "phase9g_a1r_timeout_diagnostic_plan_sha256",
    )
    assert plan["mode"] == "NON_OFFICIAL_DIAGNOSTIC"
    assert plan["official_staging_writes_permitted"] == 0
    assert plan["isolated_workers"] == 1
    assert plan["numeric_threads"] == 1
    assert plan["repeat_count"] == 2
    assert plan["diagnostic_watchdog_seconds"] == 300.0
    assert plan["watchdog_derivation"]["production_authority"] is False
    assert all(value == 0 for value in plan["sealed_scope"].values())
