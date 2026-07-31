"""The deployable decentralized runtime loop.

For every robot i, independently, once per control step:

  1 discover direct neighbours        6 exchange scores with direct neighbours
  2 receive fresh one-hop messages    7 execute leaderless finite-round consensus
  3 observe local obstacles           8 confirm mode peer-to-peer
  4 construct ego graph G_i           9 commit locally to keep or line
  5 estimate keep/line scores        10 compute its own action u_i
                                     11 send only its own command to its actuator

No central entity appears in that loop. `simulate_decentralized_episode` is the
harness that steps the simulator and the radio; it is boundary code. Every
decision is computed inside a per-robot `EpochState` that sees one `RobotView`
and one inbox.

What changed in Task 3, and why
-------------------------------
The previous runtime did **not** call the protocol it claimed to run. It kept a
plain `epoch_ids = [0] * n` list, advanced every robot's epoch id in lockstep,
and opened a decision on `step % decision_interval == 0`. Consequences:

  * epoch agreement was guaranteed by the harness, not achieved by the protocol,
    so any "decision-epoch synchronisation" measured against it was vacuous;
  * `epoch.py` (the trigger, the token, the state machine, the confirmation)
    and `comm_cost.py` were unreferenced dead code;
  * Gate D2's mode-confirmation criterion had no measurement at all.

`epoch.py` is now the sole authority for triggering, propagation, confirmation
and commitment, and `comm_cost.py` counts every protocol message at its send
site. The periodic path survives only as
`legacy_periodic_epoch_baseline`, which raises under
`strict_decentralized_runtime`.

Environment interface caveat, unchanged and restated: `env.step` takes a single
`topology_action` for the whole team because the simulator was written for a
centralized controller. Robot actions are computed individually and that
argument does not affect them; it drives the simulator's own bookkeeping. We
pass the majority committed mode and record disagreement separately. No robot
reads it, so it is not a coordination channel.
"""

from __future__ import annotations

from collections import Counter
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import torch

from ..config import Config
from ..environment import SwarmFormationEnv
from ..metrics import EpisodeAccumulator
from .comm_cost import MessageAccountant
from .comms import RadioChannel, make_radio_states, simulate_broadcast_round
from .consensus import (ConsensusNode, agreement_rate, component_agreement,
                        connected_components, consensus_residual,
                        simulate_consensus)
from .ego_graph import build_ego_graph
from .epoch import (PHASE_IDLE, EpochState, commit_or_retain, local_recovery_trigger,
                    local_trigger, simulate_confirm_consensus,
                    simulate_trigger_consensus)
from .guards import strict_enabled
from .local_controller import local_controller
from .roles import RoleAssignment
from .system_model import (KEEP, LINE, MODES, CentralizedAccessError, CommParams,
                           ConsensusParams, RobotView)


def nearest_obstacle_clearance(view: RobotView) -> float:
    """Robot i's own minimum obstacle clearance. Local, not the global minimum."""
    if not view.obstacles:
        return float("inf")
    return min(float(np.hypot(ox, oy)) - float(r) for ox, oy, r in view.obstacles)


def _robot_decision(view: RobotView, cfg: Config, selector, mode_rule: str
                    ) -> Tuple[float, float]:
    """Robot i's own pre-consensus (q_keep, q_line). Sees only its RobotView."""
    if mode_rule == "always_keep":
        return (1.0, 0.0)
    if mode_rule == "always_line":
        return (0.0, 1.0)
    if mode_rule == "geometric":
        # Scripted local rule, no learning: propose LINE while robot i's own
        # sensed clearance is tight, KEEP once it has reopened. The epoch
        # protocol decides *when* to ask; this decides *what* to answer.
        c = nearest_obstacle_clearance(view)
        return (0.0, 1.0) if c < 2.0 * cfg.env.nominal_spacing else (1.0, 0.0)
    if selector is None:
        raise ValueError(f"mode_rule={mode_rule!r} requires a selector")
    with torch.no_grad():
        b = lambda g: {"node_x": g.node_x, "edge_index": g.edge_index,
                       "edge_attr": g.edge_attr,
                       "center_index": torch.tensor([g.center_index])}
        return (float(selector.score(b(build_ego_graph(view, cfg, KEEP)))[0]),
                float(selector.score(b(build_ego_graph(view, cfg, LINE)))[0]))


def simulate_decentralized_episode(
    cfg: Config, layout, n: int, seed: int, *,
    selector=None, mode_rule: str = "geometric",
    k_score: Optional[int] = None, use_consensus: bool = True,
    comm: Optional[CommParams] = None, cons: Optional[ConsensusParams] = None,
    role_source: str = "initial_formation",
    forced_mode: Optional[int] = None,
    scripted: Optional[Dict[int, int]] = None,
    legacy_periodic_epoch_baseline: bool = False,
    accountant: Optional[MessageAccountant] = None,
    trace_modes: bool = False,
) -> Dict[str, object]:
    """BOUNDARY: run one closed-loop decentralized episode.

    `scripted` maps a control step to a mode and bypasses the epoch protocol --
    a diagnostic probe for Task 4B, never a deployable path.
    `legacy_periodic_epoch_baseline` restores the removed periodic timer and is
    refused under `strict_decentralized_runtime`.
    """
    if legacy_periodic_epoch_baseline and strict_enabled():
        raise CentralizedAccessError(
            "legacy_periodic_epoch_baseline is a diagnostic reference only and is "
            "unreachable while strict_decentralized_runtime is enabled: it opens "
            "decision epochs on a shared timer, which is a central epoch clock"
        )

    comm = comm or CommParams()
    cons = cons or ConsensusParams()
    k = cons.k_score if k_score is None else int(k_score)
    if not use_consensus:
        k = 0
    acc = accountant if accountant is not None else MessageAccountant(n_robots=n)

    env = SwarmFormationEnv(cfg)
    obs = env.reset(n, "cluttered", seed=seed, layout=layout)
    mission = (float(obs["corridor_dx"]), float(obs["corridor_dy"]))
    roles = (RoleAssignment.simulate_mission_setup_from_initial_formation(
                obs["positions"], mission, cfg.env.nominal_spacing)
             if role_source == "initial_formation"
             else RoleAssignment.from_index(n, cfg.env.nominal_spacing))
    states = make_radio_states(range(n), comm)
    channel = RadioChannel(comm, seed=int(seed))
    acc_ep = EpisodeAccumulator(formation_tolerance=cfg.env.formation_tolerance,
                                dt=cfg.env.dt)

    start_mode = KEEP if forced_mode is None else forced_mode
    epochs = {i: EpochState(robot_id=i) for i in range(n)}
    for e in epochs.values():
        e.committed_mode = start_mode

    agree_full, agree_comp, residuals = [], [], []
    disagreement_events: List[object] = []
    mode_trace: List[Tuple[int, List[int]]] = []
    n_epochs = n_entry = n_recovery = 0
    disagreement_steps = 0
    collisions_during_disagreement = 0
    step, done, last = 0, False, None

    while not done:
        views = simulate_broadcast_round(
            step, obs["positions"], obs["velocities"], roles,
            [epochs[i].committed_mode for i in range(n)],
            [epochs[i].epoch_id for i in range(n)],
            [epochs[i].remaining_commitment for i in range(n)],
            states, channel, obs["obstacles"], cfg.env.obstacle_radius,
            (float(obs["goal"][0]), float(obs["goal"][1])), mission, comm,
            accountant=acc)
        adj = {i: list(views[i].neighbour_ids()) for i in range(n)}

        if forced_mode is None and scripted is None:
            # === 1. robot-local trigger, own sensors only ===================
            armed = False
            for i in range(n):
                e = epochs[i]
                if e.phase != PHASE_IDLE or e.locked:
                    continue
                fired = (local_recovery_trigger(views[i], cfg, e, cons)
                         if e.committed_mode == LINE
                         else local_trigger(views[i], cfg, e, cons))
                if fired:
                    e.arm_trigger(step)
                    armed = True

            if armed:
                n_epochs += 1
                direction_line = sum(
                    1 for i in range(n) if epochs[i].committed_mode == KEEP)
                # === 2. peer-to-peer trigger propagation (max-consensus) ====
                simulate_trigger_consensus(
                    epochs, adj, cons.k_trigger, start_step=step,
                    delta_stale_steps=comm.delta_stale_steps,
                    packet_loss=comm.packet_loss, delay_steps=comm.delay_steps,
                    seed=int(seed) + step, record_history=False, accountant=acc)

                scoring = [i for i in range(n) if epochs[i].trigger_token is not None
                           and not epochs[i].locked]
                for i in scoring:
                    epochs[i].begin_scoring()

                # === 3. leaderless score consensus =========================
                q = {i: _robot_decision(views[i], cfg, selector, mode_rule)
                     for i in scoring}
                nodes = {i: ConsensusNode.from_logits(
                    i, q[i][0], q[i][1], len(adj[i]), epochs[i].epoch_id, cons)
                    for i in scoring}
                if nodes:
                    res = simulate_consensus(
                        nodes, {i: [j for j in adj[i] if j in nodes] for i in nodes},
                        k, start_step=step,
                        delta_stale_steps=comm.delta_stale_steps,
                        packet_loss=comm.packet_loss, delay_steps=comm.delay_steps,
                        seed=int(seed) + step, record_history=False, accountant=acc)
                    comps = connected_components({i: adj[i] for i in nodes})
                    agree_full.append(agreement_rate(res["decisions"]))
                    agree_comp.append(component_agreement(res["decisions"], comps))
                    residuals.append(consensus_residual(nodes))

                    # === 4. peer mode confirmation =========================
                    for i in scoring:
                        epochs[i].begin_confirming(nodes[i].decide(), nodes[i].margin())
                    simulate_confirm_consensus(
                        epochs, adj, cons.k_confirm, start_step=step,
                        delta_stale_steps=comm.delta_stale_steps,
                        packet_loss=comm.packet_loss, delay_steps=comm.delay_steps,
                        seed=int(seed) + step, record_history=False, accountant=acc)

                    # === 5. commit or retain, per robot ====================
                    for i in scoring:
                        before = epochs[i].committed_mode
                        n_dis_before = len(epochs[i].disagreements)
                        ok = commit_or_retain(epochs[i], step, cons)
                        if len(epochs[i].disagreements) > n_dis_before:
                            disagreement_events.append(epochs[i].disagreements[-1])
                        if ok and epochs[i].committed_mode != before:
                            if epochs[i].committed_mode == LINE:
                                n_entry += 1
                            else:
                                n_recovery += 1
                    if trace_modes:
                        mode_trace.append(
                            (step, [epochs[i].committed_mode for i in range(n)]))
                else:
                    for i in range(n):
                        if epochs[i].phase != PHASE_IDLE:
                            epochs[i].close_epoch()

        elif scripted is not None:
            if step in scripted:
                for e in epochs.values():
                    e.committed_mode = scripted[step]
                if trace_modes:
                    mode_trace.append((step, [epochs[i].committed_mode for i in range(n)]))

        for e in epochs.values():
            e.tick()

        committed = [epochs[i].committed_mode for i in range(n)]
        disagree = len(set(committed)) > 1
        disagreement_steps += int(disagree)

        actions = np.stack([local_controller(views[i], cfg, committed[i])
                            for i in range(n)])
        env_mode = Counter(committed).most_common(1)[0][0]   # bookkeeping only
        obs, _, done, last = env.step(actions, env_mode)
        acc_ep.update(last)
        if disagree and last.get("collision", False):
            collisions_during_disagreement += 1
        step += 1

    acc.set_episode_steps(step)
    m = acc_ep.finalize(last)
    return {
        "success": float(m["success"]),
        "collision_free": float(m.get("collision_free", 0.0)),
        "goal_reached": float(m.get("goal_reached", m["success"])),
        "deadlock": float(m.get("deadlock", 0.0)),
        "irreversible_collapse": float(m.get("irreversible_collapse", 0.0)),
        "completion_steps": step,
        "formation_rms_error": float(m.get("formation_rms_error", float("nan"))),
        "time_in_formation_tube": float(m.get("time_in_formation_tube", float("nan"))),
        "full_agreement": float(np.mean(agree_full)) if agree_full else float("nan"),
        "component_agreement": float(np.mean(agree_comp)) if agree_comp else float("nan"),
        "consensus_residual": float(np.mean(residuals)) if residuals else float("nan"),
        "disagreement_fraction": disagreement_steps / max(step, 1),
        "collisions_during_disagreement": collisions_during_disagreement,
        "n_decisions": n_epochs,
        "n_keep_to_line": n_entry,
        "n_line_to_keep": n_recovery,
        "n_disagreement_events": len(disagreement_events),
        "final_modes": [epochs[i].committed_mode for i in range(n)],
        "mode_trace": mode_trace,
        "comm": acc.report(),
    }
