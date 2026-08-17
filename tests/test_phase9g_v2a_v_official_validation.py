"""Phase 9G-V2A-V -- official Study-A Recoverability V2 VALIDATION closure.

These tests pin the committed VALIDATION artifacts against the frozen
contracts. They are read-only: no generation, no training, no sealed-domain
access.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rvt_swarm.phase8.common import verify_canonical_hash
from rvt_swarm.phase9d_h1r.acquisition_v2 import (
    DEFAULT_K,
    acquisition_protocol_v2_sha256,
    frozen_acquisition_protocol_v2,
    frozen_acquisition_protocol_v2_sha256,
    select_realized_trajectory_uniform_k,
)
from rvt_swarm.phase9g0r.contracts_v2 import (
    TARGET_V4_SHA256,
    recoverability_row_binding_v2_spec_sha256,
)

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results" / "rvt_fd24"

FROZEN_PROTOCOL = "19fa68a37d80f16ee1463b872f26402963daeb5a56f375423634a90dc1f3546d"
FROZEN_TARGET_V4 = "54a0e0baff79fbdc320800b772f47a40ac06ac4f0e70d4fab1bf676c54b918ee"
FROZEN_ROW_BINDING = "98f18a94c6a69d27a4cbf38169ca15e998ce4b4adfbba9a48cb1b3233391adf8"
QUALIFIED_IMAGE = (
    "sha256:2949628f6eb57abafe680687b677958c7cc52bffab84545514a48d84a936c684"
)
IMAGE_SOURCE_COMMIT = "f0a923f57fd8bea6b8249fad9652fcd37c674740"
TRAIN_SEAL = "a966f318832fb60bd99acdfdff72f0c7011d730f3e0fb51494ce318210f39bba"

ARTIFACT_HASH_FIELD = {
    "phase9g_v2a_v_comprehensive_exclusion_union_v1.json": (
        "official_v2_validation_comprehensive_exclusion_union_sha256"
    ),
    "phase9g_v2a_v_official_validation_manifest_v1.json": (
        "official_v2_validation_manifest_sha256"
    ),
    "phase9g_v2a_v_prelaunch_go_nogo_v1.json": (
        "official_v2_validation_prelaunch_sha256"
    ),
    "phase9g_v2a_v_official_validation_dataset_manifest_v1.json": (
        "dataset_manifest_sha256"
    ),
    "phase9g_v2a_v_official_validation_closure_v1.json": (
        "phase9g_v2a_v_official_validation_closure_sha256"
    ),
    "phase9g_v2a_v_stage_a_validation_ledger_v1.json": (
        "phase9g_v2a_v_stage_a_ledger_sha256"
    ),
    "phase9g_v2a_v_candidate_execution_ledger_v1.json": (
        "phase9g_v2a_v_candidate_execution_ledger_sha256"
    ),
    "phase9g_v2a_v_candidate_disposition_summary_v1.json": (
        "phase9g_v2a_v_candidate_disposition_summary_sha256"
    ),
    "phase9g_v2a_v_pair_transaction_ledger_v1.json": (
        "phase9g_v2a_v_pair_transaction_ledger_sha256"
    ),
    "phase9g_v2a_v_row_publication_audit_v1.json": (
        "phase9g_v2a_v_row_publication_audit_sha256"
    ),
    "phase9g_v2a_v_family_n_validation_audit_v1.json": (
        "phase9g_v2a_v_family_n_validation_audit_sha256"
    ),
    "phase9g_v2a_v_validation_adequacy_gate_v1.json": (
        "phase9g_v2a_v_validation_adequacy_gate_sha256"
    ),
    "phase9g_v2a_v_timeout_retry_ledger_v1.json": (
        "phase9g_v2a_v_timeout_retry_ledger_sha256"
    ),
    "phase9g_v2a_v_resume_idempotence_audit_v1.json": (
        "phase9g_v2a_v_resume_idempotence_audit_sha256"
    ),
    "phase9g_v2a_v_combined_audit_readiness_v1.json": (
        "phase9g_v2a_v_combined_audit_readiness_sha256"
    ),
}


def load(name: str):
    return json.loads((RESULTS / name).read_text(encoding="ascii"))


@pytest.fixture(scope="module")
def manifest():
    return load("phase9g_v2a_v_official_validation_manifest_v1.json")


@pytest.fixture(scope="module")
def closure():
    return load("phase9g_v2a_v_official_validation_closure_v1.json")


@pytest.fixture(scope="module")
def union():
    return load("phase9g_v2a_v_comprehensive_exclusion_union_v1.json")


@pytest.fixture(scope="module")
def dataset():
    return load("phase9g_v2a_v_official_validation_dataset_manifest_v1.json")


# --------------------------------------------------------------------------
# artifacts and canonical hashing
# --------------------------------------------------------------------------
@pytest.mark.parametrize("name", sorted(ARTIFACT_HASH_FIELD))
def test_artifact_exists_and_self_verifies(name):
    document = load(name)
    field = ARTIFACT_HASH_FIELD[name]
    assert verify_canonical_hash(document, field), name


@pytest.mark.parametrize("name", sorted(ARTIFACT_HASH_FIELD))
def test_artifact_hashes_are_full_64_hex(name):
    document = load(name)
    value = document[ARTIFACT_HASH_FIELD[name]]
    assert len(value) == 64 and set(value) <= set("0123456789abcdef")


# --------------------------------------------------------------------------
# V6 frozen manifest
# --------------------------------------------------------------------------
def test_manifest_is_exactly_300_validation_source_episodes(manifest):
    assert manifest["split"] == "validation"
    assert manifest["source_episodes"] == 300
    assert len(manifest["episodes"]) == 300


def test_manifest_binds_the_three_frozen_contracts(manifest):
    assert manifest["source_acquisition_protocol_sha256"] == FROZEN_PROTOCOL
    assert manifest["target_v4_contract_sha256"] == FROZEN_TARGET_V4
    assert manifest["recoverability_row_binding_v2_spec_sha256"] == FROZEN_ROW_BINDING


def test_manifest_contract_hashes_match_live_code(manifest):
    live = frozen_acquisition_protocol_v2_sha256(
        frozen_acquisition_protocol_v2(
            design_protocol_sha256=acquisition_protocol_v2_sha256()
        )
    )
    assert manifest["source_acquisition_protocol_sha256"] == live
    assert manifest["target_v4_contract_sha256"] == TARGET_V4_SHA256
    assert (
        manifest["recoverability_row_binding_v2_spec_sha256"]
        == recoverability_row_binding_v2_spec_sha256()
    )


def test_manifest_pins_the_qualified_image(manifest):
    assert manifest["qualified_image_digest"] == QUALIFIED_IMAGE
    assert manifest["qualified_image_source_commit"] == IMAGE_SOURCE_COMMIT


def test_manifest_production_profile_is_unchanged(manifest):
    profile = manifest["production_profile"]
    assert profile["workers"] == 12
    assert profile["numeric_threads_per_worker"] == 1
    assert profile["chunk_size"] == 1
    assert profile["infrastructure_timeout_seconds"] == 243.0
    assert profile["infrastructure_retry_limit"] == 1
    assert profile["semantic_retries"] == 0
    assert profile["cpu_authoritative"] is True
    assert profile["gpu_generation"] is False


def test_manifest_budget_is_a_cap_not_a_target(manifest):
    assert manifest["maximum_selected_source_events"] == 300 * DEFAULT_K == 1500
    assert manifest["maximum_is_a_cap_not_a_target"] is True
    assert manifest["adaptive_refill_permitted"] is False
    assert manifest["outcome_dependent_stopping_permitted"] is False


def test_manifest_covers_every_family_n_and_policy(manifest):
    assert manifest["families"] == ["F%d" % index for index in range(1, 11)]
    assert manifest["team_sizes"] == [5, 6, 8, 12, 16]
    assert set(manifest["family_counts"].values()) == {30}
    assert set(manifest["team_size_counts"].values()) == {60}
    assert len(manifest["source_policies"]) == 6
    assert 24 not in manifest["team_sizes"]


def test_manifest_episode_identities_are_unique(manifest):
    identities = [entry["identity_sha256"] for entry in manifest["episodes"]]
    assert len(set(identities)) == 300


# --------------------------------------------------------------------------
# V4/V5 exclusion union and split hygiene
# --------------------------------------------------------------------------
def test_exclusion_union_is_disjoint_from_official_identities(union):
    assert union["official_validation_intersect_union"] == 0
    assert union["official_train_intersect_union"] == 0
    assert union["official_train_intersect_official_validation"] == 0


def test_exclusion_union_reconstructed_every_recorded_identity(union):
    assert union["reconstruction_unmatched_episode_ids"] == []
    assert union["excluded_identity_count"] == len(union["excluded_identities"])


def test_exclusion_union_completeness_sweep_is_closed(union):
    sweep = union["completeness_sweep"]
    assert sweep["closed"] is True
    assert sweep["unaccounted_episode_ids"] == []


def test_train_audit_contributed_no_exclusion_identity(union):
    audit = union["train_audit_provenance"]
    assert audit["new_non_official_source_identities"] == 0
    assert audit["scientific_rows_published"] == 0
    assert audit["replay_universe_is_subset_of_official_train"] is True


def test_prelaunch_decision_was_go_with_no_blocking_failures():
    go = load("phase9g_v2a_v_prelaunch_go_nogo_v1.json")
    assert go["decision"] == "GO"
    assert go["blocking_failures"] == {}
    checks = go["checks"]
    assert checks["source_episodes_exactly_300"] is True
    assert checks["official_train_identity_overlap"] == 0
    assert checks["exclusion_union_overlap"] == 0
    assert checks["design_pilot_overlap"] == 0
    assert checks["qualification_canary_overlap"] == 0
    assert checks["audit_canary_overlap"] == 0
    assert checks["n24_episodes"] == 0
    assert checks["study_b_episodes"] == 0
    assert checks["final_test_episodes"] == 0
    assert checks["row_binding_v2_hash_is_full_64_hex"] is True


def test_prelaunch_recorded_zero_v1_row_and_event_reuse():
    go = load("phase9g_v2a_v_prelaunch_go_nogo_v1.json")
    relation = go["v1_relation"]
    assert relation["row_reuse"] == 0
    assert relation["event_reuse"] == 0
    assert relation["scientific_row_identity_overlap"] == 0
    assert relation["row_id_overlap"] == 0
    # source-episode reuse is authorised by the frozen budget, rows are not
    assert go["v1_validation_source_episode_identity_overlap"] == 300
    assert relation["source_episode_reuse_authorized"] is True


def test_train_and_validation_layouts_are_fully_disjoint():
    go = load("phase9g_v2a_v_prelaunch_go_nogo_v1.json")
    assert go["checks"]["official_train_layout_id_overlap"] == 0
    assert go["checks"]["official_train_layout_sha256_overlap"] == 0
    readiness = load("phase9g_v2a_v_combined_audit_readiness_v1.json")
    separation = readiness["split_separation_verified"]
    assert separation["train_layouts"] == 20
    assert separation["validation_layouts"] == 10


# --------------------------------------------------------------------------
# V9/V10 Stage A -- candidate-blind acquisition
# --------------------------------------------------------------------------
def test_stage_a_ran_the_complete_frozen_manifest():
    stage_a = load("phase9g_v2a_v_stage_a_validation_ledger_v1.json")
    assert stage_a["source_episodes"] == 300
    assert stage_a["fabricated_source_states"] == 0
    assert stage_a["violations"] == {}
    assert stage_a["duplicate_source_event_ids"] == 0
    assert stage_a["candidate_blind"]
    assert stage_a["frozen_before_any_candidate_execution"] is True


def test_stage_a_m_partition_sums_to_the_manifest():
    stage_a = load("phase9g_v2a_v_stage_a_validation_ledger_v1.json")
    assert (
        stage_a["episodes_with_M_zero"]
        + stage_a["episodes_with_M_below_K"]
        + stage_a["episodes_with_M_at_or_above_K"]
        == 300
    )


def test_stage_a_selection_is_within_the_frozen_cap():
    stage_a = load("phase9g_v2a_v_stage_a_validation_ledger_v1.json")
    assert stage_a["selected_source_events"] <= stage_a["selected_events_cap"]
    assert stage_a["selected_within_cap"] is True
    assert stage_a["selected_source_events"] == stage_a["distinct_source_event_ids"]


def test_stage_a_m_zero_is_only_the_known_structural_cell():
    stage_a = load("phase9g_v2a_v_stage_a_validation_ledger_v1.json")
    assert set(stage_a["m_zero_cells"]) == {"F4/N16"}
    assert stage_a["m_zero_cells"]["F4/N16"] == stage_a["episodes_with_M_zero"]


def test_stage_a_selection_indices_were_independently_recomputed():
    stage_a = load("phase9g_v2a_v_stage_a_validation_ledger_v1.json")
    assert stage_a["selection_rule_independently_recomputed"] is True
    assert stage_a["selection_index_mismatches"] == 0


@pytest.mark.parametrize(
    "m,expected",
    [(0, ()), (1, (0,)), (4, (0, 1, 2, 3)), (5, (0, 1, 2, 3, 4)),
     (9, (0, 2, 4, 6, 8)), (10, (0, 2, 4, 6, 9)), (17, (0, 4, 8, 12, 16))],
)
def test_v10_m_semantics_hold_for_the_frozen_rule(m, expected):
    universe = type("U", (), {"M": m})()
    assert select_realized_trajectory_uniform_k(universe, DEFAULT_K) == expected


# --------------------------------------------------------------------------
# V11-V13 Stage B
# --------------------------------------------------------------------------
def test_every_selected_event_was_executed(closure):
    stage_b = closure["stage_b"]
    assert stage_b["all_selected_events_executed"] is True
    assert stage_b["events_executed"] == stage_b["selected_source_events"]


def test_candidate_aggregates_are_exactly_two_per_event(closure):
    stage_b = closure["stage_b"]
    assert stage_b["candidate_aggregates_attempted"] == 2 * stage_b["events_executed"]


def test_dispositions_reconcile_against_attempted_aggregates(closure):
    stage_b = closure["stage_b"]
    assert (
        stage_b["positives"]
        + stage_b["valid_negatives"]
        + stage_b["actual_generation_invalid"]
        == stage_b["candidate_aggregates_attempted"]
    )


def test_no_fake_generation_invalid_was_emitted(closure):
    assert closure["stage_b"]["fake_generation_invalid"] == 0


def test_nonexistent_source_states_created_no_aggregates():
    summary = load("phase9g_v2a_v_candidate_disposition_summary_v1.json")
    assert summary["source_states_not_realized_producing_aggregates"] == 0
    assert summary["dispositions_reconcile_against_aggregates"] is True


def test_f8_and_f9_used_exactly_three_replicas(closure):
    policy = closure["replica_policy"]
    assert policy["f8_exactly_three_replicas"] is True
    assert policy["f9_exactly_three_replicas"] is True
    assert set(policy["by_family"]["F8"]) == {"3"}
    assert set(policy["by_family"]["F9"]) == {"3"}


def test_train_label_frequencies_were_not_consulted():
    ledger = load("phase9g_v2a_v_candidate_execution_ledger_v1.json")
    assert ledger["train_label_frequencies_consulted"] is False


# --------------------------------------------------------------------------
# V12/V21/V22 pairs, rows and accounting
# --------------------------------------------------------------------------
def test_no_partial_pair_was_published(closure):
    pairs = closure["pair_transactions"]
    assert pairs["partial_publications"] == 0
    assert pairs["retained_events"] + pairs["dropped_events"] == (
        closure["stage_b"]["events_executed"]
    )


def test_rows_equal_the_exact_sum_of_two_n(closure):
    rows = closure["rows"]
    assert rows["row_count_matches_exact_2N"] is True
    assert rows["rows_published"] == rows["expected_rows_exact_2N_sum"]


def test_row_publication_uses_exact_per_event_two_n_not_average():
    audit = load("phase9g_v2a_v_row_publication_audit_v1.json")
    assert audit["accounting_uses_exact_per_event_2N_not_average_N"] is True


def test_every_row_passed_identity_validation(closure):
    rows = closure["rows"]
    assert rows["validation_failures"] == {}
    assert rows["validation_failure_total"] == 0
    assert rows["event_identity_recomputation_mismatches"] == 0


def test_no_duplicate_or_conflicting_row_ids(closure):
    rows = closure["rows"]
    assert rows["duplicate_row_ids"] == 0
    assert rows["duplicate_row_ids_with_conflicting_payload"] == 0
    assert rows["distinct_row_ids"] == rows["rows_published"]


def test_row_audit_pins_the_three_contract_hashes():
    audit = load("phase9g_v2a_v_row_publication_audit_v1.json")
    assert audit["source_acquisition_protocol_sha256"] == FROZEN_PROTOCOL
    assert audit["recoverability_row_binding_v2_spec_sha256"] == FROZEN_ROW_BINDING
    assert audit["target_v4_contract_sha256"] == FROZEN_TARGET_V4


def test_v1_row_ids_cannot_collide_with_v2_row_ids(closure):
    relation = closure["v1_relation"]
    assert relation["v1_rows_reused"] == 0
    assert relation["v1_rows_mutated"] == 0
    assert relation["v1_events_reused"] == 0
    assert relation["constructive_collision_probe_rows"] > 0
    assert relation["constructive_collision_probe_errors"] == 0
    assert relation["v1_style_ids_colliding_with_v2_ids"] == 0


# --------------------------------------------------------------------------
# V24/V25 adequacy gate
# --------------------------------------------------------------------------
def test_adequacy_gate_unit_is_the_retained_source_event_pair():
    gate = load("phase9g_v2a_v_validation_adequacy_gate_v1.json")
    assert gate["unit"] == "RETAINED_SOURCE_EVENT_PAIR"
    assert gate["unit_is_not_robot_rows"] is True
    assert gate["unit_is_not_candidate_aggregates"] is True


def test_adequacy_gate_threshold_is_unchanged_at_thirty():
    gate = load("phase9g_v2a_v_validation_adequacy_gate_v1.json")
    assert gate["minimum"] == 30
    assert gate["gate_unchanged"] is True
    assert gate["primary_families"] == ["F%d" % index for index in range(1, 11)]


def test_every_primary_family_passes_the_frozen_gate():
    gate = load("phase9g_v2a_v_validation_adequacy_gate_v1.json")
    assert gate["all_primary_families_pass"] is True
    assert len(gate["per_family"]) == 10
    for row in gate["per_family"]:
        assert row["retained_source_events"] >= 30, row["family"]


def test_gate_was_evaluated_only_after_the_full_manifest():
    gate = load("phase9g_v2a_v_validation_adequacy_gate_v1.json")
    assert gate["evaluated_after_full_manifest"] is True
    assert gate["episodes_added_for_weak_families"] == 0
    assert gate["outcome_dependent_stopping_used"] is False
    assert gate["replenishment_performed"] is False
    assert gate["m_zero_episodes_replaced"] == 0


def test_retained_events_reconcile_with_the_gate_table(closure):
    gate = load("phase9g_v2a_v_validation_adequacy_gate_v1.json")
    total = sum(row["retained_source_events"] for row in gate["per_family"])
    assert total == closure["pair_transactions"]["retained_events"]


# --------------------------------------------------------------------------
# V26 zero-positive carry-forward
# --------------------------------------------------------------------------
def test_zero_positive_families_are_reported_descriptively(closure):
    assert closure["zero_positive_families"] == ["F3", "F4", "F6"]
    summary = load("phase9g_v2a_v_candidate_disposition_summary_v1.json")
    assert summary["descriptive_only"] is True
    for family in ("F3", "F4", "F6"):
        labels = summary["by_family"][family]
        assert labels.get("COMPACT_positive", 0) == 0
        assert labels.get("LINE_positive", 0) == 0


def test_zero_positive_families_still_pass_the_adequacy_gate():
    gate = load("phase9g_v2a_v_validation_adequacy_gate_v1.json")
    rows = {row["family"]: row for row in gate["per_family"]}
    for family in ("F3", "F4", "F6"):
        assert rows[family]["passes"] is True


def test_scenario_manifest_tension_is_carried_forward_unmodified():
    readiness = load("phase9g_v2a_v_combined_audit_readiness_v1.json")
    assert "SCENARIO_MANIFEST_VS_MID_TRAJECTORY_TENSION" in readiness["carry_forward"]


# --------------------------------------------------------------------------
# V27 class weighting
# --------------------------------------------------------------------------
def test_class_weighting_remains_none_unweighted_bce(manifest, dataset):
    assert manifest["class_weighting"] == "NONE_UNWEIGHTED_BCE"
    assert dataset["class_weighting"] == "NONE_UNWEIGHTED_BCE"
    summary = load("phase9g_v2a_v_candidate_disposition_summary_v1.json")
    assert summary["class_weighting"] == "NONE_UNWEIGHTED_BCE"
    assert summary["class_weights_selected_from_outcomes"] is False


# --------------------------------------------------------------------------
# V15/V16 operations
# --------------------------------------------------------------------------
def test_timeout_was_exactly_243_seconds_and_never_adjusted():
    ledger = load("phase9g_v2a_v_timeout_retry_ledger_v1.json")
    assert ledger["infrastructure_timeout_seconds"] == 243.0
    assert ledger["timeout_changed_during_run"] is False
    assert ledger["timeout_increased_preemptively"] is False


def test_retry_limit_matches_the_authorized_policy():
    ledger = load("phase9g_v2a_v_timeout_retry_ledger_v1.json")
    assert ledger["infrastructure_retry_limit"] == 1


def test_no_timeout_retry_or_unresolved_infrastructure_failure():
    ledger = load("phase9g_v2a_v_timeout_retry_ledger_v1.json")
    assert ledger["timeout_retries"] == 0
    assert ledger["infrastructure_retries"] == 0
    assert ledger["unresolved_infrastructure_failures"] == 0
    assert ledger["timeout_exceeded_events"] == 0


def test_no_infrastructure_condition_became_a_scientific_label():
    ledger = load("phase9g_v2a_v_timeout_retry_ledger_v1.json")
    assert ledger["infrastructure_condition_converted_to_scientific_label"] is False
    assert ledger["scientific_workload_reduced"] is False
    assert ledger["families_or_N_skipped"] == 0


def test_maximum_event_stayed_under_the_timeout():
    ledger = load("phase9g_v2a_v_timeout_retry_ledger_v1.json")
    assert ledger["maximum_event_seconds"] < ledger["infrastructure_timeout_seconds"]
    assert ledger["events_over_200s"] == 0


# --------------------------------------------------------------------------
# V17 resume and idempotence
# --------------------------------------------------------------------------
def test_no_duplicate_stage_a_or_stage_b_records():
    audit = load("phase9g_v2a_v_resume_idempotence_audit_v1.json")
    assert audit["stage_a_duplicates"] == 0
    assert audit["stage_b_duplicates"] == 0
    assert audit["alternate_scientific_ids_created"] == 0
    assert audit["duplicates_published"] == 0


def test_stage_b_executed_exactly_the_stage_a_selection():
    audit = load("phase9g_v2a_v_resume_idempotence_audit_v1.json")
    assert audit["stage_b_events_equal_stage_a_selection"] is True


# --------------------------------------------------------------------------
# V28 seals
# --------------------------------------------------------------------------
def test_dataset_manifest_is_validation_only(dataset):
    assert dataset["split"] == "validation"
    assert dataset["train_included"] is False
    assert dataset["training_authorized"] is False
    assert dataset["status"] == "VALID_FROZEN_VALIDATION_ONLY"
    assert dataset["completion_state"] == "COMPLETE"


def test_dataset_manifest_agrees_with_the_closure(closure, dataset):
    assert dataset["scientific_row_count"] == closure["rows"]["rows_published"]
    assert dataset["retained_pair_events"] == (
        closure["pair_transactions"]["retained_events"]
    )
    assert dataset["selected_source_events"] == (
        closure["stage_b"]["selected_source_events"]
    )
    assert dataset["roots"] == closure["roots"]
    assert dataset["composite_validation_seal"] == closure["composite_validation_seal"]


def test_dataset_manifest_shards_reconcile(dataset):
    assert dataset["shard_count"] == len(dataset["shards"])
    assert sum(shard["bytes"] for shard in dataset["shards"]) == dataset["total_bytes"]
    assert sum(shard["row_count"] for shard in dataset["shards"]) == (
        dataset["scientific_row_count"]
    )
    for shard in dataset["shards"]:
        assert len(shard["content_sha256"]) == 64
        assert shard["path"].startswith("rows/")


def test_composite_seal_binds_every_required_root(closure):
    roots = closure["roots"]
    assert set(roots) == {
        "manifest_root",
        "stage_a_root",
        "candidate_evaluation_root",
        "pair_transaction_root",
        "row_dataset_root",
        "operational_ledger_root",
    }
    for value in roots.values():
        assert len(value) == 64
    assert len(closure["composite_validation_seal"]) == 64


def test_manifest_root_equals_the_frozen_manifest_hash(closure, manifest):
    assert closure["roots"]["manifest_root"] == (
        manifest["official_v2_validation_manifest_sha256"]
    )


# --------------------------------------------------------------------------
# V2/V29 immutability
# --------------------------------------------------------------------------
def test_official_train_seal_is_unchanged(closure):
    train = closure["train_immutability"]
    assert train["composite_train_seal"] == TRAIN_SEAL
    assert train["verified_before_run"] is True
    assert train["verified_after_run"] is True
    assert train["shards_verified"] == "44/44"
    assert train["train_rows"] == 90294


def test_committed_train_artifacts_were_not_modified():
    train = load("phase9g_v2a_t_official_train_closure_v1.json")
    assert train["composite_train_seal"] == TRAIN_SEAL
    assert verify_canonical_hash(
        train, "phase9g_v2a_t_official_train_closure_sha256"
    )
    dataset = load("phase9g_v2a_t_official_train_dataset_manifest_v1.json")
    assert verify_canonical_hash(dataset, "dataset_manifest_sha256")


def test_v1_roots_are_unchanged(closure):
    v1 = closure["v1_immutability"]
    assert v1["train"] == (
        "4ac3d2cb65a8b5d656a5d982b344466868f8deaa8cef2b93af7ce824e9387caf"
    )
    assert v1["validation"] == (
        "c991aa3016b38b524a14d9b7037b63d97c2cbbb7d92279fc5a297b9c55d4989e"
    )
    assert v1["combined"] == (
        "7e583ef98184767edfb95387ecc23d2ab266e2137db28a9fbb3badccaa495672"
    )
    assert v1["verified_unchanged"] is True


# --------------------------------------------------------------------------
# V19/V30/V31 closed scopes
# --------------------------------------------------------------------------
def test_all_sealed_domains_remain_at_zero(closure):
    scopes = closure["closed_scopes"]
    for key in (
        "additional_train_rows",
        "residual_rows",
        "training_operations",
        "hyperparameter_trials",
        "model_checkpoints",
        "optimizer_states",
        "study_a_n24_accesses",
        "study_b_accesses",
        "final_test_accesses",
        "v1_mutations",
    ):
        assert scopes[key] == 0, key


def test_combined_audit_readiness_keeps_training_closed():
    readiness = load("phase9g_v2a_v_combined_audit_readiness_v1.json")
    assert readiness["training_authorized"] is False
    assert readiness["hyperparameter_search_authorized"] is False
    assert readiness["residual_v2_authorized"] is False
    assert readiness["next_authorized_step"] == (
        "AUTHORIZE_COMBINED_RECOVERABILITY_V2_TRAIN_VALIDATION_AUDIT"
    )
    for value in readiness["sealed_domain_counters"].values():
        assert value == 0


def test_readiness_carries_forward_the_open_implementation_task():
    readiness = load("phase9g_v2a_v_combined_audit_readiness_v1.json")
    assert "TRAINING_PIPELINE_NOT_V2_READY" in readiness["carry_forward"]
    assert "F4_N16_STRUCTURAL_SOURCE_EMPTY" in readiness["carry_forward"]


def test_closure_verdict_and_recommendation(closure):
    assert closure["verdict"] == "C"
    assert closure["recommendation"] == (
        "AUTHORIZE_COMBINED_RECOVERABILITY_V2_TRAIN_VALIDATION_AUDIT"
    )


# --------------------------------------------------------------------------
# family x N table
# --------------------------------------------------------------------------
def test_family_by_n_table_is_complete_and_descriptive(closure):
    audit = load("phase9g_v2a_v_family_n_validation_audit_v1.json")
    assert audit["descriptive_only"] is True
    assert audit["protocol_changed_in_response"] is False
    assert audit["cells"] == 50
    assert audit["family_by_n"] == closure["family_by_n"]


def test_family_by_n_totals_reconcile_with_the_closure(closure):
    cells = closure["family_by_n"].values()
    assert sum(cell["source_episodes"] for cell in cells) == 300
    assert sum(cell["selected_events"] for cell in cells) == (
        closure["stage_b"]["selected_source_events"]
    )
    assert sum(cell.get("rows", 0) for cell in cells) == (
        closure["rows"]["rows_published"]
    )
    assert sum(cell.get("retained_pair_events", 0) for cell in cells) == (
        closure["pair_transactions"]["retained_events"]
    )
    assert sum(cell.get("generation_invalid", 0) for cell in cells) == 0
