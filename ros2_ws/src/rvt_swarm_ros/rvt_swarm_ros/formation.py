from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Sequence

import numpy as np

from rvt_swarm.config import Config
from rvt_swarm.utils import clip01, unit, vec_norm


@dataclass
class PeerSnapshot:
    robot_name: str
    robot_id: int
    position: np.ndarray
    velocity: np.ndarray
    yaw: float
    topology_mode: int = 0
    formation_scale: float = 1.0
    split_active: float = 0.0
    time_since_switch: float = 0.0
    subteam_id: int = 0
    stamp_sec: float = 0.0
    recv_wall_sec: float = 0.0


@dataclass
class RuntimeFormationState:
    topology_mode: int = 0
    formation_scale: float = 1.0
    split_active: float = 0.0
    time_since_switch: float = 0.0
    topology_switches: int = 0
    formation_scale_motion: float = 0.0
    subteam_ids: Dict[str, int] = field(default_factory=dict)


@dataclass
class ScanSnapshot:
    ranges: np.ndarray
    angle_min: float
    angle_increment: float
    range_min: float
    range_max: float


@dataclass
class ObstacleTrackerState:
    centroids: np.ndarray = field(default_factory=lambda: np.zeros((0, 2), dtype=np.float32))
    stamp_sec: float = 0.0


def _lateral_axis(corridor: np.ndarray) -> np.ndarray:
    return np.array([corridor[1], -corridor[0]], dtype=np.float32)


def _subteam_assignments(positions: np.ndarray, corridor: np.ndarray) -> np.ndarray:
    lateral = _lateral_axis(corridor)
    lat = positions @ lateral
    order = np.argsort(lat)
    split = np.zeros((len(positions),), dtype=np.int64)
    half = int(np.ceil(len(positions) / 2))
    split[order[half:]] = 1
    return split


def desired_offsets(
    positions: np.ndarray,
    cfg: Config,
    topology_mode: int,
    formation_scale: float,
    subteam_ids: np.ndarray,
    corridor: np.ndarray,
) -> np.ndarray:
    n = len(positions)
    spacing = cfg.env.nominal_spacing * formation_scale
    lateral = _lateral_axis(corridor)

    if topology_mode == 2:
        order = np.argsort(positions @ corridor)
        offsets = np.zeros((n, 2), dtype=np.float32)
        for rank, robot_idx in enumerate(order):
            offsets[robot_idx] = corridor * ((rank - (n - 1) / 2.0) * spacing)
        return offsets

    if topology_mode == 3:
        counts = [max(1, int(np.sum(subteam_ids == 0))), max(1, int(np.sum(subteam_ids == 1)))]
        lane_gap = max(cfg.env.nominal_spacing, spacing + cfg.env.min_rr_distance)
        offsets = np.zeros((n, 2), dtype=np.float32)
        for team_id in (0, 1):
            members = np.flatnonzero(subteam_ids == team_id)
            if members.size == 0:
                continue
            order = members[np.argsort(positions[members] @ corridor)]
            for rank, robot_idx in enumerate(order):
                longitudinal = (rank - (counts[team_id] - 1) / 2.0) * spacing
                lane_offset = -lateral if team_id == 0 else lateral
                offsets[robot_idx] = corridor * longitudinal + lane_offset * (0.5 * lane_gap)
        return offsets

    cols = max(2, int(np.ceil(np.sqrt(n))))
    rows = int(np.ceil(n / cols))
    offsets: List[np.ndarray] = []
    for i in range(n):
        r, c = divmod(i, cols)
        offsets.append(
            lateral * ((c - (cols - 1) / 2.0) * spacing)
            + corridor * ((r - (rows - 1) / 2.0) * spacing)
        )
    return np.asarray(offsets, dtype=np.float32)


def estimate_scan_obstacles(
    scan: ScanSnapshot | None,
    self_pose: np.ndarray,
    self_yaw: float,
    tracker: ObstacleTrackerState,
    stamp_sec: float,
    cluster_distance: float,
    max_obstacles: int,
) -> tuple[np.ndarray, np.ndarray, ObstacleTrackerState]:
    if scan is None or scan.ranges.size == 0:
        empty = np.zeros((0, 2), dtype=np.float32)
        return empty, empty, ObstacleTrackerState(empty, stamp_sec)

    points: List[np.ndarray] = []
    for idx, r in enumerate(scan.ranges):
        if not np.isfinite(r):
            continue
        if r <= scan.range_min or r >= scan.range_max:
            continue
        ang = self_yaw + scan.angle_min + idx * scan.angle_increment
        points.append(
            np.array(
                [self_pose[0] + r * math.cos(ang), self_pose[1] + r * math.sin(ang)],
                dtype=np.float32,
            )
        )

    if not points:
        empty = np.zeros((0, 2), dtype=np.float32)
        return empty, empty, ObstacleTrackerState(empty, stamp_sec)

    clusters: List[List[np.ndarray]] = [[points[0]]]
    for pt in points[1:]:
        if vec_norm(pt - clusters[-1][-1]) <= cluster_distance:
            clusters[-1].append(pt)
        else:
            clusters.append([pt])

    if len(clusters) > 1 and vec_norm(clusters[0][0] - clusters[-1][-1]) <= cluster_distance:
        clusters[0] = clusters[-1] + clusters[0]
        clusters.pop()

    centroids = np.asarray([np.mean(cluster, axis=0) for cluster in clusters], dtype=np.float32)
    d = np.linalg.norm(centroids - self_pose[None, :], axis=1)
    order = np.argsort(d)[:max_obstacles]
    centroids = centroids[order]

    velocities = np.zeros_like(centroids)
    prev = tracker.centroids
    dt = max(stamp_sec - tracker.stamp_sec, 1e-3)
    if len(prev):
        used_prev: set[int] = set()
        for i, cur in enumerate(centroids):
            dist = np.linalg.norm(prev - cur[None, :], axis=1)
            prev_idx = int(np.argmin(dist))
            if prev_idx in used_prev:
                continue
            if float(dist[prev_idx]) <= max(cluster_distance * 2.0, 0.5):
                velocities[i] = (cur - prev[prev_idx]) / dt
                used_prev.add(prev_idx)

    return centroids, velocities, ObstacleTrackerState(centroids, stamp_sec)


def compute_context(
    cfg: Config,
    positions: np.ndarray,
    velocities: np.ndarray,
    goal: np.ndarray,
    obstacles: np.ndarray,
    scan: ScanSnapshot | None,
) -> dict[str, float]:
    centroid = positions.mean(axis=0)
    d_goal = vec_norm(goal - centroid)
    corridor = unit(goal - centroid).astype(np.float32)
    if vec_norm(corridor) <= 1e-6:
        corridor = np.array([1.0, 0.0], dtype=np.float32)
    lateral = _lateral_axis(corridor)

    score_terms: List[float] = []
    if len(obstacles):
        rel = obstacles - centroid[None, :]
        d = np.linalg.norm(rel, axis=1)
        local_range = max(cfg.env.nominal_spacing * 2.0, cfg.env.min_ro_distance)
        frontal_range = max(cfg.env.nominal_spacing, cfg.env.min_rr_distance)
        nearby = float(np.mean(d < local_range))
        along = rel @ corridor
        side = rel @ lateral
        frontal = float(np.mean((np.abs(along) < local_range) & (np.abs(side) < frontal_range)))
        score_terms.extend([nearby, frontal])
    if scan is not None and scan.ranges.size:
        valid = scan.ranges[np.isfinite(scan.ranges)]
        if valid.size:
            clipped = np.clip(valid / max(scan.range_max, 1e-6), 0.0, 1.0)
            score_terms.append(float(np.mean(1.0 - clipped)))
    bottleneck = clip01(float(np.mean(score_terms)) if score_terms else 0.0)
    progress = clip01(1.0 - d_goal / max(cfg.env.world_size, 1e-6))
    avg_speed = float(np.mean(np.linalg.norm(velocities, axis=1))) if len(velocities) else 0.0
    return {
        "goal_distance": float(d_goal),
        "progress": float(progress),
        "bottleneck": float(bottleneck),
        "avg_speed": avg_speed,
        "corridor_dx": float(corridor[0]),
        "corridor_dy": float(corridor[1]),
    }


def advance_runtime_state(
    runtime: RuntimeFormationState,
    cfg: Config,
    positions: np.ndarray,
    corridor: np.ndarray,
    bottleneck: float,
    topology_action: int,
    ordered_names: Sequence[str],
) -> RuntimeFormationState:
    next_state = RuntimeFormationState(
        topology_mode=runtime.topology_mode,
        formation_scale=runtime.formation_scale,
        split_active=runtime.split_active,
        time_since_switch=runtime.time_since_switch + 1.0,
        topology_switches=runtime.topology_switches,
        formation_scale_motion=runtime.formation_scale_motion,
        subteam_ids=dict(runtime.subteam_ids),
    )
    old_mode = next_state.topology_mode
    old_scale = next_state.formation_scale
    adaptive_scale = bool(cfg.method.use_adaptive_formation_scale)
    min_scale = clip01(cfg.env.min_rr_distance / max(cfg.env.nominal_spacing, 1e-6))
    bottleneck = clip01(bottleneck)
    open_space = clip01(1.0 - bottleneck)

    if topology_action == 2:
        next_state.topology_mode = 2
        target_scale = max(min_scale, min(next_state.formation_scale, 1.0 - bottleneck * (1.0 - min_scale)))
        blend = max(bottleneck, next_state.split_active)
        if adaptive_scale:
            next_state.formation_scale = float(
                np.clip(
                    next_state.formation_scale + (target_scale - next_state.formation_scale) * blend,
                    min_scale,
                    1.0,
                )
            )
        next_state.split_active = clip01(next_state.split_active * open_space)
    elif topology_action == 3:
        next_state.topology_mode = 3
        split = _subteam_assignments(positions, corridor)
        next_state.subteam_ids = {name: int(team) for name, team in zip(ordered_names, split.tolist())}
        if adaptive_scale:
            next_state.formation_scale = float(
                np.clip(
                    next_state.formation_scale + bottleneck * (1.0 - next_state.formation_scale),
                    min_scale,
                    1.0,
                )
            )
        next_state.split_active = clip01(next_state.split_active + bottleneck)
    else:
        next_state.topology_mode = 0
        target_scale = max(min_scale, 1.0 - bottleneck * (1.0 - min_scale))
        if adaptive_scale:
            next_state.formation_scale = float(
                np.clip(
                    next_state.formation_scale + (target_scale - next_state.formation_scale) * bottleneck,
                    min_scale,
                    1.0,
                )
            )
        next_state.split_active = clip01(next_state.split_active * open_space)
        if topology_action == 4:
            next_state.subteam_ids = {}

    if not adaptive_scale:
        next_state.formation_scale = 1.0

    scale_delta = abs(old_scale - next_state.formation_scale) * cfg.env.nominal_spacing
    next_state.formation_scale_motion += float(scale_delta)
    if old_mode != next_state.topology_mode:
        next_state.topology_switches += 1
        next_state.time_since_switch = 0.0
    return next_state


def build_policy_observation(
    cfg: Config,
    states: Sequence[PeerSnapshot],
    runtime: RuntimeFormationState,
    goal: np.ndarray,
    scan: ScanSnapshot | None,
    obstacles: np.ndarray,
    obstacle_velocities: np.ndarray,
) -> dict:
    positions = np.asarray([state.position for state in states], dtype=np.float32)
    velocities = np.asarray([state.velocity for state in states], dtype=np.float32)
    ordered_names = [state.robot_name for state in states]
    ordered_subteams = np.asarray(
        [runtime.subteam_ids.get(name, state.subteam_id) for name, state in zip(ordered_names, states)],
        dtype=np.int64,
    )
    context = compute_context(cfg, positions, velocities, goal, obstacles, scan)
    corridor = np.array([context["corridor_dx"], context["corridor_dy"]], dtype=np.float32)
    if runtime.topology_mode == 3 and not runtime.subteam_ids:
        ordered_subteams = _subteam_assignments(positions, corridor)
        runtime.subteam_ids = {name: int(team) for name, team in zip(ordered_names, ordered_subteams.tolist())}

    centroid = positions.mean(axis=0)
    goal_vec = goal[None, :] - positions
    offsets = desired_offsets(
        positions,
        cfg,
        runtime.topology_mode,
        runtime.formation_scale,
        ordered_subteams,
        corridor,
    )
    formation_error = centroid[None, :] + offsets - positions

    lidar_scans = np.ones((len(states), cfg.env.lidar_num_rays), dtype=np.float32) * cfg.env.lidar_range
    if scan is not None and scan.ranges.size:
        resampled = np.asarray(scan.ranges, dtype=np.float32)
        if resampled.size != cfg.env.lidar_num_rays:
            src = np.linspace(0.0, 1.0, num=resampled.size, endpoint=True)
            dst = np.linspace(0.0, 1.0, num=cfg.env.lidar_num_rays, endpoint=True)
            resampled = np.interp(dst, src, resampled).astype(np.float32)
        lidar_scans[0] = np.clip(resampled, 0.0, cfg.env.lidar_range)

    return {
        "positions": positions,
        "velocities": velocities,
        "goal": goal.astype(np.float32),
        "goal_vec": goal_vec.astype(np.float32),
        "obstacles": obstacles.astype(np.float32),
        "obstacle_velocities": obstacle_velocities.astype(np.float32),
        "lidar_scans": lidar_scans,
        "scenario": "ros_gazebo",
        "topology_mode": int(runtime.topology_mode),
        "formation_scale": float(runtime.formation_scale),
        "formation_error": formation_error.astype(np.float32),
        "stall_counter": 0,
        "topology_switches": int(runtime.topology_switches),
        "formation_scale_motion": float(runtime.formation_scale_motion),
        "subteam_ids": ordered_subteams,
        "split_active": float(runtime.split_active),
        "time_since_switch": float(runtime.time_since_switch),
        "recovery_progress": 0.0,
        **context,
    }


def action_to_twist(
    action_xy: np.ndarray,
    velocity_xy: np.ndarray,
    yaw: float,
    dt: float,
    max_speed: float,
    max_linear: float,
    max_angular: float,
    heading_gain: float,
) -> tuple[float, float]:
    desired_vel = velocity_xy + np.asarray(action_xy, dtype=np.float32) * float(dt)
    speed = min(vec_norm(desired_vel), max_speed, max_linear)
    if speed <= 1e-4:
        return 0.0, 0.0
    desired_heading = math.atan2(float(desired_vel[1]), float(desired_vel[0]))
    heading_error = math.atan2(math.sin(desired_heading - yaw), math.cos(desired_heading - yaw))
    linear = speed * max(0.0, math.cos(heading_error))
    angular = float(np.clip(heading_gain * heading_error, -max_angular, max_angular))
    return float(linear), angular
