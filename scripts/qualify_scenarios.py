"""Task 5 — oracle-based scenario qualification. NO LEARNED MODEL IS USED.

Validation layouts only. Rollout outcomes decide every label; the geometric
feasibility hypotheses in `layouts.py` are never consulted here.
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
from rvt_swarm.metrics import EpisodeAccumulator  # noqa: E402
from rvt_swarm.recoverability import clone_env  # noqa: E402
from rvt_swarm.splits import VALIDATION, setting_episode_seeds  # noqa: E402
from rvt_swarm.train import git_commit  # noqa: E402

OUT = REPO / "results" / "scenario_headroom"
TAG = "method-audit-v2-complete"
MODE_NAME = {0: "keep", 2: "line", 3: "split"}

# --- Recovery event (predeclared; see RECOVERY_EVENT_SPECIFICATION.md) --------
H = 14
L_DWELL = 3
MIN_PROGRESS = 0.02
N_ROLLOUTS = 4
PERTURB_POS = 0.02
PERTURB_ACC = 0.03
ROLLOUT_SEED = 20_250_730

TEAM_SIZES = [4, 6]
EPISODES = 4
STATE_STRIDE = 10


def recovery_event(env, topo, cfg, rng, H=H, tube_scale=1.0, L=L_DWELL, min_prog=MIN_PROGRESS):
    sim = clone_env(env, cfg)
    sim.state.positions = sim.state.positions + rng.normal(
        0, PERTURB_POS, sim.state.positions.shape).astype(np.float32)
    obs = sim.observe()
    p0 = float(obs["progress"])
    tol = cfg.env.formation_tolerance * tube_scale
    run = best = 0
    for _ in range(H):
        a = expert_action(obs, cfg, topo) + rng.normal(0, PERTURB_ACC, (sim.n_agents, 2)).astype(np.float32)
        obs, _, done, info = sim.step(a, topo)
        if info["rr_collision"] > 0 or info["ro_collision"] > 0:
            return 0
        if info["deadlock"] > 0.5 or info["irreversible_collapse"] > 0.5:
            return 0
        run = run + 1 if info["form_rms"] < tol else 0
        best = max(best, run)
        if done:
            break
    return int((float(obs["progress"]) - p0) >= min_prog and best >= L)


def fixed_mode_episode(cfg, n, layout, seed, mode):
    """Run a whole episode with the mode pinned."""
    env = SwarmFormationEnv(cfg)
    obs = env.reset(n, "cluttered", seed=seed, layout=layout)
    acc = EpisodeAccumulator(formation_tolerance=cfg.env.formation_tolerance, dt=cfg.env.dt)
    done, last = False, None
    while not done:
        obs, _, done, last = env.step(expert_action(obs, cfg, mode), mode)
        acc.update(last)
    return acc.finalize(last)


def oracle_episode(cfg, n, layout, seed, rng, replan_every=10):
    """Per-decision rollout oracle: re-choose the mode from rollout outcomes.

    ORACLE UPPER BOUND -- it clones the simulator and looks ahead. Never a
    deployable competitor.
    """
    env = SwarmFormationEnv(cfg)
    obs = env.reset(n, "cluttered", seed=seed, layout=layout)
    acc = EpisodeAccumulator(formation_tolerance=cfg.env.formation_tolerance, dt=cfg.env.dt)
    done, last, step, mode, switches = False, None, 0, 0, 0
    while not done:
        if step % replan_every == 0:
            rates = [np.mean([recovery_event(env, t, cfg, rng) for _ in range(N_ROLLOUTS)])
                     for t in LEARNED_TOPOLOGY_IDS]
            new = LEARNED_TOPOLOGY_IDS[int(np.argmax(rates))]
            if new != mode:
                switches += 1
            mode = new
        obs, _, done, last = env.step(expert_action(obs, cfg, mode), mode)
        acc.update(last)
        step += 1
    out = acc.finalize(last)
    out["oracle_switches"] = switches
    return out


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    cfg = Config()
    cfg.train.device = "cpu"
    rng = np.random.default_rng(ROLLOUT_SEED)
    layouts = build_layouts("val")
    print(f"commit={git_commit()} tag={TAG}")
    print(f"VALIDATION layouts only: {len(layouts)}; team sizes {TEAM_SIZES}; "
          f"{EPISODES} episodes each")

    state_rows, ep_rows = [], []
    for lay in layouts:
        for n in TEAM_SIZES:
            seeds = setting_episode_seeds(VALIDATION, 0, n, EPISODES, 0)
            # ---- per-state oracle scores ----
            for seed in seeds[:2]:
                env = SwarmFormationEnv(cfg)
                obs = env.reset(n, "cluttered", seed=seed, layout=lay)
                done, step = False, 0
                while not done:
                    if step % STATE_STRIDE == 0:
                        rates = {}
                        for t in LEARNED_TOPOLOGY_IDS:
                            rates[t] = float(np.mean(
                                [recovery_event(env, t, cfg, rng) for _ in range(N_ROLLOUTS)]))
                        vals = np.array([rates[t] for t in LEARNED_TOPOLOGY_IDS])
                        order = np.argsort(-vals)
                        best_i = int(order[0])
                        # tie-break toward keep (index 0) when tied with the max
                        if vals[0] == vals[best_i]:
                            best_i = 0
                        keep_r = float(vals[0])
                        best_r = float(vals[best_i])
                        second = float(np.sort(vals)[-2])
                        qualified = int(best_r >= 0.5 and len(set(vals.tolist())) > 1)
                        state_rows.append({
                            "benchmark_tag": TAG, "git_commit": git_commit(),
                            "layout_id": lay.layout_id, "family": lay.family,
                            "team_size": n, "episode_seed": seed, "step": step,
                            **{f"R_{MODE_NAME[t]}": rates[t] for t in LEARNED_TOPOLOGY_IDS},
                            "best_mode": MODE_NAME[LEARNED_TOPOLOGY_IDS[best_i]],
                            "mode_margin": best_r - second,
                            "keep_regret": best_r - keep_r,
                            "mode_necessity": int(keep_r < 0.5 <= best_r),
                            "qualified": qualified,
                        })
                    obs, _, done, _ = env.step(expert_action(obs, cfg, 0), 0)
                    step += 1
            # ---- per-episode fixed-mode and oracle policies ----
            for seed in seeds:
                per_mode = {}
                for t in LEARNED_TOPOLOGY_IDS:
                    m = fixed_mode_episode(cfg, n, lay, seed, t)
                    per_mode[MODE_NAME[t]] = m
                orc = oracle_episode(cfg, n, lay, seed, rng)
                best_fixed = max(per_mode.values(), key=lambda m: (m["success"], m["goal_reached"]))
                any_fixed_success = max(m["success"] for m in per_mode.values())
                row = {
                    "benchmark_tag": TAG, "git_commit": git_commit(),
                    "layout_id": lay.layout_id, "family": lay.family,
                    "team_size": n, "episode_seed": seed,
                    "oracle_switches": orc["oracle_switches"],
                    "switch_necessity": int(orc["success"] > 0.5 and any_fixed_success < 0.5),
                    "best_fixed_success": float(best_fixed["success"]),
                }
                for name, m in per_mode.items():
                    for k in ["success", "collision_free", "goal_reached", "deadlock",
                              "irreversible_collapse", "time_in_formation_tube",
                              "completion_time"]:
                        row[f"{name}_{k}"] = float(m[k])
                for k in ["success", "collision_free", "goal_reached", "deadlock",
                          "irreversible_collapse", "time_in_formation_tube", "completion_time"]:
                    row[f"oracle_{k}"] = float(orc[k])
                ep_rows.append(row)
        print(f"  {lay.layout_id:28s} states={len(state_rows):5d} episodes={len(ep_rows):4d}",
              flush=True)

    # ---- summary per family ----
    summary = []
    fams = sorted({r["family"] for r in state_rows})
    for fam in fams:
        s = [r for r in state_rows if r["family"] == fam]
        q = [r for r in s if r["qualified"]]
        e = [r for r in ep_rows if r["family"] == fam]
        dist = Counter(r["best_mode"] for r in q)
        n_q = max(len(q), 1)
        summary.append({
            "benchmark_tag": TAG, "family": fam,
            "states": len(s), "qualified_states": len(q),
            "qualified_fraction": len(q) / max(len(s), 1),
            "best_keep_frac": dist.get("keep", 0) / n_q,
            "best_line_frac": dist.get("line", 0) / n_q,
            "best_split_frac": dist.get("split", 0) / n_q,
            "selector_headroom": float(np.mean([r["keep_regret"] for r in q])) if q else 0.0,
            "median_mode_margin": float(np.median([r["mode_margin"] for r in q])) if q else 0.0,
            "mode_necessity": float(np.mean([r["mode_necessity"] for r in q])) if q else 0.0,
            "episodes": len(e),
            "keep_success": float(np.mean([r["keep_success"] for r in e])),
            "line_success": float(np.mean([r["line_success"] for r in e])),
            "split_success": float(np.mean([r["split_success"] for r in e])),
            "best_fixed_success": float(np.mean([r["best_fixed_success"] for r in e])),
            "oracle_success": float(np.mean([r["oracle_success"] for r in e])),
            "oracle_advantage": float(np.mean([r["oracle_success"] for r in e])
                                      - np.mean([r["keep_success"] for r in e])),
            "switch_necessity": float(np.mean([r["switch_necessity"] for r in e])),
            "mean_oracle_switches": float(np.mean([r["oracle_switches"] for r in e])),
        })

    for name, rows in [("per_state_scores.csv", state_rows), ("per_episode.csv", ep_rows),
                       ("summary.csv", summary)]:
        keys = sorted({k for r in rows for k in r})
        with (OUT / name).open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=keys)
            w.writeheader(); w.writerows(rows)
        print(f"wrote {OUT/name} ({len(rows)} rows)")

    print(f"\n{'family':20s}{'qual':>6s}{'keep':>7s}{'line':>7s}{'split':>7s}"
          f"{'headrm':>8s}{'margin':>8s}{'necess':>8s}{'keepS':>7s}{'oracS':>7s}{'oracAdv':>9s}{'swNec':>7s}")
    for r in summary:
        print(f"{r['family']:20s}{r['qualified_states']:6d}{r['best_keep_frac']:7.3f}"
              f"{r['best_line_frac']:7.3f}{r['best_split_frac']:7.3f}{r['selector_headroom']:8.3f}"
              f"{r['median_mode_margin']:8.3f}{r['mode_necessity']:8.3f}{r['keep_success']:7.3f}"
              f"{r['oracle_success']:7.3f}{r['oracle_advantage']:9.3f}{r['switch_necessity']:7.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
