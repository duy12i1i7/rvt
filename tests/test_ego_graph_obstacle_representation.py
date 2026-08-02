"""Local obstacle primitive conversion and observability tests."""

import pytest
import torch

from rvt_swarm.decentralized.ego_graph_v2 import (
    EDGE_SELF_TO_OBSTACLE,
    NODE_FEATURE_SLICES,
    NODE_OBSTACLE,
    LocalObstacleObservation,
    build_robot_local_ego_graph,
)
from rvt_swarm.topology_registry import KEEP


def _build(case):
    return build_robot_local_ego_graph(
        case.view, case.config, case.local_topology, KEEP, case.observation_step
    )


@pytest.mark.parametrize("count", (0, 1, 4))
def test_variable_obstacle_count_uses_no_padding(ego_v2_factory, count):
    obstacles = tuple((1.0 + index * 0.3, 0.1 * index, 0.1) for index in range(count))
    graph = _build(ego_v2_factory(peer_ids=(), obstacles=obstacles))
    assert graph.n_obstacle_nodes == count
    assert graph.n_nodes == 1 + count
    assert graph.n_edges == 2 * count
    assert graph.node_valid_mask.tolist() == [True] * (1 + count)


def test_obstacle_node_uses_relative_closest_point_not_global_centroid(
    ego_v2_factory,
):
    case = ego_v2_factory(peer_ids=(), obstacles=((2.0, 0.0, 0.5),))
    graph = _build(case)
    spacing = case.config.formation.nominal_spacing_meters
    obs_range = case.config.sensing.obstacle_sensing_range_meters
    assert int(graph.node_kind[1]) == NODE_OBSTACLE
    torch.testing.assert_close(
        graph.node_x[1, NODE_FEATURE_SLICES["relative_position_spacing"]],
        torch.tensor((1.5 / spacing, 0.0)),
    )
    torch.testing.assert_close(
        graph.node_x[1, NODE_FEATURE_SLICES["distance_range"]],
        torch.tensor((1.5 / obs_range,)),
    )
    assert int(graph.edge_type[0]) == EDGE_SELF_TO_OBSTACLE
    assert graph.node_source_key[1].startswith("obstacle-local:")


def test_center_range_gate_omits_unobservable_obstacle(ego_v2_factory):
    base = ego_v2_factory(peer_ids=())
    sensing = base.config.sensing.obstacle_sensing_range_meters
    graph = _build(ego_v2_factory(
        peer_ids=(), obstacles=((sensing + 0.01, 0.0, 100.0),)
    ))
    assert graph.n_obstacle_nodes == 0


def test_invalid_observations_are_omitted_and_exact_duplicates_collapse(
    ego_v2_factory,
):
    valid = LocalObstacleObservation((1.0, 0.0), 0.2)
    case = ego_v2_factory(
        peer_ids=(),
        obstacles=(
            valid,
            valid,
            LocalObstacleObservation((1.1, 0.0), -0.1),
            LocalObstacleObservation((1.2, 0.0), 0.1, confidence=1.2),
        ),
    )
    assert _build(case).n_obstacle_nodes == 1


def test_local_dynamic_obstacle_features_preserve_age_confidence_and_velocity(
    ego_v2_factory,
):
    obstacle = LocalObstacleObservation(
        (1.0, -0.5), 0.2, (0.1, -0.05), confidence=0.75, age_seconds=0.02
    )
    case = ego_v2_factory(peer_ids=(), obstacles=(obstacle,))
    graph = _build(case)
    speed = case.config.physical.maximum_speed_meters_per_second
    period = case.config.physical.control_period_seconds
    torch.testing.assert_close(
        graph.node_x[1, NODE_FEATURE_SLICES["relative_velocity_speed"]],
        torch.tensor((0.1 / speed, -0.05 / speed)),
    )
    assert float(graph.node_x[1, NODE_FEATURE_SLICES["obstacle_confidence"]][0]) == pytest.approx(0.75)
    assert float(graph.node_x[1, NODE_FEATURE_SLICES["obstacle_age_control_period"]][0]) == pytest.approx(0.02 / period)
