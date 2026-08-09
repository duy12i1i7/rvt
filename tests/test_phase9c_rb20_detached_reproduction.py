"""RB-20 -- clean detached reproducibility evidence.

The replay itself ran from a detached checkout of the execution source commit;
these tests pin what it produced and the properties that must hold regardless:
that the comparison excluded no scientific field, that the provenance delta is
metadata-only, and that nothing official was written.
"""

from __future__ import annotations

import hashlib
import json
import pathlib

from rvt_swarm.phase8.common import canonical_json_bytes

ROOT = pathlib.Path("results/rvt_fd24")
RB20 = json.loads((ROOT / "rb20_clean_detached_reproduction_v1.json").read_text())
RB18 = json.loads((ROOT / "rb18_structural_generation_canary_v1.json").read_text())
RB17 = json.loads((ROOT / "rb17_generation_contract_composite_v1.json").read_text())
CURRENT_ROOT = json.loads(
    (ROOT / "rb19_current_generation_provenance_v1.json").read_text())
TARGET = json.loads((ROOT / "target_v4_execution_contract_v1.json").read_text())
BUDGET1 = json.loads((ROOT / "datasets" / "generation_budget_v1.json").read_text())

EXECUTION_SOURCE_COMMIT = "53a51f9a9e0b169c016742313b31c59e4cccbae6"


def test_artifact_is_self_consistent() -> None:
    body = {k: v for k, v in RB20.items()
            if k != "rb20_clean_detached_reproduction_sha256"}
    assert hashlib.sha256(canonical_json_bytes(body)).hexdigest() == RB20[
        "rb20_clean_detached_reproduction_sha256"]
    assert RB20["schema_version"] == "rvt-rb20-clean-detached-reproduction/v1"
    assert RB20["provenance_class"] == "RUNTIME_CONFORMANCE_ONLY"


# ---------------------------------------------------------------------------
# RB20-0/1/2/24 -- two-commit rule, detached execution, cleanliness
# ---------------------------------------------------------------------------
def test_execution_happened_from_the_clean_detached_source_commit() -> None:
    assert RB20["execution_source_commit"] == EXECUTION_SOURCE_COMMIT
    execution = RB20["execution"]
    assert execution["detached_head"] == EXECUTION_SOURCE_COMMIT
    assert execution["head_matches_execution_source_commit"] is True
    assert execution["reused_development_tree"] is False
    assert execution["detached_status_porcelain_lines_before"] == 0
    assert execution["detached_status_porcelain_lines_after"] == 0
    assert execution["outputs_written_inside_the_tracked_tree"] is False
    assert RB20["writer_replay"]["written_outside_the_tracked_tree"] is True


def test_the_environment_is_recorded_without_becoming_a_scientific_input() -> None:
    environment = RB20["environment"]
    for field in ("platform", "machine", "python_version", "torch_version",
                  "numpy_version", "execution_source_commit", "detached_path"):
        assert environment[field], field
    assert environment["environment_values_are_scientific_inputs"] is False


# ---------------------------------------------------------------------------
# RB20-3 -- current root
# ---------------------------------------------------------------------------
def test_the_current_root_validated_from_the_detached_checkout() -> None:
    root = RB20["current_root"]
    assert root["sha256"] == CURRENT_ROOT[
        "rb19_current_generation_provenance_sha256"] == (
        "e8317ad3e9facc76511098503cdad55dfc065dedd8fc2b530a2b25845c3f5571")
    assert root["self_consistent"] is True
    assert root["missing_required_contracts"] == []
    assert root["ambiguous_current_contracts"] == []
    assert root["current_nodes_pointing_only_to_superseded"] == []
    assert root["target_v4_matches_contract"] is True
    assert root["target_v4_explicitly_cited"] is True
    assert root["target_v4_sha256"] == TARGET["target_v4_execution_contract_sha256"] == (
        "54a0e0baff79fbdc320800b772f47a40ac06ac4f0e70d4fab1bf676c54b918ee")


# ---------------------------------------------------------------------------
# RB20-4/5 -- the exact manifest and the source episodes
# ---------------------------------------------------------------------------
def test_the_exact_rb18_manifest_was_replayed() -> None:
    manifest = RB20["rb18_case_manifest"]
    assert manifest["read_from_committed_artifact"] is True
    assert manifest["replacement_case_used"] is False
    assert manifest["replayed"] is True
    assert manifest["cases"] == RB18["predeclared_cases"]
    identities = {(case["layout_id"], case["family"], case["team_size"], case["policy"])
                  for case in manifest["cases"]}
    assert ("train-f1-00", "F1", 6, "S1_ALWAYS_COMPACT") in identities
    assert ("train-f9-00", "F9", 12, "S0_SCRIPTED_DIAGNOSTIC") in identities
    assert ("validation-f8-00", "F8", 5, "S1_ALWAYS_COMPACT") in identities
    assert ("train-f5-00", "F5", 8, "S1_ALWAYS_COMPACT") in identities


def test_all_four_source_episodes_reproduced_exactly() -> None:
    comparison = RB20["source_episode_comparison"]
    assert comparison["episodes"] == 4
    assert comparison["exact_matches"] == 4
    assert comparison["mismatches"] == []


# ---------------------------------------------------------------------------
# RB20-6/7/8 -- recoverability
# ---------------------------------------------------------------------------
def test_all_fourteen_rollouts_reproduced_exactly() -> None:
    replay = RB20["recoverability_replay"]
    assert replay["decision_states"] == 3
    assert replay["candidate_rollouts"] == 14
    assert replay["rollouts_exactly_matched"] == 14
    assert replay["replica_rule"] == {"F8": 3, "F9": 3, "other": 1}
    assert replay["changed_topology_lifecycle_reproduced"] is True
    assert replay["determinism"]["identical"] is True


def test_aggregation_was_recomputed_from_raw_replicas() -> None:
    replay = RB20["recoverability_replay"]
    assert replay["aggregation_recomputed_from_raw_replicas"] is True
    assert replay["aggregate_positive"] == RB18["counts"]["recoverability"][
        "valid_positive_labels"] == 4
    assert replay["aggregate_negative"] == RB18["counts"]["recoverability"][
        "valid_negative_labels"] == 2
    assert replay["aggregate_invalid"] == 0


# ---------------------------------------------------------------------------
# RB20-9/10/11 -- residual
# ---------------------------------------------------------------------------
def test_all_thirty_six_candidate_evaluations_reproduced_exactly() -> None:
    replay = RB20["residual_replay"]
    assert replay["decision_states"] == 4
    assert replay["states_exactly_matched"] == 4
    assert replay["candidate_evaluations"] == 36
    assert replay["utility_records_compared"] == 36
    assert replay["utility_records_exactly_matched"] == 36


def test_dispositions_were_recomputed_and_match() -> None:
    replay = RB20["residual_replay"]
    counts = replay["counts"]
    assert counts["attempted_expert_decision_states"] == 4
    assert counts["labeled_states"] == 3
    assert counts["no_eligible_states"] == 1
    assert counts["execution_invalid_states"] == 0
    assert counts["target_rows_emitted"] == 3
    assert replay["counts_consistent"] is True
    assert replay["counts_match_rb18"] is True
    assert replay["no_eligible_target_rows"] == 0
    assert replay["fallback_created"] is False


# ---------------------------------------------------------------------------
# RB20-19/20 -- the semantic projection and the provenance delta
# ---------------------------------------------------------------------------
def test_the_semantic_projection_matches_exactly() -> None:
    projection = RB20["semantic_projection"]
    assert projection["exact_match"] is True
    assert projection["semantic_mismatch_count"] == 0
    assert projection["rb18_projection_sha256"] == projection["rb20_projection_sha256"]


def test_the_exclusion_list_is_explicit_minimal_and_excludes_nothing_scientific(
        ) -> None:
    projection = RB20["semantic_projection"]
    for forbidden in ("labels_excluded", "raw_predicates_excluded", "streams_excluded",
                      "identities_excluded", "targets_excluded", "utilities_excluded",
                      "dispositions_excluded", "traces_excluded",
                      "source_outcomes_excluded", "schema_payloads_excluded"):
        assert projection[forbidden] is False, forbidden
    excluded = set(projection["excluded_top_level"])
    assert excluded == {"source_commit", "contract_root", "timing",
                        "rb18_structural_generation_canary_sha256", "schema_version",
                        "provenance_class", "SCIENTIFIC_DATASET", "canary_namespace",
                        "environment", "current_root"}
    assert projection["excluded_per_residual_record"] == ["seconds"]
    included = set(projection["included_top_level"])
    for required in ("source", "recoverability", "residual", "residual_counts",
                     "schema_round_trip", "world_target_round_trip", "chunking",
                     "retry", "residual_determinism", "dry_run_writer",
                     "namespace_coexistence", "counts", "predeclared_cases"):
        assert required in included, required
    assert not (included & excluded)


def test_the_provenance_delta_is_metadata_only() -> None:
    delta = RB20["provenance_delta"]
    assert delta["rb18_referenced_root"] == RB17[
        "rb17_generation_contract_composite_sha256"]
    assert delta["rb18_root_status"] == "SUPERSEDED_EVIDENCE"
    assert delta["rb18_root_cited_target_v4"] is False
    assert delta["rb20_referenced_root"] == CURRENT_ROOT[
        "rb19_current_generation_provenance_sha256"]
    assert delta["rb20_root_cites_target_v4"] is True
    assert delta["scientific_fields_changed_by_the_repair"] == 0
    assert delta["delta_is_metadata_only"] is True


# ---------------------------------------------------------------------------
# RB20-12..18 -- schema, identities, chunking, retry, writer
# ---------------------------------------------------------------------------
def test_model_input_and_semantics_round_trip_on_replay() -> None:
    trips = RB20["schema_round_trip_replay"]
    assert len(trips) == 3
    for trip in trips:
        for field in ("orientation_exact", "node_tensor_identical",
                      "edge_tensor_identical", "edge_index_identical",
                      "candidate_context_identical", "residual_output_identical",
                      "recoverability_logit_identical",
                      "row_payload_round_trip_exact"):
            assert trip[field] is True, (trip["case_id"], field)


def test_world_plumbing_reproduces() -> None:
    trip = RB20["world_target_round_trip_replay"]
    assert trip["frame"] == "WORLD"
    assert trip["x_preserved"] and trip["y_preserved"]
    assert trip["sign_preserved"] and trip["scale_preserved"]
    assert trip["no_rotation"] is True
    assert trip["input"] == trip["recovered"]


def test_identities_were_recomputed_not_reused() -> None:
    identity = RB20["identity_replay"]
    assert identity["recomputed_not_reused"] is True
    assert identity["candidate_index_in_scientific_row_identity"] is False
    assert identity["distinct_candidate_ids_per_decision"] == [9]
    namespaces = identity["namespaces"]
    assert namespaces["residual_row_vs_candidate_collision"] is False
    assert namespaces["residual_vs_recoverability_collision"] is False
    assert namespaces["residual_candidate_ids"] == 36
    assert namespaces["recoverability_evaluation_ids"] == 14


def test_chunking_and_retry_remain_scientifically_invariant_on_replay() -> None:
    assert RB20["chunking_replay"]["identical_after_canonical_sort"] is True
    assert RB20["chunking_replay"]["execution_ids_differ"] is True
    retry = RB20["retry_replay"]
    assert retry["scientific_view_identical"] is True
    assert retry["execution_attempt_id_differs"] is True
    assert retry["disposition_stable"] is True
    assert retry["row_sha256_stable"] is True
    determinism = RB20["residual_determinism_replay"]
    for field in ("result_digest_stable", "candidate_ids_stable", "sidecar_stable",
                  "target_stable", "row_sha256_stable"):
        assert determinism[field] is True, field


def test_the_dry_run_writer_reproduced_outside_the_tracked_tree() -> None:
    writer = RB20["writer_replay"]
    assert writer["mode"] == "RUNTIME_CONFORMANCE_ONLY"
    assert writer["official_shard_paths_written"] == 0
    assert len(writer["records"]) == 3
    for record in writer["records"]:
        assert record["readback_exact"] is True
        assert record["written_sha256"] == record["readback_sha256"]
    committed = [record["written_sha256"]
                 for record in RB18["dry_run_writer"]["records"]]
    assert [record["written_sha256"] for record in writer["records"]] == committed


# ---------------------------------------------------------------------------
# RB20-21/22/23/26 -- preflight, regressions, suite, no repair
# ---------------------------------------------------------------------------
def test_preflight_reproduced_positively_and_rejected_every_negative() -> None:
    preflight = RB20["preflight_replay"]
    assert preflight["positive_status"] == "PASS"
    assert preflight["positive_failures"] == 0
    assert preflight["positive_checks"] == 53
    assert preflight["negative_cases"] == 12
    assert preflight["negative_escapes"] == 0
    for required in ("missing Target V4", "wrong Target V4 hash", "failed RB16 current",
                     "MISSION output current", "missing orientation",
                     "candidate count != 9", "KEEP online", "no-eligible fallback",
                     "N24 seal broken", "final-test seal broken",
                     "1800s timeout authoritative", "prematurely authorized"):
        assert required in preflight["cases"], required


def test_critical_regressions_and_the_full_suite_passed_from_the_source_commit() -> None:
    regressions = RB20["critical_regressions"]
    assert regressions["failed"] == 0
    assert regressions["passed"] == 257
    for module in ("transport_semantics", "target_v4_epoch_isolation",
                   "rb15_v2_producer", "phase5r_world_output_repair",
                   "rb18_structural_canary", "rb19_final_semantic_audit"):
        assert module in regressions["modules"], module
    suite = RB20["full_suite_from_execution_source_commit"]
    assert suite == {"passed": 2922, "failed": 0, "xfailed": 0, "xpassed": 0}


def test_no_semantic_repair_was_performed_in_rb20() -> None:
    assert RB20["semantic_repair_performed"] is False


# ---------------------------------------------------------------------------
# RB20-29 -- isolation
# ---------------------------------------------------------------------------
def test_official_counters_are_zero() -> None:
    for key, value in RB20["official_counters"].items():
        assert value == 0, key
    residual_audit = json.loads(
        (ROOT / "datasets" / "phase9_residual_audit.json").read_text())
    assert residual_audit["emitted_rows"] == 0
    assert residual_audit["expert_calls"] == 0
    assert BUDGET1["scientific_dataset_records_generated"] == 0
    assert BUDGET1["training_operations"] == 0


def test_sealed_domains_survived_the_replay() -> None:
    protocol = json.loads(
        (ROOT / "executable_scientific_protocol_v1.json").read_text())
    assert protocol["final_test_access_policy"]["runtime_access_count"] == 0
    assert not (ROOT / "layout_execution_specifications" / "final_test").exists()
    assert sorted(path.name for path
                  in (ROOT / "datasets" / "study_a_n24_eval_sealed").iterdir()) == [
        "namespace_manifest.json"]
    assert 24 not in {case["team_size"] for case in RB20["rb18_case_manifest"]["cases"]}


def test_upstream_artifacts_are_unchanged() -> None:
    for name, field, expected in (
            ("rb18_structural_generation_canary_v1",
             "rb18_structural_generation_canary_sha256",
             "0291cb52e11e570f48272d76b98d32966513fc8f840a6e47e718076bf3187e3c"),
            ("rb17_generation_contract_composite_v1",
             "rb17_generation_contract_composite_sha256",
             "bba1aee0430bc540f20d010b923696b5b1c51d4bfb1d92d2fa21daf2e6242da8"),
            ("rb19_current_generation_provenance_v1",
             "rb19_current_generation_provenance_sha256",
             "e8317ad3e9facc76511098503cdad55dfc065dedd8fc2b530a2b25845c3f5571"),
            ("headroom_requalification_v6", "headroom_requalification_v6_sha256",
             "d044d6b99d7a2bbb83565b121d188a35e335bfd856e3eb0e885823ca1a6742ef")):
        assert json.loads((ROOT / f"{name}.json").read_text())[field] == expected, name
