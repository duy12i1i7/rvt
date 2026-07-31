"""Authoritative geometry utility (Task 5-3).

**The single source of truth for scenario geometry.** Scenario files must call
into this module and must not recompute any of it. Two defects came from
duplicated / assumed geometry:

  * required width was computed as `lateral + 2*(robot_radius + min_ro_distance)`,
    i.e. clearance from the obstacle SURFACE. The environment does not enforce
    that -- `environment.py:566` scores a collision as
    `distance_to_obstacle_CENTRE < min_ro_distance`. The resulting "line-only"
    corridor passed the KEEP formation.
  * corridor walls were short obstacle rows spanning only the passage, so robots
    drove around their ends through open space and the "infeasible" fixture was
    crossed on 100 % of episodes.

Everything here is derived from `EnvConfig` and the authoritative role
templates, never from a report or a remembered number.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from ..config import Config
from .roles import RoleAssignment
from .system_model import KEEP, LINE

Vec2 = Tuple[float, float]


# ---------------------------------------------------------------------------
# Collision model
# ---------------------------------------------------------------------------
def robot_obstacle_threshold(cfg: Config) -> float:
    """Distance to an obstacle CENTRE below which the environment scores a hit.

    Mirrors `environment.py:566` exactly: `ro_d < min_ro_distance`, where `ro_d`
    is measured to the obstacle centre. The obstacle's drawn radius does NOT
    enter the collision test.
    """
    return float(cfg.env.min_ro_distance)


def robot_robot_threshold(cfg: Config) -> float:
    return float(cfg.env.min_rr_distance)


def lateral_extent(n: int, mode: int, cfg: Config) -> float:
    """Lateral span of the authoritative role template."""
    T = np.asarray(RoleAssignment.from_index(n, cfg.env.nominal_spacing)
                   .coords(mode), dtype=np.float64)
    return float(T[:, 1].max() - T[:, 1].min())


def required_half_separation(n: int, mode: int, cfg: Config) -> float:
    """Minimum wall half-separation `h` for the UNDEFORMED template to pass.

    Walls' inner obstacle centres sit at `+/- h`. A robot at lateral offset `y`
    needs `h - |y| > min_ro_distance`, so `h > E/2 + min_ro_distance`.

    NOTE: this is a *template* requirement. The local controller compresses the
    formation under obstacle avoidance, so a corridor below this value is not
    necessarily impassable for the controlled team -- that is what the
    closed-loop width sweep (Task 5-4) measures.
    """
    return lateral_extent(n, mode, cfg) / 2.0 + robot_obstacle_threshold(cfg)


def required_width(n: int, mode: int, cfg: Config) -> float:
    """Free width between the inner wall obstacle centres."""
    return 2.0 * required_half_separation(n, mode, cfg)


def single_robot_half_separation(cfg: Config) -> float:
    """Below this, not even one robot can pass without a collision."""
    return robot_obstacle_threshold(cfg)


# ---------------------------------------------------------------------------
# Wall construction
# ---------------------------------------------------------------------------
def corridor_walls(half_sep: float, x0: float, x1: float, cfg: Config,
                   half_world: float, spacing: Optional[float] = None,
                   centre_y: float = 0.0) -> np.ndarray:
    """Two walls leaving a gap of `2*half_sep` between inner obstacle CENTRES.

    Walls extend from the gap to the world boundary in both directions, so the
    passage cannot be bypassed around their ends. Point spacing defaults to
    `min_ro_distance` so consecutive obstacles' exclusion discs overlap and no
    robot-sized gap exists between them.
    """
    if spacing is None:
        spacing = robot_obstacle_threshold(cfg)
    xs = np.arange(x0, x1 + 1e-9, spacing)
    ys = np.arange(half_sep, half_world + spacing, spacing)
    pts: List[Tuple[float, float]] = []
    for x in xs:
        for y in ys:
            pts.append((float(x), float(centre_y + y)))
            pts.append((float(x), float(centre_y - y)))
    return np.asarray(pts, dtype=np.float64)


def effective_free_width(obstacles: np.ndarray, x: float, cfg: Config,
                         half_world: float, samples: int = 2001) -> float:
    """The free lateral width the COLLISION CHECKER actually leaves at `x`.

    Measured, not declared: samples `y` across the world at this `x` and returns
    the largest contiguous run where every sample is at least
    `min_ro_distance` from every obstacle centre. This is the quantity a
    geometry claim must be validated against.
    """
    if len(obstacles) == 0:
        return 2.0 * half_world
    thr = robot_obstacle_threshold(cfg)
    ys = np.linspace(-half_world, half_world, samples)
    near = obstacles[np.abs(obstacles[:, 0] - x) <= thr + 1e-9]
    if len(near) == 0:
        return 2.0 * half_world
    free = np.ones(samples, dtype=bool)
    for oy in near[:, 1]:
        free &= np.abs(ys - oy) >= thr
    best = run = 0
    for f in free:
        run = run + 1 if f else 0
        best = max(best, run)
    return float(best * (2.0 * half_world) / (samples - 1))


# ---------------------------------------------------------------------------
# Scenario geometry record
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class PassageGeometry:
    """Everything a scenario must declare, all of it computed here."""

    n: int
    half_separation: float
    corridor_x0: float
    corridor_x1: float
    centre_y: float
    entry_x: float
    exit_x: float
    recovery_x0: float
    recovery_width: float
    recovery_length: float
    goal: Vec2
    spawn_centre: Vec2
    half_world: float
    obstacles: np.ndarray

    @property
    def free_width(self) -> float:
        return 2.0 * self.half_separation

    def feasibility_class(self, cfg: Config) -> str:
        """Predicted class for the UNDEFORMED templates. A hypothesis only."""
        h = self.half_separation
        if h <= single_robot_half_separation(cfg):
            return "infeasible"
        if h > required_half_separation(self.n, KEEP, cfg):
            return "keep_feasible"
        if h > required_half_separation(self.n, LINE, cfg):
            return "line_only"
        return "infeasible"


def build_passage(n: int, cfg: Config, half_separation: float, *,
                  half_world: float, corridor_length: float = 1.0,
                  entry_offset: float = 0.0, centre_y: float = 0.0,
                  spawn_gap: float = 3.5) -> PassageGeometry:
    """Construct a passage with a real KEEP approach and a long downstream leg.

    `spawn_gap` must exceed the entry lookahead used by the scripted diagnostic
    policies, or the team is already inside the lookahead at spawn and enters
    LINE at step 0 with no KEEP approach at all. Measured consequence of a
    1.5 m gap against a 2.0 m lookahead: the team traverses the whole map in
    LINE, and after crossing it re-enters the keep tube only in the final 6
    steps -- short of the 20-step dwell -- so recovery scored 0 everywhere.
    """
    pad = cfg.env.robot_radius + robot_obstacle_threshold(cfg)
    spawn_x = -half_world + 1.0 + entry_offset
    x0 = spawn_x + spawn_gap
    x1 = x0 + corridor_length
    goal_x = half_world - 1.0
    entry_x, exit_x = x0 - pad, x1 + pad
    rec_x0 = exit_x + 0.5
    return PassageGeometry(
        n=n, half_separation=half_separation, corridor_x0=x0, corridor_x1=x1,
        centre_y=centre_y, entry_x=entry_x, exit_x=exit_x, recovery_x0=rec_x0,
        recovery_width=2.0 * half_world, recovery_length=goal_x - rec_x0,
        goal=(goal_x, 0.0), spawn_centre=(spawn_x, 0.0), half_world=half_world,
        obstacles=corridor_walls(half_separation, x0, x1, cfg, half_world,
                                 centre_y=centre_y))


def validate_passage(geo: PassageGeometry, cfg: Config) -> Dict[str, object]:
    """Every geometric claim, checked against the collision model."""
    mid_x = 0.5 * (geo.corridor_x0 + geo.corridor_x1)
    measured = effective_free_width(geo.obstacles, mid_x, cfg, geo.half_world)
    # a wall must block every lateral escape at the corridor's x-range
    upstream_free = effective_free_width(geo.obstacles, geo.corridor_x0 - 2.0,
                                         cfg, geo.half_world)
    line_h = required_half_separation(geo.n, LINE, cfg)
    keep_h = required_half_separation(geo.n, KEEP, cfg)
    return {
        "declared_free_width": geo.free_width,
        "measured_free_width": measured,
        "width_matches": bool(abs(measured - geo.free_width) <= 2.0 * robot_obstacle_threshold(cfg)),
        "no_bypass": bool(upstream_free > measured),   # open before, confined at
        "goal_in_bounds": bool(abs(geo.goal[0]) < geo.half_world
                               and abs(geo.goal[1]) < geo.half_world),
        "recovery_width_ok": bool(geo.recovery_width >= 2.0 * keep_h),
        "recovery_length": geo.recovery_length,
        "entry_before_exit": bool(geo.entry_x < geo.exit_x),
        "planes_intersect_passage": bool(geo.entry_x <= geo.corridor_x0
                                         and geo.exit_x >= geo.corridor_x1),
        "line_feasible_template": bool(geo.half_separation > line_h),
        "keep_feasible_template": bool(geo.half_separation > keep_h),
        "feasibility_class": geo.feasibility_class(cfg),
    }
