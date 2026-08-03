import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results/phase7_transition_execution_repair"


def _load(name):
    return json.loads((RESULTS / name).read_text(encoding="utf-8"))


def test_frozen_failure_matrix_and_independent_attribution_are_complete():
    matrix = _load("failure_matrix.json")
    forensics = _load("local_projection_forensics.json")
    assert len(matrix) == 144
    assert sum(item["transition_success"] for item in matrix) == 47
    assert len(forensics) == 97
    assert {
        item["independent_oracle"]["classification"] for item in forensics
    } == {"B_independently_infeasible"}
    assert all(item["smallest_irreducible_conflicting_sets"] for item in forensics)


def test_repaired_matrix_is_complete_and_does_not_hide_failed_primary_cells():
    summary = _load("summary.json")
    episodes = _load("repaired_episodes.json")
    assert len(episodes) == 144
    assert summary["repaired_success_count"] == 92
    assert summary["repaired_collision_free_count"] == 144
    assert summary["repaired_projection_abort_count"] == 52
    assert summary["repaired_oracle_mismatch_count"] == 0
    assert summary["primary_supported_cell_count"] == 11
    assert summary["primary_cell_count"] == 24
    assert summary["optional_supported_cell_count"] == 12
    assert summary["optional_cell_count"] == 12


def test_repair_preserves_epoch_communication_and_model_isolation_gates():
    summary = _load("summary.json")
    assert summary["strict_runtime_violation_count"] == 0
    assert summary["communication_contract_violation_count"] == 0
    assert summary["source_equals_target_epoch_count"] == 0
    assert summary["no_op_epoch_count"] == 0
    assert summary["retry_epoch_count"] == 0
    assert summary["successful_transition_wrong_epoch_count"] == 0
    assert summary["learned_model_calls"] == 0
    assert summary["residual_action_calls"] == 0
    assert summary["scientific_training_runs"] == 0
    assert summary["final_test_layout_accesses"] == 0
    assert summary["frozen_phase6_file_changes"] == []


def test_verdict_stops_before_data_or_learning():
    summary = _load("summary.json")
    assert summary["verdict"].startswith(
        "C. Only a reduced primary transition graph is valid."
    )
