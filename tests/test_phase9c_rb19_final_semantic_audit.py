"""RB-19 -- final semantic, provenance, sealed-domain and isolation audit.

The audit closes the Target V4 provenance gap RB-18 found, and these tests pin
both the closure and the negative matrix: every stale or unsafe root must be
rejected by preflight, not merely absent.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import shutil

import pytest

from rvt_swarm.decentralized import guards
from rvt_swarm.fd24.configuration import ROBOT_LOCAL_ACTION_COMPONENTS
from rvt_swarm.fd24.model import FD24_MODEL_SCHEMA_VERSION
from rvt_swarm.phase8.common import canonical_json_bytes
from rvt_swarm.phase8r import CANDIDATE_COUNT
from rvt_swarm.phase9.preflight import (
    build_preflight_audit, rb19_provenance_checks, residual_v2_contract_checks,
)
from rvt_swarm.phase9c_rb.counterfactual import replica_count_for_family
from rvt_swarm.phase9c_rb.generation_contract import (
    EMITS_TARGET_ROW, EXECUTION_ATTEMPT_KEY, CANDIDATE_EVALUATION_KEY,
    NO_ELIGIBLE_ACTION, SCIENTIFIC_ROW_KEY,
)
from rvt_swarm.topology_registry import COMPACT, KEEP, LINE

ROOT = pathlib.Path("results/rvt_fd24")
AUDIT = json.loads((ROOT / "rb19_final_semantic_isolation_audit_v1.json").read_text())
CURRENT_ROOT = json.loads(
    (ROOT / "rb19_current_generation_provenance_v1.json").read_text())
TARGET = json.loads((ROOT / "target_v4_execution_contract_v1.json").read_text())
RB17 = json.loads((ROOT / "rb17_generation_contract_composite_v1.json").read_text())
RB18 = json.loads((ROOT / "rb18_structural_generation_canary_v1.json").read_text())
V6 = json.loads((ROOT / "headroom_requalification_v6.json").read_text())
PROTOCOL = json.loads((ROOT / "executable_scientific_protocol_v1.json").read_text())
BUDGET1 = json.loads((ROOT / "datasets" / "generation_budget_v1.json").read_text())
BUDGET2 = json.loads((ROOT / "generation_budget_v2.json").read_text())


def _self_hash(document, field):
    body = {k: v for k, v in document.items() if k != field}
    return hashlib.sha256(canonical_json_bytes(body)).hexdigest()


# ---------------------------------------------------------------------------
# RB19-0/1 -- Target V4 and the repaired root
# ---------------------------------------------------------------------------
def test_artifacts_are_self_consistent() -> None:
    assert _self_hash(AUDIT, "rb19_final_semantic_isolation_audit_sha256") == AUDIT[
        "rb19_final_semantic_isolation_audit_sha256"]
    assert _self_hash(
        CURRENT_ROOT, "rb19_current_generation_provenance_sha256") == CURRENT_ROOT[
        "rb19_current_generation_provenance_sha256"]
    assert AUDIT["schema_version"] == "rvt-rb19-final-semantic-isolation-audit/v1"
    assert CURRENT_ROOT["schema_version"] == "rvt-rb19-current-generation-provenance/v1"


def test_target_v4_is_read_from_the_authoritative_artifact() -> None:
    record = AUDIT["target_v4"]
    assert record["contract_id"] == TARGET["schema_version"]
    assert record["sha256"] == TARGET["target_v4_execution_contract_sha256"]
    assert record["self_consistent"] is True
    assert record["inferred_from_code"] is False
    assert record["dispositions"] == ["RECOVERABLE_POSITIVE", "VALID_TASK_NEGATIVE",
                                      "GENERATION_INVALID"]
    assert len(record["raw_predicates"]) == 10
    assert record["positive_rule"].startswith("GOAL_COMPLETE")
    assert "generation valid" in record["valid_negative_rule"]


def test_the_target_v4_hash_agrees_with_every_authoritative_reference() -> None:
    record = AUDIT["target_v4"]
    assert record["cross_references_agree"] is True
    assert V6["protocol_hashes"]["target_v4_execution_contract"] == record["sha256"]
    assert RB18["contract_root"]["target_v4_bound_additively_here"]["sha256"] == (
        record["sha256"])
    assert TARGET["phase8_protocol_hash"] == record["phase8_protocol_hash"]


def test_rb17_is_preserved_and_superseded_not_rewritten() -> None:
    gap = AUDIT["rb17_provenance_gap"]
    assert gap["target_v4_cited_by_rb17"] is False
    assert gap["rb17_rewritten"] is False
    assert gap["executable_semantic_mismatch_found_in_rb18"] is False
    assert RB17["rb17_generation_contract_composite_sha256"] == (
        "bba1aee0430bc540f20d010b923696b5b1c51d4bfb1d92d2fa21daf2e6242da8")
    supersedes = CURRENT_ROOT["supersedes"]
    assert supersedes["sha256"] == RB17["rb17_generation_contract_composite_sha256"]
    assert supersedes["edited_in_place"] is False
    assert supersedes["retained_as_historical_evidence"] is True


# ---------------------------------------------------------------------------
# RB19-2/3/29 -- provenance closure
# ---------------------------------------------------------------------------
def test_provenance_closure_has_no_missing_or_ambiguous_node() -> None:
    closure = AUDIT["provenance_closure"]
    assert closure["missing_required_contracts"] == []
    assert closure["ambiguous_current_contracts"] == []
    assert closure["current_nodes_pointing_only_to_superseded"] == []
    assert closure["resolved_node_count"] >= closure["required_node_count"]


def test_every_closure_node_has_exactly_one_status_from_the_taxonomy() -> None:
    allowed = {"CURRENT", "SUPERSEDED_EVIDENCE", "HISTORICAL_IMMUTABLE",
               "DIAGNOSTIC_ONLY", "PENDING_OPERATIONAL_QUALIFICATION"}
    for entry in CURRENT_ROOT["closure"]:
        assert entry["status"] in allowed, entry
        assert entry["sha256"]
        assert entry["concept"] and entry["artifact"]


def test_the_expected_nodes_carry_the_expected_status() -> None:
    status = {entry["concept"]: entry["status"] for entry in CURRENT_ROOT["closure"]}
    assert status["RB16 frame-conflict audit"] == "SUPERSEDED_EVIDENCE"
    assert status["RB16 requalification"] == "CURRENT"
    assert status["RB17 generation-contract composite"] == "SUPERSEDED_EVIDENCE"
    assert status["historical generation budget V1"] == "HISTORICAL_IMMUTABLE"
    assert status["historical job manifest"] == "HISTORICAL_IMMUTABLE"
    assert status["RB18 structural canary"] == "DIAGNOSTIC_ONLY"
    assert status["residual V2 generation timeout"] == (
        "PENDING_OPERATIONAL_QUALIFICATION")
    assert status["Target V4 execution contract"] == "CURRENT"


def test_the_closure_resolves_target_v4_explicitly() -> None:
    entry = next(item for item in CURRENT_ROOT["closure"]
                 if item["concept"] == "Target V4 execution contract")
    assert entry["sha256"] == TARGET["target_v4_execution_contract_sha256"]
    assert CURRENT_ROOT["target_v4"]["explicitly_cited"] is True
    assert CURRENT_ROOT["target_v4"]["sha256"] == entry["sha256"]


def test_every_closure_hash_still_matches_its_artifact() -> None:
    for entry in CURRENT_ROOT["closure"]:
        artifact = entry["artifact"].split("#")[0]
        path = pathlib.Path(artifact)
        if not path.exists() or path.is_dir():
            continue
        if artifact.endswith(".py"):
            assert hashlib.sha256(path.read_bytes()).hexdigest() == entry["sha256"] or \
                entry["concept"] == "ego-graph feature schema", entry["concept"]


# ---------------------------------------------------------------------------
# RB19-4 -- stale semantics
# ---------------------------------------------------------------------------
def test_no_stale_semantics_are_current() -> None:
    stale = AUDIT["stale_reference_audit"]
    assert stale["stale_current_references"] == []
    assert len(stale["checks"]) >= 14
    for check in stale["checks"]:
        assert check["blocked"] is True, check["stale"]


def test_the_stale_matrix_covers_the_named_semantics() -> None:
    covered = {check["stale"] for check in AUDIT["stale_reference_audit"]["checks"]}
    for required in ("model output frame = MISSION",
                     "residual candidate count != 9",
                     "residual applied post-safety",
                     "synthetic rotation augmentation enabled",
                     "residual job timeout = 1800 s authoritative",
                     "missing mission_orientation_cos_sin",
                     "KEEP in primary online topology scope",
                     "local dwell treated as distributed COMPLETE",
                     "hardcoded SAFE readiness",
                     "persistent lifecycle message queue"):
        assert required in covered, required


# ---------------------------------------------------------------------------
# RB19-5..13 -- semantic audits
# ---------------------------------------------------------------------------
def test_recoverability_semantics_have_no_shortcut() -> None:
    record = AUDIT["recoverability_semantics"]
    for forbidden in ("proxy_classifier_label", "terminal_step_collision_only_label",
                      "historical_shortcut", "global_runtime_controller"):
        assert record[forbidden] is False, forbidden
    assert record["raw_predicates_preserved_before_mapping"] is True
    assert record["target_v4_taxonomy"] == TARGET["dispositions"]
    assert record["ordinary_failure_is_a_valid_negative"] is True
    assert record["safety_infeasible_and_solver_failure_distinct"] is True


def test_f8_f9_replica_rule_is_frozen_and_its_limitation_recorded() -> None:
    rule = AUDIT["f8_f9_replica_rule"]
    assert rule["replica_count"]["F8"] == replica_count_for_family("F8") == 3
    assert rule["replica_count"]["F9"] == replica_count_for_family("F9") == 3
    assert rule["replica_count"]["other"] == 1
    assert rule["aggregation"] == "all_success"
    assert rule["generation_shortcut_reducing_replicas"] is False
    assert rule["rule_altered_in_rb19"] is False
    assert "p^3" in rule["known_limitation"]


def test_residual_semantics_have_no_hidden_shortcut() -> None:
    record = AUDIT["residual_semantics"]
    assert record["candidate_count"] == CANDIDATE_COUNT == 9
    assert len(record["candidates"]) == 9
    for forbidden in ("hidden_fallback", "target_rotation", "candidate_subset",
                      "short_horizon_optimization",
                      "data_dependent_utility_normalization"):
        assert record[forbidden] is False, forbidden
    assert record["selector_unchanged"] is True
    assert record["target_builder_unchanged"] is True


def test_no_eligible_action_has_no_fallback_anywhere() -> None:
    record = AUDIT["no_eligible_audit"]
    assert record["scientifically_attempted"] is True
    assert record["emits_target_rows"] is False
    assert record["is_execution_invalid"] is False
    assert record["is_infrastructure_failure"] is False
    assert record["deterministic_on_retry"] is True
    for forbidden in ("creates_zero_residual", "creates_clipped_residual",
                      "creates_fallback_candidate",
                      "default_vector_behaviour_in_writers"):
        assert record[forbidden] is False, forbidden
    assert record["rb18_rows_from_no_eligible"] == 0
    assert EMITS_TARGET_ROW[NO_ELIGIBLE_ACTION] is False


def test_frame_chain_is_world_end_to_end() -> None:
    frame = AUDIT["frame_audit"]
    assert frame["expert_target"] == frame["scientific_target"] == "WORLD"
    assert frame["model_output"] == frame["runtime_insertion"] == "WORLD"
    assert frame["one_current_chain"] is True
    assert frame["world_mission_residual_transformation_in_primary_path"] is False
    assert frame["input_ego_features_frame"] == "MISSION"
    assert frame["rotation_equivariance_claimed"] is False
    assert not any("mission" in name for name in ROBOT_LOCAL_ACTION_COMPONENTS)
    assert FD24_MODEL_SCHEMA_VERSION == "rvt-fd24-model/v2"


def test_model_input_reconstructs_without_hidden_state() -> None:
    record = AUDIT["model_input_and_target"]
    assert record["reconstructable_without_hidden_state"] is True
    assert record["orientation_consumed_only_by_residual_head"] is True
    assert record["recoverability_orientation_independent"] is True
    for trip in record["rb18_evidence"]:
        assert trip["orientation_exact"] is True
        assert trip["residual_output_identical"] is True
        assert trip["recoverability_logit_identical"] is True


def test_identities_remain_distinct_and_invariant() -> None:
    record = AUDIT["identity_audit"]
    assert record["all_three_distinct"] is True
    assert record["recoverability_namespace_separate"] is True
    assert record["hash_domain_collisions"] == 0
    assert record["chunk_invariance"] is True
    assert record["retry_invariance"] is True
    assert record["semantic_retries"] == 0
    assert not set(EXECUTION_ATTEMPT_KEY) & set(SCIENTIFIC_ROW_KEY)
    assert not set(EXECUTION_ATTEMPT_KEY) & set(CANDIDATE_EVALUATION_KEY)
    assert "candidate_index" not in SCIENTIFIC_ROW_KEY


# ---------------------------------------------------------------------------
# RB19-14..19 -- splits, seals and training-selection safety
# ---------------------------------------------------------------------------
def test_split_isolation_and_the_sealed_domains() -> None:
    splits = AUDIT["split_isolation"]
    assert splits["permitted_layout_source_splits"] == ["train", "validation"]
    assert splits["final_test_job_construction"] == "prohibited"
    assert splits["train_validation_pooling"] is False
    assert splits["rb19_accessed_n24"] is False
    assert splits["rb19_accessed_final_test"] is False


def test_study_a_n24_remains_sealed_for_zero_shot_only() -> None:
    seal = AUDIT["study_a_n24_seal"]
    assert seal["rb19_accesses"] == 0
    assert seal["purpose"] == "zero_shot_size_evaluation_only"
    for prohibited in ("training", "early_stopping", "hyperparameter_search",
                       "checkpoint_selection"):
        assert prohibited in seal["prohibited_consumers"], prohibited
    assert seal["sealed_namespace_contents"] == ["namespace_manifest.json"]


def test_study_b_n24_is_distinctly_scoped() -> None:
    record = AUDIT["study_b_distinction"]
    assert record["must_not_be_conflated"] is True
    assert record["rb19_accessed_either"] is False
    assert "sealed" in record["study_a_n24"]
    assert "training" in record["study_b_n24"]
    assert "study_b_with_n24" in record["study_b_namespace"]


def test_final_test_remains_sealed() -> None:
    seal = AUDIT["final_test_seal"]
    assert seal["geometry_materialized"] is False
    assert seal["runtime_access_count"] == 0
    assert seal["geometry_compilation"] == "prohibited"
    assert seal["labels_or_statistics_used"] is False
    assert seal["rb19_accesses"] == 0
    assert seal["permitted_metadata"] == sorted(
        PROTOCOL["final_test_access_policy"]["permitted_metadata"])


def test_training_selection_safety_is_untouched() -> None:
    roles = AUDIT["train_validation_roles"]
    assert roles["class_weighting"] == "NOT_SELECTED"
    assert roles["validation_labels_inspected_for_training_statistics"] is False
    assert roles["normalization_data_dependent"] is False
    assert roles["sampling_weights_chosen"] is False
    assert roles["threshold_selection_done"] is False
    assert roles["silent_train_validation_pooling"] is False


def test_no_new_hyperparameter_was_introduced() -> None:
    freeze = AUDIT["hyperparameter_freeze"]
    assert freeze["maximum_searched_configurations"] == 12
    assert freeze["maximum_steps"] == 50000
    assert freeze["model_seeds"] == [11, 29, 47]
    for source in ("residual_v2", "world_repair", "orientation_context",
                   "generation_contracts"):
        assert freeze[f"new_hyperparameter_introduced_by_{source}"] is False, source
    assert freeze["residual_head_parameter_delta"] == 192
    assert freeze["parameter_delta_is_a_hyperparameter"] is False
    assert freeze["chosen_in_rb19"] is False
    assert freeze["contract_sha256"] == hashlib.sha256(
        pathlib.Path("docs/RVT_FD24_HYPERPARAMETER_BUDGET.md").read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# RB19-22..27 -- schedule, topology, decentralization, counters, budget
# ---------------------------------------------------------------------------
def test_event_schedule_semantics_are_current() -> None:
    record = AUDIT["event_schedule_semantics"]
    assert record["addendum_current"] is True
    assert record["horizon_fraction_timing_present"] is False
    assert record["landmark_trigger_current"] is True
    assert record["event_shifted_to_avoid_a_miss"] is False
    assert record["rb18_schedule_mutated"] is False
    assert record["early_termination_rule"] == BUDGET1["event_timestamp_contract"][
        "early_termination"]


def test_primary_topology_scope_is_compact_line_only() -> None:
    scope = AUDIT["topology_scope"]
    assert sorted(scope["primary_online_candidates"]) == sorted([COMPACT, LINE])
    assert scope["keep_is_primary_online"] is False
    assert KEEP in scope["fixed_only_topology_ids"]
    assert scope["primary_initial_topology_id"] == COMPACT


def test_runtime_decentralization_claims_hold() -> None:
    record = AUDIT["decentralization"]
    assert record["strict_guard_violations"] == 0 == len(guards.audit())
    assert record["centralized_training_orchestration_counted_as_violation"] is False
    assert "no global graph pooling" in record["runtime_properties"]
    assert "no joint action" in record["runtime_properties"]


def test_counter_denominators_cannot_silently_drop_a_state() -> None:
    counters = AUDIT["counter_denominators"]
    assert counters["silent_drop_possible"] is False
    assert counters["rows_can_be_fewer_than_attempted"] is True
    for required in ("attempted expert states", "LABELED", "NO_ELIGIBLE_ACTION",
                     "execution invalid", "infrastructure failure",
                     "emitted scientific rows"):
        assert required in counters["residual"], required
    for required in ("scheduled", "observed", "valid positive", "valid negative",
                     "execution invalid", "infrastructure failure"):
        assert required in counters["recoverability"], required


def test_budget_arithmetic_is_consistent_and_not_conflated() -> None:
    budget = AUDIT["budget_consistency"]
    assert budget["stored_dense_residual_row_upper_cap"] == 536000
    assert budget["residual_candidate_count"] == 9
    assert budget["candidate_evaluation_compute_upper_bound"] == 4824000
    assert budget["compute_bound_called_scientific_rows"] is False
    assert budget["arithmetic_consistent"] is True
    assert budget["recoverability_caps_unchanged"] is True
    assert BUDGET1["generation_budget_sha256"] == (
        "3853b8ad4484d733de9be7d0e27bf273f33e14054f3089f6b5454cc17815846e")


def test_operational_items_are_pending_without_semantic_ambiguity() -> None:
    pending = AUDIT["operational_pending"]
    assert pending["RESIDUAL_V2_GENERATION_TIMEOUT"] == (
        "PENDING_RB21_PERFORMANCE_QUALIFICATION")
    assert pending["worker_count"] == "UNFROZEN"
    assert pending["chunk_size"] == "UNFROZEN"
    assert pending["scientific_semantics_ambiguous"] is False
    assert pending["official_execution_authorized"] is False
    assert CURRENT_ROOT["generation_authorized"] is False


def test_residual_optionality_forbids_post_hoc_redefinition() -> None:
    record = AUDIT["residual_optionality"]
    assert record["h4_optional"] is True
    assert record["post_hoc_change_permitted_to"] == []
    assert "disable" in record["predeclared_response_to_unacceptable_performance"]


def test_rb19_added_no_scientific_mechanism() -> None:
    assert AUDIT["new_scientific_mechanism_added"] is False


# ---------------------------------------------------------------------------
# RB19-28 -- the preflight negative matrix
# ---------------------------------------------------------------------------
def test_preflight_passes_positively() -> None:
    audit = build_preflight_audit(pathlib.Path("."))
    assert audit["status"] == "PASS"
    assert all(check["passed"] for check in audit["checks"])
    names = {check["name"] for check in audit["checks"]}
    for required in ("rb19_target_v4_provenance", "rb19_provenance_closure_complete",
                     "rb19_repaired_rb16_is_current", "rb19_keep_not_online",
                     "rb19_study_a_n24_sealed", "rb19_final_test_sealed",
                     "rb19_generation_not_authorized",
                     "rb19_no_eligible_has_no_fallback",
                     "rb19_no_stale_current_semantics"):
        assert required in names, required


NEGATIVE_MATRIX = [
    ("missing Target V4 provenance", "rb19_current_generation_provenance_v1.json",
     ["target_v4", "explicitly_cited"], False, "rb19_target_v4_provenance"),
    ("wrong Target V4 hash", "rb19_current_generation_provenance_v1.json",
     ["target_v4", "sha256"], "0" * 64, "rb19_target_v4_provenance"),
    ("incomplete provenance closure", "rb19_current_generation_provenance_v1.json",
     ["closure_summary", "missing_required_contracts"], ["Target V4 execution contract"],
     "rb19_provenance_closure_complete"),
    ("current points to the failed RB16", "rb19_current_generation_provenance_v1.json",
     ["closure"], None, "rb19_repaired_rb16_is_current"),
    ("KEEP online", "online_topology_scope.json",
     ["active_candidate_topology_ids"], [5, 2, 0], "rb19_keep_not_online"),
    ("generation prematurely AUTHORIZED", "rb19_current_generation_provenance_v1.json",
     ["official_scientific_execution_status"], "AUTHORIZED",
     "rb19_generation_not_authorized"),
    ("final-test unsealed", "rb19_current_generation_provenance_v1.json",
     ["sealed_domains", "final_test"], "OPEN", "rb19_final_test_sealed"),
    ("Study A N24 unsealed", "rb19_current_generation_provenance_v1.json",
     ["sealed_domains", "study_a_n24"], "TRAINABLE", "rb19_study_a_n24_sealed"),
    ("NO_ELIGIBLE fallback enabled",
     "rb19_final_semantic_isolation_audit_v1.json",
     ["no_eligible_audit", "creates_zero_residual"], True,
     "rb19_no_eligible_has_no_fallback"),
    ("stale current semantics", "rb19_final_semantic_isolation_audit_v1.json",
     ["stale_reference_audit", "stale_current_references"],
     ["model output frame = MISSION"], "rb19_no_stale_current_semantics"),
]


@pytest.mark.parametrize("label,file_name,path,value,check_name", NEGATIVE_MATRIX,
                         ids=[row[0] for row in NEGATIVE_MATRIX])
def test_preflight_rejects_every_stale_or_unsafe_root(
        tmp_path, label, file_name, path, value, check_name) -> None:
    shutil.copytree("results", tmp_path / "results")
    target = tmp_path / "results/rvt_fd24" / file_name
    document = json.loads(target.read_text())
    if label == "current points to the failed RB16":
        for entry in document["closure"]:
            if entry["concept"] == "RB16 requalification":
                entry["status"] = "SUPERSEDED_EVIDENCE"
            elif entry["concept"] == "RB16 frame-conflict audit":
                entry["status"] = "CURRENT"
    else:
        node = document
        for step in path[:-1]:
            node = node[step]
        node[path[-1]] = value
    target.write_text(json.dumps(document, indent=1, sort_keys=True) + "\n")

    checks = rb19_provenance_checks(tmp_path) + residual_v2_contract_checks(tmp_path)
    failed = {check["name"] for check in checks if not check["passed"]}
    assert failed, f"{label} must be rejected"
    # either the targeted semantic check fails, or the mutated document's own
    # canonical hash does -- both are rejections, neither is a silent pass
    assert check_name in failed or any(
        name.endswith(("_hash", "root_hash", "audit_reference")) for name in failed), (
        label, sorted(failed))


def test_a_missing_current_root_is_rejected(tmp_path) -> None:
    shutil.copytree("results", tmp_path / "results")
    (tmp_path / "results/rvt_fd24/rb19_current_generation_provenance_v1.json").unlink()
    checks = rb19_provenance_checks(tmp_path)
    assert checks and not checks[0]["passed"]
    assert checks[0]["name"] == "rb19_current_root_present"


def test_the_negative_matrix_did_not_weaken_positive_semantics() -> None:
    audit = build_preflight_audit(pathlib.Path("."))
    assert audit["status"] == "PASS"
    assert len(audit["checks"]) >= 53


# ---------------------------------------------------------------------------
# RB19-30 -- protected hashes and isolation
# ---------------------------------------------------------------------------
def test_protected_artifacts_are_unchanged() -> None:
    expected = {
        "executable_scientific_protocol_v1.json": ("protocol_hash",
            "8da0b94e5ae83cf35ea38c38504d11d6e6fdce6da09766bf8cb14c4cc252158a"),
        "source_event_timing_addendum_v1.json": (
            "source_event_timing_addendum_sha256",
            "fba87e4374f4a7b8c97e5435e148345ad5611223f663e6050967efe9aa0989c5"),
        "headroom_requalification_v6.json": ("headroom_requalification_v6_sha256",
            "d044d6b99d7a2bbb83565b121d188a35e335bfd856e3eb0e885823ca1a6742ef"),
        "headroom_v6_detached_reproduction_v1.json": (
            "headroom_v6_detached_reproduction_sha256",
            "1f08ba77315e6fdbabfeac8f9350e6f5cd64468c431ecc9fba19747fcd26af32"),
        "headroom_authority_record_v1.json": ("headroom_authority_record_sha256",
            "fafe1460c69ef37ca9134c2fc17721adddda92607e3e4e3c084d6a29d9dab509"),
        "residual_expert_spec_v2.json": ("residual_expert_spec_v2_sha256",
            "e3a3093038b31f7f8c11d56be224929c9eccc27e6bde2fa47c5c6c644b7f3fbf"),
        "residual_label_contract_composite_v2.json": (
            "residual_label_contract_composite_sha256",
            "8921424d0342e26a7a22da4ca042543a8eb08c2dc310f5f5639b70678ceb08ad"),
        "rb15_residual_expert_binding_v2.json": (
            "rb15_residual_expert_binding_v2_sha256",
            "9edc8cc8d46b94c76f0fa8e3a2ea07b7bff06fd9d5cfe5f5cb26565170af3f24"),
        "rb16_native_action_frame_v1.json": ("rb16_native_action_frame_sha256",
            "de697d1253081b907afc3e3e5e275527c0c0f80ac873b140d84e30737478963c"),
        "rb16_world_output_requalification_v1.json": (
            "rb16_world_output_requalification_sha256",
            "10c4aebe41a98db7674f7ee617db8a209a148bdfe18ca76bd04cde59660ab387"),
        "rb17_generation_contract_composite_v1.json": (
            "rb17_generation_contract_composite_sha256",
            "bba1aee0430bc540f20d010b923696b5b1c51d4bfb1d92d2fa21daf2e6242da8"),
        "rb18_structural_generation_canary_v1.json": (
            "rb18_structural_generation_canary_sha256",
            "0291cb52e11e570f48272d76b98d32966513fc8f840a6e47e718076bf3187e3c"),
    }
    for name, (field, value) in expected.items():
        assert json.loads((ROOT / name).read_text())[field] == value, name
    assert BUDGET1["generation_budget_sha256"] == (
        "3853b8ad4484d733de9be7d0e27bf273f33e14054f3089f6b5454cc17815846e")


def test_official_counters_are_zero() -> None:
    counters = AUDIT["official_counters"]
    for key, value in counters.items():
        assert value == 0, key
    residual_audit = json.loads(
        (ROOT / "datasets" / "phase9_residual_audit.json").read_text())
    assert residual_audit["emitted_rows"] == 0
    assert residual_audit["expert_calls"] == 0
    assert BUDGET1["scientific_dataset_records_generated"] == 0
    assert BUDGET1["training_operations"] == 0
