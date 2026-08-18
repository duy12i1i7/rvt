"""Phase 9G-V3I-Q -- the I10 owner-decision stop.

Implementation did not start: gate I10 could not be closed from repository
authority, and I10 directs a stop rather than a guess. These tests pin the
stop, the recovered full hashes and the untouched sealed state.
"""
from __future__ import annotations

import json
import pathlib

import pytest

from rvt_swarm.phase8.common import verify_canonical_hash

RESULTS = pathlib.Path("results/rvt_fd24")

BINDING = "phase9g_v3i_q_implementation_binding_v1.json"
DECISION = "phase9g_v3i_q_replica_invalidity_owner_decision_v1.json"
READINESS = "phase9g_v3i_q_final_readiness_v1.json"
ARTIFACTS = (BINDING, DECISION, READINESS)

STOP = "V3_REPLICA_INVALIDITY_SEMANTICS_OWNER_DECISION_REQUIRED"


def load(name):
    return json.loads((RESULTS / name).read_text())


@pytest.fixture(scope="module")
def binding():
    return load(BINDING)


@pytest.fixture(scope="module")
def decision():
    return load(DECISION)


@pytest.fixture(scope="module")
def readiness():
    return load(READINESS)


# --------------------------------------------------------------- artifacts
@pytest.mark.parametrize("name", ARTIFACTS)
def test_artifact_exists(name):
    assert (RESULTS / name).exists()


@pytest.mark.parametrize("name", ARTIFACTS)
def test_artifact_self_verifies(name):
    document = load(name)
    field = next(key for key in document
                 if key.startswith("phase9g_v3i_q_") and key.endswith("sha256"))
    assert verify_canonical_hash(document, field)


# --------------------------------------------------------------- I10 stop
def test_stop_token_is_the_exact_required_token(decision):
    assert decision["STOP_TOKEN"] == STOP


def test_stop_is_raised_at_gate_i10(decision):
    assert decision["gate"] == "I10"


def test_the_semantics_were_not_guessed(decision):
    assert decision["guessed"] is False
    assert decision["agent_recommendation"]["selected_by_agent"] is False
    assert decision["agent_recommendation"]["authority_to_select"] == "OWNER"


def test_the_three_readings_are_all_recorded(decision):
    assert [r["id"] for r in decision["candidate_readings"]] == ["A", "B", "C"]


def test_only_reading_b_is_structurally_blocked(decision):
    blocked = {r["id"]: r["structurally_blocked"]
               for r in decision["candidate_readings"]}
    assert blocked == {"A": False, "B": True, "C": False}


def test_reading_b_is_blocked_by_the_frozen_row_binding(decision):
    reading = next(r for r in decision["candidate_readings"] if r["id"] == "B")
    assert "identity determines R" in reading["blocked_by"]


def test_reading_c_is_argued_against_on_likelihood_grounds(decision):
    reading = next(r for r in decision["candidate_readings"] if r["id"] == "C")
    assert "NON-OBSERVATION" in reading["against"]


def test_mixed_outcomes_cover_only_valid_replica_disagreement(decision):
    frozen = {item["item"]: item
              for item in decision["what_v3_authority_DOES_freeze"]}
    mixed = frozen["mixed replica outcomes are valid supervision"]
    assert "VALID replicas" in mixed["covers"]


def test_gate_s8_proves_the_case_is_not_hypothetical(decision):
    s8 = next(item for item in decision["what_v3_authority_DOES_freeze"]
              if item.get("gate") == "S8")
    assert "not a hypothetical case" in s8["implication"]


def test_infrastructure_failure_is_kept_separate(decision):
    separate = decision["infrastructure_failure_is_separate"]
    assert separate["unaffected_by_this_decision"] is True
    assert "is NOT a Bernoulli failure observation" in separate["rule"]


# --------------------------------------------------------------- I1 hashes
FROZEN_CONTRACTS = {
    "probabilistic target p(x, tau)":
        "a127bf9fbe907c81f2cd8037e94164f738ee756d7480c7db6955d7405bc355b6",
    "replica protocol, R per family":
        "6c2143c4782f0d851205cb118a2ff1c3e33c8a6a3e3cdc2ce5a820106551fa9a",
    "row identity and binding":
        "bdab65bdabbf503dc4d76d7d66d14c6504feb657b32d153a89643fab55058a8c",
    "event-equal grouped Bernoulli loss":
        "fc9c093327eaaa5ae95c038cf36a2a16ff2fee6d5fdc125dd1106bc3a99dfc11",
    "event-equal replica-normalized Brier":
        "0bf6dee325825953d856fb4f6b5df190879424b0d5e8d29cbe55ac930f682f04",
}


@pytest.mark.parametrize("concept,expected", sorted(FROZEN_CONTRACTS.items()))
def test_binding_pins_the_exact_frozen_contract_hash(binding, concept, expected):
    entry = next(b for b in binding["bindings"]
                 if b["scientific_concept"] == concept)
    assert entry["sha256"] == expected


def test_every_binding_hash_is_a_full_sha256(binding):
    for entry in binding["bindings"]:
        assert len(entry["sha256"]) == 64
        assert "..." not in entry["sha256"]


def test_recovered_roots_are_full_and_distinct_from_the_artifact_hashes(binding):
    roots = binding["FULL_ROOTS_RECOVERED"]
    pairs = (("official_v3_train_manifest_dry_final_sha256",
              "train_manifest_outer_artifact_sha256"),
             ("official_v3_validation_manifest_dry_final_sha256",
              "validation_manifest_outer_artifact_sha256"),
             ("v3_comprehensive_development_exclusion_union_v2_sha256",
              "exclusion_union_outer_artifact_sha256"))
    for inner, outer in pairs:
        assert len(roots[inner]) == 64 and len(roots[outer]) == 64
        assert roots[inner] != roots[outer]


def test_the_prompt_abbreviations_named_outer_artifact_hashes(binding):
    roots = binding["FULL_ROOTS_RECOVERED"]
    assert roots["train_manifest_outer_artifact_sha256"].startswith("ffb1fe33")
    assert roots["validation_manifest_outer_artifact_sha256"].startswith("72f88a62")
    assert roots["official_v3_train_manifest_dry_final_sha256"].startswith(
        "6390cd31")
    assert roots["official_v3_validation_manifest_dry_final_sha256"].startswith(
        "431e42ee")


def test_registry_root_matches_the_prompt(binding):
    roots = binding["FULL_ROOTS_RECOVERED"]
    assert roots["v3_layout_split_registry_v2_sha256"] == (
        "5494914e687a306b0288ce416e80d7c8a25f0f79377580eba58edc538d53680a")


def test_frozen_contracts_verified_exact(binding):
    assert binding["frozen_contracts_verified_exact"] is True


# --------------------------------------------------------------- I28 dry
def test_dry_manifest_shape_is_the_frozen_shape(binding):
    dry = binding["I28_dry_manifest_verification"]
    assert dry["dry_only"] is True
    assert dry["train"] == {"source_episodes": 1200, "layouts": 20,
                            "episodes_per_layout": 60.0,
                            "offsets": [0.22, 0.54], "executed": 0, "rows": 0}
    assert dry["validation"] == {"source_episodes": 300, "layouts": 10,
                                 "episodes_per_layout": 30.0,
                                 "offsets": [0.65], "executed": 0, "rows": 0}


def test_offset_0_33_is_absent_from_both_splits(binding):
    dry = binding["I28_dry_manifest_verification"]
    assert 0.33 not in dry["train"]["offsets"]
    assert 0.33 not in dry["validation"]["offsets"]


# --------------------------------------------------------------- gate 7
def test_historical_gate7_is_unchanged_and_still_fails(binding):
    gate = binding["historical_v2_gate7"]
    assert gate["status"] == "FAILED_FOR_V2"
    assert gate["modified"] is False
    assert gate["still_exceeds"] is True
    assert gate["value"] > gate["threshold"]
    assert gate["v3_applicability"] == "NOT_APPLICABLE_TO_V3_PROBABILISTIC_TARGET"


def test_gate7_is_never_relabelled_as_passing(binding):
    text = json.dumps(binding["historical_v2_gate7"])
    assert "PASSED" not in text
    assert "THRESHOLD_CHANGED" not in text


def test_the_live_v2_gate7_record_still_reads_fail():
    record = load("phase9d_v2c_r_gate7_replica_instability_v1.json")
    assert record["result"] == "FAIL"
    assert 59 / 530 > 0.10


# --------------------------------------------------------------- readiness
def test_no_code_was_written(readiness, binding):
    assert readiness["code_written"] == 0
    assert readiness["modules_created"] == 0
    assert readiness["images_built"] == 0
    assert binding["no_code_written"] is True


def test_no_official_v3_data_was_generated(readiness):
    assert readiness["I53_official_manifest_protection"] == {
        "official_v3_train_source_episodes_executed": 0,
        "official_v3_validation_source_episodes_executed": 0,
        "official_v3_scientific_rows": 0,
        "official_v3_target_v4_evaluations": 0,
        "qualification_identities_created": 0}


def test_sealed_domains_untouched(readiness):
    assert readiness["I54_sealed_domains"] == {
        "study_a_n24_accesses": 0, "study_b_accesses": 0,
        "final_test_accesses": 0, "sealed_outcomes_enumerated": 0}


def test_nothing_frozen_was_modified(readiness):
    assert readiness["frozen_contracts_modified"] == 0
    assert readiness["v2_modified"] == 0
    assert readiness["gate7_modified"] == 0


def test_no_training_and_no_hp_search(readiness):
    assert readiness["models_trained"] == 0
    assert readiness["hp_trials"] == 0


def test_verdict_is_d_with_the_blocking_recommendation(readiness):
    assert readiness["verdict"] == "D"
    assert readiness["recommendation"] == "DO_NOT_GENERATE_OFFICIAL_V3_DATA"


def test_readiness_carries_the_same_stop_token(readiness):
    assert readiness["STOP_TOKEN"] == STOP
    assert readiness["stopped_at_gate"] == "I10"


def test_the_unstarted_work_is_declared_rather_than_implied(readiness):
    assert len(readiness["work_not_started"]) >= 7
    assert "guessed rule" in readiness["why_not_started"]
