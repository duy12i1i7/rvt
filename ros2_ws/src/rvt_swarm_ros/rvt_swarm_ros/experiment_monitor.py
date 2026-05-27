from __future__ import annotations

import csv
import json
import math
import os
import site
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Sequence

import numpy as np
import rclpy
from geometry_msgs.msg import PointStamped
from rclpy.clock import Clock, ClockType
from rclpy.node import Node
from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy


def _default_repo_root() -> Path:
    override = os.environ.get("RVT_SWARM_REPO")
    if override:
        return Path(override).expanduser().resolve()
    return Path(__file__).resolve().parents[5]


REPO_ROOT = _default_repo_root()
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _add_repo_venv_site_packages(repo_root: Path) -> None:
    venv_lib = repo_root / ".venv" / "lib"
    if not venv_lib.exists():
        return
    for site_packages in sorted(venv_lib.glob("python*/site-packages")):
        site.addsitedir(str(site_packages))


_add_repo_venv_site_packages(REPO_ROOT)

from rvt_swarm.config import Config
from rvt_swarm.utils import clip01, normalized_mean, pairwise_dist, vec_norm
from rvt_swarm_msgs.msg import PeerState

from .formation import PeerSnapshot, RuntimeFormationState, compute_context, desired_offsets


@dataclass
class StaticObstacle:
    kind: str
    center: np.ndarray
    yaw: float
    radius: float = 0.0
    size_xy: np.ndarray | None = None


def _parse_pose_xy_yaw(text: str | None) -> tuple[float, float, float]:
    if not text:
        return 0.0, 0.0, 0.0
    vals = [float(v) for v in text.split()]
    vals.extend([0.0] * (6 - len(vals)))
    return vals[0], vals[1], vals[5]


def _load_static_obstacles(world_path: Path) -> List[StaticObstacle]:
    root = ET.parse(world_path).getroot()
    obstacles: List[StaticObstacle] = []
    for model in root.findall(".//world/model"):
        if model.get("name") == "ground_plane":
            continue
        static_tag = model.find("static")
        if static_tag is None or static_tag.text is None or static_tag.text.strip().lower() != "true":
            continue
        model_x, model_y, model_yaw = _parse_pose_xy_yaw(model.findtext("pose"))
        collision = model.find("./link/collision/geometry")
        if collision is None:
            continue
        box = collision.find("box/size")
        cylinder = collision.find("cylinder/radius")
        if box is not None and box.text:
            sx, sy, *_ = [float(v) for v in box.text.split()]
            obstacles.append(
                StaticObstacle(
                    kind="box",
                    center=np.array([model_x, model_y], dtype=np.float32),
                    yaw=model_yaw,
                    size_xy=np.array([sx, sy], dtype=np.float32),
                )
            )
        elif cylinder is not None and cylinder.text:
            obstacles.append(
                StaticObstacle(
                    kind="cylinder",
                    center=np.array([model_x, model_y], dtype=np.float32),
                    yaw=model_yaw,
                    radius=float(cylinder.text),
                )
            )
    return obstacles


def _box_signed_clearance(points: np.ndarray, obstacle: StaticObstacle) -> np.ndarray:
    assert obstacle.size_xy is not None
    rel = points - obstacle.center[None, :]
    c = math.cos(-obstacle.yaw)
    s = math.sin(-obstacle.yaw)
    local = np.column_stack((c * rel[:, 0] - s * rel[:, 1], s * rel[:, 0] + c * rel[:, 1]))
    half = obstacle.size_xy[None, :] * 0.5
    q = np.abs(local) - half
    outside = np.maximum(q, 0.0)
    outside_dist = np.linalg.norm(outside, axis=1)
    inside_dist = np.minimum(np.maximum(q[:, 0], q[:, 1]), 0.0)
    return outside_dist + inside_dist


def _obstacle_clearance_matrix(points: np.ndarray, obstacles: Sequence[StaticObstacle]) -> np.ndarray:
    if len(obstacles) == 0:
        return np.zeros((len(points), 0), dtype=np.float32)
    cols: List[np.ndarray] = []
    for obstacle in obstacles:
        if obstacle.kind == "cylinder":
            clearance = np.linalg.norm(points - obstacle.center[None, :], axis=1) - obstacle.radius
        else:
            clearance = _box_signed_clearance(points, obstacle)
        cols.append(clearance.astype(np.float32))
    return np.stack(cols, axis=1)


class SwarmExperimentMonitor(Node):
    def __init__(self) -> None:
        super().__init__("swarm_monitor")
        self.declare_parameter("repo_root", str(REPO_ROOT))
        self.declare_parameter("peer_topic", "/swarm/peer_states")
        self.declare_parameter("goal_topic", "/swarm/goal")
        self.declare_parameter("team_members", ["tb3_0", "tb3_1"])
        self.declare_parameter("goal_x", 4.0)
        self.declare_parameter("goal_y", 0.0)
        self.declare_parameter("method", "rvt_swarm")
        self.declare_parameter("timeout_sec", 90.0)
        self.declare_parameter("monitor_rate_hz", 6.67)
        self.declare_parameter("peer_timeout_sec", 1.0)
        self.declare_parameter("world_path", "")
        self.declare_parameter("log_dir", str(REPO_ROOT / "results" / "gazebo_runs"))
        self.declare_parameter("run_name", "")

        self.repo_root = Path(self.get_parameter("repo_root").value).expanduser().resolve()
        self.team_members = list(self.get_parameter("team_members").value)
        self.goal = np.array(
            [float(self.get_parameter("goal_x").value), float(self.get_parameter("goal_y").value)],
            dtype=np.float32,
        )
        self.method = str(self.get_parameter("method").value)
        self.timeout_sec = float(self.get_parameter("timeout_sec").value)
        self.peer_timeout_sec = float(self.get_parameter("peer_timeout_sec").value)
        self.log_dir = Path(self.get_parameter("log_dir").value).expanduser().resolve()
        self.run_name = str(self.get_parameter("run_name").value).strip() or datetime.now().strftime(
            "gazebo_%Y%m%d_%H%M%S"
        )

        world_param = str(self.get_parameter("world_path").value).strip()
        if world_param:
            world_path = Path(world_param)
        else:
            world_path = self.repo_root / "ros2_ws" / "src" / "rvt_swarm_ros" / "worlds" / "rvt_cluttered.world"
        self.world_path = world_path.expanduser().resolve()

        self.cfg = Config()
        self.runtime = RuntimeFormationState()
        self.peer_states: Dict[str, PeerSnapshot] = {}
        self.obstacles = _load_static_obstacles(self.world_path)
        self.obstacle_centroids = (
            np.asarray([obs.center for obs in self.obstacles], dtype=np.float32)
            if self.obstacles
            else np.zeros((0, 2), dtype=np.float32)
        )

        self.started = False
        self.finished = False
        self.start_time_sec = 0.0
        self.wall_start_sec = time.monotonic()
        self.step_count = 0
        self.prev_goal_distance: float | None = None
        self.prev_topology_mode: int | None = None
        self.prev_formation_scale: float | None = None
        self.stall_counter = 0
        self.topology_switches = 0
        self.formation_scale_motion = 0.0
        self.history: List[dict] = []
        self.final_summary: dict | None = None

        qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=20,
        )
        self.create_subscription(PeerState, str(self.get_parameter("peer_topic").value), self._peer_cb, qos)
        self.create_subscription(PointStamped, str(self.get_parameter("goal_topic").value), self._goal_cb, qos)

        period = 1.0 / max(float(self.get_parameter("monitor_rate_hz").value), 1e-3)
        self.timer = self.create_timer(period, self._on_timer, clock=Clock(clock_type=ClockType.STEADY_TIME))
        self.get_logger().info(
            f"Swarm monitor ready. Logging run '{self.run_name}' to {self.log_dir}."
        )

    def _peer_cb(self, msg: PeerState) -> None:
        stamp_sec = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
        self.peer_states[msg.robot_name] = PeerSnapshot(
            robot_name=msg.robot_name,
            robot_id=int(msg.robot_id),
            position=np.array([msg.x, msg.y], dtype=np.float32),
            velocity=np.array([msg.vx, msg.vy], dtype=np.float32),
            yaw=float(msg.yaw),
            topology_mode=int(msg.topology_mode),
            formation_scale=float(msg.formation_scale),
            split_active=float(msg.split_active),
            time_since_switch=float(msg.time_since_switch),
            subteam_id=int(msg.subteam_id),
            stamp_sec=stamp_sec,
            recv_wall_sec=time.monotonic(),
        )

    def _goal_cb(self, msg: PointStamped) -> None:
        self.goal = np.array([msg.point.x, msg.point.y], dtype=np.float32)

    def _ordered_team(self, now_wall_sec: float) -> List[PeerSnapshot]:
        active: List[PeerSnapshot] = []
        for name in self.team_members:
            state = self.peer_states.get(name)
            if state is None:
                return []
            if now_wall_sec - state.recv_wall_sec > self.peer_timeout_sec:
                return []
            active.append(state)
        active.sort(key=lambda item: item.robot_id)
        return active

    def _select_runtime(self, team: Sequence[PeerSnapshot]) -> tuple[int, float, float, np.ndarray]:
        lead = min(team, key=lambda item: item.robot_id)
        topology_mode = int(lead.topology_mode)
        formation_scale = float(lead.formation_scale)
        split_active = float(lead.split_active)
        subteam_ids = np.asarray([int(state.subteam_id) for state in team], dtype=np.int64)
        return topology_mode, formation_scale, split_active, subteam_ids

    def _compute_metrics(self, team: Sequence[PeerSnapshot]) -> dict:
        positions = np.asarray([state.position for state in team], dtype=np.float32)
        velocities = np.asarray([state.velocity for state in team], dtype=np.float32)
        topology_mode, formation_scale, split_active, subteam_ids = self._select_runtime(team)
        context = compute_context(self.cfg, positions, velocities, self.goal, self.obstacle_centroids, None)
        corridor = np.array([context["corridor_dx"], context["corridor_dy"]], dtype=np.float32)
        centroid = positions.mean(axis=0)
        offsets = desired_offsets(positions, self.cfg, topology_mode, formation_scale, subteam_ids, corridor)
        desired = centroid[None, :] + offsets
        form_rms = float(np.sqrt(np.mean(np.sum((desired - positions) ** 2, axis=1))))

        goal_distance = float(np.linalg.norm(self.goal - centroid))
        goal_reached = float(goal_distance < self.cfg.env.goal_tolerance)
        if self.prev_goal_distance is not None:
            goal_delta = self.prev_goal_distance - goal_distance
            if goal_delta <= 0.0:
                self.stall_counter += 1
            else:
                self.stall_counter = max(0, self.stall_counter - 1)
        self.prev_goal_distance = goal_distance

        if self.prev_topology_mode is not None and self.prev_topology_mode != topology_mode:
            self.topology_switches += 1
        self.prev_topology_mode = topology_mode

        if self.prev_formation_scale is not None:
            self.formation_scale_motion += abs(self.prev_formation_scale - formation_scale) * self.cfg.env.nominal_spacing
        self.prev_formation_scale = formation_scale

        rr_d = pairwise_dist(positions, positions)
        np.fill_diagonal(rr_d, np.inf)
        rr_collision = float(np.mean(rr_d < self.cfg.env.min_rr_distance))
        rr_clearance = float(np.min(rr_d)) if rr_d.size else float("inf")

        ro_clearances = _obstacle_clearance_matrix(positions, self.obstacles)
        ro_collision = float(np.mean(ro_clearances < self.cfg.env.min_ro_distance)) if ro_clearances.size else 0.0
        ro_clearance = float(np.min(ro_clearances)) if ro_clearances.size else float("inf")

        collision_free = float(rr_collision == 0.0 and ro_collision == 0.0)
        form_ok = float(form_rms < self.cfg.env.formation_tolerance)
        success = float(goal_reached and collision_free and form_ok)
        stall_rate = float(self.stall_counter / max(1, self.step_count))
        stalled_distance = float(self.stall_counter) * self.cfg.env.max_speed * self.cfg.env.dt
        deadlock_distance = max(self.cfg.env.goal_tolerance, self.cfg.env.nominal_spacing)
        deadlock = float(stalled_distance >= deadlock_distance and not goal_reached)
        form_ratio = clip01(form_rms / max(self.cfg.env.formation_tolerance, 1e-6))
        formation_recovery_score = clip01(1.0 - form_ratio)
        formation_recovery_time = float(
            self.step_count / max(formation_recovery_score, 1.0 / max(self.cfg.env.max_steps, 1))
        )
        switch_rate = clip01(self.topology_switches / max(self.step_count, 1))
        scale_motion_rate = float(self.formation_scale_motion / max(self.step_count, 1))
        goal_progress = clip01(1.0 - min(1.0, goal_distance / max(self.cfg.env.world_size, 1e-6)))
        irreversible_collapse = float(
            (not bool(collision_free) and form_rms > self.cfg.env.formation_tolerance)
            or deadlock
            or (split_active > 0.0 and context["bottleneck"] < goal_progress and form_rms > self.cfg.env.formation_tolerance)
        )
        recoverability_proxy = normalized_mean(
            [collision_free, formation_recovery_score, goal_progress]
        ) - normalized_mean([deadlock, irreversible_collapse, switch_rate])

        return {
            "goal_distance": goal_distance,
            "goal_progress": goal_progress,
            "goal_reached": goal_reached,
            "form_rms": form_rms,
            "form_ok": form_ok,
            "rr_collision": rr_collision,
            "ro_collision": ro_collision,
            "rr_clearance_min": rr_clearance,
            "ro_clearance_min": ro_clearance,
            "collision_free": collision_free,
            "success": success,
            "stall_rate": stall_rate,
            "deadlock": deadlock,
            "formation_recovery_score": formation_recovery_score,
            "formation_recovery_time": formation_recovery_time,
            "topology_switches": float(self.topology_switches),
            "formation_scale_motion": float(self.formation_scale_motion),
            "formation_scale_motion_rate": scale_motion_rate,
            "irreversible_collapse": irreversible_collapse,
            "recoverability_proxy": recoverability_proxy,
            "bottleneck": float(context["bottleneck"]),
            "topology_mode": float(topology_mode),
            "formation_scale": float(formation_scale),
            "split_active": float(split_active),
            "team_size": float(len(team)),
            "centroid_x": float(centroid[0]),
            "centroid_y": float(centroid[1]),
        }

    def _write_results(self, reason: str) -> None:
        if self.final_summary is not None:
            return
        self.log_dir.mkdir(parents=True, exist_ok=True)
        summary_path = self.log_dir / f"{self.run_name}.json"
        history_path = self.log_dir / f"{self.run_name}.csv"

        final = self.history[-1] if self.history else {}
        duration_sec = float(final.get("time_sec", 0.0))
        summary = {
            "run_name": self.run_name,
            "reason": reason,
            "duration_sec": duration_sec,
            "steps_recorded": len(self.history),
            "goal": self.goal.tolist(),
            "method": self.method,
            "team_members": list(self.team_members),
            "world_path": str(self.world_path),
            "metrics": final,
            "min_rr_clearance": min((row["rr_clearance_min"] for row in self.history), default=float("inf")),
            "min_ro_clearance": min((row["ro_clearance_min"] for row in self.history), default=float("inf")),
            "max_form_rms": max((row["form_rms"] for row in self.history), default=0.0),
            "topology_modes_seen": sorted({int(row["topology_mode"]) for row in self.history}),
        }
        with summary_path.open("w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)
        if self.history:
            with history_path.open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=list(self.history[0].keys()))
                writer.writeheader()
                writer.writerows(self.history)
        self.final_summary = summary
        self.get_logger().info(f"Wrote experiment summary to {summary_path}")
        self.get_logger().info(f"Wrote experiment trace to {history_path}")

    def _finish(self, reason: str) -> None:
        if self.finished:
            return
        self.finished = True
        self._write_results(reason)
        raise SystemExit(0)

    def _on_timer(self) -> None:
        if self.finished:
            return
        now_wall_sec = time.monotonic()
        elapsed = now_wall_sec - self.wall_start_sec
        team = self._ordered_team(now_wall_sec)
        if not team:
            if elapsed >= self.timeout_sec:
                self._finish("timeout_no_team")
            return
        if not self.started:
            self.started = True
            self.start_time_sec = now_wall_sec
            self.get_logger().info(f"Experiment '{self.run_name}' started with {len(team)} robots.")

        self.step_count += 1
        elapsed = now_wall_sec - self.start_time_sec
        metrics = self._compute_metrics(team)
        metrics["time_sec"] = float(elapsed)
        self.history.append(metrics)

        if metrics["success"] > 0.5:
            self._finish("success")
        if elapsed >= self.timeout_sec:
            self._finish("timeout")


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = SwarmExperimentMonitor()
    try:
        rclpy.spin(node)
    except SystemExit:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
