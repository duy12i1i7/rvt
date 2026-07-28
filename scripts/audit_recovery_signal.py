"""Task 5 — is the learned score predictive of a realised recovery event?

The quantity is called "score" throughout, never "recoverability": the point of
this pilot is to decide whether that word is earned.

VALIDATION STATES ONLY. A separate rollout seed is used for the perturbations.
"""
from __future__ import annotations

import csv
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import torch

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from rvt_swarm.config import Config, LEARNED_TOPOLOGY_IDS  # noqa: E402
from rvt_swarm.controllers import expert_action  # noqa: E402
from rvt_swarm.dataset import build_graph  # noqa: E402
from rvt_swarm.environment import SwarmFormationEnv  # noqa: E402
from rvt_swarm.policy_runtime import load_learned_model  # noqa: E402
from rvt_swarm.recoverability import rollout_score  # noqa: E402
from rvt_swarm.safety import collision_risk  # noqa: E402
from rvt_swarm.splits import VALIDATION, setting_episode_seeds  # noqa: E402
from rvt_swarm.train import git_commit  # noqa: E402
from rvt_swarm.utils import torch_device  # noqa: E402

OUT = REPO / "results" / "method_audit"
CKPT = REPO / "checkpoints" / "method_audit"
TAG = "benchmark-protocol-v2-smoke"

# ---- PREDECLARED recovery event, fixed before running -----------------------
HORIZON_H = 14          # same horizon the training labels use
TUBE_DWELL_L = 3        # must stay in the tube at least L steps
MIN_PROGRESS = 0.02     # normalised centroid progress over the horizon
N_ROLLOUTS = 4          # perturbed rollouts per (state, mode)
PERTURB_POS = 0.02      # m, initial-state perturbation
PERTURB_ACC = 0.03      # m/s^2, control noise
ROLLOUT_SEED = 20_250_729   # dedicated stream, distinct from every split seed

VAL_SCENARIOS = ["open_field", "narrow_passage"]
VAL_TEAM_SIZES = [5, 11]
EPISODES = 6
STATE_STRIDE = 8        # sample every k-th step of each validation episode


def recovery_event(env: SwarmFormationEnv, topo: int, cfg: Config, rng) -> int:
    """Binary horizon-H recovery outcome for one perturbed rollout.

    Recovered iff, over H steps: no robot-robot collision, no robot-obstacle
    collision, >= MIN_PROGRESS progress, entry into the topology-conditioned
    formation tube, remaining there >= L steps, no deadlock, no collapse.
    """
    from rvt_swarm.recoverability import clone_env

    sim = clone_env(env, cfg)
    sim.state.positions = sim.state.positions + rng.normal(0, PERTURB_POS, sim.state.positions.shape).astype(np.float32)
    obs = sim.observe()
    p0 = float(obs["progress"])
    tube_run = tube_best = 0
    for _ in range(HORIZON_H):
        a = expert_action(obs, cfg, topo)
        a = a + rng.normal(0, PERTURB_ACC, a.shape).astype(np.float32)
        obs, _, done, info = sim.step(a, topo)
        if info["rr_collision"] > 0 or info["ro_collision"] > 0:
            return 0
        if info["deadlock"] > 0.5 or info["irreversible_collapse"] > 0.5:
            return 0
        tube_run = tube_run + 1 if info["form_ok"] > 0.5 else 0
        tube_best = max(tube_best, tube_run)
        if done:
            break
    progress = float(obs["progress"]) - p0
    return int(progress >= MIN_PROGRESS and tube_best >= TUBE_DWELL_L)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    if not (CKPT / "rvt_swarm.pt").exists():
        print(f"ERROR: no audit checkpoint at {CKPT}/rvt_swarm.pt")
        return 1
    cfg = Config()
    cfg.train.device = "cpu"
    cfg.env.scenarios = VAL_SCENARIOS
    model = load_learned_model("rvt_swarm", cfg, str(CKPT), torch_device("cpu"))
    rng = np.random.default_rng(ROLLOUT_SEED)
    print(f"commit={git_commit()} tag={TAG}")
    print(f"recovery event: H={HORIZON_H} L={TUBE_DWELL_L} min_progress={MIN_PROGRESS} "
          f"rollouts={N_ROLLOUTS} perturb=({PERTURB_POS} m, {PERTURB_ACC} m/s^2) "
          f"rollout_seed={ROLLOUT_SEED}")

    rows = []
    for si, scenario in enumerate(VAL_SCENARIOS):
        for n in VAL_TEAM_SIZES:
            for seed in setting_episode_seeds(VALIDATION, si, n, EPISODES, 0):
                env = SwarmFormationEnv(cfg)
                obs = env.reset(n, scenario, seed=seed)
                done, step = False, 0
                while not done:
                    if step % STATE_STRIDE == 0:
                        node_x, ei, ea = build_graph(obs, cfg)
                        batch = {"node_x": node_x, "edge_index": ei, "edge_attr": ea,
                                 "batch_index": torch.zeros(node_x.shape[0], dtype=torch.long)}
                        with torch.no_grad():
                            out = model(batch)
                        adj = out["recoverability_scores"].squeeze(0).numpy()
                        raw = out["raw_recoverability_scores"].squeeze(0).numpy()
                        logits = out["topology_logits"].squeeze(0).numpy()
                        unc = out["uncertainty"].squeeze(0).numpy()
                        risk = collision_risk(obs, cfg)
                        d_goal = float(np.linalg.norm(obs["goal"] - obs["positions"].mean(axis=0)))
                        form_err = float(np.sqrt(np.mean(np.sum(obs["formation_error"] ** 2, axis=1))))
                        pos = obs["positions"]
                        dd = np.linalg.norm(pos[:, None] - pos[None, :], axis=-1)
                        np.fill_diagonal(dd, np.inf)
                        min_clear = float(dd.min())
                        for k, topo in enumerate(LEARNED_TOPOLOGY_IDS):
                            outcomes = [recovery_event(env, topo, cfg, rng)
                                        for _ in range(N_ROLLOUTS)]
                            rows.append({
                                "scenario": scenario, "team_size": n, "episode_seed": seed,
                                "step": step, "topology": topo,
                                "score_adjusted": float(adj[k]), "score_raw": float(raw[k]),
                                "uncertainty": float(unc[k]), "topology_logit": float(logits[k]),
                                "rollout_utility": float(rollout_score(env, topo, HORIZON_H, cfg)),
                                "min_clearance": min_clear, "formation_error": form_err,
                                "distance_to_goal": d_goal, "instantaneous_risk": float(risk),
                                "empirical_recovery_rate": float(np.mean(outcomes)),
                                "recovered": int(np.mean(outcomes) >= 0.5),
                                "n_rollouts": N_ROLLOUTS,
                            })
                    a = expert_action(obs, cfg, 0)
                    obs, _, done, _ = env.step(a, 0)
                    step += 1
                print(f"  {scenario:16s} N={n:2d} seed={seed} -> {len(rows)} rows", flush=True)

    keys = sorted(rows[0])
    with (OUT / "recovery_signal_predictions.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["benchmark_tag", "git_commit"] + keys)
        w.writeheader()
        for r in rows:
            w.writerow({"benchmark_tag": TAG, "git_commit": git_commit(), **r})
    print(f"\nwrote {OUT/'recovery_signal_predictions.csv'} "
          f"({len(rows)} rows, {len(rows)//len(LEARNED_TOPOLOGY_IDS)} states)")
    print(f"positive rate: {np.mean([r['recovered'] for r in rows]):.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
