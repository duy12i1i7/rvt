"""Phase 9D-V3F-L -- prospective V3 layout-capacity addendum and freeze closure.

Read-only tests over the amended layout objects. They also preserve the
historical V2 record and the already-frozen non-layout V3 science: nothing here
may change a scientific contract hash or contradict the gate-7 failure pin.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from rvt_swarm.phase8.common import sha256_document, verify_canonical_hash
from rvt_swarm.phase8.scenario import _SPLIT_OFFSETS, _SPLIT_VARIANTS

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results" / "rvt_fd24"

GATE7_THRESHOLD = 0.10
V2_FAILING = (59, 530)
FAMILIES = ["F%d" % index for index in range(1, 11)]

FROZEN_NON_LAYOUT = {
    "phase9d_v3f_probabilistic_target_contract_v1.json": (
        "recoverability_probabilistic_target_v3_sha256",
        "a127bf9fbe907c81f2cd8037e94164f738ee756d7480c7db6955d7405bc355b6"),
    "phase9d_v3f_replica_protocol_v1.json": (
        "recoverability_replica_protocol_v3_sha256",
        "6c2143c4782f0d851205cb118a2ff1c3e33c8a6a3e3cdc2ce5a820106551fa9a"),
    "phase9d_v3f_row_binding_v1.json": (
        "recoverability_row_binding_v3_spec_sha256",
        "bdab65bdabbf503dc4d76d7d66d14c6504feb657b32d153a89643fab55058a8c"),
    "phase9d_v3f_training_loss_contract_v1.json": (
        "recoverability_training_loss_v3_sha256",
        "fc9c093327eaaa5ae95c038cf36a2a16ff2fee6d5fdc125dd1106bc3a99dfc11"),
    "phase9d_v3f_brier_metric_contract_v1.json": (
        "recoverability_brier_metric_v3_sha256",
        "0bf6dee325825953d856fb4f6b5df190879424b0d5e8d29cbe55ac930f682f04"),
}

ARTIFACTS = [
    "phase9d_v3f_l_owner_layout_addendum_v1.json",
    "phase9d_v3f_l_layout_split_registry_v2.json",
    "phase9d_v3f_l_train_layout_set_final_v1.json",
    "phase9d_v3f_l_validation_layout_set_final_v1.json",
    "phase9d_v3f_l_train_manifest_dry_final_v1.json",
    "phase9d_v3f_l_validation_manifest_dry_final_v1.json",
    "phase9d_v3f_l_disjointness_final_v1.json",
    "phase9d_v3f_l_exclusion_union_final_v1.json",
    "phase9d_v3f_l_compute_budget_final_v1.json",
    "phase9d_v3f_l_contract_impact_v1.json",
    "phase9d_v3f_l_implementation_handoff_v1.json",
    "phase9d_v3f_l_final_readiness_v1.json",
]


def load(name):
    return json.loads((RESULTS / name).read_text(encoding="ascii"))


def hash_field(document):
    return next(key for key in document
                if key.startswith("phase9d_v3f_l_") and key.endswith("sha256"))


@pytest.fixture(scope="module")
def registry():
    return load("phase9d_v3f_l_layout_split_registry_v2.json")


@pytest.fixture(scope="module")
def train():
    return load("phase9d_v3f_l_train_manifest_dry_final_v1.json")


@pytest.fixture(scope="module")
def validation():
    return load("phase9d_v3f_l_validation_manifest_dry_final_v1.json")


@pytest.fixture(scope="module")
def readiness():
    return load("phase9d_v3f_l_final_readiness_v1.json")


# --------------------------------------------------------------------------
# artifacts
# --------------------------------------------------------------------------
@pytest.mark.parametrize("name", ARTIFACTS)
def test_artifact_exists_and_self_verifies(name):
    document = load(name)
    assert verify_canonical_hash(document, hash_field(document)), name


def test_all_twelve_required_artifacts_exist():
    assert len(sorted(RESULTS.glob("phase9d_v3f_l_*.json"))) == 12


# --------------------------------------------------------------------------
# L1 non-layout science must not move
# --------------------------------------------------------------------------
@pytest.mark.parametrize("name,field,expected", [
    (name, field, expected)
    for name, (field, expected) in FROZEN_NON_LAYOUT.items()])
def test_non_layout_contract_hashes_unchanged(name, field, expected):
    document = load(name)
    assert document[field] == expected, name
    assert verify_canonical_hash(
        document, next(k for k in document
                       if k.startswith("phase9d_v3f_") and k.endswith("sha256")))


def test_contract_impact_declares_no_non_layout_change():
    impact = load("phase9d_v3f_l_contract_impact_v1.json")
    assert impact["any_non_layout_contract_changed"] is False
    unchanged = impact["unchanged_scientific_contracts"]
    for name, (field, expected) in FROZEN_NON_LAYOUT.items():
        assert unchanged[field] == expected
    assert unchanged["source_acquisition_protocol_sha256"] == (
        "19fa68a37d80f16ee1463b872f26402963daeb5a56f375423634a90dc1f3546d")
    assert unchanged["target_v4_contract_sha256"] == (
        "54a0e0baff79fbdc320800b772f47a40ac06ac4f0e70d4fab1bf676c54b918ee")


def test_row_binding_does_not_embed_the_layout_registry_hash():
    analysis = load("phase9d_v3f_l_contract_impact_v1.json")["row_binding_analysis"]
    assert analysis["embeds_layout_registry_hash"] is False
    assert analysis["embeds_layout_sha256"] is True
    assert analysis["guessed"] is False
    live = load("phase9d_v3f_row_binding_v1.json")["row_identity_fields"]
    assert analysis["row_identity_fields"] == live
    assert not any("registry" in field for field in live)


def test_v2_gate7_failure_unchanged():
    gate7 = load("phase9d_v2c_r_gate7_replica_instability_v1.json")
    assert verify_canonical_hash(
        gate7, "phase9d_v2c_r_gate7_replica_instability_sha256")
    assert gate7["result"] == "FAIL"
    assert gate7["threshold"] == GATE7_THRESHOLD
    unstable, total = V2_FAILING
    assert unstable / total > GATE7_THRESHOLD


def test_v2_seals_unchanged(readiness):
    preservation = readiness["L1_preservation"]
    assert preservation["non_layout_contracts_changed"] == 0
    assert preservation["v2_train_seal_unchanged"] is True
    assert preservation["v2_validation_seal_unchanged"] is True
    assert preservation["gate7_still_exceeds_threshold"] is True
    assert preservation["gate7_modified"] is False


# --------------------------------------------------------------------------
# L2 offset 0.22 authority
# --------------------------------------------------------------------------
def test_offset_022_is_the_unused_train_variant_two():
    authority = load("phase9d_v3f_l_train_layout_set_final_v1.json")[
        "offset_authority"]
    assert authority["offset"] == 0.22
    assert authority["generator_coordinate"] == {
        "generator_split_namespace": "train", "variant_index": 2}
    assert authority["variant_2_in_frozen_train_tuple"] is False
    assert 2 not in _SPLIT_VARIANTS["train"]
    assert _SPLIT_OFFSETS["train"] + 0.11 * 2 == pytest.approx(0.22, abs=1e-9)


def test_offset_022_is_unused_everywhere_that_matters():
    authority = load("phase9d_v3f_l_train_layout_set_final_v1.json")[
        "offset_authority"]
    for key in ("unused_by_v2_official_train", "unused_by_v2_official_validation",
                "unused_by_design_pilots", "unused_by_qualification_canaries",
                "unused_by_v3d_design_diagnostics"):
        assert authority[key] is True, key
    assert authority["is_a_final_test_variant"] is False
    assert authority["is_study_a_n24"] is False
    assert authority["is_study_b"] is False


def test_offset_022_geometry_is_disjoint_from_everything():
    disjoint = load("phase9d_v3f_l_train_layout_set_final_v1.json")[
        "offset_authority"]["geometry_disjointness"]
    for key, value in disjoint.items():
        assert value == 0, key


def test_offset_022_authority_was_recomputed_not_quoted():
    authority = load("phase9d_v3f_l_train_layout_set_final_v1.json")[
        "offset_authority"]
    assert "not from V3F prose" in authority["evidence_source"]
    actual = hashlib.sha256(
        (ROOT / "rvt_swarm/phase8/scenario.py").read_bytes()).hexdigest()
    assert authority["generator_sha256"] == actual


def test_only_metadata_was_materialized():
    metadata = load("phase9d_v3f_l_train_layout_set_final_v1.json")[
        "offset_authority"]["L3_metadata_only"]
    assert metadata["layout_definitions_materialized"] is True
    for key in ("source_policy_rollouts", "candidate_rollouts",
                "target_v4_evaluations", "outcomes_generated"):
        assert metadata[key] == 0, key


# --------------------------------------------------------------------------
# L4/L5 final layout sets
# --------------------------------------------------------------------------
def test_train_has_exactly_twenty_unique_layouts():
    layouts = load("phase9d_v3f_l_train_layout_set_final_v1.json")
    assert layouts["layout_count"] == 20
    assert layouts["unique_layout_ids"] == 20
    assert layouts["unique_layout_sha256"] == 20
    assert layouts["unique_geometry_sha256"] == 20
    assert layouts["count_matches_expected"] is True
    assert layouts["no_duplicate_geometry_under_different_ids"] is True
    assert set(layouts["layouts_per_family"].values()) == {2}


def test_validation_has_exactly_ten_unique_layouts():
    layouts = load("phase9d_v3f_l_validation_layout_set_final_v1.json")
    assert layouts["layout_count"] == 10
    assert layouts["unique_layout_ids"] == 10
    assert layouts["unique_geometry_sha256"] == 10
    assert layouts["changed_by_this_addendum"] is False
    assert set(layouts["layouts_per_family"].values()) == {1}


def test_train_set_is_exactly_the_two_authorized_offsets():
    layouts = load("phase9d_v3f_l_train_layout_set_final_v1.json")["layouts"]
    assert {row["offset"] for row in layouts} == {0.22, 0.54}
    assert sum(1 for row in layouts if row["offset"] == 0.22) == 10
    assert sum(1 for row in layouts if row["offset"] == 0.54) == 10


def test_validation_set_is_exactly_offset_065():
    layouts = load("phase9d_v3f_l_validation_layout_set_final_v1.json")["layouts"]
    assert {row["offset"] for row in layouts} == {0.65}


# --------------------------------------------------------------------------
# L6/L7 reserve and forbidden
# --------------------------------------------------------------------------
def test_offset_033_is_reserve_and_absent_from_both_splits(registry):
    reserve = registry["assignment"]["RESERVE"]
    assert reserve["offsets"] == [0.33]
    assert reserve["official_train_membership"] == 0
    assert reserve["official_validation_membership"] == 0
    assert "UNUSED_RESERVE" in reserve["rule"]
    train_ids = set(registry["assignment"]["TRAIN"]["layout_ids"])
    validation_ids = set(registry["assignment"]["VALIDATION"]["layout_ids"])
    reserve_ids = set(reserve["layout_ids"])
    assert not (train_ids & reserve_ids)
    assert not (validation_ids & reserve_ids)


def test_near_final_variant_remains_forbidden(registry):
    forbidden = registry["assignment"]["FORBIDDEN"]
    assert 0.76 in forbidden["offsets"]
    assert forbidden["official_v3_membership"] == 0
    assert forbidden["final_identities_enumerated"] == 0
    used = set(registry["assignment"]["TRAIN"]["offsets"]) | set(
        registry["assignment"]["VALIDATION"]["offsets"])
    assert not (used & set(forbidden["offsets"]))


# --------------------------------------------------------------------------
# L8 split is never inferred from layout_id
# --------------------------------------------------------------------------
def test_split_authority_rule_is_frozen(registry):
    rule = registry["L8_split_authority_rule"]
    assert "layout_id prefix" in rule["split_is_never_determined_by"]
    assert "layout_id substring" in rule["split_is_never_determined_by"]
    assert "manifest identity" in rule["split_is_determined_by"]
    assert "layout registry membership" in rule["split_is_determined_by"]


def test_train_really_contains_a_validation_named_layout(registry):
    """The hazard is real, not hypothetical: TRAIN mixes both namespaces."""
    train_ids = registry["assignment"]["TRAIN"]["layout_ids"]
    assert any(layout_id.startswith("validation-") for layout_id in train_ids)
    assert any(layout_id.startswith("train-") for layout_id in train_ids)


def test_a_validation_named_train_layout_stays_train_through_the_contract(
        registry, train, validation):
    """Regression for L8: pick the worst-case layout -- a TRAIN layout whose
    historical id begins with 'validation-' -- and prove every authoritative
    path still classifies it as TRAIN, while naive string parsing does not."""
    trap = next(layout_id for layout_id in registry["assignment"]["TRAIN"]
                ["layout_ids"] if layout_id.startswith("validation-"))

    # naive string inference would get this wrong
    naive_split = "validation" if "validation" in trap else "train"
    assert naive_split == "validation"

    # registry membership is authoritative and says TRAIN
    assert trap in set(registry["assignment"]["TRAIN"]["layout_ids"])
    assert trap not in set(registry["assignment"]["VALIDATION"]["layout_ids"])

    # every manifest episode on that layout declares v3_split explicitly
    episodes = [e for e in train["episodes"] if e["layout_id"] == trap]
    assert episodes
    for episode in episodes:
        assert episode["v3_split"] == "v3_train"
        assert episode["v3_split"] != naive_split
        assert episode["generator_split_namespace"] == "validation"
        assert "/v3_train/" in episode["episode_id"]

    # and it never appears anywhere in the VALIDATION manifest
    assert not any(e["layout_id"] == trap for e in validation["episodes"])


def test_generator_namespace_is_recorded_but_not_authoritative(train):
    namespaces = {e["generator_split_namespace"] for e in train["episodes"]}
    assert namespaces == {"train", "validation"}
    assert {e["v3_split"] for e in train["episodes"]} == {"v3_train"}


# --------------------------------------------------------------------------
# L9 registry supersession
# --------------------------------------------------------------------------
def test_old_registry_is_marked_superseded_not_deleted(registry):
    superseded = registry["supersedes"]
    assert superseded["sha256"] == (
        "d84d0fb9699dad7d6fe4783d2bd55e1b644ed027948291aeb75148e88ea54dae")
    assert superseded["status"] == "SUPERSEDED_PRE_GENERATION_CAPACITY_VERSION"
    assert superseded["preserved"] is True
    assert superseded["deleted"] is False
    assert superseded["rewritten_in_place"] is False


def test_the_superseded_registry_artifact_still_exists_and_verifies():
    old = load("phase9d_v3f_layout_split_registry_v1.json")
    assert verify_canonical_hash(old, "phase9d_v3f_layout_split_registry_sha256")
    assert old["v3_layout_split_registry_sha256"] == (
        "d84d0fb9699dad7d6fe4783d2bd55e1b644ed027948291aeb75148e88ea54dae")


def test_frozen_v2_scenario_code_is_untouched(registry):
    assert registry["frozen_v2_scenario_code_modified"] is False
    assert registry["generator_unchanged"] is True
    assert registry["additive"] is True
    actual = hashlib.sha256(
        (ROOT / "rvt_swarm/phase8/scenario.py").read_bytes()).hexdigest()
    assert registry["generator_sha256"] == actual


def test_registry_offsets_recompute_from_the_generator_formula(registry):
    offsets = registry["generator_split_offsets"]
    assert offsets["train"] + 0.11 * 2 == pytest.approx(0.22, abs=1e-9)
    assert offsets["validation"] + 0.11 * 1 == pytest.approx(0.54, abs=1e-9)
    assert offsets["validation"] + 0.11 * 2 == pytest.approx(0.65, abs=1e-9)
    assert offsets["train"] + 0.11 * 3 == pytest.approx(0.33, abs=1e-9)


# --------------------------------------------------------------------------
# L10/L11 manifests
# --------------------------------------------------------------------------
def test_train_manifest_restores_the_intended_design(train):
    assert train["source_episodes"] == 1200
    assert len(train["episodes"]) == 1200
    assert train["layout_count"] == 20
    assert train["episodes_per_layout_min"] == 60
    assert train["episodes_per_layout_max"] == 60
    assert train["episodes_per_layout_mean"] == 60.0
    assert train["episodes_per_layout_uniform"] is True
    assert train["maximum_selected_source_events"] == 6000


def test_validation_manifest_unchanged_in_shape(validation):
    assert validation["source_episodes"] == 300
    assert validation["layout_count"] == 10
    assert validation["episodes_per_layout_mean"] == 30.0
    assert validation["episodes_per_layout_uniform"] is True
    assert validation["maximum_selected_source_events"] == 1500


@pytest.mark.parametrize("name", [
    "phase9d_v3f_l_train_manifest_dry_final_v1.json",
    "phase9d_v3f_l_validation_manifest_dry_final_v1.json"])
def test_manifests_are_dry_and_bind_the_frozen_contracts(name):
    manifest = load(name)
    assert manifest["status"].startswith("DRY_FROZEN")
    assert manifest["generated"] == 0
    assert manifest["executed"] == 0
    assert manifest["rows"] == 0
    assert manifest["families"] == FAMILIES
    assert manifest["K"] == 5
    assert manifest["recoverability_probabilistic_target_v3_sha256"] == (
        FROZEN_NON_LAYOUT["phase9d_v3f_probabilistic_target_contract_v1.json"][1])
    assert manifest["recoverability_replica_protocol_v3_sha256"] == (
        FROZEN_NON_LAYOUT["phase9d_v3f_replica_protocol_v1.json"][1])
    assert manifest["recoverability_row_binding_v3_spec_sha256"] == (
        FROZEN_NON_LAYOUT["phase9d_v3f_row_binding_v1.json"][1])


@pytest.mark.parametrize("name", [
    "phase9d_v3f_l_train_manifest_dry_final_v1.json",
    "phase9d_v3f_l_validation_manifest_dry_final_v1.json"])
def test_manifests_cite_the_new_registry_root(name):
    manifest = load(name)
    registry = load("phase9d_v3f_l_layout_split_registry_v2.json")
    assert manifest["v3_layout_split_registry_v2_sha256"] == (
        registry["v3_layout_split_registry_v2_sha256"])


@pytest.mark.parametrize("name", [
    "phase9d_v3f_l_train_manifest_dry_final_v1.json",
    "phase9d_v3f_l_validation_manifest_dry_final_v1.json"])
def test_manifest_episode_identities_are_unique(name):
    episodes = load(name)["episodes"]
    assert len({e["episode_id"] for e in episodes}) == len(episodes)


def test_replica_plan_is_unchanged_by_the_layout_amendment(train, validation):
    assert train["replica_plan"]["episodes_with_R3"] == 240
    assert validation["replica_plan"]["episodes_with_R3"] == 60


# --------------------------------------------------------------------------
# L12/L13 disjointness and union
# --------------------------------------------------------------------------
def test_every_disjointness_axis_is_zero():
    audit = load("phase9d_v3f_l_disjointness_final_v1.json")
    assert audit["all_disjoint"] is True
    assert audit["axes_with_nonzero_overlap"] == []
    assert audit["total_axes"] >= 19
    for axis in audit["axes"]:
        assert axis["overlap"] == 0, axis["axis"]


def test_the_audit_is_stronger_than_the_previous_one():
    stronger = load("phase9d_v3f_l_disjointness_final_v1.json")[
        "stronger_than_previous_audit"]
    assert stronger["current_axes"] > stronger["previous_axes"]
    assert stronger["added"]


def test_reserve_offset_is_explicitly_excluded_by_the_audit():
    axes = load("phase9d_v3f_l_disjointness_final_v1.json")["axes"]
    reserve_axes = [a for a in axes if "RESERVE" in a["axis"]]
    assert len(reserve_axes) == 2
    for axis in reserve_axes:
        assert axis["overlap"] == 0


def test_final_domain_never_enumerated():
    sealed = load("phase9d_v3f_l_disjointness_final_v1.json")["sealed_final_domain"]
    assert sealed["final_test_identities_enumerated"] == 0
    assert sealed["final_test_outcomes_inspected"] == 0
    assert sealed["near_final_variant_official_v3_membership"] == 0


def test_exclusion_union_membership_is_unchanged():
    union = load("phase9d_v3f_l_exclusion_union_final_v1.json")
    assert union["membership_changed_from_v1"] is False
    assert union["excluded_identity_count"] == union["supersedes"]["identities"]
    assert "no development identity was added or removed" in (
        union["difference_reason"])
    assert union["supersedes"]["preserved"] is True


def test_exclusion_union_intersections_are_zero():
    union = load("phase9d_v3f_l_exclusion_union_final_v1.json")
    assert union["v3_train_intersection"] == 0
    assert union["v3_validation_intersection"] == 0
    assert union["v3_train_vs_v3_validation_intersection"] == 0
    assert union["requirement_met"] is True


# --------------------------------------------------------------------------
# L14/L15 budget
# --------------------------------------------------------------------------
def test_planned_scientific_budget_is_identical():
    budget = load("phase9d_v3f_l_compute_budget_final_v1.json")
    assert budget["planned_total_unchanged"] is True
    assert budget["combined"]["maximum_candidate_replica_rollouts"] == 21000
    assert budget["previous_planned_total_replica_rollouts"] == 21000
    assert budget["why_unchanged"]


def test_layout_diversity_did_not_change_operational_parameters():
    budget = load("phase9d_v3f_l_compute_budget_final_v1.json")
    assert budget["layout_diversity_used_to_change_operational_parameters"] is False
    parameters = budget["operational_parameters_unchanged"]
    assert parameters["workers"] == 12
    assert parameters["infrastructure_timeout_seconds"] == 243.0
    assert parameters["replica_counts"] == {"F8": 3, "F9": 3, "others": 1}
    assert parameters["source_budget"] == {"train": 1200, "validation": 300}


def test_budget_caps_reconcile():
    budget = load("phase9d_v3f_l_compute_budget_final_v1.json")
    for key in ("v3_train", "v3_validation"):
        plan = budget[key]
        assert plan["maximum_selected_events"] == plan["source_episodes"] * 5
        assert plan["maximum_candidate_aggregates"] == (
            plan["maximum_selected_events"] * 2)
        expected = plan["episodes_R1"] * 5 * 2 + plan["episodes_R3"] * 5 * 2 * 3
        assert plan["maximum_candidate_replica_rollouts"] == expected
    assert budget["generation_performed"] == 0


# --------------------------------------------------------------------------
# L17/L18/L19 closure
# --------------------------------------------------------------------------
def test_h1_is_untouched():
    h1 = load("phase9d_v3f_l_contract_impact_v1.json")["L17_h1"]
    assert h1["h1_owner_rewording_required"] is False
    assert h1["h1_altered_by_layout_diversity"] is False
    assert h1["primary_metric_unchanged"] is True
    assert h1["comparator_set_unchanged"] is True
    assert h1["effect_threshold_unchanged"] is True


def test_no_v3_execution_occurred(readiness):
    outcome = readiness["L18_no_outcome_access"]
    for key in ("v3_source_episodes_executed", "v3_selected_source_events",
                "v3_target_v4_evaluations", "v3_replica_rollouts",
                "v3_scientific_rows", "v3_labels_observed"):
        assert outcome[key] == 0, key
    assert outcome["fully_prospective"] is True


def test_implementation_must_fail_closed_on_the_superseded_registry():
    handoff = load("phase9d_v3f_l_implementation_handoff_v1.json")
    assert handoff["implemented_in_this_phase"] == 0
    superseded = {item["sha256"] for item in handoff[
        "superseded_inputs_that_must_be_refused"] if "sha256" in item}
    assert "d84d0fb9699dad7d6fe4783d2bd55e1b644ed027948291aeb75148e88ea54dae" in (
        superseded)
    rule = handoff["fail_closed_requirement"]
    assert "refuse" in rule["rule"]
    assert "raise rather than warn" in rule["mechanism"]
    assert rule["must_not_silently_upgrade"] is True


def test_handoff_points_at_the_new_roots_only():
    handoff = load("phase9d_v3f_l_implementation_handoff_v1.json")
    inputs = handoff["authoritative_inputs_for_v3_implementation"]
    registry = load("phase9d_v3f_l_layout_split_registry_v2.json")
    assert inputs["layout_split_registry"]["sha256"] == (
        registry["v3_layout_split_registry_v2_sha256"])
    assert inputs["train_manifest"]["layouts"] == 20
    assert inputs["validation_manifest"]["layouts"] == 10


def test_split_authority_requirement_is_handed_off():
    requirement = load("phase9d_v3f_l_implementation_handoff_v1.json")[
        "split_authority_requirement"]
    assert "never parsed from layout_id" in requirement["rule"]
    assert "validation-f1-01" in requirement["worked_hazard"]


def test_owner_addendum_is_prospective_and_scoped():
    addendum = load("phase9d_v3f_l_owner_layout_addendum_v1.json")
    assert addendum["scope"] == (
        "LAYOUT_CAPACITY_ONLY -- no scientific target, replica, row, loss or "
        "metric decision is reopened")
    assert addendum["is_outcome_tuning"] is False
    assert addendum["prospective"] is True
    assert addendum["affects_scientific_budget"] is False
    assert addendum["affects_held_out_property"] is False
    assert addendum["previous_version_pretended_never_to_have_existed"] is False
    assert addendum["owner_decision"]["reserve_offsets"] == [0.33]


def test_sealed_domains_all_zero(readiness):
    for key, value in readiness["sealed_domains"].items():
        assert value == 0, key


def test_final_capacity_and_verdict(readiness):
    capacity = readiness["final_capacity"]
    assert capacity["v3_train_layouts"] == 20
    assert capacity["v3_validation_layouts"] == 10
    assert capacity["v3_train_offsets"] == [0.22, 0.54]
    assert capacity["v3_validation_offsets"] == [0.65]
    assert capacity["intended_design_restored"] is True
    assert readiness["verdict"] == "A"
    assert readiness["recommendation"] == (
        "AUTHORIZE_RECOVERABILITY_V3_IMPLEMENTATION_AND_QUALIFICATION")
    assert readiness["not_authorized"] == "V3 DATA GENERATION"
    assert readiness["compute_plan_unchanged"] is True
