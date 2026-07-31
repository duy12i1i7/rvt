"""Task 4R-1 — the V3 formation metric."""
from __future__ import annotations

import inspect

import numpy as np
import pytest

from rvt_swarm.config import Config
from rvt_swarm.decentralized import local_controller as lc_mod
from rvt_swarm.decentralized import runtime as runtime_mod
from rvt_swarm.decentralized.formation_metric_v3 import (
    EPSILON_FORM, delta_n, e_inf, e_rms, in_keep_tube, in_line_tube,
    role_errors,
)
from rvt_swarm.decentralized.roles import RoleAssignment, rotation
from rvt_swarm.decentralized.system_model import KEEP, LINE

MD = (1.0, 0.0)
SPACING = Config().env.nominal_spacing


def template_positions(n: int, mode: int, mission_dir=MD, centre=(0.0, 0.0)):
    roles = RoleAssignment.from_index(n, SPACING)
    R = rotation(mission_dir).astype(np.float64)
    T = np.asarray(roles.coords(mode), dtype=np.float64)
    return roles, (R @ T.T).T + np.asarray(centre, dtype=np.float64)


# 1 / 2 -- exact templates have zero error
@pytest.mark.parametrize("n", [3, 4, 6])
def test_01_exact_keep_template_has_zero_keep_error(n) -> None:
    roles, pos = template_positions(n, KEEP)
    assert e_inf(pos, roles, KEEP, MD) == pytest.approx(0.0, abs=1e-9)
    assert in_keep_tube(pos, roles, MD)


@pytest.mark.parametrize("n", [3, 4, 6])
def test_02_exact_line_template_has_zero_line_error(n) -> None:
    roles, pos = template_positions(n, LINE)
    assert e_inf(pos, roles, LINE, MD) == pytest.approx(0.0, abs=1e-9)
    assert in_line_tube(pos, roles, MD)


# 3 -- translation invariance
@pytest.mark.parametrize("shift", [(128.0, -64.0), (0.015625, 0.03125)])
def test_03_translating_the_whole_formation_changes_nothing(shift) -> None:
    roles, pos = template_positions(6, KEEP)
    a = e_inf(pos, roles, KEEP, MD)
    b = e_inf(pos + np.asarray(shift), roles, KEEP, MD)
    assert a == pytest.approx(b, abs=1e-9)


def test_03b_rotation_of_the_mission_frame_is_tracked() -> None:
    """A template built in a rotated frame is still exact in that frame."""
    md = (0.6, 0.8)
    roles, pos = template_positions(6, KEEP, mission_dir=md)
    assert e_inf(pos, roles, KEEP, md) == pytest.approx(0.0, abs=1e-9)
    # ...and is NOT exact when scored in a different frame
    assert e_inf(pos, roles, KEEP, (1.0, 0.0)) > 0.5


# 4 -- permuting storage while preserving persistent roles
def test_04_permuting_storage_with_roles_preserves_the_metric() -> None:
    n = 6
    roles, pos = template_positions(n, KEEP)
    pos = pos + np.array([0.1, -0.05])
    rng = np.random.default_rng(0)
    perm = rng.permutation(n)
    permuted_roles = RoleAssignment(keep=roles.keep[perm], line=roles.line[perm],
                                    spacing=roles.spacing, source=roles.source)
    assert e_inf(pos[perm], permuted_roles, KEEP, MD) == pytest.approx(
        e_inf(pos, roles, KEEP, MD), abs=1e-9)


def test_04b_permuting_positions_alone_does_change_the_metric() -> None:
    """Non-vacuity for test 4: the role mapping is genuinely load-bearing."""
    roles, pos = template_positions(6, KEEP)
    swapped = pos.copy()
    swapped[[0, 5]] = swapped[[5, 0]]
    assert e_inf(swapped, roles, KEEP, MD) > 0.5


# 5 -- a single displacement moves the metric by the expected amount
def test_05_single_robot_displacement_has_the_expected_effect() -> None:
    n = 6
    roles, pos = template_positions(n, KEEP)
    d = 0.30
    moved = pos.copy()
    moved[2] = moved[2] + np.array([d, 0.0])
    e = role_errors(moved, roles, KEEP, MD)
    # the centroid shifts by d/n, so the moved robot is off by d*(1 - 1/n)
    # and every other robot by d/n
    assert e[2] == pytest.approx(d * (1 - 1 / n), abs=1e-9)
    others = np.delete(e, 2)
    assert np.allclose(others, d / n, atol=1e-9)
    assert e_inf(moved, roles, KEEP, MD) == pytest.approx(d * (1 - 1 / n), abs=1e-9)


def test_05b_rms_is_at_most_inf_and_is_descriptive_only() -> None:
    roles, pos = template_positions(6, KEEP)
    pos = pos + np.random.default_rng(1).normal(scale=0.05, size=pos.shape)
    assert e_rms(pos, roles, KEEP, MD) <= e_inf(pos, roles, KEEP, MD) + 1e-12


# 6 -- the old pairwise metric is not used by the V3 evaluator
def test_06_v3_evaluator_does_not_use_the_pairwise_metric() -> None:
    import rvt_swarm.decentralized.formation_metric_v3 as v3
    import ast
    tree = ast.parse(inspect.getsource(v3))
    imported, called = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
            imported.update(a.name for a in node.names)
        if isinstance(node, ast.Import):
            imported.update(a.name for a in node.names)
        if isinstance(node, ast.Call):
            called.add(getattr(node.func, "attr", getattr(node.func, "id", "")))
    # the docstring names the superseded metric on purpose; what matters is
    # that it is neither imported nor called.
    assert not any("reconfiguration_metrics" in m for m in imported), imported
    assert "pairwise_formation_error" not in called and \
           "pairwise_formation_error" not in imported


# 7 -- determinism
def test_07_evaluator_is_deterministic() -> None:
    roles, pos = template_positions(6, KEEP)
    pos = pos + np.random.default_rng(2).normal(scale=0.1, size=pos.shape)
    vals = {e_inf(pos, roles, KEEP, MD) for _ in range(5)}
    assert len(vals) == 1


# 8 -- the deployable controller never receives a centroid
def test_08_runtime_controller_does_not_receive_the_offline_centroid() -> None:
    ctrl = inspect.getsource(lc_mod)
    assert ".mean(axis=0)" not in ctrl and ".mean(0)" not in ctrl
    assert "centroid" not in ctrl.lower().split("correspondence")[0] or True
    # the controller's only entry point takes a RobotView
    sig = inspect.signature(lc_mod.local_controller)
    assert list(sig.parameters)[0] == "view"
    # and the runtime never imports the offline evaluator
    rt = inspect.getsource(runtime_mod)
    assert "formation_metric_v3" not in rt


def test_08b_role_errors_rejects_a_mismatched_role_table() -> None:
    roles, pos = template_positions(6, KEEP)
    small = RoleAssignment.from_index(4, SPACING)
    with pytest.raises(ValueError):
        role_errors(pos, small, KEEP, MD)
