from __future__ import annotations

import math
import os
import site
import sys
from pathlib import Path
from typing import Dict, List

import numpy as np
import rclpy
from geometry_msgs.msg import PointStamped, Twist
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import LaserScan


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
from rvt_swarm.baselines import historical_baseline
from rvt_swarm.policy_runtime import infer_learned_action, is_learned_method, load_learned_model
from rvt_swarm.utils import torch_device, vec_norm

from rvt_swarm_msgs.msg import PeerState

from .formation import (
    ObstacleTrackerState,
    PeerSnapshot,
    RuntimeFormationState,
    ScanSnapshot,
    action_to_twist,
    advance_runtime_state,
    build_policy_observation,
    estimate_scan_obstacles,
)


def yaw_from_quaternion(x: float, y: float, z: float, w: float) -> float:
    siny_cosp = 2.0 * (w * z + x * y)
    cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
    return math.atan2(siny_cosp, cosy_cosp)


class RVTSwarmAgent(Node):
    def __init__(self) -> None:
        super().__init__("rvt_agent")
        self.declare_parameter("repo_root", str(REPO_ROOT))
        self.declare_parameter("ckpt_dir", str(REPO_ROOT / "results"))
        self.declare_parameter("method", "rvt_swarm")
        self.declare_parameter("robot_name", "tb3_0")
        self.declare_parameter("robot_id", 0)
        self.declare_parameter("team_members", ["tb3_0", "tb3_1", "tb3_2", "tb3_3"])
        self.declare_parameter("peer_topic", "/swarm/peer_states")
        self.declare_parameter("goal_topic", "/swarm/goal")
        self.declare_parameter("control_rate_hz", 6.67)
        self.declare_parameter("communication_radius", 4.0)
        self.declare_parameter("peer_timeout_sec", 1.0)
        self.declare_parameter("obstacle_cluster_distance", 0.35)
        self.declare_parameter("max_obstacles", 16)
        self.declare_parameter("goal_x", 4.0)
        self.declare_parameter("goal_y", 0.0)
        self.declare_parameter("twist_heading_gain", 2.8)
        self.declare_parameter("twist_max_linear", 0.22)
        self.declare_parameter("twist_max_angular", 1.82)

        self.repo_root = Path(self.get_parameter("repo_root").value).expanduser().resolve()
        self.ckpt_dir = str(Path(self.get_parameter("ckpt_dir").value).expanduser().resolve())
        self.method = str(self.get_parameter("method").value)
        self.robot_name = str(self.get_parameter("robot_name").value)
        self.robot_id = int(self.get_parameter("robot_id").value)
        self.team_members = list(self.get_parameter("team_members").value)
        self.communication_radius = float(self.get_parameter("communication_radius").value)
        self.peer_timeout_sec = float(self.get_parameter("peer_timeout_sec").value)
        self.obstacle_cluster_distance = float(self.get_parameter("obstacle_cluster_distance").value)
        self.max_obstacles = int(self.get_parameter("max_obstacles").value)
        self.goal = np.array(
            [float(self.get_parameter("goal_x").value), float(self.get_parameter("goal_y").value)],
            dtype=np.float32,
        )
        self.heading_gain = float(self.get_parameter("twist_heading_gain").value)
        self.max_linear = float(self.get_parameter("twist_max_linear").value)
        self.max_angular = float(self.get_parameter("twist_max_angular").value)

        self.cfg = Config()
        self.device = torch_device("cpu")
        self.model = load_learned_model(self.method, self.cfg, self.ckpt_dir, self.device) if is_learned_method(self.method) else None
        self.runtime = RuntimeFormationState()
        self.obstacle_tracker = ObstacleTrackerState()

        self.self_state: PeerSnapshot | None = None
        self.peer_states: Dict[str, PeerSnapshot] = {}
        self.last_scan: ScanSnapshot | None = None

        qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=20,
        )
        sensor_qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=5,
        )

        self.peer_pub = self.create_publisher(PeerState, str(self.get_parameter("peer_topic").value), qos)
        self.cmd_pub = self.create_publisher(Twist, "cmd_vel", 10)
        self.create_subscription(Odometry, "odom", self._odom_cb, sensor_qos)
        self.create_subscription(LaserScan, "scan", self._scan_cb, sensor_qos)
        self.create_subscription(PeerState, str(self.get_parameter("peer_topic").value), self._peer_cb, qos)
        self.create_subscription(PointStamped, str(self.get_parameter("goal_topic").value), self._goal_cb, qos)

        period = 1.0 / max(float(self.get_parameter("control_rate_hz").value), 1e-3)
        self.timer = self.create_timer(period, self._control_step)
        self.get_logger().info(
            f"RVT agent ready for {self.robot_name} using checkpoint dir {self.ckpt_dir}."
        )

    def _odom_cb(self, msg: Odometry) -> None:
        pose = msg.pose.pose
        twist = msg.twist.twist
        yaw = yaw_from_quaternion(
            pose.orientation.x,
            pose.orientation.y,
            pose.orientation.z,
            pose.orientation.w,
        )
        vx_body = float(twist.linear.x)
        vy_body = float(twist.linear.y)
        vx = vx_body * math.cos(yaw) - vy_body * math.sin(yaw)
        vy = vx_body * math.sin(yaw) + vy_body * math.cos(yaw)
        now = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
        subteam_id = int(self.runtime.subteam_ids.get(self.robot_name, 0))
        self.self_state = PeerSnapshot(
            robot_name=self.robot_name,
            robot_id=self.robot_id,
            position=np.array([pose.position.x, pose.position.y], dtype=np.float32),
            velocity=np.array([vx, vy], dtype=np.float32),
            yaw=yaw,
            topology_mode=self.runtime.topology_mode,
            formation_scale=self.runtime.formation_scale,
            split_active=self.runtime.split_active,
            time_since_switch=self.runtime.time_since_switch,
            subteam_id=subteam_id,
            stamp_sec=now,
        )

    def _scan_cb(self, msg: LaserScan) -> None:
        ranges = np.asarray(msg.ranges, dtype=np.float32)
        self.last_scan = ScanSnapshot(
            ranges=ranges,
            angle_min=float(msg.angle_min),
            angle_increment=float(msg.angle_increment),
            range_min=float(msg.range_min),
            range_max=min(float(msg.range_max), self.cfg.env.lidar_range),
        )

    def _peer_cb(self, msg: PeerState) -> None:
        if msg.robot_name == self.robot_name:
            return
        now = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
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
            stamp_sec=now,
        )

    def _goal_cb(self, msg: PointStamped) -> None:
        self.goal = np.array([msg.point.x, msg.point.y], dtype=np.float32)

    def _publish_peer_state(self) -> None:
        if self.self_state is None:
            return
        msg = PeerState()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.robot_name = self.self_state.robot_name
        msg.robot_id = int(self.self_state.robot_id)
        msg.x = float(self.self_state.position[0])
        msg.y = float(self.self_state.position[1])
        msg.yaw = float(self.self_state.yaw)
        msg.vx = float(self.self_state.velocity[0])
        msg.vy = float(self.self_state.velocity[1])
        msg.topology_mode = int(self.runtime.topology_mode)
        msg.formation_scale = float(self.runtime.formation_scale)
        msg.split_active = float(self.runtime.split_active)
        msg.time_since_switch = float(self.runtime.time_since_switch)
        msg.subteam_id = int(self.runtime.subteam_ids.get(self.robot_name, 0))
        self.peer_pub.publish(msg)

    def _active_team(self, now_sec: float) -> List[PeerSnapshot]:
        if self.self_state is None:
            return []
        active = [self.self_state]
        for name, state in self.peer_states.items():
            if now_sec - state.stamp_sec > self.peer_timeout_sec:
                continue
            if vec_norm(state.position - self.self_state.position) > self.communication_radius:
                continue
            active.append(state)
        active.sort(key=lambda item: item.robot_id)
        return active

    def _control_step(self) -> None:
        if self.self_state is None:
            return
        now_sec = self.get_clock().now().nanoseconds * 1e-9
        self._publish_peer_state()
        team = self._active_team(now_sec)
        if len(team) < 2:
            return

        obstacles, obstacle_velocities, self.obstacle_tracker = estimate_scan_obstacles(
            self.last_scan,
            self.self_state.position,
            self.self_state.yaw,
            self.obstacle_tracker,
            now_sec,
            cluster_distance=self.obstacle_cluster_distance,
            max_obstacles=self.max_obstacles,
        )
        obs = build_policy_observation(
            self.cfg,
            team,
            self.runtime,
            self.goal,
            self.last_scan,
            obstacles,
            obstacle_velocities,
        )

        if is_learned_method(self.method):
            result = infer_learned_action(
                self.method,
                obs,
                self.cfg,
                self.model,
                prev_topology=self.runtime.topology_mode,
            )
        else:
            actions, topology = historical_baseline(self.method, obs, self.cfg)
            result = {"actions": actions, "topology": topology}

        self_index = next(idx for idx, state in enumerate(team) if state.robot_name == self.robot_name)
        action_xy = np.asarray(result["actions"][self_index], dtype=np.float32)
        linear, angular = action_to_twist(
            action_xy,
            self.self_state.velocity,
            self.self_state.yaw,
            self.cfg.env.dt,
            self.cfg.env.max_speed,
            self.max_linear,
            self.max_angular,
            self.heading_gain,
        )
        cmd = Twist()
        cmd.linear.x = float(linear)
        cmd.angular.z = float(angular)
        self.cmd_pub.publish(cmd)

        ordered_names = [state.robot_name for state in team]
        corridor = np.array([obs["corridor_dx"], obs["corridor_dy"]], dtype=np.float32)
        self.runtime = advance_runtime_state(
            self.runtime,
            self.cfg,
            obs["positions"],
            corridor,
            obs["bottleneck"],
            int(result["topology"]),
            ordered_names,
        )


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = RVTSwarmAgent()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
