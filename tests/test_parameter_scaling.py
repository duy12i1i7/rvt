"""Task G9 — mechanical invariance under configuration changes.

Unit/integration tests only. No closed-loop success is required or claimed.
"""

from __future__ import annotations

import numpy as np
import pytest

from rvt_swarm.config import Config
from rvt_swarm.decentralized import epoch as E
from rvt_swarm.decentralized.parameters import (
    MissionParams, PlatformParams, ProtocolParams, check_team_size,
    default_parameters, derived_commitment_steps, derived_evidence_persistence_steps,
    derived_forward_sector_half_width, derived_k_trigger, derived_lookahead_distance,
    derived_recovery_dwell_steps, forward_sector_observable, normalized_ratios,
    steps_from_seconds)
from rvt_swarm.decentralized.roles import RoleAssignment, rotation
from rvt_swarm.decentralized.system_model import KEEP, LINE

BASE_P, BASE_M, BASE_C = default_parameters()


def platform(**kw) -> PlatformParams:
    import dataclasses
    return dataclasses.replace(BASE_P, **kw)


def mission(**kw) -> MissionParams:
    import dataclasses
    return dataclasses.replace(BASE_M, **kw)


# ===========================================================================
# Control frequency: time-domain behaviour must be equivalent
# ===========================================================================
@pytest.mark.parametrize("dt", [0.15, 0.075, 0.05])
def test_time_domain_behaviour_is_invariant_to_control_frequency(dt) -> None:
    p = platform(control_period=dt, communication_period=dt)
    dwell_s = derived_recovery_dwell_steps(BASE_M, p) * dt
    persist_s = derived_evidence_persistence_steps(BASE_C, p) * dt
    commit_s = derived_commitment_steps(BASE_C, p) * dt
    assert dwell_s == pytest.approx(BASE_M.recovery_dwell_seconds, abs=dt)
    assert persist_s == pytest.approx(BASE_C.evidence_persistence_seconds, abs=dt)
    assert commit_s == pytest.approx(BASE_C.commitment_seconds, abs=dt)


def test_halving_the_control_period_doubles_the_step_counts() -> None:
    slow, fast = platform(control_period=0.15), platform(control_period=0.075)
    assert derived_recovery_dwell_steps(BASE_M, fast) == \
        2 * derived_recovery_dwell_steps(BASE_M, slow)


def test_steps_from_seconds_rounds_up() -> None:
    assert steps_from_seconds(0.45, 0.15) == 3
    assert steps_from_seconds(0.46, 0.15) == 4
    assert steps_from_seconds(0.0, 0.15) == 0
    with pytest.raises(ValueError):
        steps_from_seconds(1.0, 0.0)


# ===========================================================================
# Formation spacing and robot geometry
# ===========================================================================
@pytest.mark.parametrize("spacing", [0.9, 1.35])
@pytest.mark.parametrize("clearance", [0.55, 0.80])
def test_forward_sector_scales_with_spacing_and_clearance(spacing, clearance) -> None:
    m, p = mission(nominal_spacing=spacing), platform(collision_clearance_obstacle=clearance)
    roles = RoleAssignment.from_index(6, spacing)
    K = np.asarray(roles.coords(KEEP)); K = K - K.mean(0)
    L = np.asarray(roles.coords(LINE)); L = L - L.mean(0)
    widths = [derived_forward_sector_half_width(tuple(K[i]), tuple(L[i]), p, m)
              for i in range(6)]
    # the outer role's band is its own lateral displacement plus the clearance
    assert max(widths) == pytest.approx(
        max(abs(float(K[i][1]) - float(L[i][1])) for i in range(6)) + clearance)
    # larger spacing => wider band; larger clearance => wider band
    assert max(widths) > clearance


def test_forward_sector_is_role_dependent_not_a_single_constant() -> None:
    """The whole point of the G2 repair."""
    p, m, _ = default_parameters()
    roles = RoleAssignment.from_index(6, m.nominal_spacing)
    K = np.asarray(roles.coords(KEEP)); K = K - K.mean(0)
    L = np.asarray(roles.coords(LINE)); L = L - L.mean(0)
    widths = {round(derived_forward_sector_half_width(tuple(K[i]), tuple(L[i]), p, m), 3)
              for i in range(6)}
    assert len(widths) > 1, "a single value would be the old magic number again"


def test_forward_sector_beyond_sensor_range_is_reported_not_silently_clipped() -> None:
    p = platform(obstacle_sensor_range=0.6)
    w = derived_forward_sector_half_width((0.45, 0.9), (-2.25, 0.0), p, BASE_M)
    assert w > p.obstacle_sensor_range
    assert forward_sector_observable(w, p) is False


# ===========================================================================
# Team size
# ===========================================================================
@pytest.mark.parametrize("n", [5, 6, 8])
def test_templates_and_support_check_accept_variable_team_size(n) -> None:
    c = ProtocolParams(max_team_size=max(n, BASE_C.max_team_size))
    r = check_team_size(n, BASE_P, BASE_M, c)
    assert r.team_size == n
    assert r.supported, r.reasons
    roles = RoleAssignment.from_index(n, BASE_M.nominal_spacing)
    assert roles.n == n


@pytest.mark.parametrize("n", [3, 4])
def test_unsupported_team_sizes_fail_explicitly(n) -> None:
    r = check_team_size(n, BASE_P, BASE_M, BASE_C)
    assert r.supported is False
    assert any("disjoint" in reason for reason in r.reasons), r.reasons


def test_no_fixed_size_tensor_in_deployable_paths() -> None:
    import inspect
    from rvt_swarm.decentralized import guards, models
    src = inspect.getsource(models)
    for bad in ("zeros(6", "zeros((6", "arange(6", "reshape(6"):
        assert bad not in src, bad
    assert guards.audit() == []


# ===========================================================================
# Communication topology contract
# ===========================================================================
@pytest.mark.parametrize("n_max", [4, 6, 8])
def test_k_trigger_tracks_the_declared_diameter_bound(n_max) -> None:
    c = ProtocolParams(max_team_size=n_max)
    assert derived_k_trigger(c) == n_max - 1


def test_explicit_diameter_bound_overrides_the_team_size_worst_case() -> None:
    c = ProtocolParams(max_team_size=8, max_component_diameter=3)
    assert derived_k_trigger(c) == 3


@pytest.mark.parametrize("topology", ["path", "ring", "star", "complete"])
def test_trigger_propagation_covers_every_declared_topology(topology) -> None:
    n = 6
    if topology == "path":
        adj = {i: [j for j in (i - 1, i + 1) if 0 <= j < n] for i in range(n)}
    elif topology == "ring":
        adj = {i: [(i - 1) % n, (i + 1) % n] for i in range(n)}
    elif topology == "star":
        adj = {0: list(range(1, n)), **{i: [0] for i in range(1, n)}}
    else:
        adj = {i: [j for j in range(n) if j != i] for i in range(n)}
    eps = {i: E.EpochState(robot_id=i) for i in range(n)}
    eps[n - 1].arm_trigger(0)
    E.simulate_trigger_consensus(eps, adj, derived_k_trigger(BASE_C))
    assert all(eps[i].trigger_token is not None for i in range(n)), topology
    assert len({eps[i].epoch_id for i in range(n)}) == 1


def test_lookahead_scales_with_speed_and_is_capped_by_sensor_range() -> None:
    p, m, c = default_parameters()
    slow = derived_lookahead_distance(p, m, c, speed=0.2)
    fast = derived_lookahead_distance(p, m, c, speed=p.max_speed)
    assert slow < fast
    tiny = platform(obstacle_sensor_range=0.3)
    assert derived_lookahead_distance(tiny, m, c) == pytest.approx(0.3)


def test_normalized_ratios_are_dimensionless_and_scale_correctly() -> None:
    r1 = normalized_ratios(BASE_P, BASE_M)
    r2 = normalized_ratios(BASE_P, mission(nominal_spacing=1.8))
    assert r1["sensor_range_ratio"] == pytest.approx(2 * r2["sensor_range_ratio"])
    assert r1["formation_tolerance_ratio"] == pytest.approx(
        BASE_M.formation_tolerance / BASE_M.nominal_spacing)
