"""Task 6RR-1/6RR-2 — post-repair traces + delay decomposition."""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from rvt_swarm.decentralized import epoch as E                             # noqa: E402
from rvt_swarm.decentralized import guards                                 # noqa: E402
from rvt_swarm.decentralized.comms import (RadioChannel, make_radio_states,  # noqa: E402
                                           simulate_broadcast_round)
from rvt_swarm.decentralized.consensus import ConsensusNode, simulate_consensus  # noqa: E402
from rvt_swarm.decentralized.env_geometry import (build_passage,           # noqa: E402
                                                  required_half_separation)
from rvt_swarm.decentralized.local_controller import local_controller      # noqa: E402
from rvt_swarm.decentralized.qualification_fixtures import (Fixture,       # noqa: E402
    fixture_config, simulate_reset_to_fixture)
from rvt_swarm.decentralized.roles import RoleAssignment                   # noqa: E402
from rvt_swarm.decentralized.system_model import (KEEP, LINE, CommParams,  # noqa: E402
                                                  ConsensusParams)
from rvt_swarm.environment import SwarmFormationEnv                        # noqa: E402

OUT = REPO / "results" / "recovery_propagation_latency"
N = 6
CELLS = {"alpha_025": 0.25, "alpha_035": 0.35, "alpha_045": 0.45}
SEEDS = [0, 1, 2, 3, 4]


def run_traced(cfg, geo, fx, seed):
    guards.set_strict(True)
    roles = RoleAssignment.from_index(N, cfg.env.nominal_spacing)
    comm, cons = CommParams(), ConsensusParams()
    env = SwarmFormationEnv(cfg)
    obs = simulate_reset_to_fixture(env, fx, seed, cfg)
    md = (float(obs["corridor_dx"]), float(obs["corridor_dy"]))
    ax = np.asarray(md); ax = ax / max(np.linalg.norm(ax), 1e-9)
    states = make_radio_states(range(N), comm)
    ch = RadioChannel(comm, seed=seed)
    eps = {i: E.EpochState(robot_id=i) for i in range(N)}
    for e in eps.values():
        e.committed_mode = KEEP
    ev = {i: {} for i in range(N)}          # per-robot first-time-of event
    rows, step, done = [], 0, False

    def mark(i, key, s):
        ev[i].setdefault(key, s)

    while not done:
        views = simulate_broadcast_round(
            step, obs["positions"], obs["velocities"], roles,
            [eps[i].committed_mode for i in range(N)],
            [eps[i].epoch_id for i in range(N)],
            [eps[i].remaining_commitment for i in range(N)],
            states, ch, obs["obstacles"], cfg.env.obstacle_radius,
            (float(obs["goal"][0]), float(obs["goal"][1])), md, comm)
        adj = {i: list(views[i].neighbour_ids()) for i in range(N)}
        rec = {"step": step, "robots": []}

        for i in range(N):
            v, e = views[i], eps[i]
            raw = E.forward_opening_evidence(v, cfg)
            if raw and e.committed_mode == LINE:
                mark(i, "raw_evidence", step)
            rec["robots"].append({
                "id": i, "along": float((obs["positions"] @ ax)[i]),
                "committed_mode": e.committed_mode, "latch": e.passage_latch,
                "locked": bool(e.locked), "raw_opening": bool(raw),
                "streak": int(e.forward_open_streak),
                "recovery_allowed": bool(E.recovery_trigger_allowed(e)),
                "peer_support": float(E.peer_support_for_recovery(v, e)),
                "token": None if e.trigger_token is None else list(e.trigger_token.as_tuple()),
                "requested_mode": E.requested_mode_for(e),
                "degree": v.degree})

        armed, originators = False, []
        for i in range(N):
            fired = E.latched_local_trigger_v3(views[i], cfg, eps[i], cons)
            rec["robots"][i]["armable"] = bool(fired)
            if eps[i].forward_open_streak >= E.L_TRIGGER and eps[i].committed_mode == LINE:
                mark(i, "persistence_satisfied", step)
            if fired:
                mark(i, "armable", step)
                mark(i, "originated", step)
                eps[i].arm_trigger(step)
                originators.append(i)
                armed = True
        rec["originators"] = originators

        if armed:
            E.simulate_trigger_consensus(eps, adj, cons.k_trigger,
                                         start_step=step, record_history=False)
            for i in range(N):
                if eps[i].trigger_token is not None:
                    mark(i, "token_adopted", step)
                    if E.requested_mode_for(eps[i]) == KEEP:
                        mark(i, "requested_keep", step)
            scoring = [i for i in range(N) if eps[i].trigger_token is not None
                       and not eps[i].locked]
            for i in scoring:
                eps[i].begin_scoring()
                mark(i, "eligible", step)
            q = {}
            for i in scoring:
                req = E.requested_mode_for(eps[i])
                q[i] = ((1.0, 0.0) if req == KEEP else (0.0, 1.0)) if req is not None \
                    else (1.0, 0.0)
            nodes = {i: ConsensusNode.from_logits(i, q[i][0], q[i][1], len(adj[i]),
                                                  eps[i].epoch_id, cons)
                     for i in scoring}
            if nodes and not all(nodes[i].decide() == eps[i].committed_mode
                                 for i in scoring):
                simulate_consensus(nodes, {i: [j for j in adj[i] if j in nodes]
                                           for i in nodes}, cons.k_score,
                                   start_step=step, record_history=False)
                for i in scoring:
                    mark(i, "score_done", step)
                    eps[i].begin_confirming(nodes[i].decide(), nodes[i].margin())
                E.simulate_confirm_consensus(eps, adj, cons.k_confirm,
                                             start_step=step, record_history=False)
                for i in scoring:
                    mark(i, "confirm_done", step)
                    before = eps[i].committed_mode
                    ok = E.commit_or_retain(eps[i], step, cons)
                    if ok and eps[i].committed_mode != before:
                        E.note_transition(eps[i], eps[i].committed_mode)
                        if eps[i].committed_mode == KEEP:
                            mark(i, "commit_keep", step)
                        else:
                            mark(i, "commit_line", step)
                    elif not ok:
                        rec.setdefault("rejections", []).append(
                            {"robot": i, "mode_lo": eps[i].mode_lo,
                             "mode_hi": eps[i].mode_hi,
                             "epoch_mismatch": eps[i].epoch_mismatch})
            else:
                rec["noop_epoch"] = True
                for i in scoring:
                    eps[i].close_epoch()

        rows.append(rec)
        for i, e in eps.items():
            E.update_passage_latch(e, views[i], cfg, cons)
            e.tick()
        act = np.stack([local_controller(views[i], cfg, eps[i].committed_mode)
                        for i in range(N)])
        obs, _, done, _ = env.step(act, eps[0].committed_mode)
        step += 1
    return rows, ev


def main() -> int:
    cfg = fixture_config()
    OUT.mkdir(parents=True, exist_ok=True)
    half = cfg.env.world_size / 2.0
    hl = required_half_separation(N, LINE, cfg)
    hk = required_half_separation(N, KEEP, cfg)
    summary = {}
    for label, a in CELLS.items():
        h = hl + a * (hk - hl)
        geo = build_passage(N, cfg, h, half_world=half)
        fx = Fixture(name=label, n=N, spawn_centre=geo.spawn_centre, goal=geo.goal,
                     obstacles=geo.obstacles, corridor_width=geo.free_width,
                     entry_x=geo.entry_x, exit_x=geo.exit_x,
                     recovery_x0=geo.recovery_x0, recovery_width=geo.recovery_width)
        cells = []
        with (OUT / f"{label}_trace.jsonl").open("w") as f:
            for sd in SEEDS:
                rows, ev = run_traced(cfg, geo, fx, sd)
                for r in rows:
                    f.write(json.dumps({"seed": sd, **r}) + "\n")
                cells.append({"seed": sd, "events": ev})
        summary[label] = {"h": h, "cells": cells}
        # print the decomposition for seed 0
        ev = cells[0]["events"]
        first_raw = min((e["raw_evidence"] for e in ev.values() if "raw_evidence" in e),
                        default=None)
        first_pers = min((e["persistence_satisfied"] for e in ev.values()
                          if "persistence_satisfied" in e), default=None)
        first_arm = min((e["armable"] for e in ev.values() if "armable" in e), default=None)
        commits = [e["commit_keep"] for e in ev.values() if "commit_keep" in e]
        last_raw = max((e["raw_evidence"] for e in ev.values() if "raw_evidence" in e),
                       default=None)
        print(f"{label} h={h:.3f} seed0: first_raw={first_raw} first_pers={first_pers} "
              f"first_arm={first_arm} LAST_raw={last_raw} commit={min(commits) if commits else None}")
    (OUT / "event_summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print("wrote", OUT / "event_summary.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
