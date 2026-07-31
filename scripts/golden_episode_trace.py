"""Task 6R-1/6R-3 — one episode, one trace, consumed by both analyses.

The trace is written from INSIDE the runtime loop, from the same `RobotView`
objects the deployable trigger sees. The audit does not re-run the episode and
does not read simulator obstacle arrays.
"""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from rvt_swarm.decentralized import epoch as E                            # noqa: E402
from rvt_swarm.decentralized.comms import (RadioChannel, make_radio_states,  # noqa: E402
                                           simulate_broadcast_round)
from rvt_swarm.decentralized.env_geometry import (build_passage,          # noqa: E402
                                                  required_half_separation)
from rvt_swarm.decentralized.formation_metric_v3 import e_inf             # noqa: E402
from rvt_swarm.decentralized.local_controller import local_controller     # noqa: E402
from rvt_swarm.decentralized.qualification_fixtures import (Fixture,      # noqa: E402
    fixture_config, simulate_reset_to_fixture)
from rvt_swarm.decentralized.roles import RoleAssignment                  # noqa: E402
from rvt_swarm.decentralized.runtime import _robot_decision               # noqa: E402
from rvt_swarm.decentralized.system_model import (KEEP, LINE, CommParams,  # noqa: E402
                                                  ConsensusParams)
from rvt_swarm.environment import SwarmFormationEnv                        # noqa: E402

OUT = REPO / "results" / "recovery_timing_repair"
CELL_ALPHA, SEED, N = 0.35, 0, 6          # previously published cell + seed


def main() -> int:
    cfg = fixture_config()
    OUT.mkdir(parents=True, exist_ok=True)
    half = cfg.env.world_size / 2.0
    hl = required_half_separation(N, LINE, cfg)
    hk = required_half_separation(N, KEEP, cfg)
    h = hl + CELL_ALPHA * (hk - hl)
    geo = build_passage(N, cfg, h, half_world=half)
    fx = Fixture(name="golden", n=N, spawn_centre=geo.spawn_centre, goal=geo.goal,
                 obstacles=geo.obstacles, corridor_width=geo.free_width,
                 entry_x=geo.entry_x, exit_x=geo.exit_x,
                 recovery_x0=geo.recovery_x0, recovery_width=geo.recovery_width)

    roles = RoleAssignment.from_index(N, cfg.env.nominal_spacing)
    comm, cons = CommParams(), ConsensusParams()
    env = SwarmFormationEnv(cfg)
    obs = simulate_reset_to_fixture(env, fx, SEED, cfg)
    md = (float(obs["corridor_dx"]), float(obs["corridor_dy"]))
    ax = np.asarray(md); ax = ax / max(np.linalg.norm(ax), 1e-9)
    states = make_radio_states(range(N), comm)
    ch = RadioChannel(comm, seed=SEED)
    epochs = {i: E.EpochState(robot_id=i) for i in range(N)}
    for e in epochs.values():
        e.committed_mode = KEEP

    lines, step, done = [], 0, False
    while not done:
        views = simulate_broadcast_round(
            step, obs["positions"], obs["velocities"], roles,
            [epochs[i].committed_mode for i in range(N)],
            [epochs[i].epoch_id for i in range(N)],
            [epochs[i].remaining_commitment for i in range(N)],
            states, ch, obs["obstacles"], cfg.env.obstacle_radius,
            (float(obs["goal"][0]), float(obs["goal"][1])), md, comm)
        adj = {i: list(views[i].neighbour_ids()) for i in range(N)}

        rec = {"step": step, "t": step * cfg.env.dt,
               "e_keep": e_inf(obs["positions"], roles, KEEP, md),
               "along": (obs["positions"] @ ax).tolist(),
               "exit_x_OFFLINE_ONLY": geo.exit_x, "robots": []}
        for i in range(N):
            v, e = views[i], epochs[i]
            # --- detector internals, from the SAME view the trigger sees ---
            raw = E.forward_opening_evidence(v, cfg)
            streak_before = e.forward_open_streak
            latch_before = e.passage_latch
            allowed = E.recovery_trigger_allowed(e)
            support = E.peer_support_for_recovery(v, e)
            fwd_obst = [(ox, oy) for ox, oy, _ in v.obstacles
                        if ox > 0 and abs(oy) <= E.FORWARD_SECTOR_HALF_WIDTH]
            lat = [oy for ox, oy, _ in v.obstacles if abs(ox) < 1.0]
            rec["robots"].append({
                "id": i, "role_keep": list(roles.role_of(i, KEEP)),
                "pos": obs["positions"][i].tolist(),
                "vel": obs["velocities"][i].tolist(),
                "along": float((obs["positions"] @ ax)[i]),
                "committed_mode": e.committed_mode,
                "phase": e.phase, "latch": latch_before,
                "remaining_commitment": e.remaining_commitment,
                "locked": bool(e.locked),
                "n_obstacles": len(v.obstacles),
                "obstacles": [[round(float(ox), 4), round(float(oy), 4)]
                              for ox, oy, _ in v.obstacles],
                "forward_obstacles": len(fwd_obst),
                "left_wall": min([y for y in lat if y > 0], default=None),
                "right_wall": min([-y for y in lat if y < 0], default=None),
                "raw_opening": bool(raw),
                "streak_before": int(streak_before),
                "recovery_allowed": bool(allowed),
                "peer_support": float(support),
                "degree": v.degree,
                "mission_dir": list(md),
            })
        lines.append(rec)

        # --- the deployable trigger, evaluated on these same views ---------
        armed = False
        for i in range(N):
            fired = E.latched_local_trigger_v3(views[i], cfg, epochs[i], cons)
            rec["robots"][i]["armable"] = bool(fired)
            rec["robots"][i]["streak_after"] = int(epochs[i].forward_open_streak)
            if fired:
                epochs[i].arm_trigger(step)
                armed = True
        rec["armed_any"] = armed

        if armed:
            E.simulate_trigger_consensus(epochs, adj, cons.k_trigger,
                                         start_step=step, record_history=False)
            scoring = [i for i in range(N) if epochs[i].trigger_token is not None
                       and not epochs[i].locked]
            for i in scoring:
                epochs[i].begin_scoring()
            from rvt_swarm.decentralized.consensus import (ConsensusNode,
                                                           simulate_consensus)
            q = {i: _robot_decision(views[i], cfg, None, "geometric") for i in scoring}
            nodes = {i: ConsensusNode.from_logits(i, q[i][0], q[i][1], len(adj[i]),
                                                  epochs[i].epoch_id, cons)
                     for i in scoring}
            if nodes and not all(nodes[i].decide() == epochs[i].committed_mode
                                 for i in scoring):
                simulate_consensus(nodes, {i: [j for j in adj[i] if j in nodes]
                                           for i in nodes}, cons.k_score,
                                   start_step=step, record_history=False)
                for i in scoring:
                    epochs[i].begin_confirming(nodes[i].decide(), nodes[i].margin())
                E.simulate_confirm_consensus(epochs, adj, cons.k_confirm,
                                             start_step=step, record_history=False)
                for i in scoring:
                    before = epochs[i].committed_mode
                    if E.commit_or_retain(epochs[i], step, cons) and \
                            epochs[i].committed_mode != before:
                        E.note_transition(epochs[i], epochs[i].committed_mode)
                        rec.setdefault("transitions", []).append(
                            {"robot": i, "from": before,
                             "to": epochs[i].committed_mode})
            else:
                for i in scoring:
                    epochs[i].close_epoch()
                rec["noop_epoch"] = True

        for i, e in epochs.items():
            E.update_passage_latch(e, views[i], cfg, cons)
            e.tick()
        act = np.stack([local_controller(views[i], cfg, epochs[i].committed_mode)
                        for i in range(N)])
        obs, _, done, _ = env.step(act, epochs[0].committed_mode)
        step += 1

    with (OUT / "golden_episode_trace.jsonl").open("w") as f:
        for r in lines:
            f.write(json.dumps(r) + "\n")
    print(f"wrote {len(lines)} steps -> {OUT/'golden_episode_trace.jsonl'}")
    print(f"cell alpha={CELL_ALPHA} h={h:.3f} seed={SEED} exit_x={geo.exit_x:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
