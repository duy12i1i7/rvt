"""Task 4R-5 / 4R-7 — controller qualification on valid fixtures, V3 metric.

N=6 only (the only team size certified KEEP/LINE separated). Scripted modes and
the robot-local controller. No learned selector. No final-test layouts.
"""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from rvt_swarm.config import Config                                     # noqa: E402
from rvt_swarm.decentralized.formation_metric_v3 import (               # noqa: E402
    EPSILON_FORM, L_RECOVER, e_inf, e_rms, in_keep_tube)
from rvt_swarm.decentralized.qualification_fixtures import (            # noqa: E402
    EPSILON_INIT, build_fixtures, fixture_config, fixture_layout,
    simulate_reset_to_fixture, validate_initial_conditions)
from rvt_swarm.decentralized.roles import RoleAssignment                # noqa: E402
from rvt_swarm.decentralized.runtime import simulate_decentralized_episode as run  # noqa: E402
from rvt_swarm.decentralized.system_model import KEEP, LINE             # noqa: E402
from rvt_swarm.environment import SwarmFormationEnv                     # noqa: E402

OUT = REPO / "results" / "local_controller_reconfiguration_qualification_v2"
N = 6
SEEDS = [0, 1, 2, 3, 4]
MD = (1.0, 0.0)


def score(res, fixture, roles, cfg):
    traj = res["position_trace"]; modes = res["mode_per_step"]
    md = res["mission_dir"]; T = len(traj)
    if T == 0:
        return {"scored": False}
    ek = np.array([e_inf(p, roles, KEEP, md) for p in traj])
    el = np.array([e_inf(p, roles, LINE, md) for p in traj])
    ax = np.array(md) / max(np.linalg.norm(md), 1e-9)

    t_entry = t_cross = None
    if fixture.entry_x is not None:
        for t, p in enumerate(traj):
            s = p @ ax
            if t_entry is None and float(s.max()) >= fixture.entry_x:
                t_entry = t
            if t_cross is None and float(s.min()) >= fixture.exit_x:
                t_cross = t; break

    # recovery: in-tube for L_RECOVER consecutive steps after crossing,
    # and inside the recovery region when the fixture declares one
    t_rec = None
    if t_cross is not None or fixture.entry_x is None:
        start = t_cross if t_cross is not None else 0
        need_x = fixture.recovery_x0
        for t in range(start, T - L_RECOVER + 1):
            ok = True
            for u in range(t, t + L_RECOVER):
                if ek[u] > EPSILON_FORM: ok = False; break
                if need_x is not None and float((traj[u] @ ax).min()) < need_x:
                    ok = False; break
            if ok: t_rec = t; break

    def seg(lo, hi, arr):
        lo = 0 if lo is None else max(0, lo); hi = T if hi is None else min(T, hi)
        return float(arr[lo:hi].mean()) if hi > lo else float("nan")

    trans = [(t, modes[t]) for t in range(1, T) if modes[t] != modes[t-1]]
    crossed = (t_cross is not None) if fixture.entry_x is not None else True
    full = bool(res["goal_reached"] > .5 and res["collision_free"] > .5
                and res["deadlock"] < .5 and crossed and t_rec is not None)
    return {"scored": True,
            "initial_keep_valid": bool(ek[0] <= EPSILON_INIT),
            "e_inf_keep_0": float(ek[0]),
            "keep_err_before_entry": seg(0, t_entry, ek),
            "line_err_inside": seg(t_entry, t_cross, el),
            "keep_err_after_exit": seg(t_cross, None, ek),
            "keep_err_min_after_exit": (float(ek[t_cross:].min()) if t_cross is not None else float("nan")),
            "exit_crossed": crossed, "t_entry": t_entry, "t_cross": t_cross,
            "t_reenter_keep_tube": (int(np.argmax(ek[t_cross:] <= EPSILON_FORM) + t_cross)
                                    if t_cross is not None and (ek[t_cross:] <= EPSILON_FORM).any() else None),
            "keep_recovered": t_rec is not None, "t_recover": t_rec,
            "recovery_dwell_complete": t_rec is not None,
            "goal_reached": float(res["goal_reached"]),
            "collision_free": float(res["collision_free"]),
            "deadlock": float(res["deadlock"]),
            "transition_count": len(trans), "transition_steps": [t for t,_ in trans],
            "time_in_line": float(np.mean([m == LINE for m in modes])),
            "completion_steps": T,
            "full_reconfiguration_success": full}


def main() -> int:
    cfg = fixture_config()
    OUT.mkdir(parents=True, exist_ok=True)
    fx = build_fixtures(cfg, N)
    roles = RoleAssignment.from_index(N, cfg.env.nominal_spacing)
    A, B, C = fx["A_open_keep"], fx["B_line_only_corridor"], fx["C_infeasible"]

    # entry/exit steps are geometric; derive from a keep run so probes are not
    # tuned to any policy
    ENTRY_STEP, LATE_STEP, EXIT_STEP, EARLY_STEP = 18, 45, 55, 35
    probes = [
        ("1_always_keep_open",        A, {"forced_mode": KEEP}),
        ("2_always_line_open",        A, {"forced_mode": LINE}),
        ("3_always_keep_corridor",    B, {"forced_mode": KEEP}),
        ("4_always_line_corridor",    B, {"forced_mode": LINE}),
        ("5_K_to_L_no_return",        B, {"scripted": {0: KEEP, ENTRY_STEP: LINE}}),
        ("6_K_to_L_to_K",             B, {"scripted": {0: KEEP, ENTRY_STEP: LINE, EXIT_STEP: KEEP}}),
        ("7_K_to_L_late",             B, {"scripted": {0: KEEP, LATE_STEP: LINE}}),
        ("8_L_to_K_early",            B, {"scripted": {0: KEEP, ENTRY_STEP: LINE, EARLY_STEP: KEEP}}),
        ("9_K_L_K_infeasible",        C, {"scripted": {0: KEEP, ENTRY_STEP: LINE, EXIT_STEP: KEEP}}),
    ]

    init = {f.name: validate_initial_conditions(f, 0, cfg) for f in (A, B, C)}
    for k, v in init.items():
        print(f"init {k:26s} E_inf={v['e_inf_keep']:.4f} valid={v['valid']}")
    print()

    out = {}
    for name, fixture, kw in probes:
        rows = []
        for sd in SEEDS:
            env = SwarmFormationEnv(cfg)
            obs = simulate_reset_to_fixture(env, fixture, sd, cfg)
            r = run(cfg, fixture_layout(fixture), N, sd, trace_positions=True,
                    preset_env=env, preset_obs=obs, **kw)
            m = score(r, fixture, roles, cfg)
            if m.get("scored"): rows.append(m)
        def agg(k):
            v = [float(x[k]) for x in rows if x.get(k) is not None
                 and not (isinstance(x[k], float) and np.isnan(x[k]))]
            return float(np.mean(v)) if v else float("nan")
        keys = ("initial_keep_valid","e_inf_keep_0","keep_err_before_entry","line_err_inside",
                "keep_err_after_exit","keep_err_min_after_exit","exit_crossed","keep_recovered",
                "recovery_dwell_complete","goal_reached","collision_free","deadlock",
                "transition_count","time_in_line","completion_steps","full_reconfiguration_success")
        out[name] = {k: agg(k) for k in keys}
        out[name]["n_episodes"] = len(rows)
        o = out[name]
        print(f"{name:24s} full={o['full_reconfiguration_success']:.2f} cross={o['exit_crossed']:.2f} "
              f"recov={o['keep_recovered']:.2f} keepE_after={o['keep_err_after_exit']:.3f} "
              f"min={o['keep_err_min_after_exit']:.3f} goal={o['goal_reached']:.2f} "
              f"cf={o['collision_free']:.2f}", flush=True)

    (OUT/"qualification_v2.json").write_text(json.dumps(
        {"initial_conditions": init, "probes": out,
         "epsilon_form": EPSILON_FORM, "epsilon_init": EPSILON_INIT,
         "L_recover": L_RECOVER, "N": N, "seeds": SEEDS}, indent=2, default=str))
    print("\nwrote", OUT/"qualification_v2.json")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
