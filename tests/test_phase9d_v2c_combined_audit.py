"""Phase 9D-V2C -- combined Recoverability V2 TRAIN+VALIDATION audit.

Read-only tests pinning the committed audit artifacts against frozen authority.
No generation, no training, no sealed-domain access.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from rvt_swarm.phase8.common import verify_canonical_hash
from rvt_swarm.phase8.scenario import (
    BOTH_FAIL,
    BOTH_SUCCESS,
    COMPACT_ONLY_SUCCESS,
    LINE_ONLY_SUCCESS,
    scenario_family,
)
from rvt_swarm.phase8.targets import joint_outcome_category

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results" / "rvt_fd24"

FROZEN_PROTOCOL = "19fa68a37d80f16ee1463b872f26402963daeb5a56f375423634a90dc1f3546d"
FROZEN_TARGET_V4 = "54a0e0baff79fbdc320800b772f47a40ac06ac4f0e70d4fab1bf676c54b918ee"
FROZEN_ROW_BINDING = "98f18a94c6a69d27a4cbf38169ca15e998ce4b4adfbba9a48cb1b3233391adf8"
TRAIN_SEAL = "a966f318832fb60bd99acdfdff72f0c7011d730f3e0fb51494ce318210f39bba"
VAL_SEAL = "667b117555a65ad9da7f8e6e7f71b2cfb6843cc66d8e8c35eb68650b7818ca69"
PRIMARY = ["F%d" % index for index in range(1, 11)]

ARTIFACTS = [
    "phase9d_v2c_combined_integrity_v1.json",
    "phase9d_v2c_combined_accounting_v1.json",
    "phase9d_v2c_family_n_matrix_v1.json",
    "phase9d_v2c_validation_gate_v1.json",
    "phase9d_v2c_scenario_semantic_authority_v1.json",
    "phase9d_v2c_scenario_field_hypothesis_binding_v1.json",
    "phase9d_v2c_zero_positive_replication_v1.json",
    "phase9d_v2c_target_v4_failure_decomposition_v1.json",
    "phase9d_v2c_candidate_decisiveness_v1.json",
    "phase9d_v2c_predeclared_gate_audit_v1.json",
    "phase9d_v2c_event_equal_weighting_v1.json",
    "phase9d_v2c_feature_schema_v1.json",
    "phase9d_v2c_train_validation_shift_v1.json",
    "phase9d_v2c_training_pipeline_readiness_v1.json",
    "phase9d_v2c_model_training_contract_snapshot_v1.json",
    "phase9d_v2c_combined_dataset_root_v1.json",
    "phase9d_v2c_final_readiness_v1.json",
]


def load(name):
    return json.loads((RESULTS / name).read_text(encoding="ascii"))


def hash_field(document):
    return next(key for key in document
                if key.startswith("phase9d_v2c_") and key.endswith("sha256"))


@pytest.fixture(scope="module")
def readiness():
    return load("phase9d_v2c_final_readiness_v1.json")


@pytest.fixture(scope="module")
def gates():
    return load("phase9d_v2c_predeclared_gate_audit_v1.json")


@pytest.fixture(scope="module")
def semantics():
    return load("phase9d_v2c_scenario_semantic_authority_v1.json")


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


# --------------------------------------------------------------------------
# C1/C2 integrity
# --------------------------------------------------------------------------
def test_both_composite_seals_recompute_exactly():
    integrity = load("phase9d_v2c_combined_integrity_v1.json")
    assert integrity["train"]["composite_seal_recomputed"] == TRAIN_SEAL
    assert integrity["train"]["composite_seal_matches_expected"] is True
    assert integrity["validation"]["composite_seal_recomputed"] == VAL_SEAL
    assert integrity["validation"]["composite_seal_matches_expected"] is True


def test_dataset_manifest_roots_equal_closure_roots():
    integrity = load("phase9d_v2c_combined_integrity_v1.json")
    for split in ("train", "validation"):
        assert integrity[split]["dataset_manifest_roots_equal_closure_roots"]
        assert integrity[split]["manifest_root_equals_frozen_manifest_hash"]
        assert integrity[split]["shard_sums_reconcile"]
        assert integrity[split]["every_shard_hash_is_full_64_hex"]


def test_frozen_contracts_are_identical_in_both_splits():
    integrity = load("phase9d_v2c_combined_integrity_v1.json")
    contracts = integrity["frozen_contracts"]
    assert contracts["source_acquisition_protocol_sha256"] == FROZEN_PROTOCOL
    assert contracts["target_v4_contract_sha256"] == FROZEN_TARGET_V4
    assert contracts["recoverability_row_binding_v2_spec_sha256"] == FROZEN_ROW_BINDING
    assert contracts["identical_in_both_splits"] is True


def test_v1_roots_are_unchanged():
    v1 = load("phase9d_v2c_combined_integrity_v1.json")["v1_immutability"]
    assert v1["train_unchanged"] is True
    assert v1["validation_unchanged"] is True
    assert v1["combined_unchanged"] is True
    assert v1["v1_rows_merged_into_v2"] == 0
    assert v1["v1_artifacts_mutated"] == 0


# --------------------------------------------------------------------------
# C4/C19 accounting
# --------------------------------------------------------------------------
def test_all_declared_combined_identities_hold():
    accounting = load("phase9d_v2c_combined_accounting_v1.json")
    assert accounting["all_expected_identities_hold"] is True
    for key, check in accounting["identity_checks"].items():
        assert check["matches"], key


def test_combined_totals_are_the_expected_values():
    combined = load("phase9d_v2c_combined_accounting_v1.json")["combined"]
    assert combined["source_episodes"] == 1500
    assert combined["selected_events"] == 6317
    assert combined["candidate_aggregates"] == 12634
    assert combined["replica_executions"] == 18162
    assert combined["positive"] == 4068
    assert combined["valid_negative"] == 8566
    assert combined["rows"] == 113514
    assert combined["generation_invalid"] == 0


def test_aggregates_are_two_per_event_and_dispositions_reconcile():
    accounting = load("phase9d_v2c_combined_accounting_v1.json")
    for scope in ("train", "validation", "combined"):
        assert accounting["aggregates_equal_two_E"][scope] is True
        assert accounting["dispositions_reconcile"][scope] is True


def test_rows_are_not_independent_observations():
    effective = load("phase9d_v2c_combined_accounting_v1.json")[
        "C4_effective_scientific_sample_size"]
    assert effective["robot_local_rows_statistically_independent"] is False
    assert effective["raw_row_mean_permitted"] is False
    assert effective["primary_clustered_unit"] == "SOURCE_DECISION_EVENT"
    assert effective["row_to_event_inflation_factor"] > 17


def test_no_posthoc_combined_class_balance_gate():
    balance = load("phase9d_v2c_combined_accounting_v1.json")["C19_class_balance"]
    assert balance["class_weighting"] == "NONE_UNWEIGHTED_BCE"
    assert balance["class_weighting_selected_from_data"] is False
    assert balance["posthoc_combined_class_balance_gate_authorized"] is False
    assert balance["statement"] == (
        "NO_POSTHOC_COMBINED_CLASS_BALANCE_GATE_AUTHORIZED")


# --------------------------------------------------------------------------
# C6 adequacy gate
# --------------------------------------------------------------------------
def test_validation_gate_unit_and_threshold_are_frozen():
    gate = load("phase9d_v2c_validation_gate_v1.json")
    assert gate["unit"] == "RETAINED_VALIDATION_SOURCE_EVENT_PAIR"
    assert gate["unit_is_not_rows"] is True
    assert gate["unit_is_not_candidate_aggregates"] is True
    assert gate["unit_is_not_replicas"] is True
    assert gate["minimum"] == 30
    assert gate["primary_families"] == PRIMARY
    assert gate["primary_families_match_h1_map"] is True


def test_every_primary_family_passes_the_validation_gate():
    gate = load("phase9d_v2c_validation_gate_v1.json")
    assert gate["all_primary_families_pass"] is True
    assert len(gate["per_family"]) == 10
    for row in gate["per_family"]:
        assert row["retained_source_events"] >= 30, row["family"]
    assert gate["minimum_family"] == "F4"
    assert gate["minimum_count"] == 77
    assert gate["margin_over_gate"] == 47
    assert gate["sum_of_per_family_equals_retained_pairs"] is True


def test_gate_four_was_the_v1_blocker():
    contrast = load("phase9d_v2c_validation_gate_v1.json")[
        "v1_era_result_for_contrast"]
    assert contrast["decision"] == "RECOVERABILITY_TRAINING_BLOCKED"
    assert contrast["passing_families_then"] == ["F7"]
    assert contrast["passing_families_now"] == PRIMARY


# --------------------------------------------------------------------------
# C5/C7 family x N
# --------------------------------------------------------------------------
def test_family_n_matrices_are_complete_for_both_splits():
    matrix = load("phase9d_v2c_family_n_matrix_v1.json")
    assert matrix["families"] == PRIMARY
    assert matrix["team_sizes"] == [5, 6, 8, 12, 16]
    assert len(matrix["train"]) == 50
    assert len(matrix["validation"]) == 50
    assert matrix["no_threshold_invented"] is True


def test_no_unexpected_empty_or_degenerate_cell_in_either_split():
    counts = load("phase9d_v2c_family_n_matrix_v1.json")["classification_counts"]
    for split in ("train", "validation"):
        assert counts[split].get("UNEXPECTED_STRUCTURAL_EMPTY", 0) == 0
        assert counts[split].get("UNEXPECTED_LABEL_DEGENERACY", 0) == 0


def test_cell_classification_replicates_exactly_across_splits():
    counts = load("phase9d_v2c_family_n_matrix_v1.json")["classification_counts"]
    assert counts["train"] == counts["validation"]
    assert counts["train"]["EXPECTED_STRUCTURAL_SOURCE_EMPTY"] == 1


def test_f4_n16_is_expected_structural_source_empty():
    cell = load("phase9d_v2c_family_n_matrix_v1.json")["C7_f4_n16"]
    assert cell["classification"] == "EXPECTED_STRUCTURAL_SOURCE_EMPTY"
    assert cell["present_in_train"] is True
    assert cell["present_in_validation"] is True
    assert cell["prospectively_predicted_in_h1r"] is True
    assert cell["replenished"] is False
    assert cell["contributes_events"] == 0
    assert cell["contributes_rows"] == 0
    assert cell["blocks_a_frozen_h1_claim"] is False


# --------------------------------------------------------------------------
# C8/C16 zero-positive replication
# --------------------------------------------------------------------------
def test_f3_f4_f6_are_zero_positive_on_both_candidates_in_both_splits():
    replication = load("phase9d_v2c_zero_positive_replication_v1.json")
    assert replication[
        "families_zero_positive_on_both_candidates_in_both_splits"] == [
            "F3", "F4", "F6"]
    for family in ("F3", "F4", "F6"):
        counts = replication["exact_counts"][family]
        assert counts["train"].get("COMPACT_RECOVERABLE_POSITIVE", 0) == 0
        assert counts["train"].get("LINE_RECOVERABLE_POSITIVE", 0) == 0
        assert counts["validation"].get("COMPACT_positive", 0) == 0
        assert counts["validation"].get("LINE_positive", 0) == 0


def test_replication_is_on_disjoint_layouts():
    replication = load("phase9d_v2c_zero_positive_replication_v1.json")
    assert replication["replication_is_on_disjoint_layouts"] is True
    assert replication["train_layouts"] == 20
    assert replication["validation_layouts"] == 10
    assert replication["layout_overlap"] == 0


def test_no_posthoc_replication_threshold_was_created():
    replication = load("phase9d_v2c_zero_positive_replication_v1.json")
    assert replication["no_posthoc_replication_threshold_created"] is True


def test_acquisition_bias_diagnostics_show_no_collapse():
    diagnostics = load("phase9d_v2c_zero_positive_replication_v1.json")[
        "C15_acquisition_bias_diagnostics_train"]
    assert diagnostics["late_ordinal_collapse"] is False
    assert diagnostics["policy_dependence"] is False
    rates = list(diagnostics["by_source_policy_positive_rate"].values())
    assert max(rates) - min(rates) < 0.05
    ordinals = list(diagnostics["by_selection_ordinal_positive_rate"].values())
    assert min(ordinals) > 0.20


# --------------------------------------------------------------------------
# C9/C10 scenario semantics
# --------------------------------------------------------------------------
def test_two_distinct_objects_share_the_vocabulary(semantics):
    assert semantics["answer"] == "TWO_DISTINCT_OBJECTS_SHARE_THE_VOCABULARY"
    assert semantics["object_1_scenario_headroom_category"]["unit"] == (
        "layout x team-size cell")
    assert semantics["object_2_joint_recoverability_outcome"]["unit"] == (
        "one Recoverability decision event")
    assert semantics["object_1_scenario_headroom_category"][
        "bound_hypothesis"] == "H2"
    assert semantics["object_2_joint_recoverability_outcome"][
        "bound_hypothesis"] == "H1"


def test_the_two_objects_are_not_coupled_in_code(semantics):
    coupling = semantics["the_two_objects_are_not_coupled"]
    assert coupling[
        "hits_in_recoverability_generation_or_acquisition_code"] == 0
    assert coupling["no_authority_asserts_headroom_equals_joint_outcome"] is True


def test_no_scenario_authority_conflict_is_returned(semantics):
    conflict = semantics["C10_decisive_semantic_conflict_test"]
    assert conflict["is_line_only_success_a_decision_state_label_expectation"] is False
    assert conflict["returns_RECOVERABILITY_SCENARIO_AUTHORITY_CONFLICT"] is False


def test_measured_headroom_records_both_fail_for_f3_f4_f6(semantics):
    finding = semantics["decisive_finding"]
    assert finding["F3"]["measured_line_only_cells"] == 0
    assert finding["F4"]["measured_line_only_cells"] == 0
    assert finding["F6"]["measured_compact_only_or_both_success_cells"] == 0
    measured = semantics["measured_headroom_authority"]
    assert measured["status"] == "AUTHORITATIVE_PRE_DATA_HEADROOM"
    assert measured["cells"] == 150
    assert measured["category_mismatches"] == 0
    assert measured["predates_all_recoverability_v2_data"] is True


def test_declared_family_categories_are_unchanged_in_code():
    # the declarations themselves must NOT be rewritten by this audit
    assert scenario_family("F3").expected_headroom_categories == (
        LINE_ONLY_SUCCESS,)
    assert scenario_family("F4").expected_headroom_categories == (
        LINE_ONLY_SUCCESS,)
    assert scenario_family("F6").expected_headroom_categories == (
        COMPACT_ONLY_SUCCESS, BOTH_SUCCESS)


def test_measured_headroom_artifact_is_unmodified(semantics):
    document = json.loads(
        (RESULTS / "headroom_requalification_v6.json").read_text(encoding="ascii"))
    assert document["headroom_requalification_v6_sha256"] == (
        semantics["measured_headroom_authority"]["sha256"])
    for family in ("F3", "F6"):
        assert document["per_family_counts"][family] == {"BOTH_FAIL": 15}
    assert document["per_family_counts"]["F4"] == {
        "BOTH_FAIL": 12, "INVALID_OR_AMBIGUOUS": 3}


# --------------------------------------------------------------------------
# C11/C12/C28 hypothesis binding
# --------------------------------------------------------------------------
def test_hypothesis_authority_hash_matches_the_h1_requirement_map():
    binding = load("phase9d_v2c_scenario_field_hypothesis_binding_v1.json")
    assert binding["hypothesis_authority"][
        "matches_h1_requirement_map_declared_hash"] is True
    actual = hashlib.sha256(
        (ROOT / "docs/RVT_FD24_RESEARCH_QUESTIONS_AND_HYPOTHESES.md").read_bytes()
    ).hexdigest()
    assert binding["hypothesis_authority"]["sha256"] == actual


def test_headroom_fields_bind_to_h2_and_never_gate_h1():
    binding = load("phase9d_v2c_scenario_field_hypothesis_binding_v1.json")
    headroom = [item for item in binding["binding"]
                if "headroom" in item["field"]]
    assert headroom
    for item in headroom:
        assert item["primary_hypothesis"] == "H2"
        assert item["used_as_an_H1_label_gate"] is False


def test_joint_outcome_binds_to_h1_and_is_a_label_gate():
    binding = load("phase9d_v2c_scenario_field_hypothesis_binding_v1.json")
    joint = [item for item in binding["binding"]
             if "joint_outcome_category" in item["field"]]
    assert joint and joint[0]["primary_hypothesis"] == "H1"
    assert joint[0]["used_as_an_H1_label_gate"] is True


def test_no_cross_hypothesis_confusion_statement():
    confusion = load("phase9d_v2c_scenario_field_hypothesis_binding_v1.json")[
        "C12_no_cross_hypothesis_confusion"]
    assert confusion["statement"] == (
        "H2_EPISODE_HEADROOM != H1_MID_TRAJECTORY_RECOVERABILITY_LABEL")
    assert len(confusion["proof"]) >= 5
    assert confusion["the_tension_is_explained_not_erased"] is True


def test_h2_is_protected():
    protection = load("phase9d_v2c_scenario_field_hypothesis_binding_v1.json")[
        "C28_h2_protection"]
    assert protection["scenario_declarations_rewritten"] == 0
    assert protection["scenario_geometry_modified"] is False
    assert protection["headroom_categories_modified"] is False
    assert protection["h2_empirically_confirmed"] is False
    assert protection["h2_remains_falsifiable"] is True


# --------------------------------------------------------------------------
# C17 decisiveness naming
# --------------------------------------------------------------------------
def test_joint_outcome_function_is_the_decision_event_object():
    # the four names in the decisiveness artifact come from THIS function
    assert joint_outcome_category.__module__.endswith("phase8.targets")
    decisiveness = load("phase9d_v2c_candidate_decisiveness_v1.json")
    assert "NOT the scenario-manifest headroom categories" in (
        decisiveness["naming_warning"])


def test_train_decisive_events_exist():
    decisiveness = load("phase9d_v2c_candidate_decisiveness_v1.json")
    joint = decisiveness["train"]["joint_categories"]
    assert joint["COMPACT_ONLY_SUCCESS"] == 1105
    assert joint["LINE_ONLY_SUCCESS"] == 737
    assert set(joint) == {COMPACT_ONLY_SUCCESS, LINE_ONLY_SUCCESS,
                          BOTH_SUCCESS, BOTH_FAIL}
    assert decisiveness["informative_events_exist"] is True


def test_zero_positive_validation_families_have_determined_joint_counts():
    determined = load("phase9d_v2c_candidate_decisiveness_v1.json")[
        "validation"]["fully_determined_families"]
    assert set(determined) == {"F3", "F4", "F6", "F10"}
    assert determined["F3"]["BOTH_FAIL"] == 111
    assert determined["F4"]["BOTH_FAIL"] == 77
    assert determined["F6"]["BOTH_FAIL"] == 131
    assert determined["F10"]["LINE_ONLY_SUCCESS"] == 47


# --------------------------------------------------------------------------
# C18 gates
# --------------------------------------------------------------------------
def test_all_nine_predeclared_gates_are_present_and_none_invented(gates):
    assert [item["gate"] for item in gates["gates"]] == list(range(1, 10))
    assert gates["new_gates_invented"] == 0
    assert gates["posthoc_gate_added"] is False


def test_no_predeclared_gate_fails(gates):
    assert gates["gates_failing"] == []


def test_gates_one_through_six_pass(gates):
    assert gates["gates_fully_passing"] == [1, 2, 3, 4, 5, 6]


def test_gate_two_validation_lower_bounds_clear_the_minimum(gates):
    gate = next(item for item in gates["gates"] if item["gate"] == 2)
    assert gate["validation"]["COMPACT_ONLY_SUCCESS_lower_bound"] >= 20
    assert gate["validation"]["LINE_ONLY_SUCCESS_lower_bound"] >= 20
    assert gate["result"] == "PASS"


def test_gate_three_rates_are_inside_the_frozen_interval(gates):
    gate = next(item for item in gates["gates"] if item["gate"] == 3)
    for scope in ("train", "validation", "combined"):
        for value in gate[scope].values():
            assert 0.10 <= value <= 0.90


def test_gate_six_invalid_rate_is_zero(gates):
    gate = next(item for item in gates["gates"] if item["gate"] == 6)
    assert gate["combined_invalid_rate"] == 0.0
    assert gate["maximum_family_invalid_rate"] == 0.0


def test_gates_not_fully_evaluated_are_declared_honestly(gates):
    assert gates["gates_not_fully_evaluated_in_this_phase"] == [7, 8, 9]
    gate7 = next(item for item in gates["gates"] if item["gate"] == 7)
    assert gate7["result"] == "NOT_EVALUATED"


# --------------------------------------------------------------------------
# C20 weighting
# --------------------------------------------------------------------------
def test_event_equal_weighting_is_frozen():
    weighting = load("phase9d_v2c_event_equal_weighting_v1.json")
    assert weighting["frozen_status"] == "FROZEN_EVENT_EQUAL_WEIGHT"
    assert weighting["raw_row_mean_permitted"] is False
    assert weighting["robot_local_rows_statistically_independent"] is False
    assert weighting["n_dependent_weighting_intended"] is False
    assert weighting["class_weighting"] == "NONE_UNWEIGHTED_BCE"
    assert weighting["model_training_performed"] is False


def test_every_event_carries_equal_weight_regardless_of_n():
    rows = load("phase9d_v2c_event_equal_weighting_v1.json")[
        "combined_demonstration"]
    assert {row["team_size"] for row in rows} == {5, 6, 8, 12, 16}
    for row in rows:
        assert row["frozen_event_weight_per_event"] == 1.0
        assert row["frozen_within_event_weight_per_candidate"] == 0.5
        assert row["rows_per_event"] == 2 * row["team_size"]
        assert row["frozen_within_event_weight_per_robot_candidate_row"] == (
            pytest.approx(0.5 / row["team_size"]))


def test_naive_row_mean_would_distort_by_team_size():
    rows = {row["team_size"]: row for row in
            load("phase9d_v2c_event_equal_weighting_v1.json")[
                "combined_demonstration"]}
    assert rows[16]["naive_relative_event_weight_vs_N5"] == pytest.approx(3.2)
    assert rows[5]["naive_row_mean_distortion_factor"] < 1.0
    assert rows[16]["naive_row_mean_distortion_factor"] > 1.0


# --------------------------------------------------------------------------
# C22 schema
# --------------------------------------------------------------------------
def test_train_feature_schema_is_frozen_and_clean():
    schema = load("phase9d_v2c_feature_schema_v1.json")
    assert schema["frozen_node_dim"] == 35
    assert schema["frozen_edge_dim"] == 19
    train = schema["train"]
    assert train["node_feature_dims"] == {"35": 90294}
    assert train["nonfinite_values"] == 0
    assert train["mask_length_violations"] == 0
    assert train["payload_validation_failures"] == 0
    assert train["row_identity_validation_failures"] == 0
    assert train["v1_schema_mixing"] is False
    assert train["zero_edge_rows_are_contract_valid"] is True


def test_validation_rows_were_validated_at_generation():
    validation = load("phase9d_v2c_feature_schema_v1.json")["validation"]
    assert validation["rows"] == 23220
    assert validation["row_validation_failure_total_recorded_at_generation"] == 0
    assert validation["every_row_revalidated_in_image_at_generation"] is True


# --------------------------------------------------------------------------
# C23 shift
# --------------------------------------------------------------------------
def test_no_major_structural_mismatch_between_splits():
    shift = load("phase9d_v2c_train_validation_shift_v1.json")
    assert shift["major_structural_mismatch_found"] is False
    assert shift["no_significance_threshold_invented"] is True
    assert shift["label_rate"]["within_frozen_gate"] is True
    assert shift["structural_categories_repeat"]["exact_structural_replication"]


def test_design_balance_is_uniform_in_both_splits():
    design = load("phase9d_v2c_train_validation_shift_v1.json")["design_balance"]
    assert design["design_is_uniform_in_both_splits"] is True
    assert design["train_validation_episode_ratio"] == 4.0


# --------------------------------------------------------------------------
# C21/C30/C31/C32 downstream
# --------------------------------------------------------------------------
def test_training_pipeline_is_not_v2_ready():
    pipeline = load("phase9d_v2c_training_pipeline_readiness_v1.json")
    assert pipeline["status"] == "TRAINING_PIPELINE_NOT_V2_READY"
    assert pipeline["evidence"][
        "all_three_are_generation_or_contract_modules_not_loaders"] is True
    assert pipeline["evidence"]["existing_loader"]["consumes_v2_rows"] is False
    assert pipeline["evidence"]["training_operations_performed"] == 0
    assert pipeline["model_training_authorised_by_this_phase"] is False


def test_loader_requirements_cover_the_frozen_semantics():
    requirements = load("phase9d_v2c_training_pipeline_readiness_v1.json")[
        "required_additive_loader"]
    assert requirements["must_be_additive"] is True
    joined = " ".join(requirements["requirements"])
    for needle in ("decision event", "raw row mean is prohibited",
                   "NONE_UNWEIGHTED_BCE", "Deterministic shuffling".lower(),
                   "GENERATION_INVALID"):
        assert needle.lower() in joined.lower(), needle


def test_model_training_contract_is_snapshot_only():
    contract = load("phase9d_v2c_model_training_contract_snapshot_v1.json")
    assert contract["status"] == "SNAPSHOT_ONLY_NOT_EXECUTED"
    budget = contract["hyperparameter_budget"]
    assert budget["maximum_searched_configurations"] == 12
    assert budget["maximum_steps"] == 50000
    assert budget["model_seeds"] == [11, 29, 47]
    assert budget["optimizer"] == "AdamW"
    for value in contract["execution_counters"].values():
        assert value == 0


def test_residual_remains_on_hold(readiness):
    residual = readiness["C32_residual_ordering"]
    assert residual["residual_v2_status"] == "HOLD"
    assert residual["residual_generation_operations"] == 0
    assert residual[
        "authority_releasing_residual_before_recoverability_training_found"] is False


# --------------------------------------------------------------------------
# C24/C25/C26/C27/C29 final
# --------------------------------------------------------------------------
def test_validation_independence_is_uncontaminated(readiness):
    independence = readiness["C24_validation_independence"]
    assert independence["commits_after_the_validation_closure_commit"] == 0
    assert independence["contamination_found"] is False
    assert independence["new_gates_invented"] == 0
    assert independence[
        "validation_remains_eligible_for_development_and_model_selection"] is True


def test_all_sealed_domains_remain_zero(readiness):
    for key, value in readiness["C25_sealed_domains"].items():
        if key == "sealed_information_influenced_this_audit":
            assert value is False
        else:
            assert value == 0, key


def test_zero_positive_families_final_classification(readiness):
    classification = readiness["C27_zero_positive_family_final_classification"]
    for family in ("F3", "F4", "F6"):
        assert classification[family] == (
            "LEGITIMATE_STRUCTURAL_ONE_CLASS_REGION_COMPATIBLE_WITH_H1")
    assert classification["classification_letter"] == "A"
    assert classification["incorporates_train_evidence"] is True
    assert classification["incorporates_validation_evidence"] is True
    assert len(classification["evidence"]) >= 5


def test_h1_is_scientifically_testable(readiness):
    testability = readiness["C26_h1_scientific_testability"]
    assert testability["both_candidate_classes_exist_globally"] is True
    assert testability["candidate_conditioned_differences_exist"] is True
    assert testability["validation_family_gate_passes"] is True
    assert testability["no_label_implementation_defect"] is True
    assert testability[
        "structural_one_class_families_violate_a_frozen_claim"] is False


def test_dataset_adequacy_finding_and_its_provisions(readiness):
    assert readiness["C29_dataset_adequacy_finding"] == (
        "RECOVERABILITY_V2_DATASET_ADEQUATE_WITH_DECLARED_STRUCTURAL_REGIONS")
    assert readiness["C29_finding_is_provisional_on"]


def test_verdict_is_audit_incomplete_with_bounded_outstanding_work(readiness):
    assert readiness["verdict"] == "E"
    assert readiness["recommendation"] == "AUDIT_INCOMPLETE"
    outstanding = readiness["outstanding_work"]
    assert outstanding["everything_outstanding_is_measurement_not_analysis"] is True
    assert outstanding["tasks"]
    assert outstanding["prepared_scripts"]


def test_no_training_step_was_authorised_here(readiness):
    boundary = readiness["C30_training_next_step_boundary"]
    assert boundary["model_training_performed_in_this_phase"] is False
    assert boundary["qualified_v2_training_loader_exists"] is False
    assert boundary["recommended_next_authorization"] == (
        "AUTHORIZE_RECOVERABILITY_V2_TRAINING_PIPELINE_IMPLEMENTATION")
    assert boundary["not_recommended"] == "START_MODEL_TRAINING"


# --------------------------------------------------------------------------
# C33 combined root
# --------------------------------------------------------------------------
def test_combined_root_references_and_does_not_rewrite():
    root = load("phase9d_v2c_combined_dataset_root_v1.json")
    assert root["references_only_does_not_rewrite"] is True
    assert root["underlying_datasets_mutated"] == 0
    assert root["train"]["composite_seal"] == TRAIN_SEAL
    assert root["validation"]["composite_seal"] == VAL_SEAL
    assert root["source_acquisition_protocol_sha256"] == FROZEN_PROTOCOL
    assert root["target_v4_contract_sha256"] == FROZEN_TARGET_V4
    assert root["recoverability_row_binding_v2_spec_sha256"] == FROZEN_ROW_BINDING
    assert root["training_authorized"] is False


def test_combined_root_totals_reconcile():
    root = load("phase9d_v2c_combined_dataset_root_v1.json")
    combined = root["combined"]
    assert combined["source_episodes"] == (
        root["train"]["source_episodes"] + root["validation"]["source_episodes"])
    assert combined["rows"] == root["train"]["rows"] + root["validation"]["rows"]
    assert combined["shards"] == (
        root["train"]["shards"] + root["validation"]["shards"])
    assert len(root["combined_development_dataset_root_sha256"]) == 64


def test_combined_root_split_policy_is_disjoint():
    policy = load("phase9d_v2c_combined_dataset_root_v1.json")["split_policy"]
    assert policy["layout_overlap"] == 0
    assert policy["source_episode_identity_overlap"] == 0
    assert policy["final_test_included"] is False
    assert policy["n24_included"] is False
    assert policy["study_b_included"] is False
