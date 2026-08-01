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
from .epoch import (PHASE_IDLE, EpochState, commit_or_retain,
                    latched_local_trigger, latched_local_trigger_v3,
                    local_recovery_trigger,
                    local_trigger, note_transition, requested_mode_for,
                    simulate_confirm_consensus, simulate_trigger_consensus,
                    update_passage_latch)
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
        # G5 REPAIR. The literal factor 2.0 is gone. The threshold is the
        # DERIVED lookahead distance: braking distance at the current speed
        # plus the ground covered while the distributed protocol runs, capped
        # at the sensor range. See docs/LOOKAHEAD_DISTANCE_DERIVATION.md.
        from .parameters import default_parameters, derived_lookahead_distance
        platform, mission, protocol = default_parameters(cfg.env)
        lookahead = derived_lookahead_distance(platform, mission, protocol)
        c = nearest_obstacle_clearance(view)
        return (0.0, 1.0) if c < lookahead else (1.0, 0.0)
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
    scripted_planes: Optional[Tuple[float, float, float]] = None,
    legacy_periodic_epoch_baseline: bool = False,
    accountant: Optional[MessageAccountant] = None,
    trace_modes: bool = False,
    trace_positions: bool = False,
    recovery_event: str = "v3",
    preset_env=None,
    preset_obs=None,
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

    # `preset_env`/`preset_obs` let a qualification fixture install a valid
    # initial condition (robots on the KEEP role template) before t = 0. It is
    # initialization, not control: the loop below is unchanged.
    if preset_env is not None and preset_obs is not None:
        env, obs = preset_env, preset_obs
    else:
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
    pos_trace: List[np.ndarray] = []
    mode_per_step: List[int] = []
    n_epochs = n_entry = n_recovery = n_noop = 0
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

        if forced_mode is None and scripted is None and scripted_planes is None:
            # === 1. robot-local trigger, own sensors only ===================
            armed = False
            for i in range(n):
                e = epochs[i]
                if e.phase != PHASE_IDLE or e.locked:
                    continue
                # Latched trigger: the passage lifecycle decides WHICH
                # direction may fire, and suppresses a direction that has
                # already completed for this bottleneck (Task 5-7).
                trig = (latched_local_trigger_v3 if recovery_event == "v3"
                        else latched_local_trigger)
                fired = trig(views[i], cfg, e, cons)
                if fired:
                    # Local no-op pre-arm check. Robot i evaluates its OWN
                    # proposal from its OWN view and declines to open an epoch
                    # to propose the mode it already holds. Entirely local --
                    # the same computation the epoch would perform anyway -- and
                    # it is what removes the residual no-op epochs the latch
                    # cannot see (a legitimate trigger reason firing where the
                    # answer happens to be "no change").
                    # The check must use the mode the EVENT requests, not a
                    # re-derivation from a second signal. Using
                    # `_robot_decision` here re-introduced exactly the defect
                    # Task 6R repaired, one layer earlier: a robot with valid
                    # forward-opening evidence at step 46 had its arming
                    # cancelled because `nearest_obstacle_clearance` (0.872 m,
                    # still between the walls) said LINE -- the mode it already
                    # held. The traced protocol commits at 45-46; the runtime
                    # was committing at 73-88 purely because of this line.
                    own = requested_mode_for(e)
                    if own is None or own == e.committed_mode:
                        e.suppressed_noop_arm += 1
                        fired = False
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
                # The proposal must be the mode the firing EVENT requested.
                # For the scripted geometric policy the event type IS the
                # decision, so re-deriving it from a second, lagging signal
                # only discards valid epochs (see epoch.latched_local_trigger_v3).
                # A learned selector still scores freely -- this branch is the
                # scripted diagnostic path only.
                q = {}
                for i in scoring:
                    req = requested_mode_for(epochs[i])
                    if mode_rule == "geometric" and req is not None:
                        q[i] = (1.0, 0.0) if req == KEEP else (0.0, 1.0)
                    else:
                        q[i] = _robot_decision(views[i], cfg, selector, mode_rule)
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

                    # === 3b. no-op guard ===================================
                    # If every scoring robot's post-consensus proposal already
                    # equals its committed mode, the epoch cannot change
                    # anything. Closing it here skips the confirmation round
                    # entirely. Measured churn before this guard was 16.2
                    # epochs per corridor traversal against an ideal of 2, with
                    # 26 % of protocol bytes spent on epochs that changed no
                    # mode. This does NOT suppress legitimate retries: an epoch
                    # whose proposal differs from the committed mode still runs
                    # confirmation, and a confirmation failure still retains and
                    # records a disagreement.
                    if all(nodes[i].decide() == epochs[i].committed_mode
                           for i in scoring):
                        n_noop += 1
                        for i in scoring:
                            epochs[i].close_epoch()
                            epochs[i].remaining_commitment = max(
                                epochs[i].remaining_commitment, cons.h_commit)
                        step += 0   # fall through to the control update
                    else:
                        # === 4. peer mode confirmation =====================
                        for i in scoring:
                            epochs[i].begin_confirming(nodes[i].decide(), nodes[i].margin())
                        simulate_confirm_consensus(
                            epochs, adj, cons.k_confirm, start_step=step,
                            delta_stale_steps=comm.delta_stale_steps,
                            packet_loss=comm.packet_loss,
                            delay_steps=comm.delay_steps,
                            seed=int(seed) + step, record_history=False,
                            accountant=acc)

                        # === 5. commit or retain, per robot ================
                        for i in scoring:
                            before = epochs[i].committed_mode
                            n_dis_before = len(epochs[i].disagreements)
                            ok = commit_or_retain(epochs[i], step, cons)
                            if len(epochs[i].disagreements) > n_dis_before:
                                disagreement_events.append(
                                    epochs[i].disagreements[-1])
                            if ok and epochs[i].committed_mode != before:
                                note_transition(epochs[i],
                                                epochs[i].committed_mode)
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

        elif scripted_planes is not None:
            # DIAGNOSTIC policy P3/P4: scripted transitions at the KNOWN
            # GEOMETRIC PLANES, reacting to the team's actual position. Uses
            # global position and is therefore NOT deployable -- it is the
            # reference against which the deployable event-triggered policy is
            # measured. A precomputed step schedule cannot serve here: the step
            # at which the team clears the exit depends on the mode it is in,
            # so a schedule taken from a different policy's probe commands the
            # return while the team is still inside the passage.
            entry_x, exit_x, lookahead = scripted_planes
            ax = np.asarray(mission, dtype=np.float64)
            ax = ax / max(float(np.linalg.norm(ax)), 1e-9)
            along = obs["positions"] @ ax
            want = KEEP
            if float(along.max()) >= entry_x - lookahead:
                want = LINE
            if float(along.min()) >= exit_x:
                want = KEEP if scripted is None else scripted.get("return", KEEP)
            for e in epochs.values():
                if e.committed_mode != want:
                    e.committed_mode = want
                    if trace_modes:
                        mode_trace.append(
                            (step, [epochs[i].committed_mode for i in range(n)]))

        elif scripted is not None:
            if step in scripted:
                for e in epochs.values():
                    e.committed_mode = scripted[step]
                if trace_modes:
                    mode_trace.append((step, [epochs[i].committed_mode for i in range(n)]))

        for i, e in epochs.items():
            if forced_mode is None and scripted is None and scripted_planes is None:
                update_passage_latch(e, views[i], cfg, cons)
            e.tick()

        committed = [epochs[i].committed_mode for i in range(n)]
        disagree = len(set(committed)) > 1
        disagreement_steps += int(disagree)

        if trace_positions:
            pos_trace.append(obs["positions"].copy())
            mode_per_step.append(Counter(committed).most_common(1)[0][0])
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
        "n_noop_epochs": n_noop,
        "suppressed_entry": sum(e.suppressed_entry for e in epochs.values()),
        "suppressed_recovery": sum(e.suppressed_recovery for e in epochs.values()),
        "suppressed_noop_arm": sum(e.suppressed_noop_arm for e in epochs.values()),
        "passage_latch": [epochs[i].passage_latch for i in range(n)],
        "n_keep_to_line": n_entry,
        "n_line_to_keep": n_recovery,
        "n_disagreement_events": len(disagreement_events),
        "final_modes": [epochs[i].committed_mode for i in range(n)],
        "mode_trace": mode_trace,
        "position_trace": pos_trace,
        "mode_per_step": mode_per_step,
        "obstacles": obs["obstacles"].copy(),
        "mission_dir": mission,
        "goal": (float(obs["goal"][0]), float(obs["goal"][1])),
        "comm": acc.report(),
    }
