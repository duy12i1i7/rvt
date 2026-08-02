"""Shared registry-sliced robot-local formation controller mechanics."""

from dataclasses import replace

import numpy as np
import pytest

from rvt_swarm.decentralized.local_control_types import LocalPeerControlState
from rvt_swarm.decentralized.robot_local_controller import robot_local_formation_term
from rvt_swarm.topology_registry import COMPACT, KEEP, LINE


@pytest.mark.parametrize("n", (5, 6, 8, 12, 16, 24))
@pytest.mark.parametrize("topology", (KEEP, COMPACT, LINE))
def test_exact_topology_has_zero_local_formation_term(
    phase6_input_factory, n, topology
):
    runtime, _, _, controller_input = phase6_input_factory(n=n, topology=topology)
    term, used, missing = robot_local_formation_term(controller_input, runtime)
    np.testing.assert_allclose(term, (0.0, 0.0), atol=1e-12)
    assert used + missing == len(controller_input.local_topology.formation_neighbours)


def test_fresh_nominal_peer_changes_formation_term(phase6_input_factory):
    runtime, _, _, controller_input = phase6_input_factory(topology=COMPACT)
    peer_id = controller_input.local_topology.formation_neighbours[0].peer_robot_id
    peer = next(item for item in controller_input.peer_states if item.peer_robot_id == peer_id)
    moved = replace(
        peer,
        relative_position_meters=(peer.relative_position_meters[0] + 0.2,
                                  peer.relative_position_meters[1]),
    )
    changed = replace(
        controller_input,
        peer_states=tuple(moved if item.peer_robot_id == peer_id else item
                          for item in controller_input.peer_states),
    )
    original = robot_local_formation_term(controller_input, runtime)[0]
    actual = robot_local_formation_term(changed, runtime)[0]
    assert actual[0] > original[0]


def test_zero_neighbour_and_stale_neighbour_are_explicit(phase6_input_factory):
    runtime, _, _, controller_input = phase6_input_factory(topology=LINE)
    empty = replace(controller_input, peer_states=())
    assert robot_local_formation_term(empty, runtime) == (
        (0.0, 0.0),
        0,
        len(controller_input.local_topology.formation_neighbours),
    )
    peer = controller_input.peer_states[0]
    stale = replace(
        controller_input,
        peer_states=(replace(
            peer,
            message_age_seconds=(
                runtime.communication.maximum_message_age_seconds
                + runtime.communication.communication_period_seconds
            ),
        ),),
    )
    assert robot_local_formation_term(stale, runtime)[1] == 0


def test_nonformation_peer_cannot_change_term(phase6_input_factory):
    runtime, _, _, controller_input = phase6_input_factory(n=8, topology=LINE)
    nominal_ids = {
        item.peer_robot_id for item in controller_input.local_topology.formation_neighbours
    }
    unrelated = next(
        item for item in controller_input.peer_states
        if item.peer_robot_id not in nominal_ids
    )
    changed_peer = replace(unrelated, relative_position_meters=(0.41, -0.27))
    changed = replace(
        controller_input,
        peer_states=tuple(changed_peer if item.peer_robot_id == unrelated.peer_robot_id else item
                          for item in controller_input.peer_states),
    )
    assert robot_local_formation_term(changed, runtime)[0] == pytest.approx(
        robot_local_formation_term(controller_input, runtime)[0], abs=1e-12
    )


def test_out_of_range_peer_is_excluded(phase6_input_factory):
    runtime, _, _, controller_input = phase6_input_factory(topology=KEEP)
    fake = LocalPeerControlState(
        peer_robot_id=999,
        relative_position_meters=(
            runtime.communication.communication_range_meters
            + runtime.formation.nominal_spacing_meters,
            0.0,
        ),
        relative_velocity_meters_per_second=(0.0, 0.0),
        message_age_seconds=0.0,
    )
    changed = replace(controller_input, peer_states=controller_input.peer_states + (fake,))
    assert robot_local_formation_term(changed, runtime)[0] == pytest.approx(
        robot_local_formation_term(controller_input, runtime)[0], abs=1e-12
    )
