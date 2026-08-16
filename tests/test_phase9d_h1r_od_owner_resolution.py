"""Phase 9D-H1R-OD -- owner resolution, frozen protocol, fixed-budget manifest.

The owner superseded the historical 70/30 sampling clause for Recoverability V2.
These tests pin that the resolution changed *only* the authority record: the
executable selection semantics are byte-identical to the H1R design object, the
rule stays candidate-blind and deterministic, the source-episode budget stays
frozen, and manifest compilation fails closed on design-pilot reuse and on every
sealed domain.
"""

from __future__ import annotations

import copy
import json
import pathlib

import pytest

from rvt_swarm.phase8.common import (
    canonical_json_bytes, sha256_document, verify_canonical_hash,
)
from rvt_swarm.phase9d_h1r.acquisition_v2 import (
    DEFAULT_K, REALIZED_TRAJECTORY_UNIFORM_K, SELECTION_SEMANTICS_KEYS,
    SOURCE_EVENT_IDENTITY_SCHEMA_VERSION, SUPERSEDED_SAMPLING_CLAUSE,
    AcquisitionError, acquisition_protocol_v2, acquisition_protocol_v2_sha256,
    build_source_event_key, frozen_acquisition_protocol_v2,
    frozen_acquisition_protocol_v2_sha256, recoverability_source_event_id_v2,
    select, selection_semantics,
)
from rvt_swarm.phase9d_h1r.exclusion import (
    DesignPilotReuseError, design_pilot_identity,
)
from rvt_swarm.phase9d_h1r.manifest_v2 import (
    FROZEN_DECISION_EVENT_CAP, FROZEN_SOURCE_EPISODE_BUDGET,
    ManifestCompilationError, compile_v2_source_manifest,
)

ROOT = pathlib.Path("results/rvt_fd24")

DESIGN = acquisition_protocol_v2()
DESIGN_SHA = acquisition_protocol_v2_sha256(DESIGN)
FROZEN = frozen_acquisition_protocol_v2(design_protocol_sha256=DESIGN_SHA)
FROZEN_SHA = frozen_acquisition_protocol_v2_sha256(FROZEN)

OD_ARTIFACTS = {
    "owner_resolution": ("phase9d_h1r_owner_sampling_resolution_v1.json",
                         "phase9d_h1r_owner_sampling_resolution_sha256"),
    "frozen_protocol": (
        "phase9d_h1r_od_source_acquisition_protocol_v2_frozen.json",
        "phase9d_h1r_od_source_acquisition_protocol_v2_frozen_sha256"),
    "requalification": ("phase9d_h1r_od_feasibility_requalification_v1.json",
                        "phase9d_h1r_od_feasibility_requalification_sha256"),
    "readiness_v2": ("phase9d_h1r_v2_generation_readiness_v2.json",
                     "phase9d_h1r_v2_generation_readiness_v2_sha256"),
}


def load(name):
    path, _field = OD_ARTIFACTS[name]
    return json.loads((ROOT / path).read_text(encoding="ascii"))


# ---------------------------------------------------------------------------
# the resolution changed the authority record, not the rule
# ---------------------------------------------------------------------------
def test_frozen_protocol_selection_semantics_are_identical_to_the_design() -> None:
    assert selection_semantics(FROZEN) == selection_semantics(DESIGN)


def test_frozen_protocol_keeps_the_rule_and_k() -> None:
    assert FROZEN["rule"] == REALIZED_TRAJECTORY_UNIFORM_K == "REALIZED_TRAJECTORY_UNIFORM_K"
    assert FROZEN["K"] == DEFAULT_K == 5
    assert FROZEN["status"] == "FROZEN"


def test_frozen_protocol_records_the_supersession_explicitly() -> None:
    clause = FROZEN["superseded_sampling_clause"]
    assert clause["status"] == "SUPERSEDED_FOR_RECOVERABILITY_V2"
    assert clause["clause"] == \
        "Sampling is 70% event-balanced and 30% trajectory-uniform."
    assert clause["authority"] == "docs/RVT_DECISION_STATE_SAMPLING_PROTOCOL.md"
    assert clause["post_hoc_meaning_invented"] is False
    assert clause["superseded_prospectively"] is True


def test_frozen_protocol_hash_differs_from_the_design_hash() -> None:
    assert FROZEN_SHA != DESIGN_SHA
    assert FROZEN["design_protocol_sha256"] == DESIGN_SHA


def test_frozen_protocol_declares_h1_unchanged() -> None:
    assert FROZEN["h1_meaning_unchanged"] is True
    assert FROZEN["source_acquisition_v2_prospectively_amended"] is True
    for item in ("Target V4", "candidate rollout", "candidate-pair atomicity",
                 "evaluation metric", "paired comparison", "baseline definition",
                 "Recoverability definition", "candidate topology"):
        assert item in FROZEN["unchanged_by_this_amendment"]


def test_frozen_protocol_forbids_post_freeze_adaptation() -> None:
    decision = FROZEN["owner_decision"]
    assert decision["adaptive_change_after_freeze_permitted"] is False
    for banned in ("future V2 positive/negative balance", "candidate validity",
                   "family performance", "validation score", "H1 metric",
                   "training quality"):
        assert banned in decision["may_not_be_revised_using"]


def test_frozen_protocol_does_not_authorize_generation() -> None:
    assert FROZEN["authorizes_official_generation"] is False


# ---------------------------------------------------------------------------
# selection semantics under the final owner rule
# ---------------------------------------------------------------------------
class _Universe:
    def __init__(self, m):
        self.M = m


@pytest.mark.parametrize("m,expected", [
    (0, ()), (1, (0,)), (2, (0, 1)), (3, (0, 1, 2)), (4, (0, 1, 2, 3)),
    (5, (0, 1, 2, 3, 4)), (6, (0, 1, 2, 3, 5)), (13, (0, 3, 6, 9, 12)),
    (101, (0, 25, 50, 75, 100)),
])
def test_owner_rule_selection(m, expected) -> None:
    assert select(REALIZED_TRAJECTORY_UNIFORM_K, _Universe(m), DEFAULT_K) == expected


def test_owner_formula_matches_floor_j_times_m_minus_one_over_four() -> None:
    for m in range(6, 500):
        expected = sorted({(j * (m - 1)) // 4 for j in range(5)})
        assert list(select(REALIZED_TRAJECTORY_UNIFORM_K, _Universe(m),
                           DEFAULT_K)) == expected


def test_first_and_last_eligible_states_always_selected() -> None:
    for m in range(1, 300):
        chosen = select(REALIZED_TRAJECTORY_UNIFORM_K, _Universe(m), DEFAULT_K)
        assert chosen[0] == 0 and chosen[-1] == m - 1


def test_no_fabrication_and_never_more_than_k() -> None:
    for m in range(0, 300):
        chosen = select(REALIZED_TRAJECTORY_UNIFORM_K, _Universe(m), DEFAULT_K)
        assert len(chosen) == min(m, DEFAULT_K)
        assert len(set(chosen)) == len(chosen)


def test_selection_is_deterministic_across_repeated_calls() -> None:
    for m in (0, 3, 5, 37, 87):
        runs = {select(REALIZED_TRAJECTORY_UNIFORM_K, _Universe(m), DEFAULT_K)
                for _ in range(25)}
        assert len(runs) == 1


# ---------------------------------------------------------------------------
# candidate blindness and the acquisition preimage
# ---------------------------------------------------------------------------
OUTCOME_TOKENS = (
    "aggregate_label", "recoverability_label", "compact_outcome", "line_outcome",
    "target_v4_disposition", "RECOVERABLE_POSITIVE", "VALID_TASK_NEGATIVE",
    "both_success", "both_fail", "decisive", "model_prediction", "class_balance",
    "pair_retention", "candidate_validity",
)


def test_no_outcome_field_appears_in_the_acquisition_hash_preimage() -> None:
    """The bytes actually hashed to produce the frozen protocol hash must not
    contain a candidate-outcome field. The declared prohibition list is excluded
    from the scan, since naming what is banned is not using it."""
    preimage = copy.deepcopy(FROZEN)
    preimage.pop("prohibited_selection_inputs", None)
    preimage["superseded_sampling_clause"].pop("why_non_operational", None)
    preimage["owner_decision"].pop("may_not_be_revised_using", None)
    payload = canonical_json_bytes(preimage).decode("ascii").lower()
    for token in OUTCOME_TOKENS:
        assert token.lower() not in payload, token


def test_no_outcome_field_appears_in_the_event_identity_preimage() -> None:
    state = type("S", (), {"control_step": 120,
                           "source_state_fingerprint": "b" * 64})()
    key = build_source_event_key(
        study="study_a_zero_shot", split="validation", family="F4",
        layout_sha256="a" * 64, team_size=16, episode_id="episode-7",
        state=state, protocol_sha256=FROZEN_SHA)
    payload = canonical_json_bytes(key).decode("ascii").lower()
    for token in OUTCOME_TOKENS:
        assert token.lower() not in payload, token
    assert recoverability_source_event_id_v2(key) == sha256_document(key)


def test_event_identity_still_rejects_outcome_dimensions() -> None:
    state = type("S", (), {"control_step": 10,
                           "source_state_fingerprint": "c" * 64})()
    key = build_source_event_key(
        study="s", split="train", family="F1", layout_sha256="a" * 64,
        team_size=5, episode_id="e", state=state, protocol_sha256=FROZEN_SHA)
    for field in ("aggregate_label", "label", "disposition", "model_output",
                  "candidate_topology", "worker_id", "chunk_id", "attempt_index"):
        with pytest.raises(AcquisitionError):
            recoverability_source_event_id_v2(dict(key, **{field: 1}))


def test_v1_and_v2_event_identities_are_separated() -> None:
    assert SOURCE_EVENT_IDENTITY_SCHEMA_VERSION == \
        "rvt-recoverability-source-event-identity/v2"
    state = type("S", (), {"control_step": 60,
                           "source_state_fingerprint": "d" * 64})()
    v2_key = build_source_event_key(
        study="study_a_zero_shot", split="train", family="F1",
        layout_sha256="a" * 64, team_size=6, episode_id="episode-0",
        state=state, protocol_sha256=FROZEN_SHA)
    # A V1-style identity carries no realized state and no protocol hash, so the
    # two namespaces cannot collide.
    v1_like = {"schema_version": "rvt-generation-job-identity/v1",
               "study": "study_a_zero_shot", "split": "train", "family": "F1",
               "team_size": 6, "episode_id": "episode-0",
               "decision_event_id": "event-0"}
    assert sha256_document(v1_key := v2_key) != sha256_document(v1_like)
    assert "realized_source_timestep" in v1_key
    assert "decision_event_id" not in v1_key


def test_protocol_hash_changes_if_k_or_rule_changes() -> None:
    for mutation in ({"K": 4}, {"rule": "FIRST_K_ELIGIBLE"},
                     {"include_initial_state": False}):
        mutated = dict(FROZEN, **mutation)
        assert sha256_document(mutated) != FROZEN_SHA


# ---------------------------------------------------------------------------
# fixed-budget manifest compilation
# ---------------------------------------------------------------------------
def episodes_for(split, count, *, study="study_a_zero_shot", team_size=8):
    return [{"study": study, "split": split, "family": "F%d" % (index % 10 + 1),
             "team_size": team_size, "layout_id": "%s-f%d-00" % (split,
                                                                 index % 10 + 1),
             "source_policy": "S1_ALWAYS_COMPACT",
             "episode_id": "%s/episode-%d" % (split, index),
             "seed_identity": "s" * 64}
            for index in range(count)]


def test_manifest_compiles_at_exactly_the_frozen_budget() -> None:
    for split, budget in FROZEN_SOURCE_EPISODE_BUDGET.items():
        manifest = compile_v2_source_manifest(
            split, episodes_for(split, budget), protocol_sha256=FROZEN_SHA,
            excluded=set())
        assert manifest["source_episodes"] == budget
        assert manifest["maximum_selected_source_events"] == budget * DEFAULT_K
        assert manifest["maximum_selected_source_events"] == \
            FROZEN_DECISION_EVENT_CAP[split]
        assert manifest["maximum_saturates_frozen_cap"] is True
        assert manifest["authorizes_official_generation"] is False
        assert verify_canonical_hash(manifest, "v2_source_manifest_sha256")


def test_frozen_budget_matches_committed_authority() -> None:
    budget = json.loads(
        (ROOT / "datasets" / "generation_budget_v1.json").read_text())
    declared = {dataset["split"]: dataset["expected_source_episodes"]
                for dataset in budget["datasets"]
                if dataset["study"] == "study_a_zero_shot"}
    assert declared["train"] == FROZEN_SOURCE_EPISODE_BUDGET["train"] == 1200
    assert declared["validation"] == FROZEN_SOURCE_EPISODE_BUDGET["validation"] == 300
    events = {dataset["split"]: dataset["expected_decision_events"]
              for dataset in budget["datasets"]
              if dataset["study"] == "study_a_zero_shot"}
    assert events["train"] == FROZEN_DECISION_EVENT_CAP["train"] == 6000
    assert events["validation"] == FROZEN_DECISION_EVENT_CAP["validation"] == 1500


@pytest.mark.parametrize("delta", [-1, 1, -300, 60])
def test_manifest_refuses_any_budget_other_than_the_frozen_one(delta: int) -> None:
    budget = FROZEN_SOURCE_EPISODE_BUDGET["validation"]
    with pytest.raises(ManifestCompilationError):
        compile_v2_source_manifest(
            "validation", episodes_for("validation", budget + delta),
            protocol_sha256=FROZEN_SHA, excluded=set())


def test_manifest_fails_closed_on_a_design_pilot_identity() -> None:
    budget = FROZEN_SOURCE_EPISODE_BUDGET["validation"]
    episodes = episodes_for("validation", budget)
    burned = {design_pilot_identity(**{k: v for k, v in episodes[7].items()})}
    with pytest.raises(DesignPilotReuseError):
        compile_v2_source_manifest("validation", episodes,
                                   protocol_sha256=FROZEN_SHA, excluded=burned)


def test_manifest_uses_the_committed_exclusion_set_by_default() -> None:
    document = json.loads(
        (ROOT / "phase9d_h1r_design_pilot_exclusion_set_v1.json").read_text())
    entry = document["excluded_identities"][0]
    fields = {name: entry[name] for name in
              ("study", "split", "family", "team_size", "layout_id",
               "source_policy", "episode_id", "seed_identity")}
    budget = FROZEN_SOURCE_EPISODE_BUDGET["validation"]
    episodes = episodes_for("validation", budget)
    episodes[0] = dict(fields, split="validation")
    # split is rewritten so the compiler reaches the exclusion check rather than
    # the split guard; the identity then no longer matches, proving the guard is
    # keyed on the whole identity and not on a substring.
    manifest = compile_v2_source_manifest("validation", episodes,
                                          protocol_sha256=FROZEN_SHA)
    assert manifest["design_pilot_identities_excluded"] == \
        document["excluded_identity_count"] == 300


def test_manifest_rejects_duplicate_identities() -> None:
    budget = FROZEN_SOURCE_EPISODE_BUDGET["validation"]
    episodes = episodes_for("validation", budget)
    episodes[5] = dict(episodes[4])
    with pytest.raises(ManifestCompilationError):
        compile_v2_source_manifest("validation", episodes,
                                   protocol_sha256=FROZEN_SHA, excluded=set())


def test_manifest_declares_no_adaptive_refill() -> None:
    manifest = compile_v2_source_manifest(
        "validation", episodes_for("validation", 300),
        protocol_sha256=FROZEN_SHA, excluded=set())
    assert manifest["adaptive_refill_permitted"] is False
    assert manifest["outcome_dependent_stopping_permitted"] is False
    assert manifest["actual_selected_events_may_be_lower"] is True
    for rule in ("generate until 30 labels", "generate until class balance is good",
                 "generate until a family reaches a target"):
        assert rule in manifest["forbidden_stopping_rules"]


# ---------------------------------------------------------------------------
# seals
# ---------------------------------------------------------------------------
def test_manifest_refuses_n24_episodes() -> None:
    episodes = episodes_for("validation", 300)
    episodes[3] = dict(episodes[3], team_size=24)
    with pytest.raises(ManifestCompilationError):
        compile_v2_source_manifest("validation", episodes,
                                   protocol_sha256=FROZEN_SHA, excluded=set())


def test_manifest_refuses_sealed_studies_and_splits() -> None:
    for mutation in ({"study": "study_a_n24_evaluation"},
                     {"study": "study_b_with_n24"},
                     {"split": "n24_evaluation"}, {"split": "final_test"}):
        episodes = episodes_for("validation", 300)
        episodes[11] = dict(episodes[11], **mutation)
        with pytest.raises((ManifestCompilationError,)):
            compile_v2_source_manifest("validation", episodes,
                                       protocol_sha256=FROZEN_SHA, excluded=set())


@pytest.mark.parametrize("split", ["final_test", "test", "n24_evaluation",
                                   "study_b_train"])
def test_no_sealed_split_has_a_v2_budget(split: str) -> None:
    with pytest.raises(ManifestCompilationError):
        compile_v2_source_manifest(split, [], protocol_sha256=FROZEN_SHA,
                                   excluded=set())


# ---------------------------------------------------------------------------
# OD artifacts
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("name", sorted(OD_ARTIFACTS))
def test_od_artifact_hashes_canonically(name: str) -> None:
    path, field = OD_ARTIFACTS[name]
    document = json.loads((ROOT / path).read_text(encoding="ascii"))
    assert verify_canonical_hash(document, field)


def test_owner_resolution_binds_the_previous_h1r_evidence() -> None:
    resolution = load("owner_resolution")
    predecessor = resolution["predecessor"]
    assert predecessor["h1r_commit"] == \
        "22159b13283974a5fd6f34eba91f88544e141bf2"
    assert predecessor["historical_evidence_rewritten"] is False
    assert predecessor["h1r_verdict"] == "A"
    assert predecessor["h1r_design_protocol_object_sha256"] == DESIGN_SHA
    assert resolution["frozen_protocol_sha256"] == FROZEN_SHA


def test_owner_resolution_records_the_clause_and_its_authority_hash() -> None:
    clause = load("owner_resolution")["historical_clause"]
    assert clause["status"] == "SUPERSEDED_FOR_RECOVERABILITY_V2"
    assert clause["authority_file_sha256_matches_h1_requirement_map"] is True
    assert clause["incompleteness_authority"]["status"] == \
        "BLOCKED_PROTOCOL_INCOMPLETENESS"


def test_owner_resolution_forbids_outcome_based_event_balancing() -> None:
    decision = load("owner_resolution")["owner_decision"]
    assert decision["post_hoc_meaning_for_event_balanced_invented"] is False
    for banned in ("recoverability label", "COMPACT outcome", "LINE outcome",
                   "both-success", "both-fail", "decisive outcome",
                   "candidate validity", "Target V4 result", "model prediction",
                   "class balance", "pair retention"):
        assert banned in decision["prohibited_event_balancing_inputs"]
    assert decision["recorded_as"] == "V2_PROTOCOL_AMENDMENT"
    assert decision["disguised_as_original_v1_rule"] is False


def test_owner_resolution_freezes_generation_invalid_semantics() -> None:
    semantics = load("owner_resolution")["generation_invalid_semantics"]
    assert semantics["unreached_future_source_state_is_generation_invalid"] is False
    assert semantics["unreached_future_source_state_disposition"] == \
        "NOT_A_REALIZED_SOURCE_STATE"
    assert semantics[
        "generation_invalid_requires_an_actually_attempted_candidate_rollout"] is True
    assert semantics["m_zero_episode_contributes_selected_events"] == 0
    assert semantics["m_zero_episode_contributes_fake_events"] == 0
    assert semantics["m_zero_episode_contributes_fake_candidate_invalids"] == 0


def test_owner_resolution_keeps_v1_pilot_only_and_immutable() -> None:
    policy = load("owner_resolution")["v1_data_policy"]
    assert policy["classification"] == "PILOT_DESIGN_DIAGNOSTIC"
    assert policy["merged_into_v2_confirmatory_data"] is False
    assert policy["mutated"] is False and policy["deleted"] is False
    assert policy["manifests_and_seals_preserved_permanently"] is True
    assert policy["train_manifest_sha256"] == \
        "4ac3d2cb65a8b5d656a5d982b344466868f8deaa8cef2b93af7ce824e9387caf"
    assert policy["validation_manifest_sha256"] == \
        "c991aa3016b38b524a14d9b7037b63d97c2cbbb7d92279fc5a297b9c55d4989e"
    assert policy["combined_recoverability_root_sha256"] == \
        "7e583ef98184767edfb95387ecc23d2ab266e2137db28a9fbb3badccaa495672"


def test_owner_resolution_keeps_the_budget_and_gate_frozen() -> None:
    resolution = load("owner_resolution")
    budget = resolution["fixed_source_budget"]
    assert budget["train_source_episodes"] == 1200
    assert budget["validation_source_episodes"] == 300
    assert budget["confirmed_from_committed_authority"] is True
    assert budget["k_saturates_frozen_caps_exactly"] is True
    assert budget["replenish_missing_events"] is False
    assert budget["extra_episodes_when_M_below_K"] is False
    assert budget["outcome_dependent_stopping"] is False
    gate = resolution["adequacy_gate"]
    assert gate[
        "required_minimum_retained_validation_events_per_primary_family"] == 30
    assert gate["lowered"] is False and gate["retained_redefined"] is False
    assert gate["difficult_families_removed"] is False


def test_requalification_reuses_committed_evidence_without_new_search() -> None:
    requalification = load("requalification")
    assert requalification["evidence_reused_not_regenerated"] is True
    assert requalification["new_outcome_informed_search_performed"] is False
    assert requalification["K_tuned"] is False
    feasibility = json.loads(
        (ROOT / "phase9d_h1r_source_only_feasibility_v1.json").read_text())
    assert requalification["source_evidence"]["sha256"] == \
        feasibility["phase9d_h1r_source_only_feasibility_sha256"]


def test_requalification_shows_every_family_clearing_the_gate() -> None:
    requalification = load("requalification")
    rows = requalification["by_family"]
    assert [row["family"] for row in rows] == ["F%d" % i for i in range(1, 11)]
    assert requalification["all_families_have_nonzero_support"] is True
    assert requalification["families_below_gate"] == []
    for row in rows:
        assert row["selected_v2_states"] > 0
        assert row["projected_retained_validation_events"] >= 30
        assert row["meets_gate"] is True
    assert requalification["worst_family"]["family"] == "F4"
    assert requalification["worst_family_margin_over_gate"] >= 1.0


def test_readiness_v2_reports_the_resolved_state() -> None:
    readiness = load("readiness_v2")
    assert readiness["owner_decision_resolved"] is True
    assert readiness["h1_meaning_unchanged"] is True
    assert readiness["source_acquisition_protocol_v2_sha256"] == FROZEN_SHA
    assert readiness["rule"] == REALIZED_TRAJECTORY_UNIFORM_K
    assert readiness["K"] == 5
    assert readiness["candidate_blind"] is True
    assert readiness["design_pilot_exclusion_active"] is True
    assert readiness["v1_reused"] is False
    assert readiness["adequacy_threshold_unchanged"] is True
    assert readiness["adequacy_threshold"] == 30
    assert readiness["fixed_train_source_budget"] == 1200
    assert readiness["fixed_validation_source_budget"] == 300
    assert readiness["projected_worst_family_validation_support"] >= 30
    assert readiness["official_generation_started"] is False
    assert readiness["verdict"] == "C"
    assert readiness["recommendation"] == \
        "AUTHORIZE_FRESH_RECOVERABILITY_V2_GENERATION"


def test_readiness_v2_keeps_every_sealed_counter_at_zero() -> None:
    counters = load("readiness_v2")["sealed_domain_counters"]
    assert set(counters.values()) == {0}


def test_readiness_v2_does_not_authorize_residual_or_training() -> None:
    readiness = load("readiness_v2")
    assert readiness["official_v2_generation_authorized"] is False
    assert readiness["residual_v2_authorized"] is False
    assert readiness["training_authorized"] is False


def test_readiness_v2_supersedes_v1_without_rewriting_it() -> None:
    readiness = load("readiness_v2")
    previous = json.loads(
        (ROOT / "phase9d_h1r_v2_generation_readiness_v1.json").read_text())
    assert readiness["supersedes"]["rewritten"] is False
    assert readiness["supersedes"]["sha256"] == \
        previous["phase9d_h1r_v2_generation_readiness_sha256"]
    assert previous["verdict"] == "A"
    assert verify_canonical_hash(
        previous, "phase9d_h1r_v2_generation_readiness_sha256")


def test_frozen_protocol_artifact_matches_the_executable_object() -> None:
    document = load("frozen_protocol")
    assert document["acquisition_protocol_sha256"] == FROZEN_SHA
    assert document["supersession_status"] == "SUPERSEDED_FOR_RECOVERABILITY_V2"
    assert document["selection_semantics_unchanged_from_design"] is True
    assert document["selection_semantics_digest"] == \
        sha256_document(selection_semantics(FROZEN))
    assert set(SELECTION_SEMANTICS_KEYS) <= set(document["acquisition_protocol"])
