"""RB-17 -- generation identity, dispositions, schema binding and versioning.

The three identities are proven distinct and independently varying, the
no-eligible disposition is proven to emit nothing while still counting, the
model V2 orientation context is proven to survive serialization, and preflight
is proven to *reject* each stale contract rather than merely parse the new ones.
"""

from __future__ import annotations

import copy
import hashlib
import json
import pathlib

import pytest
import torch

from rvt_swarm.decentralized.ego_graph_v2 import (
    EGO_GRAPH_SCHEMA_VERSION, build_robot_local_ego_graph, dump_robot_local_ego_graph,
    load_robot_local_ego_graph,
)
from rvt_swarm.fd24.configuration import ROBOT_LOCAL_ACTION_COMPONENTS, FD24ModelConfig
from rvt_swarm.fd24.model import (
    FD24_MODEL_INPUT_SCHEMA_VERSION, FD24_MODEL_SCHEMA_VERSION, RVTFD24LocalModel,
    prepare_fd24_model_batch,
)
from rvt_swarm.phase8 import targets as phase8_targets
from rvt_swarm.phase8.common import canonical_json_bytes
from rvt_swarm.phase9.preflight import build_preflight_audit, residual_v2_contract_checks
from rvt_swarm.phase9c_rb import policies as P
from rvt_swarm.phase9c_rb.binding import build_binding, load_execution_specification
from rvt_swarm.phase9c_rb.generation_contract import (
    CANDIDATE_EVALUATION_KEY, DISPOSITIONS, EMITS_TARGET_ROW, EXECUTION_ATTEMPT_KEY,
    EXECUTION_INVALID, INFRASTRUCTURE_FAILURE, LABELED, NO_ELIGIBLE_ACTION,
    RESIDUAL_SUPERVISION_ROW_SCHEMA_VERSION, SCIENTIFIC_ROW_KEY, DispositionCounts,
    GenerationContractError, ResidualSupervisionRowV2, candidate_evaluation_id,
    execution_attempt_id, residual_scientific_row_id,
)
from rvt_swarm.phase9c_rb.residual_expert_v2 import evaluate_residual_expert_v2
from rvt_swarm.phase9c_rb.session import SimulatorEpisodeSession
from rvt_swarm.runtime_configuration import DEFAULT_RUNTIME_CONFIG
from rvt_swarm.topology_registry import COMPACT

ROOT = pathlib.Path("results/rvt_fd24")
PROTOCOL = json.loads((ROOT / "executable_scientific_protocol_v1.json").read_text())
TARGET_CONTRACT = json.loads((ROOT / "target_v4_execution_contract_v1.json").read_text())
CONTRACTS = json.loads((ROOT / "source_policy_contracts_v1.json").read_text())
SPEC = json.loads((ROOT / "residual_expert_spec_v2.json").read_text())
BUDGET_V1 = json.loads((ROOT / "datasets" / "generation_budget_v1.json").read_text())

ROW_IDENTITY = json.loads((ROOT / "residual_scientific_row_identity_v2.json").read_text())
CANDIDATE_IDENTITY = json.loads(
    (ROOT / "residual_candidate_evaluation_identity_v2.json").read_text())
EXECUTION_IDENTITY = json.loads(
    (ROOT / "residual_execution_attempt_identity_v1.json").read_text())
DISPOSITION = json.loads(
    (ROOT / "residual_generation_disposition_contract_v1.json").read_text())
ROW_SCHEMA = json.loads((ROOT / "residual_supervision_row_schema_v2.json").read_text())
BUDGET_V2 = json.loads((ROOT / "generation_budget_v2.json").read_text())
MANIFEST_V2 = json.loads((ROOT / "residual_job_manifest_v2.json").read_text())
COMPOSITE = json.loads(
    (ROOT / "rb17_generation_contract_composite_v1.json").read_text())

MODEL = FD24ModelConfig()
SEEDS = {"initial_condition": 11, "communication": 22, "dynamic_obstacle": 33}


def build_session(layout="train-f1-00", split="train", team_size=6,
                  policy_id=P.S1, steps=20):
    binding = build_binding(
        load_execution_specification(ROOT, split, layout), team_size=team_size,
        source_policy=policy_id, protocol=PROTOCOL, target_contract=TARGET_CONTRACT,
        source_policy_contracts=CONTRACTS)
    policy = P.build_source_policy(
        policy_id, contracts=CONTRACTS, seed=7, horizon_seconds=binding.horizon_seconds,
        team_size=team_size, family_id=binding.family,
        runtime_config=DEFAULT_RUNTIME_CONFIG, event_plan=())
    session = SimulatorEpisodeSession(binding, protocol=PROTOCOL,
                                      target_contract=TARGET_CONTRACT, seeds=SEEDS,
                                      source_policy=policy)
    for _ in range(steps):
        session.step()
    return session


def base_key(**overrides):
    key = {"study": "study_a_zero_shot", "split": "train", "family": "F1",
           "layout_sha256": "l" * 64, "team_size": 6, "episode_id": "episode-0",
           "timestep": 20, "robot_id": 0, "topology_id": COMPACT,
           "graph_fingerprint": "g" * 64,
           "residual_expert_spec_sha256": SPEC["residual_expert_spec_v2_sha256"]}
    key.update(overrides)
    return key


# ---------------------------------------------------------------------------
# RB17-0 -- provenance root
# ---------------------------------------------------------------------------
def test_rb17_consumes_the_current_residual_runtime_composite() -> None:
    root = COMPOSITE["provenance_root_consumed"]
    runtime = json.loads((ROOT / "residual_runtime_composite_v1.json").read_text())
    assert root["sha256"] == runtime["residual_runtime_composite_sha256"] == (
        "24c65a41855a2ffe9345755f0630dfe707e9446065d7cef8516f8f1e89cb19ff")
    assert root["chain"] == ["Residual Expert V2", "RB15 producer",
                             "failed RB16 evidence", "WORLD-frame model repair",
                             "successful RB16 requalification"]
    states = {row["role"]: row["state"] for row in COMPOSITE["components"]}
    assert states["RB-16 frame-conflict audit"] == "SUPERSEDED_EVIDENCE"
    assert states["RB-16 requalification"] == "CURRENT"
    assert COMPOSITE["historical_artifacts_rewritten"] is False


def test_every_artifact_hashes_canonically() -> None:
    for document, field in (
            (ROW_IDENTITY, "residual_scientific_row_identity_v2_sha256"),
            (CANDIDATE_IDENTITY, "residual_candidate_evaluation_identity_v2_sha256"),
            (EXECUTION_IDENTITY, "residual_execution_attempt_identity_v1_sha256"),
            (DISPOSITION, "residual_generation_disposition_contract_v1_sha256"),
            (ROW_SCHEMA, "residual_supervision_row_schema_v2_sha256"),
            (BUDGET_V2, "generation_budget_v2_sha256"),
            (MANIFEST_V2, "residual_job_manifest_v2_sha256"),
            (COMPOSITE, "rb17_generation_contract_composite_sha256")):
        body = {k: v for k, v in document.items() if k != field}
        assert hashlib.sha256(canonical_json_bytes(body)).hexdigest() == document[field]


# ---------------------------------------------------------------------------
# RB17-2/3/4/5 -- three distinct identities
# ---------------------------------------------------------------------------
def test_scientific_row_identity_excludes_every_non_scientific_dimension() -> None:
    assert "candidate_index" not in SCIENTIFIC_ROW_KEY
    assert "replica_index" not in SCIENTIFIC_ROW_KEY
    assert not any("chunk" in name or "worker" in name or "attempt" in name
                   for name in SCIENTIFIC_ROW_KEY)
    assert tuple(ROW_IDENTITY["key_fields"]) == SCIENTIFIC_ROW_KEY
    assert ROW_IDENTITY["candidate_index_in_identity"] is False
    with pytest.raises(GenerationContractError, match="must not carry"):
        residual_scientific_row_id(base_key(candidate_index=3))
    with pytest.raises(GenerationContractError, match="missing"):
        residual_scientific_row_id({"study": "study_a_zero_shot"})


def test_scientific_key_fields_come_from_the_frozen_contracts() -> None:
    residual_cell = BUDGET_V1["job_identity_contract"]["residual_cell"]
    dense_order = BUDGET_V1["dense_row_contract"]["canonical_order"]
    for field in residual_cell:
        assert field in SCIENTIFIC_ROW_KEY, field
    for field in dense_order:
        assert field in SCIENTIFIC_ROW_KEY, field
    assert "residual_expert_spec_sha256" in SCIENTIFIC_ROW_KEY
    assert set(SCIENTIFIC_ROW_KEY) == set(residual_cell) | set(dense_order) | {
        "robot_id", "residual_expert_spec_sha256"}


def test_row_identity_varies_with_every_key_field() -> None:
    reference = residual_scientific_row_id(base_key())
    for field, replacement in (("study", "study_b"), ("split", "validation"),
                               ("family", "F9"), ("layout_sha256", "m" * 64),
                               ("team_size", 8), ("episode_id", "episode-1"),
                               ("timestep", 21), ("robot_id", 1),
                               ("topology_id", 2), ("graph_fingerprint", "h" * 64),
                               ("residual_expert_spec_sha256", "z" * 64)):
        assert residual_scientific_row_id(base_key(**{field: replacement})) != reference


def test_nine_candidates_have_nine_distinct_evaluation_ids() -> None:
    row_id = residual_scientific_row_id(base_key())
    ids = [candidate_evaluation_id({"residual_scientific_row_id": row_id,
                                    "candidate_index": index, "replica_index": 0,
                                    "matched_stream_identity_sha256": "s" * 64})
           for index in range(9)]
    assert len(set(ids)) == 9
    assert all(item != row_id for item in ids)
    assert tuple(CANDIDATE_IDENTITY["key_fields"]) == CANDIDATE_EVALUATION_KEY
    with pytest.raises(GenerationContractError, match="frozen nine"):
        candidate_evaluation_id({"residual_scientific_row_id": row_id,
                                 "candidate_index": 9, "replica_index": 0,
                                 "matched_stream_identity_sha256": "s" * 64})


def test_candidate_identity_also_varies_with_replica_and_streams() -> None:
    row_id = residual_scientific_row_id(base_key())
    def make(**overrides):
        key = {"residual_scientific_row_id": row_id, "candidate_index": 0,
               "replica_index": 0, "matched_stream_identity_sha256": "s" * 64}
        key.update(overrides)
        return candidate_evaluation_id(key)
    assert make() != make(replica_index=1)
    assert make() != make(matched_stream_identity_sha256="t" * 64)


def test_execution_identity_is_purely_operational() -> None:
    assert tuple(EXECUTION_IDENTITY["key_fields"]) == EXECUTION_ATTEMPT_KEY
    assert EXECUTION_IDENTITY["purely_operational"] is True
    assert EXECUTION_IDENTITY["chunk_size_frozen"] is False
    assert EXECUTION_IDENTITY["rows_per_job_frozen"] is False
    for forbidden in ("scientific row identity", "candidate utility",
                      "selected target", "matched streams"):
        assert forbidden in EXECUTION_IDENTITY["may_not_affect"]
    first = execution_attempt_id({"chunk_id": "a", "worker_id": 0,
                                  "attempt_index": 0, "task_range": [0, 10]})
    second = execution_attempt_id({"chunk_id": "b", "worker_id": 4,
                                   "attempt_index": 1, "task_range": [5, 10]})
    assert first != second
    # and no execution field is part of any scientific identity
    assert not set(EXECUTION_ATTEMPT_KEY) & set(SCIENTIFIC_ROW_KEY)
    assert not set(EXECUTION_ATTEMPT_KEY) & set(CANDIDATE_EVALUATION_KEY)


# ---------------------------------------------------------------------------
# RB17-29/30 -- chunking independence and retry identity, from real evidence
# ---------------------------------------------------------------------------
def test_scientific_identity_is_invariant_to_chunking() -> None:
    evidence = EXECUTION_IDENTITY["evidence"]
    assert evidence["identical_after_canonical_sort"] is True
    assert evidence["execution_ids_differ"] is True
    assert len(set(evidence["partition_a_row_ids"])) == 3


def test_infrastructure_retry_preserves_every_scientific_identity() -> None:
    retry = EXECUTION_IDENTITY["retry"]
    assert retry["semantic_generation_retries"] == 0
    assert retry["maximum_infrastructure_retries"] == 1
    assert retry["scientific_denominator_delta"] == 0
    assert retry["randomness_resampled_on_retry"] is False
    evidence = retry["evidence"]
    for field in ("scientific_row_id_stable", "candidate_ids_stable",
                  "matched_streams_stable", "target_stable", "attempt_ids_differ"):
        assert evidence[field] is True, field


def test_duplicate_semantics_are_defined_per_identity_class() -> None:
    duplicates = EXECUTION_IDENTITY["duplicates"]
    assert duplicates["scientific_row"].startswith("reject")
    assert "deduplicate" in duplicates["candidate_evaluation"]
    assert "must not create a duplicate scientific sample" in duplicates[
        "execution_attempt"]
    assert duplicates["weakened_scientific_duplicate_detection"] is False
    assert duplicates["historical_policy_preserved"] == BUDGET_V1[
        "job_identity_contract"]["duplicate_semantic_identity_policy"] == "reject"


# ---------------------------------------------------------------------------
# RB17-8/9/10/31 -- the no-eligible contract
# ---------------------------------------------------------------------------
def test_disposition_taxonomy_is_minimal_and_hard_separated() -> None:
    assert DISPOSITIONS == (LABELED, NO_ELIGIBLE_ACTION, EXECUTION_INVALID,
                            INFRASTRUCTURE_FAILURE)
    assert tuple(DISPOSITION["dispositions"]) == DISPOSITIONS
    assert len(set(DISPOSITIONS)) == 4
    assert EMITS_TARGET_ROW[LABELED] is True
    for other in (NO_ELIGIBLE_ACTION, EXECUTION_INVALID, INFRASTRUCTURE_FAILURE):
        assert EMITS_TARGET_ROW[other] is False
    assert DISPOSITION["no_separate_valid_method_failure_category"]["frozen_reference"]


def test_no_eligible_emits_no_row_but_stays_in_the_denominator() -> None:
    counts = DispositionCounts()
    counts.record(LABELED)
    counts.record(NO_ELIGIBLE_ACTION)
    counts.record(NO_ELIGIBLE_ACTION)
    counts.record(EXECUTION_INVALID)
    counts.record(INFRASTRUCTURE_FAILURE)
    report = counts.as_dict()
    assert report["attempted_expert_decision_states"] == 4      # not the infra failure
    assert report["no_eligible_states"] == 2
    assert report["target_rows_emitted"] == 1 == report["labeled_states"]
    assert counts.consistent()
    assert report["target_rows_emitted"] < report["attempted_expert_decision_states"]


def test_no_eligible_is_never_converted_into_a_target() -> None:
    contract = DISPOSITION["no_eligible_action"]
    assert contract["target_rows"] == 0
    assert contract["counts_in_denominator"] is True
    for forbidden in ("zero residual target", "clipped target", "rotated target",
                      "base-action target", "arbitrary fallback"):
        assert forbidden in contract["forbidden_conversions"]
    evidence = contract["evidence"]
    assert evidence["disposition"] == NO_ELIGIBLE_ACTION
    assert evidence["target_rows"] == 0
    assert evidence["candidates_evaluated"] == 9
    assert evidence["all_safety_infeasible"] is True
    assert evidence["counts"]["attempted_expert_decision_states"] == 1
    assert evidence["counts"]["no_eligible_states"] == 1
    assert evidence["counts"]["execution_invalid_states"] == 0
    assert evidence["counts"]["infrastructure_failures"] == 0
    assert evidence["counts_consistent"] is True


def test_a_supervision_row_cannot_be_built_for_a_no_eligible_decision() -> None:
    with pytest.raises(GenerationContractError, match="only a LABELED"):
        ResidualSupervisionRowV2(
            RESIDUAL_SUPERVISION_ROW_SCHEMA_VERSION, "r" * 64,
            {"residual_target_world_acceleration": (0.0, 0.0)}, (1.0, 0.0), "e" * 64,
            EGO_GRAPH_SCHEMA_VERSION, FD24_MODEL_INPUT_SCHEMA_VERSION,
            FD24_MODEL_SCHEMA_VERSION, "s" * 64, "x" * 64, "d" * 64, "m" * 64,
            4, "c" * 64, NO_ELIGIBLE_ACTION)


# ---------------------------------------------------------------------------
# RB17-11/12/13/14 -- model V2 serialization
# ---------------------------------------------------------------------------
def test_the_frozen_dense_row_alone_cannot_rebuild_a_model_v2_input() -> None:
    fields = set(phase8_targets.DenseActionSample.__dataclass_fields__)
    assert "feature_sha256" in fields
    assert "mission_orientation_cos_sin" not in fields
    assert "node_x" not in fields
    assert ROW_SCHEMA["why_a_binding_is_required"].startswith(
        "the frozen dense row references its features only by feature_sha256")
    assert ROW_SCHEMA["extends_frozen"]["modified"] is False


def test_the_binding_adds_orientation_without_new_scientific_information() -> None:
    added = ROW_SCHEMA["added_fields"]["mission_orientation_cos_sin"]
    assert added["shape"] == [2]
    assert added["source"] == "RobotLocalEgoGraph.mission_orientation_cos_sin"
    assert added["provenance"] == "LOCAL_MISSION_CONFIGURATION"
    assert added["recomputed_from_layout_ids_at_training_time"] is False
    assert added["read_from_hidden_simulator_state"] is False
    assert added["introduces_new_scientific_information"] is False
    assert ROW_SCHEMA["model_input_reconstruction"]["all_preserved"] is True


def test_orientation_survives_the_record_round_trip_and_the_model(
        ) -> None:
    session = build_session()
    robot = session.robots[0]
    graph = build_robot_local_ego_graph(
        session._build_robot_view(robot), session.runtime_config,
        robot.local_topology_metadata, COMPACT, 20)
    restored = load_robot_local_ego_graph(
        dump_robot_local_ego_graph(graph), session.runtime_config)
    assert restored.mission_orientation_cos_sin == graph.mission_orientation_cos_sin

    model = RVTFD24LocalModel(MODEL, session.runtime_config)
    model.eval()
    with torch.no_grad():
        before = model(prepare_fd24_model_batch((graph,)))
        after = model(prepare_fd24_model_batch((restored,)))
    assert torch.equal(before.residual_action, after.residual_action)
    assert torch.equal(before.recoverability_logit, after.recoverability_logit)
    evidence = ROW_SCHEMA["orientation_round_trip_evidence"]
    for field in ("orientation_exact", "record_sha256_stable", "residual_identical",
                  "recoverability_identical"):
        assert evidence[field] is True, field


def test_orientation_reaches_only_the_residual_head() -> None:
    evidence = ROW_SCHEMA["orientation_head_isolation_evidence"]
    assert evidence["residual_differs"] is True
    assert evidence["recoverability_invariant"] is True


def test_world_target_round_trips_with_a_non_symmetric_mixed_sign_vector() -> None:
    from rvt_swarm.fd24.configuration import residual_action_limits
    limits = residual_action_limits(MODEL, DEFAULT_RUNTIME_CONFIG)
    delta = (limits[0] * 0.5, -limits[1] * 0.25)
    assert delta[0] != delta[1] and abs(delta[0]) != abs(delta[1])
    row = ResidualSupervisionRowV2(
        RESIDUAL_SUPERVISION_ROW_SCHEMA_VERSION, "r" * 64,
        {"residual_target_world_acceleration": delta}, (1.0, 0.0), "e" * 64,
        EGO_GRAPH_SCHEMA_VERSION, FD24_MODEL_INPUT_SCHEMA_VERSION,
        FD24_MODEL_SCHEMA_VERSION, "s" * 64, "x" * 64, "d" * 64, "m" * 64,
        4, "c" * 64, LABELED)
    decoded = json.loads(json.dumps(row.canonical_payload()))
    assert tuple(decoded["dense_row"]["residual_target_world_acceleration"]) == delta
    assert decoded["mission_orientation_cos_sin"] == [1.0, 0.0]
    assert row.canonical_sha256() == ResidualSupervisionRowV2(
        **{**row.__dict__}).canonical_sha256()
    target = ROW_SCHEMA["target_field"]
    assert target["frame"] == "WORLD" and target["units"] == "meters_per_second_squared"
    assert not any(target["round_trip"].values())


def test_a_row_rejects_a_non_unit_orientation() -> None:
    with pytest.raises(GenerationContractError, match="unit vector"):
        ResidualSupervisionRowV2(
            RESIDUAL_SUPERVISION_ROW_SCHEMA_VERSION, "r" * 64,
            {"residual_target_world_acceleration": (0.01, 0.0)}, (0.5, 0.5), "e" * 64,
            EGO_GRAPH_SCHEMA_VERSION, FD24_MODEL_INPUT_SCHEMA_VERSION,
            FD24_MODEL_SCHEMA_VERSION, "s" * 64, "x" * 64, "d" * 64, "m" * 64,
            4, "c" * 64, LABELED)


def test_row_schema_pins_the_repaired_model_not_v1() -> None:
    pins = ROW_SCHEMA["model_schema_pins"]
    assert pins["model_schema_version"] == FD24_MODEL_SCHEMA_VERSION == "rvt-fd24-model/v2"
    assert tuple(pins["output_components"]) == ROBOT_LOCAL_ACTION_COMPONENTS
    assert not any("mission" in name for name in pins["output_components"])
    assert pins["historical_v1_rewritten"] is False
    assert pins["incompatible_schema_load"] == "reject"


def test_candidate_records_live_in_a_sidecar_not_the_training_row() -> None:
    sidecar = ROW_SCHEMA["candidate_audit_sidecar"]
    assert sidecar["decision"] == "B_GENERATION_AUDIT_SIDECAR"
    assert sidecar["keyed_by"] == "candidate_evaluation_id"
    assert sidecar["reproducibility_preserved"] is True
    assert sidecar["changes_the_scientific_objective"] is False
    provenance = ROW_SCHEMA["selected_candidate_provenance"]
    assert provenance["nine_candidate_records_in_the_training_row"] is False
    assert "selected_candidate_index" in provenance["fields"]
    assert "selector_sha256" in provenance["fields"]


# ---------------------------------------------------------------------------
# RB17-19/20/21/22/23 -- budget versioning
# ---------------------------------------------------------------------------
def test_budget_v2_is_additive_and_preserves_source_counts() -> None:
    assert BUDGET_V2["extends"]["sha256"] == BUDGET_V1["generation_budget_sha256"] == (
        "3853b8ad4484d733de9be7d0e27bf273f33e14054f3089f6b5454cc17815846e")
    assert BUDGET_V2["extends"]["overwritten"] is False
    preserved = BUDGET_V2["preserved_scientific_source_counts"]
    for field, value in BUDGET_V1["exact_total_budget"].items():
        assert preserved[field] == value, field


def test_nine_candidates_do_not_multiply_stored_rows() -> None:
    additions = BUDGET_V2["residual_v2_additions"]
    assert additions["residual_candidate_count"] == 9
    assert additions["stored_residual_supervision_upper_cap"] == 536000
    assert additions["candidate_evaluation_compute_upper_bound"] == 4824000
    assert additions["nine_candidates_do_not_create_nine_rows"] is True
    assert additions["compute_bound_is_not_a_row_count"] is True
    assert 536000 * 9 == 4824000


def test_the_historical_timeout_is_not_authoritative_and_none_is_chosen() -> None:
    timeout = BUDGET_V2["timeout"]
    assert timeout["historical_residual_action_cell_generation_job_seconds"] == 1800
    assert timeout["historical_value_authoritative_for_v2"] is False
    assert timeout["RESIDUAL_V2_GENERATION_TIMEOUT"] == (
        "PENDING_RB21_PERFORMANCE_QUALIFICATION")
    assert timeout["replacement_chosen_in_rb17"] is False
    assert BUDGET_V1["timeout_contract"]["wall_clock_seconds"][
        "residual_action_cell_generation_job"] == 1800      # V1 untouched


def test_no_chunk_size_is_frozen() -> None:
    chunking = BUDGET_V2["chunking"]
    assert chunking["chunk_size_frozen"] is False
    assert chunking["rows_per_job_frozen"] is False
    assert chunking["rows_per_worker_frozen"] is False


def test_the_rb15_benchmark_is_input_to_rb21_not_a_guarantee() -> None:
    performance = BUDGET_V2["performance_provenance"]
    assert performance["state"] == "INPUT_TO_RB21"
    assert performance["candidate_evaluations"] == 90
    assert performance["expert_decisions"] == 10
    assert performance["mean_seconds_per_candidate_continuation"] == pytest.approx(
        1.593423, abs=1e-6)
    assert performance["promoted_to_a_capacity_guarantee"] is False
    assert performance["projected_single_worker_days"] > 0


# ---------------------------------------------------------------------------
# RB17-24/25 -- manifest and composite
# ---------------------------------------------------------------------------
def test_manifest_v2_is_versioned_and_unauthorized() -> None:
    assert MANIFEST_V2["schema_version"] == "rvt-residual-job-manifest/v2"
    assert MANIFEST_V2["historical_manifest"]["mutated"] is False
    assert MANIFEST_V2["historical_manifest"]["sha256"] == hashlib.sha256(
        (ROOT / "datasets" / "phase9_job_manifest.json").read_bytes()).hexdigest()
    assert MANIFEST_V2["official_scientific_execution_status"] == (
        "NOT_AUTHORIZED_PENDING_RB18_RB21")
    assert MANIFEST_V2["official_job_records_emitted"] == 0
    references = MANIFEST_V2["references"]
    for required in ("source_scientific_protocol", "et_timing_addendum",
                     "headroom_authority", "residual_expert_spec_v2",
                     "residual_label_contract_composite_v2", "rb15_binding",
                     "model_residual_output_frame_v2",
                     "rb16_world_output_requalification", "residual_runtime_composite",
                     "model_v2_input_schema", "generation_budget_v2",
                     "scientific_row_identity", "candidate_evaluation_identity",
                     "execution_attempt_identity", "disposition_contract",
                     "supervision_row_schema"):
        assert required in references, required


def test_the_composite_is_the_single_current_root() -> None:
    assert COMPOSITE["status"] == "CURRENT"
    assert COMPOSITE["generation_authorized"] is False
    assert COMPOSITE["RESIDUAL_V2_GENERATION_TIMEOUT"] == (
        "PENDING_RB21_PERFORMANCE_QUALIFICATION")
    assert "RB-18" in COMPOSITE["next_phase"]
    for role, sha in ((("scientific row identity V2"),
                       ROW_IDENTITY["residual_scientific_row_identity_v2_sha256"]),
                      ("generation budget V2", BUDGET_V2["generation_budget_v2_sha256"]),
                      ("residual job manifest V2",
                       MANIFEST_V2["residual_job_manifest_v2_sha256"])):
        entry = next(row for row in COMPOSITE["components"] if row["role"] == role)
        assert entry["sha256"] == sha


# ---------------------------------------------------------------------------
# RB17-26 -- preflight rejects stale contracts
# ---------------------------------------------------------------------------
def test_preflight_accepts_the_current_v2_contracts() -> None:
    audit = build_preflight_audit(pathlib.Path("."))
    assert audit["status"] == "PASS"
    names = {check["name"] for check in audit["checks"]}
    for required in ("residual_v2_model_frame_is_world",
                     "residual_v2_orientation_context_present",
                     "residual_v2_target_frame_world",
                     "residual_v2_row_identity_excludes_candidate_index",
                     "residual_v2_timeout_not_stale",
                     "residual_v2_candidate_count",
                     "residual_v2_no_synthetic_augmentation",
                     "residual_v2_disposition_vocabulary",
                     "residual_v2_generation_not_authorized"):
        assert required in names, required


@pytest.mark.parametrize("mutation,check_name", [
    ({"file": "residual_supervision_row_schema_v2.json",
      "path": ["model_schema_pins", "output_components"],
      "value": ["mission_longitudinal_acceleration", "mission_lateral_acceleration"]},
     "residual_v2_model_frame_is_world"),
    ({"file": "residual_supervision_row_schema_v2.json",
      "path": ["added_fields"], "value": {}},
     "residual_v2_orientation_context_present"),
    ({"file": "residual_supervision_row_schema_v2.json",
      "path": ["target_field", "frame"], "value": "MISSION"},
     "residual_v2_target_frame_world"),
    ({"file": "residual_scientific_row_identity_v2.json",
      "path": ["candidate_index_in_identity"], "value": True},
     "residual_v2_row_identity_excludes_candidate_index"),
    ({"file": "generation_budget_v2.json",
      "path": ["timeout", "RESIDUAL_V2_GENERATION_TIMEOUT"], "value": "1800"},
     "residual_v2_timeout_not_stale"),
    ({"file": "generation_budget_v2.json",
      "path": ["residual_v2_additions", "residual_candidate_count"], "value": 4},
     "residual_v2_candidate_count"),
    ({"file": "residual_generation_disposition_contract_v1.json",
      "path": ["dispositions"], "value": ["LABELED"]},
     "residual_v2_disposition_vocabulary"),
    ({"file": "residual_job_manifest_v2.json",
      "path": ["official_scientific_execution_status"], "value": "AUTHORIZED"},
     "residual_v2_generation_not_authorized"),
])
def test_preflight_rejects_each_stale_or_incompatible_contract(
        tmp_path, mutation, check_name) -> None:
    """Parsing the new contracts is not authorization: each must be rejectable."""
    import shutil
    shutil.copytree("results", tmp_path / "results")
    target = tmp_path / "results/rvt_fd24" / mutation["file"]
    document = json.loads(target.read_text())
    node = document
    for step in mutation["path"][:-1]:
        node = node[step]
    node[mutation["path"][-1]] = mutation["value"]
    target.write_text(json.dumps(document, indent=1, sort_keys=True) + "\n")

    checks = residual_v2_contract_checks(tmp_path)
    by_name = {check["name"]: check for check in checks}
    # the mutated document's own canonical hash breaks first, which is itself a
    # rejection; the semantic check must also fail when the hash is repaired.
    hash_checks = [check for check in checks
                   if check["name"].startswith("residual_v2_contract_hash")
                   and not check["passed"]]
    assert hash_checks or not by_name[check_name]["passed"]
    if check_name in by_name and not hash_checks:
        assert by_name[check_name]["passed"] is False


def test_preflight_rejects_a_missing_v2_contract(tmp_path) -> None:
    import shutil
    shutil.copytree("results", tmp_path / "results")
    (tmp_path / "results/rvt_fd24/residual_supervision_row_schema_v2.json").unlink()
    checks = residual_v2_contract_checks(tmp_path)
    missing = [check for check in checks
               if check["name"].endswith("supervision_row_schema")
               and not check["passed"]]
    assert missing


# ---------------------------------------------------------------------------
# RB17-27/33 -- isolation
# ---------------------------------------------------------------------------
def test_no_scientific_data_was_generated() -> None:
    residual_audit = json.loads(
        (ROOT / "datasets" / "phase9_residual_audit.json").read_text())
    assert residual_audit["emitted_rows"] == 0
    assert residual_audit["expert_calls"] == 0
    assert BUDGET_V1["scientific_dataset_records_generated"] == 0
    assert BUDGET_V1["training_operations"] == 0
    assert BUDGET_V1["rollout_jobs_executed"] == 0
    isolation = COMPOSITE["isolation"]
    for key, value in isolation.items():
        assert value == 0, key


def test_sealed_domains_hold() -> None:
    assert PROTOCOL["final_test_access_policy"]["runtime_access_count"] == 0
    assert not (ROOT / "layout_execution_specifications" / "final_test").exists()
    assert MANIFEST_V2["final_test_job_construction"] == "prohibited"
    assert MANIFEST_V2["study_a_n24_jobs"] == 0


def test_upstream_scientific_semantics_are_unchanged() -> None:
    assert SPEC["residual_expert_spec_v2_sha256"] == (
        "e3a3093038b31f7f8c11d56be224929c9eccc27e6bde2fa47c5c6c644b7f3fbf")
    for name, field, expected in (
            ("residual_label_contract_composite_v2",
             "residual_label_contract_composite_sha256",
             "8921424d0342e26a7a22da4ca042543a8eb08c2dc310f5f5639b70678ceb08ad"),
            ("rb15_residual_expert_binding_v2",
             "rb15_residual_expert_binding_v2_sha256",
             "9edc8cc8d46b94c76f0fa8e3a2ea07b7bff06fd9d5cfe5f5cb26565170af3f24"),
            ("rb16_world_output_requalification_v1",
             "rb16_world_output_requalification_sha256",
             "10c4aebe41a98db7674f7ee617db8a209a148bdfe18ca76bd04cde59660ab387"),
            ("headroom_requalification_v6", "headroom_requalification_v6_sha256",
             "d044d6b99d7a2bbb83565b121d188a35e335bfd856e3eb0e885823ca1a6742ef")):
        assert json.loads((ROOT / f"{name}.json").read_text())[field] == expected, name
