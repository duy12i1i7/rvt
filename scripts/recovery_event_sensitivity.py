"""Task 7 — recovery-event parameter sensitivity. Validation layouts only.

Grid and selection rule are fixed in docs/RECOVERY_EVENT_SPECIFICATION.md before
this script runs. No learned model is involved.
"""
from __future__ import annotations

import csv
import sys
from collections import Counter
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from rvt_swarm.config import Config, LEARNED_TOPOLOGY_IDS  # noqa: E402
from rvt_swarm.controllers import expert_action  # noqa: E402
from rvt_swarm.environment import SwarmFormationEnv  # noqa: E402
from rvt_swarm.layouts import build_layouts  # noqa: E402
from rvt_swarm.splits import VALIDATION, setting_episode_seeds  # noqa: E402
from rvt_swarm.train import git_commit  # noqa: E402
from scripts.qualify_scenarios import recovery_event  # noqa: E402

OUT = REPO / "results" / "scenario_headroom"
TAG = "method-audit-v2-complete"
MODE_NAME = {0: "keep", 2: "line", 3: "split"}
ROLLOUT_SEED = 20_250_731

# Predeclared grid (one axis moved at a time from the default).
DEFAULT = dict(H=14, tube_scale=1.0, L=3, min_prog=0.02)
GRID = [DEFAULT] + [
    {**DEFAULT, "H": 7}, {**DEFAULT, "H": 28},
    {**DEFAULT, "tube_scale": 0.75}, {**DEFAULT, "tube_scale": 1.5},
    {**DEFAULT, "L": 1}, {**DEFAULT, "L": 5},
    {**DEFAULT, "min_prog": 0.01}, {**DEFAULT, "min_prog": 0.05},
]
TEAM_SIZES = [4, 6]
EPISODES = 2
STATE_STRIDE = 20
N_ROLLOUTS = 4


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    cfg = Config()
    layouts = build_layouts("val")
    print(f"commit={git_commit()} tag={TAG} | {len(GRID)} grid points, validation layouts only")

    # Collect the states once, then re-label them under every grid point.
    states = []
    for lay in layouts:
        for n in TEAM_SIZES:
            for seed in setting_episode_seeds(VALIDATION, 0, n, EPISODES, 0):
                env = SwarmFormationEnv(cfg)
                obs = env.reset(n, "cluttered", seed=seed, layout=lay)
                done, step = False, 0
                while not done:
                    if step % STATE_STRIDE == 0:
                        snap = SwarmFormationEnv(cfg)
                        snap.n_agents = env.n_agents
                        from dataclasses import replace
                        snap.state = replace(
                            env.state,
                            positions=env.state.positions.copy(),
                            velocities=env.state.velocities.copy(),
                            goal=env.state.goal.copy(),
                            obstacles=env.state.obstacles.copy(),
                            obstacle_velocities=env.state.obstacle_velocities.copy(),
                            corridor_direction=env.state.corridor_direction.copy(),
                            subteam_ids=env.state.subteam_ids.copy(),
                        )
                        states.append((lay.family, lay.layout_id, n, snap))
                    obs, _, done, _ = env.step(expert_action(obs, cfg, 0), 0)
                    step += 1
    print(f"collected {len(states)} validation states")

    rows, labels_by_point = [], {}
    for gi, params in enumerate(GRID):
        rng = np.random.default_rng(ROLLOUT_SEED)
        labels, by_family, by_mode, nonuniform = {}, {}, {}, 0
        for si, (fam, lid, n, snap) in enumerate(states):
            per_mode = {}
            for t in LEARNED_TOPOLOGY_IDS:
                r = np.mean([recovery_event(snap, t, cfg, rng, H=params["H"],
                                            tube_scale=params["tube_scale"],
                                            L=params["L"], min_prog=params["min_prog"])
                             for _ in range(N_ROLLOUTS)])
                lab = int(r >= 0.5)
                per_mode[t] = lab
                labels[(si, t)] = lab
                by_mode.setdefault(MODE_NAME[t], []).append(lab)
                by_family.setdefault(fam, []).append(lab)
            if len(set(per_mode.values())) > 1:
                nonuniform += 1
        labels_by_point[gi] = labels
        pooled = float(np.mean(list(labels.values())))
        flips = (float(np.mean([labels[k] != labels_by_point[0][k] for k in labels]))
                 if gi > 0 else 0.0)
        row = {"benchmark_tag": TAG, "git_commit": git_commit(), "grid_point": gi,
               "is_default": int(gi == 0), **params,
               "states": len(states), "positive_rate": pooled,
               "label_flip_fraction_vs_default": flips,
               "label_stability_vs_default": 1.0 - flips,
               "nonuniform_state_fraction": nonuniform / max(len(states), 1)}
        for m, v in by_mode.items():
            row[f"positive_rate_{m}"] = float(np.mean(v))
        for f, v in by_family.items():
            row[f"positive_rate_family_{f}"] = float(np.mean(v))
        rows.append(row)
        print(f"  H={params['H']:2d} tube={params['tube_scale']:.2f} L={params['L']} "
              f"prog={params['min_prog']:.2f} -> pos={pooled:.3f} "
              f"stability={1-flips:.3f} nonuniform={nonuniform/max(len(states),1):.3f}",
              flush=True)

    keys = sorted({k for r in rows for k in r})
    with (OUT / "recovery_event_sensitivity.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader(); w.writerows(rows)
    print(f"\nwrote {OUT/'recovery_event_sensitivity.csv'}")

    d = rows[0]
    print("\nSelection rule check on the DEFAULT point:")
    print(f"  S1 not too easy  (<=0.85): {d['positive_rate']:.3f} "
          f"{'PASS' if d['positive_rate'] <= 0.85 else 'FAIL'}")
    print(f"  S2 not too rare  (>=0.15): {d['positive_rate']:.3f} "
          f"{'PASS' if d['positive_rate'] >= 0.15 else 'FAIL'}")
    worst = min(r["label_stability_vs_default"] for r in rows[1:])
    print(f"  S3 stability     (>=0.80): worst={worst:.3f} {'PASS' if worst >= 0.80 else 'FAIL'}")
    print(f"  S4 discriminative(>=0.20): {d['nonuniform_state_fraction']:.3f} "
          f"{'PASS' if d['nonuniform_state_fraction'] >= 0.20 else 'FAIL'}")
    inf = d.get("positive_rate_family_infeasible")
    if inf is not None:
        print(f"  S5 infeasible    (<=0.05): {inf:.3f} {'PASS' if inf <= 0.05 else 'FAIL'}")
    return 0


if __name__ == "__main__":
    main()
