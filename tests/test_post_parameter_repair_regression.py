"""Artifact-level checks for the frozen post-parameter-repair regression."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "results" / "post_parameter_repair_regression"


def load(name: str):
    return json.loads((OUT / name).read_text())


def test_manifest_has_complete_derived_provenance_and_frozen_cardinality():
    manifest = load("experiment_manifest.json")
    assert manifest["source"]["runtime_tag"] == \
        "decentralized-parameter-semantics-v1"
    assert manifest["scope"]["final_test_layout_access"] is False
    assert manifest["scope"]["parameter_tuning_from_results"] is False
    assert manifest["frozen_experiment_cells"]["episode_count"] == 30
    assert len(manifest["frozen_experiment_cells"]["scenarios"]) == 6
    assert len({x["geometry_sha256"] for x in
                manifest["frozen_experiment_cells"]["scenarios"]}) == 6
    for name, value in manifest["derived_quantities"].items():
        values = value if isinstance(value, list) else [value]
        for item in values:
            assert item["source_parameters"], name
            assert item["derivation_formula"], name
            assert "result" in item, name
            assert "normalized_value" in item, name


def test_role_detector_validation_uses_B_and_matches_old_frozen_trace():
    result = load("role_dependent_detector_validation.json")
    assert result["deployable_runtime_detector"] == "B_role_dependent"
    widths = {round(x["derived_forward_sector_half_width_m"], 2)
              for x in result["role_geometry"]}
    assert widths == {0.55, 1.45}
    assert all(x["complete_future_expansion_region_observed"]
               for x in result["role_geometry"])
    assert all(x["old_raw_opening_mismatch_count"] == 0
               for x in result["alpha_025_frozen_trace_comparison"])
    outer = {0, 2, 3, 5}
    for episode in result["alpha_025_frozen_trace_comparison"]:
        for robot in episode["robots"]:
            if robot["robot_id"] in outer:
                assert robot["B_only_point_count"] > 0
                assert robot[
                    "any_B_only_point_intersects_future_KEEP_expansion_region"]


def test_mechanical_checks_cover_only_declared_team_sizes_and_contracts():
    result = load("mechanical_parameterization_checks.json")
    assert result["closed_loop_claim"].startswith("N=6 only")
    assert [x["team_size"] for x in result["team_sizes"]] == [5, 6, 8]
    for item in result["team_sizes"]:
        assert item["roles_generated"]
        assert item["outer_roles_wider_than_centre_when_required"]
        assert item["widths_increase_with_spacing"]
        assert item["widths_increase_with_collision_clearance"]
        assert item["all_required_sectors_observable"]
        assert item["unsupported_configuration_result"]["supported"]
        assert item["propagation"]["contract_satisfied"]


def test_closed_loop_contains_exact_four_arms_and_episode_fields():
    result = load("closed_loop_results.json")
    assert result["final_test_layout_access"] is False
    assert result["learned_selector"] is False
    assert set(result["arms"]) == {
        "always_KEEP", "always_LINE", "preserved_pre_parameter_repair_V3",
        "corrected_parameterized_V3",
    }
    required = {
        "first_ENTRY_evidence_step", "KEEP_to_LINE_proposal_step",
        "KEEP_to_LINE_commitment_step",
        "first_forward_opening_evidence_per_robot",
        "role_dependent_detector_width_m_per_robot",
        "first_RECOVERY_evidence_step", "RECOVERY_proposal_step",
        "LINE_to_KEEP_commitment_step",
        "robot_positions_at_recovery_commitment_m",
        "wall_constraint_at_recovery_commitment_per_robot",
        "lateral_expansion_velocity_after_commitment_per_robot",
        "bottleneck_crossing", "collision_free", "goal_reaching",
        "KEEP_tube_entry", "recovery_dwell_completion",
        "full_reconfiguration_success", "successful_epochs", "retry_epochs",
        "no_op_epochs", "total_epochs", "protocol_bytes",
    }
    for arm in result["arms"].values():
        assert len(arm["per_episode"]) == 30
    corrected = result["arms"]["corrected_parameterized_V3"]["per_episode"]
    assert all(required <= set(row) for row in corrected)


def test_every_failure_has_exactly_one_primary_category_and_verdict_is_B():
    attribution = load("failure_attribution.json")
    failures = attribution["per_failed_episode"]
    assert len(failures) == attribution["failed_episode_count"] == 16
    assert sum(attribution["primary_category_counts"].values()) == len(failures)
    assert set(item["primary_category"] for item in failures) == {"B"}

    gates = load("regression_gates.json")
    assert gates["P1_detector_geometry"]["pass"]
    assert gates["P2_decentralization"]["pass"]
    assert gates["P3_propagation_correctness"]["pass"]
    assert gates["P4_closed_loop_passage"]["pass"] is False
    assert gates["P5_full_reconfiguration"]["pass"] is False
    assert gates["P6_epoch_control"]["pass"]
    assert gates["P7_alpha_025_separate"]["reported_separately"]
    assert gates["decision_case"] == "CASE_2"
    assert gates["verdict"] == "B"
