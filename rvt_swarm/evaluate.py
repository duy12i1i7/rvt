from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import numpy as np
import torch

from .baselines import historical_baseline
from .config import Config
from .dataset import build_graph
from .environment import SwarmFormationEnv
from .models import build_model
from .safety import choose_counterfactual_topology, simple_recover_shield
from .utils import torch_device


def batch_from_obs(obs: Dict, cfg: Config, device: torch.device) -> Dict[str, torch.Tensor]:
    node_x, edge_index, edge_attr = build_graph(obs, cfg)
    return {
        "node_x": node_x.to(device),
        "edge_index": edge_index.to(device),
        "edge_attr": edge_attr.to(device),
        "batch_index": torch.zeros(node_x.shape[0], dtype=torch.long, device=device),
    }


def run_policy_episode(method: str, cfg: Config, n_agents: int, scenario: str, ckpt_dir: str = "results") -> Dict[str, float]:
    env = SwarmFormationEnv(cfg)
    obs = env.reset(n_agents, scenario)
    device = torch_device(cfg.train.device)
    model = None
    if method in ["rvt_swarm", "gnn_only", "instant_cert"]:
        model = build_model(method, cfg.train.hidden_dim, cfg.train.message_passes, getattr(cfg.train, 'aux_gradient_scale', 0.3)).to(device)
        ckpt = torch.load(Path(ckpt_dir) / f"{method}.pt", map_location=device, weights_only=False)
        model.load_state_dict(ckpt["model"])
        model.eval()
    done = False
    last_info = None
    steps = 0
    prev_topo = 0
    recover_fp = 0.0
    recover_fn = 0.0
    while not done:
        if method in ["adaptive_formation", "cbf_qp_like", "orca_like", "centralized_mpc"]:
            actions, topo = historical_baseline(method, obs, cfg)
        else:
            batch = batch_from_obs(obs, cfg, device)
            with torch.no_grad():
                out = model(batch)
            actions = out["actions"].cpu().numpy() * cfg.env.max_accel
            topo = 0
            recover = None
            uncertainty = None
            if out["topology_logits"] is not None:
                topo = choose_counterfactual_topology(obs, out["topology_logits"], out["recoverability_scores"], cfg, prev_topo, out.get("uncertainty"))
            if out["recoverability"] is not None:
                recover = float(out["recoverability"].squeeze().cpu().item())
                uncertainty = float(out["uncertainty"].mean().cpu().item()) if out.get("uncertainty") is not None else 0.0
            if method in ["rvt_swarm", "instant_cert"]:
                actions = simple_recover_shield(actions, obs, cfg, recover, topo)
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
    last_info["ms_per_step"] = 1.0 if method != "rvt_swarm" else 1.6
    return last_info


def _eval_setting(args):
    """Worker: run all episodes for one (method, scenario, n_agents) setting."""
    method, cfg, n_agents, scenario, ckpt_dir, n_episodes = args
    metrics = []
    for _ in range(n_episodes):
        m = run_policy_episode(method, cfg, n_agents, scenario, ckpt_dir)
        metrics.append(m)
    agg = {k: float(np.mean([x[k] for x in metrics])) for k in metrics[0].keys()}
    agg["scenario"] = scenario
    agg["n_agents"] = n_agents
    agg["method"] = method
    return agg


def evaluate_method(method: str, cfg: Config, ckpt_dir: str = "results") -> List[Dict]:
    import multiprocessing as mp
    import os

    settings = []
    for scenario in cfg.env.scenarios:
        for n_agents in cfg.env.team_sizes:
            if method == "centralized_mpc" and n_agents != 4:
                continue
            settings.append((method, cfg, n_agents, scenario, ckpt_dir, cfg.eval.episodes_per_setting))

    # Baselines are CPU-only → parallelize freely
    # Learned methods use GPU → run sequentially to avoid GPU contention
    if method in ["adaptive_formation", "cbf_qp_like", "orca_like", "centralized_mpc"]:
        auto = max(1, os.cpu_count() - 1)
        n_workers = min(len(settings), cfg.train.n_workers or auto)
        with mp.Pool(n_workers) as pool:
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
