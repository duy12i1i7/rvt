"""Mission-frame, invariance, and physical normalization tests."""

import math

import torch

from rvt_swarm.decentralized.ego_graph_v2 import (
    NODE_FEATURE_SLICES,
    build_robot_local_ego_graph,
)
from rvt_swarm.topology_registry import KEEP


def _build(case):
    return build_robot_local_ego_graph(
        case.view, case.config, case.local_topology, KEEP, case.observation_step
    )


def test_world_translation_does_not_change_graph(ego_v2_factory):
    a = _build(ego_v2_factory(origin=(2.0, -1.0)))
    b = _build(ego_v2_factory(origin=(101.0, 44.0)))
    assert a.fingerprint() == b.fingerprint()


def test_joint_rotation_with_mission_heading_preserves_features(ego_v2_factory):
    base = _build(ego_v2_factory(
        mission=(1.0, 0.0),
        peer_local_positions={1: (1.2, -0.4)},
        peer_ids=(1,),
        obstacles=((2.0, 0.5, 0.2, -0.1, 0.03),),
    ))
    rotated = _build(ego_v2_factory(
        mission=(0.0, 1.0),
        peer_local_positions={1: (1.2, -0.4)},
        peer_ids=(1,),
        obstacles=((2.0, 0.5, 0.2, -0.1, 0.03),),
    ))
    torch.testing.assert_close(base.node_x, rotated.node_x, rtol=0.0, atol=1e-6)
    torch.testing.assert_close(base.edge_attr, rotated.edge_attr, rtol=0.0, atol=1e-6)
    assert torch.equal(base.node_feature_valid_mask, rotated.node_feature_valid_mask)
    assert torch.equal(base.edge_feature_valid_mask, rotated.edge_feature_valid_mask)


def test_declared_normalization_uses_runtime_physical_configuration(ego_v2_factory):
    case = ego_v2_factory(
        peer_ids=(1,), peer_local_positions={1: (0.9, 0.0)},
        own_velocity_local=(0.45, -0.225), goal_local=(1.8, 0.9),
    )
    graph = _build(case)
    peer = graph.node_x[1]
    root = graph.node_x[0]
    spacing = case.config.formation.nominal_spacing_meters
    speed = case.config.physical.maximum_speed_meters_per_second
    comm = case.config.communication.communication_range_meters

    torch.testing.assert_close(
        peer[NODE_FEATURE_SLICES["relative_position_spacing"]],
        torch.tensor((0.9 / spacing, 0.0)),
    )
    torch.testing.assert_close(
        peer[NODE_FEATURE_SLICES["distance_range"]],
        torch.tensor((0.9 / comm,)),
    )
    torch.testing.assert_close(
        root[NODE_FEATURE_SLICES["self_velocity_speed"]],
        torch.tensor((0.45 / speed, -0.225 / speed)),
    )
    torch.testing.assert_close(
        root[NODE_FEATURE_SLICES["goal_vector_spacing"]],
        torch.tensor((1.8 / spacing, 0.9 / spacing)),
    )
    assert math.isclose(
        float(root[NODE_FEATURE_SLICES["goal_distance_spacing"]][0]),
        math.hypot(1.8, 0.9) / spacing,
        rel_tol=1e-6,
    )
