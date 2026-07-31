"""Task 6-1 — what can each robot know at the successful recovery time?

Offline diagnosis only. The centroid and the global exit plane appear here
because this is an audit; nothing here is deployable.
"""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from rvt_swarm.decentralized.comms import (RadioChannel, make_radio_states,   # noqa: E402
                                           simulate_broadcast_round)
from rvt_swarm.decentralized.env_geometry import (build_passage,              # noqa: E402
                                                  required_half_separation)
from rvt_swarm.decentralized.epoch import TriggerThresholds                   # noqa: E402
from rvt_swarm.decentralized.formation_metric_v3 import (EPSILON_FORM,        # noqa: E402
                                                         L_RECOVER, e_inf)
from rvt_swarm.decentralized.local_controller import local_controller         # noqa: E402
from rvt_swarm.decentralized.qualification_fixtures import (Fixture,          # noqa: E402
    fixture_config, fixture_layout, simulate_reset_to_fixture)
from rvt_swarm.decentralized.roles import RoleAssignment                      # noqa: E402
from rvt_swarm.decentralized.system_model import (KEEP, LINE, CommParams)     # noqa: E402
from rvt_swarm.environment import SwarmFormationEnv                           # noqa: E402

OUT = REPO / "results" / "local_exit_observability_audit"
N, SEEDS = 6, [0, 1, 2, 3, 4]
ALPHAS = {"a0.25": 0.25, "a0.35": 0.35, "a0.45": 0.45}   # the line-requiring band


def trace_episode(cfg, geo, fx, seed, switch_step):
    """Run scripted K->L->K and record per-robot local observables each step."""
    roles = RoleAssignment.from_index(N, cfg.env.nominal_spacing)
    comm = CommParams()
    th = TriggerThresholds.from_config(cfg)
    env = SwarmFormationEnv(cfg)
    obs = simulate_reset_to_fixture(env, fx, seed, cfg)
    md = (float(obs["corridor_dx"]), float(obs["corridor_dy"]))
    ax = np.asarray(md); ax = ax / max(np.linalg.norm(ax), 1e-9)
    states = make_radio_states(range(N), comm)
    ch = RadioChannel(comm, seed=seed)
    mode = KEEP
    rows, step, done = [], 0, False
    while not done:
        if step == 0:
            mode = KEEP
        if step == 18:
            mode = LINE
        if step == switch_step:
            mode = KEEP
        views = simulate_broadcast_round(
            step, obs["positions"], obs["velocities"], roles, [mode] * N,
            [0] * N, [0] * N, states, ch, obs["obstacles"],
            cfg.env.obstacle_radius,
            (float(obs["goal"][0]), float(obs["goal"][1])), md, comm)
        along = obs["positions"] @ ax
        rec = {"step": step, "mode": mode, "along": along.tolist(),
               "e_keep": e_inf(obs["positions"], roles, KEEP, md)}
        per = []
        for i in range(N):
            v = views[i]
            obst = list(v.obstacles)
            clear = min((float(np.hypot(ox, oy)) for ox, oy, _ in obst),
                        default=float("inf"))
            # local side-wall evidence: obstacles roughly abeam (|dx| < 1.0)
            lat = [oy for ox, oy, _ in obst if abs(ox) < 1.0]
            left = min([y for y in lat if y > 0], default=float("inf"))
            right = min([-y for y in lat if y < 0], default=float("inf"))
            # local FORWARD free space: nearest obstacle in the forward sector
            fwd = min((float(np.hypot(ox, oy)) for ox, oy, _ in obst
                       if ox > 0 and abs(oy) < 1.2), default=float("inf"))
            per.append({"id": i, "along": float(along[i]), "clear": clear,
                        "left_wall": left, "right_wall": right,
                        "forward_free": fwd, "degree": v.degree,
                        "n_obstacles": len(obst)})
        rec["robots"] = per
        rows.append(rec)
        act = np.stack([local_controller(views[i], cfg, mode) for i in range(N)])
        obs, _, done, _ = env.step(act, mode)
        step += 1
    return rows, ax, roles, md, th


def main() -> int:
    cfg = fixture_config()
    OUT.mkdir(parents=True, exist_ok=True)
    half = cfg.env.world_size / 2.0
    hl = required_half_separation(N, LINE, cfg)
    hk = required_half_separation(N, KEEP, cfg)
    out = {}
    for label, a in ALPHAS.items():
        h = hl + a * (hk - hl)
        geo = build_passage(N, cfg, h, half_world=half)
        fx = Fixture(name=label, n=N, spawn_centre=geo.spawn_centre, goal=geo.goal,
                     obstacles=geo.obstacles, corridor_width=geo.free_width,
                     entry_x=geo.entry_x, exit_x=geo.exit_x,
                     recovery_x0=geo.recovery_x0, recovery_width=geo.recovery_width)
        cells = []
        for sd in SEEDS:
            rows, ax, roles, md, th = trace_episode(cfg, geo, fx, sd, 55)
            T = len(rows)
            # per-robot physical exit times (own x past the exit plane)
            t_exit = {}
            for i in range(N):
                t_exit[i] = next((r["step"] for r in rows
                                  if r["robots"][i]["along"] >= geo.exit_x), None)
            done_exits = [t for t in t_exit.values() if t is not None]
            # per-robot LOCAL detection of reopening (own clearance >= threshold)
            t_local = {}
            for i in range(N):
                t_local[i] = next((r["step"] for r in rows
                                   if r["step"] > 20
                                   and r["robots"][i]["clear"] >= th.recovery_clearance_m),
                                  None)
            det = [t for t in t_local.values() if t is not None]
            # forward-opening detection: forward sector clear while still inside
            t_fwd = {}
            for i in range(N):
                t_fwd[i] = next((r["step"] for r in rows
                                 if r["step"] > 20
                                 and r["robots"][i]["forward_free"] == float("inf")
                                 and r["robots"][i]["along"] < geo.exit_x), None)
            fwd = [t for t in t_fwd.values() if t is not None]
            centroid_exit = next((r["step"] for r in rows
                                  if float(np.mean(r["along"])) >= geo.exit_x), None)
            cells.append({
                "seed": sd, "steps": T,
                "t_first_exit": min(done_exits) if done_exits else None,
                "t_last_exit": max(done_exits) if done_exits else None,
                "t_majority_exit": (sorted(done_exits)[N // 2]
                                    if len(done_exits) > N // 2 else None),
                "t_centroid_exit_OFFLINE_ONLY": centroid_exit,
                "t_first_local_reopen": min(det) if det else None,
                "t_all_local_reopen": max(det) if det else None,
                "t_first_forward_opening": min(fwd) if fwd else None,
                "successful_command_step": 55,
                "per_robot_exit": t_exit,
                "per_robot_local_reopen": t_local,
            })
        out[label] = {"half_separation": h, "exit_x": geo.exit_x, "cells": cells}
        c = cells[0]
        print(f"{label} h={h:.3f}: first_exit={c['t_first_exit']} "
              f"majority={c['t_majority_exit']} last={c['t_last_exit']} "
              f"centroid={c['t_centroid_exit_OFFLINE_ONLY']} | "
              f"first_local_reopen={c['t_first_local_reopen']} "
              f"first_forward_opening={c['t_first_forward_opening']} | "
              f"successful_cmd=55", flush=True)
    (OUT / "observability.json").write_text(json.dumps(out, indent=2, default=str))
    print("\nwrote", OUT / "observability.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
