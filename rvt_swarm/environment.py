from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

import numpy as np

from .config import Config
from .utils import clip01, normalized_mean, pairwise_dist, soft_clip, unit


@dataclass
class EnvState:
    positions: np.ndarray
    velocities: np.ndarray
    goal: np.ndarray
    obstacles: np.ndarray
    obstacle_velocities: np.ndarray
    scenario: str
    step_count: int
    topology_mode: int
    formation_scale: float
    prev_goal_distance: float
    stall_counter: int
    topology_switches: int
    bottleneck_score: float
    corridor_direction: np.ndarray
    formation_recovery_progress: float
    split_active: float
    subteam_ids: np.ndarray
    time_since_switch: int


class SwarmFormationEnv:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.ec = cfg.env
        self.state: EnvState | None = None
        self.n_agents = 0
        self.rng = np.random.default_rng(cfg.train.seed)

    def reset(self, n_agents: int, scenario: str, seed: int | None = None) -> Dict:
        if seed is not None:
            self.rng = np.random.default_rng(seed)
        self.n_agents = n_agents
        positions = self._spawn_agents(n_agents, scenario)
        velocities = np.zeros_like(positions)
        goal = np.array([self.ec.world_size * 0.38, 0.0], dtype=np.float32)
        obstacles, obstacle_velocities = self._spawn_obstacles(scenario)
        prev_goal_distance = float(np.linalg.norm(goal - positions.mean(axis=0)))
        corridor_direction = np.array([0.0, 1.0], dtype=np.float32) if scenario == "narrow_passage" else np.array([1.0, 0.0], dtype=np.float32)
        self.state = EnvState(
            positions=positions,
            velocities=velocities,
            goal=goal,
            obstacles=obstacles,
            obstacle_velocities=obstacle_velocities,
            scenario=scenario,
            step_count=0,
            topology_mode=0,
            formation_scale=1.0,
            prev_goal_distance=prev_goal_distance,
            stall_counter=0,
            topology_switches=0,
            bottleneck_score=0.0,
            corridor_direction=corridor_direction,
            formation_recovery_progress=0.0,
            split_active=0.0,
            subteam_ids=np.zeros((n_agents,), dtype=np.int64),
            time_since_switch=0,
        )
        self.state.bottleneck_score = self._compute_bottleneck_score()
        # Ensure no robot spawns inside an obstacle
        self._resolve_collisions()
        return self.observe()

    def _spawn_agents(self, n_agents: int, scenario: str) -> np.ndarray:
        base = np.array([-self.ec.world_size * 0.38, 0.0], dtype=np.float32)
        spacing = self.ec.nominal_spacing
        cols = max(2, int(np.ceil(np.sqrt(n_agents))))
        if scenario == "narrow_passage":
            cols = max(1, min(4, n_agents // 2))
        rows = int(np.ceil(n_agents / cols))
        pts = []
        for i in range(n_agents):
            r, c = divmod(i, cols)
            offset = np.array([(c - (cols - 1) / 2) * spacing, (r - (rows - 1) / 2) * spacing], dtype=np.float32)
            pts.append(base + offset)
        return np.stack(pts, axis=0)

    def _spawn_obstacles(self, scenario: str) -> Tuple[np.ndarray, np.ndarray]:
        obs = []
        vel = []
        if scenario == "open_field":
            count = 2
        elif scenario == "cluttered":
            count = self.ec.obstacle_count
        elif scenario == "narrow_passage":
            count = self.ec.obstacle_count + 4
        else:
            count = self.ec.obstacle_count
        for _ in range(count):
            x = self.rng.uniform(-2.0, 2.0)
            y = self.rng.uniform(-3.5, 3.5)
            if scenario == "narrow_passage" and abs(x) < 1.1 and abs(y) > 0.9:
                x = self.rng.choice([-0.6, 0.6])
            obs.append([x, y])
            if scenario == "dynamic_obstacles" and len(vel) < self.ec.dynamic_obstacle_count:
                vx = self.rng.choice([-1.0, 1.0]) * self.ec.dynamic_obstacle_speed
                vy = self.rng.uniform(-0.15, 0.15)
                vel.append([vx, vy])
            else:
                vel.append([0.0, 0.0])
        if scenario == "narrow_passage":
            for y in np.linspace(-3.5, 3.5, 10):
                if abs(y) > 0.75:
                    obs.append([0.0, y])
                    vel.append([0.0, 0.0])
        return np.array(obs, dtype=np.float32), np.array(vel, dtype=np.float32)

    def _compute_bottleneck_score(self) -> float:
        assert self.state is not None
        centroid = self.state.positions.mean(axis=0)
        score_terms = []
        if self.state.scenario == "narrow_passage":
            score_terms.append(clip01(1.0 - abs(centroid[0]) / max(self.ec.world_size * 0.5, 1e-6)))
        if len(self.state.obstacles):
            rel = self.state.obstacles - centroid[None, :]
            d = np.linalg.norm(rel, axis=1)
            local_range = max(self.ec.nominal_spacing * 2.0, self.ec.min_ro_distance)
            frontal_range = max(self.ec.nominal_spacing, self.ec.min_rr_distance)
            nearby = float(np.mean(d < local_range))
            frontal = float(np.mean((np.abs(rel[:, 0]) < local_range) & (np.abs(rel[:, 1]) < frontal_range)))
            score_terms.extend([nearby, frontal])
        return clip01(normalized_mean(score_terms))

    def _corridor_direction(self) -> np.ndarray:
        assert self.state is not None
        if self.state.scenario == "narrow_passage":
            return np.array([0.0, 1.0], dtype=np.float32)
        return unit(self.state.goal - self.state.positions.mean(axis=0)).astype(np.float32)

    def _subteam_assignments(self) -> np.ndarray:
        assert self.state is not None
        proj_axis = self.state.corridor_direction
        lateral_axis = np.array([proj_axis[1], -proj_axis[0]], dtype=np.float32)
        lat = self.state.positions @ lateral_axis
        order = np.argsort(lat)
        split = np.zeros((self.n_agents,), dtype=np.int64)
        half = int(np.ceil(self.n_agents / 2))
        split[order[half:]] = 1
        return split

    def desired_offsets(self, mode: int | None = None, scale: float | None = None) -> np.ndarray:
        assert self.state is not None
        mode = self.state.topology_mode if mode is None else mode
        scale = self.state.formation_scale if scale is None else scale
        n = self.n_agents
        spacing = self.ec.nominal_spacing * scale
        corridor = self.state.corridor_direction
        lateral = np.array([corridor[1], -corridor[0]], dtype=np.float32)

        if mode == 2:  # line along corridor
            return np.array([
                corridor * ((i - (n - 1) / 2) * spacing) for i in range(n)
            ], dtype=np.float32)

        if mode == 3:  # split into two lines on both sides of corridor axis
            split = self.state.subteam_ids
            counts = [max(1, int(np.sum(split == 0))), max(1, int(np.sum(split == 1)))]
            lane_gap = max(self.ec.nominal_spacing, spacing + self.ec.min_rr_distance)
            offsets = np.zeros((n, 2), dtype=np.float32)
            idx0 = idx1 = 0
            for i in range(n):
                if split[i] == 0:
                    longitudinal = (idx0 - (counts[0] - 1) / 2) * spacing
                    offsets[i] = corridor * longitudinal - lateral * (0.5 * lane_gap)
                    idx0 += 1
                else:
                    longitudinal = (idx1 - (counts[1] - 1) / 2) * spacing
                    offsets[i] = corridor * longitudinal + lateral * (0.5 * lane_gap)
                    idx1 += 1
            return offsets

        cols = max(2, int(np.ceil(np.sqrt(n))))
        rows = int(np.ceil(n / cols))
        offsets = []
        for i in range(n):
            r, c = divmod(i, cols)
            offsets.append(
                lateral * ((c - (cols - 1) / 2) * spacing)
                + corridor * ((r - (rows - 1) / 2) * spacing)
            )
        return np.array(offsets, dtype=np.float32)

    def infer_context(self) -> Dict[str, float]:
        assert self.state is not None
        centroid = self.state.positions.mean(axis=0)
        d_goal = np.linalg.norm(self.state.goal - centroid)
        self.state.bottleneck_score = self._compute_bottleneck_score()
        self.state.corridor_direction = self._corridor_direction()
        progress = clip01(1.0 - d_goal / max(self.ec.world_size, 1e-6))
        avg_speed = float(np.mean(np.linalg.norm(self.state.velocities, axis=1)))
        return {
            "goal_distance": float(d_goal),
            "progress": float(progress),
            "bottleneck": float(self.state.bottleneck_score),
            "avg_speed": avg_speed,
            "corridor_dx": float(self.state.corridor_direction[0]),
            "corridor_dy": float(self.state.corridor_direction[1]),
            "recovery_progress": float(self.state.formation_recovery_progress),
            "split_active": float(self.state.split_active),
            "time_since_switch": float(self.state.time_since_switch),
        }

    def observe(self) -> Dict:
        assert self.state is not None
        ctx = self.infer_context()
        centroid = self.state.positions.mean(axis=0)
        goal_vec = self.state.goal - self.state.positions
        offsets = self.desired_offsets()
        target_positions = centroid + offsets
        formation_err = target_positions - self.state.positions
        lidar_scans = self._simulate_lidar()
        return {
            "positions": self.state.positions.copy(),
            "velocities": self.state.velocities.copy(),
            "goal": self.state.goal.copy(),
            "goal_vec": goal_vec.copy(),
            "obstacles": self.state.obstacles.copy(),
            "obstacle_velocities": self.state.obstacle_velocities.copy(),
            "lidar_scans": lidar_scans,
            "scenario": self.state.scenario,
            "topology_mode": self.state.topology_mode,
            "formation_scale": self.state.formation_scale,
            "formation_error": formation_err,
            "stall_counter": self.state.stall_counter,
            "topology_switches": self.state.topology_switches,
            "subteam_ids": self.state.subteam_ids.copy(),
            **ctx,
        }

    def apply_topology(self, topology_action: int) -> None:
        assert self.state is not None
        old_mode = self.state.topology_mode
        old_scale = self.state.formation_scale
        self.state.time_since_switch += 1
        adaptive_scale = bool(self.cfg.method.use_adaptive_formation_scale)
        min_scale = clip01(self.ec.min_rr_distance / max(self.ec.nominal_spacing, 1e-6))
        bottleneck = clip01(self.state.bottleneck_score)
        open_space = clip01(1.0 - bottleneck)

        if topology_action == 1:  # compress
            self.state.topology_mode = 0
            target_scale = max(min_scale, 1.0 - bottleneck * (1.0 - min_scale))
            if adaptive_scale:
                self.state.formation_scale = float(
                    np.clip(
                        self.state.formation_scale + (target_scale - self.state.formation_scale) * bottleneck,
                        min_scale,
                        1.0,
                    )
                )
            self.state.split_active = clip01(self.state.split_active * open_space)
        elif topology_action == 2:  # line
            self.state.topology_mode = 2
            target_scale = max(min_scale, min(self.state.formation_scale, 1.0 - bottleneck * (1.0 - min_scale)))
            blend = max(bottleneck, clip01(self.state.split_active))
            if adaptive_scale:
                self.state.formation_scale = float(
                    np.clip(
                        self.state.formation_scale + (target_scale - self.state.formation_scale) * blend,
                        min_scale,
                        1.0,
                    )
                )
            self.state.split_active = clip01(self.state.split_active * open_space)
        elif topology_action == 3:  # split
            self.state.topology_mode = 3
            self.state.subteam_ids = self._subteam_assignments()
            if adaptive_scale:
                self.state.formation_scale = float(
                    np.clip(
                        self.state.formation_scale + bottleneck * (1.0 - self.state.formation_scale),
                        min_scale,
                        1.0,
                    )
                )
            self.state.split_active = clip01(self.state.split_active + bottleneck)
        elif topology_action == 4:  # recover
            self.state.topology_mode = 0
            if adaptive_scale:
                self.state.formation_scale = float(
                    np.clip(
                        self.state.formation_scale + (1.0 - self.state.formation_scale) * max(open_space, clip01(self.state.split_active)),
                        min_scale,
                        1.0,
                    )
                )
            self.state.split_active = clip01(self.state.split_active * bottleneck)
            self.state.subteam_ids[:] = 0
        else:  # keep
            self.state.topology_mode = self.state.topology_mode if bottleneck > open_space else 0
            target_scale = max(min_scale, 1.0 - bottleneck * (1.0 - min_scale))
            if adaptive_scale:
                self.state.formation_scale = float(
                    np.clip(
                        self.state.formation_scale + (target_scale - self.state.formation_scale) * bottleneck,
                        min_scale,
                        1.0,
                    )
                )
            self.state.split_active = clip01(self.state.split_active * open_space)

        if not adaptive_scale:
            self.state.formation_scale = 1.0

        scale_changed = adaptive_scale and abs(old_scale - self.state.formation_scale) * self.ec.nominal_spacing > self.ec.robot_radius
        if old_mode != self.state.topology_mode or scale_changed:
            self.state.topology_switches += 1
            self.state.time_since_switch = 0

    # ── LiDAR simulation ─────────────────────────────────────────
    def _simulate_lidar(self) -> np.ndarray:
        """Cast rays from each robot and return distance readings.

        Returns:
            lidar_scans: (n_agents, lidar_num_rays) array of distances.
                         Each value is in [0, lidar_range].  A value equal
                         to lidar_range means the ray hit nothing.
        """
        n = self.n_agents
        n_rays = self.ec.lidar_num_rays
        max_r = self.ec.lidar_range
        half_fov = self.ec.lidar_fov / 2.0
        pos = self.state.positions
        vel = self.state.velocities
        obs = self.state.obstacles
        r_obs = self.ec.obstacle_radius
        r_robot = self.ec.robot_radius

        scans = np.full((n, n_rays), max_r, dtype=np.float32)
        angles_offset = np.linspace(-half_fov, half_fov, n_rays)

        for i in range(n):
            # Heading from velocity (fallback: toward goal)
            spd = np.linalg.norm(vel[i])
            if spd > 0.02:
                heading = np.arctan2(vel[i, 1], vel[i, 0])
            else:
                gdir = self.state.goal - pos[i]
                heading = np.arctan2(gdir[1], gdir[0])
            ray_angles = heading + angles_offset
            cos_a = np.cos(ray_angles)
            sin_a = np.sin(ray_angles)

            # Check against obstacles (circles)
            for k in range(len(obs)):
                dx = obs[k, 0] - pos[i, 0]
                dy = obs[k, 1] - pos[i, 1]
                # Project onto each ray direction
                # For ray origin O, direction D, circle center C, radius R:
                # t_closest = dot(C-O, D),  dist_perp² = |C-O|² - t²
                # hit if dist_perp < R  and  t > 0
                for ray_idx in range(n_rays):
                    d_x, d_y = cos_a[ray_idx], sin_a[ray_idx]
                    t = dx * d_x + dy * d_y
                    if t < 0:
                        continue
                    perp_sq = dx * dx + dy * dy - t * t
                    if perp_sq < r_obs * r_obs:
                        # Ray enters circle at t - sqrt(R² - perp²)
                        entry = t - np.sqrt(max(0.0, r_obs * r_obs - perp_sq))
                        if 0 < entry < scans[i, ray_idx]:
                            scans[i, ray_idx] = entry

            # Check against other robots (circles)
            for j in range(n):
                if j == i:
                    continue
                dx = pos[j, 0] - pos[i, 0]
                dy = pos[j, 1] - pos[i, 1]
                for ray_idx in range(n_rays):
                    d_x, d_y = cos_a[ray_idx], sin_a[ray_idx]
                    t = dx * d_x + dy * d_y
                    if t < 0:
                        continue
                    perp_sq = dx * dx + dy * dy - t * t
                    if perp_sq < r_robot * r_robot:
                        entry = t - np.sqrt(max(0.0, r_robot * r_robot - perp_sq))
                        if 0 < entry < scans[i, ray_idx]:
                            scans[i, ray_idx] = entry

        return scans

    # ── Collision response helpers ──────────────────────────────────
    def _resolve_collisions(self) -> None:
        """Push apart overlapping robots/obstacles (elastic response).

        Runs a few iterations so that resolving one overlap doesn't create
        another.  This is the standard "position projection" approach used
        in most multi-robot simulators.
        """
        pos = self.state.positions
        obs = self.state.obstacles
        r_robot = self.ec.robot_radius
        r_obs = self.ec.obstacle_radius
        n = self.n_agents

        for _iteration in range(3):  # 3 iterations is enough for light overlaps
            # Robot–robot
            for i in range(n):
                for j in range(i + 1, n):
                    diff = pos[i] - pos[j]
                    d = np.linalg.norm(diff)
                    min_d = 2 * r_robot  # sum of radii
                    if d < min_d and d > 1e-8:
                        overlap = min_d - d
                        push = (overlap / 2 + 0.01) * diff / d
                        pos[i] += push
                        pos[j] -= push
                        # Kill approach velocity component
                        n_hat = diff / d
                        vi_along = np.dot(self.state.velocities[i], n_hat)
                        vj_along = np.dot(self.state.velocities[j], n_hat)
                        if vi_along < 0:
                            self.state.velocities[i] -= vi_along * n_hat
                        if vj_along > 0:
                            self.state.velocities[j] -= vj_along * n_hat

            # Robot–obstacle (obstacles are immovable for robots)
            for i in range(n):
                for k in range(len(obs)):
                    diff = pos[i] - obs[k]
                    d = np.linalg.norm(diff)
                    min_d = r_robot + r_obs
                    if d < min_d and d > 1e-8:
                        overlap = min_d - d
                        push = (overlap + 0.01) * diff / d
                        pos[i] += push
                        # Kill approach velocity toward obstacle
                        n_hat = diff / d
                        v_along = np.dot(self.state.velocities[i], n_hat)
                        if v_along < 0:
                            self.state.velocities[i] -= v_along * n_hat

    def step(self, actions: np.ndarray, topology_action: int = 0) -> Tuple[Dict, float, bool, Dict]:
        assert self.state is not None
        self.apply_topology(topology_action)
        actions = np.asarray(actions, dtype=np.float32)
        for i in range(self.n_agents):
            actions[i] = soft_clip(actions[i], self.ec.max_accel)
        self.state.velocities += actions * self.ec.dt
        speed = np.linalg.norm(self.state.velocities, axis=1, keepdims=True)
        speed = np.maximum(speed, 1e-8)
        over = speed > self.ec.max_speed
        self.state.velocities[over[:, 0]] = self.state.velocities[over[:, 0]] / speed[over[:, 0]] * self.ec.max_speed
        self.state.positions += self.state.velocities * self.ec.dt
        self.state.obstacles += self.state.obstacle_velocities * self.ec.dt
        for j, p in enumerate(self.state.obstacles):
            if abs(p[1]) > self.ec.world_size * 0.35:
                self.state.obstacle_velocities[j, 1] *= -1
            if abs(p[0]) > self.ec.world_size * 0.25:
                self.state.obstacle_velocities[j, 0] *= -1

        # Resolve any overlaps from this step (hard collision response)
        self._resolve_collisions()

        self.state.step_count += 1

        centroid = self.state.positions.mean(axis=0)
        goal_distance = float(np.linalg.norm(self.state.goal - centroid))
        goal_delta = self.state.prev_goal_distance - goal_distance
        if goal_delta <= 0.0:
            self.state.stall_counter += 1
        else:
            self.state.stall_counter = max(0, self.state.stall_counter - 1)
        self.state.prev_goal_distance = goal_distance

        metrics = self.compute_metrics()
        self.state.formation_recovery_progress = clip01(
            1.0 - metrics["form_rms"] / max(self.ec.formation_tolerance, 1e-6)
        )
        form_ratio = clip01(metrics["form_rms"] / max(self.ec.formation_tolerance, 1e-6))
        switch_rate = clip01(metrics["topology_switches"] / max(self.state.step_count, 1))
        positive = normalized_mean(
            [
                metrics["goal_progress"],
                metrics["recoverability_proxy"],
                metrics["formation_recovery_score"],
                metrics["form_ok"],
            ]
        )
        negative = normalized_mean(
            [
                form_ratio,
                clip01(metrics["rr_collision"] + metrics["ro_collision"]),
                metrics["stall_rate"],
                switch_rate,
            ]
        )
        reward = positive - negative
        done = bool(metrics["goal_reached"] or self.state.step_count >= self.ec.max_steps)
        return self.observe(), reward, done, metrics.copy()

    def compute_metrics(self) -> Dict[str, float]:
        assert self.state is not None
        centroid = self.state.positions.mean(axis=0)
        d_goal = np.linalg.norm(self.state.goal - centroid)
        goal_reached = d_goal < self.ec.goal_tolerance
        desired = centroid + self.desired_offsets()
        form_rms = float(np.sqrt(np.mean(np.sum((desired - self.state.positions) ** 2, axis=1))))
        rr_d = pairwise_dist(self.state.positions, self.state.positions)
        np.fill_diagonal(rr_d, 999.0)
        rr_collision = float(np.mean(rr_d < self.ec.min_rr_distance))
        ro_d = pairwise_dist(self.state.positions, self.state.obstacles)
        ro_collision = float(np.mean(ro_d < self.ec.min_ro_distance)) if ro_d.size else 0.0
        collision_free = rr_collision == 0.0 and ro_collision == 0.0
        form_ok = form_rms < self.ec.formation_tolerance
        success = float(goal_reached and collision_free and form_ok)
        stall_rate = float(self.state.stall_counter / max(1, self.state.step_count))
        stalled_distance = float(self.state.stall_counter) * self.ec.max_speed * self.ec.dt
        deadlock_distance = max(self.ec.goal_tolerance, self.ec.nominal_spacing)
        deadlock = float(stalled_distance >= deadlock_distance and not goal_reached)
        form_ratio = clip01(form_rms / max(self.ec.formation_tolerance, 1e-6))
        formation_recovery_score = clip01(1.0 - form_ratio)
        formation_recovery_time = float(
            self.state.step_count / max(formation_recovery_score, 1.0 / max(self.ec.max_steps, 1))
        )
        switch_rate = clip01(self.state.topology_switches / max(self.state.step_count, 1))
        goal_progress = clip01(1.0 - min(1.0, d_goal / max(self.ec.world_size, 1e-6)))
        irrecoverable = float(
            (not collision_free and form_rms > self.ec.formation_tolerance)
            or deadlock
            or (self.state.split_active > 0.0 and self.state.bottleneck_score < goal_progress and form_rms > self.ec.formation_tolerance)
        )
        recoverability_proxy = normalized_mean(
            [
                float(collision_free),
                formation_recovery_score,
                goal_progress,
            ]
        ) - normalized_mean([deadlock, irrecoverable, switch_rate])
        return {
            "goal_distance": float(d_goal),
            "goal_progress": goal_progress,
            "goal_reached": float(goal_reached),
            "form_rms": form_rms,
            "form_ok": float(form_ok),
            "rr_collision": rr_collision,
            "ro_collision": ro_collision,
            "collision_free": float(collision_free),
            "success": success,
            "stall_rate": stall_rate,
            "deadlock": deadlock,
            "formation_recovery_score": formation_recovery_score,
            "topology_switches": float(self.state.topology_switches),
            "formation_recovery_time": formation_recovery_time,
            "irreversible_collapse": irrecoverable,
            "recoverability_proxy": recoverability_proxy,
            "bottleneck": float(self.state.bottleneck_score),
        }
