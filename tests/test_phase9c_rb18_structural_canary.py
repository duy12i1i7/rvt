"""RB-18 -- structural generation canary.

The canary itself is an expensive end-to-end sweep, so these tests pin what it
recorded plus the semantics that must hold independently: that the contract root
gap is reported rather than papered over, that NO_ELIGIBLE_ACTION can never be
serialized as EXECUTION_INVALID, that preflight stays strict, and that no
official counter moved.
"""

from __future__ import annotations

import hashlib
import json
import pathlib

import pytest

from rvt_swarm.phase8.common import canonical_json_bytes
from rvt_swarm.phase9.preflight import build_preflight_audit, residual_v2_contract_checks
from rvt_swarm.phase9c_rb.counterfactual import replica_count_for_family
from rvt_swarm.phase9c_rb.generation_contract import (
    DISPOSITIONS, EMITS_TARGET_ROW, EXECUTION_INVALID, LABELED, NO_ELIGIBLE_ACTION,
    RESIDUAL_SUPERVISION_ROW_SCHEMA_VERSION, GenerationContractError,
    ResidualSupervisionRowV2,
)

ROOT = pathlib.Path("results/rvt_fd24")
CANARY = json.loads(
    (ROOT / "rb18_structural_generation_canary_v1.json").read_text())
COMPOSITE = json.loads(
    (ROOT / "rb17_generation_contract_composite_v1.json").read_text())
PROTOCOL = json.loads((ROOT / "executable_scientific_protocol_v1.json").read_text())
BUDGET_V1 = json.loads((ROOT / "datasets" / "generation_budget_v1.json").read_text())
CANARY_DIR = ROOT / "rb18_canary"


def test_canary_artifact_is_self_consistent_and_diagnostic() -> None:
    body = {k: v for k, v in CANARY.items()
            if k != "rb18_structural_generation_canary_sha256"}
    assert hashlib.sha256(canonical_json_bytes(body)).hexdigest() == CANARY[
        "rb18_structural_generation_canary_sha256"]
    assert CANARY["schema_version"] == "rvt-rb18-structural-generation-canary/v1"
    assert CANARY["provenance_class"] == "RUNTIME_CONFORMANCE_ONLY"
    assert CANARY["SCIENTIFIC_DATASET"] is False
    assert CANARY["canary_namespace"] == "results/rvt_fd24/rb18_canary"


# ---------------------------------------------------------------------------
# RB18-0 -- the contract root, and the gap it exposed
# ---------------------------------------------------------------------------
def test_the_rb17_root_is_the_only_provenance_used() -> None:
    root = CANARY["contract_root"]
    assert root["rb17_generation_contract_composite_sha256"] == COMPOSITE[
        "rb17_generation_contract_composite_sha256"]
    resolved = root["resolved_from_root"]
    for required in ("source_scientific_protocol", "et_timing_addendum",
                     "headroom_authority", "residual_expert_spec_v2", "rb15_binding",
                     "model_residual_output_frame_v2", "residual_runtime_composite",
                     "scientific_row_identity", "candidate_evaluation_identity",
                     "execution_attempt_identity", "disposition_contract",
                     "supervision_row_schema", "generation_budget_v2"):
        assert required in resolved, required


def test_the_target_v4_provenance_gap_is_reported_not_hidden() -> None:
    """RB18-0 found the one reference the RB17 root does not reach."""
    root = CANARY["contract_root"]
    assert root["target_v4_reachable_from_root"] is False
    assert "Target V4" in root["target_v4_gap"]
    bound = root["target_v4_bound_additively_here"]
    assert bound["path"] == "results/rvt_fd24/target_v4_execution_contract_v1.json"
    assert bound["rb17_composite_rewritten"] is False
    # the project identifies that contract by its embedded canonical self-hash,
    # the same value headroom v6 records in protocol_hashes
    contract = json.loads(
        (ROOT / "target_v4_execution_contract_v1.json").read_text())
    assert bound["sha256"] == contract["target_v4_execution_contract_sha256"]
    v6 = json.loads((ROOT / "headroom_requalification_v6.json").read_text())
    assert bound["sha256"] == v6["protocol_hashes"]["target_v4_execution_contract"]
    # the RB17 composite really is untouched
    assert COMPOSITE["rb17_generation_contract_composite_sha256"] == (
        "bba1aee0430bc540f20d010b923696b5b1c51d4bfb1d92d2fa21daf2e6242da8")


# ---------------------------------------------------------------------------
# RB18-3/4/5/6 -- predeclared cases and source episodes
# ---------------------------------------------------------------------------
def test_cases_were_predeclared_with_the_required_diversity() -> None:
    cases = CANARY["predeclared_cases"]
    families = {case["family"] for case in cases}
    sizes = {case["team_size"] for case in cases}
    assert {"F1", "F8", "F9"} <= families
    assert families & {"F5"}
    assert len(sizes) >= 2 and min(sizes) <= 6 and max(sizes) >= 8
    assert 24 not in sizes
    assert all(case["split"] in ("train", "validation") for case in cases)
    assert all("role" in case and case["role"] for case in cases)


def test_source_episodes_ran_without_schedule_mutation() -> None:
    source = CANARY["source"]
    assert len(source) == len(CANARY["predeclared_cases"])
    for record in source:
        assert record["event_schedule_mutated"] is False
        assert record["replica_count"] == replica_count_for_family(record["family"])
        assert record["control_step"] >= 0
    counts = CANARY["counts"]["source"]
    assert counts["source_episodes"] == len(source)
    assert counts["unreachable_due_to_early_termination"] == sum(
        1 for record in source if record["terminated_before_decision_step"])


# ---------------------------------------------------------------------------
# RB18-7..10 -- recoverability branch
# ---------------------------------------------------------------------------
def test_recoverability_ran_through_target_v4_with_frozen_replicas() -> None:
    records = CANARY["recoverability"]
    assert records
    for record in records:
        assert record["topology_candidates"] == [2, 5]
        expected = replica_count_for_family(record["family"])
        assert record["replicas_per_candidate"] == expected
        assert record["candidate_rollouts"] == 2 * expected
        assert len(record["replica_records"]) == record["candidate_rollouts"]
        for replica in record["replica_records"]:
            assert replica["target_v4_disposition"] in (
                "RECOVERABLE_POSITIVE", "VALID_TASK_NEGATIVE", "GENERATION_INVALID")
            assert replica["snapshot_sha256"] == record["decision_snapshot_sha256"]
            assert "failed_predicates" in replica


def test_f8_and_f9_used_three_matched_replicas() -> None:
    by_family = {record["family"]: record for record in CANARY["recoverability"]}
    for family in ("F8", "F9"):
        assert by_family[family]["replicas_per_candidate"] == 3
        assert by_family[family]["candidate_rollouts"] == 6
    assert by_family["F1"]["replicas_per_candidate"] == 1


def test_at_least_one_changed_topology_lifecycle_executed() -> None:
    assert any(record["changed_topology_lifecycle_created"]
               for record in CANARY["recoverability"])


def test_recoverability_reruns_are_bit_identical() -> None:
    determinism = CANARY["recoverability_determinism"]
    assert determinism["identical"] is True
    assert determinism["first_digest"] == determinism["second_digest"]


def test_raw_failure_causes_are_preserved_before_target_v4_mapping() -> None:
    for record in CANARY["recoverability"]:
        for replica in record["replica_records"]:
            assert "termination_cause" in replica
            assert "failed_predicates" in replica
            assert "control_steps" in replica
            # the raw cause is not collapsed into the disposition
            assert replica["termination_cause"] != replica["target_v4_disposition"]


# ---------------------------------------------------------------------------
# RB18-11..14 -- residual branch and dispositions
# ---------------------------------------------------------------------------
def test_every_residual_state_ran_all_nine_candidates() -> None:
    for task in CANARY["residual"]:
        assert task["candidate_evaluations"] == 9
        assert task["distinct_candidate_ids"] == 9
        assert len(task["candidate_sidecar"]) == 9
        assert task["disposition"] in DISPOSITIONS


def test_the_canary_contains_a_labeled_state_with_one_row() -> None:
    labeled = [task for task in CANARY["residual"] if task["disposition"] == LABELED]
    assert labeled
    for task in labeled:
        assert task["prospective_rows"] == 1
        assert task["selected_candidate_index"] is not None
        assert task["residual_target_world_acceleration"] is not None
        assert len(task["residual_target_world_acceleration"]) == 2
        assert len(task["mission_orientation_cos_sin"]) == 2
        assert task["prospective_row_sha256"]
        assert task["selector_error"] is None


def test_the_canary_contains_a_no_eligible_state_with_no_row() -> None:
    no_eligible = [task for task in CANARY["residual"]
                   if task["disposition"] == NO_ELIGIBLE_ACTION]
    assert len(no_eligible) >= 1
    for task in no_eligible:
        assert task["prospective_rows"] == 0
        assert task["prospective_row_sha256"] is None
        assert task["residual_target_world_acceleration"] is None
        assert task["selected_candidate_index"] is None
        assert "no eligible" in task["selector_error"]
        # the nine evaluation identities still exist as audit evidence
        assert task["distinct_candidate_ids"] == 9


def test_disposition_counts_are_consistent_and_keep_the_denominator() -> None:
    counts = CANARY["residual_counts"]
    assert CANARY["residual_counts_consistent"] is True
    assert counts["attempted_expert_decision_states"] == (
        counts["labeled_states"] + counts["no_eligible_states"]
        + counts["execution_invalid_states"])
    assert counts["target_rows_emitted"] == counts["labeled_states"]
    assert counts["no_eligible_states"] >= 1
    assert counts["target_rows_emitted"] < counts["attempted_expert_decision_states"]


def test_no_eligible_can_never_be_serialized_as_execution_invalid() -> None:
    assert EMITS_TARGET_ROW[NO_ELIGIBLE_ACTION] is False
    assert EMITS_TARGET_ROW[EXECUTION_INVALID] is False
    assert NO_ELIGIBLE_ACTION != EXECUTION_INVALID
    for disposition in (NO_ELIGIBLE_ACTION, EXECUTION_INVALID):
        with pytest.raises(GenerationContractError, match="only a LABELED"):
            ResidualSupervisionRowV2(
                RESIDUAL_SUPERVISION_ROW_SCHEMA_VERSION, "r" * 64,
                {"residual_target_world_acceleration": (0.0, 0.0)}, (1.0, 0.0),
                "e" * 64, "rvt-ego-graph/v2", "rvt-fd24-model-input/v2",
                "rvt-fd24-model/v2", "s" * 64, "x" * 64, "d" * 64, "m" * 64,
                4, "c" * 64, disposition)


def test_an_ordinary_candidate_failure_is_still_a_valid_outcome() -> None:
    """A collision inside a counterfactual is a label, not an execution invalidity."""
    terminations = {item["termination"] for task in CANARY["residual"]
                    for item in task["candidate_sidecar"]}
    assert terminations <= {"GOAL_COMPLETE", "COLLISION", "HORIZON_COMPLETE",
                            "PERSISTENT_DEADLOCK", "WORLD_BOUNDARY_EXIT",
                            "IRREVERSIBLE_PROGRESS_LOSS", "NUMERICAL_INVALID"}
    assert CANARY["residual_counts"]["execution_invalid_states"] == 0


# ---------------------------------------------------------------------------
# RB18-15..18 -- schema, loader and model round trip
# ---------------------------------------------------------------------------
def test_every_labeled_row_round_trips_through_the_loader_and_model() -> None:
    trips = CANARY["schema_round_trip"]
    assert len(trips) == CANARY["residual_counts"]["labeled_states"]
    for trip in trips:
        for field in ("orientation_exact", "node_tensor_identical",
                      "edge_tensor_identical", "edge_index_identical",
                      "candidate_context_identical", "residual_output_identical",
                      "recoverability_logit_identical",
                      "row_payload_round_trip_exact"):
            assert trip[field] is True, (trip["case_id"], field)
        assert len(trip["orientation"]) == 2
        assert len(trip["target_world"]) == 2


def test_a_non_symmetric_world_target_survives_the_writer_path() -> None:
    trip = CANARY["world_target_round_trip"]
    assert trip["frame"] == "WORLD"
    assert trip["x_preserved"] and trip["y_preserved"]
    assert trip["sign_preserved"] and trip["scale_preserved"]
    assert trip["no_rotation"] is True
    assert trip["input"] == trip["recovered"]
    assert trip["input"][0] != trip["input"][1]
    assert abs(trip["input"][0]) != abs(trip["input"][1])


# ---------------------------------------------------------------------------
# RB18-19..23 -- identity, chunking, retry, determinism
# ---------------------------------------------------------------------------
def test_scientific_identity_never_contains_a_candidate_index() -> None:
    identity = json.loads(
        (ROOT / "residual_scientific_row_identity_v2.json").read_text())
    assert identity["candidate_index_in_identity"] is False
    for task in CANARY["residual"]:
        assert task["scientific_row_id"] not in task["candidate_evaluation_ids"]
    all_rows = {task["scientific_row_id"] for task in CANARY["residual"]}
    assert len(all_rows) == len(CANARY["residual"])


def test_chunking_does_not_change_any_scientific_output() -> None:
    chunking = CANARY["chunking"]
    assert chunking["identical_after_canonical_sort"] is True
    assert chunking["execution_ids_differ"] is True
    assert chunking["partition_a_tasks"] == chunking["partition_b_tasks"] >= 2


def test_an_infrastructure_retry_changes_only_execution_metadata() -> None:
    retry = CANARY["retry"]
    assert retry["scientific_view_identical"] is True
    assert retry["execution_attempt_id_differs"] is True
    assert retry["disposition_stable"] is True
    assert retry["row_sha256_stable"] is True


def test_residual_reruns_are_bit_identical() -> None:
    determinism = CANARY["residual_determinism"]
    for field in ("result_digest_stable", "candidate_ids_stable", "sidecar_stable",
                  "target_stable", "row_sha256_stable"):
        assert determinism[field] is True, field


# ---------------------------------------------------------------------------
# RB18-24/25 -- writer and namespaces
# ---------------------------------------------------------------------------
def test_the_dry_run_writer_used_official_encoding_and_read_back() -> None:
    writer = CANARY["dry_run_writer"]
    assert writer["mode"] == "RUNTIME_CONFORMANCE_ONLY"
    assert "canonical" in writer["encoding"]
    assert writer["official_shard_paths_written"] == 0
    assert writer["records"]
    for record in writer["records"]:
        assert record["readback_exact"] is True
        assert record["written_sha256"] == record["readback_sha256"]
        assert record["path"].startswith("results/rvt_fd24/rb18_canary/")
    assert CANARY_DIR.exists()
    written = sorted(path.name for path in CANARY_DIR.iterdir())
    assert len(written) == len(writer["records"]) + 1     # rows plus the sidecar
    assert "candidate_audit_sidecar.json" in written


def test_the_canary_wrote_nothing_under_an_official_path() -> None:
    datasets = ROOT / "datasets"
    for name in ("study_a_zero_shot", "study_a_n24_eval_sealed", "study_b_with_n24"):
        entries = sorted(path.name for path in (datasets / name).iterdir())
        assert entries == ["namespace_manifest.json"], (name, entries)
    assert not any(ROOT.glob("**/*.shard"))
    assert not any(ROOT.glob("**/*.parquet"))


def test_recoverability_and_residual_namespaces_do_not_collide() -> None:
    namespaces = CANARY["namespace_coexistence"]
    assert namespaces["residual_row_vs_candidate_collision"] is False
    assert namespaces["residual_vs_recoverability_collision"] is False
    assert namespaces["namespaces_explicit"] is True
    assert namespaces["recoverability_evaluation_ids"] == CANARY["counts"][
        "recoverability"]["candidate_rollouts"]
    assert namespaces["residual_candidate_ids"] == 9 * len(CANARY["residual"])


# ---------------------------------------------------------------------------
# RB18-26 -- preflight stays strict
# ---------------------------------------------------------------------------
def test_preflight_passes_before_and_after_the_canary() -> None:
    audit = build_preflight_audit(pathlib.Path("."))
    assert audit["status"] == "PASS"
    assert all(check["passed"] for check in audit["checks"])


@pytest.mark.parametrize("file_name,path,value,check_name", [
    ("residual_supervision_row_schema_v2.json",
     ["model_schema_pins", "output_components"],
     ["mission_longitudinal_acceleration", "mission_lateral_acceleration"],
     "residual_v2_model_frame_is_world"),
    ("residual_supervision_row_schema_v2.json", ["added_fields"], {},
     "residual_v2_orientation_context_present"),
    ("residual_scientific_row_identity_v2.json", ["candidate_index_in_identity"], True,
     "residual_v2_row_identity_excludes_candidate_index"),
    ("generation_budget_v2.json",
     ["timeout", "historical_value_authoritative_for_v2"], True,
     "residual_v2_timeout_not_stale"),
    ("rb16_world_output_requalification_v1.json",
     ["augmentation", "PRIMARY_SYNTHETIC_ROTATION_AUGMENTATION"], "ENABLED",
     "residual_v2_no_synthetic_augmentation"),
    ("residual_generation_disposition_contract_v1.json", ["dispositions"],
     ["LABELED", "MYSTERY"], "residual_v2_disposition_vocabulary"),
])
def test_preflight_still_rejects_each_stale_contract_after_the_canary(
        tmp_path, file_name, path, value, check_name) -> None:
    import shutil
    shutil.copytree("results", tmp_path / "results")
    target = tmp_path / "results/rvt_fd24" / file_name
    document = json.loads(target.read_text())
    node = document
    for step in path[:-1]:
        node = node[step]
    node[path[-1]] = value
    target.write_text(json.dumps(document, indent=1, sort_keys=True) + "\n")

    checks = residual_v2_contract_checks(tmp_path)
    failed = {check["name"] for check in checks if not check["passed"]}
    assert failed, "a mutated contract must fail at least one check"
    assert check_name in failed or any(
        name.startswith("residual_v2_contract_hash") for name in failed)


# ---------------------------------------------------------------------------
# RB18-27/28 -- observability only, and the official counters
# ---------------------------------------------------------------------------
def test_timing_is_observability_only() -> None:
    timing = CANARY["timing"]
    assert timing["observability_only"] is True
    assert timing["operational_decision_made"] is False
    assert timing["canary_wall_clock_seconds"] > 0
    for forbidden in ("worker_count", "chunk_size", "job_timeout", "cluster_size"):
        assert forbidden not in timing
    budget = json.loads((ROOT / "generation_budget_v2.json").read_text())
    assert budget["timeout"]["RESIDUAL_V2_GENERATION_TIMEOUT"] == (
        "PENDING_RB21_PERFORMANCE_QUALIFICATION")
    assert budget["chunking"]["chunk_size_frozen"] is False


def test_official_counters_are_all_zero() -> None:
    official = CANARY["counts"]["official"]
    for key, value in official.items():
        assert value == 0, key
    residual_audit = json.loads(
        (ROOT / "datasets" / "phase9_residual_audit.json").read_text())
    assert residual_audit["emitted_rows"] == 0
    assert residual_audit["expert_calls"] == 0
    assert BUDGET_V1["scientific_dataset_records_generated"] == 0
    assert BUDGET_V1["training_operations"] == 0
    assert BUDGET_V1["rollout_jobs_executed"] == 0
    manifest = json.loads((ROOT / "residual_job_manifest_v2.json").read_text())
    assert manifest["official_scientific_execution_status"] == (
        "NOT_AUTHORIZED_PENDING_RB18_RB21")


def test_sealed_domains_were_untouched() -> None:
    assert PROTOCOL["final_test_access_policy"]["runtime_access_count"] == 0
    assert not (ROOT / "layout_execution_specifications" / "final_test").exists()
    assert 24 not in {case["team_size"] for case in CANARY["predeclared_cases"]}
    assert all(case["split"] in ("train", "validation")
               for case in CANARY["predeclared_cases"])


def test_upstream_scientific_semantics_are_unchanged() -> None:
    for name, field, expected in (
            ("residual_expert_spec_v2", "residual_expert_spec_v2_sha256",
             "e3a3093038b31f7f8c11d56be224929c9eccc27e6bde2fa47c5c6c644b7f3fbf"),
            ("residual_label_contract_composite_v2",
             "residual_label_contract_composite_sha256",
             "8921424d0342e26a7a22da4ca042543a8eb08c2dc310f5f5639b70678ceb08ad"),
            ("rb15_residual_expert_binding_v2", "rb15_residual_expert_binding_v2_sha256",
             "9edc8cc8d46b94c76f0fa8e3a2ea07b7bff06fd9d5cfe5f5cb26565170af3f24"),
            ("rb16_world_output_requalification_v1",
             "rb16_world_output_requalification_sha256",
             "10c4aebe41a98db7674f7ee617db8a209a148bdfe18ca76bd04cde59660ab387"),
            ("rb17_generation_contract_composite_v1",
             "rb17_generation_contract_composite_sha256",
             "bba1aee0430bc540f20d010b923696b5b1c51d4bfb1d92d2fa21daf2e6242da8"),
            ("headroom_requalification_v6", "headroom_requalification_v6_sha256",
             "d044d6b99d7a2bbb83565b121d188a35e335bfd856e3eb0e885823ca1a6742ef")):
        assert json.loads((ROOT / f"{name}.json").read_text())[field] == expected, name
    assert BUDGET_V1["generation_budget_sha256"] == (
        "3853b8ad4484d733de9be7d0e27bf273f33e14054f3089f6b5454cc17815846e")
