"""Phase 9D-V3F-I -- the required-replica scientific invalidity owner freeze.

Owner decision A: a candidate whose required replica set contains any
scientifically GENERATION_INVALID rollout is NOT scientifically labelable, and
its whole (COMPACT, LINE) pair publishes zero supervised rows. These tests pin
the frozen contract, its compatibility with every prior frozen contract, and
the fact that nothing frozen was mutated to accommodate it.
"""
from __future__ import annotations

import json
import pathlib

import pytest

from rvt_swarm.phase8.common import verify_canonical_hash

RESULTS = pathlib.Path("results/rvt_fd24")

OWNER = "phase9d_v3f_i_owner_decision_v1.json"
CONTRACT = "phase9d_v3f_i_invalidity_contract_v1.json"
COMPAT = "phase9d_v3f_i_contract_compatibility_v1.json"
PROV = "phase9d_v3f_i_provenance_binding_v1.json"
TESTS = "phase9d_v3f_i_required_tests_v1.json"
HANDOFF = "phase9d_v3f_i_implementation_handoff_v1.json"
READY = "phase9d_v3f_i_final_readiness_v1.json"
ARTIFACTS = (OWNER, CONTRACT, COMPAT, PROV, TESTS, HANDOFF, READY)

INVALIDITY_CONTRACT_SHA256 = (
    "66bdd9ffce3f0b6417f20c4b41602b5ea4be266a728bcdb1dd306b0e27ef5c75")

FROZEN = {
    "recoverability_probabilistic_target_v3_sha256":
        "a127bf9fbe907c81f2cd8037e94164f738ee756d7480c7db6955d7405bc355b6",
    "recoverability_replica_protocol_v3_sha256":
        "6c2143c4782f0d851205cb118a2ff1c3e33c8a6a3e3cdc2ce5a820106551fa9a",
    "recoverability_row_binding_v3_spec_sha256":
        "bdab65bdabbf503dc4d76d7d66d14c6504feb657b32d153a89643fab55058a8c",
    "recoverability_training_loss_v3_sha256":
        "fc9c093327eaaa5ae95c038cf36a2a16ff2fee6d5fdc125dd1106bc3a99dfc11",
    "recoverability_brier_metric_v3_sha256":
        "0bf6dee325825953d856fb4f6b5df190879424b0d5e8d29cbe55ac930f682f04",
    "source_acquisition_protocol_sha256":
        "19fa68a37d80f16ee1463b872f26402963daeb5a56f375423634a90dc1f3546d",
    "target_v4_contract_sha256":
        "54a0e0baff79fbdc320800b772f47a40ac06ac4f0e70d4fab1bf676c54b918ee",
}


def load(name):
    return json.loads((RESULTS / name).read_text())


@pytest.fixture(scope="module")
def owner():
    return load(OWNER)


@pytest.fixture(scope="module")
def contract():
    return load(CONTRACT)["contract"]


@pytest.fixture(scope="module")
def compat():
    return load(COMPAT)


@pytest.fixture(scope="module")
def prov():
    return load(PROV)


@pytest.fixture(scope="module")
def required_tests():
    return load(TESTS)


@pytest.fixture(scope="module")
def handoff():
    return load(HANDOFF)


@pytest.fixture(scope="module")
def readiness():
    return load(READY)


# ------------------------------------------------------------- artifacts
@pytest.mark.parametrize("name", ARTIFACTS)
def test_required_artifact_exists(name):
    assert (RESULTS / name).exists()


@pytest.mark.parametrize("name", ARTIFACTS)
def test_artifact_self_verifies(name):
    document = load(name)
    field = next(k for k in document
                 if k.startswith("phase9d_v3f_i_") and k.endswith("sha256"))
    assert verify_canonical_hash(document, field)


def test_all_seven_required_artifacts_and_no_more():
    found = sorted(p.name for p in RESULTS.glob("phase9d_v3f_i_*.json"))
    assert found == sorted(ARTIFACTS)


def test_invalidity_contract_inner_hash_is_stable():
    """The inner contract root, verified the way every V3F contract nests it.

    The inner hash is sealed over the contract body alone; the outer artifact
    hash is then sealed over body plus inner. Verifying the inner root therefore
    means recomputing it with the outer field removed -- exactly the two-level
    pattern used by phase9d_v3f_replica_protocol_v1.json and its siblings.
    """
    document = load(CONTRACT)
    inner = "recoverability_v3_required_replica_invalidity_contract_v1_sha256"
    outer = "phase9d_v3f_i_invalidity_contract_sha256"
    assert document[inner] == INVALIDITY_CONTRACT_SHA256
    body = {k: v for k, v in document.items() if k != outer}
    assert verify_canonical_hash(body, inner)
    assert verify_canonical_hash(document, outer)


def test_the_two_level_nesting_matches_the_frozen_v3f_precedent():
    """The same recomputation must succeed on an already-frozen V3F contract."""
    document = json.loads(
        (RESULTS / "phase9d_v3f_replica_protocol_v1.json").read_text())
    body = {k: v for k, v in document.items()
            if k != "phase9d_v3f_replica_protocol_sha256"}
    assert verify_canonical_hash(body, "recoverability_replica_protocol_v3_sha256")
    assert verify_canonical_hash(document, "phase9d_v3f_replica_protocol_sha256")


# ------------------------------------------------------------- A0 handoff
def test_handoff_records_the_full_stop_commit_sha(owner):
    handoff = owner["handoff"]
    assert handoff["stop_commit_full_sha"] == (
        "abab5f477340b7f10c042a66cdfc0adef6024258")
    assert len(handoff["stop_commit_full_sha"]) == 40
    assert handoff["stop_commit_full_sha"].startswith(
        handoff["stop_commit_abbreviation_in_prompt"])


def test_the_stop_token_being_cleared_is_the_exact_one(owner, handoff):
    token = "V3_REPLICA_INVALIDITY_SEMANTICS_OWNER_DECISION_REQUIRED"
    assert owner["handoff"]["stop_token_resolved"] == token
    assert handoff["stop_token_cleared"] == token


# ------------------------------------------------------------- owner rule
def test_owner_selected_a_and_rejected_b_and_c(owner):
    status = {o["id"]: o["owner_status"] for o in owner["options_presented_at_the_stop"]}
    assert status == {"A": "SELECTED", "B": "REJECTED", "C": "REJECTED"}


def test_branch_1_produces_supervision_at_the_frozen_R(owner):
    branch = owner["decision_rule"]["branch_1"]
    assert branch["supervision_exists"] is True
    assert branch["R"] == "R_required"
    assert branch["k"] == "SUM_r Y_r"


def test_branch_2_produces_no_supervision_at_all(owner):
    branch = owner["decision_rule"]["branch_2"]
    assert branch["supervision_exists"] is False
    assert branch["k_R"] == "UNDEFINED"
    assert branch["candidate_scientifically_labelable"] is False


def test_non_imputation_forbids_every_listed_shortcut(owner):
    forbidden = owner["non_imputation_rule"]["forbidden"]
    assert "R_effective < R_required" in forbidden
    assert "k computed only over valid replicas" in forbidden
    assert "invalid replica counted as failure" in forbidden
    assert "invalid replica counted as success" in forbidden


def test_invalid_is_neither_zero_nor_one(owner):
    not_list = owner["non_imputation_rule"]["a_generation_invalid_replica_is_not"]
    assert "Y = 0" in not_list and "Y = 1" in not_list


def test_pair_publishes_two_N_rows_or_zero(owner):
    pair = owner["pair_atomicity_rule"]
    assert pair["rows_when_both_labelable"] == "exactly 2 * N_event V3 robot-local rows"
    assert pair["rows_when_either_non_labelable"] == 0
    assert pair["do_not_publish_the_other_candidate_alone"] is True
    assert pair["do_not_publish_a_partial_robot_set"] is True


def test_mixed_valid_patterns_are_untouched(owner):
    unchanged = owner["unchanged_by_this_decision"]
    assert unchanged["mixed_valid_patterns_remain_supervision"] == [
        "001", "010", "100", "011", "101", "110"]


# ------------------------------------------------------------- A2 contract
def test_contract_has_all_fifteen_clauses(contract):
    assert len([k for k in contract if k.startswith("C")]) == 15


def test_contract_is_additive_and_supersedes_nothing(contract):
    document = load(CONTRACT)["contract"]
    assert document["additive"] is True
    assert document["supersedes_in_place"] is False


def test_required_replica_definition_binds_R_to_the_protocol(contract):
    clause = contract["C1_required_replica_definition"]
    assert clause["R_authority"] == "recoverability_replica_protocol_v3_sha256"
    assert clause["R_values"]["F8"] == 3 and clause["R_values"]["F9"] == 3
    assert all(v == 1 for f, v in clause["R_values"].items()
               if f not in ("F8", "F9"))
    assert clause["R_is_never_read_from_the_observed_record_count"] is True


def test_validity_predicate_is_target_v4_and_is_not_redefined(contract):
    clause = contract["C2_scientific_validity_predicate_authority"]
    assert clause["target_v4_contract_sha256"] == FROZEN["target_v4_contract_sha256"]
    assert clause["valid_dispositions"] == ["RECOVERABLE_POSITIVE",
                                            "VALID_TASK_NEGATIVE"]
    assert clause["target_v4_label_for_generation_invalid"] is None
    assert clause["predicate_redefined_by_this_contract"] is False


def test_generation_invalid_causes_match_the_implementation(contract):
    from rvt_swarm.phase8e.target import _GENERATION_INVALID_CAUSES
    clause = contract["C2_scientific_validity_predicate_authority"]
    assert set(clause["generation_invalid_causes"]) == set(_GENERATION_INVALID_CAUSES)


def test_shrink_r_is_forbidden(contract):
    assert contract["C5_no_shrink_R"]["SHRINK_R_ON_INVALID"] == "FORBIDDEN"


def test_replacement_replica_is_forbidden(contract):
    clause = contract["C6_no_replacement_replica"]
    assert clause["sample_replica_r_plus_R"] == "FORBIDDEN"
    assert clause["reroll_until_valid"] == "FORBIDDEN"


def test_early_abort_is_forbidden_so_accounting_stays_exact(contract):
    clause = contract["C7_no_early_abort"]
    assert clause["early_abort"] == "FORBIDDEN"
    assert any("D5" in reason for reason in clause["derived_from"])
    assert any("S8" in reason for reason in clause["derived_from"])


def test_audit_disposition_is_repository_consistent(contract):
    clause = contract["C9_audit_disposition"]
    assert clause["repository_consistent_status"] == (
        "SCIENTIFICALLY_RECONCILED_GENERATION_INVALID")
    assert clause["is_a_recoverability_training_label"] is False
    assert clause["training_rows_committable"] is False


def test_the_repository_status_string_actually_exists_in_code():
    source = pathlib.Path(
        "rvt_swarm/phase9g0r/contracts.py").read_text()
    assert "SCIENTIFICALLY_RECONCILED_GENERATION_INVALID" in source
    assert "PENDING_INFRASTRUCTURE_RESOLUTION" in source


def test_audit_evidence_is_retained_not_erased(contract):
    clause = contract["C10_audit_evidence_retention"]
    assert clause["erases_evidence"] is False
    assert clause["blocks_supervised_row_publication"] is True
    assert clause["placeholder_supervised_rows"] == "FORBIDDEN"
    assert clause["identity_mutation_after_invalidity"] == "FORBIDDEN"
    assert len(clause["must_retain"]) == 9


def test_infrastructure_failure_stays_separate(contract):
    clause = contract["C11_infrastructure_scientific_separation"]
    assert clause["conversion_of_infrastructure_failure_into_Y0"] == "FORBIDDEN"
    assert clause[
        "conversion_of_infrastructure_failure_into_GENERATION_INVALID"] == "FORBIDDEN"
    assert clause["the_two_dispositions_must_never_be_merged"] is True
    for cause in ("timeout", "worker crash", "process death",
                  "serialization failure", "network failure",
                  "transport failure", "unexecuted scheduled work"):
        assert cause in clause["out_of_scope"]


def test_the_frozen_denominator_rule_is_quoted_correctly():
    from rvt_swarm.phase9c_rb.generation_contract import (
        COUNTS_IN_SCIENTIFIC_DENOMINATOR, EMITS_TARGET_ROW,
        EXECUTION_INVALID, INFRASTRUCTURE_FAILURE)
    assert COUNTS_IN_SCIENTIFIC_DENOMINATOR[EXECUTION_INVALID] is True
    assert COUNTS_IN_SCIENTIFIC_DENOMINATOR[INFRASTRUCTURE_FAILURE] is False
    assert EMITS_TARGET_ROW[EXECUTION_INVALID] is False


def test_s8_is_retained_at_the_frozen_threshold(contract):
    clause = contract["C12_s8_relationship"]
    assert clause["retained"] is True
    assert clause["weakened"] is False
    assert clause["threshold_changed"] is False
    assert clause["frozen_threshold_text"] == (
        "invalid rollout rate is below 0.02 overall and below 0.05 in every family")
    assert clause["threshold_authority_sha256"] == (
        "f9171f37d3402925d9f460e1b231cf0d433dce3fa3fa10bb9562208a6276fe5d")


def test_s8_threshold_text_matches_the_frozen_document(contract):
    text = pathlib.Path("docs/RVT_RECOVERABILITY_LABEL_AUDIT_GATES.md").read_text()
    assert ("invalid rollout rate is below 0.02 overall and below 0.05 in every "
            "family") in text


def test_s8_unit_is_the_replica_rollout_with_an_honest_denominator(contract):
    clause = contract["C12_s8_relationship"]
    assert clause["unit"].startswith("replica rollout")
    assert clause["censored_rollouts_remain_in_the_denominator"] is True
    assert clause["hidden_denominator_changes"] == "FORBIDDEN"


def test_no_outcome_dependent_refill(contract):
    clause = contract["C14_no_outcome_dependent_refill"]
    assert clause["official_source_episode_manifests_remain_fixed"] is True
    assert clause["train_source_episodes"] == 1200
    assert clause["validation_source_episodes"] == 300
    assert "budget refill" in clause["a_dropped_source_event_must_not_trigger"]


@pytest.mark.parametrize("field,expected", sorted(FROZEN.items()))
def test_contract_pins_every_unchanged_frozen_hash(contract, field, expected):
    assert contract["C15_unchanged_contracts"]["hashes"][field] == expected


# ------------------------------------------------------------- A1 compat
def test_no_owner_decision_contract_conflict(compat):
    assert compat["OWNER_DECISION_CONTRACT_CONFLICT"] is False
    assert compat["blocking_conflicts"] == 0


def test_every_required_compatibility_axis_is_audited(compat):
    axes = {a["axis"] for a in compat["axes"]}
    assert axes == {
        "Target V4", "V3 probabilistic target", "fixed replica protocol",
        "row identity", "pair atomicity", "event-equal loss", "Brier metric",
        "S8 invalid-rate gate", "historical V1/V2 validity semantics"}


def test_no_axis_mandates_a_different_behaviour(compat):
    for axis in compat["axes"]:
        assert axis["compatible"] is True
        assert axis["mandates_a_different_behaviour"] is False


def test_every_tension_was_examined_and_none_survived(compat):
    assert len(compat["tensions_examined_and_resolved"]) == 6
    for tension in compat["tensions_examined_and_resolved"]:
        assert tension["survives"] is False
        assert tension["resolution"]


def test_the_adversarial_audit_reported_no_conflicts(compat):
    audit = compat["independent_adversarial_audit"]
    assert audit["scopes_completed"] == 8
    assert audit["scopes_reporting_conflict_found"] == 0
    assert audit["hard_conflicts_reported"] == 0
    assert audit["tensions_surviving_verification"] == 0


def test_the_incomplete_verification_stage_is_disclosed(compat):
    audit = compat["independent_adversarial_audit"]
    assert "usage limit" in audit["verification_stage_status"]
    assert audit["tensions_verified_by_hand"] == 6


def test_reading_c_is_named_as_the_one_that_would_have_conflicted(compat):
    reading = compat["the_only_reading_that_would_have_conflicted"]
    assert reading["reading"].startswith("C")
    assert reading["owner_rejected_it"] is True


# ------------------------------------------------------------- A4 provenance
def test_row_binding_v3_does_not_change(prov):
    determination = prov["row_binding_v3_determination"]
    assert determination["answer"] == "NO"
    assert determination["row_binding_v3_modified"] is False
    assert determination["stop_required"] is False
    assert determination["row_identity_field_count_unchanged"] == 16


def test_the_case_for_changing_row_binding_was_actually_argued(prov):
    determination = prov["row_binding_v3_determination"]
    assert determination["strongest_case_FOR_changing_it"]["argument"]
    assert determination["strongest_case_FOR_changing_it"]["why_it_does_not_carry"]
    assert len(determination["case_AGAINST_changing_it"]) >= 5


def test_row_binding_v3_file_is_byte_identical_to_its_frozen_hash():
    document = json.loads(
        (RESULTS / "phase9d_v3f_row_binding_v1.json").read_text())
    assert document["recoverability_row_binding_v3_spec_sha256"] == (
        FROZEN["recoverability_row_binding_v3_spec_sha256"])
    assert verify_canonical_hash(document, "phase9d_v3f_row_binding_sha256")


def test_exactly_the_outcome_dependent_objects_bind_the_new_hash(prov):
    binds = {o["object"] for o in prov["objects"] if o["binds_invalidity_contract"]}
    does_not = {o["object"] for o in prov["objects"]
                if not o["binds_invalidity_contract"]}
    assert binds == {"candidate supervision provenance",
                     "pair transaction provenance", "V3 dataset manifest",
                     "V3 dataset seal"}
    assert does_not == {"official rollout configuration",
                        "candidate task provenance",
                        "V3 row identity (RECOVERABILITY_ROW_BINDING_V3)"}


def test_binding_follows_a_stated_rule_not_a_preference(prov):
    assert "if and only if" in prov["binding_rule"]["statement"]
    for obj in prov["objects"]:
        assert obj["binds_invalidity_contract"] == obj[
            "determined_by_the_invalidity_rule"]


def test_placeholder_rows_are_prohibited(prov):
    assert prov["placeholder_row_prohibition"]["rule"].startswith(
        "a non-labelable pair emits zero supervised")


# ------------------------------------------------------------- A5 tests
def test_all_eleven_numbered_cases_are_specified(required_tests):
    ids = [t["id"] for t in required_tests["tests"]]
    assert ids == ["T%d" % n for n in range(1, 12)]
    assert required_tests["count"] == 11


def test_the_three_valid_patterns_publish_rows(required_tests):
    by_id = {t["id"]: t for t in required_tests["tests"]}
    assert by_id["T1"]["expected_supervision"] == "(k, R) = (3, 3)"
    assert by_id["T2"]["expected_supervision"] == "(k, R) = (2, 3)"
    assert by_id["T3"]["expected_supervision"] == "(k, R) = (0, 3)"
    for case in ("T1", "T2", "T3"):
        assert "published" in by_id[case]["expected_rows"]


def test_the_invalid_case_produces_no_k_or_R(required_tests):
    case = next(t for t in required_tests["tests"] if t["id"] == "T4")
    assert case["expected_candidate_labelable"] is False
    assert case["expected_supervision"] == "NONE; (k, R) is UNDEFINED"
    assert "(k, R) = (1, 3)" in case["must_not_produce"]
    assert "(k, R) = (1, 2)" in case["must_not_produce"]


def test_all_three_pair_cases_publish_zero_rows(required_tests):
    by_id = {t["id"]: t for t in required_tests["tests"]}
    for case in ("T5", "T6", "T7"):
        assert by_id[case]["expected_pair_rows"] == 0
        assert by_id[case]["expected_pair_status"] == (
            "SCIENTIFICALLY_RECONCILED_GENERATION_INVALID")


def test_infrastructure_timeout_is_not_scientific_invalidity(required_tests):
    case = next(t for t in required_tests["tests"] if t["id"] == "T8")
    assert case["expected_scientific_disposition"] == "NOT GENERATION_INVALID"
    assert case["expected_pair_status"] == "PENDING_INFRASTRUCTURE_RESOLUTION"
    assert case["expected_scientifically_reconciled"] is False


def test_no_replacement_replica_case_also_pins_no_early_abort(required_tests):
    case = next(t for t in required_tests["tests"] if t["id"] == "T9")
    assert case["expected_replica_executions"].startswith("exactly R_required")
    assert "no early abort" in case["also_assert"]


def test_s8_case_specifies_numerator_and_denominator_exactly(required_tests):
    case = next(t for t in required_tests["tests"] if t["id"] == "T11")
    assert case["numerator"].startswith("executed required Target-V4 replica")
    assert case["denominator"] == "executed required Target-V4 replica rollouts"
    assert case["unit"] == "replica rollout"
    assert any("INCLUDES rollouts belonging to censored" in a
               for a in case["assertions"])
    assert any("EXCLUDES infrastructure failures" in a for a in case["assertions"])


def test_no_test_was_implemented_in_this_phase(required_tests):
    assert required_tests["implemented_in_this_phase"] == 0


# ------------------------------------------------------------- A3 handoff
def test_handoff_makes_the_new_hash_mandatory(handoff):
    assert handoff["new_mandatory_frozen_input"]["sha256"] == INVALIDITY_CONTRACT_SHA256
    assert handoff["new_mandatory_frozen_input"]["must_be_bound_by_phase_9g_v3i_q"] is True
    assert handoff["frozen_inputs_for_implementation"][
        "recoverability_v3_required_replica_invalidity_contract_v1_sha256"
    ] == INVALIDITY_CONTRACT_SHA256


def test_handoff_requires_failing_closed(handoff):
    fail_closed = handoff["fail_closed_requirement"]
    assert INVALIDITY_CONTRACT_SHA256 in fail_closed["rule"]
    assert fail_closed["must_not_silently_default_to_any_rule"] is True
    assert fail_closed["must_not_infer_the_rule_from_observed_data"] is True


def test_handoff_still_refuses_the_superseded_layout_registry(handoff):
    assert handoff["superseded_registry_that_must_still_be_refused"] == (
        "d84d0fb9699dad7d6fe4783d2bd55e1b644ed027948291aeb75148e88ea54dae")
    assert handoff["frozen_inputs_for_implementation"][
        "v3_layout_split_registry_v2_sha256"] == (
        "5494914e687a306b0288ce416e80d7c8a25f0f79377580eba58edc538d53680a")


def test_handoff_amends_only_the_affected_capabilities(handoff):
    amended = {c["id"] for c in handoff["amended_capabilities"]}
    assert amended == {"I3", "I4", "I6", "I7", "I8", "I9"}
    new = {c["id"] for c in handoff["new_capabilities"]}
    assert new == {"I10", "I11", "I12"}


def test_handoff_does_not_authorize_generation(handoff):
    assert handoff["implemented_in_this_phase"] == 0
    assert "may NOT generate official V3 data" in handoff["authorized_next_phase"]


# ------------------------------------------------------------- A6 / A7
def test_v2_history_is_untouched(readiness):
    v2 = readiness["A6_v2_history"]
    assert v2["v2_rows_modified"] == 0
    assert v2["v2_contracts_modified"] == 0
    assert v2["v2_train_seal_modified"] is False
    assert v2["v2_validation_seal_modified"] is False


def test_gate_7_still_fails_for_v2(readiness):
    v2 = readiness["A6_v2_history"]
    assert v2["gate_7_status"] == "FAILED_FOR_V2"
    assert v2["gate_7_modified"] is False
    assert v2["gate_7_marked_passed"] is False
    assert v2["gate_7_threshold_changed"] is False
    assert v2["gate_7_still_exceeds"] is True
    assert v2["gate_7_value"] > v2["gate_7_threshold"]
    assert 59 / 530 > 0.10


def test_the_live_gate_7_record_is_unchanged():
    record = json.loads(
        (RESULTS / "phase9d_v2c_r_gate7_replica_instability_v1.json").read_text())
    assert record["result"] == "FAIL"


def test_no_scientific_execution_happened(readiness):
    assert readiness["A7_no_scientific_execution"] == {
        "v3_source_episodes_executed": 0,
        "v3_candidate_rollouts_executed": 0,
        "v3_target_v4_evaluations": 0,
        "v3_rows": 0,
        "models_trained": 0,
        "hp_trials": 0,
        "images_built": 0,
        "v3_runtime_code_written": 0,
        "replica_counts_changed": 0,
        "probabilistic_target_semantics_changed": 0,
        "source_acquisition_modified": 0,
        "target_v4_modified": 0,
        "v2_modified": 0,
        "n24_accesses": 0,
        "study_b_accesses": 0,
        "final_test_accesses": 0,
    }


@pytest.mark.parametrize("field,expected", sorted(FROZEN.items()))
def test_readiness_pins_every_unchanged_frozen_hash(readiness, field, expected):
    assert readiness["frozen_hashes_unchanged"][field] == expected


def test_every_frozen_v3_contract_still_verifies_on_disk():
    pairs = (("phase9d_v3f_probabilistic_target_contract_v1.json",
              "recoverability_probabilistic_target_v3_sha256"),
             ("phase9d_v3f_replica_protocol_v1.json",
              "recoverability_replica_protocol_v3_sha256"),
             ("phase9d_v3f_row_binding_v1.json",
              "recoverability_row_binding_v3_spec_sha256"),
             ("phase9d_v3f_training_loss_contract_v1.json",
              "recoverability_training_loss_v3_sha256"),
             ("phase9d_v3f_brier_metric_contract_v1.json",
              "recoverability_brier_metric_v3_sha256"))
    for name, field in pairs:
        document = json.loads((RESULTS / name).read_text())
        assert document[field] == FROZEN[field]


def test_verdict_is_a_with_the_resume_recommendation(readiness):
    assert readiness["verdict"] == "A"
    assert readiness["recommendation"] == (
        "RESUME_RECOVERABILITY_V3_IMPLEMENTATION_AND_QUALIFICATION")
    assert readiness["data_generation_authorized"] is False
    assert readiness["training_authorized"] is False
