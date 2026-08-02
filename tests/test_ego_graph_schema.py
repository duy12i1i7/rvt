"""Mechanical contract tests for the authoritative ego-graph V2 schema."""

import pytest
import torch

from rvt_swarm.decentralized.ego_graph_v2 import (
    EDGE_FEATURE_DEFINITIONS,
    EDGE_FEATURE_DIM,
    EDGE_TYPES,
    EGO_GRAPH_FEATURE_SCHEMA_SHA256,
    EGO_GRAPH_NORMALIZATION_VERSION,
    EGO_GRAPH_SCHEMA_VERSION,
    NODE_FEATURE_DEFINITIONS,
    NODE_FEATURE_DIM,
    NODE_KINDS,
    NODE_SELF,
    build_robot_local_ego_graph,
)
from rvt_swarm.topology_registry import COMPACT, KEEP, LINE


@pytest.mark.parametrize("n", (5, 6, 8, 12, 16, 24))
@pytest.mark.parametrize("candidate", (KEEP, COMPACT, LINE))
def test_schema_constructs_for_every_required_size_and_topology(
    ego_v2_factory, n, candidate
):
    case = ego_v2_factory(n=n)
    graph = build_robot_local_ego_graph(
        case.view, case.config, case.local_topology, candidate, case.observation_step
    )

    assert graph.schema_version == EGO_GRAPH_SCHEMA_VERSION == "rvt-ego-graph/v2"
    assert graph.normalization_version == EGO_GRAPH_NORMALIZATION_VERSION
    assert len(EGO_GRAPH_FEATURE_SCHEMA_SHA256) == 64
    assert graph.candidate_topology_id == candidate
    assert graph.node_x.shape == (graph.n_nodes, NODE_FEATURE_DIM)
    assert graph.edge_attr.shape == (graph.n_edges, EDGE_FEATURE_DIM)
    assert graph.node_feature_valid_mask.shape == graph.node_x.shape
    assert graph.edge_feature_valid_mask.shape == graph.edge_attr.shape
    assert graph.node_valid_mask.dtype == torch.bool
    assert graph.edge_valid_mask.dtype == torch.bool
    assert graph.node_kind.dtype == torch.int64
    assert graph.edge_type.dtype == torch.int64
    assert graph.root_index == 0
    assert int(graph.node_kind[0]) == NODE_SELF
    assert int((graph.node_kind == NODE_SELF).sum()) == 1
    assert set(graph.node_kind.tolist()) <= set(NODE_KINDS)
    assert set(graph.edge_type.tolist()) <= set(EDGE_TYPES)
    assert graph.n_edges == 2 * (graph.n_peer_nodes + graph.n_obstacle_nodes)
    assert bool(torch.isfinite(graph.node_x).all())
    assert bool(torch.isfinite(graph.edge_attr).all())


def test_feature_definitions_tile_each_tensor_without_implicit_columns():
    assert sum(item.width for item in NODE_FEATURE_DEFINITIONS) == NODE_FEATURE_DIM
    assert sum(item.width for item in EDGE_FEATURE_DEFINITIONS) == EDGE_FEATURE_DIM
    assert len({item.name for item in NODE_FEATURE_DEFINITIONS}) == len(
        NODE_FEATURE_DEFINITIONS
    )
    assert len({item.name for item in EDGE_FEATURE_DEFINITIONS}) == len(
        EDGE_FEATURE_DEFINITIONS
    )
    for definition in NODE_FEATURE_DEFINITIONS + EDGE_FEATURE_DEFINITIONS:
        assert definition.units
        assert definition.normalization
        assert definition.runtime_source
        assert definition.missing_data


def test_schema_has_no_evaluation_or_outcome_fields(ego_v2_factory):
    case = ego_v2_factory()
    graph = build_robot_local_ego_graph(
        case.view, case.config, case.local_topology, KEEP, case.observation_step
    )
    prohibited = (
        "outcome", "success", "label", "alpha", "centroid", "global_formation",
        "minimum_distance", "exit_plane", "future_trajectory", "scenario_family",
    )
    field_names = " ".join(vars(graph)).lower()
    assert all(token not in field_names for token in prohibited)
