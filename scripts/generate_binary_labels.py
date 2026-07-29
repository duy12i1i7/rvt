"""Task 3 — Recovery Event V2 task-recovery labels for keep and line.

Train and validation layouts only. Final-test layouts are NOT loaded.
No learned model is involved. The shaped rollout utility is not used.
"""
from __future__ import annotations

import csv
import sys
from collections import Counter
from dataclasses import replace
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from rvt_swarm.config import Config  # noqa: E402
from rvt_swarm.controllers import expert_action  # noqa: E402
from rvt_swarm.environment import SwarmFormationEnv  # noqa: E402
from rvt_swarm.layouts import build_layouts  # noqa: E402
from rvt_swarm.provenance import stamp  # noqa: E402
from rvt_swarm.recovery_v2 import evaluate_modes  # noqa: E402
from rvt_swarm.regions import regions_for_layout  # noqa: E402
from rvt_swarm.splits import TRAIN, VALIDATION, setting_episode_seeds  # noqa: E402

OUT = REPO / "results" / "binary_mode_pilot"
MODES = {0: "keep", 2: "line"}                 # split REMOVED
PILOT_FAMILIES = ["line_corridor", "keep_line_keep", "keep_open", "ambiguous"]
TEAM_SIZES = [4, 6]
H_COMMIT, T_MAX, DWELL_L, TUBE = 10, 120, 3, 1.0
N_ROLLOUTS = 4
ROLLOUT_SEED = 20_250_901
STATE_STRIDE = 12
EPISODES = {"train": 3, "val": 2}


def snapshot(env, cfg):
    s = SwarmFormationEnv(cfg)
    s.n_agents = env.n_agents
    s.state = replace(env.state,
                      positions=env.state.positions.copy(),
                      velocities=env.state.velocities.copy(),
                      goal=env.state.goal.copy(),
                      obstacles=env.state.obstacles.copy(),
                      obstacle_velocities=env.state.obstacle_velocities.copy(),
                      corridor_direction=env.state.corridor_direction.copy(),
                      subteam_ids=env.state.subteam_ids.copy())
    return s


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    cfg = Config(); cfg.train.device = "cpu"
    prov = stamp()
    print(f"provenance: {prov['source_commit'][:8]} layout_hash={prov['layout_split_hash']}")
    rng = np.random.default_rng(ROLLOUT_SEED)
    rows = []

    for split, split_key in (("train", TRAIN), ("val", VALIDATION)):
        layouts = [l for l in build_layouts(split) if l.family in PILOT_FAMILIES]
        for lay in layouts:
            reg = regions_for_layout(lay, cfg)
            for n in TEAM_SIZES:
                for seed in setting_episode_seeds(split_key, 0, n, EPISODES[split], 0):
                    env = SwarmFormationEnv(cfg)
                    obs = env.reset(n, "cluttered", seed=seed, layout=lay)
                    done, step = False, 0
                    while not done:
                        if step % STATE_STRIDE == 0:
                            snap = snapshot(env, cfg)
                            recs = evaluate_modes(
                                snap, list(MODES), cfg, reg, rng, n_rollouts=N_ROLLOUTS,
                                h_commit=H_COMMIT, t_max=T_MAX, dwell_L=DWELL_L,
                                tube_scale=TUBE)
                            for m, rs in recs.items():
                                p = float(np.mean([r.task_recovery for r in rs]))
                                rows.append({
                                    **prov,
                                    "state_id": f"{lay.layout_id}|{n}|{seed}|{step}",
                                    "layout_id": lay.layout_id, "family": lay.family,
                                    "split": split, "team_size": n, "episode_seed": seed,
                                    "step": step, "mode": MODES[m],
                                    "task_recovery_label": int(p >= 0.5),
                                    "empirical_recovery_probability": p,
                                    "formation_recovery_label": int(
                                        np.mean([r.formation_recovery for r in rs]) >= 0.5),
                                    "local_progress_label": int(
                                        np.mean([r.local_progress for r in rs]) >= 0.5),
                                    "collision_outcome": float(np.mean(
                                        [(r.rr_collision_steps + r.ro_collision_steps) > 0
                                         for r in rs])),
                                    "deadlock": float(np.mean([r.deadlock for r in rs])),
                                    "irreversible_collapse": float(np.mean(
                                        [r.irreversible_collapse for r in rs])),
                                    "goal_completion": float(np.mean(
                                        [r.task_completed for r in rs])),
                                    "rollout_seed": ROLLOUT_SEED,
                                    "h_commit": H_COMMIT, "t_max": T_MAX,
                                    "n_rollouts": N_ROLLOUTS,
                                })
                        obs, _, done, _ = env.step(expert_action(obs, cfg, 0), 0)
                        step += 1
            print(f"  {lay.layout_id:28s} rows={len(rows)}", flush=True)

    with (OUT / "task_recovery_labels.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=sorted({k for r in rows for k in r}))
        w.writeheader(); w.writerows(rows)

    # ---- label statistics, reported separately per the task ----------------
    stats = []
    def add(scope, key, sub):
        if not sub:
            return
        for mode in ("keep", "line"):
            ms = [r for r in sub if r["mode"] == mode]
            if not ms:
                continue
            stats.append({**prov, "scope": scope, "key": key, "mode": mode,
                          "n": len(ms),
                          "positive_rate": float(np.mean([r["task_recovery_label"] for r in ms])),
                          "mean_empirical_probability": float(np.mean(
                              [r["empirical_recovery_probability"] for r in ms])),
                          "formation_recovery_rate": float(np.mean(
                              [r["formation_recovery_label"] for r in ms])),
                          "goal_completion_rate": float(np.mean([r["goal_completion"] for r in ms]))})
    add("overall", "all", rows)
    for f in sorted({r["family"] for r in rows}):
        add("family", f, [r for r in rows if r["family"] == f])
    for n in TEAM_SIZES:
        add("team_size", str(n), [r for r in rows if r["team_size"] == n])
    for s in ("train", "val"):
        add("split", s, [r for r in rows if r["split"] == s])

    with (OUT / "label_statistics.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=sorted({k for r in stats for k in r}))
        w.writeheader(); w.writerows(stats)

    print(f"\nwrote {OUT/'task_recovery_labels.csv'} ({len(rows)} rows)")
    print(f"{'scope':10s}{'key':18s}{'mode':6s}{'n':>6s}{'pos_rate':>10s}{'mean_p':>9s}")
    for s in stats:
        print(f"{s['scope']:10s}{s['key']:18s}{s['mode']:6s}{s['n']:6d}"
              f"{s['positive_rate']:10.3f}{s['mean_empirical_probability']:9.3f}")

    # ---- degeneracy check --------------------------------------------------
    degenerate = [s for s in stats if s["scope"] == "overall"
                  and (s["positive_rate"] <= 0.05 or s["positive_rate"] >= 0.95)]
    if degenerate:
        print("\n*** DEGENERATE LABELS -- STOP BEFORE TRAINING ***")
        for s in degenerate:
            print(f"    {s['mode']}: positive rate {s['positive_rate']:.3f}")
        return 1
    print("\nLabel balance acceptable; no degenerate mode.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
