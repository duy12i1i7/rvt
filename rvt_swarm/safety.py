from __future__ import annotations

from typing import Dict

import numpy as np
import torch

from .config import Config, TOPOLOGY_IDS
from .utils import soft_clip, unit


def collision_risk(obs: Dict) -> float:
    pos = obs["positions"]
    risk = 0.0
    for i in range(len(pos)):
        for j in range(i + 1, len(pos)):
            d = np.linalg.norm(pos[i] - pos[j])
            risk = max(risk, max(0.0, 0.9 - d))
        for o in obs["obstacles"]:
            d = np.linalg.norm(pos[i] - o)
            risk = max(risk, max(0.0, 0.95 - d))
    return float(risk)


def progress_direction(obs: Dict) -> np.ndarray:
    centroid = obs["positions"].mean(axis=0)
    return unit(obs["goal"] - centroid)


def simple_recover_shield(actions: np.ndarray, obs: Dict, cfg: Config, recoverability: float | None = None, topo: int = 0) -> np.ndarray:
    if not cfg.method.use_progress_shield:
        return actions
    risk = collision_risk(obs)
    if recoverability is not None:
        risk = max(0.0, risk - 0.15 * float(recoverability))
    # Only intervene above risk threshold — avoid disrupting good actions
    threshold = getattr(cfg.method, 'shield_risk_threshold', 0.35)
    if risk < threshold:
        return actions
    # Additive correction: keep learned action, ADD small collision avoidance
    max_blend = getattr(cfg.method, 'max_shield_blend', 0.3)
    strength = min((risk - threshold) / max(1.0 - threshold, 1e-6), max_blend)
    safe = actions.copy()
    for i in range(len(safe)):
        repel = np.zeros(2, dtype=np.float32)
        for j in range(len(safe)):
            if i == j:
                continue
            diff = obs["positions"][i] - obs["positions"][j]
            d = np.linalg.norm(diff)
            if d < 0.48:  # Very tight — only near-collision
                repel += unit(diff) * (0.48 - d)
        for o in obs["obstacles"]:
            diff = obs["positions"][i] - o
            d = np.linalg.norm(diff)
            if d < 0.56:
                repel += unit(diff) * (0.56 - d)
        # Additive: learned action + small correction (preserves policy quality)
        correction = strength * repel
        safe[i] = soft_clip(safe[i] + correction, cfg.env.max_accel)
    return safe


def choose_topology_from_logits(topology_logits: torch.Tensor) -> int:
    return TOPOLOGY_IDS[int(torch.argmax(topology_logits, dim=-1).item())]


def choose_counterfactual_topology(
    obs: Dict,
    topology_logits: torch.Tensor,
    recoverability_scores: torch.Tensor | None,
    cfg: Config,
    previous_topology: int = 0,
    uncertainty: torch.Tensor | None = None,
) -> int:
    # Cooldown: don't switch if recently switched — let formation converge
    cooldown = getattr(cfg.method, 'topology_cooldown', 5)
    if obs.get("time_since_switch", 999) < cooldown:
        return previous_topology

    topo_prior = torch.softmax(topology_logits / max(cfg.method.topology_temperature, 1e-6), dim=-1).squeeze(0)
    if recoverability_scores is None or not cfg.method.use_counterfactual_topology:
        return choose_topology_from_logits(topology_logits)
    scores = recoverability_scores.squeeze(0).detach().cpu().numpy().astype(np.float32)
    prior = topo_prior.detach().cpu().numpy().astype(np.float32)
    uncert = uncertainty.squeeze(0).detach().cpu().numpy().astype(np.float32) if uncertainty is not None else np.zeros_like(scores)

    # Context bonuses for situationally appropriate topologies
    context = np.zeros_like(scores)
    bottleneck = obs["bottleneck"] > 0.50
    if bottleneck:
        context[TOPOLOGY_IDS.index(1)] += 0.04
        context[TOPOLOGY_IDS.index(2)] += 0.10
        context[TOPOLOGY_IDS.index(3)] += 0.05
    if obs["progress"] > 0.75 and obs["bottleneck"] < 0.30:
        context[TOPOLOGY_IDS.index(4)] += 0.12
    # Strongly prefer keep in easy situations
    if obs["bottleneck"] < 0.35:
        context[TOPOLOGY_IDS.index(0)] += 0.18

    # Heavy switch penalties to preserve formation stability
    switch_penalty = np.zeros_like(scores)
    for idx, topo in enumerate(TOPOLOGY_IDS):
        if topo != previous_topology:
            switch_penalty[idx] = 0.22
        if topo == 3:  # Split is most disruptive
            switch_penalty[idx] += 0.12

    combined = 0.60 * scores + 0.18 * prior + context - 0.18 * uncert - switch_penalty
    best_idx = int(np.argmax(combined))
    current_idx = TOPOLOGY_IDS.index(previous_topology)
    if combined[best_idx] < combined[current_idx] + cfg.method.switch_hysteresis:
        return previous_topology
    return TOPOLOGY_IDS[best_idx]
