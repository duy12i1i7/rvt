"""Freshness, duplicate, loss, and missing-data behavior."""

from dataclasses import replace

import pytest
import torch

from rvt_swarm.decentralized.ego_graph_v2 import (
    NODE_FEATURE_SLICES,
    LocalObstacleObservation,
    build_robot_local_ego_graph,
)
from rvt_swarm.topology_registry import KEEP


def _build(case, view=None):
    return build_robot_local_ego_graph(
        case.view if view is None else view,
        case.config,
        case.local_topology,
        KEEP,
        case.observation_step,
    )


def test_stale_future_lost_and_out_of_range_peers_are_omitted(ego_v2_factory):
    case = ego_v2_factory(peer_ids=(1, 2, 3, 4))
    stale_limit = case.config.derived.message_stale_rounds
    comm = case.config.communication.communication_range_meters
    records = (
        replace(case.view.neighbours[0], message_age_steps=stale_limit + 1),
        replace(case.view.neighbours[1], message_age_steps=-1),
        replace(case.view.neighbours[2], link_valid=False),
        replace(case.view.neighbours[3], rel_position=(comm + 0.1, 0.0)),
    )
    graph = _build(case, replace(case.view, neighbours=records))
    assert graph.n_peer_nodes == 0
    assert graph.n_nodes == 1


def test_invalid_sender_or_topology_is_omitted(ego_v2_factory):
    case = ego_v2_factory(peer_ids=(1, 2))
    records = (
        replace(case.view.neighbours[0], robot_id=case.view.robot_id),
        replace(case.view.neighbours[1], committed_mode=999),
    )
    assert _build(case, replace(case.view, neighbours=records)).n_peer_nodes == 0


def test_exact_duplicate_collapses_and_fresher_duplicate_wins(ego_v2_factory):
    case = ego_v2_factory(peer_ids=(1,), peer_ages={1: 2})
    old = case.view.neighbours[0]
    duplicate_graph = _build(
        case, replace(case.view, neighbours=(old, old))
    )
    assert duplicate_graph.n_peer_nodes == 1

    fresh = replace(old, message_age_steps=0, rel_position=(0.7, 0.1))
    selected = _build(case, replace(case.view, neighbours=(old, fresh)))
    position = selected.node_x[1, NODE_FEATURE_SLICES["relative_position_spacing"]]
    spacing = case.config.formation.nominal_spacing_meters
    torch.testing.assert_close(position, torch.tensor((0.7 / spacing, 0.1 / spacing)))


def test_conflicting_same_age_duplicate_is_omitted(ego_v2_factory):
    case = ego_v2_factory(peer_ids=(1,))
    record = case.view.neighbours[0]
    conflict = replace(record, rel_position=(record.rel_position[0] + 0.2, 0.0))
    graph = _build(case, replace(case.view, neighbours=(record, conflict)))
    assert graph.n_peer_nodes == 0


def test_missing_peer_velocity_uses_zero_with_false_feature_mask(ego_v2_factory):
    case = ego_v2_factory(peer_ids=(1,))
    record = replace(case.view.neighbours[0], rel_velocity=None)
    graph = _build(case, replace(case.view, neighbours=(record,)))
    block = NODE_FEATURE_SLICES["relative_velocity_speed"]
    assert graph.node_x[1, block].tolist() == [0.0, 0.0]
    assert graph.node_feature_valid_mask[1, block].tolist() == [False, False]


def test_stale_invalid_and_partial_obstacle_behavior(ego_v2_factory):
    control = ego_v2_factory().config.physical.control_period_seconds
    case = ego_v2_factory(
        peer_ids=(),
        obstacles=(
            LocalObstacleObservation((1.0, 0.0), 0.2, age_seconds=control + 1e-3),
            LocalObstacleObservation((1.2, 0.0), 0.2, valid=False),
            LocalObstacleObservation((1.4, 0.0), 0.2, None, 0.8, control / 2),
        ),
    )
    graph = _build(case)
    assert graph.n_obstacle_nodes == 1
    block = NODE_FEATURE_SLICES["relative_velocity_speed"]
    assert not bool(graph.node_feature_valid_mask[1, block].any())
    assert float(graph.node_x[1, NODE_FEATURE_SLICES["obstacle_confidence"]][0]) == pytest.approx(0.8)


def test_temporary_loss_drops_peer_immediately(ego_v2_factory):
    present = ego_v2_factory(peer_ids=(1,))
    assert _build(present).n_peer_nodes == 1
    lost = replace(
        present.view,
        neighbours=(replace(present.view.neighbours[0], link_valid=False),),
    )
    assert _build(present, lost).n_peer_nodes == 0
