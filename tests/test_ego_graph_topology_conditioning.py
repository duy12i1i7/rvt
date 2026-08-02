"""Robot-local candidate-topology conditioning tests."""

from dataclasses import replace

import pytest
import torch

from rvt_swarm.decentralized.ego_graph_v2 import (
    EDGE_FEATURE_SLICES,
    NODE_FEATURE_SLICES,
    RobotLocalTopologyMetadata,
    build_robot_local_ego_graph,
)
from rvt_swarm.topology_registry import (
    COMPACT,
    KEEP,
    LINE,
    PRIMARY_TOPOLOGY_IDS,
    TOPOLOGY_REGISTRY_SCHEMA_VERSION,
)


@pytest.mark.parametrize("candidate", (KEEP, COMPACT, LINE))
def test_candidate_id_and_own_role_features_are_explicit(
    ego_v2_factory, candidate
):
    case = ego_v2_factory(peer_ids=())
    graph = build_robot_local_ego_graph(
        case.view, case.config, case.local_topology, candidate, case.observation_step
    )
    onehot = graph.node_x[0, NODE_FEATURE_SLICES["candidate_topology_onehot"]]
    expected = torch.tensor([
        1.0 if item == candidate else 0.0 for item in PRIMARY_TOPOLOGY_IDS
    ])
    assert graph.candidate_topology_id == candidate
    assert torch.equal(onehot, expected)


@pytest.mark.parametrize("candidate", (KEEP, COMPACT, LINE))
def test_desired_pairwise_offset_comes_from_local_registry_slice(
    ego_v2_factory, candidate
):
    seed = ego_v2_factory(peer_ids=())
    local_candidate = seed.local_topology.candidate(candidate)
    neighbour = local_candidate.formation_neighbours[0]
    case = ego_v2_factory(
        peer_ids=(neighbour.peer_robot_id,),
        peer_local_positions={
            neighbour.peer_robot_id: neighbour.desired_offset_from_observer_meters
        },
    )
    graph = build_robot_local_ego_graph(
        case.view, case.config, case.local_topology, candidate, case.observation_step
    )
    spacing = case.config.formation.nominal_spacing_meters
    desired = graph.edge_attr[0, EDGE_FEATURE_SLICES["desired_pairwise_offset_spacing"]]
    residual = graph.edge_attr[0, EDGE_FEATURE_SLICES["formation_residual_spacing"]]
    torch.testing.assert_close(
        desired,
        torch.tensor(neighbour.desired_offset_from_observer_meters) / spacing,
    )
    torch.testing.assert_close(residual, torch.zeros(2), atol=1e-6, rtol=0.0)


def test_unobserved_nominal_neighbour_metadata_does_not_create_node_or_edge(
    ego_v2_factory,
):
    case = ego_v2_factory(n=12, peer_ids=())
    candidate = case.local_topology.candidate(COMPACT)
    altered = replace(
        candidate,
        formation_neighbours=tuple(
            replace(
                item,
                candidate_role_offset_meters=(999.0, -999.0),
                desired_offset_from_observer_meters=(555.0, -555.0),
            )
            for item in candidate.formation_neighbours
        ),
    )
    local = replace(
        case.local_topology,
        candidates=tuple(
            altered if item.topology_id == COMPACT else item
            for item in case.local_topology.candidates
        ),
    )
    before = build_robot_local_ego_graph(
        case.view, case.config, case.local_topology, COMPACT, case.observation_step
    )
    after = build_robot_local_ego_graph(
        case.view, case.config, local, COMPACT, case.observation_step
    )
    assert before.fingerprint() == after.fingerprint()
    assert before.n_nodes == 1
    assert before.n_edges == 0


def test_local_slice_preserves_phase3_registry_identity(ego_v2_factory):
    local = ego_v2_factory().local_topology
    assert local.topology_registry_schema_version == TOPOLOGY_REGISTRY_SCHEMA_VERSION
    assert tuple(item.topology_id for item in local.candidates) == PRIMARY_TOPOLOGY_IDS
    assert set(RobotLocalTopologyMetadata.__dataclass_fields__) == {
        "topology_registry_schema_version", "observer_robot_id",
        "observer_role_id", "team_size", "candidates",
    }
