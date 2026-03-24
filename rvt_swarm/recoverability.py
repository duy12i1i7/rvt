from __future__ import annotations

from dataclasses import replace
from typing import Dict, List, Tuple

import numpy as np

from .config import Config, TOPOLOGY_IDS
from .controllers import expert_action
from .environment import SwarmFormationEnv
from .safety import select_topology_from_score_signal, topology_context_features, topology_switch_readiness
from .utils import clip01, normalized_mean


CANDIDATE_TOPOLOGIES = TOPOLOGY_IDS


def compute_deadlock_penalty(info: Dict[str, float]) -> float:
    stall_rate = clip01(float(info["stall_rate"]))
    return normalized_mean([float(info["deadlock"]), stall_rate, float(stall_rate > 0.0)])


def compute_formation_tube_score(info: Dict[str, float], cfg: Config) -> float:
    tol = max(cfg.env.formation_tolerance, 1e-6)
    return clip01(1.0 - float(info["form_rms"]) / tol)


def clone_env(env: SwarmFormationEnv, cfg: Config) -> SwarmFormationEnv:
    sim = SwarmFormationEnv(cfg)
    sim.n_agents = env.n_agents
    assert env.state is not None
    sim.state = replace(
        env.state,
        positions=env.state.positions.copy(),
        velocities=env.state.velocities.copy(),
        goal=env.state.goal.copy(),
        obstacles=env.state.obstacles.copy(),
        obstacle_velocities=env.state.obstacle_velocities.copy(),
        corridor_direction=env.state.corridor_direction.copy(),
        subteam_ids=env.state.subteam_ids.copy(),
    )
    return sim


def rollout_score(env: SwarmFormationEnv, topology_action: int, horizon: int, cfg: Config) -> float:
    sim = clone_env(env, cfg)
    score = 0.0
    prev_switches = 0.0
    for t in range(horizon):
        obs = sim.observe()
        action = expert_action(obs, cfg, topology_action)
        _, _, done, info = sim.step(action, topology_action)
        progress = float(info["goal_progress"])
        tube = compute_formation_tube_score(info, cfg)
        collision = float(info["collision_free"])
        recover_proxy = float(info["recoverability_proxy"])
        deadlock_penalty = compute_deadlock_penalty(info)
        switch_count = float(info["topology_switches"])
        switch_penalty = clip01(max(switch_count - prev_switches, 0.0))
        prev_switches = switch_count
        positive = normalized_mean([collision, progress, tube, recover_proxy])
        negative = normalized_mean([deadlock_penalty, switch_penalty])
        step_score = positive - negative
        score += step_score
        if done:
            score += normalized_mean(
                [
                    float(info["success"]),
                    float(info["goal_reached"]),
                    float(info["collision_free"]),
                ]
            )
            break
        if t >= 3 and info["irreversible_collapse"] > 0.5:
            score -= clip01(float(info["irreversible_collapse"]) + float(info["deadlock"]))
            break
    return float(score / max(horizon, 1))


def classify_recoverability(score: float) -> float:
    if score > 0.0:
        return 1.0
    if score < 0.0:
        return -1.0
    return 0.0


def recoverability_targets(
    env: SwarmFormationEnv,
    cfg: Config,
    obs: Dict | None = None,
    previous_topology: int = 0,
) -> Tuple[float, int, np.ndarray, float]:
    scores: List[float] = []
    for topo in CANDIDATE_TOPOLOGIES:
        scores.append(rollout_score(env, topo, cfg.train.recover_horizon, cfg))
    scores_np = np.array(scores, dtype=np.float32)
    best_idx = int(np.argmax(scores_np))
    ordered = np.sort(scores_np)
    best_score = float(scores_np[best_idx])
    gap = best_score - float(ordered[-2]) if len(ordered) > 1 else best_score
    score_scale = max(float(np.mean(np.abs(scores_np))), 1e-6)
    best_signal = best_score / score_scale
    gap_signal = gap / score_scale
    recover_margin = float(np.tanh(0.5 * (best_signal + gap_signal)))
    keep_idx = CANDIDATE_TOPOLOGIES.index(0)
    keep_margin = float(np.tanh(float(scores_np[keep_idx]) / score_scale))
    score_targets = np.tanh(scores_np / score_scale).astype(np.float32)
    current_obs = env.observe() if obs is None else obs
    allowed, context = topology_context_features(current_obs, cfg, previous_topology)
    switch_ready = topology_switch_readiness(current_obs, previous_topology)
    selected_topology = select_topology_from_score_signal(
        score_targets,
        allowed,
        context,
        previous_topology=previous_topology,
        switch_ready=switch_ready,
    )
    return recover_margin, selected_topology, score_targets, keep_margin
