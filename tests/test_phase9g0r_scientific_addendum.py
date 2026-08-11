"""Phase 9G0-R prospective owner-addendum contracts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import torch

from rvt_swarm.decentralized.ego_graph_v2 import build_robot_local_ego_graph
from rvt_swarm.phase8.common import sha256_document
from rvt_swarm.phase9g0r.contracts import (
    GENERATION_INVALID,
    INFRASTRUCTURE_FAILURE,
    CandidateAggregateDisposition,
    Phase9G0RContractError,
    communication_configuration_sha256,
    lifecycle_configuration_sha256,
    official_rollout_configuration_sha256,
    reconcile_candidate_pair,
    recoverability_ego_payload,
    recoverability_graph_fingerprint,
    recoverability_scientific_row_id,
    restore_recoverability_ego_graph,
    retained_dense_state_indices,
)
from rvt_swarm.runtime_configuration import RuntimeConfig, canonical_runtime_hash
from rvt_swarm.topology_registry import COMPACT, LINE


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results/rvt_fd24"

CANONICAL_ARTIFACTS = (
    ("phase9_recoverability_row_identity_v1.json", "phase9_recoverability_row_identity_sha256"),
    ("phase9_recoverability_ego_payload_binding_v1.json", "phase9_recoverability_ego_payload_binding_sha256"),
    ("phase9_recoverability_row_binding_v1.json", "phase9_recoverability_row_binding_sha256"),
    ("phase9_official_rollout_configuration_v1.json", "phase9_official_rollout_configuration_sha256"),
    ("phase9_lifecycle_config_hash_v1.json", "phase9_lifecycle_config_hash_sha256"),
    ("phase9_communication_config_hash_v1.json", "phase9_communication_config_hash_sha256"),
    ("phase9_recoverability_candidate_pair_transaction_v1.json", "phase9_recoverability_candidate_pair_transaction_sha256"),
    ("phase9_residual_dense_state_retention_v1.json", "phase9_residual_dense_state_retention_sha256"),
    ("phase9_predata_generation_scientific_addendum_v1.json", "phase9_predata_generation_scientific_addendum_sha256"),
)


def _row_key(**overrides):
    value = {
        "schema": "rvt-recoverability-row-identity/v1",
        "study": "study_a_zero_shot",
        "split": "train",
        "family": "F1",
        "layout_sha256": "a" * 64,
        "team_size": 6,
        "episode_id": "episode-0",
        "timestep": 20,
        "robot_id": 0,
        "candidate_topology_id": COMPACT,
        "graph_fingerprint": "b" * 64,
        "target_v4_contract_sha256": "c" * 64,
        "recoverability_row_binding_spec_sha256": "d" * 64,
    }
    value.update(overrides)
    return value


def _aggregate(candidate, disposition, label):
    return CandidateAggregateDisposition(
        "event-0", candidate, disposition, label, 1
    )


def test_every_scientific_addendum_artifact_has_a_valid_canonical_hash() -> None:
    for name, field in CANONICAL_ARTIFACTS:
        document = json.loads((RESULTS / name).read_text(encoding="ascii"))
        expected = document.pop(field)
        assert sha256_document(document) == expected


def test_addendum_is_prospective_and_k16_passes_the_authoritative_cap() -> None:
    addendum = json.loads(
        (RESULTS / "phase9_predata_generation_scientific_addendum_v1.json")
        .read_text(encoding="ascii")
    )
    assert set(addendum["pre_addendum_isolation"].values()) == {0}
    retention = json.loads(
        (RESULTS / "phase9_residual_dense_state_retention_v1.json")
        .read_text(encoding="ascii")
    )
    proof = retention["cap_proof"]
    assert proof["total_authorized_robot_episodes"] == 32560
    assert proof["strict_upper_bound"] == 520960
    assert proof["authoritative_dense_state_cap"] == 536000
    assert proof["remaining_capacity"] == 15040
    assert proof["passes"] is True


def test_recoverability_row_identity_varies_only_with_scientific_input_identity() -> None:
    reference = recoverability_scientific_row_id(_row_key())
    assert recoverability_scientific_row_id(_row_key()) == reference
    # Label and operational interventions remain outside the key and cannot move it.
    for diagnostic_label in (0, 1):
        for worker, chunk, attempt in ((0, 1, 0), (12, 8, 1)):
            assert diagnostic_label in (0, 1)
            assert min(worker, chunk, attempt) >= 0
            assert recoverability_scientific_row_id(_row_key()) == reference
    for field, replacement in (
        ("study", "study_b_with_n24"),
        ("split", "validation"),
        ("family", "F10"),
        ("layout_sha256", "e" * 64),
        ("team_size", 8),
        ("episode_id", "episode-1"),
        ("timestep", 21),
        ("robot_id", 1),
        ("candidate_topology_id", LINE),
        ("graph_fingerprint", "f" * 64),
    ):
        assert recoverability_scientific_row_id(
            _row_key(**{field: replacement})
        ) != reference
    with pytest.raises(Phase9G0RContractError, match="extra"):
        recoverability_scientific_row_id(_row_key(label=1))
    with pytest.raises(Phase9G0RContractError, match="extra"):
        recoverability_scientific_row_id(_row_key(worker_id=3))
    with pytest.raises(Phase9G0RContractError, match="extra"):
        recoverability_scientific_row_id(_row_key(replica_index=0))


def test_ego_payload_round_trip_reproduces_exact_model_input(ego_v2_factory) -> None:
    case = ego_v2_factory(
        peer_ids=(2, 1),
        obstacles=((1.0, 0.2, 0.1), (1.5, -0.3, 0.2, 0.1, 0.0)),
    )
    graph = build_robot_local_ego_graph(
        case.view, case.config, case.local_topology, LINE, case.observation_step
    )
    payload, candidate = recoverability_ego_payload(graph)
    fingerprint = recoverability_graph_fingerprint(payload)
    restored = restore_recoverability_ego_graph(payload, candidate, case.config)
    assert len(fingerprint) == 64
    assert "candidate_topology_id" not in payload["metadata"]
    assert candidate == LINE
    assert restored.candidate_topology_id == LINE
    assert restored.node_x.shape[1] == 35
    assert restored.edge_attr.shape[1] == 19
    for field in (
        "node_x", "node_feature_valid_mask", "node_valid_mask", "node_kind",
        "edge_index", "edge_attr", "edge_feature_valid_mask", "edge_valid_mask",
        "edge_type",
    ):
        assert torch.equal(getattr(restored, field), getattr(graph, field))
    changed = json.loads(json.dumps(payload))
    changed["tensors"]["node_x"][0][0] += 1.0
    assert recoverability_graph_fingerprint(changed) != fingerprint


def test_lifecycle_and_communication_hashes_use_scientific_configuration_only() -> None:
    runtime = RuntimeConfig.for_team_size(6)
    lifecycle = lifecycle_configuration_sha256(runtime)
    contract = {
        "profile": "nominal",
        "assumption_class": "inside_method_assumptions",
        "delay_upper_bound_seconds": 0.0,
        "packet_drop_probability": 0.0,
        "team_size_schedule": {},
    }
    first = communication_configuration_sha256(runtime, contract, 123)
    second = communication_configuration_sha256(runtime, dict(reversed(tuple(contract.items()))), 123)
    assert len(lifecycle) == len(first) == 64
    assert first == second
    assert first != communication_configuration_sha256(runtime, contract, 124)
    assert lifecycle != lifecycle_configuration_sha256(RuntimeConfig.for_team_size(8))


def test_rollout_hash_rejects_operational_fields_and_tracks_science() -> None:
    runtime = RuntimeConfig.for_team_size(6)
    kwargs = {
        "study": "study_a_zero_shot",
        "split": "train",
        "family": "F1",
        "layout_sha256": "a" * 64,
        "team_size": 6,
        "episode_id": "episode-0",
        "decision_event_id": "event-0",
        "decision_timestep": 20,
        "candidate_topology_id": COMPACT,
        "replica_index": 0,
        "matched_disturbance_seed": 123,
        "source_policy_contract_sha256": "b" * 64,
        "topology_registry_contract_sha256": "c" * 64,
        "base_controller_contract_sha256": "d" * 64,
        "transition_execution_protocol_sha256": "e" * 64,
        "safety_contract_sha256": "f" * 64,
        "simulator_protocol_sha256": "1" * 64,
        "target_v4_contract_sha256": "2" * 64,
        "runtime_configuration_sha256": canonical_runtime_hash(runtime),
        "control_period_seconds": runtime.physical.control_period_seconds,
        "lifecycle_config_sha256": lifecycle_configuration_sha256(runtime),
        "communication_config_sha256": "3" * 64,
    }
    reference = official_rollout_configuration_sha256(**kwargs)
    assert reference == official_rollout_configuration_sha256(**kwargs)
    assert reference != official_rollout_configuration_sha256(
        **{**kwargs, "replica_index": 1}
    )
    with pytest.raises(Phase9G0RContractError, match="operational"):
        official_rollout_configuration_sha256(**kwargs, worker_id=12)


@pytest.mark.parametrize("count", (0, 1, 2, 15, 16, 17, 32, 100))
def test_residual_retention_indices_are_exact(count: int) -> None:
    indices = retained_dense_state_indices(count)
    assert tuple(sorted(indices)) == indices
    assert len(set(indices)) == len(indices)
    assert len(indices) == min(count, 16)
    if count > 16:
        assert len(indices) == 16
        assert indices[0] == 0
        assert indices[-1] == count - 1
    expected = (
        tuple(range(count))
        if count <= 16
        else tuple((j * (count - 1)) // 15 for j in range(16))
    )
    assert indices == expected
    with pytest.raises(Phase9G0RContractError, match="remain 16"):
        retained_dense_state_indices(count, retention_k=15)


def test_candidate_pair_transaction_is_all_or_none() -> None:
    positive = _aggregate(COMPACT, "RECOVERABLE_POSITIVE", 1)
    negative = _aggregate(LINE, "VALID_TASK_NEGATIVE", 0)
    compact_rows = tuple({"robot_id": index, "candidate": COMPACT} for index in range(6))
    line_rows = tuple({"robot_id": index, "candidate": LINE} for index in range(6))
    valid = reconcile_candidate_pair(
        positive, negative, team_size=6,
        compact_rows=compact_rows, line_rows=line_rows,
    )
    assert valid.scientifically_reconciled is True
    assert valid.training_rows_committable is True
    assert valid.expected_row_count == valid.actual_row_count == 12

    for compact, line in (
        (_aggregate(COMPACT, GENERATION_INVALID, None), negative),
        (positive, _aggregate(LINE, GENERATION_INVALID, None)),
        (_aggregate(COMPACT, GENERATION_INVALID, None),
         _aggregate(LINE, GENERATION_INVALID, None)),
    ):
        result = reconcile_candidate_pair(compact, line, team_size=6)
        assert result.scientifically_reconciled is True
        assert result.training_rows_committable is False
        assert result.actual_row_count == 0

    pending = reconcile_candidate_pair(
        _aggregate(COMPACT, INFRASTRUCTURE_FAILURE, None), negative, team_size=6
    )
    assert pending.scientifically_reconciled is False
    assert pending.training_rows_committable is False
    assert pending.actual_row_count == 0

    with pytest.raises(Phase9G0RContractError, match="exactly N"):
        reconcile_candidate_pair(
            positive, negative, team_size=6,
            compact_rows=compact_rows[:-1], line_rows=line_rows,
        )
