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


def test_isolated_replays_complete_deterministically_after_old_timeout() -> None:
    replays = [
        _canonical(
            f"phase9g_a1r_timeout_replays/replay-{index}.json",
            "phase9g_a1r_timeout_diagnostic_replay_sha256",
        )
        for index in (1, 2)
    ]
    for replay in replays:
        assert replay["mode"] == "NON_OFFICIAL_DIAGNOSTIC"
        assert replay["official_staging_writes"] == 0
        assert replay["timing"]["atomic_unit_wall_seconds"] > 60.0
        assert replay["timing"]["atomic_unit_wall_seconds"] < 300.0
        assert replay["timing"]["replica_rollout_seconds"] == []
        assert replay["timing"]["target_v4_evaluation_seconds"] == []
        assert replay["completion_disposition"]["disposition"] == (
            "GENERATION_INVALID"
        )
        assert replay["source_terminated_before_event"] is True
    for field in (
        "scientific_semantic_digest",
        "replica_output_digest",
        "target_v4_input_digest",
        "target_v4_output_digest",
    ):
        assert replays[0][field] == replays[1][field]


def test_long_tail_set_was_predeclared_with_required_structural_coverage() -> None:
    manifest = _canonical(
        "phase9g_a1r_long_tail_manifest_v4.json",
        "phase9g0p_recoverability_benchmark_manifest_sha256",
    )
    assert manifest["mode"] == "NON_OFFICIAL_DIAGNOSTIC"
    assert manifest["predeclared_before_measurement"] is True
    assert manifest["event_count"] == 9
    assert manifest["scheduler_atomic_unit_count"] == 18
    assert manifest["workers_to_compare"] == [1, 12]
    assert manifest["chunk_size_atomic_units"] == 1
    assert manifest["diagnostic_profile_watchdog_seconds"] == 2700.0
    assert manifest["diagnostic_profile_watchdog_derivation"][
        "production_authority"
    ] is False
    intents = {
        intent for event in manifest["events"] for intent in event["coverage_intent"]
    }
    assert {
        "exact_timed_out_structural_unit",
        "same_family_team_size",
        "long_horizon",
        "three_replicas",
        "changed_topology",
        "per_replica_timing_coverage",
        "actual_per_replica_timing_coverage",
    } <= intents
    assert all(value == 0 for value in manifest["sealed_scope"].values())
    timeout = _canonical(
        "phase9g_a1r_timeout_unit_v1.json",
        "phase9g_a1r_timeout_unit_sha256",
    )
    exact = next(
        event for event in manifest["events"]
        if "exact_timed_out_structural_unit" in event["coverage_intent"]
    )
    assert exact["event_id"] == timeout["timed_out_unit"]["decision_event_id"]
    assert exact["source"]["layout_sha256"] == timeout["timed_out_unit"][
        "layout_sha256"
    ]
    replica_event = next(
        event for event in manifest["events"]
        if "actual_per_replica_timing_coverage" in event["coverage_intent"]
    )
    checkpoint = _canonical(
        "phase9g_a1r_staging_checkpoint_v1.json",
        "phase9g_a1r_staging_checkpoint_sha256",
    )
    official = next(
        item for item in checkpoint["transaction_descriptors"]
        if item["decision_event_id"] == replica_event["event_id"]
    )
    assert official["candidate_pair_status"] == (
        "SCIENTIFICALLY_RECONCILED_LABELABLE"
    )


def test_initial_incomplete_long_tail_selection_is_excluded() -> None:
    defect = _canonical(
        "phase9g_a1r_diagnostic_selection_defect_v1.json",
        "phase9g_a1r_diagnostic_selection_defect_sha256",
    )
    assert defect["status"] == "INVALID_DIAGNOSTIC_SELECTION_EXCLUDED"
    assert defect["claimed_exact_event_id"] != defect["required_exact_event_id"]
    assert defect["claimed_layout_sha256"] != defect["required_layout_sha256"]
    assert defect["may_participate_in_timeout_derivation"] is False
    assert defect["official_staging_effect"] == 0
