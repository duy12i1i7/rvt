"""Task 6RR-10 — complete three-cell rerun, four arms."""
from __future__ import annotations
import json, sys, statistics
from pathlib import Path
import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from rvt_swarm.decentralized.env_geometry import (build_passage,           # noqa: E402
                                                  required_half_separation)
from rvt_swarm.decentralized.formation_metric_v3 import (EPSILON_FORM,     # noqa: E402
                                                         L_RECOVER, e_inf)
from rvt_swarm.decentralized.qualification_fixtures import (Fixture,       # noqa: E402
    fixture_config, fixture_layout, simulate_reset_to_fixture)
from rvt_swarm.decentralized.roles import RoleAssignment                   # noqa: E402
from rvt_swarm.decentralized.runtime import simulate_decentralized_episode as run  # noqa: E402
from rvt_swarm.decentralized.system_model import KEEP, LINE                # noqa: E402
from rvt_swarm.environment import SwarmFormationEnv                        # noqa: E402

OUT = REPO / "results" / "recovery_propagation_latency_repair"
N, SEEDS = 6, [0, 1, 2, 3, 4]
VARIANTS = [(1.0, 0.0), (2.0, 0.5)]
ALPHAS = {"alpha_025": 0.25, "alpha_035": 0.35, "alpha_045": 0.45}


def score(r, geo, roles):
    tr, md = r["position_trace"], r["mission_dir"]
    ax = np.asarray(md); ax = ax / max(np.linalg.norm(ax), 1e-9)
    ek = np.array([e_inf(p, roles, KEEP, md) for p in tr])
    tc = next((t for t, p in enumerate(tr) if float((p @ ax).min()) >= geo.exit_x), None)
    rec = False
    if tc is not None:
        for t in range(tc, len(tr) - L_RECOVER + 1):
            if all(ek[u] <= EPSILON_FORM
                   and float((tr[u] @ ax).min()) >= geo.recovery_x0
                   for u in range(t, t + L_RECOVER)):
                rec = True
                break
    l2k = next((s for s, m in r["mode_trace"] if all(x == KEEP for x in m)), None)
    return {"crossed": tc is not None, "dwell": rec,
            "collision_free": float(r["collision_free"]),
            "full": bool(r["goal_reached"] > .5 and r["collision_free"] > .5
                         and tc is not None and rec),
            "epochs": r["n_decisions"], "noop": r["n_noop_epochs"],
            "k2l": r["n_keep_to_line"] // N, "l2k": r["n_line_to_keep"] // N,
            "commit_step": l2k,
            "bytes": sum(c["bytes"] for c in r["comm"]["categories"].values())}


def main() -> int:
    cfg = fixture_config()
    OUT.mkdir(parents=True, exist_ok=True)
    half = cfg.env.world_size / 2.0
    roles = RoleAssignment.from_index(N, cfg.env.nominal_spacing)
    hl = required_half_separation(N, LINE, cfg)
    hk = required_half_separation(N, KEEP, cfg)
    ARMS = {
        "1_scripted_early_KLK": lambda g: dict(scripted_planes=(g.entry_x, g.exit_x, 2.0)),
        "4_v3_final_repair":    lambda g: dict(mode_rule="geometric", recovery_event="v3"),
    }
    out = {}
    for label, a in ALPHAS.items():
        h = hl + a * (hk - hl)
        out[label] = {"h": h, "arms": {}}
        for arm, kwf in ARMS.items():
            rows = []
            for clen, off in VARIANTS:
                geo = build_passage(N, cfg, h, half_world=half,
                                    corridor_length=clen, entry_offset=off)
                fx = Fixture(name=label, n=N, spawn_centre=geo.spawn_centre,
                             goal=geo.goal, obstacles=geo.obstacles,
                             corridor_width=geo.free_width, entry_x=geo.entry_x,
                             exit_x=geo.exit_x, recovery_x0=geo.recovery_x0,
                             recovery_width=geo.recovery_width)
                for sd in SEEDS:
                    env = SwarmFormationEnv(cfg)
                    obs = simulate_reset_to_fixture(env, fx, sd, cfg)
                    r = run(cfg, fixture_layout(fx), N, sd, trace_positions=True,
                            trace_modes=True, preset_env=env, preset_obs=obs,
                            **kwf(geo))
                    rows.append({"seed": sd, "variant": f"len{clen}_off{off}",
                                 **score(r, geo, roles)})
            def agg(k):
                v = [float(x[k]) for x in rows if x.get(k) is not None]
                return float(np.mean(v)) if v else float("nan")
            out[label]["arms"][arm] = {
                "per_episode": rows,
                "full": agg("full"), "crossed": agg("crossed"),
                "dwell": agg("dwell"), "collision_free": agg("collision_free"),
                "epochs_median": statistics.median([x["epochs"] for x in rows]),
                "noop_total": sum(x["noop"] for x in rows),
                "commit_step_mean": agg("commit_step"),
                "bytes_mean": agg("bytes")}
            o = out[label]["arms"][arm]
            print(f"{label} {arm:24s} full={o['full']:.2f} cross={o['crossed']:.2f} "
                  f"dwell={o['dwell']:.2f} cf={o['collision_free']:.2f} "
                  f"ep_med={o['epochs_median']:.0f} noop={o['noop_total']} "
                  f"commit={o['commit_step_mean']:.0f} bytes={o['bytes_mean']:.0f}",
                  flush=True)
    (OUT / "four_arm_comparison.json").write_text(json.dumps(out, indent=2, default=str))
    print("\nwrote", OUT / "four_arm_comparison.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
