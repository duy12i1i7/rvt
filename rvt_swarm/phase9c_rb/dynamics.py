"""F9 dynamic obstacles (RB-11).

The executable contract is authoritative and the descriptive
`obstacle_speed_mps` is not: the two disagree in every non-final F9 layout
(0.15 vs 0.4167 m/s in `train-f9-00`), and
`PHASE8E_F9_DYNAMIC_OBSTACLE_EXECUTION_CONTRACT.md` resolves it in favour of the
timestamped waypoints, because each waypoint is a complete position-time
constraint. This module therefore reads `waypoints`/`segments` and never
`declared_speed_meters_per_second_audit_only`.

The v1 path consumes no random draw. That is explicit -- the dynamic-obstacle
seed identity is still carried through snapshots and matched between candidate
clones, so enabling a stochastic path later cannot silently change matching.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

Vec2 = Tuple[float, float]

MOTION_ID = "timestamped_piecewise_linear_hold_after_final"


@dataclass(frozen=True)
class DynamicObstacle:
    """One moving closed circle with a frozen timestamped path."""

    obstacle_index: int
    radius_meters: float
    waypoints: Tuple[Tuple[float, float, float], ...]      # (x, y, t)
    seed_identity: int

    def __post_init__(self) -> None:
        if self.radius_meters <= 0.0:
            raise ValueError("GEOMETRY_INVALID: nonpositive dynamic obstacle radius")
        if len(self.waypoints) < 2:
            raise ValueError("GEOMETRY_INVALID: fewer than two waypoints")
        for point in self.waypoints:
            if not all(math.isfinite(value) for value in point):
                raise ValueError("GEOMETRY_INVALID: nonfinite waypoint")
        for a, b in zip(self.waypoints, self.waypoints[1:]):
            if not b[2] > a[2]:
                raise ValueError("SCHEDULE_INVALID: nonincreasing waypoint time")

    def segment_index(self, episode_time_seconds: float) -> int:
        """Index of the active segment; clamped before first / after final."""
        if episode_time_seconds <= self.waypoints[0][2]:
            return 0
        for index in range(len(self.waypoints) - 1):
            if episode_time_seconds < self.waypoints[index + 1][2]:
                return index
        return len(self.waypoints) - 2

    def state(self, episode_time_seconds: float) -> Tuple[Vec2, Vec2]:
        """`(position, velocity)` at absolute episode time.

        Hold with zero velocity before the first waypoint and after the last;
        constant velocity inside a segment, changing atomically at waypoints.
        """
        first, last = self.waypoints[0], self.waypoints[-1]
        if episode_time_seconds <= first[2]:
            return ((first[0], first[1]), (0.0, 0.0))
        if episode_time_seconds >= last[2]:
            return ((last[0], last[1]), (0.0, 0.0))
        index = self.segment_index(episode_time_seconds)
        ax, ay, at = self.waypoints[index]
        bx, by, bt = self.waypoints[index + 1]
        duration = bt - at
        alpha = (episode_time_seconds - at) / duration
        return ((ax + alpha * (bx - ax), ay + alpha * (by - ay)),
                ((bx - ax) / duration, (by - ay) / duration))

    def snapshot(self, episode_time_seconds: float) -> Dict[str, object]:
        position, velocity = self.state(episode_time_seconds)
        return {
            "obstacle_index": self.obstacle_index,
            "segment_index": self.segment_index(episode_time_seconds),
            "episode_time_seconds": float(episode_time_seconds),
            "position_meters": [float(position[0]), float(position[1])],
            "velocity_meters_per_second": [float(velocity[0]), float(velocity[1])],
            "radius_meters": float(self.radius_meters),
            "seed_identity": int(self.seed_identity),
            "motion": MOTION_ID,
            "random_draws_consumed": 0,
        }


@dataclass(frozen=True)
class DynamicWorld:
    obstacles: Tuple[DynamicObstacle, ...]
    robot_radius_meters: float
    obstacle_clearance_margin_meters: float
    collision_tolerance_meters: float
    sensing_range_meters: float

    def threshold(self, obstacle: DynamicObstacle) -> float:
        """Same radius-aware circle threshold as the static world."""
        return self.robot_radius_meters + max(
            self.obstacle_clearance_margin_meters, obstacle.radius_meters)

    def swept_collision(self, position_a: Vec2, position_b: Vec2,
                        time_a: float, time_b: float) -> Optional[str]:
        """Continuous check with both robot and obstacle linearly interpolated."""
        from .world import _moving_point_min_distance
        for obstacle in self.obstacles:
            centre_a, _ = obstacle.state(time_a)
            centre_b, _ = obstacle.state(time_b)
            separation = _moving_point_min_distance(position_a, position_b, centre_a, centre_b)
            if separation <= self.threshold(obstacle) + self.collision_tolerance_meters:
                return f"dynamic-{obstacle.obstacle_index}"
        return None

    def observable_tokens(self, position: Vec2, episode_time_seconds: float
                          ) -> Tuple[Tuple[Vec2, Vec2, float, str], ...]:
        """Ego-relative `(rel_center, rel_velocity, radius, key)` within R_obs.

        Waypoints, future velocity changes and the terminal pose are never
        included -- the robot gets the *current* circle only.
        """
        tokens: List[Tuple[float, Vec2, Vec2, float, str]] = []
        for obstacle in self.obstacles:
            centre, velocity = obstacle.state(episode_time_seconds)
            offset = (centre[0] - position[0], centre[1] - position[1])
            distance = math.hypot(offset[0], offset[1])
            if distance <= self.sensing_range_meters:
                tokens.append((distance, offset, velocity, obstacle.radius_meters,
                               f"dynamic-{obstacle.obstacle_index}"))
        tokens.sort(key=lambda item: (item[0], item[4]))
        return tuple((offset, velocity, radius, key)
                     for _, offset, velocity, radius, key in tokens)

    def snapshot(self, episode_time_seconds: float) -> Tuple[Dict[str, object], ...]:
        return tuple(o.snapshot(episode_time_seconds) for o in self.obstacles)


def build_dynamic_world(specification: Mapping[str, object], runtime_config: object,
                        target_contract: Mapping[str, object],
                        dynamic_obstacle_seed: int) -> DynamicWorld:
    obstacles: List[DynamicObstacle] = []
    for entry in specification.get("dynamic_obstacles") or []:
        if str(entry.get("motion")) != MOTION_ID:
            raise ValueError(f"SCHEDULE_INVALID: unsupported motion {entry.get('motion')!r}")
        waypoints = tuple((float(p[0]), float(p[1]), float(p[2]))
                          for p in entry["waypoints"])
        obstacles.append(DynamicObstacle(
            obstacle_index=int(entry["dynamic_obstacle_index"]),
            radius_meters=float(entry["radius_meters"]),
            waypoints=waypoints,
            seed_identity=int(dynamic_obstacle_seed),
        ))
    tolerance = float(
        target_contract["conditions"]["collision_free_complete_horizon"]      # type: ignore[index]
        ["tolerance_meters"])
    return DynamicWorld(
        obstacles=tuple(obstacles),
        robot_radius_meters=float(runtime_config.physical.robot_radius_meters),
        obstacle_clearance_margin_meters=float(runtime_config.safety.obstacle_clearance_margin_meters),
        collision_tolerance_meters=tolerance,
        sensing_range_meters=float(runtime_config.sensing.obstacle_sensing_range_meters),
    )
