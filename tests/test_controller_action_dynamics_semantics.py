"""Two-dimensional controller actions match simulator acceleration semantics."""

import numpy as np
import pytest

from rvt_swarm.config import Config
from rvt_swarm.decentralized.phase6_qualification import semi_implicit_acceleration_step
from rvt_swarm.environment import SwarmFormationEnv
from rvt_swarm.runtime_configuration import DEFAULT_RUNTIME_CONFIG


def test_action_is_acceleration_under_semi_implicit_euler():
    config = DEFAULT_RUNTIME_CONFIG
    position, velocity = semi_implicit_acceleration_step(
        (1.0, -2.0),
        (0.1, 0.2),
        (0.3, -0.4),
        config,
    )
    expected_velocity = np.array((0.1, 0.2)) + np.array((0.3, -0.4)) * 0.15
    expected_position = np.array((1.0, -2.0)) + expected_velocity * 0.15
    np.testing.assert_allclose(velocity, expected_velocity, atol=1e-12)
    np.testing.assert_allclose(position, expected_position, atol=1e-12)


def test_acceleration_and_speed_are_radially_clipped():
    config = DEFAULT_RUNTIME_CONFIG
    position, velocity = semi_implicit_acceleration_step(
        (0.0, 0.0),
        (0.9, 0.0),
        (100.0, 100.0),
        config,
    )
    assert np.linalg.norm(velocity) <= config.physical.maximum_speed_meters_per_second + 1e-12
    assert np.asarray(position).shape == (2,)


def test_mechanical_integrator_matches_environment_without_contact():
    legacy = Config()
    legacy.env.obstacle_count = 0
    environment = SwarmFormationEnv(legacy)
    environment.reset(1, "open_field", seed=4)
    environment.state.obstacles = np.zeros((0, 2), dtype=np.float32)
    environment.state.obstacle_velocities = np.zeros((0, 2), dtype=np.float32)
    environment.state.positions[0] = np.array((0.0, 0.0), dtype=np.float32)
    environment.state.velocities[0] = np.array((0.1, -0.2), dtype=np.float32)
    action = (0.3, 0.4)
    expected_position, expected_velocity = semi_implicit_acceleration_step(
        (0.0, 0.0),
        (0.1, -0.2),
        action,
        DEFAULT_RUNTIME_CONFIG,
    )
    environment.step(np.asarray((action,), dtype=np.float32), 0)
    np.testing.assert_allclose(environment.state.velocities[0], expected_velocity, atol=1e-7)
    np.testing.assert_allclose(environment.state.positions[0], expected_position, atol=1e-7)


def test_phase5_residual_units_are_acceleration():
    from rvt_swarm.fd24.configuration import residual_action_limits
    from rvt_swarm.fd24.configuration import FD24ModelConfig

    limits = residual_action_limits(FD24ModelConfig(), DEFAULT_RUNTIME_CONFIG)
    assert limits == pytest.approx((0.15, 0.15))
    assert all(limit < DEFAULT_RUNTIME_CONFIG.physical.maximum_acceleration_meters_per_second_squared
               for limit in limits)
