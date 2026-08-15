from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.build_phase9d_r_recoverability_audit import (
    COMBINED_ROOT,
    FAMILIES,
    TEAM_SIZES,
    TRAIN_MANIFEST,
    VALIDATION_MANIFEST,
    Phase9DRAuditError,
    _build_class_balance,
    _build_consistency,
    _build_cube,
    _build_decisions,
    _build_h1_requirements,
    _build_invalid_matrix,
    _build_missing,
    _build_statistical_unit,
    _canonical,
    _summaries,
)


ROOT = Path(__file__).resolve().parents[1]
INPUT_PATH = ROOT / "results/rvt_fd24/phase9d_recoverability_input_integrity_v1.json"


def input_audit() -> dict:
    return _canonical(INPUT_PATH, "phase9d_r_dataset_readonly_audit_sha256")


def test_readonly_input_audit_binds_exact_dataset_roots_and_integrity() -> None:
    audit = input_audit()
    assert audit["status"] == "PASS"
    assert audit["execution_mode"] == "READ_ONLY"
    assert audit["datasets"]["train"]["manifest_sha256"] == TRAIN_MANIFEST
    assert audit["datasets"]["validation"]["manifest_sha256"] == VALIDATION_MANIFEST
    assert audit["combined_root"]["manifest_sha256"] == COMBINED_ROOT
    assert not any(audit["split_isolation"].values())
    assert audit["official_dataset_mutations"] == 0
    for split in ("train", "validation"):
        integrity = audit["datasets"][split]["integrity"]
        assert integrity["matched_seed_mismatches"] == 0
        assert integrity["graph_fingerprint_failures"] == 0
        assert integrity["row_identity_failures"] == 0
        assert integrity["partial_pair_publications"] == 0
        assert integrity["staging_writable_files"] == 0


def test_complete_cube_keeps_denominators_separate_and_exposes_zeroes() -> None:
    cube, _ = _build_cube(input_audit())
    assert len(cube) == 2 * 10 * 5 * 2
    assert {cell["team_size"] for cell in cube} == set(TEAM_SIZES)
    assert {cell["family"] for cell in cube} == set(FAMILIES)
    for cell in cube:
        expected_events = 120 if cell["split"] == "TRAIN" else 30
        expected_episodes = 24 if cell["split"] == "TRAIN" else 6
        assert cell["scheduled_source_decision_events"] == expected_events
        assert cell["scheduled_source_episodes"] == expected_episodes
        assert cell["candidate_aggregates"] == expected_events
        assert cell["candidate_aggregates"] == (
            cell["positive_aggregates"]
            + cell["negative_aggregates"]
            + cell["generation_invalid_aggregates"]
        )
        assert cell["scheduled_source_decision_events"] == (
            cell["retained_candidate_pairs"] + cell["dropped_candidate_pairs"]
        )
    f4_validation = [
        cell for cell in cube
        if cell["split"] == "VALIDATION" and cell["family"] == "F4"
    ]
    assert all(cell["retained_candidate_pairs"] == 0 for cell in f4_validation)
    assert all(cell["robot_local_scientific_rows"] == 0 for cell in f4_validation)


def test_cube_reconciles_published_split_totals() -> None:
    cube, _ = _build_cube(input_audit())
    for split, expected in (
        ("TRAIN", (6000, 12000, 532, 354, 11114, 443, 5557, 8340)),
        ("VALIDATION", (1500, 3000, 154, 86, 2760, 120, 1380, 2294)),
    ):
        cells = [cell for cell in cube if cell["split"] == split]
        compact = [cell for cell in cells if cell["candidate_topology"] == "COMPACT"]
        observed = (
            sum(cell["scheduled_source_decision_events"] for cell in compact),
            sum(cell["candidate_aggregates"] for cell in cells),
            sum(cell["positive_aggregates"] for cell in cells),
            sum(cell["negative_aggregates"] for cell in cells),
            sum(cell["generation_invalid_aggregates"] for cell in cells),
            sum(cell["retained_candidate_pairs"] for cell in compact),
            sum(cell["dropped_candidate_pairs"] for cell in compact),
            sum(cell["robot_local_scientific_rows"] for cell in cells),
        )
        assert observed == expected


def test_missing_definition_is_recovered_without_new_threshold() -> None:
    cube, _ = _build_cube(input_audit())
    missing = _build_missing(ROOT, cube, _summaries(cube))
    assert missing["authoritative_structurally_missing_family_cell_count"] == 11
    assert missing["contributing_zero_retained_family_n_cell_count"] == 28
    assert missing["unexpected_executable_or_manifest_gap_count"] == 0
    assert missing["unknown_cause_count"] == 0
    assert missing["unscheduled_family_n_topology_cells"] == []
    assert {
        (cell["split"], cell["family"])
        for cell in missing["authoritative_structurally_missing_family_cells"]
    } == {
        ("TRAIN", "F2"), ("TRAIN", "F3"), ("TRAIN", "F4"),
        ("TRAIN", "F6"), ("TRAIN", "F8"), ("TRAIN", "F10"),
        ("VALIDATION", "F3"), ("VALIDATION", "F4"),
        ("VALIDATION", "F6"), ("VALIDATION", "F8"),
        ("VALIDATION", "F10"),
    }


def test_invalid_reasons_are_scientific_source_causes_only() -> None:
    matrix = _build_invalid_matrix(input_audit())
    assert len(matrix["cells"]) == 2 * 10 * 5
    assert matrix["infrastructure_misclassification_count"] == 0
    assert matrix["transition_execution_invalid_events"] == 0
    assert matrix["target_v4_generation_invalid_events"] == 0
    assert matrix["s3_hold_unknown_invalid_events"] == 0
    totals = {
        (row["split"], row["reason"]): row["count"]
        for row in matrix["split_reason_totals_in_source_events"]
    }
    assert totals[("TRAIN", "SOURCE_TERMINATED_BEFORE_EVENT:COLLISION")] == 3517
    assert totals[("TRAIN", "SOURCE_TERMINATED_BEFORE_EVENT:GOAL_COMPLETE")] == 1920
    assert totals[("TRAIN", "SOURCE_TERMINATED_BEFORE_EVENT:INITIALIZATION_INVALID")] == 120
    assert totals[("VALIDATION", "SOURCE_TERMINATED_BEFORE_EVENT:COLLISION")] == 796
    assert totals[("VALIDATION", "SOURCE_TERMINATED_BEFORE_EVENT:GOAL_COMPLETE")] == 554
    assert totals[("VALIDATION", "SOURCE_TERMINATED_BEFORE_EVENT:INITIALIZATION_INVALID")] == 30


def test_split_consistency_lists_asymmetric_retained_support() -> None:
    cube, _ = _build_cube(input_audit())
    consistency = _build_consistency(cube, input_audit())
    assert consistency["validation_supported_but_train_missing_family_n_cells"] == [
        {"family": "F2", "team_size": 16},
        {"family": "F8", "team_size": 8}
    ]
    assert consistency["train_supported_but_validation_missing_family_n_cells"] == [
        {"family": "F3", "team_size": 6},
        {"family": "F3", "team_size": 8},
        {"family": "F6", "team_size": 5},
        {"family": "F6", "team_size": 12},
    ]
    assert consistency["joint_category_distribution"]["jensen_shannon_divergence_base2"] < 0.15
    assert consistency["robot_rows_treated_as_independent"] is False


def test_predeclared_label_gates_have_one_exact_failure() -> None:
    audit = input_audit()
    cube, _ = _build_cube(audit)
    requirements = _build_h1_requirements(ROOT, audit, _summaries(cube))
    statuses = {gate["gate"]: gate["status"] for gate in requirements["label_audit_gates"]}
    assert statuses == {1: "PASS", 2: "PASS", 3: "PASS", 4: "FAIL", 5: "PASS", 6: "PASS", 7: "PASS", 8: "PASS", 9: "PASS"}
    gate4 = next(gate for gate in requirements["label_audit_gates"] if gate["gate"] == 4)
    assert gate4["passing_families"] == ["F7"]
    assert len(gate4["failures"]) == 9
    gate2 = next(gate for gate in requirements["label_audit_gates"] if gate["gate"] == 2)
    assert gate2["train_decisive"]["COMPACT_ONLY_SUCCESS"] == 70
    assert gate2["train_decisive"]["LINE_ONLY_SUCCESS"] == 128
    assert gate2["validation_decisive"]["COMPACT_ONLY_SUCCESS"] == 20
    assert gate2["validation_decisive"]["LINE_ONLY_SUCCESS"] == 46


def test_class_balance_is_aggregate_and_row_level_separately() -> None:
    audit = input_audit()
    cube, _ = _build_cube(audit)
    balance = _build_class_balance(cube, audit)
    assert balance["aggregate_level"]["train"]["positive"] == 532
    assert balance["aggregate_level"]["train"]["negative"] == 354
    assert balance["aggregate_level"]["validation"]["positive"] == 154
    assert balance["aggregate_level"]["validation"]["negative"] == 86
    assert balance["robot_local_row_level"]["train"] == {
        "positive": 4474,
        "negative": 3866,
        "positive_fraction": pytest.approx(4474 / 8340),
    }
    assert balance["robot_local_row_level"]["validation"] == {
        "positive": 1362,
        "negative": 932,
        "positive_fraction": pytest.approx(1362 / 2294),
    }


def test_frozen_loss_prevents_n_dependent_event_weighting() -> None:
    contract = _build_statistical_unit(input_audit())
    assert contract["n_dependent_weighting_intended"] is False
    assert contract["raw_row_mean_permitted"] is False
    for row in contract["team_size_weight_audit"]:
        assert row["rows_per_retained_event"] == 2 * row["team_size"]
        assert row["frozen_event_averaged_effective_event_weight"] == 1.0
        assert row["frozen_within_event_weight_per_robot_candidate_row"] == pytest.approx(
            1 / (2 * row["team_size"])
        )


def test_adequacy_and_go_no_go_are_closed_without_execution() -> None:
    adequacy, residual, training = _build_decisions()
    assert adequacy["classification"] == "RECOVERABILITY_DATASET_INADEQUATE_FOR_FROZEN_H1"
    assert residual["decision"] == "HOLD_RESIDUAL_PENDING_RECOVERABILITY_SCIENTIFIC_DECISION"
    assert training["decision"] == "RECOVERABILITY_TRAINING_BLOCKED"
    assert residual["residual_generation_operations"] == 0
    assert training["training_operations"] == 0
    assert training["hyperparameter_trials"] == 0


def test_canonical_validator_rejects_tampering(tmp_path: Path) -> None:
    document = json.loads(INPUT_PATH.read_text(encoding="ascii"))
    document["status"] = "TAMPERED"
    path = tmp_path / "tampered.json"
    path.write_text(json.dumps(document), encoding="ascii")
    with pytest.raises(Phase9DRAuditError, match="canonical hash mismatch"):
        _canonical(path, "phase9d_r_dataset_readonly_audit_sha256")
