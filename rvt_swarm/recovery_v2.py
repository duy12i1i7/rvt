"""Recovery Event V2 — three separated concepts (Tasks 1-3).

V1 conflated local short-horizon improvement, formation recovery, and eventual
task feasibility into one 14-step label, and consequently fired on 27.8 % of
rollouts in provably impassable corridors.

Here they are three distinct events:

    A. local_progress        short-horizon diagnostic ONLY. Never called recovery.
    B. formation_recovery    tube entry + dwell + no collision/deadlock/collapse.
                             Says nothing about task completion.
    C. task_recovery         THE GOLD STANDARD. Full horizon, requires reaching
                             the completion region, which for a bottleneck
                             scenario cannot be reached without traversing the
                             obstacle structure.

The candidate-mode intervention (Task 2) commits to mode `tau` for `H_commit`
steps and then hands over to a **continuation policy that is identical for every
candidate**, so candidates differ only in the decision being evaluated.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Dict, List, Optional

import numpy as np

from .config import Config
from .controllers import expert_action
from .environment import SwarmFormationEnv
from .regions import ScenarioRegions

# The common continuation mode. Identical for every candidate -- the oracle is
# never allowed a privileged continuation for the candidate it prefers.
CONTINUATION_MODE = 0  # keep


@dataclass
class RolloutRecord:
    """Everything Task 3 requires to be stored per rollout."""
    local_progress: int = 0
    formation_recovery: int = 0
    task_recovery: int = 0
    task_completed: int = 0
    rr_collision_steps: int = 0
    ro_collision_steps: int = 0
    deadlock: int = 0
    irreversible_collapse: int = 0
    tube_entry_time: float = float("nan")
    tube_dwell_max: int = 0
    goal_progress: float = 0.0
    crossed_bottleneck: int = 0
    reached_downstream: int = 0
    terminal_reason: str = "horizon"
    rollout_duration: int = 0

    def as_dict(self) -> Dict:
        return dict(self.__dict__)


def _clone(env: SwarmFormationEnv, cfg: Config) -> SwarmFormationEnv:
    sim = SwarmFormationEnv(cfg)
    sim.n_agents = env.n_agents
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


def rollout(
    env: SwarmFormationEnv,
    mode: int,
    cfg: Config,
    regions: ScenarioRegions,
    rng: np.random.Generator,
    *,
    h_commit: int = 10,
    t_max: int = 120,
    tube_scale: float = 1.0,
    dwell_L: int = 3,
    perturb_pos: float = 0.02,
    perturb_acc: float = 0.03,
    full_mode: bool = False,
    local_horizon: int = 14,
    local_min_progress: float = 0.02,
) -> RolloutRecord:
    """One candidate-mode rollout, returning all three events plus diagnostics.

    Intervention A (default): commit to `mode` for `h_commit` steps, then use the
    common continuation policy. Intervention B (`full_mode=True`): hold `mode`
    for the entire rollout.
    """
    sim_cfg = replace(cfg, env=replace(cfg.env, max_steps=max(t_max + 1, cfg.env.max_steps)))
    sim = _clone(env, sim_cfg)
    sim.state.positions = sim.state.positions + rng.normal(
        0.0, perturb_pos, sim.state.positions.shape).astype(np.float32)

    rec = RolloutRecord()
    obs = sim.observe()
    p0 = float(obs["progress"])
    start_centroid = obs["positions"].mean(axis=0)
    tol = cfg.env.formation_tolerance * tube_scale
    dwell = 0
    local_p0 = p0
    local_form0 = float(np.sqrt(np.mean(np.sum(obs["formation_error"] ** 2, axis=1))))

    for step in range(t_max):
        active = mode if (full_mode or step < h_commit) else CONTINUATION_MODE
        a = expert_action(obs, cfg, active)
        a = a + rng.normal(0.0, perturb_acc, a.shape).astype(np.float32)
        obs, _, _, info = sim.step(a, active)
        rec.rollout_duration = step + 1

        if info["rr_collision"] > 0:
            rec.rr_collision_steps += 1
        if info["ro_collision"] > 0:
            rec.ro_collision_steps += 1
        if info["deadlock"] > 0.5:
            rec.deadlock = 1
        if info["irreversible_collapse"] > 0.5:
            rec.irreversible_collapse = 1

        centroid = obs["positions"].mean(axis=0)
        if regions.has_bottleneck and regions.crossed_exit(centroid):
            rec.crossed_bottleneck = 1
        if regions.has_bottleneck and regions.in_downstream(centroid):
            rec.reached_downstream = 1

        if info["form_rms"] < tol:
            dwell += 1
            if np.isnan(rec.tube_entry_time):
                rec.tube_entry_time = float(step + 1)
            rec.tube_dwell_max = max(rec.tube_dwell_max, dwell)
        else:
            dwell = 0

        # --- local progress diagnostic, evaluated over the first `local_horizon`
        if step + 1 == local_horizon:
            form_now = float(info["form_rms"])
            rec.local_progress = int(
                (float(obs["progress"]) - local_p0) >= local_min_progress
                or form_now < local_form0
            )

        if rec.rr_collision_steps or rec.ro_collision_steps:
            rec.terminal_reason = "collision"
            break
        if rec.irreversible_collapse:
            rec.terminal_reason = "collapse"
            break
        if rec.deadlock:
            rec.terminal_reason = "deadlock"
            break
        if info["goal_reached"] > 0.5:
            rec.task_completed = 1
            rec.terminal_reason = "goal"
            break
    else:
        rec.terminal_reason = "horizon"

    if rec.rollout_duration < local_horizon and rec.local_progress == 0:
        # Episode ended before the diagnostic window closed.
        rec.local_progress = int(rec.task_completed == 1)

    rec.goal_progress = float(obs["progress"]) - p0

    # --- B. formation recovery -------------------------------------------
    rec.formation_recovery = int(
        rec.tube_dwell_max >= dwell_L
        and rec.rr_collision_steps == 0
        and rec.ro_collision_steps == 0
        and rec.deadlock == 0
        and rec.irreversible_collapse == 0
    )

    # --- C. task recovery (GOLD STANDARD) --------------------------------
    completion = bool(rec.task_completed)
    if regions.has_bottleneck:
        # A bottleneck scenario additionally demands actual traversal, so that
        # approaching an impassable wall can never qualify.
        completion = completion and bool(rec.crossed_bottleneck)
    rec.task_recovery = int(
        completion
        and rec.rr_collision_steps == 0
        and rec.ro_collision_steps == 0
        and rec.deadlock == 0
        and rec.irreversible_collapse == 0
        and rec.tube_dwell_max >= dwell_L
    )
    return rec


def evaluate_modes(
    env: SwarmFormationEnv,
    modes: List[int],
    cfg: Config,
    regions: ScenarioRegions,
    rng: np.random.Generator,
    n_rollouts: int = 4,
    **kw,
) -> Dict[int, List[RolloutRecord]]:
    """Every candidate mode, same intervention, same continuation policy."""
    return {m: [rollout(env, m, cfg, regions, rng, **kw) for _ in range(n_rollouts)]
            for m in modes}


def rate(records: List[RolloutRecord], field_name: str) -> float:
    return float(np.mean([getattr(r, field_name) for r in records])) if records else 0.0
