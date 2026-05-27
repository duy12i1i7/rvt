from __future__ import annotations

from typing import Dict, Tuple

import numpy as np

from .config import Config
from .controllers import expert_action
from .utils import clip01, soft_clip, unit, vec_norm

try:
    import rvo2
except ImportError:  # pragma: no cover - depends on optional compiled third-party package.
    rvo2 = None


BASELINE_METHODS = {
    "adaptive_formation",
    "cbf_qp_like",
    "orca",
    "orca_like",
    "centralized_mpc",
}


def is_baseline_method(name: str) -> bool:
    return name in BASELINE_METHODS


def _repulsion(diff: np.ndarray, active_distance: float) -> np.ndarray:
    d = vec_norm(diff)
    if d <= 1e-6 or d >= active_distance:
        return np.zeros(2, dtype=np.float32)
    scale = clip01(1.0 - d / max(active_distance, 1e-6)) / d
    return (diff * scale).astype(np.float32)


def _heuristic_topology(obs: Dict) -> int:
    open_space = clip01(1.0 - float(obs["bottleneck"]))
    split_active = clip01(float(obs.get("split_active", 0.0)))
    recovering = float(obs.get("recovery_progress", 0.0)) < float(obs["progress"])
    if obs["bottleneck"] > open_space:
        return 3 if split_active > 0.0 else 2
    return 4 if recovering and split_active > 0.0 else 0


def _clip_velocity(vec: np.ndarray, max_speed: float) -> np.ndarray:
    speed = vec_norm(vec)
    if speed <= max_speed:
        return vec.astype(np.float32)
    return (vec / max(speed, 1e-6) * max_speed).astype(np.float32)


def _circle_vertices(center: np.ndarray, radius: float, num_vertices: int = 8) -> list[tuple[float, float]]:
    vertices: list[tuple[float, float]] = []
    for idx in range(num_vertices):
        angle = 2.0 * np.pi * float(idx) / float(num_vertices)
        vertices.append(
            (
                float(center[0] + radius * np.cos(angle)),
                float(center[1] + radius * np.sin(angle)),
            )
        )
    return vertices


def _require_rvo2() -> None:
    if rvo2 is None:
        raise ImportError(
            "The 'orca' baseline requires the compiled 'rvo2' module. "
            "Install repo requirements or build third_party/Python-RVO2 first."
        )


def orca(obs: Dict, cfg: Config) -> Tuple[np.ndarray, int]:
    _require_rvo2()

    pos = np.asarray(obs["positions"], dtype=np.float32)
    vel = np.asarray(obs["velocities"], dtype=np.float32)
    obs_pos = np.asarray(obs["obstacles"], dtype=np.float32)
    obs_vel = np.asarray(obs.get("obstacle_velocities", np.zeros_like(obs_pos)), dtype=np.float32)

    topology = _heuristic_topology(obs)
    desired_accel = expert_action(obs, cfg, topology)
    pref_vel = np.asarray(
        [_clip_velocity(vel[i] + cfg.env.dt * desired_accel[i], cfg.env.max_speed) for i in range(len(pos))],
        dtype=np.float32,
    )

    time_horizon = max(2.0 * cfg.env.dt, cfg.env.sensing_radius / max(cfg.env.max_speed, 1e-6))
    sim = rvo2.PyRVOSimulator(
        float(cfg.env.dt),
        float(cfg.env.sensing_radius),
        int(max(len(pos) + len(obs_pos) - 1, 1)),
        float(time_horizon),
        float(time_horizon),
        float(cfg.env.robot_radius),
        float(cfg.env.max_speed),
    )

    moving_mask = np.linalg.norm(obs_vel, axis=1) > 1e-5 if len(obs_vel) else np.zeros((0,), dtype=bool)
    static_obstacles = obs_pos[~moving_mask] if len(obs_pos) else np.zeros((0, 2), dtype=np.float32)
    moving_obstacles = obs_pos[moving_mask] if len(obs_pos) else np.zeros((0, 2), dtype=np.float32)
    moving_obstacle_vel = obs_vel[moving_mask] if len(obs_vel) else np.zeros((0, 2), dtype=np.float32)

    for center in static_obstacles:
        sim.addObstacle(_circle_vertices(center, cfg.env.obstacle_radius))
    if len(static_obstacles):
        sim.processObstacles()

    robot_ids = []
    for i in range(len(pos)):
        robot_ids.append(
            sim.addAgent(
                (float(pos[i, 0]), float(pos[i, 1])),
                float(cfg.env.sensing_radius),
                int(max(len(pos) + len(moving_obstacles) - 1, 1)),
                float(time_horizon),
                float(time_horizon),
                float(cfg.env.robot_radius),
                float(cfg.env.max_speed),
                (float(vel[i, 0]), float(vel[i, 1])),
            )
        )
    obstacle_agent_ids = []
    obstacle_agent_speed = max(cfg.env.dynamic_obstacle_speed, 1e-3)
    for i in range(len(moving_obstacles)):
        ov = moving_obstacle_vel[i]
        obstacle_agent_ids.append(
            sim.addAgent(
                (float(moving_obstacles[i, 0]), float(moving_obstacles[i, 1])),
                float(cfg.env.sensing_radius),
                int(max(len(pos) + len(moving_obstacles) - 1, 1)),
                float(time_horizon),
                float(time_horizon),
                float(cfg.env.obstacle_radius),
                float(max(obstacle_agent_speed, vec_norm(ov))),
                (float(ov[0]), float(ov[1])),
            )
        )

    for agent_id, target_vel in zip(robot_ids, pref_vel):
        sim.setAgentPrefVelocity(agent_id, (float(target_vel[0]), float(target_vel[1])))
    for agent_id, target_vel in zip(obstacle_agent_ids, moving_obstacle_vel):
        sim.setAgentPrefVelocity(agent_id, (float(target_vel[0]), float(target_vel[1])))

    sim.doStep()

    actions = np.zeros_like(pos)
    inv_dt = 1.0 / max(cfg.env.dt, 1e-6)
    for i, agent_id in enumerate(robot_ids):
        next_vel = np.asarray(sim.getAgentVelocity(agent_id), dtype=np.float32)
        actions[i] = soft_clip((next_vel - vel[i]) * inv_dt, cfg.env.max_accel)
    return actions, topology


def orca_like(obs: Dict, cfg: Config) -> Tuple[np.ndarray, int]:
    pos = obs["positions"]
    vel = obs["velocities"]
    goal = obs["goal"]
    n = len(pos)
    actions = np.zeros((n, 2), dtype=np.float32)
    centroid = pos.mean(axis=0)
    desired = unit(goal - centroid)
    rr_active = max(cfg.env.nominal_spacing, cfg.env.min_rr_distance)
    ro_active = max(cfg.env.nominal_spacing, cfg.env.min_ro_distance)
    for i in range(n):
        terms = [
            desired,
            -vel[i] / max(cfg.env.max_speed, 1e-6),
        ]
        for j in range(n):
            if i == j:
                continue
            terms.append(_repulsion(pos[i] - pos[j], rr_active))
        for o in obs["obstacles"]:
            terms.append(_repulsion(pos[i] - o, ro_active))
        mean_term = np.zeros(2, dtype=np.float32)
        for term in terms:
            mean_term += term
        actions[i] = soft_clip(mean_term / float(len(terms)), cfg.env.max_accel)
    return actions, 0


def adaptive_formation(obs: Dict, cfg: Config) -> Tuple[np.ndarray, int]:
    topo = _heuristic_topology(obs)
    actions = expert_action(obs, cfg, topo)
    return actions, topo


def cbf_qp_like(obs: Dict, cfg: Config) -> Tuple[np.ndarray, int]:
    actions = expert_action(obs, cfg, 0)
    pos = obs["positions"]
    rr_active = max(cfg.env.nominal_spacing, cfg.env.min_rr_distance)
    ro_active = max(cfg.env.nominal_spacing, cfg.env.min_ro_distance)
    for i in range(len(pos)):
        repel = np.zeros(2, dtype=np.float32)
        for j in range(len(pos)):
            if i == j:
                continue
            repel += _repulsion(pos[i] - pos[j], rr_active)
        for o in obs["obstacles"]:
            repel += _repulsion(pos[i] - o, ro_active)
        actions[i] = soft_clip(actions[i] + repel, cfg.env.max_accel)
    return actions, 0


def centralized_mpc_proxy(obs: Dict, cfg: Config) -> Tuple[np.ndarray, int]:
    topo = _heuristic_topology(obs)
    actions = expert_action(obs, cfg, topo)
    centroid = obs["positions"].mean(axis=0)
    goal_dir = unit(obs["goal"] - centroid)
    mixed = []
    for a in actions:
        terms = [a / max(cfg.env.max_accel, 1e-6), goal_dir]
        mixed.append(soft_clip((terms[0] + terms[1]) * 0.5, cfg.env.max_accel))
    return np.array(mixed, dtype=np.float32), topo


def historical_baseline(name: str, obs: Dict, cfg: Config) -> Tuple[np.ndarray, int]:
    if name == "adaptive_formation":
        return adaptive_formation(obs, cfg)
    if name == "cbf_qp_like":
        return cbf_qp_like(obs, cfg)
    if name == "orca":
        return orca(obs, cfg)
    if name == "orca_like":
        return orca_like(obs, cfg)
    if name == "centralized_mpc":
        return centralized_mpc_proxy(obs, cfg)
    raise ValueError(name)
