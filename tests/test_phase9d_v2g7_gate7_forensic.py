"""Phase 9D-V2G7 -- Gate-7 forensic root-cause audit.

Read-only tests over the forensic artifacts. These preserve historical facts:
in particular that TRAIN F9/LINE measured 59/530 = 0.1113207547 against a
frozen 0.10 and that gate 7 therefore FAILED for Recoverability V2. No test
here may be written so that 59/530 passes the 0.10 gate.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import pytest

from rvt_swarm.phase8.common import verify_canonical_hash
from rvt_swarm.phase8.targets import (
    DETERMINISTIC_ROLLOUT_REPLICAS,
    ROLLOUT_AGGREGATION,
    STOCHASTIC_ROLLOUT_REPLICAS,
)
from rvt_swarm.phase9c_rb.counterfactual import replica_count_for_family

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results" / "rvt_fd24"

GATE7_THRESHOLD = 0.10
FAILING_UNSTABLE = 59
FAILING_DENOMINATOR = 530

ARTIFACTS = [
    "phase9d_v2g7_gate_authority_v1.json",
    "phase9d_v2g7_exact_cell_recount_v1.json",
    "phase9d_v2g7_f9_line_unstable_manifest_v1.json",
    "phase9d_v2g7_replica_pattern_audit_v1.json",
    "phase9d_v2g7_random_stream_audit_v1.json",
    "phase9d_v2g7_replay_determinism_v1.json",
    "phase9d_v2g7_failure_predicate_audit_v1.json",
    "phase9d_v2g7_localization_audit_v1.json",
    "phase9d_v2g7_statistical_context_v1.json",
    "phase9d_v2g7_replica_count_analysis_v1.json",
    "phase9d_v2g7_target_semantics_v1.json",
    "phase9d_v2g7_root_cause_v1.json",
    "phase9d_v2g7_dataset_status_v1.json",
    "phase9d_v2g7_remediation_options_v1.json",
    "phase9d_v2g7_v3_data_reuse_matrix_v1.json",
    "phase9d_v2g7_owner_decision_package_v1.json",
    "phase9d_v2g7_final_readiness_v1.json",
]


def load(name):
    return json.loads((RESULTS / name).read_text(encoding="ascii"))


def hash_field(document):
    return next(key for key in document
                if key.startswith("phase9d_v2g7_") and key.endswith("sha256"))


@pytest.fixture(scope="module")
def recount():
    return load("phase9d_v2g7_exact_cell_recount_v1.json")


@pytest.fixture(scope="module")
def authority():
    return load("phase9d_v2g7_gate_authority_v1.json")


@pytest.fixture(scope="module")
def readiness():
    return load("phase9d_v2g7_final_readiness_v1.json")


@pytest.fixture(scope="module")
def unstable_events():
    path = RESULTS / "phase9d_v2g7_f9_line_unstable_events_v1.jsonl"
    return [json.loads(line) for line in
            path.read_text(encoding="ascii").splitlines() if line.strip()]


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


def test_earlier_gate7_failure_artifact_still_verifies_and_still_says_fail():
    """The historical record must survive this phase untouched."""
    prior = load("phase9d_v2c_r_gate7_replica_instability_v1.json")
    assert verify_canonical_hash(
        prior, "phase9d_v2c_r_gate7_replica_instability_sha256")
    assert prior["result"] == "FAIL"
    assert prior["threshold"] == GATE7_THRESHOLD


# --------------------------------------------------------------------------
# G1 authority and chronology
# --------------------------------------------------------------------------
def test_gate7_threshold_is_unchanged(authority):
    assert authority["threshold"] == GATE7_THRESHOLD
    assert authority["threshold_direction"] == "at most"
    assert authority["gate_modified_in_this_phase"] is False
    assert authority["gate_reinterpreted_in_this_phase"] is False


def test_gate7_is_prospective(authority):
    chronology = authority["creation_chronology"]
    assert chronology["gate_is_prospective"] is True
    assert chronology["gate_document_ever_modified"] is False
    assert chronology["gate_document_commits_total"] == 1
    assert chronology["specification_predates_official_train_by_days"] >= 1
    assert chronology["implementation_predates_official_train_by_hours"] >= 1


def test_gate7_authority_hash_matches_the_live_document(authority):
    actual = hashlib.sha256(
        (ROOT / "docs/RVT_RECOVERABILITY_LABEL_AUDIT_GATES.md").read_bytes()
    ).hexdigest()
    assert authority["authority_hash"] == actual


def test_gate7_has_no_escape_clause(authority):
    assert authority["scientific_escape_clause"] is None
    assert "gate 3" in authority["escape_clause_comparison"]


# --------------------------------------------------------------------------
# G2 the failure, reproduced
# --------------------------------------------------------------------------
def test_failure_is_reproduced_exactly(recount):
    assert recount["gate_result"] == "FAIL"
    assert recount["reproduces_previous_phase"] is True
    assert recount["recomputed_value"] == pytest.approx(
        FAILING_UNSTABLE / FAILING_DENOMINATOR, abs=1e-9)
    assert recount["maximum_instability_rate"] > GATE7_THRESHOLD


def test_the_failing_cell_is_train_f9_line(recount):
    failing = recount["failing_cells"]
    assert len(failing) == 1
    cell = failing[0]
    assert (cell["split"], cell["family"], cell["candidate"]) == (
        "train", "F9", "LINE")
    assert cell["unstable"] == FAILING_UNSTABLE
    assert cell["aggregates"] == FAILING_DENOMINATOR


def test_all_eight_cells_were_recounted(recount):
    assert len(recount["cells"]) == 8
    assert recount["aggregates_replayed"] == 2764
    for cell in recount["cells"]:
        expected = cell["unstable"] / cell["aggregates"]
        assert cell["instability_rate"] == pytest.approx(expected, abs=1e-12)
        assert (cell["stable_all_positive"] + cell["stable_all_negative"]
                + cell["unstable"]) == cell["aggregates"]


def test_seven_cells_pass_and_one_fails(recount):
    results = [c["result"] for c in recount["cells"]]
    assert results.count("PASS") == 7
    assert results.count("FAIL") == 1


# --------------------------------------------------------------------------
# G3 the 59
# --------------------------------------------------------------------------
def test_unstable_event_manifest_is_complete_and_hashed(unstable_events):
    manifest = load("phase9d_v2g7_f9_line_unstable_manifest_v1.json")
    assert manifest["records"] == FAILING_UNSTABLE == len(unstable_events)
    path = RESULTS / "phase9d_v2g7_f9_line_unstable_events_v1.jsonl"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == manifest["sha256"]
    assert manifest["rows_modified"] == 0


def test_every_enumerated_event_is_genuinely_unstable(unstable_events):
    for event in unstable_events:
        assert event["family"] == "F9"
        assert event["split"] == "train"
        assert event["candidate_topology"] == "LINE"
        assert len(set(event["replica_labels"])) > 1
        assert len(event["replica_labels"]) == 3
        assert event["aggregate_label"] == 0
        assert event["aggregate_disposition"] == "VALID_TASK_NEGATIVE"
        assert event["rows_modified"] == 0


def test_enumerated_events_match_the_sealed_ledger(unstable_events):
    for event in unstable_events:
        assert int(event["sealed_aggregate_label"]) == int(event["aggregate_label"])
        assert event["sealed_aggregate_disposition"] == event["aggregate_disposition"]


def test_enumerated_events_share_one_initial_state_and_diverge_after(unstable_events):
    for event in unstable_events:
        assert len(set(event["replica_final_state_hashes"])) > 1
        assert len(set(event["matched_disturbance_seeds"])) == 3


# --------------------------------------------------------------------------
# G4/G14 patterns and aggregation
# --------------------------------------------------------------------------
def test_bit_patterns_sum_to_the_cell_totals():
    patterns = load("phase9d_v2g7_replica_pattern_audit_v1.json")["by_cell"]
    recount = load("phase9d_v2g7_exact_cell_recount_v1.json")["cells"]
    index = {f"{c['split']}/{c['family']}/{c['candidate']}": c for c in recount}
    for key, value in patterns.items():
        assert sum(value["patterns"].values()) == index[key]["aggregates"]
        assert value["unstable"] == index[key]["unstable"]


def test_failing_cell_bit_pattern_counts_are_pinned():
    detail = load("phase9d_v2g7_replica_pattern_audit_v1.json")["failing_cell_detail"]
    assert detail["patterns"] == {"000": 217, "001": 9, "010": 8, "100": 10,
                                  "011": 5, "101": 19, "110": 8, "111": 254}
    assert detail["one_success_two_failure"] == 27
    assert detail["two_success_one_failure"] == 32
    assert detail["unstable_total"] == FAILING_UNSTABLE


def test_all_success_aggregation_holds_everywhere():
    mapping = load("phase9d_v2g7_replica_pattern_audit_v1.json")["G14_aggregation_mapping"]
    assert mapping["rule"].startswith("all_success")
    assert ROLLOUT_AGGREGATION == "all_success"
    assert mapping["observed_violations"] == 0
    assert mapping["mapping"]["111"] == 1
    for pattern, label in mapping["mapping"].items():
        if pattern != "111":
            assert label == 0


def test_mixed_replica_events_are_valid_not_invalid():
    mapping = load("phase9d_v2g7_replica_pattern_audit_v1.json")["G14_aggregation_mapping"]
    assert mapping["verdict"] == (
        "VALID_ROBUST_NEGATIVE_LABELS_WITH_MIXED_REPLICA_EVIDENCE")
    assert mapping["generation_invalid_aggregates"] == 0
    assert set(mapping["mixed_pattern_dispositions"]) == {"VALID_TASK_NEGATIVE"}
    assert set(mapping["mixed_pattern_labels"]) == {"0"}


# --------------------------------------------------------------------------
# G5/G6 no implementation defect
# --------------------------------------------------------------------------
def test_no_gate7_implementation_defect():
    stream = load("phase9d_v2g7_random_stream_audit_v1.json")
    assert stream["GATE7_IMPLEMENTATION_DEFECT"] is False


def test_no_replica_index_is_a_systematic_dissenter():
    audit = load("phase9d_v2g7_random_stream_audit_v1.json")["G5_replica_index_audit"]
    assert audit["any_cell_significant_at_0.05"] is False
    assert audit["maximum_chi_square"] < audit["critical_value_2df_0.05"]


def test_matched_randomness_holds_exactly():
    matched = load("phase9d_v2g7_random_stream_audit_v1.json")["G6_matched_randomness"]
    assert matched["matched_stream_mismatches"] == 0
    assert matched["required_mismatches"] == 0
    assert matched["matched_seed_collisions"] == 0
    assert matched["candidate_job_seeds_equal_across_candidates"] == 0
    assert matched["events_with_divergent_initial_clone_hash"] == 0


def test_the_disturbance_reaches_every_rollout():
    matched = load("phase9d_v2g7_random_stream_audit_v1.json")["G6_matched_randomness"]
    assert matched["disturbance_demonstrably_applied"] is True
    assert matched["aggregates_with_divergent_final_state"] == (
        matched["aggregates_total"])


# --------------------------------------------------------------------------
# G7 determinism is not the same as disagreement
# --------------------------------------------------------------------------
def test_replay_determinism_and_stochastic_disagreement_are_distinct():
    determinism = load("phase9d_v2g7_replay_determinism_v1.json")
    assert determinism["REPLAY_DETERMINISM"] == "CONFIRMED"
    assert determinism["CROSS_REPLICA_STOCHASTIC_DISAGREEMENT"] == "PRESENT"
    assert determinism["the_two_are_distinct"] is True
    assert determinism["aggregate_label_mismatches"] == 0
    assert determinism["aggregate_disposition_mismatches"] == 0
    assert determinism["official_rows_created"] == 0


# --------------------------------------------------------------------------
# G8 predicate decomposition
# --------------------------------------------------------------------------
def test_one_predicate_flips_in_every_unstable_failing_cell_event():
    failing = load("phase9d_v2g7_failure_predicate_audit_v1.json")["failing_cell"]
    assert failing["universal_flip"] == "target_metric_v3_dwell_complete"
    assert failing["universal_flip_count"] == FAILING_UNSTABLE
    assert failing["universal_flip_fraction"] == 1.0


def test_predicate_names_come_from_the_frozen_contract():
    audit = load("phase9d_v2g7_failure_predicate_audit_v1.json")
    from rvt_swarm.phase8.targets import TaskRecoveryConditions
    declared = set(TaskRecoveryConditions.__dataclass_fields__)
    assert set(audit["predicate_set"]) <= declared
    assert audit["relabelling_performed"] == 0


# --------------------------------------------------------------------------
# G9/G10 localization
# --------------------------------------------------------------------------
def test_instability_is_broadly_distributed():
    conclusion = load("phase9d_v2g7_localization_audit_v1.json")["G9_conclusion"]
    assert conclusion["distribution"] == "BROADLY_DISTRIBUTED"
    assert len(conclusion["evidence"]) >= 3
    assert len(conclusion["systematic_structure"]) >= 3


def test_no_post_hoc_subgroup_gate_was_created():
    audit = load("phase9d_v2g7_localization_audit_v1.json")
    assert audit["descriptive_only"] is True
    assert audit["post_hoc_subgroup_gates_created"] == 0


def test_validation_does_not_override_train():
    comparison = load("phase9d_v2g7_localization_audit_v1.json")["G10_train_validation"]
    assert comparison["validation_does_not_override_train"] is True
    assert comparison["train_f9_line"]["rate"] > GATE7_THRESHOLD
    assert comparison["validation_f9_line"]["rate"] < GATE7_THRESHOLD
    assert comparison["structure_replicates"] is True


# --------------------------------------------------------------------------
# G11 statistics never convert the gate
# --------------------------------------------------------------------------
def test_statistical_context_does_not_change_the_verdict():
    context = load("phase9d_v2g7_statistical_context_v1.json")
    assert context["v2_gate_verdict_changed_by_this_analysis"] is False
    assert context["retroactive_pass_asserted"] is False
    assert "EMPIRICAL DATASET GATE" in context["CRITICAL"]


def test_exact_interval_and_test_recompute():
    failing = load("phase9d_v2g7_statistical_context_v1.json")["failing_cell"]
    n, k = FAILING_DENOMINATOR, FAILING_UNSTABLE

    def cdf(j, total, p):
        return sum(math.comb(total, i) * p ** i * (1 - p) ** (total - i)
                   for i in range(0, j + 1))

    recomputed = 1.0 - cdf(k - 1, n, GATE7_THRESHOLD)
    assert failing["exact_one_sided_p_value"] == pytest.approx(recomputed, abs=1e-8)
    low, high = failing["clopper_pearson_95"]
    assert low < k / n < high


def test_the_observed_rate_still_exceeds_the_threshold():
    """Explicit guard: no analysis in this phase may make 59/530 <= 0.10."""
    assert FAILING_UNSTABLE / FAILING_DENOMINATOR > GATE7_THRESHOLD


# --------------------------------------------------------------------------
# G12/G13 semantics and replica count
# --------------------------------------------------------------------------
def test_replica_counts_match_the_frozen_contract():
    semantics = load("phase9d_v2g7_target_semantics_v1.json")
    assert semantics["replica_count"]["F8"] == replica_count_for_family("F8") == 3
    assert semantics["replica_count"]["F9"] == replica_count_for_family("F9") == 3
    assert replica_count_for_family("F1") == DETERMINISTIC_ROLLOUT_REPLICAS == 1
    assert STOCHASTIC_ROLLOUT_REPLICAS == 3


def test_target_semantics_are_robustness_not_probability():
    semantics = load("phase9d_v2g7_target_semantics_v1.json")
    assert semantics["intended_target_v4_semantics"] == (
        "ROBUST_RECOVERABILITY_UNDER_ALL_SAMPLED_DISTURBANCES")
    assert semantics["aggregation"]["mixed_outcomes_block_the_row"] is False
    assert semantics["aggregation"]["only_numerical_invalidity_blocks_the_row"] is True
    assert semantics["G12_gate7_alignment"]["gate7_declared_misaligned"] is False


def test_more_replicas_cannot_fix_gate_seven():
    analysis = load("phase9d_v2g7_replica_count_analysis_v1.json")
    assert analysis["answer"].startswith("NO")
    assert analysis["official_protocol_changed"] is False
    for row in analysis["table"]:
        previous = None
        for replicas in (1, 3, 5, 7, 9, 15):
            value = row["R%d" % replicas]
            if previous is not None:
                assert value >= previous
            previous = value


def test_disagreement_probability_formula_is_monotone_in_r():
    for p in (0.05, 0.2, 0.5):
        values = [1 - p ** r - (1 - p) ** r for r in range(1, 12)]
        assert all(b > a for a, b in zip(values, values[1:]))


# --------------------------------------------------------------------------
# G15/G16 root cause and status
# --------------------------------------------------------------------------
def test_root_cause_is_intrinsic_stochastic_boundary():
    root = load("phase9d_v2g7_root_cause_v1.json")
    assert root["classification_letter"] == "C"
    assert root["primary_classification"] == (
        "INTRINSIC_STOCHASTIC_BOUNDARY_WITH_VALID_CURRENT_LABELS")
    assert root["GATE7_IMPLEMENTATION_DEFECT"] is False
    assert root["gate7_measurement_invalidated"] is False
    assert len(root["evidence_for_C"]) >= 6


def test_defect_alternatives_are_explicitly_excluded():
    excluded = load("phase9d_v2g7_root_cause_v1.json")["alternatives_excluded"]
    for key in ("A_IMPLEMENTATION_OR_PROVENANCE_DEFECT",
                "B_TARGET_LABEL_IMPLEMENTATION_DEFECT",
                "D_SOURCE_ACQUISITION_DEFECT", "F_INSUFFICIENT_EVIDENCE"):
        assert excluded[key]["excluded"] is True


def test_dataset_remains_blocked_but_informative():
    status = load("phase9d_v2g7_dataset_status_v1.json")
    assert status["training_status"] == "BLOCKED_FOR_TRAINING_UNDER_FROZEN_GATE7"
    assert status["scientific_status"] == (
        "SCIENTIFICALLY_INFORMATIVE_FOR_PROTOCOL_DEVELOPMENT")
    assert status["marked_adequate_for_training"] is False
    assert status["deletion_authorized"] is False
    assert status["measurement_invalidating_defect_found"] is False


# --------------------------------------------------------------------------
# G17-G25 remediation
# --------------------------------------------------------------------------
def test_no_remediation_was_implemented():
    options = load("phase9d_v2g7_remediation_options_v1.json")
    assert options["none_implemented"] is True
    assert len(options["options"]) == 5


def test_posthoc_options_are_labelled_as_such():
    options = load("phase9d_v2g7_remediation_options_v1.json")
    assert set(options["POSTHOC_SALVAGE"]) == {"A", "B"}
    assert set(options["CLEAN_PROSPECTIVE_REPAIR"]) == {"D", "E"}
    threshold_option = next(o for o in options["options"] if o["id"] == "A")
    assert threshold_option["class"] == "POSTHOC_SALVAGE"
    assert threshold_option["recommended_merely_because_cheap"] is False


def test_ranking_places_prospective_repairs_above_salvage():
    ranking = load("phase9d_v2g7_remediation_options_v1.json")[
        "G25_ranking_by_scientific_defensibility"]
    positions = {row["option"]: row["rank"] for row in ranking}
    assert positions["E"] < positions["A"]
    assert positions["D"] < positions["A"]
    assert positions["E"] < positions["B"]
    assert positions["D"] < positions["B"]


def test_validation_contamination_is_declared():
    reuse = load("phase9d_v2g7_v3_data_reuse_matrix_v1.json")
    contamination = reuse["G22_validation_contamination"]
    assert contamination["fresh_independent_validation_identities_required"] is True
    assert contamination["final_test_layouts_must_not_be_used"] is True
    assert contamination["generated_in_this_phase"] == 0


def test_reuse_matrix_marks_labels_unusable_under_semantics_change():
    assets = {row["asset"]: row for row in
              load("phase9d_v2g7_v3_data_reuse_matrix_v1.json")["G23_asset_reuse"]}
    assert assets["aggregate labels"]["target_semantics_change"].startswith(
        "NOT REUSABLE")
    assert assets["robot-local rows (113514)"][
        "target_semantics_change"].startswith("NOT REUSABLE")


def test_provenance_consequences_require_new_identity_for_semantic_change():
    consequences = {row["option"][0]: row for row in
                    load("phase9d_v2g7_v3_data_reuse_matrix_v1.json")[
                        "G24_provenance_consequences"]}
    for option in ("C", "D", "E"):
        assert consequences[option]["new_target_contract_hash"] is True
        assert consequences[option]["new_row_identity_version"] is True
        assert consequences[option]["new_dataset_namespace"] is True


# --------------------------------------------------------------------------
# G26/G27/G28 closure
# --------------------------------------------------------------------------
def test_owner_decision_package_offers_exactly_four_choices():
    package = load("phase9d_v2g7_owner_decision_package_v1.json")
    assert [choice["id"] for choice in package["choices"]] == [1, 2, 3, 4]
    assert package["agent_selected_a_decision"] is False
    assert package["decision_is_the_owners"] is True


def test_posthoc_amendment_choice_is_labelled_weaker():
    package = load("phase9d_v2g7_owner_decision_package_v1.json")
    amend = next(c for c in package["choices"] if c["id"] == 2)
    assert amend["label"] == "SCIENTIFICALLY WEAKER"


def test_final_test_remains_sealed(readiness):
    sealed = readiness["G26_final_test_sealed"]
    assert sealed["final_test_layout_hashes_inspected"] == 0
    assert sealed["final_test_outcomes_inspected"] == 0
    assert sealed["n24_sealed_evaluation_accessed"] == 0
    assert sealed["study_b_accessed"] == 0
    assert sealed["successor_protocol_designed_without_final_test_evidence"] is True


def test_all_sealed_domain_counters_are_zero(readiness):
    for key, value in readiness["sealed_domains"].items():
        assert value == 0, key


def test_nothing_was_mutated(readiness):
    mutation = readiness["no_mutation"]
    assert mutation["train_shard_count"] == 44
    assert mutation["validation_shard_count"] == 12
    assert mutation["forensic_replay_rows_written_into_official_data"] == 0
    assert mutation["official_mounts"] == "read-only"


def test_final_verdict_and_recommendation(readiness):
    assert readiness["verdict"] == "B"
    assert readiness["final_root_cause_letter"] == "C"
    assert readiness["v2_marked_pass"] is False
    assert readiness["dataset_training_status"] == (
        "BLOCKED_FOR_TRAINING_UNDER_FROZEN_GATE7")
    recommendation = readiness["G28_agent_recommendation"]
    assert recommendation["recommended_option"] == 3
    assert recommendation["agent_did_not_perform_it"] is True
    assert recommendation["owner_authorization_required"] is True


def test_every_required_question_is_answered(readiness):
    answers = readiness["Q_answers"]
    assert len(answers) == 15
    for key, value in answers.items():
        assert value, key
