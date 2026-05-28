from __future__ import annotations
from typing import Dict, Tuple

import numpy as np

from .config import Config
from .controllers import expert_action
from .environment import EnvState, SwarmFormationEnv
from .safety import _build_cbf_constraints, _solve_per_robot_qp, progress_direction
from .utils import clip01, soft_clip, unit, vec_norm

try:
    import rvo2
except ImportError:  # pragma: no cover - depends on optional compiled third-party package.
    rvo2 = None


BASELINE_METHODS = {
    "adaptive_formation",
    "cbf_qp",
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


def cbf_qp(obs: Dict, cfg: Config) -> Tuple[np.ndarray, int]:
    nominal = np.asarray(expert_action(obs, cfg, 0), dtype=np.float32)
    safe = nominal.copy()
    progress_dir = progress_direction(obs)
    for i in range(len(safe)):
        constraints = _build_cbf_constraints(i, obs, cfg)
        if not constraints:
            continue
        safe[i] = _solve_per_robot_qp(
            u_nom=safe[i],
            constraints=constraints,
            progress_dir=progress_dir,
            max_accel=cfg.env.max_accel,
            progress_weight=0.0,
        )
    return safe, 0


def _predictive_state_from_obs(obs: Dict, cfg: Config) -> EnvState:
    positions = np.asarray(obs["positions"], dtype=np.float32).copy()
    velocities = np.asarray(obs["velocities"], dtype=np.float32).copy()
    goal = np.asarray(obs["goal"], dtype=np.float32).copy()
    obstacles = np.asarray(obs["obstacles"], dtype=np.float32).copy()
    obstacle_velocities = np.asarray(
        obs.get("obstacle_velocities", np.zeros_like(obstacles)),
        dtype=np.float32,
    ).copy()
    corridor = np.array(
        [float(obs.get("corridor_dx", 1.0)), float(obs.get("corridor_dy", 0.0))],
        dtype=np.float32,
    )
    if vec_norm(corridor) <= 1e-6:
        corridor = unit(goal - positions.mean(axis=0)).astype(np.float32)
    if vec_norm(corridor) <= 1e-6:
        corridor = np.array([1.0, 0.0], dtype=np.float32)
    prev_goal_distance = float(obs.get("goal_distance", vec_norm(goal - positions.mean(axis=0))))
    subteam_ids = np.asarray(obs.get("subteam_ids", np.zeros((len(positions),), dtype=np.int64)), dtype=np.int64).copy()
    if subteam_ids.shape[0] != len(positions):
        subteam_ids = np.zeros((len(positions),), dtype=np.int64)
    return EnvState(
        positions=positions,
        velocities=velocities,
        goal=goal,
        obstacles=obstacles,
        obstacle_velocities=obstacle_velocities,
        scenario=str(obs.get("scenario", "predictive_rollout")),
        step_count=int(obs.get("step_count", 0)),
        topology_mode=int(obs.get("topology_mode", 0)),
        formation_scale=float(obs.get("formation_scale", 1.0)),
        prev_goal_distance=prev_goal_distance,
        stall_counter=int(obs.get("stall_counter", 0)),
        topology_switches=int(obs.get("topology_switches", 0)),
        bottleneck_score=float(obs.get("bottleneck", 0.0)),
        corridor_direction=corridor.astype(np.float32),
        formation_recovery_progress=float(obs.get("recovery_progress", 0.0)),
        split_active=float(obs.get("split_active", 0.0)),
        subteam_ids=subteam_ids,
        time_since_switch=int(obs.get("time_since_switch", 0.0)),
        formation_scale_motion=float(obs.get("formation_scale_motion", 0.0)),
    )


def _clone_predictive_env(env: SwarmFormationEnv) -> SwarmFormationEnv:
    assert env.state is not None
    clone = SwarmFormationEnv(env.cfg)
    clone.n_agents = env.n_agents
    state = env.state
    clone.state = EnvState(
        positions=state.positions.copy(),
        velocities=state.velocities.copy(),
        goal=state.goal.copy(),
        obstacles=state.obstacles.copy(),
        obstacle_velocities=state.obstacle_velocities.copy(),
        scenario=state.scenario,
        step_count=int(state.step_count),
        topology_mode=int(state.topology_mode),
        formation_scale=float(state.formation_scale),
        prev_goal_distance=float(state.prev_goal_distance),
        stall_counter=int(state.stall_counter),
        topology_switches=int(state.topology_switches),
        bottleneck_score=float(state.bottleneck_score),
        corridor_direction=state.corridor_direction.copy(),
        formation_recovery_progress=float(state.formation_recovery_progress),
        split_active=float(state.split_active),
        subteam_ids=state.subteam_ids.copy(),
        time_since_switch=int(state.time_since_switch),
        formation_scale_motion=float(state.formation_scale_motion),
    )
    return clone


def _mpc_topology_candidates(obs: Dict) -> tuple[int, ...]:
    bottleneck = clip01(float(obs.get("bottleneck", 0.0)))
    split_active = clip01(float(obs.get("split_active", 0.0)))
    recovering = float(obs.get("recovery_progress", 0.0)) < float(obs.get("progress", 0.0))
    candidates = [0, 2]
    if bottleneck > 0.25:
        candidates.append(1)
    if len(obs["positions"]) >= 4 and (bottleneck > 0.35 or split_active > 0.0):
        candidates.append(3)
    if recovering or split_active > 0.0:
        candidates.append(4)
    # Stable de-duplication keeps the branching factor low.
    return tuple(dict.fromkeys(candidates))


def _mpc_budget(n_agents: int) -> tuple[int, int]:
    if n_agents <= 4:
        return 2, 4
    if n_agents <= 8:
        return 2, 3
    if n_agents <= 16:
        return 2, 2
    return 1, 2


def _centralized_mpc_stage_cost(
    cfg: Config,
    metrics: Dict[str, float],
    topology_action: int,
    prev_topology: int,
) -> float:
    goal_term = metrics["goal_distance"] / max(1.0, cfg.env.world_size)
    form_term = metrics["form_rms"] / max(1e-6, cfg.env.formation_tolerance)
    collision_term = clip01(metrics["rr_collision"] + metrics["ro_collision"])
    switch_term = float(topology_action != prev_topology)
    deadlock_term = metrics["deadlock"]
    collapse_term = metrics["irreversible_collapse"]
    success_bonus = metrics["success"]
    recoverability_bonus = clip01(metrics["recoverability_proxy"] + 1.0) * 0.5
    return (
        1.6 * goal_term
        + 0.9 * form_term
        + 8.0 * collision_term
        + 4.0 * deadlock_term
        + 6.0 * collapse_term
        + 0.15 * switch_term
        - 0.8 * success_bonus
        - 0.25 * recoverability_bonus
    )


def centralized_mpc(obs: Dict, cfg: Config) -> Tuple[np.ndarray, int]:
    # Short-horizon beam search keeps the controller predictive without making
    # full benchmark sweeps prohibitively expensive at larger team sizes.
    horizon, beam_width = _mpc_budget(len(obs["positions"]))
    root = SwarmFormationEnv(cfg)
    root.n_agents = len(obs["positions"])
    root.state = _predictive_state_from_obs(obs, cfg)

    beam = [{
        "env": root,
        "cost": 0.0,
        "first_actions": None,
        "first_topology": int(obs.get("topology_mode", 0)),
        "last_topology": int(obs.get("topology_mode", 0)),
    }]
    candidates = _mpc_topology_candidates(obs)

    for depth in range(horizon):
        expanded = []
        for node in beam:
            sim_obs = node["env"].observe()
            for topology_action in candidates:
                trial_env = _clone_predictive_env(node["env"])
                actions = np.asarray(expert_action(sim_obs, cfg, topology_action), dtype=np.float32)
                _, _, done, metrics = trial_env.step(actions, topology_action)
                total_cost = float(node["cost"]) + _centralized_mpc_stage_cost(
                    cfg,
                    metrics,
                    topology_action,
                    int(node["last_topology"]),
                )
                expanded.append(
                    {
                        "env": trial_env,
                        "cost": total_cost,
                        "first_actions": actions if depth == 0 else node["first_actions"],
                        "first_topology": int(topology_action) if depth == 0 else int(node["first_topology"]),
                        "last_topology": int(topology_action),
                        "done": bool(done),
                    }
                )
        if not expanded:
            break
        expanded.sort(key=lambda item: (float(item["cost"]), int(item["done"])))
        beam = expanded[:beam_width]
        if all(item["done"] for item in beam):
            break

    if not beam:
        topo = _heuristic_topology(obs)
        return expert_action(obs, cfg, topo), topo
    best = min(beam, key=lambda item: float(item["cost"]))
    return np.asarray(best["first_actions"], dtype=np.float32), int(best["first_topology"])


def historical_baseline(name: str, obs: Dict, cfg: Config) -> Tuple[np.ndarray, int]:
    if name == "adaptive_formation":
        return adaptive_formation(obs, cfg)
    if name == "cbf_qp":
        return cbf_qp(obs, cfg)
    if name == "cbf_qp_like":
        return cbf_qp_like(obs, cfg)
    if name == "orca":
        return orca(obs, cfg)
    if name == "orca_like":
        return orca_like(obs, cfg)
    if name == "centralized_mpc":
        return centralized_mpc(obs, cfg)
    raise ValueError(name)
