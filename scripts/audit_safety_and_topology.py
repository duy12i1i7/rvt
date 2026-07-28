"""Tasks 2 and 3 — safety-filter attribution and topology-switching audits.

VALIDATION SPLIT ONLY. Grids are predeclared in this file before running.
No final-test scenario, seed, or metric is touched.
"""
from __future__ import annotations

import csv
import sys
from collections import Counter
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from rvt_swarm.config import Config  # noqa: E402
from rvt_swarm.environment import SwarmFormationEnv  # noqa: E402
from rvt_swarm.metrics import EpisodeAccumulator  # noqa: E402
from rvt_swarm.policy_runtime import infer_learned_action, load_learned_model  # noqa: E402
from rvt_swarm.splits import VALIDATION, setting_episode_seeds  # noqa: E402
from rvt_swarm.train import git_commit  # noqa: E402
from rvt_swarm.utils import torch_device  # noqa: E402

OUT = REPO / "results" / "method_audit"
CKPT = REPO / "checkpoints" / "method_audit"
TAG = "benchmark-protocol-v2-smoke"

# ---- PREDECLARED GRIDS (fixed before any run; never tuned on final test) ----
RISK_THRESHOLD_GRID = [0.50, 0.65, 0.75, 0.85, 0.95]
DWELL_GRID = [0, 3, 5, 10]
HYSTERESIS_GRID = [0.0, 0.05, 0.10, 0.25]

VAL_SCENARIOS = ["open_field", "narrow_passage"]
VAL_TEAM_SIZES = [5, 11]
VAL_EPISODES = 8


def val_config() -> Config:
    cfg = Config()
    cfg.train.device = "cpu"
    cfg.env.team_sizes = [4, 8]
    cfg.env.scenarios = VAL_SCENARIOS
    return cfg


def val_seeds():
    for si, scenario in enumerate(VAL_SCENARIOS):
        for n in VAL_TEAM_SIZES:
            for seed in setting_episode_seeds(VALIDATION, si, n, VAL_EPISODES, 0):
                yield scenario, n, seed


def run_episode(method, cfg, n, scenario, seed, model):
    """One validation episode with full per-step safety + selector instrumentation."""
    env = SwarmFormationEnv(cfg)
    obs = env.reset(n, scenario, seed=seed)
    acc = EpisodeAccumulator(formation_tolerance=cfg.env.formation_tolerance, dt=cfg.env.dt)
    steps_log, prev_topo, done, last = [], 0, False, None
    while not done:
        rt = infer_learned_action(method, obs, cfg, model, prev_topo)
        ss, sel = rt.get("safety_stats", {}), rt.get("selector_stats", {})
        nominal, filtered = rt["nominal_actions"], rt["actions"]
        diff = np.linalg.norm(filtered - nominal, axis=-1)
        nom = np.linalg.norm(nominal, axis=-1)
        rel = float(np.mean(diff / np.maximum(nom, 1e-6)))
        prev = prev_topo
        prev_topo = rt["topology"]
        obs, _, done, info = env.step(filtered, rt["topology"])
        acc.update(info, shield_activated=bool(ss.get("activated", 0.0) > 0.5))
        steps_log.append({
            "activated": float(ss.get("activated", 0.0)),
            "triggered": float(ss.get("triggered", 0.0)),
            "reason": str(ss.get("reason", "na")),
            "risk": float(ss.get("risk", 0.0)),
            "threshold": float(ss.get("threshold", 0.0)),
            "n_active_constraints": float(ss.get("n_active_constraints", 0.0)),
            "relative_intervention": rel,
            "cos_direction": float(ss.get("mean_cos_direction_change", 1.0)),
            "min_rr_clearance": float(info["min_rr_clearance"]),
            "min_ro_clearance": float(info["min_ro_clearance"]),
            "collision_free": float(info["collision_free"]),
            "goal_progress": float(info["goal_progress"]),
            "form_rms": float(info["form_rms"]),
            "topology": int(rt["topology"]),
            "prev_topology": int(prev),
            "switched": int(rt["topology"] != prev),
            "selector_reason": str(sel.get("reason", "na")),
            "time_since_switch": float(sel.get("time_since_switch", 0.0)),
            "bottleneck": float(sel.get("bottleneck", 0.0)),
            "scores": sel.get("scores"),
            "uncertainty": sel.get("uncertainty"),
            "logit_choice": sel.get("logit_argmax_choice"),
        })
        last = info
    return acc.finalize(last), steps_log


def sweep(method, cfg_fn, label, model, extra=None):
    """Aggregate episode metrics + per-step diagnostics over the validation set."""
    ep_rows, all_steps = [], []
    for scenario, n, seed in val_seeds():
        cfg = cfg_fn()
        m, log = run_episode(method, cfg, n, scenario, seed, model)
        ep_rows.append(m)
        all_steps.extend(log)
    agg = {"variant": label, **(extra or {})}
    for k in ["success", "goal_reached", "collision_free", "form_ok",
              "time_in_formation_tube", "deadlock", "irreversible_collapse",
              "topology_switches", "stall_rate", "safety_filter_activation_rate"]:
        agg[k] = float(np.nanmean([r[k] for r in ep_rows]))
    agg["episodes"] = len(ep_rows)
    agg["steps"] = len(all_steps)
    return agg, all_steps


def safety_attribution(model, base_cfg_fn):
    print(f"\n{'='*72}\nTASK 2 — SAFETY-FILTER ATTRIBUTION (validation only)\n{'='*72}")
    rows, step_rows = [], []

    # (1) nominal learned policy, filter disabled
    def no_filter():
        c = base_cfg_fn(); c.audit.disable_safety_filter = True; return c
    agg, steps = sweep("rvt_swarm", no_filter, "1_no_filter", model)
    rows.append(agg)

    # (2) shipped filter (derived threshold)
    agg_cur, steps_cur = sweep("rvt_swarm", base_cfg_fn, "2_current_filter", model)
    rows.append(agg_cur)
    step_rows = steps_cur

    # (4) predeclared threshold grid
    for th in RISK_THRESHOLD_GRID:
        def with_th(th=th):
            c = base_cfg_fn(); c.audit.risk_threshold_override = th; return c
        agg, _ = sweep("rvt_swarm", with_th, f"4_threshold_{th:.2f}", model,
                       extra={"risk_threshold": th})
        rows.append(agg)

    # intervention statistics from the shipped configuration
    act = np.array([s["activated"] for s in steps_cur])
    rel = np.array([s["relative_intervention"] for s in steps_cur])
    rel_act = rel[act > 0.5]
    stats = {
        "variant": "2_current_filter_intervention_stats",
        "activation_rate": float(act.mean()),
        "rel_mean_all": float(rel.mean()),
        "rel_median_all": float(np.median(rel)),
        "rel_mean_when_active": float(rel_act.mean()) if rel_act.size else 0.0,
        "rel_median_when_active": float(np.median(rel_act)) if rel_act.size else 0.0,
        "rel_p90": float(np.percentile(rel, 90)),
        "rel_p95": float(np.percentile(rel, 95)),
        "pct_rel_gt_0.10": float((rel > 0.10).mean()),
        "pct_rel_gt_0.25": float((rel > 0.25).mean()),
        "pct_rel_gt_0.50": float((rel > 0.50).mean()),
        "pct_rel_gt_1.00": float((rel > 1.00).mean()),
        "mean_cos_direction_when_active": float(
            np.mean([s["cos_direction"] for s in steps_cur if s["activated"] > 0.5])
        ) if rel_act.size else 1.0,
        "collision_steps_while_active": float(
            np.mean([1 - s["collision_free"] for s in steps_cur if s["activated"] > 0.5])
        ) if rel_act.size else 0.0,
        "progress_when_active": float(
            np.mean([s["goal_progress"] for s in steps_cur if s["activated"] > 0.5])
        ) if rel_act.size else 0.0,
        "progress_when_idle": float(
            np.mean([s["goal_progress"] for s in steps_cur if s["activated"] <= 0.5])
        ) if (act <= 0.5).any() else 0.0,
    }
    reasons = Counter(s["reason"] for s in steps_cur if s["triggered"] > 0.5)
    for r, c in reasons.items():
        stats[f"reason_{r}"] = c / max(len(steps_cur), 1)
    rows.append(stats)

    print(f"  activation rate            {stats['activation_rate']:.3f}")
    print(f"  relative intervention      mean={stats['rel_mean_all']:.3f} "
          f"median={stats['rel_median_all']:.3f} p90={stats['rel_p90']:.3f} "
          f"p95={stats['rel_p95']:.3f}")
    print(f"  steps with rel > 0.10/0.25/0.50/1.00: "
          f"{stats['pct_rel_gt_0.10']:.3f} / {stats['pct_rel_gt_0.25']:.3f} / "
          f"{stats['pct_rel_gt_0.50']:.3f} / {stats['pct_rel_gt_1.00']:.3f}")
    print(f"  trigger reasons            {dict(reasons)}")
    for r in rows:
        if "success" in r:
            print(f"  {r['variant']:24s} succ={r['success']:.3f} cf={r['collision_free']:.3f} "
                  f"goal={r['goal_reached']:.3f} dead={r['deadlock']:.3f} "
                  f"act={r['safety_filter_activation_rate']:.3f}")
    return rows, step_rows


def topology_audit(model, base_cfg_fn, steps_cur):
    print(f"\n{'='*72}\nTASK 3 — TOPOLOGY SWITCHING (validation only)\n{'='*72}")
    rows = []
    switches = [i for i, s in enumerate(steps_cur) if s["switched"]]
    dwell, trans = [], Counter()
    last = 0
    for i in switches:
        dwell.append(i - last); last = i
        trans[(steps_cur[i]["prev_topology"], steps_cur[i]["topology"])] += 1
    reversals = {k: 0 for k in (1, 2, 5, 10)}
    for i in switches:
        prev = steps_cur[i]["prev_topology"]
        for w in reversals:
            if any(steps_cur[j]["topology"] == prev
                   for j in range(i + 1, min(i + 1 + w, len(steps_cur)))):
                reversals[w] += 1
    before_after = {"progress": [], "form_rms": [], "risk": []}
    for i in switches:
        if i >= 3 and i + 3 < len(steps_cur):
            for k, key in [("progress", "goal_progress"), ("form_rms", "form_rms"),
                           ("risk", "risk")]:
                before_after[k].append(steps_cur[i + 3][key] - steps_cur[i - 3][key])
    n_sw = max(len(switches), 1)
    summary = {
        "variant": "switch_diagnostics",
        "total_steps": len(steps_cur),
        "total_switches": len(switches),
        "switch_rate": len(switches) / max(len(steps_cur), 1),
        "dwell_mean": float(np.mean(dwell)) if dwell else float("nan"),
        "dwell_median": float(np.median(dwell)) if dwell else float("nan"),
        "dwell_p10": float(np.percentile(dwell, 10)) if dwell else float("nan"),
        **{f"reversal_within_{w}": reversals[w] / n_sw for w in reversals},
        **{f"delta_{k}_after_switch": (float(np.mean(v)) if v else float("nan"))
           for k, v in before_after.items()},
        "pct_switch_while_filter_active": float(
            np.mean([steps_cur[i]["activated"] for i in switches])) if switches else 0.0,
        "transition_matrix": str(dict(trans)),
    }
    rows.append(summary)
    print(f"  switches {summary['total_switches']} over {summary['total_steps']} steps "
          f"(rate {summary['switch_rate']:.3f})")
    print(f"  dwell mean={summary['dwell_mean']:.1f} median={summary['dwell_median']:.1f} "
          f"p10={summary['dwell_p10']:.1f} steps")
    print("  reversal within 1/2/5/10 steps: " +
          " / ".join(f"{summary[f'reversal_within_{w}']:.3f}" for w in (1, 2, 5, 10)))
    print(f"  switches while filter active: {summary['pct_switch_while_filter_active']:.3f}")
    print(f"  transitions: {dict(trans)}")

    variants = [
        ("1_fixed_topology", lambda: _c(base_cfg_fn, selector_mode="fixed")),
        ("2_logits_argmax", lambda: _c(base_cfg_fn, selector_mode="logits_argmax")),
        ("3_score_argmax", lambda: _c(base_cfg_fn, selector_mode="score_argmax")),
        ("4_lexicographic_shipped", base_cfg_fn),
        ("7_no_uncertainty_adj", lambda: _c(base_cfg_fn, use_uncertainty_adjustment=False)),
    ]
    for d in DWELL_GRID[1:]:
        variants.append((f"5_min_dwell_{d}", lambda d=d: _c(base_cfg_fn, min_dwell_steps=d)))
    for h in HYSTERESIS_GRID[1:]:
        variants.append((f"6_hysteresis_{h:.2f}", lambda h=h: _c(base_cfg_fn, hysteresis_margin=h)))

    for label, fn in variants:
        agg, _ = sweep("rvt_swarm", fn, label, model)
        rows.append(agg)
        print(f"  {label:26s} succ={agg['success']:.3f} cf={agg['collision_free']:.3f} "
              f"goal={agg['goal_reached']:.3f} tube={agg['time_in_formation_tube']:.3f} "
              f"switches={agg['topology_switches']:.2f} dead={agg['deadlock']:.3f}")
    return rows


def _c(base_cfg_fn, **kw):
    c = base_cfg_fn()
    for k, v in kw.items():
        setattr(c.audit, k, v)
    return c


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    if not (CKPT / "rvt_swarm.pt").exists():
        print(f"ERROR: no audit checkpoint at {CKPT}/rvt_swarm.pt")
        return 1
    model = load_learned_model("rvt_swarm", val_config(), str(CKPT), torch_device("cpu"))
    print(f"commit={git_commit()} tag={TAG}")

    safety_rows, steps_cur = safety_attribution(model, val_config)
    topo_rows = topology_audit(model, val_config, steps_cur)

    for name, rows in [("safety_filter_attribution.csv", safety_rows),
                       ("topology_switching.csv", topo_rows)]:
        keys = sorted({k for r in rows for k in r})
        with (OUT / name).open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=["benchmark_tag", "git_commit"] + keys)
            w.writeheader()
            for r in rows:
                w.writerow({"benchmark_tag": TAG, "git_commit": git_commit(), **r})
        print(f"\nwrote {OUT / name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
