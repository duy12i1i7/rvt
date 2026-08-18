"""Phase 9D-V3F -- owner decision and prospective V3 freeze.

Read-only tests over the frozen V3 contracts and dry manifests. They also
preserve the historical V2 record: gate 7 failed at 59/530 and that fact must
survive. Nothing here may modify or contradict that pin.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import pytest

from rvt_swarm.phase8.common import sha256_document, verify_canonical_hash
from rvt_swarm.phase8.scenario import STUDY_A_TRAINING_SIZES
from rvt_swarm.phase9c_rb.counterfactual import replica_count_for_family

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results" / "rvt_fd24"

GATE7_THRESHOLD = 0.10
V2_FAILING = (59, 530)
V2_TRAIN_SEAL = "a966f318832fb60bd99acdfdff72f0c7011d730f3e0fb51494ce318210f39bba"
V2_VAL_SEAL = "667b117555a65ad9da7f8e6e7f71b2cfb6843cc66d8e8c35eb68650b7818ca69"
FROZEN_ACQ = "19fa68a37d80f16ee1463b872f26402963daeb5a56f375423634a90dc1f3546d"
TV4 = "54a0e0baff79fbdc320800b772f47a40ac06ac4f0e70d4fab1bf676c54b918ee"
FAMILIES = ["F%d" % index for index in range(1, 11)]

ARTIFACTS = [
    "phase9d_v3f_owner_decisions_v1.json",
    "phase9d_v3f_h1_compatibility_v1.json",
    "phase9d_v3f_probabilistic_target_contract_v1.json",
    "phase9d_v3f_replica_protocol_v1.json",
    "phase9d_v3f_row_binding_v1.json",
    "phase9d_v3f_training_loss_contract_v1.json",
    "phase9d_v3f_brier_metric_contract_v1.json",
    "phase9d_v3f_gate_registry_v1.json",
    "phase9d_v3f_layout_split_registry_v1.json",
    "phase9d_v3f_train_manifest_dry_v1.json",
    "phase9d_v3f_validation_manifest_dry_v1.json",
    "phase9d_v3f_disjointness_audit_v1.json",
    "phase9d_v3f_exclusion_union_v1.json",
    "phase9d_v3f_compute_budget_v1.json",
    "phase9d_v3f_implementation_requirements_v1.json",
    "phase9d_v3f_qualification_plan_v1.json",
    "phase9d_v3f_publication_provenance_v1.json",
    "phase9d_v3f_final_readiness_v1.json",
]


def load(name):
    return json.loads((RESULTS / name).read_text(encoding="ascii"))


def hash_field(document):
    return next(key for key in document
                if key.startswith("phase9d_v3f_") and key.endswith("sha256"))


@pytest.fixture(scope="module")
def target():
    return load("phase9d_v3f_probabilistic_target_contract_v1.json")


@pytest.fixture(scope="module")
def replica():
    return load("phase9d_v3f_replica_protocol_v1.json")


@pytest.fixture(scope="module")
def binding():
    return load("phase9d_v3f_row_binding_v1.json")


@pytest.fixture(scope="module")
def train():
    return load("phase9d_v3f_train_manifest_dry_v1.json")


@pytest.fixture(scope="module")
def validation():
    return load("phase9d_v3f_validation_manifest_dry_v1.json")


@pytest.fixture(scope="module")
def readiness():
    return load("phase9d_v3f_final_readiness_v1.json")


# --------------------------------------------------------------------------
# artifacts
# --------------------------------------------------------------------------
@pytest.mark.parametrize("name", ARTIFACTS)
def test_artifact_exists_and_self_verifies(name):
    document = load(name)
    assert verify_canonical_hash(document, hash_field(document)), name


def test_all_eighteen_required_artifacts_exist():
    # exclude the later phase9d_v3f_l_* layout-capacity addendum, which shares
    # this glob prefix but belongs to Phase 9D-V3F-L
    own = [path for path in RESULTS.glob("phase9d_v3f_*.json")
           if not path.name.startswith("phase9d_v3f_l_")]
    assert len(own) == 18


@pytest.mark.parametrize("name,field", [
    ("phase9d_v3f_probabilistic_target_contract_v1.json",
     "recoverability_probabilistic_target_v3_sha256"),
    ("phase9d_v3f_replica_protocol_v1.json",
     "recoverability_replica_protocol_v3_sha256"),
    ("phase9d_v3f_row_binding_v1.json",
     "recoverability_row_binding_v3_spec_sha256"),
    ("phase9d_v3f_training_loss_contract_v1.json",
     "recoverability_training_loss_v3_sha256"),
    ("phase9d_v3f_brier_metric_contract_v1.json",
     "recoverability_brier_metric_v3_sha256"),
    ("phase9d_v3f_layout_split_registry_v1.json",
     "v3_layout_split_registry_sha256"),
])
def test_inner_contract_hash_is_a_full_64_hex(name, field):
    value = load(name)[field]
    assert len(value) == 64 and set(value) <= set("0123456789abcdef")


# --------------------------------------------------------------------------
# historical V2 must survive
# --------------------------------------------------------------------------
def test_v2_gate7_failure_is_preserved():
    gate7 = load("phase9d_v2c_r_gate7_replica_instability_v1.json")
    assert verify_canonical_hash(
        gate7, "phase9d_v2c_r_gate7_replica_instability_sha256")
    assert gate7["result"] == "FAIL"
    assert gate7["threshold"] == GATE7_THRESHOLD


def test_the_failing_ratio_still_exceeds_the_threshold():
    unstable, total = V2_FAILING
    assert unstable / total > GATE7_THRESHOLD


def test_v2_seals_unchanged(readiness):
    immutability = readiness["F17_historical_v2_immutability"]
    assert immutability["v2_train_seal"] == V2_TRAIN_SEAL
    assert immutability["v2_validation_seal"] == V2_VAL_SEAL
    assert immutability["v2_train_seal_unchanged"] is True
    assert immutability["v2_validation_seal_unchanged"] is True
    assert immutability["gate7_still_fail"] is True
    assert immutability["gate7_threshold_unchanged"] is True
    assert immutability["v2_code_or_contract_needed_for_replay_mutated"] is False


def test_gate7_is_retired_not_passed():
    historical = load("phase9d_v3f_gate_registry_v1.json")["HISTORICAL_V2_GATE_7"]
    assert historical["v2_result"] == "FAILED_FOR_V2"
    assert historical["v3_applicability"] == (
        "NOT_APPLICABLE_TO_V3_PROBABILISTIC_TARGET")
    assert historical["marked_passed"] is False
    assert historical["threshold_changed"] is False
    assert historical["erased"] is False
    assert "0.11132075471698113" in historical["v2_observed_value"]


def test_the_disagreement_cap_is_not_carried_over():
    forbidden = load("phase9d_v3f_gate_registry_v1.json")["forbidden_gate"]
    assert forbidden["status"] == "NOT CARRIED OVER TO V3"


# --------------------------------------------------------------------------
# F1 owner decisions
# --------------------------------------------------------------------------
def test_no_blocking_conflicts_and_no_silent_overrides():
    decisions = load("phase9d_v3f_owner_decisions_v1.json")
    assert decisions["blocking_conflict_count"] == 0
    assert decisions["blocking_conflicts"] == []
    assert decisions["silent_overrides"] == 0
    assert decisions["total_decisions"] == 34


def test_the_layout_capacity_consequence_is_declared():
    decisions = load("phase9d_v3f_owner_decisions_v1.json")
    consequences = decisions["declared_consequences"]
    assert consequences
    entry = consequences[0]
    assert entry["decision"] == "15"
    assert entry["owner_option"]
    assert "NOT authorized" in entry["owner_option"]


def test_h1_needs_no_rewording():
    compatibility = load("phase9d_v3f_h1_compatibility_v1.json")
    assert compatibility["verdict"] == "H1_PRESERVED_WITHOUT_REWORDING"
    assert compatibility["h1_owner_rewording_required"] is False
    assert compatibility["h1_wording_changed"] is False
    live = load("phase9d_h1_requirement_map_v1.json")
    assert compatibility["h1_exact_wording"] == live["h1_exact_statement"]
    actual = hashlib.sha256(
        (ROOT / "docs/RVT_FD24_RESEARCH_QUESTIONS_AND_HYPOTHESES.md").read_bytes()
    ).hexdigest()
    assert compatibility["h1_authority_sha256"] == actual


def test_h1_compatibility_separates_the_three_layers():
    layers = load("phase9d_v3f_h1_compatibility_v1.json")["three_layer_analysis"]
    assert layers["layer_1_historical_h1_scientific_claim"][
        "constrains_the_label_type"] is False
    assert layers["layer_2_historical_binary_implementation"]["named_in_h1"] is False
    assert layers["layer_3_v3_probabilistic_implementation"][
        "supports_the_same_selection_rule"] is True


def test_h1_drift_tripwire_exists():
    assert load("phase9d_v3f_h1_compatibility_v1.json")["drift_tripwire"]


# --------------------------------------------------------------------------
# F2 target contract
# --------------------------------------------------------------------------
def test_target_v4_is_referenced_not_redefined(target):
    per_replica = target["per_replica_target"]
    assert per_replica["target_v4_contract_sha256"] == TV4
    assert per_replica["redefined_by_v3"] is False
    assert "NEVER called Target V4" in per_replica["naming_rule"]


def test_observation_is_k_and_R(target):
    observation = target["observation"]
    assert observation["canonical_form"] == "(k, R)"
    assert observation["not_an_all_success_binary_label"] is True
    assert observation["not_an_abstention_label"] is True
    assert observation["not_a_three_state_class"] is True
    assert observation["not_a_hard_thresholded_p_estimate"] is True
    assert "convenience only" in observation["derived_descriptive_value"]


def test_mixed_outcomes_are_supervision(target):
    mixed = target["mixed_outcomes"]
    assert mixed["status"] == "VALID_SUPERVISION"
    assert len(mixed["patterns"]) == 6
    assert mixed["is_generation_invalid"] is False
    assert mixed["discarded"] is False
    assert mixed["outcome_dependent_filtering_permitted"] is False


def test_no_abstention_or_boundary_class(target):
    abstention = target["abstention"]
    assert abstention["ABSTENTION_TARGET"] == "NONE"
    assert abstention["BOUNDARY_CLASS"] == "NONE"
    assert abstention["THREE_STATE_TARGET"] == "NONE"


def test_disturbance_law_is_bound_and_scope_limited(target):
    law = target["disturbance_law"]
    assert law["distribution"] == "uniform on a disk of radius 0.05 * a_max"
    assert law["iid_across_replicas"] is True
    assert "RELATIVE TO this frozen simulation" in law["SCOPE_LIMITATION"]
    actual = hashlib.sha256(
        (ROOT / "docs/PHASE8E_INITIALIZATION_AND_DISTURBANCE_CONTRACT.md"
         ).read_bytes()).hexdigest()
    assert law["authority_sha256"] == actual


def test_no_runtime_threshold_is_frozen(target):
    assert target["runtime_threshold_frozen_here"] is False
    assert target["model_output"]["hard_class_output"] is False
    assert target["model_output"]["abstain_output"] is False


def test_target_contract_hash_recomputes(target):
    body = {k: v for k, v in target.items()
            if k not in ("recoverability_probabilistic_target_v3_sha256",
                         "phase9d_v3f_probabilistic_target_contract_sha256")}
    assert sha256_document(body) == target[
        "recoverability_probabilistic_target_v3_sha256"]


# --------------------------------------------------------------------------
# F3 replica protocol
# --------------------------------------------------------------------------
def test_replica_counts_match_the_frozen_classification(replica):
    counts = replica["replica_counts"]
    for family in FAMILIES:
        assert counts[family] == replica_count_for_family(family), family
    assert replica["family_stochastic_classification"][
        "stochastic_families"] == ["F8", "F9"]
    assert replica["family_stochastic_classification"][
        "additional_stochastic_families_inferred"] == 0


def test_adaptive_replication_is_disabled(replica):
    assert replica["adaptive_replication"] == "DISABLED"
    assert replica["R_expansion_permitted"] is False
    assert len(replica["adaptive_replication_rationale"]) >= 5


def test_matched_randomness_is_required(replica):
    matched = replica["matched_randomness"]
    assert "COMPACT" in matched["requirement"] and "LINE" in matched["requirement"]
    assert matched["candidate_specific_streams"] == "FORBIDDEN"
    assert replica["counter_stream_authority"]["worker_order_invariant"] is True
    assert replica["counter_stream_authority"]["retry_invariant"] is True


def test_r3_precision_disclaimer_present(replica):
    assert "NOT claimed to estimate" in replica["R3_precision_disclaimer"]


# --------------------------------------------------------------------------
# F4/F5/F6 row binding
# --------------------------------------------------------------------------
def test_row_identity_excludes_every_outcome_field(binding):
    fields = set(binding["row_identity_fields"])
    for prohibited in binding["prohibited_identity_fields"]:
        assert prohibited not in fields, prohibited
    assert "k" not in fields and "R" not in fields


def test_row_identity_binds_all_four_contracts(binding):
    fields = binding["row_identity_fields"]
    for required in ("source_acquisition_protocol_sha256",
                     "target_v4_contract_sha256",
                     "recoverability_probabilistic_target_v3_sha256",
                     "recoverability_replica_protocol_v3_sha256",
                     "recoverability_row_binding_v3_spec_sha256"):
        assert required in fields, required
    bound = binding["bound_contracts"]
    assert bound["source_acquisition_protocol_sha256"] == FROZEN_ACQ
    assert bound["target_v4_contract_sha256"] == TV4


def test_R_is_bound_through_the_protocol_not_the_payload(binding):
    assert "replica_protocol_v3_sha256" in binding["R_binding"]
    assert binding["outcome_independence"].startswith("the row identity contains")


def test_v2_rows_cannot_masquerade_as_v3(binding):
    relation = binding["v2_row_identity_relation"]
    assert relation["collision_possible"] is False
    assert relation["v2_rows_may_masquerade_as_v3"] is False


def test_supervision_record_is_not_identity(binding):
    record = binding["F6_supervision_record"]
    assert record["is_scientific_identity"] is False
    assert record["canonical_observation"] == "(k, R)"
    assert record["k_over_R_is_descriptive_only"] is True
    for required in ("R", "k", "replica_target_v4_labels"):
        assert required in record["fields"]


def test_replica_identity_may_carry_replica_index(binding):
    provenance = binding["F5_event_and_candidate_provenance"]
    assert provenance["candidate_event_identity"]["outcome_independent"] is True
    assert "replica_index" in provenance["replica_evaluation_identity"]["fields"]
    assert provenance["replica_evaluation_identity"]["outcome_independent"] is True


# --------------------------------------------------------------------------
# F7 loss contract
# --------------------------------------------------------------------------
def test_loss_divides_by_R(readiness):
    loss = load("phase9d_v3f_training_loss_contract_v1.json")
    assert loss["candidate_term"]["division_by_R"] == "MANDATORY"
    assert "/ R" in loss["candidate_term"]["formula"]


def test_loss_reduces_to_bce_at_R1():
    loss = load("phase9d_v3f_training_loss_contract_v1.json")
    assert "Bernoulli BCE" in loss["candidate_term"]["R1_reduction"]
    assert loss["relation_to_frozen_loss_contract"]["contradiction"] is False
    assert loss["relation_to_frozen_loss_contract"][
        "v3_relation"].startswith("GENERALIZATION")


def test_every_worked_example_carries_unit_event_weight():
    loss = load("phase9d_v3f_training_loss_contract_v1.json")
    examples = loss["worked_examples"]
    assert {(e["team_size"], e["R"]) for e in examples} == {
        (5, 1), (16, 1), (5, 3), (16, 3)}
    for example in examples:
        assert example["total_event_weight"] == 1.0
        assert example["step_3_event_weight"] == 1.0


def test_worked_example_losses_recompute():
    loss = load("phase9d_v3f_training_loss_contract_v1.json")
    for example in loss["worked_examples"]:
        p, k, r = example["p_hat"], example["k"], example["R"]
        expected = -(k * math.log(p) + (r - k) * math.log(1 - p)) / r
        assert example["per_candidate_loss_before_aggregation"] == pytest.approx(
            expected, abs=1e-9)


def test_N_and_R_invariance_are_proved():
    proofs = load("phase9d_v3f_training_loss_contract_v1.json")["invariance_proofs"]
    for key in ("N_invariance", "R_invariance"):
        assert proofs[key]["verified_in_worked_examples"] is True
        assert proofs[key]["proof"]


def test_class_weighting_is_none():
    loss = load("phase9d_v3f_training_loss_contract_v1.json")
    assert loss["class_weighting"] == "NONE"
    assert loss["positive_class_weight"] == "NONE"
    assert loss["stochastic_family_reweighting"] == "NONE"
    assert loss["f9_upweighting"] == "NONE"
    assert loss["implemented"] is False


# --------------------------------------------------------------------------
# F8 Brier
# --------------------------------------------------------------------------
def test_brier_is_replica_normalized_and_event_equal():
    brier = load("phase9d_v3f_brier_metric_contract_v1.json")
    assert "(1/R)" in brier["candidate_formula"]
    assert brier["replica_normalization"].startswith("MANDATORY")
    assert brier["raw_row_mean_permitted"] is False
    assert len(brier["aggregation_order"]) == 5


def test_brier_does_not_outrank_task_success():
    authority = load("phase9d_v3f_brier_metric_contract_v1.json")["authority"]
    assert authority["brier_does_not_outrank_task_success"] is True
    assert authority["lexicographic_position"] == 3
    actual = hashlib.sha256(
        (ROOT / "docs/RVT_CHECKPOINT_SELECTION_CONTRACT.md").read_bytes()
    ).hexdigest()
    assert authority["checkpoint_contract_sha256"] == actual


def test_calibration_is_not_the_h1_headline():
    brier = load("phase9d_v3f_brier_metric_contract_v1.json")
    assert brier["calibration_is_not_the_h1_headline"] is True
    assert "episode task success" in brier["h1_headline_remains"]


# --------------------------------------------------------------------------
# F10 split registry
# --------------------------------------------------------------------------
def test_only_authorized_offsets_are_used():
    registry = load("phase9d_v3f_layout_split_registry_v1.json")
    assert registry["authorized_offsets"] == [0.54, 0.65]
    used = {entry["offset"] for entry in registry["assignment"]}
    assert used == {0.54, 0.65}
    assert "0.76" in registry["forbidden_offsets"]


def test_frozen_v2_scenario_code_is_not_modified():
    registry = load("phase9d_v3f_layout_split_registry_v1.json")
    assert registry["frozen_v2_scenario_code_modified"] is False
    assert registry["generator_unchanged"] is True
    assert registry["additive"] is True
    actual = hashlib.sha256(
        (ROOT / "rvt_swarm/phase8/scenario.py").read_bytes()).hexdigest()
    assert registry["generator_sha256"] == actual


def test_capacity_shortfall_is_declared_not_papered_over():
    finding = load("phase9d_v3f_layout_split_registry_v1.json")["CAPACITY_FINDING"]
    assert finding["total_fresh_layouts_available"] == 20
    assert finding["split_task_nominal_request"]["total"] == 30
    assert finding["shortfall"] == 10
    assert finding["mapping_invented_to_close_the_gap"] is False
    assert finding["declared_consequence"]
    assert finding["owner_option_not_exercised"]["status"].startswith(
        "NOT AUTHORIZED")


def test_layout_id_naming_hazard_is_recorded():
    hazard = load("phase9d_v3f_layout_split_registry_v1.json")["NAMING_HAZARD"]
    assert "never be used to infer" in hazard["rule"]


def test_offsets_recompute_from_the_generator_formula():
    registry = load("phase9d_v3f_layout_split_registry_v1.json")
    base = registry["generator_split_offsets"]["validation"]
    for entry in registry["assignment"]:
        assert entry["offset"] == pytest.approx(
            base + 0.11 * entry["variant_index"], abs=1e-9)


# --------------------------------------------------------------------------
# F11/F12 dry manifests
# --------------------------------------------------------------------------
def test_train_manifest_is_1200_dry_episodes(train):
    assert train["source_episodes"] == 1200
    assert len(train["episodes"]) == 1200
    assert train["maximum_selected_source_events"] == 6000
    assert train["status"].startswith("DRY_FROZEN")
    assert train["generated"] == 0 and train["executed"] == 0 and train["rows"] == 0


def test_validation_manifest_is_300_dry_episodes(validation):
    assert validation["source_episodes"] == 300
    assert len(validation["episodes"]) == 300
    assert validation["maximum_selected_source_events"] == 1500
    assert validation["generated"] == 0


@pytest.mark.parametrize("name", ["phase9d_v3f_train_manifest_dry_v1.json",
                                  "phase9d_v3f_validation_manifest_dry_v1.json"])
def test_manifests_cover_the_full_domain(name):
    manifest = load(name)
    assert manifest["families"] == FAMILIES
    assert manifest["team_sizes"] == list(STUDY_A_TRAINING_SIZES)
    assert len(manifest["source_policies"]) == 6
    assert set(manifest["family_counts"].values()) == {
        manifest["source_episodes"] // 10}
    assert 24 not in manifest["team_sizes"]


@pytest.mark.parametrize("name", ["phase9d_v3f_train_manifest_dry_v1.json",
                                  "phase9d_v3f_validation_manifest_dry_v1.json"])
def test_manifests_bind_every_frozen_contract(name):
    manifest = load(name)
    assert manifest["source_acquisition_protocol_sha256"] == FROZEN_ACQ
    assert manifest["target_v4_contract_sha256"] == TV4
    assert manifest["K"] == 5
    for key in ("recoverability_probabilistic_target_v3_sha256",
                "recoverability_replica_protocol_v3_sha256",
                "recoverability_row_binding_v3_spec_sha256",
                "v3_layout_split_registry_sha256"):
        assert len(manifest[key]) == 64


@pytest.mark.parametrize("name", ["phase9d_v3f_train_manifest_dry_v1.json",
                                  "phase9d_v3f_validation_manifest_dry_v1.json"])
def test_episode_identities_are_unique_and_carry_an_explicit_split(name):
    manifest = load(name)
    episodes = manifest["episodes"]
    assert len({e["episode_id"] for e in episodes}) == len(episodes)
    for episode in episodes:
        assert episode["v3_split"] == manifest["v3_split"]
        assert episode["generator_split_namespace"] == "validation"
        assert set(episode["seeds"]) == {"initial_condition", "communication",
                                         "dynamic_obstacle", "data_sampling"}


@pytest.mark.parametrize("name", ["phase9d_v3f_train_manifest_dry_v1.json",
                                  "phase9d_v3f_validation_manifest_dry_v1.json"])
def test_replica_plan_matches_the_frozen_protocol(name):
    manifest = load(name)
    for episode in manifest["episodes"]:
        assert episode["replicas_per_candidate"] == replica_count_for_family(
            episode["family"])
    plan = manifest["replica_plan"]
    assert plan["episodes_with_R3"] + plan["episodes_with_R1"] == (
        manifest["source_episodes"])
    assert plan["episodes_with_R3"] == manifest["source_episodes"] * 2 // 10


def test_no_replenishment_or_outcome_dependent_stopping(train, validation):
    for manifest in (train, validation):
        assert manifest["replenishment_permitted"] is False
        assert manifest["outcome_dependent_stopping_permitted"] is False
        assert manifest["maximum_is_a_cap_not_a_target"] is True


# --------------------------------------------------------------------------
# F13/F14 disjointness
# --------------------------------------------------------------------------
def test_every_disjointness_axis_is_zero():
    audit = load("phase9d_v3f_disjointness_audit_v1.json")
    assert audit["all_disjoint"] is True
    assert audit["axes_with_nonzero_overlap"] == []
    assert audit["total_axes"] >= 15
    for axis in audit["axes"]:
        assert axis["overlap"] == 0, axis["axis"]


def test_final_domain_proved_without_enumeration():
    sealed = load("phase9d_v3f_disjointness_audit_v1.json")["sealed_final_domain"]
    assert sealed["final_test_identities_inspected"] == 0
    assert sealed["final_test_enumerated"] is False
    assert sealed["final_identities_revealed"] is False
    assert "PermissionError" in sealed["proof_mechanism"]


def test_exclusion_union_intersections_are_zero():
    union = load("phase9d_v3f_exclusion_union_v1.json")
    assert union["v3_train_intersection"] == 0
    assert union["v3_validation_intersection"] == 0
    assert union["v3_train_vs_v3_validation_intersection"] == 0
    assert union["requirement_met"] is True
    assert union["excluded_identity_count"] > 1500


# --------------------------------------------------------------------------
# F15 budget
# --------------------------------------------------------------------------
def test_budget_is_caps_only_and_planning_only():
    budget = load("phase9d_v3f_compute_budget_v1.json")
    assert budget["planning_only"] is True
    assert budget["generation_performed"] == 0
    assert "caps only" in budget["method"]
    assert budget["assumptions"]


def test_budget_replica_caps_reconcile():
    budget = load("phase9d_v3f_compute_budget_v1.json")
    for key in ("v3_train", "v3_validation"):
        plan = budget[key]
        assert plan["maximum_selected_events"] == plan["source_episodes"] * 5
        assert plan["maximum_candidate_aggregates"] == (
            plan["maximum_selected_events"] * 2)
        expected = (plan["maximum_selected_events_from_R1_families"] * 2 * 1
                    + plan["maximum_selected_events_from_R3_families"] * 2 * 3)
        assert plan["maximum_candidate_replica_rollouts"] == expected


# --------------------------------------------------------------------------
# F16-F21 closure
# --------------------------------------------------------------------------
def test_no_v3_data_was_generated(readiness):
    generation = readiness["F16_no_data_generation"]
    for key in ("v3_source_episodes_executed", "v3_selected_states_generated",
                "v3_candidate_rollouts", "v3_scientific_rows"):
        assert generation[key] == 0, key
    assert generation["artifacts_are_dry_manifests_and_contracts_only"] is True


def test_implementation_requirements_are_additive_and_unimplemented():
    requirements = load("phase9d_v3f_implementation_requirements_v1.json")
    assert requirements["implemented_in_this_phase"] == 0
    assert requirements["all_capabilities_must_be_additive"] is True
    assert requirements["v2_replay_must_remain_byte_identical"] is True
    assert len(requirements["capabilities"]) == 9


def test_qualification_ladder_precedes_generation():
    plan = load("phase9d_v3f_qualification_plan_v1.json")
    assert plan["no_official_v3_generation_before_all_required_qualification_closes"]
    assert [step["step"] for step in plan["ladder"]] == list(range(1, 10))


def test_fresh_validation_outcomes_are_protected():
    protection = load("phase9d_v3f_qualification_plan_v1.json")[
        "F20_fresh_validation_protection"]
    assert protection["v3_validation_identity_pool_frozen_now"] is True
    assert protection["qualification_must_use_dedicated_canary_identities"] is True
    assert protection[
        "canary_identities_must_be_disjoint_from_both_v3_manifests"] is True
    assert len(protection["outcomes_must_not_be_inspected_during"]) >= 4


def test_publication_provenance_does_not_hide_v2():
    provenance = load("phase9d_v3f_publication_provenance_v1.json")
    assert provenance["v2_failure_hidden"] is False
    stages = provenance["narrative_chain"]
    assert len(stages) == 7
    failure = next(s for s in stages if s["stage"] == 3)
    assert "59/530" in failure["value"]
    assert failure["must_be_reported"] is True


def test_sealed_domains_all_zero(readiness):
    for key, value in readiness["sealed_domains"].items():
        assert value == 0, key


def test_final_verdict_and_recommendation(readiness):
    assert readiness["verdict"] == "A"
    assert readiness["recommendation"] == (
        "AUTHORIZE_RECOVERABILITY_V3_IMPLEMENTATION_AND_QUALIFICATION")
    assert readiness["not_authorized_by_this_verdict"] == "DATA GENERATION"
    assert readiness["h1_owner_rewording_required"] is False


def test_readiness_records_the_declared_consequence(readiness):
    consequence = readiness["declared_consequence"]
    assert consequence["v2_train_layouts"] == 20
    assert consequence["v3_train_layouts"] == 10
    assert consequence["affects_held_out_property"] is False
    assert consequence["owner_option_recorded"] is True
