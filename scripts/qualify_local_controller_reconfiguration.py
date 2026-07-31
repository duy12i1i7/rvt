"""Task 4 — controller requalification under the V2 reconfiguration task.

No learned selector. Robot-local controller with scripted / geometric mode
policies only. Validation + train layouts, never final-test.
"""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from rvt_swarm.config import Config                                    # noqa: E402
from rvt_swarm.decentralized.reconfiguration_metrics import score_episode  # noqa: E402
from rvt_swarm.decentralized.roles import RoleAssignment               # noqa: E402
from rvt_swarm.decentralized.runtime import simulate_decentralized_episode as run  # noqa: E402
from rvt_swarm.decentralized.system_model import KEEP, LINE            # noqa: E402
from rvt_swarm.environment import SwarmFormationEnv                    # noqa: E402
from rvt_swarm.layouts import build_layouts                            # noqa: E402
from rvt_swarm.splits import VALIDATION, setting_episode_seeds         # noqa: E402

OUT = REPO / "results" / "local_controller_reconfiguration_qualification"
FAMS = ("line_corridor", "keep_line_keep", "keep_open", "ambiguous")
EPISODES = 2

def roles_for(cfg, lay, n, seed):
    env = SwarmFormationEnv(cfg); obs = env.reset(n, "cluttered", seed=seed, layout=lay)
    md = (float(obs["corridor_dx"]), float(obs["corridor_dy"]))
    return RoleAssignment.simulate_mission_setup_from_initial_formation(
        obs["positions"], md, cfg.env.nominal_spacing)

def sweep(cfg, name, fn, fams=FAMS):
    rows = []
    for lay in [l for l in build_layouts("val") if l.family in fams]:
        for n in (4, 6):
            for sd in setting_episode_seeds(VALIDATION, 0, n, EPISODES, 0):
                r = fn(lay, n, sd)
                m = score_episode(r, roles_for(cfg, lay, n, sd), cfg, n)
                if m.get("scored"):
                    rows.append({"family": lay.family, "n": n, "seed": sd, **m})
    return rows

def agg(rows, key):
    v = [float(r[key]) for r in rows if r.get(key) is not None
         and not (isinstance(r[key], float) and np.isnan(r[key]))]
    return float(np.mean(v)) if v else float("nan")

KEYS = ("initial_keep_valid","corridor_entry","bottleneck_crossed","exit_plane_crossed",
        "keep_recovered","recovery_dwell_complete","goal_reached","collision_free",
        "deadlock","formation_rms_before","formation_rms_inside","formation_rms_after",
        "transition_count","time_in_line","completion_steps","full_reconfiguration_success")

def main() -> int:
    cfg = Config(); cfg.train.device = "cpu"; cfg.env.scenarios = ["cluttered"]
    OUT.mkdir(parents=True, exist_ok=True)
    T = 120
    arms = {
        "1_always_keep":        lambda l,n,s: run(cfg,l,n,s,forced_mode=KEEP,trace_positions=True),
        "2_always_line":        lambda l,n,s: run(cfg,l,n,s,forced_mode=LINE,trace_positions=True),
        "3_scripted_K_L_K":     lambda l,n,s: run(cfg,l,n,s,scripted={0:KEEP,30:LINE,75:KEEP},trace_positions=True),
        "4_scripted_K_L_norec": lambda l,n,s: run(cfg,l,n,s,scripted={0:KEEP,30:LINE},trace_positions=True),
        "5_geometric_event":    lambda l,n,s: run(cfg,l,n,s,mode_rule="geometric",trace_positions=True),
    }
    out = {}
    for name, fn in arms.items():
        rows = sweep(cfg, name, fn)
        out[name] = {"pooled": {k: agg(rows, k) for k in KEYS},
                     "by_family": {f: {k: agg([r for r in rows if r["family"]==f], k) for k in KEYS}
                                   for f in sorted({r["family"] for r in rows})},
                     "n_episodes": len(rows)}
        p = out[name]["pooled"]
        print(f"{name:24s} full={p['full_reconfiguration_success']:.3f} "
              f"cross={p['bottleneck_crossed']:.3f} recov={p['keep_recovered']:.3f} "
              f"goal={p['goal_reached']:.3f} cf={p['collision_free']:.3f} "
              f"line%={p['time_in_line']:.2f}", flush=True)

    # ---- Task 4B forced transition probes, corridor families only ----------
    probes = {
        "A_keep_from_start":   lambda l,n,s: run(cfg,l,n,s,forced_mode=KEEP,trace_positions=True),
        "B_line_from_start":   lambda l,n,s: run(cfg,l,n,s,forced_mode=LINE,trace_positions=True),
        "C_K_to_L_valid":      lambda l,n,s: run(cfg,l,n,s,scripted={0:KEEP,30:LINE},trace_positions=True),
        "D_L_to_K_after_exit": lambda l,n,s: run(cfg,l,n,s,scripted={0:KEEP,30:LINE,75:KEEP},trace_positions=True),
        "E_K_to_L_too_late":   lambda l,n,s: run(cfg,l,n,s,scripted={0:KEEP,70:LINE},trace_positions=True),
        "F_L_to_K_too_early":  lambda l,n,s: run(cfg,l,n,s,scripted={0:KEEP,30:LINE,45:KEEP},trace_positions=True),
    }
    pr = {}
    for name, fn in probes.items():
        rows = sweep(cfg, name, fn, fams=("line_corridor","keep_line_keep"))
        pr[name] = {k: agg(rows, k) for k in KEYS}
        p = pr[name]
        print(f"  probe {name:22s} full={p['full_reconfiguration_success']:.3f} "
              f"cross={p['bottleneck_crossed']:.3f} recov={p['keep_recovered']:.3f} "
              f"cf={p['collision_free']:.3f} rms_after={p['formation_rms_after']:.3f}", flush=True)

    (OUT/"qualification.json").write_text(json.dumps({"arms":out,"probes":pr}, indent=2, default=str))
    print("wrote", OUT/"qualification.json")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
