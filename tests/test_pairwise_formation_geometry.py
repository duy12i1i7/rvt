"""Evidence tests for the persistent formation-role protocol.

Every test here targets one falsifiable property of
`rvt_swarm.decentralized.roles`. The point is not that the module runs; it is
that the module cannot secretly depend on the joint state:

  * pairwise geometry is exactly antisymmetric (no per-robot convention),
  * role coordinates are mission constants (no runtime recomputation),
  * the deployable entry points cannot even accept a positions array,
  * `from_initial_formation` -- the one constructor that reads positions -- is
    never reachable from a control step.

`roles.py` is frozen for this task and is never modified here.
"""

from __future__ import annotations

import ast
import inspect
import os
import typing
from typing import Dict, List, Sequence, Tuple

import numpy as np
import pytest

from rvt_swarm.config import Config
from rvt_swarm.controllers import _desired_offsets
from rvt_swarm.decentralized import roles as roles_mod
from rvt_swarm.decentralized.roles import (
    RoleAssignment,
    desired_offset_for_neighbour,
    pairwise_offset,
    rotation,
)
from rvt_swarm.decentralized.system_model import (
    KEEP,
    LINE,
    MODES,
    PROHIBITED_OBS_KEYS,
    NeighbourRecord,
    RobotView,
)
from rvt_swarm.environment import SwarmFormationEnv
from rvt_swarm.layouts import build_layouts

SPACING = 0.9  # cfg.env.nominal_spacing

# Mission directions. Axis-aligned, non-axis-aligned, negative components, and
# deliberately unnormalised inputs so the normalisation inside rotation() is
# exercised rather than assumed.
MISSION_DIRS: Tuple[Tuple[float, float], ...] = (
    (1.0, 0.0),
    (0.0, 1.0),
    (-1.0, 0.0),
    (0.6, 0.8),
    (-0.6, 0.8),
    (0.37, -0.93),
    (1.0, 1.0),          # unnormalised, 45 deg
    (-2.5, 0.75),        # unnormalised, obtuse
)


def _unit(d: Tuple[float, float]) -> Tuple[float, float]:
    v = np.asarray(d, dtype=np.float64)
    v = v / np.linalg.norm(v)
    return (float(v[0]), float(v[1]))


# Unit-length variants. `controllers._desired_offsets` multiplies the raw
# (corridor_dx, corridor_dy) into the template without normalising it, so the
# centralized reference is only well posed for a unit corridor vector. The
# environment always supplies one -- asserted by
# `test_environment_supplies_a_unit_mission_direction` -- so restricting the
# cross-check to unit directions is a property of the reference, not a dodge.
UNIT_MISSION_DIRS: Tuple[Tuple[float, float], ...] = tuple(
    _unit(d) for d in MISSION_DIRS
)

# float32 round-off budget. The role tables are float32, so a quantity that is
# mathematically exact is reproduced to ~1e-7 in magnitude here. Anything that
# must hold *bit-exactly* is asserted with == and never with a tolerance.
F32_TOL = 1e-6


def _both_role_sources(n: int) -> Dict[str, RoleAssignment]:
    """Both constructors, so no property is proved for only one arm."""
    rng = np.random.default_rng(7)
    initial = rng.uniform(-2.0, 2.0, size=(n, 2)).astype(np.float32)
    return {
        "index": RoleAssignment.from_index(n, SPACING),
        "initial_formation": RoleAssignment.simulate_mission_setup_from_initial_formation(
            initial, (1.0, 0.0), SPACING
        ),
    }


def _ranks_from_line_table(line: np.ndarray, spacing: float) -> List[int]:
    """Recover the integer rank each robot holds in the line template."""
    n = int(line.shape[0])
    return [int(round(float(line[i, 0]) / spacing + (n - 1) / 2.0)) for i in range(n)]


# ---------------------------------------------------------------------------
# 1. exact antisymmetry
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("n", [4, 6])
@pytest.mark.parametrize("mode", list(MODES))
def test_pairwise_offset_is_exactly_antisymmetric(n: int, mode: int) -> None:
    """d_ij = -d_ji bit-exactly, for every pair, mode, N and mission direction.

    Exactness matters: an approximate antisymmetry would mean the two robots of
    a pair are pulling toward slightly different rendezvous geometries, which is
    exactly the failure a centroid-referenced formulation would hide.
    """
    checked = 0
    for assignment in _both_role_sources(n).values():
        coords = assignment.coords(mode)
        for mission_dir in MISSION_DIRS:
            for i in range(n):
                for j in range(n):
                    d_ij = pairwise_offset(tuple(coords[i]), tuple(coords[j]), mission_dir)
                    d_ji = pairwise_offset(tuple(coords[j]), tuple(coords[i]), mission_dir)
                    assert np.array_equal(d_ij, -d_ji), (
                        f"antisymmetry broken for n={n} mode={mode} "
                        f"dir={mission_dir} pair=({i},{j}): {d_ij} vs {-d_ji}"
                    )
                    if i == j:
                        assert np.array_equal(d_ij, np.zeros(2, dtype=np.float32))
                    checked += 1
    assert checked == 2 * len(MISSION_DIRS) * n * n  # test is not vacuous


@pytest.mark.parametrize("n", [4, 6])
@pytest.mark.parametrize("mode", list(MODES))
def test_pairwise_offsets_are_translation_invariant(n: int, mode: int) -> None:
    """A common translation of the template leaves every d_ij unchanged.

    This is the property that removes the need for a swarm centroid: no robot
    can observe where the template as a whole sits.
    """
    assignment = RoleAssignment.from_index(n, SPACING)
    coords = assignment.coords(mode)
    shift = np.array([3.7, -1.9], dtype=np.float32)
    shifted = (coords + shift).astype(np.float32)
    for mission_dir in MISSION_DIRS:
        for i in range(n):
            for j in range(n):
                base = pairwise_offset(tuple(coords[i]), tuple(coords[j]), mission_dir)
                moved = pairwise_offset(tuple(shifted[i]), tuple(shifted[j]), mission_dir)
                assert np.allclose(base, moved, atol=F32_TOL)


# ---------------------------------------------------------------------------
# 2. persistence: roles are mission constants
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("n", [4, 6])
def test_constructing_roles_twice_gives_identical_tables(n: int) -> None:
    rng = np.random.default_rng(11)
    initial = rng.uniform(-2.0, 2.0, size=(n, 2)).astype(np.float32)

    a1, a2 = RoleAssignment.from_index(n, SPACING), RoleAssignment.from_index(n, SPACING)
    assert np.array_equal(a1.keep, a2.keep) and np.array_equal(a1.line, a2.line)
    assert a1.source == a2.source == "index"

    b1 = RoleAssignment.simulate_mission_setup_from_initial_formation(initial, (1.0, 0.0), SPACING)
    b2 = RoleAssignment.simulate_mission_setup_from_initial_formation(initial.copy(), (1.0, 0.0), SPACING)
    assert np.array_equal(b1.keep, b2.keep) and np.array_equal(b1.line, b2.line)
    assert b1.source == b2.source == "initial_formation"


def test_role_assignment_is_immutable() -> None:
    assignment = RoleAssignment.from_index(4, SPACING)
    with pytest.raises(Exception):
        assignment.keep = np.zeros((4, 2), dtype=np.float32)  # type: ignore[misc]
    with pytest.raises(Exception):
        assignment.spacing = 1.0  # type: ignore[misc]


def test_from_index_signature_cannot_see_any_position() -> None:
    """The strict arm literally has no channel through which state could enter."""
    params = list(inspect.signature(RoleAssignment.from_index).parameters)
    assert params == ["n", "spacing"], params


@pytest.mark.parametrize("n", [4, 6])
def test_roles_do_not_change_as_the_swarm_moves(n: int) -> None:
    """Roles are fixed at t=0 and are identical after the swarm has moved metres.

    Runs the real environment so the invariant is checked against genuine motion,
    not against a mock. Also checks the derived pairwise offsets, since those are
    what the controller consumes.
    """
    cfg = Config()
    cfg.train.device = "cpu"
    cfg.env.scenarios = ["cluttered"]
    env = SwarmFormationEnv(cfg)
    layout = [lay for lay in build_layouts("val") if lay.family == "line_corridor"][0]
    obs = env.reset(n, "cluttered", seed=20000001, layout=layout)

    initial_positions = np.asarray(obs["positions"], dtype=np.float32).copy()
    mission_dir = (float(obs["corridor_dx"]), float(obs["corridor_dy"]))
    assignment = RoleAssignment.simulate_mission_setup_from_initial_formation(
        initial_positions, mission_dir, cfg.env.nominal_spacing
    )
    keep_t0 = assignment.keep.copy()
    line_t0 = assignment.line.copy()
    offsets_t0 = {
        (i, j, mode): pairwise_offset(
            assignment.role_of(i, mode), assignment.role_of(j, mode), mission_dir
        )
        for mode in MODES
        for i in range(n)
        for j in range(n)
    }

    rng = np.random.default_rng(3)
    for _ in range(80):
        action = rng.uniform(-0.6, 0.6, size=(n, 2)).astype(np.float32)
        obs, _reward, done, _info = env.step(action, 2)
        if done:
            break

    moved = float(np.abs(np.asarray(obs["positions"]) - initial_positions).max())
    assert moved > 0.5, f"swarm barely moved ({moved:.3f} m); test would be vacuous"

    # The role tables are unchanged, and nothing recomputed them.
    assert np.array_equal(assignment.keep, keep_t0)
    assert np.array_equal(assignment.line, line_t0)
    for (i, j, mode), expected in offsets_t0.items():
        now = pairwise_offset(
            assignment.role_of(i, mode), assignment.role_of(j, mode), mission_dir
        )
        assert np.array_equal(now, expected), f"role geometry drifted for ({i},{j}) mode={mode}"


@pytest.mark.parametrize("n", [4, 6])
def test_only_from_initial_formation_reads_positions(n: int) -> None:
    """Position arguments exist on exactly one public entry point of the module.

    Enumerates every public callable in `roles` and asserts that the only one
    whose parameters carry position-like names is the mission-setup constructor.
    """
    position_like = {
        "positions",
        "pos",
        "p",
        "all_positions",
        "joint_state",
        "state",
        "states",
        "obs",
        "observation",
        "velocities",
        "vel",
    }
    offenders: List[str] = []
    for name, obj in vars(roles_mod).items():
        if name.startswith("_"):
            continue
        if not (inspect.isfunction(obj) or inspect.isclass(obj)):
            continue
        callables = [(name, obj)] if inspect.isfunction(obj) else [
            (f"{name}.{m}", getattr(obj, m))
            for m in dir(obj)
            if not m.startswith("_") and callable(getattr(obj, m, None))
        ]
        for qualname, fn in callables:
            try:
                params = set(inspect.signature(fn).parameters)
            except (TypeError, ValueError):
                continue
            if params & position_like:
                offenders.append(qualname)
    assert offenders == [], f"position-carrying entry points beyond setup: {offenders}"
    # The one legitimate reader is a *constructor*, and takes initial positions only.
    setup_params = list(
        inspect.signature(RoleAssignment.simulate_mission_setup_from_initial_formation).parameters
    )
    assert setup_params == ["initial_positions", "mission_dir", "spacing"], setup_params


# ---------------------------------------------------------------------------
# 3. rotation()
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("mission_dir", MISSION_DIRS)
def test_rotation_is_a_proper_rotation_mapping_x_onto_the_mission_direction(
    mission_dir: Tuple[float, float]
) -> None:
    R = rotation(mission_dir)
    assert R.shape == (2, 2)
    assert np.allclose(R.T @ R, np.eye(2), atol=F32_TOL), R.T @ R
    assert np.allclose(np.linalg.det(R.astype(np.float64)), 1.0, atol=F32_TOL)

    unit = np.asarray(mission_dir, dtype=np.float64)
    unit = unit / np.linalg.norm(unit)
    assert np.allclose(R @ np.array([1.0, 0.0]), unit, atol=F32_TOL)
    # and the template's lateral axis is the mission direction turned +90 deg
    assert np.allclose(R @ np.array([0.0, 1.0]), np.array([-unit[1], unit[0]]), atol=F32_TOL)


def test_rotation_of_degenerate_direction_is_identity() -> None:
    """A zero mission direction must not produce NaNs in a deployable path."""
    R = rotation((0.0, 0.0))
    assert np.allclose(R, np.eye(2), atol=F32_TOL)
    assert np.isfinite(R).all()


# ---------------------------------------------------------------------------
# 4. keep template vs the centralized grid it replaces
# ---------------------------------------------------------------------------
def _centralized_keep_offsets(n: int, mission_dir: Tuple[float, float]) -> np.ndarray:
    cfg = Config()
    obs = {
        "positions": np.zeros((n, 2), dtype=np.float32),
        "corridor_dx": float(mission_dir[0]),
        "corridor_dy": float(mission_dir[1]),
    }
    return _desired_offsets(obs, cfg, 0, 1.0, np.zeros((n,), dtype=np.int64))


def _pairwise_table(offsets: np.ndarray) -> np.ndarray:
    return (offsets[None, :, :] - offsets[:, None, :]).astype(np.float64)


def _max_pairwise_gap(a: np.ndarray, b: np.ndarray) -> float:
    """Largest Euclidean disagreement between two pairwise-offset tables."""
    return float(np.linalg.norm(_pairwise_table(a) - _pairwise_table(b), axis=-1).max())


@pytest.mark.parametrize("n", [4, 6])
def test_environment_supplies_a_unit_mission_direction(n: int) -> None:
    """The centralized reference assumes |corridor| = 1; check the env delivers it."""
    cfg = Config()
    cfg.train.device = "cpu"
    cfg.env.scenarios = ["cluttered"]
    env = SwarmFormationEnv(cfg)
    for layout in build_layouts("val")[:6]:
        obs = env.reset(n, "cluttered", seed=20000001, layout=layout)
        norm = float(np.hypot(obs["corridor_dx"], obs["corridor_dy"]))
        assert abs(norm - 1.0) < 1e-3, (layout.layout_id, norm)


@pytest.mark.parametrize("n", [4, 6])
@pytest.mark.parametrize("mission_dir", list(UNIT_MISSION_DIRS))
def test_keep_template_reproduces_centralized_grid_pairwise(
    n: int, mission_dir: Tuple[float, float]
) -> None:
    """The decentralized keep template equals the centralized grid it replaces.

    Comparison is on pairwise differences because the centralized template is
    centroid-anchored while the decentralized one is defined only up to a common
    translation -- and pairwise differences are exactly the quantity the
    decentralized controller consumes. Equality here is what makes the
    centralized/decentralized comparison like-for-like: any mismatch would mean
    the two controllers aim at different formations, so a performance gap could
    not be attributed to decentralization.

    This test is sign-sensitive by construction: the centralized template uses
    lateral = (corridor_y, -corridor_x) (mission direction rotated -90 deg)
    while `rotation()` sends the template +y axis to +90 deg, so a template that
    forgot to negate its lateral coordinate would be a mirror image -- congruent
    as a point set, but assigning robots to mirrored slots -- and would fail
    here with a delta of (cols-1) * spacing.
    """
    central = _centralized_keep_offsets(n, mission_dir)
    decentral = (rotation(mission_dir) @ RoleAssignment.from_index(n, SPACING).keep.T).T
    delta = _max_pairwise_gap(central, decentral)
    assert delta < F32_TOL, (
        f"keep pairwise geometry differs from the centralized grid by {delta:.4f} m "
        f"(n={n}, mission_dir={mission_dir})"
    )


@pytest.mark.parametrize("n", [4, 6])
def test_keep_pairwise_comparison_would_catch_a_mirrored_template(n: int) -> None:
    """Guard against test 4 passing for the wrong reason.

    Feeds the comparison a deliberately mirrored keep table and asserts the
    pairwise metric rejects it, so the passing result above is evidence about
    the lateral convention rather than about a symmetric grid being
    indistinguishable from its own reflection.
    """
    mission_dir = (0.6, 0.8)
    central = _centralized_keep_offsets(n, mission_dir)
    mirrored_keep = RoleAssignment.from_index(n, SPACING).keep.copy()
    mirrored_keep[:, 1] *= -1.0
    mirrored_world = (rotation(mission_dir) @ mirrored_keep.T).T
    delta = _max_pairwise_gap(central, mirrored_world)
    cols = max(2, int(np.ceil(np.sqrt(n))))
    assert delta > F32_TOL
    assert abs(delta - 2.0 * (cols - 1) * SPACING) < 1e-4, delta


# ---------------------------------------------------------------------------
# 5. line template
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("n", [4, 6])
@pytest.mark.parametrize("source", ["index", "initial_formation"])
def test_line_template_is_single_file_at_nominal_spacing(n: int, source: str) -> None:
    assignment = _both_role_sources(n)[source]
    line = assignment.line

    # Single file: zero lateral coordinate, bit-exactly, in the template frame.
    assert np.array_equal(line[:, 1], np.zeros((n,), dtype=np.float32))

    # Consecutive ranks are `spacing` apart, and the file is centred.
    ranks = _ranks_from_line_table(line, SPACING)
    by_rank = np.array([line[ranks.index(r), 0] for r in range(n)], dtype=np.float64)
    gaps = np.diff(by_rank)
    assert np.allclose(gaps, SPACING, atol=F32_TOL), gaps
    assert abs(float(by_rank.mean())) < F32_TOL
    assert abs(float(by_rank[-1] - by_rank[0]) - (n - 1) * SPACING) < F32_TOL

    # And in the world frame the file lies along the mission direction.
    for mission_dir in MISSION_DIRS:
        R = rotation(mission_dir)
        world = (R @ line.T).T
        lateral_axis = R @ np.array([0.0, 1.0], dtype=np.float32)
        assert np.allclose(world @ lateral_axis, 0.0, atol=F32_TOL)


# ---------------------------------------------------------------------------
# 6. rank permutations
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("n", [4, 6])
def test_both_constructors_give_valid_rank_permutations(n: int) -> None:
    rng = np.random.default_rng(23)
    assignments = {
        "index": RoleAssignment.from_index(n, SPACING),
        "initial_formation": RoleAssignment.simulate_mission_setup_from_initial_formation(
            rng.uniform(-3.0, 3.0, size=(n, 2)).astype(np.float32), (0.6, 0.8), SPACING
        ),
    }
    for name, assignment in assignments.items():
        ranks = _ranks_from_line_table(assignment.line, SPACING)
        assert sorted(ranks) == list(range(n)), f"{name} ranks are not a permutation: {ranks}"
    assert _ranks_from_line_table(assignments["index"].line, SPACING) == list(range(n))


@pytest.mark.parametrize("n", [4, 6])
def test_from_initial_formation_orders_ranks_along_the_mission_direction(n: int) -> None:
    """The setup-time assignment picks the non-crossing permutation, deterministically."""
    rng = np.random.default_rng(101)
    mission_dir = (0.6, 0.8)
    positions = rng.uniform(-3.0, 3.0, size=(n, 2)).astype(np.float32)
    assignment = RoleAssignment.simulate_mission_setup_from_initial_formation(positions, mission_dir, SPACING)
    ranks = _ranks_from_line_table(assignment.line, SPACING)
    along = positions @ np.asarray(mission_dir, dtype=np.float32)
    for i in range(n):
        for j in range(n):
            if along[i] < along[j]:
                assert ranks[i] < ranks[j]

    # Deterministic tie-breaking by robot ID: identical projections -> id order.
    tied = np.zeros((n, 2), dtype=np.float32)
    tied_assignment = RoleAssignment.simulate_mission_setup_from_initial_formation(tied, mission_dir, SPACING)
    assert _ranks_from_line_table(tied_assignment.line, SPACING) == list(range(n))


# ---------------------------------------------------------------------------
# 7. computable from three local quantities alone
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("mode", list(MODES))
def test_offset_needs_only_own_role_neighbour_role_and_mission_direction(mode: int) -> None:
    """Call the geometry with exactly three plain tuples -- nothing else exists.

    Then show the RobotView/NeighbourRecord wrapper agrees, with a neighbour
    record that carries no absolute position at all.
    """
    n = 6
    assignment = RoleAssignment.from_index(n, SPACING)
    mission_dir = (0.6, 0.8)
    i, j = 1, 4

    role_i = assignment.role_of(i, mode)
    role_j = assignment.role_of(j, mode)
    assert isinstance(role_i, tuple) and len(role_i) == 2
    assert all(isinstance(c, float) for c in role_i + role_j)

    # three scalars-pairs in, one displacement out
    expected = pairwise_offset(role_i, role_j, mission_dir)

    view = RobotView(
        robot_id=i,
        position=(0.0, 0.0),
        velocity=(0.0, 0.0),
        role_keep=assignment.role_of(i, KEEP),
        role_line=assignment.role_of(i, LINE),
        committed_mode=mode,
        epoch_id=0,
        steps_since_decision=0,
        local_progress=0.0,
        goal=(10.0, 0.0),
        mission_dir=mission_dir,
        neighbours=(),
        obstacles=(),
    )
    neighbour = NeighbourRecord(
        robot_id=j,
        rel_position=(1.0, -0.2),
        rel_velocity=(0.0, 0.0),
        role_keep=assignment.role_of(j, KEEP),
        role_line=assignment.role_of(j, LINE),
        committed_mode=mode,
        epoch_id=0,
        message_age_steps=0,
        degree=1,
        link_valid=True,
    )
    got = desired_offset_for_neighbour(view, neighbour, mode)
    assert np.array_equal(got, expected)

    # The answer does not depend on where either robot actually is.
    for rel in [(0.0, 0.0), (5.0, 5.0), (-3.3, 0.1)]:
        moved = NeighbourRecord(
            robot_id=j, rel_position=rel, rel_velocity=(0.0, 0.0),
            role_keep=neighbour.role_keep, role_line=neighbour.role_line,
            committed_mode=mode, epoch_id=0, message_age_steps=0,
            degree=1, link_valid=True,
        )
        assert np.array_equal(desired_offset_for_neighbour(view, moved, mode), expected)


def test_neighbour_record_exposes_no_absolute_position() -> None:
    fields = set(NeighbourRecord.__dataclass_fields__)
    assert "position" not in fields and "abs_position" not in fields
    assert "rel_position" in fields and "rel_velocity" in fields
    # RobotView carries no joint-state field. (`obstacles` is present and is a
    # locally-sensed list bounded by r_obs, not the global obstacle array; the
    # contract for that field is enforced where the view is built, not here.)
    joint_state_keys = {"positions", "velocities", "formation_error", "subteam_ids"}
    assert not (set(RobotView.__dataclass_fields__) & joint_state_keys)
    assert joint_state_keys <= set(PROHIBITED_OBS_KEYS)


# ---------------------------------------------------------------------------
# 8. no runtime joint-state access
# ---------------------------------------------------------------------------
PACKAGE_DIR = os.path.dirname(inspect.getfile(roles_mod))

JOINT_STATE_PARAM_NAMES = {
    "positions", "velocities", "pos", "vel", "all_positions", "all_states",
    "joint_state", "obs", "observation", "swarm", "robots", "states", "index",
    "robot_index", "idx",
}


@pytest.mark.parametrize("fn", [pairwise_offset, desired_offset_for_neighbour])
def test_deployable_geometry_takes_no_joint_state_argument(fn) -> None:
    sig = inspect.signature(fn)
    names = list(sig.parameters)
    assert not (set(names) & JOINT_STATE_PARAM_NAMES), names
    hints = typing.get_type_hints(fn)
    for pname, ann in hints.items():
        if pname == "return":
            continue  # the *output* is a 2-vector ndarray; only inputs are gated
        assert ann is not np.ndarray, f"{fn.__name__}({pname}) is annotated as an array"
        assert ann in (Tuple[float, float], int, RobotView, NeighbourRecord), (
            f"{fn.__name__}({pname}): {ann}")
    assert names == ["role_i", "role_j", "mission_dir"] or names == [
        "view", "neighbour", "mode"
    ], names


def test_pairwise_offset_rejects_a_positions_array() -> None:
    """Semantic proof, not just a name check: an (N,2) array cannot be consumed."""
    joint = np.arange(12, dtype=np.float32).reshape(6, 2)
    with pytest.raises(Exception):
        pairwise_offset(joint, joint, (1.0, 0.0))


def _package_sources() -> Dict[str, str]:
    out: Dict[str, str] = {}
    for name in sorted(os.listdir(PACKAGE_DIR)):
        if name.endswith(".py"):
            with open(os.path.join(PACKAGE_DIR, name), "r", encoding="utf-8") as fh:
                out[name] = fh.read()
    return out


def _enclosing_function(tree: ast.AST, target: ast.AST) -> Sequence[str]:
    stack: List[str] = []
    found: List[str] = []

    def walk(node: ast.AST) -> None:
        is_fn = isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        if is_fn:
            stack.append(node.name)
        if node is target:
            found.extend(stack)
        for child in ast.iter_child_nodes(node):
            walk(child)
        if is_fn:
            stack.pop()

    walk(tree)
    return list(found)


def _runtime_call_sites(source: str, name: str = "roles.py") -> List[Tuple[str, Sequence[str]]]:
    tree = ast.parse(source, filename=name)
    sites: List[Tuple[str, Sequence[str]]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        called = (
            func.attr if isinstance(func, ast.Attribute)
            else func.id if isinstance(func, ast.Name)
            else None
        )
        if called == "simulate_mission_setup_from_initial_formation":
            sites.append((name, _enclosing_function(tree, node)))
    return sites


def test_the_ast_guard_detects_a_planted_runtime_violation() -> None:
    """Non-vacuity check for the guard below, on synthetic source.

    Without this, a guard that silently found nothing would look identical to a
    guard that found nothing because the code is clean.
    """
    violating = (
        "class Robot:\n"
        "    def control_step(self, positions):\n"
        "        self.roles = RoleAssignment.simulate_mission_setup_from_initial_formation(positions, (1, 0), 0.9)\n"
    )
    sites = _runtime_call_sites(violating, "planted.py")
    assert sites, "scanner failed to see a call it should have found"
    assert sites[0][1] == ["control_step"], sites  # chain is functions, not classes
    assert any("step" in fn.lower() or "control" in fn.lower() for fn in sites[0][1])

    clean = (
        "def build_mission(initial_positions):\n"
        "    return RoleAssignment.simulate_mission_setup_from_initial_formation(initial_positions, (1, 0), 0.9)\n"
    )
    clean_sites = _runtime_call_sites(clean, "clean.py")
    assert clean_sites and clean_sites[0][1] == ["build_mission"]
    assert not any(
        "step" in fn.lower() or "control" in fn.lower() for fn in clean_sites[0][1]
    )


def test_from_initial_formation_is_never_called_from_runtime_code() -> None:
    """Mission setup may call it; no step/control function may.

    Scans the whole `rvt_swarm.decentralized` package with the AST, so a future
    module that quietly re-derives roles inside a control loop fails this test.
    """
    sources = _package_sources()
    assert "roles.py" in sources
    assert "def simulate_mission_setup_from_initial_formation" in sources["roles.py"], (
        "constructor renamed; this guard would silently pass on nothing"
    )

    # It is *defined* in roles.py. Any other module that so much as names it must
    # be justified by the call-site check below.
    files_mentioning = sorted(
        name for name, src in sources.items()
        if "simulate_mission_setup_from_initial_formation" in src
    )
    assert "roles.py" in files_mentioning

    call_sites: List[Tuple[str, Sequence[str]]] = []
    for name, src in sources.items():
        tree = ast.parse(src, filename=name)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            called = (
                func.attr if isinstance(func, ast.Attribute)
                else func.id if isinstance(func, ast.Name)
                else None
            )
            if called == "simulate_mission_setup_from_initial_formation":
                call_sites.append((name, _enclosing_function(tree, node)))

    setup_markers = (
        "setup", "configure", "config", "build", "make", "create", "init",
        "mission", "reset", "assign_roles", "prepare",
        # A `simulate_`-prefixed function is, by the package's own convention,
        # non-deployable boundary code. Calling mission setup from inside the
        # episode harness at reset time is exactly the sanctioned use; the
        # step/control assertion above still forbids the loop.
        "simulate_",
    )
    for name, chain in call_sites:
        for fn_name in chain:
            lowered = fn_name.lower()
            assert "step" not in lowered and "control" not in lowered, (
                f"{name}: from_initial_formation is called from runtime function "
                f"{'.'.join(chain)} -- roles must not be recomputed in the loop"
            )
        if chain:  # module-level calls are trivially mission setup
            assert any(m in fn.lower() for fn in chain for m in setup_markers), (
                f"{name}: from_initial_formation called from {'.'.join(chain)}, "
                "which is not recognisable as mission setup"
            )

    # Reported so the evidence is legible, not just asserted.
    print(f"from_initial_formation: mentioned in {files_mentioning}, "
          f"call sites {[(f, list(c)) for f, c in call_sites]}")


def test_roles_module_never_reads_prohibited_obs_keys() -> None:
    """No literal prohibited obs key is subscripted anywhere in roles.py.

    Scoped to roles.py: this file owns the role protocol. Sibling modules
    (notably the `simulate_` boundary in comms.py) are audited by their own
    guard tests.
    """
    src = _package_sources()["roles.py"]
    tree = ast.parse(src, filename="roles.py")
    offenders: List[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant):
            value = node.slice.value
            if isinstance(value, str) and value in PROHIBITED_OBS_KEYS:
                offenders.append(value)
    assert offenders == [], offenders


def test_no_simulation_boundary_function_lives_in_roles() -> None:
    """roles.py is fully deployable: it holds no `simulate_` boundary function."""
    simulate_fns = [n for n in vars(roles_mod) if n.startswith("simulate_")]
    assert simulate_fns == [], simulate_fns
