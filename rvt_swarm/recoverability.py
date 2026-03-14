from __future__ import annotations

from dataclasses import replace
from typing import Dict, List, Tuple

import numpy as np

from .config import Config, TOPOLOGY_IDS
from .controllers import expert_action
from .environment import SwarmFormationEnv


CANDIDATE_TOPOLOGIES = TOPOLOGY_IDS


def compute_deadlock_penalty(info: Dict[str, float]) -> float:
    return 0.7 * float(info["deadlock"]) + 0.5 * float(info["stall_rate"] > 0.35) + 0.2 * float(info["stall_rate"])


def compute_formation_tube_score(info: Dict[str, float], cfg: Config) -> float:
    tol = max(cfg.env.formation_tolerance * 1.45, 1e-6)
    return float(np.clip(1.0 - info["form_rms"] / tol, 0.0, 1.0))


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
    alive_bonus = 0.0
    for t in range(horizon):
        obs = sim.observe()
        action = expert_action(obs, cfg, topology_action)
        _, _, done, info = sim.step(action, topology_action)
        progress = float(info["goal_progress"])
        tube = compute_formation_tube_score(info, cfg)
        collision = float(info["collision_free"])
        recover_proxy = float(info["recoverability_proxy"])
        deadlock_penalty = compute_deadlock_penalty(info)
        switch_penalty = 0.08 * float(info["topology_switches"] > 2)
        recovery_bonus = 0.0
        if topology_action == 4:
            recovery_bonus += 0.20 * tube + 0.08 * float(obs.get("split_active", 0.0) > 0.0)
            if obs["bottleneck"] < 0.3:
                recovery_bonus += 0.14
        if topology_action in [2, 3] and obs["bottleneck"] > 0.4:
            recovery_bonus += 0.05
        lingering_split_penalty = 0.12 * float(obs.get("split_active", 0.0) > 0.45 and obs["bottleneck"] < 0.25)
        step_score = 0.95 * collision + 0.65 * progress + 1.55 * tube + 0.75 * recover_proxy + recovery_bonus - deadlock_penalty - switch_penalty - lingering_split_penalty
        alive_bonus += 0.05 * collision
        score += step_score
        if done:
            score += 1.2 * float(info["success"]) + 0.3 * float(info["goal_reached"])
            break
        if t >= 3 and info["irreversible_collapse"] > 0.5:
            score -= 1.0
            break
    return float((score + alive_bonus) / max(horizon, 1))


def classify_recoverability(score: float) -> float:
    if score > 0.78:
        return 1.0
    if score < 0.05:
        return -1.0
    return 0.0


def recoverability_targets(env: SwarmFormationEnv, cfg: Config) -> Tuple[float, int, np.ndarray]:
    scores: List[float] = []
    for topo in CANDIDATE_TOPOLOGIES:
        scores.append(rollout_score(env, topo, cfg.train.recover_horizon, cfg))
    scores_np = np.array(scores, dtype=np.float32)
    best_idx = int(np.argmax(scores_np))
    ordered = np.sort(scores_np)
    gap = float(scores_np[best_idx] - ordered[-2]) if len(ordered) > 1 else float(scores_np[best_idx])
    norm_scores = (scores_np - scores_np.mean()) / max(scores_np.std(), 1e-6)
    formation_bonus = 0.18 if CANDIDATE_TOPOLOGIES[best_idx] == 4 else 0.0
    recover_margin = float(np.tanh(0.55 * gap + 0.30 * scores_np[best_idx] + formation_bonus))
    return recover_margin, CANDIDATE_TOPOLOGIES[best_idx], norm_scores
