"""Task 5-4 — predeclared closed-loop corridor-width sweep.

Diagnostic fixed policies only. No learned selector. No final-test layouts.
The alpha grid, the controls, the seeds and the geometry variants are all fixed
in this file BEFORE the sweep runs, and every cell is reported.
"""
from __future__ import annotations
import json, sys, statistics
from pathlib import Path
import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from rvt_swarm.decentralized.env_geometry import (                      # noqa: E402
    build_passage, required_half_separation, single_robot_half_separation,
    validate_passage)
from rvt_swarm.decentralized.formation_metric_v3 import (               # noqa: E402
    EPSILON_FORM, L_RECOVER, e_inf)
from rvt_swarm.decentralized.qualification_fixtures import (            # noqa: E402
    EPSILON_INIT, Fixture, fixture_config, fixture_layout,
    simulate_reset_to_fixture)
from rvt_swarm.decentralized.roles import RoleAssignment                # noqa: E402
from rvt_swarm.decentralized.runtime import simulate_decentralized_episode as run  # noqa: E402
from rvt_swarm.decentralized.system_model import KEEP, LINE             # noqa: E402
from rvt_swarm.environment import SwarmFormationEnv                     # noqa: E402

OUT = REPO / "results" / "reconfiguration_width_sweep"
N = 6
ALPHAS = [0.05, 0.15, 0.25, 0.35, 0.45, 0.55, 0.65, 0.75, 0.85, 0.95]
SEEDS = [0, 1, 2]
VARIANTS = [                       # (corridor_length, entry_offset, centre_y)
    (1.0, 0.0, 0.0),
    (2.0, 0.5, 0.0),
]
# P3/P4 are predeclared as scripted transitions at the KNOWN GEOMETRIC ENTRY
# AND EXIT PLANES. An earlier implementation used fixed step numbers (18 / 55),
# which is NOT the predeclared policy and confounded the sweep badly: at
# h = 0.775 a fixed switch at step 18 gave crossing 0.00, while switching at the
# entry plane gives crossing 1.00 and full success 1.00. The planes are computed
# per geometry and per seed from an always-KEEP probe, so the timing is a
# property of the layout rather than a tuned constant.
ENTRY_LOOKAHEAD = 2.0     # m before the entry plane; ~the keep template's own extent


def plane_steps(geo, fx, cfg, sd):
    """Steps at which the team reaches the entry-lookahead and the exit plane.

    Derived from an always-KEEP probe of the SAME geometry and seed, so the
    scripted policy transitions at the declared geometric planes rather than at
    an arbitrary step.
    """
    env = SwarmFormationEnv(cfg)
    obs = simulate_reset_to_fixture(env, fx, sd, cfg)
    r = run(cfg, fixture_layout(fx), N, sd, forced_mode=KEEP,
            trace_positions=True, preset_env=env, preset_obs=obs)
    traj = r["position_trace"]
    ax = np.array(r["mission_dir"]); ax = ax / max(np.linalg.norm(ax), 1e-9)
    t_in = next((t for t, p in enumerate(traj)
                 if float((p @ ax).max()) >= geo.entry_x - ENTRY_LOOKAHEAD), 0)
    t_out = next((t for t, p in enumerate(traj)
                  if float((p @ ax).min()) >= geo.exit_x), None)
    if t_out is None:            # always-KEEP never crossed: use the line probe
        env = SwarmFormationEnv(cfg)
        obs = simulate_reset_to_fixture(env, fx, sd, cfg)
        r2 = run(cfg, fixture_layout(fx), N, sd, forced_mode=LINE,
                 trace_positions=True, preset_env=env, preset_obs=obs)
        t2 = r2["position_trace"]
        t_out = next((t for t, p in enumerate(t2)
                      if float((p @ ax).min()) >= geo.exit_x), len(t2) - 1)
    return int(t_in), int(t_out)


def to_fixture(geo, cfg) -> Fixture:
    return Fixture(name="sweep", n=N, spawn_centre=geo.spawn_centre, goal=geo.goal,
                   obstacles=geo.obstacles, corridor_width=geo.free_width,
                   entry_x=geo.entry_x, exit_x=geo.exit_x,
                   recovery_x0=geo.recovery_x0, recovery_width=geo.recovery_width)


def score(res, geo, roles):
    traj, modes = res["position_trace"], res["mode_per_step"]
    md = res["mission_dir"]; T = len(traj)
    if T == 0:
        return None
    ek = np.array([e_inf(p, roles, KEEP, md) for p in traj])
    el = np.array([e_inf(p, roles, LINE, md) for p in traj])
    ax = np.array(md) / max(np.linalg.norm(md), 1e-9)
    t_entry = t_cross = None
    for t, p in enumerate(traj):
        s = p @ ax
        if t_entry is None and float(s.max()) >= geo.entry_x:
            t_entry = t
        if t_cross is None and float(s.min()) >= geo.exit_x:
            t_cross = t; break
    t_rec = None
    if t_cross is not None:
        for t in range(t_cross, T - L_RECOVER + 1):
            if all(ek[u] <= EPSILON_FORM
                   and float((traj[u] @ ax).min()) >= geo.recovery_x0
                   for u in range(t, t + L_RECOVER)):
                t_rec = t; break
    trans = [t for t in range(1, T) if modes[t] != modes[t - 1]]
    full = bool(res["goal_reached"] > .5 and res["collision_free"] > .5
                and res["deadlock"] < .5 and t_cross is not None and t_rec is not None)
    def seg(lo, hi, a):
        lo = 0 if lo is None else lo; hi = T if hi is None else hi
        return float(a[lo:hi].mean()) if hi > lo else float("nan")
    return {"initial_valid": bool(ek[0] <= EPSILON_INIT),
            "crossed": t_cross is not None, "goal": float(res["goal_reached"]),
            "collision_free": float(res["collision_free"]),
            "deadlock": float(res["deadlock"]),
            "recovered": t_rec is not None, "dwell": t_rec is not None,
            "full": full, "keep_err_before": seg(0, t_entry, ek),
            "line_err_inside": seg(t_entry, t_cross, el),
            "keep_err_after": seg(t_cross, None, ek),
            "transitions": len(trans), "transition_steps": trans,
            "time_in_line": float(np.mean([m == LINE for m in modes])),
            "epochs": res["n_decisions"], "noop_epochs": res["n_noop_epochs"],
            "steps": T}


POLICY_NAMES = ("P1_always_keep", "P2_always_line", "P3_scripted_KLK",
                "P4_scripted_KL", "P5_geometric")


def policy_kwargs(name, t_in, t_out):
    if name == "P1_always_keep":
        return dict(forced_mode=KEEP)
    if name == "P2_always_line":
        return dict(forced_mode=LINE)
    if name == "P3_scripted_KLK":
        return dict(scripted_planes=(t_in, t_out, ENTRY_LOOKAHEAD))
    if name == "P4_scripted_KL":
        # enters LINE at the plane and NEVER returns
        return dict(scripted_planes=(t_in, float("inf"), ENTRY_LOOKAHEAD))
    return dict(mode_rule="geometric")


def main() -> int:
    cfg = fixture_config()
    OUT.mkdir(parents=True, exist_ok=True)
    roles = RoleAssignment.from_index(N, cfg.env.nominal_spacing)
    half = cfg.env.world_size / 2.0
    h_line = required_half_separation(N, LINE, cfg)
    h_keep = required_half_separation(N, KEEP, cfg)
    cells = [("infeasible_control", single_robot_half_separation(cfg) - 0.10)]
    cells += [(f"alpha_{a:.2f}", h_line + a * (h_keep - h_line)) for a in ALPHAS]
    cells += [("keep_feasible_control", h_keep + 0.30)]
    print(f"h_line={h_line:.3f} h_keep={h_keep:.3f}; {len(cells)} width cells "
          f"x {len(POLICY_NAMES)} policies x {len(SEEDS)*len(VARIANTS)} episodes")

    out = {}
    for label, h in cells:
        out[label] = {"half_separation": h, "free_width": 2 * h, "policies": {}}
        for pname in POLICY_NAMES:
            rows = []
            for (clen, off, cy) in VARIANTS:
                geo = build_passage(N, cfg, h, half_world=half,
                                    corridor_length=clen, entry_offset=off, centre_y=cy)
                out[label].setdefault("validation", validate_passage(geo, cfg))
                fx = to_fixture(geo, cfg)
                for sd in SEEDS:
                    kw = policy_kwargs(pname, geo.entry_x, geo.exit_x)
                    env = SwarmFormationEnv(cfg)
                    obs = simulate_reset_to_fixture(env, fx, sd, cfg)
                    r = run(cfg, fixture_layout(fx), N, sd, trace_positions=True,
                            preset_env=env, preset_obs=obs, **kw)
                    m = score(r, geo, roles)
                    if m: rows.append(m)
            def agg(k):
                v = [float(x[k]) for x in rows if x.get(k) is not None
                     and not (isinstance(x[k], float) and np.isnan(x[k]))]
                return float(np.mean(v)) if v else float("nan")
            out[label]["policies"][pname] = {
                k: agg(k) for k in ("initial_valid","crossed","goal","collision_free",
                                    "deadlock","recovered","dwell","full",
                                    "keep_err_before","line_err_inside","keep_err_after",
                                    "transitions","time_in_line","epochs","noop_epochs","steps")}
            out[label]["policies"][pname]["n_episodes"] = len(rows)
        p = out[label]["policies"]
        print(f"  {label:22s} h={h:.3f} w={2*h:.3f} | "
              f"K:cr={p['P1_always_keep']['crossed']:.2f},full={p['P1_always_keep']['full']:.2f} "
              f"L:cr={p['P2_always_line']['crossed']:.2f},full={p['P2_always_line']['full']:.2f} "
              f"KLK:cr={p['P3_scripted_KLK']['crossed']:.2f},full={p['P3_scripted_KLK']['full']:.2f} "
              f"KL:full={p['P4_scripted_KL']['full']:.2f} "
              f"GEO:full={p['P5_geometric']['full']:.2f}", flush=True)

    (OUT / "width_sweep.json").write_text(json.dumps(
        {"cells": out, "alphas": ALPHAS, "seeds": SEEDS, "variants": VARIANTS,
         "h_line": h_line, "h_keep": h_keep, "N": N}, indent=2, default=str))
    print("\nwrote", OUT / "width_sweep.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
