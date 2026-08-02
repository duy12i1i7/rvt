import math

import pytest

import rvt_swarm.decentralized.transition_runtime as transition_runtime
from rvt_swarm.decentralized.transition_admissibility import ADMITTED_DIRECTED_PAIRS
from rvt_swarm.decentralized.transition_protocol import TransitionProtocolRuntimeOptions
from rvt_swarm.decentralized.transition_readiness import (
    RobotLocalTransitionInput,
    construct_robot_local_transition_envelope,
)


def _input(n, source, target, robot_id=0, fixture="exact_source"):
    graph = transition_runtime.communication_graph(n, "complete")
    runtime = transition_runtime.StrictTransitionRuntime(
        n, source, graph, options=TransitionProtocolRuntimeOptions(True)
    )
    positions, velocities, origin, direction = transition_runtime._initial_state(
        n, source, fixture, runtime.runtime_config
    )
    intent = runtime.nodes[0].request_intent(
        1, target, "externally_forced_diagnostic", 0.0
    )
    assert intent is not None
    for node in runtime.nodes:
        node.adopt_intent(intent, 0.0)
    certs = runtime.local_readiness_certificates(
        positions, velocities, source, target, 1, intent.epoch_id,
        0.0, origin, direction,
    )
    cert = certs[robot_id]
    return cert.envelope, runtime.runtime_config


@pytest.mark.parametrize("n", (5, 6, 8, 12, 16, 24))
@pytest.mark.parametrize("source,target", ADMITTED_DIRECTED_PAIRS)
def test_envelope_supports_all_pairs_and_variable_n(n, source, target):
    envelope, config = _input(n, source, target)
    assert envelope.supported
    assert envelope.observation_complete
    assert 0.0 <= envelope.certified_fraction <= 1.0
    assert envelope.prediction_horizon_seconds > config.physical.control_period_seconds


def test_translation_and_rotation_do_not_change_required_extent():
    exact, _ = _input(6, 2, 0, 0, "exact_source")
    rotated, _ = _input(6, 2, 0, 0, "rotated_mission")
    assert rotated.required_observation_extent_meters == pytest.approx(
        exact.required_observation_extent_meters
    )
    assert math.hypot(*rotated.full_role_displacement_world_meters) == pytest.approx(
        math.hypot(*exact.full_role_displacement_world_meters)
    )
