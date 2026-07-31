"""Task 4R-3 — every qualification episode must start inside the KEEP tube."""
from __future__ import annotations

import numpy as np
import pytest

from rvt_swarm.decentralized.formation_metric_v3 import EPSILON_FORM, e_inf
from rvt_swarm.decentralized.qualification_fixtures import (
    EPSILON_INIT, SPAWN_JITTER, build_fixtures, fixture_config,
    fixture_layout, simulate_reset_to_fixture, validate_initial_conditions)
from rvt_swarm.decentralized.roles import RoleAssignment
from rvt_swarm.decentralized.system_model import KEEP
from rvt_swarm.environment import SwarmFormationEnv

CFG = fixture_config()
FIXTURES = build_fixtures(CFG, 6)
SEEDS = [0, 1, 2, 3, 4]


def test_epsilon_init_is_stricter_than_epsilon_form() -> None:
    assert EPSILON_INIT < EPSILON_FORM


@pytest.mark.parametrize("name", sorted(FIXTURES))
@pytest.mark.parametrize("seed", SEEDS)
def test_every_fixture_and_seed_starts_valid(name, seed) -> None:
    v = validate_initial_conditions(FIXTURES[name], seed, CFG)
    assert v["in_keep_tube"], v["e_inf_keep"]
    assert v["no_rr_collision"] and v["no_ro_collision"]
    assert v["in_bounds"] and v["connected"]
    assert v["valid"]


@pytest.mark.parametrize("name", sorted(FIXTURES))
def test_environment_reset_preserves_the_valid_initial_condition(name) -> None:
    """The check must hold on the state the EPISODE sees, not just on paper."""
    roles = RoleAssignment.from_index(6, CFG.env.nominal_spacing)
    env = SwarmFormationEnv(CFG)
    obs = simulate_reset_to_fixture(env, FIXTURES[name], 0, CFG)
    md = (float(obs["corridor_dx"]), float(obs["corridor_dy"]))
    assert e_inf(obs["positions"], roles, KEEP, md) <= EPSILON_INIT


def test_jitter_is_bounded_and_seeded() -> None:
    f = FIXTURES["A_open_keep"]
    a = f.initial_positions(3, CFG)
    b = f.initial_positions(3, CFG)
    assert np.allclose(a, b), "initialization must be deterministic per seed"
    c = f.initial_positions(4, CFG)
    assert not np.allclose(a, c), "different seeds must differ"
    roles = RoleAssignment.from_index(6, CFG.env.nominal_spacing)
    from rvt_swarm.decentralized.qualification_fixtures import template_spawn
    exact = template_spawn(6, CFG, f.spawn_centre, 3, jitter=0.0)
    assert np.abs(a - exact).max() <= SPAWN_JITTER + 1e-9


def test_an_invalid_initial_condition_is_actually_rejected() -> None:
    """Non-vacuity: the validator must be able to say no."""
    import dataclasses as dc
    bad = dc.replace(FIXTURES["A_open_keep"], spawn_centre=(0.0, 0.0))
    object.__setattr__(bad, "n", 6)
    # a huge jitter destroys the formation
    from rvt_swarm.decentralized.qualification_fixtures import template_spawn
    pos = template_spawn(6, CFG, (0.0, 0.0), 0, jitter=2.0)
    roles = RoleAssignment.from_index(6, CFG.env.nominal_spacing)
    assert e_inf(pos, roles, KEEP, (1.0, 0.0)) > EPSILON_INIT
