from __future__ import annotations

import time
from typing import Dict, List

import numpy as np

from .baselines import historical_baseline, is_baseline_method
from .config import Config
from .environment import SwarmFormationEnv
from .metrics import EVALUATION_SCHEMA_VERSION, EpisodeAccumulator
from .splits import (
    TEST,
    VALIDATION,
    assert_no_test_seeds,
    assert_validation_config,
    setting_episode_seeds,
)
from .utils import normalized_mean, torch_device


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
    # Episode-level aggregation with the semantics fixed in
    # docs/EPISODE_METRIC_SPECIFICATION.md.
    accumulator = EpisodeAccumulator(
        formation_tolerance=cfg.env.formation_tolerance, dt=cfg.env.dt
    )
    start_time = time.perf_counter()
    while not done:
        shield_activated = False
        if is_baseline_method(method):
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
            shield_activated = bool(runtime.get("safety_stats", {}).get("activated", 0.0) > 0.5)
        prev_topo = topo
        obs, _, done, info = env.step(actions, topo)
        accumulator.update(info, shield_activated=shield_activated)
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
    last_info = accumulator.finalize(last_info)
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


def _setting_episode_seeds(
    cfg: Config,
    scenario_idx: int,
    n_agents: int,
    n_episodes: int,
    split: str = TEST,
) -> List[int]:
    """Episode seeds drawn from `split`'s namespace.

    Test episodes depend only on `seeds.final_test_seed` and validation episodes
    only on `seeds.validation_seed`; neither depends on `model_seed`, so every
    method and every training seed sees an identical episode set.
    """
    seeds = cfg.seed_config()
    split_seed = seeds.final_test_seed if split == TEST else seeds.validation_seed
    return setting_episode_seeds(split, scenario_idx, n_agents, n_episodes, split_seed=split_seed)


def evaluate_method(
    method: str, cfg: Config, ckpt_dir: str = "results", split: str = TEST
) -> List[Dict]:
    """Evaluate on `split`. Defaults to the final test split.

    This function is *not* a model-selection path: it is called only after a
    checkpoint has been frozen.
    """
    settings = []
    for scenario_idx, scenario in enumerate(cfg.env.scenarios):
        for n_agents in cfg.env.team_sizes:
            episode_seeds = _setting_episode_seeds(
                cfg, scenario_idx, n_agents, cfg.eval.episodes_per_setting, split=split
            )
            settings.append((method, cfg, n_agents, scenario, ckpt_dir, episode_seeds))

    # Evaluate sequentially. This avoids worker-process crashes from
    # platform-specific NumPy / BLAS runtime issues without changing metrics.
    rows = [_eval_setting(s) for s in settings]

    return rows


SUMMARY_KEYS = [
    # task
    "success", "success_terminal", "goal_reached", "goal_reached_terminal",
    "completion_time", "completion_time_censored",
    # safety
    "collision_free", "collision_free_terminal",
    "rr_collision", "ro_collision", "rr_collision_max", "ro_collision_max",
    "robot_robot_collision_steps", "robot_obstacle_collision_steps",
    "min_rr_clearance", "min_ro_clearance",
    # formation
    "form_ok", "time_in_formation_tube", "form_rms", "form_rms_mean", "form_rms_max",
    "formation_recovery_time",
    # liveness / failure
    "stall_rate", "stall_rate_terminal", "deadlock", "deadlock_terminal",
    "irreversible_collapse", "irreversible_collapse_terminal",
    # topology and safety filter
    "topology_switches", "formation_scale_motion_rate",
    "safety_filter_activations", "safety_filter_activation_rate",
    # diagnostics
    "recoverability_false_positive", "recoverability_false_negative", "ms_per_step",
]


def summarize(rows: List[Dict]) -> Dict[str, float]:
    out = {
        k: float(np.nanmean([r[k] for r in rows]))
        for k in SUMMARY_KEYS
        if rows and k in rows[0]
    }
    out["max_n"] = max(r["n_agents"] for r in rows)
    out["evaluation_schema_version"] = float(EVALUATION_SCHEMA_VERSION)
    return out


def summarize_by_team_size(rows: List[Dict]) -> Dict[str, Dict[str, float]]:
    """Aggregate benchmark rows by team size for clearer per-N reporting."""
    grouped: Dict[int, List[Dict]] = {}
    for row in rows:
        grouped.setdefault(int(row["n_agents"]), []).append(row)

    summary: Dict[str, Dict[str, float]] = {}
    for n_agents in sorted(grouped):
        summary[str(n_agents)] = summarize(grouped[n_agents])
        summary[str(n_agents)]["n_agents"] = int(n_agents)
    return summary


def rollout_validation_summary(
    method: str,
    cfg: Config,
    model,
    ckpt_dir: str = "results",
    episodes_per_setting: int | None = None,
    seed_offset: int = 0,
) -> Dict[str, float]:
    """THIS IS A MODEL-SELECTION PATH.

    Everything computed here feeds early stopping, checkpoint ranking, and the
    top-k re-evaluation. It must therefore touch the validation split only. The
    guards below raise `TestSetLeakageError` rather than silently proceeding.
    """
    scenarios = [s for s in cfg.train.rollout_val_scenarios if s in cfg.env.scenarios]
    # Validation team sizes are intentionally NOT filtered against
    # cfg.env.team_sizes: the validation sweep is disjoint from the test sweep by
    # construction, so filtering would empty it.
    team_sizes = list(cfg.train.rollout_val_team_sizes)
    episodes = int(episodes_per_setting or cfg.train.rollout_val_episodes_per_setting)
    if not scenarios:
        scenarios = list(cfg.env.scenarios[:1])
    if not team_sizes:
        raise ValueError("rollout validation requires at least one validation team size")

    assert_validation_config(scenarios, team_sizes, context="rollout_validation_summary")

    rows: List[Dict] = []
    for scenario_idx, scenario in enumerate(scenarios):
        for n_agents in team_sizes:
            metrics = []
            episode_seeds = _setting_episode_seeds(
                cfg,
                scenario_idx,
                n_agents,
                episodes,
                split=VALIDATION,
            )
            assert_no_test_seeds(episode_seeds, context="rollout_validation_summary")
            for seed in episode_seeds:
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
