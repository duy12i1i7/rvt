"""Tasks 6, 7 and 9 — sensitivity, surrogate evaluation, and headroom re-qualification.

Training and validation layouts only. No learned model is trained or evaluated.
All grids and gates are predeclared in the accompanying docs.
"""
from __future__ import annotations

import csv
import sys
from collections import Counter
from itertools import product
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from rvt_swarm.config import Config, LEARNED_TOPOLOGY_IDS  # noqa: E402
from rvt_swarm.controllers import expert_action  # noqa: E402
from rvt_swarm.environment import SwarmFormationEnv  # noqa: E402
from rvt_swarm.layouts import build_layouts  # noqa: E402
from rvt_swarm.metrics import EpisodeAccumulator  # noqa: E402
from rvt_swarm.recoverability import rollout_score  # noqa: E402
from rvt_swarm.recovery_v2 import CONTINUATION_MODE, evaluate_modes, rollout  # noqa: E402
from rvt_swarm.regions import regions_for_layout  # noqa: E402
from rvt_swarm.safety import collision_risk  # noqa: E402
from rvt_swarm.splits import VALIDATION, setting_episode_seeds  # noqa: E402
from rvt_swarm.train import git_commit  # noqa: E402

OUT_SENS = REPO / "results" / "recovery_event_v2"
OUT_HEAD = REPO / "results" / "scenario_headroom_v2"
TAG = "scenario-headroom-v1-invalid-recovery-label"
MODE_NAME = {0: "keep", 2: "line", 3: "split"}
ROLLOUT_SEED = 20_250_801

DEFAULT = dict(h_commit=10, t_max=120, tube_scale=1.0, dwell_L=3, perturb_pos=0.02)
GRID = [DEFAULT] + [
    {**DEFAULT, "h_commit": 5}, {**DEFAULT, "h_commit": 20},
    {**DEFAULT, "t_max": 60}, {**DEFAULT, "t_max": 240},
    {**DEFAULT, "tube_scale": 0.75}, {**DEFAULT, "tube_scale": 1.5},
    {**DEFAULT, "dwell_L": 1}, {**DEFAULT, "dwell_L": 5},
    {**DEFAULT, "perturb_pos": 0.05},
]
TEAM_SIZES = [4, 6]
N_ROLLOUTS = 3
STATE_STRIDE = 25
EPISODES_STATES = 1
EPISODES_POLICY = 3


def kappa(a, b):
    a, b = np.asarray(a), np.asarray(b)
    po = float((a == b).mean())
    pe = float(((a == 1).mean() * (b == 1).mean()) + ((a == 0).mean() * (b == 0).mean()))
    return (po - pe) / (1 - pe) if (1 - pe) > 1e-9 else 1.0


def auroc(y, s):
    y, s = np.asarray(y), np.asarray(s, float)
    if len(np.unique(y)) < 2:
        return float("nan")
    order = np.argsort(s)
    ranks = np.empty(len(s), float)
    ranks[order] = np.arange(1, len(s) + 1)
    _, inv, cnt = np.unique(s, return_inverse=True, return_counts=True)
    sums = np.zeros(len(cnt)); np.add.at(sums, inv, ranks)
    ranks = (sums / cnt)[inv]
    n1, n0 = y.sum(), len(y) - y.sum()
    return float((ranks[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)) if n1 and n0 else float("nan")


def auprc(y, s):
    y, s = np.asarray(y), np.asarray(s, float)
    if y.sum() == 0:
        return float("nan")
    o = np.argsort(-s); y = y[o]
    tp = np.cumsum(y); prec = tp / np.arange(1, len(y) + 1); rec = tp / y.sum()
    return float(np.sum(np.diff(np.concatenate([[0], rec])) * prec))


def ece(y, p, bins=10):
    y, p = np.asarray(y, float), np.clip(np.asarray(p, float), 0, 1)
    e = np.quantile(p, np.linspace(0, 1, bins + 1)); e[0], e[-1] = -np.inf, np.inf
    return float(sum(((p > e[i]) & (p <= e[i + 1])).mean()
                     * abs(y[(p > e[i]) & (p <= e[i + 1])].mean() - p[(p > e[i]) & (p <= e[i + 1])].mean())
                     for i in range(bins) if ((p > e[i]) & (p <= e[i + 1])).sum()))


def collect_states(cfg, split="val"):
    """Sampled decision states with their surrogate features, from validation layouts."""
    from dataclasses import replace
    states = []
    for lay in build_layouts(split):
        reg = regions_for_layout(lay, cfg)
        for n in TEAM_SIZES:
            for seed in setting_episode_seeds(VALIDATION, 0, n, EPISODES_STATES, 0):
                env = SwarmFormationEnv(cfg)
                obs = env.reset(n, "cluttered", seed=seed, layout=lay)
                done, step = False, 0
                while not done:
                    if step % STATE_STRIDE == 0:
                        snap = SwarmFormationEnv(cfg); snap.n_agents = env.n_agents
                        snap.state = replace(
                            env.state,
                            positions=env.state.positions.copy(),
                            velocities=env.state.velocities.copy(),
                            goal=env.state.goal.copy(),
                            obstacles=env.state.obstacles.copy(),
                            obstacle_velocities=env.state.obstacle_velocities.copy(),
                            corridor_direction=env.state.corridor_direction.copy(),
                            subteam_ids=env.state.subteam_ids.copy())
                        pos = obs["positions"]
                        d = np.linalg.norm(pos[:, None] - pos[None, :], axis=-1)
                        np.fill_diagonal(d, np.inf)
                        states.append({
                            "layout_id": lay.layout_id, "family": lay.family,
                            "team_size": n, "seed": seed, "step": step,
                            "snap": snap, "regions": reg,
                            "min_clearance": float(d.min()),
                            "formation_error": float(np.sqrt(np.mean(
                                np.sum(obs["formation_error"] ** 2, axis=1)))),
                            "distance_to_goal": float(np.linalg.norm(
                                obs["goal"] - pos.mean(axis=0))),
                            "instantaneous_risk": float(collision_risk(obs, cfg)),
                        })
                    obs, _, done, _ = env.step(expert_action(obs, cfg, 0), 0)
                    step += 1
    return states


def main() -> int:
    OUT_SENS.mkdir(parents=True, exist_ok=True)
    OUT_HEAD.mkdir(parents=True, exist_ok=True)
    cfg = Config(); cfg.train.device = "cpu"
    print(f"commit={git_commit()} tag={TAG}")
    states = collect_states(cfg)
    print(f"collected {len(states)} validation decision states", flush=True)

    # ================= TASK 6 — sensitivity =================
    labels_by_point, sens_rows = {}, []
    for gi, params in enumerate(GRID):
        rng = np.random.default_rng(ROLLOUT_SEED)
        labels, by_fam, by_mode = {}, {}, {}
        for si, st in enumerate(states):
            recs = evaluate_modes(st["snap"], LEARNED_TOPOLOGY_IDS, cfg, st["regions"],
                                  rng, n_rollouts=N_ROLLOUTS, **params)
            for m, rs in recs.items():
                lab = int(np.mean([r.task_recovery for r in rs]) >= 0.5)
                labels[(si, m)] = lab
                by_fam.setdefault(st["family"], []).append(lab)
                by_mode.setdefault(MODE_NAME[m], []).append(lab)
        labels_by_point[gi] = labels
        base = labels_by_point[0]
        agree = float(np.mean([labels[k] == base[k] for k in labels]))
        kap = kappa([labels[k] for k in labels], [base[k] for k in labels]) if gi else 1.0
        row = {"benchmark_tag": TAG, "git_commit": git_commit(), "grid_point": gi,
               "is_default": int(gi == 0), **params,
               "states": len(states), "positive_rate": float(np.mean(list(labels.values()))),
               "agreement_vs_default": agree, "cohens_kappa_vs_default": kap,
               "infeasible_false_positive_rate": float(np.mean(by_fam.get("infeasible", [0]))),
               "open_field_false_negative_rate": 1.0 - float(np.mean(by_fam.get("keep_open", [1])))}
        for f, v in by_fam.items():
            row[f"prevalence_{f}"] = float(np.mean(v))
        for m, v in by_mode.items():
            row[f"prevalence_mode_{m}"] = float(np.mean(v))
        sens_rows.append(row)
        print(f"  H_c={params['h_commit']:2d} T={params['t_max']:3d} tube={params['tube_scale']:.2f} "
              f"L={params['dwell_L']} perturb={params['perturb_pos']:.2f} -> "
              f"pos={row['positive_rate']:.3f} agree={agree:.3f} kappa={kap:.3f} "
              f"infeasFP={row['infeasible_false_positive_rate']:.3f} "
              f"openFN={row['open_field_false_negative_rate']:.3f}", flush=True)

    with (OUT_SENS / "sensitivity.csv").open("w", newline="") as fh:
        keys = sorted({k for r in sens_rows for k in r})
        w = csv.DictWriter(fh, fieldnames=keys); w.writeheader(); w.writerows(sens_rows)
    print(f"wrote {OUT_SENS/'sensitivity.csv'}")

    # ================= TASK 7 — surrogates vs the gold standard =================
    rng = np.random.default_rng(ROLLOUT_SEED + 1)
    sur_rows, gold, feats = [], [], {k: [] for k in
        ["shaped_rollout_utility", "local_progress", "formation_recovery",
         "crossed_bottleneck", "min_clearance", "instantaneous_risk",
         "distance_to_goal", "formation_error", "combined_surrogate"]}
    per_state = []
    for st in states:
        recs = evaluate_modes(st["snap"], LEARNED_TOPOLOGY_IDS, cfg, st["regions"],
                              rng, n_rollouts=N_ROLLOUTS, **DEFAULT)
        entry = {"family": st["family"], "gold": {}, "sur": {}}
        for m, rs in recs.items():
            g = int(np.mean([r.task_recovery for r in rs]) >= 0.5)
            gold.append(g)
            entry["gold"][m] = g
            util = rollout_score(st["snap"], m, 14, cfg)
            lp = float(np.mean([r.local_progress for r in rs]))
            fr = float(np.mean([r.formation_recovery for r in rs]))
            cb = float(np.mean([r.crossed_bottleneck for r in rs]))
            vals = {"shaped_rollout_utility": util, "local_progress": lp,
                    "formation_recovery": fr, "crossed_bottleneck": cb,
                    "min_clearance": st["min_clearance"],
                    "instantaneous_risk": -st["instantaneous_risk"],
                    "distance_to_goal": -st["distance_to_goal"],
                    "formation_error": -st["formation_error"],
                    "combined_surrogate": 0.5 * cb + 0.3 * fr + 0.2 * lp}
            for k, v in vals.items():
                feats[k].append(v)
            entry["sur"][m] = vals
        per_state.append(entry)

    gold = np.array(gold)
    print(f"\nTASK 7 — surrogates vs full-horizon task recovery (n={len(gold)}, "
          f"positive rate {gold.mean():.3f})")
    print(f"{'surrogate':26s}{'AUROC':>8s}{'AUPRC':>8s}{'Brier':>8s}{'ECE':>8s}"
          f"{'FalseSafe':>11s}{'top1':>7s}{'pair':>7s}{'kendall':>9s}")
    for k, v in feats.items():
        s = np.array(v, float)
        z = (s - s.mean()) / max(s.std(), 1e-9); p = 1 / (1 + np.exp(-z))
        thr = np.median(s); pred = s >= thr
        fs = float((pred & (gold == 0)).sum() / max((gold == 0).sum(), 1))
        top1 = pair = pn = 0; taus = []; nq = 0
        for e in per_state:
            gm = np.array([e["gold"][m] for m in LEARNED_TOPOLOGY_IDS])
            sm = np.array([e["sur"][m][k] for m in LEARNED_TOPOLOGY_IDS])
            if gm.max() == gm.min():
                continue
            nq += 1
            top1 += int(gm[int(np.argmax(sm))] == gm.max())
            c = d = 0
            for i in range(3):
                for j in range(i + 1, 3):
                    if gm[i] != gm[j]:
                        pn += 1
                        pair += int(np.sign(sm[i] - sm[j]) == np.sign(gm[i] - gm[j]))
                        s_ = np.sign(sm[i] - sm[j]) * np.sign(gm[i] - gm[j])
                        c += s_ > 0; d += s_ < 0
            taus.append((c - d) / max(c + d, 1))
        row = {"benchmark_tag": TAG, "surrogate": k, "auroc": auroc(gold, s),
               "auprc": auprc(gold, s), "brier": float(np.mean((p - gold) ** 2)),
               "ece": ece(gold, p), "false_safe_rate": fs,
               "top1_accuracy": top1 / max(nq, 1), "pairwise_accuracy": pair / max(pn, 1),
               "kendall_tau": float(np.mean(taus)) if taus else float("nan"),
               "discriminative_states": nq}
        sur_rows.append(row)
        print(f"{k:26s}{row['auroc']:8.3f}{row['auprc']:8.3f}{row['brier']:8.3f}"
              f"{row['ece']:8.3f}{fs:11.3f}{row['top1_accuracy']:7.3f}"
              f"{row['pairwise_accuracy']:7.3f}{row['kendall_tau']:9.3f}")
    with (OUT_HEAD / "surrogate_evaluation.csv").open("w", newline="") as fh:
        keys = sorted({k for r in sur_rows for k in r})
        w = csv.DictWriter(fh, fieldnames=keys); w.writeheader(); w.writerows(sur_rows)

    # ================= TASK 9 — headroom re-qualification =================
    print("\nTASK 9 — headroom under V2 labels")
    rng = np.random.default_rng(ROLLOUT_SEED + 2)
    state_rows, ep_rows = [], []
    for st in states:
        recs = evaluate_modes(st["snap"], LEARNED_TOPOLOGY_IDS, cfg, st["regions"],
                              rng, n_rollouts=N_ROLLOUTS, **DEFAULT)
        rates = {m: float(np.mean([r.task_recovery for r in rs])) for m, rs in recs.items()}
        vals = np.array([rates[m] for m in LEARNED_TOPOLOGY_IDS])
        bi = int(np.argmax(vals))
        if vals[0] == vals[bi]:
            bi = 0
        best, keep_r, second = float(vals[bi]), float(vals[0]), float(np.sort(vals)[-2])
        state_rows.append({
            "benchmark_tag": TAG, "layout_id": st["layout_id"], "family": st["family"],
            "team_size": st["team_size"], "step": st["step"],
            **{f"R_{MODE_NAME[m]}": rates[m] for m in LEARNED_TOPOLOGY_IDS},
            "best_mode": MODE_NAME[LEARNED_TOPOLOGY_IDS[bi]],
            "mode_margin": best - second, "keep_regret": best - keep_r,
            "mode_necessity": int(keep_r < 0.5 <= best),
            "qualified": int(best >= 0.5 and len(set(vals.tolist())) > 1)})

    for lay in build_layouts("val"):
        reg = regions_for_layout(lay, cfg)
        for n in TEAM_SIZES:
            for seed in setting_episode_seeds(VALIDATION, 0, n, EPISODES_POLICY, 0):
                per_mode = {}
                for m in LEARNED_TOPOLOGY_IDS:
                    env = SwarmFormationEnv(cfg)
                    obs = env.reset(n, "cluttered", seed=seed, layout=lay)
                    acc = EpisodeAccumulator(formation_tolerance=cfg.env.formation_tolerance,
                                             dt=cfg.env.dt)
                    done, last = False, None
                    while not done:
                        obs, _, done, last = env.step(expert_action(obs, cfg, m), m)
                        acc.update(last)
                    per_mode[MODE_NAME[m]] = acc.finalize(last)
                # per-decision oracle on the V2 label
                env = SwarmFormationEnv(cfg)
                obs = env.reset(n, "cluttered", seed=seed, layout=lay)
                acc = EpisodeAccumulator(formation_tolerance=cfg.env.formation_tolerance,
                                         dt=cfg.env.dt)
                done, last, step, mode, sw = False, None, 0, 0, 0
                while not done:
                    if step % 20 == 0:
                        r = evaluate_modes(env, LEARNED_TOPOLOGY_IDS, cfg, reg, rng,
                                           n_rollouts=2, **DEFAULT)
                        nm = LEARNED_TOPOLOGY_IDS[int(np.argmax(
                            [np.mean([x.task_recovery for x in r[m]]) for m in LEARNED_TOPOLOGY_IDS]))]
                        sw += int(nm != mode); mode = nm
                    obs, _, done, last = env.step(expert_action(obs, cfg, mode), mode)
                    acc.update(last); step += 1
                orc = acc.finalize(last)
                any_fixed = max(m["success"] for m in per_mode.values())
                row = {"benchmark_tag": TAG, "layout_id": lay.layout_id, "family": lay.family,
                       "team_size": n, "seed": seed, "oracle_switches": sw,
                       "switch_necessity": int(orc["success"] > 0.5 and any_fixed < 0.5),
                       "best_fixed_success": float(any_fixed)}
                for nm_, m in per_mode.items():
                    for k in ["success", "collision_free", "goal_reached", "deadlock",
                              "irreversible_collapse"]:
                        row[f"{nm_}_{k}"] = float(m[k])
                for k in ["success", "collision_free", "goal_reached", "deadlock",
                          "irreversible_collapse"]:
                    row[f"oracle_{k}"] = float(orc[k])
                ep_rows.append(row)
        print(f"  {lay.layout_id:28s} episodes={len(ep_rows)}", flush=True)

    summary = []
    for fam in sorted({r["family"] for r in state_rows}):
        s = [r for r in state_rows if r["family"] == fam]
        q = [r for r in s if r["qualified"]]
        e = [r for r in ep_rows if r["family"] == fam]
        dist = Counter(r["best_mode"] for r in q); nq = max(len(q), 1)
        summary.append({
            "benchmark_tag": TAG, "family": fam, "states": len(s), "qualified_states": len(q),
            "best_keep_frac": dist.get("keep", 0) / nq, "best_line_frac": dist.get("line", 0) / nq,
            "best_split_frac": dist.get("split", 0) / nq,
            "selector_headroom": float(np.mean([r["keep_regret"] for r in q])) if q else 0.0,
            "median_mode_margin": float(np.median([r["mode_margin"] for r in q])) if q else 0.0,
            "mode_necessity": float(np.mean([r["mode_necessity"] for r in q])) if q else 0.0,
            "keep_success": float(np.mean([r["keep_success"] for r in e])),
            "line_success": float(np.mean([r["line_success"] for r in e])),
            "split_success": float(np.mean([r["split_success"] for r in e])),
            "oracle_success": float(np.mean([r["oracle_success"] for r in e])),
            "oracle_advantage": float(np.mean([r["oracle_success"] for r in e])
                                      - np.mean([r["keep_success"] for r in e])),
            "switch_necessity": float(np.mean([r["switch_necessity"] for r in e])),
            "mean_oracle_switches": float(np.mean([r["oracle_switches"] for r in e]))})

    for name, rows in [("per_state_scores.csv", state_rows), ("per_episode.csv", ep_rows),
                       ("summary.csv", summary)]:
        with (OUT_HEAD / name).open("w", newline="") as fh:
            keys = sorted({k for r in rows for k in r})
            w = csv.DictWriter(fh, fieldnames=keys); w.writeheader(); w.writerows(rows)
        print(f"wrote {OUT_HEAD/name} ({len(rows)} rows)")

    print(f"\n{'family':20s}{'qual':>6s}{'keep':>7s}{'line':>7s}{'split':>7s}"
          f"{'headrm':>8s}{'margin':>8s}{'keepS':>7s}{'oracS':>7s}{'oracAdv':>9s}{'swNec':>7s}")
    for r in summary:
        print(f"{r['family']:20s}{r['qualified_states']:6d}{r['best_keep_frac']:7.3f}"
              f"{r['best_line_frac']:7.3f}{r['best_split_frac']:7.3f}{r['selector_headroom']:8.3f}"
              f"{r['median_mode_margin']:8.3f}{r['keep_success']:7.3f}{r['oracle_success']:7.3f}"
              f"{r['oracle_advantage']:9.3f}{r['switch_necessity']:7.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
