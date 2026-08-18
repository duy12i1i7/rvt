"""Phase 9D-V3D -- prospective stochastic Recoverability V3 design.

Read-only tests over the design artifacts. They also preserve the historical
V2 facts: gate 7 failed at 59/530 and that record must survive. No test here
may modify or contradict the existing pin that 59/530 > 0.10.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import pytest

from rvt_swarm.phase8.common import verify_canonical_hash
from rvt_swarm.phase8.scenario import SPLIT_NAMES
from rvt_swarm.phase8.targets import STOCHASTIC_ROLLOUT_REPLICAS

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results" / "rvt_fd24"

GATE7_THRESHOLD = 0.10
V2_FAILING = (59, 530)

ARTIFACTS = [
    "phase9d_v3d_h1_semantic_boundary_v1.json",
    "phase9d_v3d_disturbance_semantics_v1.json",
    "phase9d_v3d_target_option_matrix_v1.json",
    "phase9d_v3d_replica_count_analysis_v1.json",
    "phase9d_v3d_event_weighting_design_v1.json",
    "phase9d_v3d_v2_train_reuse_matrix_v1.json",
    "phase9d_v3d_v2_validation_contamination_v1.json",
    "phase9d_v3d_fresh_validation_design_v1.json",
    "phase9d_v3d_provenance_versioning_v1.json",
    "phase9d_v3d_v3_gate_design_v1.json",
    "phase9d_v3d_compute_budget_v1.json",
    "phase9d_v3d_publication_implication_v1.json",
    "phase9d_v3d_owner_decision_package_v1.json",
    "phase9d_v3d_final_recommendation_v1.json",
]


def load(name):
    return json.loads((RESULTS / name).read_text(encoding="ascii"))


def hash_field(document):
    return next(key for key in document
                if key.startswith("phase9d_v3d_") and key.endswith("sha256"))


@pytest.fixture(scope="module")
def final():
    return load("phase9d_v3d_final_recommendation_v1.json")


@pytest.fixture(scope="module")
def options():
    return load("phase9d_v3d_target_option_matrix_v1.json")


@pytest.fixture(scope="module")
def disturbance():
    return load("phase9d_v3d_disturbance_semantics_v1.json")


@pytest.fixture(scope="module")
def replicas():
    return load("phase9d_v3d_replica_count_analysis_v1.json")


# --------------------------------------------------------------------------
# artifacts
# --------------------------------------------------------------------------
@pytest.mark.parametrize("name", ARTIFACTS)
def test_artifact_exists_and_self_verifies(name):
    document = load(name)
    assert verify_canonical_hash(document, hash_field(document)), name


@pytest.mark.parametrize("name", ARTIFACTS)
def test_artifact_hash_is_full_64_hex(name):
    document = load(name)
    value = document[hash_field(document)]
    assert len(value) == 64 and set(value) <= set("0123456789abcdef")


def test_all_fourteen_required_artifacts_exist():
    assert len(sorted(RESULTS.glob("phase9d_v3d_*.json"))) == 14


# --------------------------------------------------------------------------
# historical V2 facts must survive this phase
# --------------------------------------------------------------------------
def test_v2_gate7_failure_record_is_preserved():
    prior = load("phase9d_v2c_r_gate7_replica_instability_v1.json")
    assert verify_canonical_hash(
        prior, "phase9d_v2c_r_gate7_replica_instability_sha256")
    assert prior["result"] == "FAIL"
    assert prior["threshold"] == GATE7_THRESHOLD
    forensic = load("phase9d_v2g7_exact_cell_recount_v1.json")
    assert verify_canonical_hash(
        forensic, "phase9d_v2g7_exact_cell_recount_sha256")
    assert forensic["gate_result"] == "FAIL"


def test_the_failing_ratio_still_exceeds_the_threshold():
    unstable, total = V2_FAILING
    assert unstable / total > GATE7_THRESHOLD


def test_v2_remains_blocked_and_was_not_rescued(final):
    assert final["v2_status"] == "BLOCKED_FOR_TRAINING_UNDER_FROZEN_GATE7"
    assert final["v2_rescue_attempted"] is False
    assert final["gate7_modified"] is False
    assert "59/530" in final["v2_gate7_historical_failure_preserved"]


def test_v3_gate_design_does_not_touch_historical_gate7():
    gates = load("phase9d_v3d_v3_gate_design_v1.json")
    assert gates["historical_gate7_modified"] is False
    assert gates["historical_gate7_status"].startswith("FAILED")
    assert gates["D23_gate7_disposition"]["action"].startswith("RETIRE_FOR_V3")


# --------------------------------------------------------------------------
# D1 H1 boundary
# --------------------------------------------------------------------------
def test_h1_is_not_rewritten():
    h1 = load("phase9d_v3d_h1_semantic_boundary_v1.json")
    assert h1["h1_rewritten_in_this_phase"] is False
    live = json.loads(
        (RESULTS / "phase9d_h1_requirement_map_v1.json").read_text(encoding="ascii"))
    assert h1["h1_exact_statement"] == live["h1_exact_statement"]
    assert h1["primary_metric"] == live["primary_metric"]
    assert h1["primary_evaluation_unit"] == live["primary_evaluation_unit"]


def test_h1_authority_hash_matches_the_document():
    h1 = load("phase9d_v3d_h1_semantic_boundary_v1.json")
    actual = hashlib.sha256(
        (ROOT / "docs/RVT_FD24_RESEARCH_QUESTIONS_AND_HYPOTHESES.md").read_bytes()
    ).hexdigest()
    assert h1["h1_authority_sha256"] == actual


def test_target_type_is_an_implementation_choice_not_a_hypothesis_commitment():
    h1 = load("phase9d_v3d_h1_semantic_boundary_v1.json")
    assert "IMPLEMENTATION CHOICE" in h1["required_object_classification"]["answer"]
    assert h1["historical_implementation_choice_vs_hypothesis_meaning"]["separable"]


def test_hypothesis_drift_is_flagged_not_hidden():
    h1 = load("phase9d_v3d_h1_semantic_boundary_v1.json")
    assert h1["warning"]
    assert h1["how_much_can_change_without_a_new_hypothesis"][
        "becomes_a_new_hypothesis_if"]


# --------------------------------------------------------------------------
# D2/D3/D8 disturbance semantics
# --------------------------------------------------------------------------
def test_replicas_are_iid_samples_not_a_stress_bank(disturbance):
    d3 = disturbance["D3_what_the_replica_streams_are"]
    assert d3["classification"] == (
        "IID_SAMPLES_FROM_A_PROSPECTIVELY_FROZEN_DISTRIBUTION")
    assert d3["not_a_fixed_stress_bank"] is True
    assert len(d3["evidence"]) >= 5


def test_probability_is_declared_relative_to_the_frozen_law(disturbance):
    d3 = disturbance["D3_what_the_replica_streams_are"]
    assert "frozen disturbance law" in d3["caveat"]
    d8 = disturbance["D8_fixed_bank_versus_population"]
    assert d8["answer"] == "POPULATION_PROBABILITY_UNDER_A_FROZEN_DISTURBANCE_LAW"
    assert d8["additional_replicas_are_new_samples_not_repeats"] is True


def test_disturbance_authority_hashes_match(disturbance):
    authority = disturbance["authority"]
    for key, path in (("contract_sha256",
                       "docs/PHASE8E_INITIALIZATION_AND_DISTURBANCE_CONTRACT.md"),
                      ("rollout_protocol_sha256",
                       "docs/RVT_COUNTERFACTUAL_ROLLOUT_PROTOCOL.md"),
                      ("stream_code_sha256", "rvt_swarm/phase9c_rb/streams.py")):
        actual = hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
        assert authority[key] == actual, path


def test_matched_randomness_is_a_stated_v3_requirement(disturbance):
    assert disturbance["matched_randomness_preserved_requirement"]


# --------------------------------------------------------------------------
# D9/D10/D26 replica analysis
# --------------------------------------------------------------------------
def test_r3_cannot_estimate_a_per_event_probability(replicas):
    finding = replicas["D9_what_R3_can_establish"]
    assert "uninformative" in finding["1_of_3"]
    assert "uninformative" in finding["2_of_3"]
    assert "CANNOT estimate" in finding["conclusion"]


def test_per_event_intervals_recompute(replicas):
    entry = next(e for e in replicas["D9_per_event_intervals"] if e["R"] == 3)
    for item in entry["intervals"]:
        low, high = item["clopper_pearson_95"]
        assert 0.0 <= low <= item["point_estimate"] <= high <= 1.0
        assert item["width"] == pytest.approx(high - low, abs=1e-6)
    widths = {i["k"]: i["width"] for i in entry["intervals"]}
    assert widths[1] > 0.85 and widths[2] > 0.85


def test_replica_requirements_increase_as_precision_tightens(replicas):
    need = replicas["D26_replicas_for_a_target_per_event_half_width_at_p_0.5"]
    ordered = [need[k] for k in sorted(need, key=float, reverse=True)]
    assert ordered == sorted(ordered)
    assert need["0.1"] > need["0.3"]


def test_the_decisive_asymmetry_is_recorded(replicas):
    asymmetry = replicas["decisive_asymmetry"]
    assert "D robust confidence bound" in asymmetry[
        "targets_needing_per_event_precision"]
    assert "C probabilistic with a binomial likelihood" in asymmetry[
        "targets_not_needing_per_event_precision"]


def test_r_is_not_chosen_from_compute_or_from_the_v2_failure(replicas):
    assert replicas["R_not_chosen_from_compute_cost"] is True
    assert replicas["R_not_chosen_from_the_observed_v2_failure"] is True


def test_adaptive_replication_is_conditional_and_not_recommended_yet(replicas):
    adaptive = replicas["D10_adaptive_replication"]
    assert adaptive["scientifically_valid"] == "CONDITIONALLY"
    assert adaptive["implemented"] is False
    assert "NOT recommended" in adaptive["recommendation"]
    assert "PRESERVED" in adaptive["consequences"]["matched_randomness"]


def test_frozen_replica_constant_is_unchanged():
    assert STOCHASTIC_ROLLOUT_REPLICAS == 3


# --------------------------------------------------------------------------
# D11 event weighting
# --------------------------------------------------------------------------
def test_replica_count_never_buys_scientific_weight():
    weighting = load("phase9d_v3d_event_weighting_design_v1.json")
    assert weighting["frozen_status"] == "FROZEN_EVENT_EQUAL_WEIGHT"
    assert weighting["raw_row_mean_permitted"] is False
    for row in weighting["numeric_demonstration"]:
        assert row["effective_event_weight"] == 1.0
    assert "1/R" in weighting["required_normalization_for_a_binomial_target"][
        "per_candidate_term"]


def test_weighting_demonstration_covers_both_r_and_team_size():
    rows = load("phase9d_v3d_event_weighting_design_v1.json")[
        "numeric_demonstration"]
    assert {r["R"] for r in rows} == {1, 9}
    assert {r["team_size"] for r in rows} == {5, 16}


# --------------------------------------------------------------------------
# D4-D7/D12-D15/D28 option matrix
# --------------------------------------------------------------------------
def test_all_four_options_are_evaluated(options):
    assert [o["id"] for o in options["options"]] == ["A", "B", "C", "D"]
    assert options["thresholds_selected_from_v2_outcomes"] == 0


def test_abstention_deletion_flaw_is_addressed(options):
    option_a = next(o for o in options["options"] if o["id"] == "A")
    flaw = option_a["CRITICAL_FLAW_ADDRESSED"]
    assert flaw["pure_deletion_is_insufficient"] is True
    assert "cannot" in flaw["answer"]


def test_three_state_r_dependence_is_identified(options):
    option_b = next(o for o in options["options"] if o["id"] == "B")
    assert "FATAL_FLAW" in "".join(option_b.keys())
    assert "R" in option_b["definition_variant_1_FATAL_FLAW"]


def test_h1_is_literally_unchanged_under_every_option(options):
    for option in options["options"]:
        assert option["h1_compatibility"]["h1_literally_unchanged"] is True
        assert option["h1_compatibility"][
            "comparator_definition_changes"] is False


def test_safety_is_never_overridden(options):
    safety = options["D15_safety_semantics"]
    assert "NEVER overrides" in safety["invariant"]
    assert safety["safety_controller_modified"] is False
    assert safety["conservative_default"]


def test_boundary_states_are_modelled_not_deleted(options):
    decision = options["D28_boundary_handling_decision"]
    assert decision["answer"] == "C -- RETAINED_AS_PROBABILISTIC_SUPERVISION"
    assert decision["deletion_policy_justification_required_and_not_met"] is True


def test_runtime_use_is_specified_for_every_option(options):
    runtime = options["D14_runtime_use"]
    for key in ("A", "B", "C", "D"):
        assert runtime[key]
    assert runtime["h2_runtime_not_redesigned_here"] is True


# --------------------------------------------------------------------------
# D16-D22 reuse, contamination, fresh validation, provenance
# --------------------------------------------------------------------------
def test_v2_train_is_development_data():
    reuse = load("phase9d_v3d_v2_train_reuse_matrix_v1.json")
    assert reuse["v2_train_status"] == "DEVELOPMENT_DATA"
    assert reuse["in_place_relabelling_prohibited"] is True


def test_v2_labels_and_labelled_rows_never_survive_a_semantics_change():
    matrix = {row["asset"]: row for row in
              load("phase9d_v3d_v2_train_reuse_matrix_v1.json")[
                  "D21_label_reuse_matrix"]}
    for asset in ("candidate aggregate label (all-success binary)",
                  "robot-local rows as labelled training rows"):
        for option in ("A", "B", "C", "D"):
            assert matrix[asset][option] == "not reusable"


def test_cheaper_reuse_is_not_preferred_for_being_cheaper():
    paths = load("phase9d_v3d_v2_train_reuse_matrix_v1.json")["D20_path_comparison"]
    assert "NO" in paths["decisive_observation"]
    assert "fresh" in paths["recommended_shape"]


def test_v2_validation_is_development_evidence():
    contamination = load("phase9d_v3d_v2_validation_contamination_v1.json")
    assert contamination["status"] == "DEVELOPMENT_EVIDENCE"
    assert contamination[
        "must_not_be_called_untouched_confirmatory_validation_for_v3"] is True
    assert contamination["recorded_prospectively"] is True
    assert len(contamination["inspection_history"]) >= 5


def test_fresh_validation_needs_owner_authority_and_no_final_access():
    fresh = load("phase9d_v3d_fresh_validation_design_v1.json")
    assert fresh["generated_in_this_phase"] == 0
    assert fresh["owner_authority_required"] is True
    assert fresh["changes_frozen_scenario_code"] is True
    assert fresh["no_final_test_access_required"] is True
    assert len(fresh["required_properties"]) >= 6


def test_validation_variant_offsets_are_computed_from_the_generator():
    fresh = load("phase9d_v3d_fresh_validation_design_v1.json")
    offsets = fresh["geometry_offset_structure"]
    base = offsets["split_offsets"]["validation"]
    for index, value in offsets["validation_variant_offsets"].items():
        assert value == pytest.approx(base + 0.11 * int(index), abs=1e-9)
    assert offsets["split_offsets"]["final_test"] == 0.79
    assert set(SPLIT_NAMES) == {"train", "validation", "final_test"}


def test_final_test_can_remain_valid_but_only_conditionally():
    final_test = load("phase9d_v3d_fresh_validation_design_v1.json")[
        "D19_final_test_validity"]
    assert final_test["final_test_identities_inspected"] == 0
    assert final_test["final_test_outcomes_inspected"] == 0
    assert final_test["can_the_original_final_set_remain_valid_for_v3"] == (
        "YES, CONDITIONALLY")
    assert len(final_test["conditions"]) >= 4
    assert final_test["caveat"]


def test_provenance_requires_a_full_new_identity_stack():
    provenance = load("phase9d_v3d_provenance_versioning_v1.json")
    for key, value in provenance["required_new_identity_authority"].items():
        assert value is True, key
    assert provenance["mixed_semantics_under_one_dataset_identity"] == "PROHIBITED"
    assert provenance["historical_v2_artifacts_immutable"] is True


def test_acquisition_protocol_may_remain_unchanged():
    provenance = load("phase9d_v3d_provenance_versioning_v1.json")
    unchanged = provenance["may_remain_unchanged"]
    assert unchanged["source_acquisition_protocol_v2_hash"] == (
        "19fa68a37d80f16ee1463b872f26402963daeb5a56f375423634a90dc1f3546d")


# --------------------------------------------------------------------------
# D23/D24 gates
# --------------------------------------------------------------------------
def test_gate_categories_are_kept_separate():
    gates = load("phase9d_v3d_v3_gate_design_v1.json")["D24_prospective_v3_gate_set"]
    assert set(gates) >= {"DATA_INTEGRITY_GATES", "SCIENTIFIC_DISTRIBUTION_GATES",
                          "MODEL_PERFORMANCE_GATES"}
    assert gates["categories_kept_separate"] is True
    assert gates["no_threshold_taken_from_v2_observed_values"] is True


def test_boundary_gate_is_a_minimum_not_a_maximum():
    gates = load("phase9d_v3d_v3_gate_design_v1.json")["D24_prospective_v3_gate_set"]
    boundary = next(g for g in gates["SCIENTIFIC_DISTRIBUTION_GATES"]
                    if g["id"] == "V3-S3")
    assert "MINIMUM not a" in boundary["threshold"]


def test_every_gate_has_a_rationale():
    gates = load("phase9d_v3d_v3_gate_design_v1.json")["D24_prospective_v3_gate_set"]
    for category in ("DATA_INTEGRITY_GATES", "SCIENTIFIC_DISTRIBUTION_GATES",
                     "MODEL_PERFORMANCE_GATES"):
        for gate in gates[category]:
            assert gate["rationale"], gate["id"]
            assert gate["threshold"], gate["id"]


def test_owner_parameters_in_the_gate_set_are_marked():
    gates = load("phase9d_v3d_v3_gate_design_v1.json")
    assert gates["owner_parameters_in_the_gate_set"]


# --------------------------------------------------------------------------
# D25 budget
# --------------------------------------------------------------------------
def test_budget_is_derived_from_measured_v2_timing():
    budget = load("phase9d_v3d_compute_budget_v1.json")
    assert budget["generation_performed"] == 0
    basis = budget["measured_basis"]
    assert basis["stage_b_cpu_seconds"] == 19594.0
    assert basis["replica_executions"] == 3710
    assert basis["cpu_seconds_per_replica_execution"] == pytest.approx(
        19594.0 / 3710, abs=1e-3)


def test_budget_projections_increase_with_replica_count():
    projections = load("phase9d_v3d_compute_budget_v1.json")[
        "v3_projections_full_1500_episode_scale"]["R_on_f8_f9_only"]
    values = [projections[k]["estimated_cpu_hours"]
              for k in sorted(projections, key=int)]
    assert values == sorted(values)


def test_rows_do_not_scale_with_replica_count():
    storage = load("phase9d_v3d_compute_budget_v1.json")["storage"]
    assert storage["rows_scale_with_R"] is False


def test_budget_assumptions_are_declared():
    assert load("phase9d_v3d_compute_budget_v1.json")["assumptions"]


# --------------------------------------------------------------------------
# D29-D32 owner package, publication, final
# --------------------------------------------------------------------------
def test_owner_parameters_are_listed_and_not_selected():
    package = load("phase9d_v3d_owner_decision_package_v1.json")
    assert package["agent_selected_owner_parameters"] is False
    parameters = package["D29_owner_parameters"]
    assert len(parameters) >= 10
    assert any(p.get("owner_authority_required") is False for p in parameters)


def test_freeze_boundary_precedes_generation():
    freeze = load("phase9d_v3d_owner_decision_package_v1.json")[
        "D30_prospective_freeze_boundary"]
    assert freeze["freeze_precedes_generation"] is True
    assert freeze["nothing_may_be_selected_after_seeing_v3_outcomes"] is True
    assert len(freeze["must_be_frozen_before_any_v3_official_generation"]) >= 12


def test_ordering_is_corrected_not_copied():
    ordering = load("phase9d_v3d_owner_decision_package_v1.json")["D31_ordering"]
    assert ordering["correction_to_the_proposed_ordering"]["change"]
    assert ordering["no_step_executed_in_this_phase"] is True


def test_publication_narrative_does_not_hide_v2():
    publication = load("phase9d_v3d_publication_implication_v1.json")
    assert publication["v2_hidden"] is False
    assert len(publication["required_narrative_elements"]) == 4
    assert publication["development_versus_confirmatory"][
        "must_be_labelled_distinctly_in_every_table"] is True
    assert publication["anti_patterns_to_avoid"]


def test_final_recommendation_class_and_verdict(final):
    assert final["FINAL_RECOMMENDATION_CLASS"] == "C"
    assert final["FINAL_RECOMMENDATION_NAME"] == "PROBABILISTIC_RECOVERABILITY"
    assert final["verdict"] == "A"
    assert final["recommendation"] == "OWNER_DECISION_AND_FREEZE_RECOVERABILITY_V3"
    assert final["do_not_implement_yet"] is True


def test_recommendation_rejects_the_other_options_explicitly(final):
    for key in ("why_not_A", "why_not_B", "why_not_D"):
        assert final[key]
    assert len(final["why_C"]) >= 5


def test_recommendation_declares_what_it_is_not(final):
    assert final["what_this_recommendation_is_not"]
    assert final["residual_risks"]


def test_nothing_was_implemented_or_generated(final):
    assert final["implementation_performed"] == 0
    assert final["v3_rows_generated"] == 0
    assert final["models_trained"] == 0
    for key, value in final["sealed_domains"].items():
        assert value == 0, key
