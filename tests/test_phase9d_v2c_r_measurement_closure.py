"""Phase 9D-V2C-R -- measurement closure for the combined Recoverability V2 audit.

Read-only tests pinning the measured artifacts against frozen gate authority.
No generation, no training, no sealed-domain access.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import pytest

from rvt_swarm.phase8.common import verify_canonical_hash

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results" / "rvt_fd24"

FROZEN_PROTOCOL = "19fa68a37d80f16ee1463b872f26402963daeb5a56f375423634a90dc1f3546d"
FROZEN_TARGET_V4 = "54a0e0baff79fbdc320800b772f47a40ac06ac4f0e70d4fab1bf676c54b918ee"
FROZEN_ROW_BINDING = "98f18a94c6a69d27a4cbf38169ca15e998ce4b4adfbba9a48cb1b3233391adf8"
TRAIN_SEAL = "a966f318832fb60bd99acdfdff72f0c7011d730f3e0fb51494ce318210f39bba"
VAL_SEAL = "667b117555a65ad9da7f8e6e7f71b2cfb6843cc66d8e8c35eb68650b7818ca69"
JOINT_CATEGORIES = ("BOTH_SUCCESS", "COMPACT_ONLY_SUCCESS",
                    "LINE_ONLY_SUCCESS", "BOTH_FAIL")
PRIMARY = ["F%d" % index for index in range(1, 11)]

ARTIFACTS = [
    "phase9d_v2c_r_gate7_replica_instability_v1.json",
    "phase9d_v2c_r_gate8_distribution_shift_v1.json",
    "phase9d_v2c_r_validation_joint_outcomes_v1.json",
    "phase9d_v2c_r_combined_joint_outcomes_v1.json",
    "phase9d_v2c_r_validation_target_v4_predicates_v1.json",
    "phase9d_v2c_r_validation_feature_schema_v1.json",
    "phase9d_v2c_r_graph_distribution_v1.json",
    "phase9d_v2c_r_validation_shard_integrity_v1.json",
    "phase9d_v2c_r_complete_gate_table_v1.json",
    "phase9d_v2c_r_final_readiness_v1.json",
]


def load(name):
    return json.loads((RESULTS / name).read_text(encoding="ascii"))


def hash_field(document):
    return next(key for key in document
                if key.startswith("phase9d_v2c_r_") and key.endswith("sha256"))


@pytest.fixture(scope="module")
def gate_table():
    return load("phase9d_v2c_r_complete_gate_table_v1.json")


@pytest.fixture(scope="module")
def gate7():
    return load("phase9d_v2c_r_gate7_replica_instability_v1.json")


@pytest.fixture(scope="module")
def gate8():
    return load("phase9d_v2c_r_gate8_distribution_shift_v1.json")


@pytest.fixture(scope="module")
def readiness():
    return load("phase9d_v2c_r_final_readiness_v1.json")


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


def test_historical_v2c_artifacts_are_not_rewritten():
    # the resume phase is additive; the prior audit's artifacts must still verify
    for name in ("phase9d_v2c_final_readiness_v1.json",
                 "phase9d_v2c_predeclared_gate_audit_v1.json",
                 "phase9d_v2c_scenario_semantic_authority_v1.json",
                 "phase9d_v2c_combined_dataset_root_v1.json"):
        document = load(name)
        field = next(key for key in document
                     if key.startswith("phase9d_v2c_") and key.endswith("sha256"))
        assert verify_canonical_hash(document, field), name


# --------------------------------------------------------------------------
# R1/R2/R3 gate 7
# --------------------------------------------------------------------------
def test_gate7_definition_is_recovered_not_invented(gate7):
    assert gate7["gate_id"] == 7
    assert gate7["threshold"] == 0.10
    assert gate7["permitted_maximum"] == 0.10
    assert gate7["unit"] == "candidate aggregate with more than one replica"
    assert "audit_phase9d_r_dataset_readonly.py" in (
        gate7["authority"]["implementation"])
    actual = hashlib.sha256(
        (ROOT / "docs/RVT_RECOVERABILITY_LABEL_AUDIT_GATES.md").read_bytes()
    ).hexdigest()
    assert gate7["authority"]["sha256"] == actual


def test_gate7_is_a_full_census_of_both_splits(gate7):
    assert gate7["census_complete"] is True
    splits = {row["split"] for row in gate7["per_family_candidate"]}
    assert splits == {"train", "validation"}
    families = {row["family"] for row in gate7["per_family_candidate"]}
    assert families == {"F8", "F9"}
    assert len(gate7["per_family_candidate"]) == 4 * 2  # 2 families x 2 candidates x 2 splits


def test_gate7_fails_on_the_measured_census(gate7):
    """The measured maximum exceeds the frozen threshold. Pinned so it cannot
    be silently lost: gate 7 is the one frozen gate this dataset does not meet."""
    assert gate7["result"] == "FAIL"
    assert gate7["maximum_stochastic_label_instability"] > 0.10
    assert gate7["failing_cell_count"] == 1
    failing = gate7["failing_cells"][0]
    assert failing["split"] == "train"
    assert failing["family"] == "F9"
    assert failing["candidate"] == "LINE"
    assert failing["unstable_aggregates"] == 59
    assert failing["stochastic_candidate_aggregates"] == 530
    assert failing["instability_rate"] == pytest.approx(59 / 530, abs=1e-8)
    assert failing["excess_unstable_aggregates"] == 6


def test_gate7_other_cells_are_inside_the_threshold(gate7):
    inside = [row for row in gate7["per_family_candidate"]
              if not (row["split"] == "train" and row["family"] == "F9"
                      and row["candidate"] == "LINE")]
    assert len(inside) == 7
    for row in inside:
        assert row["instability_rate"] <= 0.10, row
        assert row["unstable_aggregates"] <= row["stochastic_candidate_aggregates"]


def test_gate7_threshold_was_not_tuned_and_definition_not_reinterpreted(gate7):
    assert gate7["threshold"] == 0.10
    assert gate7["threshold_tuned"] is False
    assert gate7["definition_reinterpreted"] is False
    assert gate7["gate_has_a_scientific_scope_escape_clause"] is False


def test_gate7_rates_reconcile_with_their_counts(gate7):
    for row in gate7["per_family_candidate"]:
        expected = row["unstable_aggregates"] / row["stochastic_candidate_aggregates"]
        assert row["instability_rate"] == pytest.approx(expected, abs=1e-8)
        assert row["replica_executions"] == 3 * row["stochastic_candidate_aggregates"]


def test_replay_reproduced_the_sealed_labels_exactly(gate7):
    determinism = gate7["determinism"]
    assert determinism["all_replayed_aggregate_labels_match_the_sealed_ledger"]
    assert determinism["all_replayed_dispositions_match_the_sealed_ledger"]
    for split in ("train", "validation"):
        assert determinism[split]["aggregate_label_mismatches"] == 0
        assert determinism[split]["aggregate_disposition_mismatches"] == 0
        assert determinism[split]["events_absent_from_sealed_ledger"] == 0


def test_replay_wrote_nothing_into_official_data(gate7):
    assert gate7["read_only"]["rows_written"] == 0
    assert gate7["read_only"]["manifests_modified"] == 0
    assert gate7["read_only"]["seals_modified"] == 0


def test_r3_replica_arithmetic_is_exact(gate7):
    arithmetic = gate7["R3_replica_arithmetic"]
    assert arithmetic["approximation_used"] is False
    for scope in ("train", "validation", "combined"):
        assert arithmetic[scope]["matches"] is True
    assert arithmetic["train"]["computed"] == 14452
    assert arithmetic["validation"]["computed"] == 3710
    assert arithmetic["combined"]["computed"] == 18162


# --------------------------------------------------------------------------
# R4/R5/R6 gate 8
# --------------------------------------------------------------------------
def test_gate8_has_both_frozen_components(gate8):
    assert gate8["gate_id"] == 8
    assert gate8["components"] == 2
    assert gate8["rate_component"]["maximum_permitted_rate_difference"] == 0.15
    assert gate8["divergence_component"]["maximum_permitted_js_divergence"] == 0.15


def test_gate8_divergence_convention_is_explicit(gate8):
    divergence = gate8["divergence_component"]
    assert divergence["logarithm_base"] == 2
    assert divergence["smoothing_convention"].startswith("NONE")
    assert divergence["library_default_used"] is False
    assert tuple(divergence["category_order_frozen"]) == JOINT_CATEGORIES


def test_gate8_divergence_recomputes_from_the_published_counts(gate8):
    divergence = gate8["divergence_component"]
    left = divergence["train_counts"]
    right = divergence["validation_counts"]
    left_total, right_total = sum(left.values()), sum(right.values())
    p = [left[k] / left_total for k in JOINT_CATEGORIES]
    q = [right[k] / right_total for k in JOINT_CATEGORIES]
    middle = [(a + b) / 2.0 for a, b in zip(p, q)]

    def kl(first, second):
        return sum(a * math.log2(a / b)
                   for a, b in zip(first, second) if a > 0.0)

    recomputed = 0.5 * kl(p, middle) + 0.5 * kl(q, middle)
    assert divergence["jensen_shannon_divergence_base2"] == pytest.approx(
        recomputed, abs=1e-12)


def test_gate8_passes_both_components(gate8):
    assert gate8["rate_component"]["result"] == "PASS"
    assert gate8["divergence_component"]["result"] == "PASS"
    assert gate8["gate_result"] == "PASS"
    assert gate8["rate_component"][
        "maximum_candidate_positive_rate_difference"] <= 0.15
    assert gate8["divergence_component"][
        "jensen_shannon_divergence_base2"] <= 0.15


def test_gate8_rate_statistic_is_the_maximum_over_candidates(gate8):
    rate = gate8["rate_component"]
    assert rate["maximum_candidate_positive_rate_difference"] == pytest.approx(
        max(rate["per_candidate_absolute_difference"].values()), abs=1e-12)


def test_prior_descriptive_values_were_recomputed(gate8):
    prior = gate8["prior_descriptive_values_recomputed_not_accepted"]
    assert prior["agree"] is True


def test_per_family_shift_did_not_become_a_gate(gate8):
    shift = gate8["R6_per_family_shift_remains_descriptive"]
    assert shift["predeclared_per_family_label_rate_gate_exists"] is False
    assert shift["converted_into_a_gate"] is False
    assert gate8["no_posthoc_dimension_added_to_the_decision"] is True


# --------------------------------------------------------------------------
# R7/R8/R9 joint outcomes
# --------------------------------------------------------------------------
def test_validation_joint_outcomes_are_measured_not_estimated():
    joint = load("phase9d_v2c_r_validation_joint_outcomes_v1.json")
    assert joint["estimated_from_marginals"] is False
    assert joint["events"] == 1285
    assert joint["events_equal_retained_pairs"] is True
    assert sum(joint["counts"].values()) == 1285


def test_prior_lower_bounds_held_against_the_measured_counts():
    joint = load("phase9d_v2c_r_validation_joint_outcomes_v1.json")
    superseded = joint["supersedes_prior_lower_bounds"]
    assert superseded["bounds_held"] is True
    assert superseded["measured_COMPACT_ONLY"] >= superseded[
        "prior_COMPACT_ONLY_lower_bound"]
    assert superseded["measured_LINE_ONLY"] >= superseded[
        "prior_LINE_ONLY_lower_bound"]


def test_combined_joint_outcomes_reconcile():
    combined = load("phase9d_v2c_r_combined_joint_outcomes_v1.json")
    assert combined["combined_equals_train_plus_validation"] is True
    assert combined["combined_events_equal_retained_pairs"] is True
    assert combined["train"]["events"] == 5032
    assert combined["validation"]["events"] == 1285
    assert combined["combined"]["events"] == 6317
    assert sum(combined["combined"]["counts"].values()) == 6317


def test_joint_categories_use_explicit_recoverability_naming():
    combined = load("phase9d_v2c_r_combined_joint_outcomes_v1.json")
    assert combined["distinct_from_scenario_headroom_categories"] is True
    for scope in ("train", "validation", "combined"):
        for key in combined[scope]["counts"]:
            assert key.startswith("RECOVERABILITY_EVENT_")


def test_decisive_events_exist_in_both_splits():
    combined = load("phase9d_v2c_r_combined_joint_outcomes_v1.json")
    decisive = combined["decisive_events"]
    assert decisive["train"] >= 50
    assert decisive["validation"] >= 20
    assert decisive["combined"] == decisive["train"] + decisive["validation"]


def test_joint_by_family_sums_to_the_split_total():
    for name, total in (("phase9d_v2c_r_validation_joint_outcomes_v1.json", 1285),):
        document = load(name)
        summed = sum(sum(counts.values())
                     for counts in document["by_family"].values())
        assert summed == total


# --------------------------------------------------------------------------
# R10/R11 predicate decomposition
# --------------------------------------------------------------------------
def test_validation_predicates_use_repository_names():
    predicates = load("phase9d_v2c_r_validation_target_v4_predicates_v1.json")
    assert predicates["predicate_names_are_repository_authoritative"] is True
    assert predicates["relabelling_performed"] == 0
    assert predicates["rows_written"] == 0
    names = set()
    for cell in predicates["validation"]["by_cell"].values():
        names |= set(cell["failed_predicates"])
    assert "downstream_goal_complete" in names
    assert "collision_free_complete_horizon" in names


def test_zero_positive_families_fail_downstream_goal_complete_in_validation():
    predicates = load("phase9d_v2c_r_validation_target_v4_predicates_v1.json")
    comparison = predicates["R10_mechanism_comparison"]["validation"]
    for family in ("F3", "F4", "F6"):
        for candidate in ("COMPACT", "LINE"):
            cell = comparison["%s/%s" % (family, candidate)]
            assert cell["positives"] == 0
            assert cell["downstream_goal_complete_failures"] == cell["replicas"]
            assert cell["safety_infeasible"] == cell["replicas"]


def test_the_same_mechanism_repeats_in_both_splits():
    predicates = load("phase9d_v2c_r_validation_target_v4_predicates_v1.json")
    assert predicates["R10_mechanism_comparison"][
        "same_mechanism_repeats_independently"] is True


def test_validation_positive_control_produces_positives():
    control = load("phase9d_v2c_r_validation_target_v4_predicates_v1.json")[
        "R14_positive_control"]
    assert control["control_family"] == "F1"
    assert control["label_path_produces_positives_in_validation"] is True
    assert control["tuning_performed"] is False
    assert int(control["F1_COMPACT"]["labels"].get("1", 0)) > 0


def test_f10_compact_is_zero_positive_in_both_splits_without_violating_a_gate():
    f10 = load("phase9d_v2c_r_validation_target_v4_predicates_v1.json")[
        "R11_f10_compact"]
    assert f10["train_positive"] == 0
    assert f10["validation_positive"] == 0
    assert f10["train_line_positive"] > 0
    assert f10["validation_line_positive"] > 0
    assert f10["violates_an_existing_frozen_gate"] is False
    assert f10["positive_per_family_requirement_invented"] is False
    assert f10["joint_train"]["COMPACT_ONLY_SUCCESS"] == 0
    assert f10["joint_validation"]["COMPACT_ONLY_SUCCESS"] == 0


# --------------------------------------------------------------------------
# R12/R16 feature schema
# --------------------------------------------------------------------------
def test_validation_feature_schema_is_frozen_and_clean():
    schema = load("phase9d_v2c_r_validation_feature_schema_v1.json")
    assert schema["tensor_access_path"] == "graph_payload['tensors']"
    assert schema["earlier_wrong_key_bug_repeated"] is False
    validation = schema["validation"]
    assert validation["rows"] == 23220
    assert validation["node_feature_dimensions"] == {"35": 23220}
    assert validation["non_finite_values"] == 0
    assert validation["mask_length_violations"] == 0
    assert validation["row_validation_failure_total"] == 0
    assert validation["duplicate_row_ids"] == 0
    assert validation["groups_with_wrong_row_count"] == 0
    assert validation["rows_with_zero_nodes"] == 0


def test_combined_feature_validity_is_complete():
    combined = load("phase9d_v2c_r_validation_feature_schema_v1.json")["R16_combined"]
    assert combined["rows"] == 113514
    assert combined["rows_match_expected"] is True
    assert combined["node_dimension_uniform_across_both_splits"] is True
    assert combined["edge_dimension_uniform_across_both_splits"] is True
    assert combined["single_feature_schema_hash_across_both_splits"] is True
    for key in ("schema_mismatch", "non_finite_feature", "unexpected_empty_graph",
                "candidate_topology_encoding_error", "row_identity_failure",
                "zero_node_rows"):
        assert combined[key] == 0, key


def test_validation_schema_binds_the_three_contracts():
    schema = load("phase9d_v2c_r_validation_feature_schema_v1.json")
    assert schema["source_acquisition_protocol_sha256"] == FROZEN_PROTOCOL
    assert schema["target_v4_contract_sha256"] == FROZEN_TARGET_V4
    assert schema["recoverability_row_binding_v2_spec_sha256"] == FROZEN_ROW_BINDING


# --------------------------------------------------------------------------
# R13/R17 distributions
# --------------------------------------------------------------------------
def test_graph_distribution_is_descriptive_only():
    distribution = load("phase9d_v2c_r_graph_distribution_v1.json")
    assert distribution["descriptive_only"] is True
    assert distribution["new_statistical_gates_created"] == 0
    assert distribution["structural_incompatibility_found"] is False


def test_candidate_topology_rows_are_balanced_in_both_splits():
    topology = load("phase9d_v2c_r_graph_distribution_v1.json")["candidate_topology"]
    for split in ("train", "validation"):
        counts = list(topology[split].values())
        assert len(counts) == 2 and counts[0] == counts[1]
    assert topology["balanced_in_both_splits"] is True


def test_split_hygiene_is_zero_on_every_axis():
    hygiene = load("phase9d_v2c_r_graph_distribution_v1.json")[
        "split_hygiene_measured"]
    assert len(hygiene) >= 8
    for axis, value in hygiene.items():
        assert value["overlap"] == 0, axis
    assert hygiene["row_ids"]["train"] == 90294
    assert hygiene["row_ids"]["validation"] == 23220


# --------------------------------------------------------------------------
# R14/R15/R22 integrity
# --------------------------------------------------------------------------
def test_validation_shards_verify_byte_for_byte():
    integrity = load("phase9d_v2c_r_validation_shard_integrity_v1.json")
    validation = integrity["validation"]
    assert validation["shards_verified"] == validation["shards_declared"] == 12
    assert validation["shard_failures"] == []
    assert validation["byte_mismatches"] == 0
    assert validation["rows_counted"] == validation["rows_declared"] == 23220
    assert validation["bytes_counted"] == validation["bytes_declared"]
    assert validation["composite_seal_matches"] is True
    assert validation["composite_seal_recomputed"] == VAL_SEAL


def test_train_seal_is_reverified_unchanged():
    integrity = load("phase9d_v2c_r_validation_shard_integrity_v1.json")
    train = integrity["train_reverification"]
    assert train["shards_verified"] == train["shards_declared"] == 44
    assert train["shard_failures"] == []
    assert train["rows_counted"] == 90294
    assert train["composite_seal_matches"] is True
    assert train["composite_seal_recomputed"] == TRAIN_SEAL
    assert all(train["roots_match"].values())


def test_no_sealed_dataset_integrity_failure():
    integrity = load("phase9d_v2c_r_validation_shard_integrity_v1.json")
    assert integrity["sealed_dataset_integrity_failure"] is False


def test_row_root_algorithm_is_the_frozen_one():
    algorithm = load("phase9d_v2c_r_validation_shard_integrity_v1.json")[
        "R15_row_root_algorithm"]
    assert algorithm["algorithm"] == "sha256_document(sorted(scientific_row_id))"
    assert algorithm["shard_hash_aggregation_used"] is False
    assert algorithm["train_row_root_matches"] is True
    assert algorithm["validation_row_root_matches"] is True


def test_all_six_roots_match_in_both_splits():
    integrity = load("phase9d_v2c_r_validation_shard_integrity_v1.json")
    for scope in ("validation", "train_reverification"):
        assert all(integrity[scope]["roots_match"].values()), scope


# --------------------------------------------------------------------------
# R19 complete gate table
# --------------------------------------------------------------------------
def test_gate_table_covers_every_frozen_gate(gate_table):
    assert [row["gate_id"] for row in gate_table["gates"]] == list(range(1, 10))
    assert gate_table["total_gates"] == 9
    assert gate_table["new_gates_invented"] == 0
    assert gate_table["posthoc_threshold_added"] == 0


def test_no_gate_remains_unevaluated(gate_table):
    assert gate_table["gates_not_evaluated"] == []
    assert gate_table["every_gate_measured"] is True
    for row in gate_table["gates"]:
        assert row["result"] in {"PASS", "FAIL"}
        assert row["measurement_source"]


def test_eight_gates_pass_and_gate_seven_fails(gate_table):
    assert gate_table["gates_passing"] == [1, 2, 3, 4, 5, 6, 8, 9]
    assert gate_table["gates_failing"] == [7]


def test_gate_table_authority_hash_matches_the_document(gate_table):
    actual = hashlib.sha256(
        (ROOT / "docs/RVT_RECOVERABILITY_LABEL_AUDIT_GATES.md").read_bytes()
    ).hexdigest()
    assert gate_table["authority_sha256"] == actual


# --------------------------------------------------------------------------
# R18/R20/R22/R23 closure
# --------------------------------------------------------------------------
def test_scenario_semantic_resolution_is_preserved(readiness):
    semantics = readiness["R18_scenario_semantics"]
    assert semantics["reopened"] is False
    assert semantics["statement"] == (
        "H2_EPISODE_HEADROOM != H1_MID_TRAJECTORY_RECOVERABILITY_LABEL")
    for family in ("F3", "F4", "F6"):
        assert semantics["classification"][family] == (
            "LEGITIMATE_STRUCTURAL_ONE_CLASS_REGION_COMPATIBLE_WITH_H1")


def test_training_pipeline_status_is_only_confirmed(readiness):
    pipeline = readiness["R20_training_pipeline"]
    assert pipeline["status"] == "TRAINING_PIPELINE_NOT_V2_READY"
    assert pipeline["loader_implemented_in_this_phase"] is False
    assert pipeline["training_operations"] == 0
    assert pipeline["probe_models"] == 0
    assert pipeline["hyperparameter_trials"] == 0


def test_no_data_mutation(readiness):
    mutation = readiness["R22_no_data_mutation"]
    assert mutation["train_namespace_mutation"] == 0
    assert mutation["validation_namespace_mutation"] == 0
    assert mutation["train_shard_count_before"] == mutation["train_shard_count_after"]
    assert mutation["validation_shard_count_before"] == (
        mutation["validation_shard_count_after"])
    assert mutation["train_seal_unchanged"] is True
    assert mutation["validation_seal_unchanged"] is True


def test_sealed_domains_all_zero(readiness):
    for key, value in readiness["R23_sealed_domains"].items():
        assert value == 0, key


def test_final_classification_and_verdict(readiness):
    assert readiness["final_dataset_classification"] == (
        "RECOVERABILITY_V2_DATASET_ADEQUATE_WITH_DECLARED_STRUCTURAL_REGIONS")
    assert readiness["verdict"] == "A"
    assert readiness["recommendation"] == "DO_NOT_TRAIN"
    assert readiness["training_authorized_by_this_phase"] is False
    assert readiness["gate_summary"]["failing"] == [7]


def test_no_forbidden_remedy_was_applied(readiness):
    meaning = readiness["what_this_does_and_does_not_mean"]
    assert "tuning the 0.10 threshold" in meaning["forbidden_responses"]
    assert meaning["owner_options_not_exercised_here"]
    gate7 = load("phase9d_v2c_r_gate7_replica_instability_v1.json")
    assert gate7["threshold"] == 0.10


def test_gate7_failure_does_not_reopen_the_scenario_semantics(readiness):
    semantics = readiness["R18_scenario_semantics"]
    assert semantics["gate7_failure_is_unrelated_to_this_question"] is True
    assert semantics["new_measurements_confirm_rather_than_disturb_it"] is True


def test_readiness_lists_no_outstanding_measurement(readiness):
    assert readiness["outstanding_measurements"] == []
    assert readiness["supersedes"]["previous_verdict"] == "E"
