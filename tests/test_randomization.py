"""Finding 4 — can two different evaluation seeds produce identical initial states?

The manuscript states that the seed rule "ensures that all methods see matched
scenarios and matched random starts". Obstacle layouts are indeed seeded, but
`_spawn_agents` is a pure function of (n_agents, scenario) and consumes no
randomness at all, so every episode with the same team size and scenario starts
from the identical configuration. The goal is likewise a fixed constant.

Files involved
--------------
rvt_swarm/environment.py:44-78   `reset` (seeds `self.rng`, fixes the goal)
rvt_swarm/environment.py:50      `goal = [world_size * 0.38, 0.0]`  (constant)
rvt_swarm/environment.py:80-92   `_spawn_agents` (deterministic lattice)
rvt_swarm/environment.py:94-122  `_spawn_obstacles` (correctly seeded)
rvt_swarm/evaluate.py:83-87      `_setting_episode_seeds`

The start-position test asserts the documented behaviour and therefore fails
against the unfixed code. The goal test records a *remaining* limitation that
this change deliberately does not address.
"""

from __future__ import annotations

import numpy as np

from rvt_swarm.config import Config
from rvt_swarm.environment import SwarmFormationEnv


def _reset(seed: int, n_agents: int = 8, scenario: str = "narrow_passage") -> dict:
    return SwarmFormationEnv(Config()).reset(n_agents, scenario, seed=seed)


def test_different_seeds_give_different_start_positions() -> None:
    a = _reset(1)
    b = _reset(99_999)

    assert not np.allclose(a["positions"], b["positions"]), (
        "two different evaluation seeds produced byte-identical start positions; "
        "episodes are not independently initialised"
    )


def test_same_seed_is_still_reproducible() -> None:
    """Randomising starts must not cost determinism."""
    a = _reset(4242)
    b = _reset(4242)

    assert np.allclose(a["positions"], b["positions"])
    assert np.allclose(a["obstacles"], b["obstacles"])


def test_start_positions_vary_across_a_seed_sweep() -> None:
    """A single differing pair could be luck; require broad variation."""
    starts = [_reset(s)["positions"] for s in range(20, 40)]
    reference = starts[0]
    differing = sum(1 for s in starts[1:] if not np.allclose(s, reference))

    assert differing == len(starts) - 1, (
        f"only {differing}/{len(starts) - 1} seeds produced a distinct start configuration"
    )


def test_spawn_randomisation_never_creates_an_initial_collision() -> None:
    """Jittered starts must remain feasible for every team size and scenario."""
    cfg = Config()
    for scenario in cfg.env.scenarios:
        for n_agents in (2, 8, 24):
            for seed in range(5):
                obs = SwarmFormationEnv(cfg).reset(n_agents, scenario, seed=seed)
                pos = obs["positions"]
                deltas = pos[:, None, :] - pos[None, :, :]
                distances = np.linalg.norm(deltas, axis=-1)
                np.fill_diagonal(distances, np.inf)
                closest = float(distances.min())
                assert closest >= cfg.env.min_rr_distance, (
                    f"{scenario} N={n_agents} seed={seed}: robots spawn "
                    f"{closest:.4f} m apart, inside the collision threshold"
                )


def test_spawn_randomisation_never_starts_a_robot_outside_the_workspace() -> None:
    """Regression: jitter pushed the outermost narrow_passage column out of bounds.

    That layout uses four columns whose outermost offset sits ~9 mm inside the
    boundary, so un-clamped jitter started robots up to ~3 cm outside the world.
    Caught by consistency check 8 during the protocol-v2 smoke benchmark.
    """
    cfg = Config()
    limit = cfg.env.world_size * 0.5
    for scenario in cfg.env.scenarios:
        for n_agents in (2, 4, 8, 16, 24):
            for seed in range(8):
                pos = SwarmFormationEnv(cfg).reset(n_agents, scenario, seed=seed)["positions"]
                worst = float(np.abs(pos).max())
                assert worst <= limit, (
                    f"{scenario} N={n_agents} seed={seed}: robot starts at "
                    f"|pos|={worst:.4f} m, outside the {limit:.1f} m workspace bound"
                )


def test_obstacle_layouts_were_already_seeded() -> None:
    """Scopes the finding: obstacles were never the problem, starts were."""
    a = _reset(1)
    b = _reset(99_999)
    assert not np.allclose(a["obstacles"], b["obstacles"])


def test_goal_is_constant_across_seeds_known_remaining_limitation() -> None:
    """DOCUMENTED LIMITATION, not a passing grade.

    Every episode in the benchmark drives to the same goal at
    (world_size * 0.38, 0). Randomising the goal is a benchmark-design change
    that is deliberately out of scope for this minimal correction; see
    docs/BENCHMARK_BUG_VERIFICATION.md. This test exists so that the limitation
    fails loudly (and the documentation gets updated) the moment someone
    randomises the goal.
    """
    a = _reset(1)
    b = _reset(99_999)
    assert np.allclose(a["goal"], b["goal"])
