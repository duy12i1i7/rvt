"""RB-15 V2 -- canary, performance and job-identity artifacts.

These pin the artifacts rather than re-running the canary: the canary itself is
an expensive runtime-conformance sweep, and what must not drift is what it
recorded and the fact that it emitted no scientific data.
"""

from __future__ import annotations

import hashlib
import json
import pathlib

import pytest

from rvt_swarm.phase8.common import canonical_json_bytes
from rvt_swarm.phase8r import CANDIDATE_COUNT

ROOT = pathlib.Path("results/rvt_fd24")
CANARY = json.loads((ROOT / "rb15_v2_canary_v1.json").read_text())
BINDING = json.loads((ROOT / "rb15_residual_expert_binding_v2.json").read_text())
IDENTITY = json.loads((ROOT / "residual_generation_job_identity_v2.json").read_text())
SPEC = json.loads((ROOT / "residual_expert_spec_v2.json").read_text())
BUDGET = json.loads((ROOT / "datasets" / "generation_budget_v1.json").read_text())
S3Z = json.loads((ROOT / "phase9_s3_centerline_execution_contract_v1.json").read_text())


def _self_hash(document: dict, field: str) -> str:
    body = {key: value for key, value in document.items() if key != field}
    return hashlib.sha256(canonical_json_bytes(body)).hexdigest()


# ---------------------------------------------------------------------------
# RB15V2-32/33 -- the canary
# ---------------------------------------------------------------------------
def test_canary_artifacts_are_self_consistent() -> None:
    assert _self_hash(CANARY, "rb15_v2_canary_sha256") == CANARY["rb15_v2_canary_sha256"]
    assert _self_hash(BINDING, "rb15_residual_expert_binding_v2_sha256") == BINDING[
        "rb15_residual_expert_binding_v2_sha256"]
    assert _self_hash(IDENTITY, "residual_generation_job_identity_v2_sha256") == IDENTITY[
        "residual_generation_job_identity_v2_sha256"]


def test_canary_is_runtime_conformance_only() -> None:
    assert CANARY["schema_version"] == "rvt-rb15-v2-canary/v1"
    assert CANARY["provenance_class"] == "RUNTIME_CONFORMANCE_ONLY"
    assert CANARY["SCIENTIFIC_SUPERVISION"] is False
    assert CANARY["scientific_dataset_schema_used"] is False
    assert CANARY["official_generation_counters_incremented"] is False
    for forbidden in ("rvt-residual-action-dataset", "rvt-dense-action-sample",
                      "rvt-task-recoverability-target", "rvt-local-view-task-label"):
        assert forbidden not in json.dumps(CANARY), forbidden


def test_canary_covers_the_required_diagnostic_variety() -> None:
    assert len(CANARY["team_sizes_covered"]) >= 2
    assert 24 not in CANARY["team_sizes_covered"]
    assert CANARY["n24_used"] is False
    assert len(CANARY["families_covered"]) > 1
    assert CANARY["collision_counterfactuals"] >= 1
    assert CANARY["candidates_where_projection_changed_the_action"] >= 1
    assert CANARY["decision_states_evaluated"] >= 1
    assert CANARY["candidate_evaluations"] == (
        CANARY["decision_states_evaluated"] * CANDIDATE_COUNT)


def test_every_canary_record_exercised_the_whole_path() -> None:
    for record in CANARY["records"]:
        assert len(record["candidates"]) == CANDIDATE_COUNT
        assert record["robot_view_sha256"]
        assert record["snapshot_sha256"]
        assert record["candidate_lattice_sha256"] == SPEC["candidate_lattice"][
            "candidate_set_sha256"]
        assert record["matched_stream_identity_shared_by_all_candidates"] is True
        assert set(record["base_action_components"]) == {
            "formation_term", "goal_term", "damping_term", "obstacle_term"}
        assert all(value in ("SELF_LOCAL", "ONE_HOP_LOCAL", "LOCAL_OBSTACLE",
                             "LOCAL_PROTOCOL_STATE", "LOCAL_CONTROLLER_DERIVED",
                             "LOCAL_SAFETY_DERIVED", "IMMUTABLE_FROZEN_CONFIG")
                   for value in record["provenance"].values())
        for candidate in record["candidates"]:
            assert candidate["robot_local_information_only"] is True
            assert set(candidate["utilities"]) == {
                "normalized_progress", "normalized_clearance_margin",
                "normalized_formation_error", "normalized_action_deviation"}
            assert candidate["control_intervals"] >= 1
        if record["selected_index"] is not None:
            assert record["target"]["frame"] == "world"
            assert record["target"]["units"] == "meters_per_second_squared"
            assert record["target"]["rb16_rotation_applied"] is False


def test_the_no_eligible_candidate_case_is_the_frozen_path() -> None:
    """One diagnostic state had no eligible candidate. That is declared, not a bug."""
    failures = [record for record in CANARY["records"] if record["selector_error"]]
    assert len(failures) == CANARY["selector_failures"]
    for record in failures:
        assert "no eligible" in record["selector_error"]
        assert record["target"] is None
        # every candidate, including the zero residual, was locally safety-infeasible
        assert all(candidate["safety_projection_compatible"] is False
                   for candidate in record["candidates"])
        assert all(candidate["locally_feasible"] is True
                   for candidate in record["candidates"])
    policy = BUDGET["invalid_record_contract"]["residual_expert_invalid"]
    assert "no_target_row" in policy and "no_replacement" in policy


# ---------------------------------------------------------------------------
# RB15V2-34/35/36 -- performance
# ---------------------------------------------------------------------------
def test_performance_distributions_are_reported_not_just_the_best_case() -> None:
    candidate = CANARY["performance"]["seconds_per_candidate_continuation"]
    expert = CANARY["performance"]["seconds_per_nine_candidate_expert_evaluation"]
    steps = CANARY["performance"]["rollout_control_intervals_per_candidate"]
    for summary in (candidate, expert, steps):
        assert {"count", "mean", "median", "minimum", "maximum"} <= set(summary)
        assert summary["maximum"] >= summary["median"] >= summary["minimum"]
    assert candidate["count"] >= 10 and "p90" in candidate and "p95" in candidate
    assert candidate["maximum"] > candidate["median"]      # the tail is reported
    assert (CANARY["performance"]["early_terminating_candidates_at_most_20_intervals"]
            + CANARY["performance"]["long_rollout_candidates"]) == candidate["count"]


def test_projection_states_formulas_and_chooses_nothing() -> None:
    projection = CANARY["projection"]
    assert projection["frozen_candidate_evaluation_upper_bound"] == 536000 * 9 == 4824000
    assert projection["workers_chosen"] is None
    assert projection["timeout_chosen"] is None
    assert projection["efficiency_assumed"] is None
    assert "efficiency(W)" in projection["formula_w_workers"]
    expected = (CANARY["performance"]["seconds_per_candidate_continuation"]["mean"]
                * 4824000)
    assert projection["single_worker_seconds"] == pytest.approx(expected, rel=1e-6)
    assert len(projection["limitations"]) >= 4


def test_performance_status_is_recorded_with_evidence() -> None:
    status = BINDING["performance_status"]
    assert status["RESIDUAL_V2_PERFORMANCE_STATUS"] in (
        "QUALIFIED_FOR_JOB_BUDGET_DESIGN", "OPERATIONAL_RISK", "INSUFFICIENT_BENCHMARK")
    assert status["evidence"]["candidate_continuations_measured"] >= 10
    assert status["scientific_parameters_changed_to_improve_performance"] == []
    assert status["candidates_still"] == 9
    assert status["intervention_still_one_control_interval"] is True
    assert status["evaluation_still_episode_remainder"] is True
    assert status["utility_objective_unchanged"] is True
    assert "a generation timeout" in status["not_qualified_to_choose"]


# ---------------------------------------------------------------------------
# RB15V2-37 -- job identity
# ---------------------------------------------------------------------------
def test_job_identity_v2_names_every_dimension_the_producer_varies_over() -> None:
    fields = {row["field"] for row in IDENTITY["required_fields"]}
    assert {"residual_cell_job_id", "decision_state_id", "robot_id", "candidate_index",
            "replica_index", "matched_stream_identity",
            "residual_expert_spec_v2_sha256"} <= fields
    for row in IDENTITY["required_fields"]:
        assert row["producer_evidence"], row["field"]
    assert IDENTITY["status"] == "PROPOSED_INPUT_TO_RB17"
    assert IDENTITY["official_job_manifest_mutated"] is False
    assert IDENTITY["official_job_records_emitted"] == 0
    assert IDENTITY["generation_authorized"] is False


def test_the_official_job_manifest_and_budget_are_unchanged() -> None:
    assert BUDGET["job_identity_contract"]["residual_cell"] == [
        "study", "split", "family", "layout_sha256", "team_size"]
    assert BUDGET["timeout_contract"]["wall_clock_seconds"][
        "residual_action_cell_generation_job"] == 1800
    assert BUDGET["scientific_dataset_records_generated"] == 0
    protocol = json.loads((ROOT / "executable_scientific_protocol_v1.json").read_text())
    assert protocol["generation_budget_hash"] == BUDGET["generation_budget_sha256"]
    assert BINDING["generation"]["official_generation_authorized"] is False
    assert BINDING["generation"]["RESIDUAL_V2_GENERATION_TIMEOUT"] == (
        "PENDING_PERFORMANCE_BENCHMARK")


# ---------------------------------------------------------------------------
# RB15V2-38/39/40 -- binding artifact and isolation
# ---------------------------------------------------------------------------
def test_binding_pins_every_authoritative_input_by_hash() -> None:
    inputs = BINDING["authoritative_inputs"]
    assert inputs["residual_expert_spec_v2"]["sha256"] == (
        "e3a3093038b31f7f8c11d56be224929c9eccc27e6bde2fa47c5c6c644b7f3fbf")
    assert inputs["residual_expert_spec_v2"]["reinterpreted"] is False
    assert inputs["residual_label_contract_composite_v2"]["sha256"] == (
        "8921424d0342e26a7a22da4ca042543a8eb08c2dc310f5f5639b70678ceb08ad")
    assert inputs["v1_selector"]["modified"] is False
    assert inputs["v1_target_builder"]["modified"] is False
    assert inputs["v1_evaluation_schema"]["extended"] is False
    assert inputs["phase6_controller"]["modified"] is False
    assert inputs["local_safety_projection"]["modified"] is False
    for name in ("phase6_controller", "local_safety_projection", "matched_streams",
                 "snapshot", "utility_reducers", "candidate_enumerator"):
        entry = inputs[name]
        digest = hashlib.sha256(pathlib.Path(entry["path"]).read_bytes()).hexdigest()
        assert digest == entry["sha256"], name
    assert inputs["phase8_targets_module"]["sha256"] == hashlib.sha256(
        pathlib.Path("rvt_swarm/phase8/targets.py").read_bytes()).hexdigest()
    view = inputs["robot_view"]
    for old_field, path_field in (
        ("definition_sha256", "definition_path"),
        ("builder_sha256", "builder_path"),
    ):
        path = pathlib.Path(view[path_field])
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != view[old_field]:
            additive = S3Z["runtime_files"][str(path)]
            assert additive["before_sha256"] == view[old_field]
            assert additive["after_sha256"] == digest
        else:
            assert view[old_field] == digest
    assert S3Z["consumer_boundary"][
        "residual_expert_canonical_view_hash_includes_new_fields"
    ] is False
    assert view["richer_expert_only_view_created"] is False


def test_binding_records_the_producer_and_its_refactor_evidence() -> None:
    producer = BINDING["producer"]
    digest = hashlib.sha256(pathlib.Path(producer["path"]).read_bytes()).hexdigest()
    assert digest == producer["sha256"]
    assert producer["session_refactor"]["behaviour_identical"] is True
    assert "v6" in producer["session_refactor"]["evidence"]
    assert BINDING["producer_implemented"] is True
    assert BINDING["candidate_set"]["count"] == 9
    assert BINDING["candidate_set"][
        "phase8_fixture_candidate_values_required_to_match"] is False


def test_binding_records_all_audits_as_passing() -> None:
    audits = BINDING["audits"]
    for gate in ("selector_equivalence", "hidden_global_intervention",
                 "one_hop_non_vacuity", "provenance_negative_test", "determinism_repeat",
                 "candidate_order_independence", "identical_snapshot_per_candidate",
                 "matched_exogenous_streams", "one_interval_intervention",
                 "failure_trajectories_scored", "target_builder_native_frame"):
        assert audits[gate] == "PASS", gate
    assert audits["rb16_rotation_applied"] is False
    assert BINDING["rb16"]["PRIMARY_SYNTHETIC_ROTATION_AUGMENTATION"] == "DISABLED"
    assert BINDING["rb16"]["started"] is False


def test_no_scientific_data_was_generated() -> None:
    isolation = BINDING["isolation"]
    for key in ("locality_violations", "final_test_access_count",
                "study_a_n24_access_count", "recoverability_rows", "residual_rows",
                "scientific_shards", "new_fd24_checkpoints", "optimizer_states",
                "training_operations"):
        assert isolation[key] == 0, key
    residual_audit = json.loads(
        (ROOT / "datasets" / "phase9_residual_audit.json").read_text())
    assert residual_audit["emitted_rows"] == 0
    assert residual_audit["expert_calls"] == 0
    assert BINDING["generation"]["official_residual_generation_run"] is False


def test_headroom_authority_chain_is_referenced_and_unmodified() -> None:
    provenance = BINDING["headroom_provenance"]
    assert provenance["modified"] is False
    assert provenance["H2_PRE_DATA_VIABILITY"] is True
    assert provenance["H2_EMPIRICALLY_CONFIRMED"] is False
    v6 = json.loads((ROOT / "headroom_requalification_v6.json").read_text())
    assert v6["headroom_requalification_v6_sha256"] == provenance[
        "headroom_requalification_v6_sha256"]
