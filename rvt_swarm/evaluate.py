from __future__ import annotations

import time
from typing import Dict, List

import numpy as np

from .baselines import historical_baseline
from .config import Config
from .environment import SwarmFormationEnv
from .utils import limit_child_threads, normalized_mean, torch_device


def run_policy_episode(
    method: str,
    cfg: Config,
    n_agents: int,
    scenario: str,
    ckpt_dir: str = "results",
    seed: int | None = None,
    model=None,
) -> Dict[str, float]:
    env = SwarmFormationEnv(cfg)
    obs = env.reset(n_agents, scenario, seed=seed)
    done = False
    last_info = None
    steps = 0
    prev_topo = 0
    recover_fp = 0.0
    recover_fn = 0.0
    start_time = time.perf_counter()
    while not done:
        if method in ["adaptive_formation", "cbf_qp_like", "orca_like", "centralized_mpc"]:
            actions, topo = historical_baseline(method, obs, cfg)
        else:
            from .policy_runtime import infer_learned_action, load_learned_model

            model_device = None
            if model is not None:
                model_device = next(model.parameters()).device
            device = model_device or torch_device(cfg.train.device)
            if model is None:
                model = load_learned_model(method, cfg, ckpt_dir, device)
            runtime = infer_learned_action(method, obs, cfg, model, prev_topo)
            actions = runtime["actions"]
            topo = runtime["topology"]
            recover = runtime["recoverability"]
        prev_topo = topo
        obs, _, done, info = env.step(actions, topo)
        if method in ["rvt_swarm", "instant_cert"] and recover is not None:
            fail_now = float(info["irreversible_collapse"] > 0.5)
            pred_safe = float(recover > 0.0)
            recover_fp += float(pred_safe and fail_now)
            recover_fn += float((1.0 - pred_safe) and (1.0 - fail_now))
        last_info = info
        steps += 1
        if steps >= cfg.env.max_steps:
            break
    assert last_info is not None
    last_info = last_info.copy()
    last_info["steps"] = steps
    last_info["recoverability_false_positive"] = recover_fp / max(steps, 1)
    last_info["recoverability_false_negative"] = recover_fn / max(steps, 1)
    elapsed = max(time.perf_counter() - start_time, 0.0)
    last_info["ms_per_step"] = 1000.0 * elapsed / max(steps, 1)
    return last_info


def _eval_setting(args):
    """Worker: run all episodes for one (method, scenario, n_agents) setting."""
    method, cfg, n_agents, scenario, ckpt_dir, episode_seeds = args
    metrics = []
    for seed in episode_seeds:
        m = run_policy_episode(method, cfg, n_agents, scenario, ckpt_dir, seed=seed)
        metrics.append(m)
    agg = {k: float(np.mean([x[k] for x in metrics])) for k in metrics[0].keys()}
    agg["scenario"] = scenario
    agg["n_agents"] = n_agents
    agg["method"] = method
    return agg


def _setting_episode_seeds(cfg: Config, scenario_idx: int, n_agents: int, n_episodes: int, seed_offset: int = 0) -> List[int]:
    return [
        int(cfg.train.seed + seed_offset + 10_000 * scenario_idx + 100 * n_agents + episode_idx)
        for episode_idx in range(n_episodes)
    ]


def evaluate_method(method: str, cfg: Config, ckpt_dir: str = "results") -> List[Dict]:
    import multiprocessing as mp
    import os

    settings = []
    for scenario_idx, scenario in enumerate(cfg.env.scenarios):
        for n_agents in cfg.env.team_sizes:
            episode_seeds = _setting_episode_seeds(
                cfg, scenario_idx, n_agents, cfg.eval.episodes_per_setting
            )
            settings.append((method, cfg, n_agents, scenario, ckpt_dir, episode_seeds))

    # Baselines are CPU-only → parallelize freely
    # Learned methods use GPU → run sequentially to avoid GPU contention
    if method in ["adaptive_formation", "cbf_qp_like", "orca_like", "centralized_mpc"]:
        auto = max(1, (os.cpu_count() * 3) // 4)
        n_workers = min(len(settings), cfg.train.n_workers or auto)
        with limit_child_threads(True):
            ctx = mp.get_context("spawn")
            with ctx.Pool(n_workers) as pool:
                rows = pool.map(_eval_setting, settings)
    else:
        rows = [_eval_setting(s) for s in settings]

    return rows


def summarize(rows: List[Dict]) -> Dict[str, float]:
    keys = [
        "success", "goal_reached", "collision_free", "form_ok", "rr_collision", "ro_collision",
        "form_rms", "stall_rate", "deadlock", "topology_switches", "formation_recovery_time",
        "irreversible_collapse", "recoverability_false_positive", "recoverability_false_negative", "ms_per_step"
    ]
    out = {k: float(np.mean([r[k] for r in rows])) for k in keys}
    out["max_n"] = max(r["n_agents"] for r in rows)
    return out


def rollout_validation_summary(
    method: str,
    cfg: Config,
    model,
    ckpt_dir: str = "results",
    episodes_per_setting: int | None = None,
    seed_offset: int = 50_000,
) -> Dict[str, float]:
    scenarios = [s for s in cfg.train.rollout_val_scenarios if s in cfg.env.scenarios]
    team_sizes = [n for n in cfg.train.rollout_val_team_sizes if n in cfg.env.team_sizes]
    episodes = int(episodes_per_setting or cfg.train.rollout_val_episodes_per_setting)
    if not scenarios:
        scenarios = list(cfg.env.scenarios[:1])
    if not team_sizes:
        team_sizes = list(cfg.env.team_sizes[-1:])

    rows: List[Dict] = []
    for scenario_idx, scenario in enumerate(scenarios):
        for n_agents in team_sizes:
            metrics = []
            for seed in _setting_episode_seeds(
                cfg,
                scenario_idx,
                n_agents,
                episodes,
                seed_offset=seed_offset,
            ):
                metrics.append(
                    run_policy_episode(
                        method,
                        cfg,
                        n_agents,
                        scenario,
                        ckpt_dir=ckpt_dir,
                        seed=seed,
                        model=model,
                    )
                )
            agg = {k: float(np.mean([x[k] for x in metrics])) for k in metrics[0].keys()}
            agg["scenario"] = scenario
            agg["n_agents"] = n_agents
            agg["method"] = method
            rows.append(agg)
    return summarize(rows)


def rollout_validation_score(summary: Dict[str, float]) -> float:
    positive = normalized_mean(
        [
            summary["success"],
            summary["goal_reached"],
            summary["collision_free"],
            summary["form_ok"],
        ]
    )
    negative = normalized_mean(
        [
            summary["irreversible_collapse"],
            summary["deadlock"],
            summary["stall_rate"],
        ]
    )
    return float(positive - negative)


def rollout_validation_key(summary: Dict[str, float]) -> tuple[float, ...]:
    return (
        float(summary["success"]),
        float(summary["goal_reached"]),
        float(summary["collision_free"]),
        float(summary["form_ok"]),
        -float(summary["irreversible_collapse"]),
        -float(summary["deadlock"]),
        -float(summary["stall_rate"]),
    )
