"""Minimal controller-qualification fixtures (Tasks 4R-3, 4R-4).

These are **controller mechanics fixtures**, not the six scientific scenario
families of Task 5. Their geometry is derived from the authoritative role
templates, never from any learned model's performance.

Three fixtures, all at N = 6 (the only team size certified separated, see
`docs/KEEP_LINE_DISJOINTNESS_V3.md`):

  A  OPEN_KEEP        wide, obstacle-free, KEEP feasible throughout
  B  LINE_ONLY        approach -> line-only corridor -> recovery region -> goal
  C  INFEASIBLE       corridor narrower than LINE can safely pass

Episodes start **inside the KEEP tube** by construction: robots are placed on
the persistent KEEP role template with a small bounded perturbation. The
invalidated Task 4 run started at `E_inf^KEEP = 3.018 m` and then counted the
failure to reach KEEP as a recovery failure.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from ..config import Config
from .formation_metric_v3 import EPSILON_FORM, e_inf
from .roles import RoleAssignment, rotation
from .system_model import KEEP, LINE

# Initial-condition tolerance. Strictly smaller than epsilon_form so an episode
# starts comfortably inside the tube rather than on its boundary.
EPSILON_INIT: float = 0.25

# Bounded, seeded perturbation applied to the exact template.
SPAWN_JITTER: float = 0.06

# Safety margin added to a template's required width when sizing free space.
SAFETY_MARGIN: float = 0.30

MISSION_DIR: Tuple[float, float] = (1.0, 0.0)

# World size and episode budget required to host a full KEEP -> LINE -> KEEP
# mission at N = 6. MEASURED, not guessed (Task 4R-4 item 6):
#
#   LINE -> KEEP settling from the exact line template in open space takes
#   ~54 control steps to re-enter the keep tube, and the recovery dwell needs
#   a further L_recover = 20, so ~74 steps must remain AFTER the exit plane.
#   At ~0.135 m/step that is ~10 m of downstream travel.
#
#   The default 12 m world affords only ~40 steps after crossing: the team
#   reaches min E_inf 0.466-0.653 and holds the tube for 0-5 steps before the
#   goal terminates the episode. An 18 m world affords ~87 steps, and all seeds
#   reach 0.192-0.270 with a 38-51 step dwell.
#
# These are properties of the controller and the task, not tuning knobs: the
# numbers were measured before the probe set was run and are not adjusted to
# change any probe's outcome.
FIXTURE_WORLD_SIZE: float = 18.0
FIXTURE_MAX_STEPS: int = 260
MEASURED_SETTLING_STEPS: int = 54


def lateral_extent(n: int, mode: int, cfg: Config) -> float:
    """Lateral span of the AUTHORITATIVE role template, in metres."""
    roles = RoleAssignment.from_index(n, cfg.env.nominal_spacing)
    T = np.asarray(roles.coords(mode), dtype=np.float64)
    return float(T[:, 1].max() - T[:, 1].min())


def required_half_separation(n: int, mode: int, cfg: Config) -> float:
    """Minimum wall half-separation `h` a formation needs to pass safely.

    Derived from the environment's ACTUAL collision model, not from a nominal
    clearance convention. `environment.py:566` scores a robot-obstacle
    collision as `distance_to_obstacle_CENTRE < min_ro_distance`, so a robot at
    lateral offset `y` from the corridor axis needs `h - |y| > min_ro_distance`
    where the walls' inner obstacle centres sit at `+/- h`.

    An earlier version of this module used
    `lateral + 2 * (robot_radius + min_ro_distance)` as a required *width*,
    measuring clearance from the obstacle SURFACE. The environment does not
    enforce that, so the resulting corridors were far more permissive than
    intended: a "line-only" corridor passed the keep formation, and an
    "infeasible" corridor was crossed on every episode.
    """
    return lateral_extent(n, mode, cfg) / 2.0 + cfg.env.min_ro_distance


def required_width(n: int, mode: int, cfg: Config) -> float:
    """Free width between the inner wall obstacle centres."""
    return 2.0 * required_half_separation(n, mode, cfg)


def template_spawn(n: int, cfg: Config, centre: Tuple[float, float],
                   seed: int, mode: int = KEEP,
                   jitter: float = SPAWN_JITTER) -> np.ndarray:
    """Positions on the exact role template plus a bounded seeded perturbation."""
    roles = RoleAssignment.from_index(n, cfg.env.nominal_spacing)
    T = np.asarray(roles.coords(mode), dtype=np.float64)
    T = T - T.mean(axis=0)
    R = rotation(MISSION_DIR).astype(np.float64)
    pos = (R @ T.T).T + np.asarray(centre, dtype=np.float64)
    rng = np.random.default_rng(int(seed))
    return pos + rng.uniform(-jitter, jitter, size=pos.shape)


@dataclass(frozen=True)
class Fixture:
    """A deterministic qualification scenario.

    `obstacles` are point obstacles of radius `cfg.env.obstacle_radius`, laid
    out as two walls forming a corridor of the declared usable width.
    """

    name: str
    n: int
    spawn_centre: Tuple[float, float]
    goal: Tuple[float, float]
    obstacles: np.ndarray
    corridor_width: Optional[float]
    entry_x: Optional[float]
    exit_x: Optional[float]
    recovery_x0: Optional[float]
    recovery_width: Optional[float]
    notes: str = ""

    def initial_positions(self, seed: int, cfg: Config) -> np.ndarray:
        return template_spawn(self.n, cfg, self.spawn_centre, seed)


def _corridor_walls(half_sep: float, x0: float, x1: float, obstacle_radius: float,
                    half_world: float, spacing: float = 0.5) -> np.ndarray:
    """A corridor that actually confines: walls span from the gap to the world edge.

    Usable width is measured between obstacle SURFACES, so the inner wall
    centres sit at +/- (width/2 + obstacle_radius).

    The first version laid two short rows of obstacles along the corridor only.
    Robots simply drove AROUND them through the open space beyond, which is why
    the deliberately infeasible fixture was crossed 100% of the time. Blocking
    the flanks all the way to the world boundary is what makes the fixture test
    what it claims to.

    Point spacing 0.5 m against radius 0.35 m gives overlapping obstacles, so
    the wall has no gaps a robot could thread.
    """
    inner = half_sep          # obstacle CENTRES sit here; see required_half_separation
    xs = np.arange(x0, x1 + 1e-9, spacing)
    ys = np.arange(inner, half_world + spacing, spacing)
    pts = []
    for x in xs:
        for y in ys:
            pts.append((x, y))
            pts.append((x, -y))
    return np.asarray(pts, dtype=np.float64)


def fixture_config(base: Optional[Config] = None) -> Config:
    """A Config sized to host the mission. Use this for every fixture episode."""
    cfg = base or Config()
    cfg.train.device = "cpu"
    cfg.env.scenarios = ["cluttered"]
    cfg.env.world_size = FIXTURE_WORLD_SIZE
    cfg.env.max_steps = FIXTURE_MAX_STEPS
    return cfg


def build_fixtures(cfg: Optional[Config] = None, n: int = 6) -> Dict[str, Fixture]:
    """The three fixtures. Geometry is computed, not hard-coded."""
    cfg = cfg or fixture_config()
    r_obs = cfg.env.obstacle_radius
    h_keep = required_half_separation(n, KEEP, cfg)   # 1.450 m at N=6
    h_line = required_half_separation(n, LINE, cfg)   # 0.550 m at N=6

    # -- B: line-only corridor ------------------------------------------
    # w_line + margin <= corridor < w_keep + margin, taken at the midpoint of
    # that interval so the choice is not tuned to any policy.
    # h_line + margin <= h <= h_keep - margin, at the midpoint so the choice is
    # not tuned to any policy. LINE passes, KEEP cannot.
    corridor_h = 0.5 * ((h_line + SAFETY_MARGIN) + (h_keep - SAFETY_MARGIN))
    corridor_w = 2.0 * corridor_h
    # World is [-6, 6]^2 and the episode budget is 120 steps at 0.9 m/s
    # (16.2 m of travel), so the whole mission must fit inside the world with
    # room to spare. The previous fixture put the goal at x = 12, outside the
    # world entirely, which is why every probe scored goal_reached = 0.
    half = cfg.env.world_size / 2.0
    # Corridor placed early so the DOWNSTREAM leg is as long as possible; the
    # settling measurement above is what sets that priority.
    spawn_x = -half + 1.0
    corridor_x0, corridor_x1 = spawn_x + 1.5, spawn_x + 2.5
    goal_x = half - 1.0
    pad = cfg.env.robot_radius + cfg.env.min_ro_distance
    entry_x, exit_x = corridor_x0 - pad, corridor_x1 + pad
    # Recovery region: comfortably wider than KEEP needs, and long enough for
    # the controller to converge (length set in the fixture doc from a measured
    # settling time, not guessed).
    recovery_x0 = exit_x + 0.5
    recovery_w = 2.0 * half            # open beyond the corridor
    line_only = Fixture(
        name="B_line_only_corridor", n=n,
        spawn_centre=(spawn_x, 0.0), goal=(goal_x, 0.0),
        obstacles=_corridor_walls(corridor_h, corridor_x0, corridor_x1, r_obs, half),
        corridor_width=corridor_w, entry_x=entry_x, exit_x=exit_x,
        recovery_x0=recovery_x0, recovery_width=recovery_w,
        notes=(f"wall half-separation {corridor_h:.3f} m; LINE needs > {h_line:.3f}, "
               f"KEEP needs > {h_keep:.3f}"))

    # -- A: open field ---------------------------------------------------
    open_keep = Fixture(
        name="A_open_keep", n=n,
        spawn_centre=(spawn_x, 0.0), goal=(goal_x, 0.0),
        obstacles=np.zeros((0, 2), dtype=np.float64),
        corridor_width=None, entry_x=None, exit_x=None,
        recovery_x0=None, recovery_width=None,
        notes="no obstacles; KEEP feasible throughout")

    # -- C: infeasible ---------------------------------------------------
    # Narrower than a single robot can safely pass: 2*(r_robot + d_ro) is the
    # clearance one robot needs, so anything below it is impassable.
    # Below the single-robot requirement, so even one robot on the centreline
    # is inside the collision threshold.
    infeasible_h = cfg.env.min_ro_distance - 0.10
    infeasible_w = 2.0 * infeasible_h
    infeasible = Fixture(
        name="C_infeasible", n=n,
        spawn_centre=(spawn_x, 0.0), goal=(goal_x, 0.0),
        obstacles=_corridor_walls(infeasible_h, corridor_x0, corridor_x1, r_obs, half),
        corridor_width=infeasible_w, entry_x=entry_x, exit_x=exit_x,
        recovery_x0=None, recovery_width=None,
        notes=(f"wall half-separation {infeasible_h:.3f} m < single-robot "
               f"requirement {cfg.env.min_ro_distance:.3f}"))

    return {f.name: f for f in (open_keep, line_only, infeasible)}


# ---------------------------------------------------------------------------
# Initial-condition validation (Task 4R-3)
# ---------------------------------------------------------------------------
def validate_initial_conditions(fixture: Fixture, seed: int,
                                cfg: Optional[Config] = None,
                                comm_radius: float = 3.0) -> Dict[str, object]:
    """Every precondition an episode must satisfy before it may be scored."""
    cfg = cfg or Config()
    pos = fixture.initial_positions(seed, cfg)
    roles = RoleAssignment.from_index(fixture.n, cfg.env.nominal_spacing)

    err = e_inf(pos, roles, KEEP, MISSION_DIR)
    # robot-robot
    d_rr = float("inf")
    for i in range(len(pos)):
        for j in range(i + 1, len(pos)):
            d_rr = min(d_rr, float(np.linalg.norm(pos[i] - pos[j])))
    # robot-obstacle
    d_ro = float("inf")
    if len(fixture.obstacles):
        for p in pos:
            d = np.linalg.norm(fixture.obstacles - p, axis=1) - cfg.env.obstacle_radius
            d_ro = min(d_ro, float(d.min()))
    # connectivity of the nominal communication graph
    adj = {i: [j for j in range(len(pos)) if j != i
               and np.linalg.norm(pos[i] - pos[j]) <= comm_radius]
           for i in range(len(pos))}
    seen, stack = {0}, [0]
    while stack:
        u = stack.pop()
        for v in adj[u]:
            if v not in seen:
                seen.add(v)
                stack.append(v)
    bound = cfg.env.world_size / 2.0 - cfg.env.robot_radius

    return {
        "e_inf_keep": err,
        "in_keep_tube": bool(err <= EPSILON_INIT),
        "min_robot_robot": d_rr,
        "no_rr_collision": bool(d_rr > cfg.env.min_rr_distance),
        "min_robot_obstacle": d_ro,
        "no_ro_collision": bool(d_ro > cfg.env.min_ro_distance),
        "in_bounds": bool(np.all(np.abs(pos) <= bound)),
        "connected": bool(len(seen) == len(pos)),
        "valid": bool(err <= EPSILON_INIT
                      and d_rr > cfg.env.min_rr_distance
                      and (not len(fixture.obstacles) or d_ro > cfg.env.min_ro_distance)
                      and np.all(np.abs(pos) <= bound)
                      and len(seen) == len(pos)),
    }


# ---------------------------------------------------------------------------
# Fixture -> environment
# ---------------------------------------------------------------------------
def fixture_layout(fixture: Fixture):
    """A `Layout` carrying the fixture's geometry."""
    from ..layouts import Layout
    return Layout(layout_id=f"fixture_{fixture.name}", family="qualification",
                  split="train", obstacles=[tuple(o) for o in fixture.obstacles],
                  goal=tuple(fixture.goal),
                  start_center=tuple(fixture.spawn_centre), params={})


def simulate_reset_to_fixture(env, fixture: Fixture, seed: int,
                              cfg: Optional[Config] = None):
    """BOUNDARY: reset `env` with the robots placed on the KEEP role template.

    The environment spawns procedurally and then translates by `start_center`.
    We substitute `_spawn_agents` for the duration of the reset so the robots
    land on the exact persistent-role template (plus bounded jitter) instead,
    and the translation cancels exactly. The substitution is removed
    immediately afterwards.

    This is initialization, not control: it runs once, before t = 0.
    """
    cfg = cfg or Config()
    lay = fixture_layout(fixture)
    target = fixture.initial_positions(seed, cfg).astype(np.float32)
    shift = (np.asarray(fixture.spawn_centre, dtype=np.float32)
             - np.array([-env.ec.world_size * 0.38, 0.0], dtype=np.float32))
    original = env._spawn_agents
    try:
        env._spawn_agents = lambda n_agents, scenario: (target - shift)
        obs = env.reset(fixture.n, "cluttered", seed=seed, layout=lay)
    finally:
        env._spawn_agents = original
    return obs
