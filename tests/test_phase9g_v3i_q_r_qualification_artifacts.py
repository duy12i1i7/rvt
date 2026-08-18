"""Phase 9G-V3I-Q-R -- the qualification record.

Separate from the implementation tests: this file pins what was measured,
including the two limitations that were declared rather than smoothed over.
"""
from __future__ import annotations

import json
import pathlib

import pytest

from rvt_swarm.phase8.common import verify_canonical_hash

RESULTS = pathlib.Path("results/rvt_fd24")
PREFIX = "phase9g_v3i_q_r_"

ARTIFACTS = (
    "environment_baseline", "implementation_binding", "invalidity_binding",
    "compiler_qualification", "replica_execution", "no_early_abort",
    "supervision_schema", "pair_atomicity", "s8_accounting", "row_binding",
    "loader_grouping", "loss_qualification", "brier_qualification",
    "registry_guard", "v1_v2_regression", "reference_canary", "determinism",
    "failure_resume", "image_provenance", "windows_target",
    "target_semantic_replay", "official_data_protection", "final_readiness",
)

CANARY_DIGEST = (
    "95dbdab76ce8066f6e535c09a86dca73bb4018e135c590a0ac72584b992df340")
FINAL_COMMIT = "beb65ba6eedcf0eebba07cde57a361b9956d15be"
INVALIDITY = "66bdd9ffce3f0b6417f20c4b41602b5ea4be266a728bcdb1dd306b0e27ef5c75"


def load(stem):
    return json.loads((RESULTS / f"{PREFIX}{stem}_v1.json").read_text())


@pytest.mark.parametrize("stem", ARTIFACTS)
def test_artifact_exists_and_self_verifies(stem):
    document = load(stem)
    field = next(key for key in document
                 if key.startswith(PREFIX) and key.endswith("sha256"))
    assert verify_canonical_hash(document, field)


def test_all_twenty_three_required_artifacts_and_no_more():
    found = sorted(path.name for path in RESULTS.glob(f"{PREFIX}*.json"))
    assert found == sorted(f"{PREFIX}{stem}_v1.json" for stem in ARTIFACTS)


# ------------------------------------------------------------------ R0
def test_baseline_is_classified_tool_environment_only():
    baseline = load("environment_baseline")
    assert baseline["classification"] == "TOOL_ENVIRONMENT_ONLY"
    assert baseline["BASELINE_TEST_FAILURE_NOT_ENVIRONMENT_ONLY"] is False
    conditions = baseline["classification_conditions"]
    assert conditions["exact_tests_pass_in_the_canonical_environment"] is True
    assert conditions["test_assertions_changed"] is False
    assert conditions["source_change_needed"] is False


def test_baseline_records_both_the_failing_and_the_passing_invocation():
    runs = {run["invocation"]: run for run in load("environment_baseline")["runs"]}
    assert runs["ordinary host, no PYTHONPATH"]["failed"] == 2
    assert runs["canonical environment, PYTHONPATH=/Users/udy/rvt"]["failed"] == 0
    assert runs["canonical environment, PYTHONPATH=/Users/udy/rvt"]["passed"] == 4146
    assert runs["ordinary host, no PYTHONPATH"][
        "reproduced_on_the_exact_owner_freeze_source_state"] is True


def test_the_two_suite_counts_are_reconciled_not_left_dangling():
    """4265 is the image's suite; 4316 adds this phase's own record tests."""
    baseline = load("environment_baseline")
    counts = {run["passed"] for run in baseline["runs"]}
    assert {4144, 4146, 4265, 4316} == counts
    assert "postdate the image" in baseline["count_reconciliation"]
    assert load("final_readiness")["suite_results"][
        "phase_closure_canonical_host"] == {
            "passed": 4316, "failed": 0,
            "note": "adds this phase's 51 qualification-record tests, which "
                    "postdate the image and contain no runtime code"}


def test_the_two_failures_are_not_buried_under_later_counts():
    assert load("environment_baseline")["buried_under_later_v3_counts"] is False


# ------------------------------------------------------------------ R9 / C7
def test_no_early_abort_is_recorded_as_forbidden():
    record = load("no_early_abort")
    assert record["rule"] == "EARLY_ABORT_ON_SCIENTIFIC_INVALIDITY = FORBIDDEN"
    assert record["owner_ratified_clause"] == "C7"
    assert record["planned_is_outcome_independent"] is True
    for index in (0, 1, 2):
        assert record[f"invalid_at_replica_{index}_still_executes_R"] is True
    assert record["candidate_ordering_alters_total_execution"] is False
    assert record["canary_shortfalls"] == 0
    assert record["invalidity_contract_hash_unchanged_by_ratification"] == INVALIDITY


# ------------------------------------------------------------------ R11 / R33
def test_supervision_exists_only_for_fully_valid_replica_sets():
    record = load("supervision_schema")
    rule = record["R11_supervision_rule"]
    assert rule["any_generation_invalid"] == "supervision = NONE"
    assert rule["partial_k"] == "FORBIDDEN"
    assert rule["R_shrink"] == "FORBIDDEN"
    assert record["invalid_replica_target_v4_label"] is None
    assert record["manufactured_bernoulli_outcomes"] == 0


def test_the_canary_observed_a_real_mixed_outcome():
    record = load("supervision_schema")
    assert record["canary_mixed_0_lt_k_lt_R"] >= 1
    assert record["R33_mixed_outcome_remained_valid_supervision"] is True
    assert record["R33_mixed_outcome_marked_generation_invalid"] == 0


# ------------------------------------------------------------------ R32
def test_rows_are_two_N_never_two_N_R():
    accounting = load("pair_atomicity")["R32_row_accounting"]
    assert accounting["labelable_event"] == "2 * N"
    assert accounting["never"] == "2 * N * R"
    assert accounting["invalid_pair"] == 0
    observed = {int(key) for key in accounting["canary_rows_per_event_observed"]}
    assert observed == {2 * n for n in accounting["canary_team_sizes"]}


def test_no_semantically_duplicate_pair_status_was_invented():
    record = load("pair_atomicity")
    assert record["status_when_invalid"] == (
        "SCIENTIFICALLY_RECONCILED_GENERATION_INVALID")
    assert record["semantically_duplicate_status_invented"] == 0
    assert record["status_when_infrastructure"] == (
        "PENDING_INFRASTRUCTURE_RESOLUTION")


# ------------------------------------------------------------------ R38 / S8
def test_s8_numerator_and_denominator_are_recorded_exactly():
    record = load("s8_accounting")
    assert record["numerator"].startswith("executed required Target-V4 replica")
    assert record["denominator"] == "executed required Target-V4 replica rollouts"
    assert record["unit"] == "replica rollout"
    assert record["scientific_invalid_rollouts_remain_in_the_denominator"] is True
    assert record[
        "infrastructure_failures_excluded_until_resolved_and_executed"] is True
    assert record["censored_events_hidden_from_s8"] == 0
    assert record["hidden_denominator_changes"] == 0
    assert record["tuned"] is False
    assert record["inequalities_are_strict"] is True


def test_s8_thresholds_are_the_frozen_ones():
    record = load("s8_accounting")
    assert record["maximum_overall_rate"] == 0.02
    assert record["maximum_family_rate"] == 0.05
    assert record["frozen_threshold_text"] == (
        "invalid rollout rate is below 0.02 overall and below 0.05 in every "
        "family")


# ------------------------------------------------------------------ R15
def test_the_invalidity_contract_binds_exactly_four_objects():
    record = load("invalidity_binding")
    assert record["invalidity_contract_sha256"] == INVALIDITY
    assert {item["object"] for item in record["binds"]} == {
        "candidate supervision provenance", "pair transaction provenance",
        "dataset manifest", "dataset seal"}
    assert {item["object"] for item in record["does_not_bind"]} == {
        "official rollout configuration", "candidate task identity",
        "Row Identity V3"}
    assert record["binding_widened_or_narrowed_by_intuition"] is False
    assert record["row_binding_v3_modified"] is False


# ------------------------------------------------------------------ R24
def test_the_mandatory_brier_fixture_is_recorded_at_exactly_one_quarter():
    fixture = load("brier_qualification")["R24_mandatory_fixture"]
    assert fixture["required"] == 0.25
    assert float(fixture["observed"]) == 0.25
    assert fixture["incorrect_shortcut_value"] == pytest.approx(
        0.0277777777777, abs=1e-9)
    assert load("brier_qualification")["shortcut_implemented_anywhere"] is False


def test_loss_reduces_exactly_to_bce_at_R1():
    record = load("loss_qualification")
    assert record["R22_R1_bce_equivalence"]["equality"].startswith("exact")
    assert record["division_by_R"] == "MANDATORY"
    assert record["R21_weight_invariance"]["N_weighting"] == 0
    assert record["R21_weight_invariance"]["R_weighting"] == 0


# ------------------------------------------------------------------ R34-R36
def test_every_determinism_axis_agrees():
    record = load("determinism")
    assert record["R34_replica_order_invariance"]["reference"] is True
    assert record["R34_replica_order_invariance"]["target"] is True
    assert record["R35_candidate_order_invariance"]["digest_identical"] is True
    assert record["R36_worker_invariance"]["all_identical"] is True


def test_reference_and_target_digests_are_identical():
    replay = load("target_semantic_replay")
    assert replay["R49_semantic_equality"]["identical"] is True
    assert replay["R49_semantic_equality"]["reference_digest"] == CANARY_DIGEST
    assert replay["R49_semantic_equality"]["target_digest"] == CANARY_DIGEST
    assert replay["R49_semantic_equality"]["new_tolerance_introduced"] is False
    assert replay["R52_numerical_fixtures"]["bit_identical_mismatches"] == 0


# ------------------------------------------------------------------ R37 / R51
def test_resume_is_clean_on_both_sides():
    record = load("failure_resume")
    for side in ("reference", "target"):
        assert record[side]["duplicates"] == 0
        assert record[side]["identity_mismatch"] == 0
        assert record[side]["seed_substitution"] == 0
        assert record[side]["partial_supervised_rows"] == 0
        assert record[side]["semantic_digest_matches_uninterrupted_run"] is True


def test_infrastructure_failure_never_becomes_science():
    separation = load("failure_resume")["infrastructure_versus_science"]
    assert separation["R_reduced"] is False
    assert separation["k_R_constructed"] is False
    assert separation["pair_marked_scientifically_non_labelable"] is False
    assert separation["status"] == "PENDING_INFRASTRUCTURE_RESOLUTION"


# ------------------------------------------------------------------ R41-R48
def test_the_image_reports_the_exact_final_commit():
    record = load("image_provenance")
    assert record["source_commit"] == FINAL_COMMIT
    assert record["declared_revision_label"] == FINAL_COMMIT
    assert record["commit_read_from_inside_the_running_container"] == FINAL_COMMIT
    assert record["architecture"] == "amd64/linux"
    assert record["package_upgrades"] == 0
    assert record["in_image_full_suite"] == {"passed": 4265, "failed": 0,
                                             "runs": 2}


def test_the_transport_limitation_is_declared_not_hidden():
    transport = load("image_provenance")["R46_transport"]
    assert transport["rebuilt_independently_on_target"] is False
    assert transport["builds_performed"] == 1
    assert transport["declared_limitation"] is True
    assert "no linux/amd64 Docker daemon" in transport["note"]


def test_the_target_segfault_is_disclosed():
    anomaly = load("windows_target")["observed_anomaly"]
    assert anomaly["reproduced"] is False
    assert anomaly["subsequent_clean_runs"] == 7
    assert anomaly["related_to_v3"] is False
    assert anomaly["disclosed_rather_than_omitted"] is True


def test_target_and_host_suite_counts_agree():
    target = load("windows_target")["R48_full_suite_in_image_on_target"]
    assert target["passed"] == 4265 and target["failed"] == 0
    assert target["second_run"] == {"passed": 4265, "failed": 0,
                                    "seconds": 375.94}
    assert target["matches_canonical_host_count"] is True


# ------------------------------------------------------------------ R53 / R54
def test_no_official_v3_data_was_generated():
    protection = load("official_data_protection")
    assert protection["R53"] == {
        "official_v3_train_source_episodes_executed": 0,
        "official_v3_validation_source_episodes_executed": 0,
        "official_v3_selected_source_states_generated": 0,
        "official_v3_target_v4_evaluations": 0,
        "official_v3_rows": 0,
        "qualification_identities_overlapping_official_manifests": 0,
    }
    assert protection["R54_sealed_domains"] == {
        "study_a_n24_access": 0, "study_b_access": 0, "final_test_access": 0,
        "training": 0, "hp_trials": 0}


def test_v1_v2_and_gate_7_are_untouched():
    record = load("v1_v2_regression")
    assert record["v1_modules_modified"] == 0
    assert record["v2_modules_modified"] == 0
    gate = record["historical_gate_7"]
    assert gate["status"] == "FAILED_FOR_V2"
    assert gate["modified"] is False
    assert gate["marked_passed"] is False
    assert gate["still_exceeds"] is True
    assert gate["exact_decimal"] == "0.11132075471698114"


def test_the_guards_were_reconciled_without_weakening_them():
    for entry in load("v1_v2_regression")["guards_reconciled_rather_than_suppressed"]:
        assert entry["assertion_weakened"] is False


# ------------------------------------------------------------------ R55
def test_every_readiness_criterion_is_met():
    readiness = load("final_readiness")
    assert readiness["criteria_total"] == 27
    assert readiness["criteria_met"] == 27
    assert readiness["criteria_unmet"] == []
    assert all(item["met"] for item in readiness["R55_criteria"])


def test_verdict_is_c_with_train_only_authorization():
    readiness = load("final_readiness")
    assert readiness["verdict"] == "C"
    assert readiness["recommendation"] == (
        "AUTHORIZE_OFFICIAL_RECOVERABILITY_V3_TRAIN_GENERATION")
    assert readiness["recommendation_scope"] == "TRAIN ONLY"
    assert readiness["validation_generation_authorized"] is False
    assert readiness["training_authorized"] is False
    assert readiness["hp_search_authorized"] is False


def test_the_declared_limitations_survive_into_the_readiness_record():
    limitations = load("final_readiness")["declared_limitations"]
    assert len(limitations) == 3
    assert any("no linux/amd64 Docker daemon" in item for item in limitations)
    assert any("segfaulted" in item for item in limitations)
    assert any("zero scientific" in item for item in limitations)
