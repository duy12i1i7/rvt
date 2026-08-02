"""Actual controller terms are invariant to unavailable/evaluation variables."""

from dataclasses import replace

import numpy as np
import pytest

from rvt_swarm.decentralized.local_control_types import (
    LocalObstacleControlState,
    LocalPeerControlState,
)
from rvt_swarm.topology_registry import COMPACT, KEEP


def signature(output):
    return (
        output.formation_term,
        output.goal_term,
        output.obstacle_term,
        output.base_action,
        output.projected_action,
    )


@pytest.mark.parametrize("intervention", (
    "out_of_range_position",
    "out_of_range_velocity",
    "unobserved_obstacle",
    "global_centroid",
    "global_formation_error",
    "unobserved_role",
    "simulator_order",
    "evaluation_metadata",
))
def test_unavailable_interventions_leave_output_unchanged(
    phase6_input_factory, intervention
):
    runtime, adapter, _, controller_input = phase6_input_factory(topology=KEEP)
    expected = signature(adapter.controller.evaluate(controller_input))
    if intervention in ("out_of_range_position", "out_of_range_velocity", "unobserved_role"):
        outside = LocalPeerControlState(
            peer_robot_id=999,
            relative_position_meters=(runtime.communication.communication_range_meters + 1.0, 0.0),
            relative_velocity_meters_per_second=(999.0 if intervention == "out_of_range_velocity" else 0.0, 0.0),
            message_age_seconds=0.0,
        )
        changed = replace(controller_input, peer_states=controller_input.peer_states + (outside,))
    elif intervention == "unobserved_obstacle":
        outside = LocalObstacleControlState(
            "outside",
            (runtime.sensing.obstacle_sensing_range_meters + 1.0, 0.0),
            100.0,
            (-999.0, 0.0),
        )
        changed = replace(controller_input, obstacle_states=(outside,))
    elif intervention == "simulator_order":
        changed = replace(controller_input, peer_states=tuple(reversed(controller_input.peer_states)))
    else:
        # Centroid, global formation error and evaluation metadata are absent
        # from the closed input type, so the unchanged object is the intervention.
        changed = controller_input
    np.testing.assert_allclose(
        np.asarray(signature(adapter.controller.evaluate(changed))),
        np.asarray(expected),
        atol=1e-12,
    )


def test_fresh_local_peer_is_a_positive_control(phase6_input_factory):
    _, adapter, _, controller_input = phase6_input_factory(topology=KEEP)
    peer_id = controller_input.local_topology.formation_neighbours[0].peer_robot_id
    peer = next(item for item in controller_input.peer_states if item.peer_robot_id == peer_id)
    changed_peer = replace(peer, relative_position_meters=(
        peer.relative_position_meters[0] + 0.2,
        peer.relative_position_meters[1],
    ))
    changed = replace(
        controller_input,
        peer_states=tuple(changed_peer if item.peer_robot_id == peer_id else item
                          for item in controller_input.peer_states),
    )
    assert adapter.controller.evaluate(changed).formation_term != pytest.approx(
        adapter.controller.evaluate(controller_input).formation_term
    )


def test_local_obstacle_is_a_positive_control(phase6_input_factory):
    _, adapter, _, controller_input = phase6_input_factory(topology=KEEP)
    obstacle = LocalObstacleControlState("local", (0.7, 0.0), 0.35, (0.0, 0.0))
    changed = replace(controller_input, obstacle_states=(obstacle,))
    assert adapter.controller.evaluate(changed).obstacle_term != (0.0, 0.0)


def test_forced_topology_is_a_positive_control(phase6_input_factory):
    _, keep_adapter, keep_view, _ = phase6_input_factory(topology=KEEP)
    _, compact_adapter, compact_view, _ = phase6_input_factory(topology=COMPACT)
    keep = keep_adapter.evaluate(keep_view, 0.0)
    compact = compact_adapter.evaluate(compact_view, 0.0)
    assert keep.forced_topology_id != compact.forced_topology_id
    assert keep_adapter.local_topology_metadata.candidate(KEEP) != (
        compact_adapter.local_topology_metadata.candidate(COMPACT)
    )
