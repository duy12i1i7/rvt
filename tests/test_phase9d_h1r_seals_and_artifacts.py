"""Phase 9D-H1R -- sealed domains, split isolation, V1 immutability, artifacts.

Protocol V2 is designed prospectively and source-only. Nothing in this phase may
touch Study-A N=24, Study B or the final-test split, mutate the immutable V1
Recoverability dataset, or create any authorization for official generation.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from rvt_swarm.phase8.common import sha256_document, verify_canonical_hash
from rvt_swarm.phase9c_rb.binding import BindingError, load_execution_specification
from rvt_swarm.phase9d_h1r.acquisition_v2 import (
    DEFAULT_K, REALIZED_TRAJECTORY_UNIFORM_K, acquisition_protocol_v2_sha256,
)

ROOT = pathlib.Path("results/rvt_fd24")

ARTIFACTS = {
    "protocol": ("phase9d_h1r_source_acquisition_protocol_v2.json",
                 "phase9d_h1r_source_acquisition_protocol_v2_sha256"),
    "feasibility": ("phase9d_h1r_source_only_feasibility_v1.json",
                    "phase9d_h1r_source_only_feasibility_sha256"),
    "comparison": ("phase9d_h1r_source_acquisition_rule_comparison_v1.json",
                   "phase9d_h1r_source_acquisition_rule_comparison_sha256"),
    "exclusion": ("phase9d_h1r_design_pilot_exclusion_set_v1.json",
                  "phase9d_h1r_design_pilot_exclusion_set_sha256"),
    "budget": ("phase9d_h1r_v2_budget_design_v1.json",
               "phase9d_h1r_v2_budget_design_sha256"),
    "readiness": ("phase9d_h1r_v2_generation_readiness_v1.json",
                  "phase9d_h1r_v2_generation_readiness_sha256"),
}


def load(name: str):
    path, _field = ARTIFACTS[name]
    return json.loads((ROOT / path).read_text(encoding="ascii"))


# ---------------------------------------------------------------------------
# artifacts hash canonically
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("name", sorted(ARTIFACTS))
def test_artifact_hashes_canonically(name: str) -> None:
    path, field = ARTIFACTS[name]
    document = json.loads((ROOT / path).read_text(encoding="ascii"))
    assert verify_canonical_hash(document, field), f"{path} self-hash mismatch"


def test_readiness_composite_binds_every_other_artifact() -> None:
    readiness = load("readiness")
    referenced = readiness["artifacts"]
    for name, (path, field) in ARTIFACTS.items():
        if name == "readiness":
            continue
        document = json.loads((ROOT / path).read_text(encoding="ascii"))
        assert referenced[name]["path"] == f"results/rvt_fd24/{path}"
        assert referenced[name]["sha256"] == document[field]


def test_readiness_binds_the_r2_causal_audit_and_v1_roots() -> None:
    readiness = load("readiness")
    inputs = readiness["input_identity"]
    assert inputs["r2_audit_commit"] == \
        "92668d29c5ea765fc9c1c3ecea23fdc60200b5e6"
    roots = readiness["v1_dataset_roots"]
    assert roots["train_manifest_sha256"] == \
        "4ac3d2cb65a8b5d656a5d982b344466868f8deaa8cef2b93af7ce824e9387caf"
    assert roots["validation_manifest_sha256"] == \
        "c991aa3016b38b524a14d9b7037b63d97c2cbbb7d92279fc5a297b9c55d4989e"
    assert roots["combined_recoverability_root_sha256"] == \
        "7e583ef98184767edfb95387ecc23d2ab266e2137db28a9fbb3badccaa495672"


# ---------------------------------------------------------------------------
# no authorization is created
# ---------------------------------------------------------------------------
def test_no_artifact_authorizes_official_generation() -> None:
    for name in ARTIFACTS:
        document = load(name)
        payload = json.dumps(document)
        assert '"generation_authorized": true' not in payload.lower()
    readiness = load("readiness")
    assert readiness["official_v2_generation_authorized"] is False
    assert readiness["recommendation"] == "DO_NOT_AUTHORIZE_V2_GENERATION"
    assert readiness["residual_v2_authorized"] is False
    assert readiness["training_authorized"] is False


def test_official_counters_are_all_zero() -> None:
    counters = load("readiness")["isolation"]
    for field in ("study_a_n24_dataset_accesses", "study_b_dataset_accesses",
                  "final_test_dataset_accesses", "training_operations",
                  "hyperparameter_trials", "model_checkpoints", "optimizer_states",
                  "official_v2_recoverability_rows", "official_v2_candidate_rollouts",
                  "residual_v2_generation_operations", "v1_dataset_mutations"):
        assert counters[field] == 0, field


# ---------------------------------------------------------------------------
# sealed domains
# ---------------------------------------------------------------------------
def test_study_a_n24_namespace_holds_only_its_manifest() -> None:
    namespace = ROOT / "datasets" / "study_a_n24_eval_sealed"
    assert sorted(p.name for p in namespace.iterdir()) == ["namespace_manifest.json"]
    manifest = json.loads((namespace / "namespace_manifest.json").read_text())
    assert manifest["record_count"] == 0
    assert manifest["purpose"] == "zero_shot_size_evaluation_only"


def test_study_b_namespace_holds_only_its_manifest() -> None:
    namespace = ROOT / "datasets" / "study_b_with_n24"
    assert sorted(p.name for p in namespace.iterdir()) == ["namespace_manifest.json"]
    assert json.loads(
        (namespace / "namespace_manifest.json").read_text())["record_count"] == 0


def test_final_test_geometry_is_not_runtime_loadable() -> None:
    with pytest.raises(BindingError):
        load_execution_specification(ROOT, "final_test", "final-test-f1-00")
    assert not (ROOT / "layout_execution_specifications" / "final_test").exists()


def test_the_pilot_touched_no_sealed_domain() -> None:
    feasibility = load("feasibility")
    domain = feasibility["design_pilot_domain"]
    assert 24 not in domain["team_sizes"]
    assert domain["study"] == "study_a_design_pilot"
    assert domain["layout_split"] in ("train", "validation")
    assert feasibility["sealed_domain_accesses"] == {
        "study_a_n24": 0, "study_b": 0, "final_test": 0}


def test_no_pilot_identity_uses_an_official_split() -> None:
    exclusion = load("exclusion")
    for entry in exclusion["excluded_identities"]:
        assert entry["split"] == "design_pilot"
        assert entry["study"] == "study_a_design_pilot"
        assert entry["team_size"] != 24


# ---------------------------------------------------------------------------
# V1 immutability
# ---------------------------------------------------------------------------
def test_v1_recoverability_dataset_roots_are_unchanged() -> None:
    train = json.loads((ROOT / "phase9g_a1c_official_train"
                        / "dataset_manifest.json").read_text())
    validation = json.loads((ROOT / "phase9g_a1v_official_validation"
                             / "validation_dataset_manifest.json").read_text())
    combined = json.loads((ROOT / "phase9g_a1v_official_validation"
                           / "combined_dataset_root_manifest.json").read_text())
    assert train["dataset_manifest_sha256"] == \
        "4ac3d2cb65a8b5d656a5d982b344466868f8deaa8cef2b93af7ce824e9387caf"
    assert validation["dataset_manifest_sha256"] == \
        "c991aa3016b38b524a14d9b7037b63d97c2cbbb7d92279fc5a297b9c55d4989e"
    assert combined["combined_recoverability_dataset_root_sha256"] == \
        "7e583ef98184767edfb95387ecc23d2ab266e2137db28a9fbb3badccaa495672"


def test_v1_is_treated_as_pilot_design_diagnostic_data() -> None:
    readiness = load("readiness")
    policy = readiness["v1_data_policy"]
    assert policy["classification"] == "PILOT_DESIGN_DIAGNOSTIC"
    assert policy["mutated"] is False
    assert policy["reused_as_confirmatory_h1_evidence"] is False
    assert policy["official_v2_generated_fresh"] is True


# ---------------------------------------------------------------------------
# frozen gates and semantics are not reopened
# ---------------------------------------------------------------------------
def test_the_thirty_per_family_validation_gate_is_unchanged() -> None:
    budget = load("budget")
    assert budget["adequacy_gate"]["required_minimum_retained_validation_events_"
                                   "per_primary_family"] == 30
    assert budget["adequacy_gate"]["lowered"] is False
    gates = json.loads(
        (ROOT / "phase9d_h1_requirement_map_v1.json").read_text())
    gate4 = next(g for g in gates["label_audit_gates"] if g["gate"] == 4)
    assert gate4["required_minimum_retained_validation_events_per_primary_family"] == 30


def test_class_weighting_stays_closed() -> None:
    readiness = load("readiness")
    assert readiness["frozen_and_not_reopened"]["class_weighting"] == \
        "NONE_UNWEIGHTED_BCE"


def test_frozen_candidate_semantics_are_untouched() -> None:
    frozen = load("readiness")["frozen_and_not_reopened"]
    for field in ("target_v4_sha256", "candidate_pair_all_or_none_publication",
                  "f8_f9_replica_rule", "matched_randomness", "compact_semantics",
                  "line_semantics", "safety", "topology_transition_science"):
        assert field in frozen
    assert frozen["candidate_pair_all_or_none_publication"] == "UNCHANGED"
    assert frozen["f8_f9_replica_rule"] == "3_MATCHED_REPLICAS_ALL_SUCCESS"


def test_no_realized_source_state_is_reported_as_generation_invalid() -> None:
    protocol = load("protocol")
    assert protocol["acquisition_protocol"][
        "not_a_realized_source_state_is_not_generation_invalid"] is True
    accounting = load("readiness")["v2_accounting_vocabulary"]
    assert "NOT_A_REALIZED_SOURCE_STATE" in accounting["source_stage_outcomes"]
    assert "GENERATION_INVALID" in accounting["candidate_stage_outcomes"]
    assert "GENERATION_INVALID" not in accounting["source_stage_outcomes"]


def test_protocol_artifact_hash_matches_the_executable_protocol() -> None:
    document = load("protocol")
    assert document["acquisition_protocol_sha256"] == acquisition_protocol_v2_sha256(
        document["acquisition_protocol"])
    assert document["acquisition_protocol"]["rule"] == REALIZED_TRAJECTORY_UNIFORM_K
    assert document["acquisition_protocol"]["K"] == DEFAULT_K


# ---------------------------------------------------------------------------
# the owner decision is surfaced, not resolved
# ---------------------------------------------------------------------------
def test_the_open_owner_decision_is_recorded_explicitly() -> None:
    readiness = load("readiness")
    assert readiness["verdict"] == "A"
    decisions = readiness["owner_decisions_required"]
    assert decisions, "verdict A must enumerate what the owner has to decide"
    for decision in decisions:
        assert decision["resolved_by_this_phase"] is False
        assert decision["options"]
    assert any("event-balanced" in decision["question"].lower()
               for decision in decisions)


def test_h1_meaning_is_recorded_as_preserved_with_evidence() -> None:
    readiness = load("readiness")
    h1 = readiness["h1_authority"]
    assert h1["s0_s4_are_semantic_h1_stages"] is False
    assert h1["decision_state_slots_are_data_sampling_times"] is True
    assert h1["primary_evaluation_unit"] == "PAIRED_EPISODE"
    assert h1["primary_metric"] == "EPISODE_TASK_SUCCESS"
    assert h1["per_family_effect_claim_predeclared"] is False
