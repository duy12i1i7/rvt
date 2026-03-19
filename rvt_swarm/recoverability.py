from __future__ import annotations

from dataclasses import replace
from typing import Dict, List, Tuple

import numpy as np

from .config import Config, TOPOLOGY_IDS
from .controllers import expert_action
from .environment import SwarmFormationEnv
from .utils import clip01, normalized_mean, standardize_np


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
        switch_penalty = clip01(switch_count / max(t + 1, 1))
        bottleneck = clip01(float(obs["bottleneck"]))
        split_active = clip01(float(obs.get("split_active", 0.0)))
        open_space = clip01(1.0 - bottleneck)
        recovery_bonus = 0.0
        if topology_action == 4:
            recovery_bonus = normalized_mean([tube, split_active, open_space])
        elif topology_action in (2, 3):
            recovery_bonus = bottleneck
        lingering_split_penalty = split_active * open_space * float(topology_action != 4)
        positive = normalized_mean([collision, progress, tube, recover_proxy, recovery_bonus])
        negative = normalized_mean([deadlock_penalty, switch_penalty, lingering_split_penalty])
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


def recoverability_targets(env: SwarmFormationEnv, cfg: Config) -> Tuple[float, int, np.ndarray]:
    scores: List[float] = []
    for topo in CANDIDATE_TOPOLOGIES:
        scores.append(rollout_score(env, topo, cfg.train.recover_horizon, cfg))
    scores_np = np.array(scores, dtype=np.float32)
    norm_scores = standardize_np(scores_np)
    best_idx = int(np.argmax(norm_scores))
    ordered = np.sort(norm_scores)
    gap = float(norm_scores[best_idx] - ordered[-2]) if len(ordered) > 1 else float(norm_scores[best_idx])
    formation_bonus = float(CANDIDATE_TOPOLOGIES[best_idx] == 4)
    recover_margin = float(np.tanh(norm_scores[best_idx] + gap + formation_bonus))
    return recover_margin, CANDIDATE_TOPOLOGIES[best_idx], norm_scores
