"""Canonical V2 serialization, hashing, and migration policy."""

import hashlib
import json

import pytest
import torch

from rvt_swarm.decentralized.ego_graph_v2 import (
    EGO_GRAPH_SCHEMA_VERSION,
    EgoGraphMigrationError,
    EgoGraphSerializationError,
    build_robot_local_ego_graph,
    dump_robot_local_ego_graph,
    load_robot_local_ego_graph,
    migrate_legacy_ego_graph_schema,
)
from rvt_swarm.runtime_configuration import RuntimeConfig
from rvt_swarm.topology_registry import LINE


def _serialized(ego_v2_factory):
    case = ego_v2_factory(
        peer_ids=(2, 1),
        obstacles=((1.0, 0.2, 0.1), (1.5, -0.3, 0.2, 0.1, 0.0)),
    )
    graph = build_robot_local_ego_graph(
        case.view, case.config, case.local_topology, LINE, case.observation_step
    )
    return case, graph, dump_robot_local_ego_graph(graph)


def test_round_trip_is_deterministic_and_preserves_masks(ego_v2_factory):
    case, graph, payload = _serialized(ego_v2_factory)
    restored = load_robot_local_ego_graph(payload, case.config)
    assert dump_robot_local_ego_graph(restored) == payload
    assert restored.fingerprint() == graph.fingerprint()
    assert torch.equal(restored.node_x, graph.node_x)
    assert torch.equal(restored.node_feature_valid_mask, graph.node_feature_valid_mask)
    assert torch.equal(restored.edge_feature_valid_mask, graph.edge_feature_valid_mask)
    root = json.loads(payload)
    assert root["schema_version"] == EGO_GRAPH_SCHEMA_VERSION
    assert len(root["feature_schema_sha256"]) == 64
    assert len(root["runtime_config_sha256"]) == 64
    assert root["units"]["observation_timestamp_seconds"] == "s"


def test_content_tampering_is_rejected(ego_v2_factory):
    case, _, payload = _serialized(ego_v2_factory)
    raw = json.loads(payload)
    raw["tensors"]["node_x"][0][0] = 123.0
    with pytest.raises(EgoGraphSerializationError, match="content hash"):
        load_robot_local_ego_graph(json.dumps(raw), case.config)


@pytest.mark.parametrize("operation", ("unknown", "missing"))
def test_closed_record_schema_rejects_unknown_or_missing_fields(
    ego_v2_factory, operation
):
    case, _, payload = _serialized(ego_v2_factory)
    raw = json.loads(payload)
    if operation == "unknown":
        raw["global_centroid"] = [0.0, 0.0]
    else:
        del raw["metadata"]
    with pytest.raises(EgoGraphSerializationError):
        load_robot_local_ego_graph(json.dumps(raw), case.config)


def test_unknown_and_legacy_schema_are_not_guessed(ego_v2_factory):
    case, _, payload = _serialized(ego_v2_factory)
    raw = json.loads(payload)
    raw["schema_version"] = "rvt-ego-graph/v1"
    with pytest.raises(EgoGraphMigrationError):
        load_robot_local_ego_graph(json.dumps(raw), case.config)
    with pytest.raises(EgoGraphMigrationError):
        migrate_legacy_ego_graph_schema("legacy-global-graph/68x11-unversioned")


def test_runtime_configuration_hash_mismatch_is_rejected(ego_v2_factory):
    _, _, payload = _serialized(ego_v2_factory)
    with pytest.raises(EgoGraphSerializationError, match="configuration hash"):
        load_robot_local_ego_graph(payload, RuntimeConfig.for_team_size(8))


def test_serialized_record_contains_no_evaluation_only_fields(ego_v2_factory):
    _, _, payload = _serialized(ego_v2_factory)
    lower = payload.lower()
    prohibited = (
        "global_centroid", "formation_error", "mission_outcome", "passage_label",
        "corridor_alpha", "scenario_family", "future_trajectory", "rollout",
    )
    assert all(token not in lower for token in prohibited)
