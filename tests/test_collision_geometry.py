"""Findings 2 and 3 — is the collision threshold reachable by the simulator itself?

Finding 2: `_resolve_collisions()` separates contacting bodies to a distance that
is still *inside* the distance the metric calls a collision, so any contact that
is being resolved is scored as a collision on that step.

Finding 3: at maximum compression the *commanded* formation spacing equals the
robot-robot collision threshold, i.e. the controller's own set-point sits exactly
on the failure boundary.

Files involved
--------------
rvt_swarm/environment.py:413-461  `_resolve_collisions` (separation targets)
rvt_swarm/environment.py:522-560  `compute_metrics` (collision thresholds)
rvt_swarm/config.py:16-19         robot_radius / obstacle_radius / min_rr / min_ro
rvt_swarm/environment.py:255      `min_scale` used by `apply_topology`
rvt_swarm/controllers.py:28       duplicated `min_scale` used by `expert_action`

These tests assert the invariant "the simulator must be able to satisfy its own
metric", so they fail against the unfixed code.
"""

from __future__ import annotations

import numpy as np

from rvt_swarm.config import Config
from rvt_swarm.controllers import _project_topology_state
from rvt_swarm.environment import SwarmFormationEnv


def _bare_env(n_agents: int = 2) -> SwarmFormationEnv:
    cfg = Config()
    env = SwarmFormationEnv(cfg)
    env.reset(n_agents, "open_field", seed=0)
    env.state.obstacles = np.zeros((0, 2), dtype=np.float32)
    env.state.obstacle_velocities = np.zeros((0, 2), dtype=np.float32)
    env.state.velocities = np.zeros((n_agents, 2), dtype=np.float32)
    return env


# --------------------------------------------------------------------------
# Finding 2 — resolver vs. metric
# --------------------------------------------------------------------------
def test_robot_robot_resolution_clears_the_collision_threshold() -> None:
    env = _bare_env(2)
    cfg = env.cfg
    env.state.positions = np.array([[0.0, 0.0], [0.10, 0.0]], dtype=np.float32)

    env._resolve_collisions()
    separation = float(np.linalg.norm(env.state.positions[0] - env.state.positions[1]))

    assert separation >= cfg.env.min_rr_distance, (
        f"resolver left robots {separation:.4f} m apart, inside the "
        f"{cfg.env.min_rr_distance:.4f} m robot-robot collision threshold"
    )


def test_robot_obstacle_resolution_clears_the_collision_threshold() -> None:
    env = _bare_env(2)
    cfg = env.cfg
    env.state.obstacles = np.array([[0.0, 0.0]], dtype=np.float32)
    env.state.obstacle_velocities = np.zeros((1, 2), dtype=np.float32)
    env.state.positions = np.array([[0.05, 0.0], [6.0, 6.0]], dtype=np.float32)

    env._resolve_collisions()
    distance = float(np.linalg.norm(env.state.positions[0] - env.state.obstacles[0]))

    assert distance >= cfg.env.min_ro_distance, (
        f"resolver left the robot {distance:.4f} m from the obstacle, inside the "
        f"{cfg.env.min_ro_distance:.4f} m robot-obstacle collision threshold"
    )


def test_state_is_collision_free_immediately_after_resolution() -> None:
    """The end-to-end consequence: resolution must produce a clean metric."""
    env = _bare_env(2)
    env.state.obstacles = np.array([[1.5, 0.0]], dtype=np.float32)
    env.state.obstacle_velocities = np.zeros((1, 2), dtype=np.float32)
    env.state.positions = np.array([[0.0, 0.0], [0.12, 0.0]], dtype=np.float32)

    env._resolve_collisions()
    metrics = env.compute_metrics()

    assert metrics["rr_collision"] == 0.0
    assert metrics["ro_collision"] == 0.0
    assert metrics["collision_free"] == 1.0, (
        "a state the simulator has just declared resolved is still scored as a collision"
    )


# --------------------------------------------------------------------------
# Finding 3 — commanded spacing vs. metric
# --------------------------------------------------------------------------
def test_minimum_commanded_spacing_exceeds_collision_threshold() -> None:
    cfg = Config()
    env = SwarmFormationEnv(cfg)
    env.reset(6, "narrow_passage", seed=0)

    # Drive the formation scale to its floor by asserting maximum bottleneck.
    env.state.bottleneck_score = 1.0
    for _ in range(50):
        env.apply_topology(1)  # compress
    min_spacing = cfg.env.nominal_spacing * env.state.formation_scale

    assert min_spacing > cfg.env.min_rr_distance, (
        f"fully compressed formation commands {min_spacing:.4f} m spacing, which is "
        f"not above the {cfg.env.min_rr_distance:.4f} m robot-robot collision threshold"
    )


def test_expert_controller_uses_the_same_spacing_floor() -> None:
    """controllers.py duplicates the scale floor; the two must not diverge."""
    cfg = Config()
    obs = {
        "positions": np.zeros((6, 2), dtype=np.float32),
        "bottleneck": 1.0,
        "split_active": 0.0,
        "formation_scale": 0.0,  # request the floor
        "topology_mode": 0,
        "corridor_dx": 1.0,
        "corridor_dy": 0.0,
        "subteam_ids": np.zeros((6,), dtype=np.int64),
    }
    _, scale, _ = _project_topology_state(obs, cfg, 1)
    controller_spacing = cfg.env.nominal_spacing * scale

    env = SwarmFormationEnv(cfg)
    env.reset(6, "narrow_passage", seed=0)
    env.state.bottleneck_score = 1.0
    env.state.formation_scale = 0.0
    env.apply_topology(1)
    env_spacing = cfg.env.nominal_spacing * env.state.formation_scale

    assert controller_spacing == env_spacing, "expert and environment scale floors diverge"
    assert controller_spacing > cfg.env.min_rr_distance


def test_desired_offsets_at_minimum_scale_are_mutually_feasible() -> None:
    """The template itself must not place two robots inside the collision threshold."""
    cfg = Config()
    env = SwarmFormationEnv(cfg)
    env.reset(8, "narrow_passage", seed=0)
    env.state.bottleneck_score = 1.0
    for _ in range(50):
        env.apply_topology(1)
    scale = env.state.formation_scale

    for mode in (0, 2, 3):  # keep, line, split
        offsets = env.desired_offsets(mode=mode, scale=scale)
        deltas = offsets[:, None, :] - offsets[None, :, :]
        distances = np.linalg.norm(deltas, axis=-1)
        np.fill_diagonal(distances, np.inf)
        closest = float(distances.min())
        assert closest > cfg.env.min_rr_distance, (
            f"template mode={mode} at scale={scale:.4f} commands a closest pair of "
            f"{closest:.4f} m, at or inside the {cfg.env.min_rr_distance:.4f} m threshold"
        )
