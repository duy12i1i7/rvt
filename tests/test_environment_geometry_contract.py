"""Task 5-3 — geometry must match the environment's actual collision model."""
from __future__ import annotations

import numpy as np
import pytest

from rvt_swarm.config import Config
from rvt_swarm.decentralized.env_geometry import (
    build_passage, corridor_walls, effective_free_width, lateral_extent,
    required_half_separation, required_width, robot_obstacle_threshold,
    single_robot_half_separation, validate_passage)
from rvt_swarm.decentralized.roles import RoleAssignment, rotation
from rvt_swarm.decentralized.system_model import KEEP, LINE

CFG = Config()
CFG.env.world_size = 18.0
HALF = CFG.env.world_size / 2.0
N = 6


def test_threshold_mirrors_the_environment_source() -> None:
    import inspect
    from rvt_swarm import environment
    src = inspect.getsource(environment)
    assert "ro_d < self.ec.min_ro_distance" in src
    assert robot_obstacle_threshold(CFG) == CFG.env.min_ro_distance


# 1 -- declared width == width the collision checker leaves
@pytest.mark.parametrize("h", [0.45, 0.7, 1.0, 1.45, 2.0])
def test_01_declared_free_width_matches_the_collision_checker(h) -> None:
    geo = build_passage(N, CFG, h, half_world=HALF)
    measured = effective_free_width(geo.obstacles,
                                    0.5 * (geo.corridor_x0 + geo.corridor_x1),
                                    CFG, HALF)
    # the checker leaves 2h minus one threshold on each side of the inner rows
    expected = 2.0 * (h - robot_obstacle_threshold(CFG))
    assert measured == pytest.approx(max(expected, 0.0), abs=0.05), (measured, expected)


# 2 -- an infeasible corridor really is impassable for an exact LINE template
def test_02_line_infeasible_corridor_blocks_the_exact_line_template() -> None:
    h = single_robot_half_separation(CFG) - 0.10
    geo = build_passage(N, CFG, h, half_world=HALF)
    roles = RoleAssignment.from_index(N, CFG.env.nominal_spacing)
    T = np.asarray(roles.coords(LINE), dtype=np.float64)
    R = rotation((1.0, 0.0)).astype(np.float64)
    thr = robot_obstacle_threshold(CFG)
    mid = 0.5 * (geo.corridor_x0 + geo.corridor_x1)
    # place the exact LINE template on the corridor axis, centred in the passage
    pos = (R @ (T - T.mean(0)).T).T + np.array([mid, 0.0])
    d = np.linalg.norm(geo.obstacles[None, :, :] - pos[:, None, :], axis=2)
    assert d.min() < thr, "an infeasible corridor must violate the threshold"


def test_02b_a_line_feasible_corridor_admits_the_exact_line_template() -> None:
    """Non-vacuity for test 2."""
    h = required_half_separation(N, LINE, CFG) + 0.30
    geo = build_passage(N, CFG, h, half_world=HALF)
    roles = RoleAssignment.from_index(N, CFG.env.nominal_spacing)
    T = np.asarray(roles.coords(LINE), dtype=np.float64)
    R = rotation((1.0, 0.0)).astype(np.float64)
    mid = 0.5 * (geo.corridor_x0 + geo.corridor_x1)
    pos = (R @ (T - T.mean(0)).T).T + np.array([mid, 0.0])
    d = np.linalg.norm(geo.obstacles[None, :, :] - pos[:, None, :], axis=2)
    assert d.min() >= robot_obstacle_threshold(CFG)


# 3 -- walls cannot be bypassed around their ends
def test_03_walls_cannot_be_bypassed() -> None:
    geo = build_passage(N, CFG, 1.0, half_world=HALF)
    thr = robot_obstacle_threshold(CFG)
    xs = np.arange(geo.corridor_x0, geo.corridor_x1 + 1e-9, 0.1)
    for x in xs:
        w = effective_free_width(geo.obstacles, x, CFG, HALF)
        assert w < 2.0 * HALF - 1.0, f"open lateral escape at x={x}: {w}"
    # and the widest free run at every corridor x is the passage itself
    ys = np.linspace(-HALF, HALF, 2001)
    mid = 0.5 * (geo.corridor_x0 + geo.corridor_x1)
    near = geo.obstacles[np.abs(geo.obstacles[:, 0] - mid) <= thr + 1e-9]
    free = np.ones_like(ys, dtype=bool)
    for oy in near[:, 1]:
        free &= np.abs(ys - oy) >= thr
    # the only free band must straddle y = 0
    idx = np.flatnonzero(free)
    assert len(idx), "corridor is fully blocked"
    assert ys[idx].min() < 0 < ys[idx].max()


# 4 -- goal in bounds
def test_04_goal_is_inside_world_bounds() -> None:
    geo = build_passage(N, CFG, 1.0, half_world=HALF)
    v = validate_passage(geo, CFG)
    assert v["goal_in_bounds"]


# 5 -- downstream recovery region is big enough
def test_05_recovery_region_has_width_and_length() -> None:
    geo = build_passage(N, CFG, 1.0, half_world=HALF)
    v = validate_passage(geo, CFG)
    assert v["recovery_width_ok"]
    # ~74 steps at ~0.135 m/step is the measured requirement
    assert geo.recovery_length >= 74 * 0.135 * 0.8, geo.recovery_length


# 6 -- entry/exit planes bracket the passage
def test_06_entry_and_exit_planes_intersect_the_passage() -> None:
    geo = build_passage(N, CFG, 1.0, half_world=HALF)
    v = validate_passage(geo, CFG)
    assert v["entry_before_exit"] and v["planes_intersect_passage"]


# --- feasibility classification -------------------------------------------
def test_feasibility_classes_are_ordered_and_exhaustive() -> None:
    h_line = required_half_separation(N, LINE, CFG)
    h_keep = required_half_separation(N, KEEP, CFG)
    assert single_robot_half_separation(CFG) <= h_line < h_keep
    for h, want in ((0.40, "infeasible"), (1.00, "line_only"), (2.00, "keep_feasible")):
        assert build_passage(N, CFG, h, half_world=HALF).feasibility_class(CFG) == want


def test_required_values_at_n6() -> None:
    assert required_half_separation(N, LINE, CFG) == pytest.approx(0.550)
    assert required_half_separation(N, KEEP, CFG) == pytest.approx(1.450)
    assert required_width(N, KEEP, CFG) == pytest.approx(2.900)


def test_no_scenario_module_duplicates_the_geometry_maths() -> None:
    """The contract: geometry is computed in ONE place."""
    import inspect
    from rvt_swarm.decentralized import qualification_fixtures as qf
    src = inspect.getsource(qf)
    # the old surface-clearance formula must not reappear anywhere
    assert "robot_radius + cfg.env.min_ro_distance)" not in src.replace(
        "pad = cfg.env.robot_radius + cfg.env.min_ro_distance", "")
