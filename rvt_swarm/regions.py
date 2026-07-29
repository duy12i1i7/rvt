"""Geometric regions derived from scenario geometry (Task 4).

The V1 recovery label fired on teams that merely *approached* a wall. These
regions make traversal a geometric fact: the exit plane sits beyond every
obstacle in the constricting structure, so a centroid past it cannot have got
there without going through.

Everything here is computed from obstacle coordinates. No learned model output is
involved at any point.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np


@dataclass(frozen=True)
class ScenarioRegions:
    """Axis-aligned regions along the corridor (+x) direction.

        approach   |  entrance | interior | exit |  downstream        goal
      -------------+-----------+----------+------+------------------+-----
                 x_in                          x_exit            goal
    """

    has_bottleneck: bool
    entrance_x: float      # first plane of the constricting structure
    exit_x: float          # plane beyond the last obstacle of the structure
    downstream_x: float    # exit_x plus a clearance margin
    goal: np.ndarray
    goal_tolerance: float
    start_x: float

    # ---- membership tests (centroid-based) --------------------------------
    def in_approach(self, centroid) -> bool:
        return float(centroid[0]) < self.entrance_x

    def in_interior(self, centroid) -> bool:
        return self.entrance_x <= float(centroid[0]) <= self.exit_x

    def crossed_exit(self, centroid) -> bool:
        """True only past the last obstacle of the constricting structure."""
        return float(centroid[0]) > self.exit_x

    def in_downstream(self, centroid) -> bool:
        return float(centroid[0]) >= self.downstream_x

    def in_goal(self, centroid) -> bool:
        return float(np.linalg.norm(np.asarray(centroid) - self.goal)) < self.goal_tolerance

    def starts_downstream(self) -> bool:
        """Guard: a layout whose start is already past the exit cannot test crossing."""
        return self.start_x > self.exit_x


def regions_for(obstacles, goal, cfg, start_x: Optional[float] = None,
                min_wall_tiles: int = 3) -> ScenarioRegions:
    """Derive regions from obstacle geometry.

    A *constricting structure* is a set of obstacles clustered in x that the team
    must pass. It is detected as the densest x-band of obstacles between the start
    and the goal; a layout with too few obstacles in any band has no bottleneck.
    """
    obstacles = np.asarray(obstacles, dtype=np.float64).reshape(-1, 2)
    goal = np.asarray(goal, dtype=np.float64)
    start_x = float(start_x if start_x is not None else -cfg.env.world_size * 0.38)
    clearance = cfg.env.obstacle_radius + cfg.env.min_ro_distance

    if len(obstacles) == 0:
        return ScenarioRegions(False, start_x, start_x, start_x, goal,
                               cfg.env.goal_tolerance, start_x)

    # Obstacles between the start and the goal are candidates for the structure.
    between = obstacles[(obstacles[:, 0] > start_x) & (obstacles[:, 0] < goal[0])]
    if len(between) < min_wall_tiles:
        # Sparse clutter: no structure that must be traversed.
        return ScenarioRegions(False, start_x, start_x, start_x, goal,
                               cfg.env.goal_tolerance, start_x)

    # Cluster in x with a tolerance of one obstacle diameter; take the widest
    # cluster (the wall/blocker), then bracket it.
    xs = np.sort(np.unique(np.round(between[:, 0], 3)))
    groups, cur = [], [xs[0]]
    for x in xs[1:]:
        if x - cur[-1] <= 2.0 * cfg.env.obstacle_radius + 0.5:
            cur.append(x)
        else:
            groups.append(cur)
            cur = [x]
    groups.append(cur)
    counts = [int(((between[:, 0] >= g[0] - 1e-6) & (between[:, 0] <= g[-1] + 1e-6)).sum())
              for g in groups]
    best = int(np.argmax(counts))
    if counts[best] < min_wall_tiles:
        return ScenarioRegions(False, start_x, start_x, start_x, goal,
                               cfg.env.goal_tolerance, start_x)

    entrance_x = float(groups[best][0]) - clearance
    exit_x = float(groups[best][-1]) + clearance
    return ScenarioRegions(True, entrance_x, exit_x, exit_x + 0.5 * clearance,
                           goal, cfg.env.goal_tolerance, start_x)


def regions_for_layout(layout, cfg) -> ScenarioRegions:
    return regions_for(layout.obstacle_array, np.asarray(layout.goal), cfg,
                       start_x=float(layout.start_center[0]))
