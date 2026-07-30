"""The deployable decentralized runtime loop.

For every robot i, independently, once per control step:

  1 discover direct neighbours        6 exchange scores with direct neighbours
  2 receive fresh one-hop messages    7 execute leaderless finite-round consensus
  3 observe local obstacles           8 confirm mode peer-to-peer
  4 construct ego graph G_i           9 commit locally to keep or line
  5 estimate keep/line scores        10 compute its own action u_i
                                     11 send only its own command to its actuator

No central entity appears in that loop. `simulate_decentralized_episode` below
is the harness that steps the simulator and the radio; it is boundary code. The
per-robot decisions inside it are computed by `_robot_decision`, which sees one
`RobotView` and nothing else.

What the environment API forces us to concede, stated plainly: `env.step` takes
a SINGLE `topology_action` for the whole team, because the simulator was written
for a centralized controller. The robots' actions are computed individually and
that argument does not affect the physics of those actions -- it drives the
simulator's own formation bookkeeping. We pass the majority committed mode for
that bookkeeping and record disagreement separately. This is a simulator
interface artefact, not a coordination channel: no robot reads it.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import torch

from ..config import Config
from ..environment import SwarmFormationEnv
from ..metrics import EpisodeAccumulator
from .comms import RadioChannel, make_radio_states, simulate_broadcast_round
from .consensus import (ConsensusNode, agreement_rate, component_agreement,
                        connected_components, consensus_residual,
                        simulate_consensus)
from .ego_graph import build_ego_graph
from .local_controller import local_controller
from .roles import RoleAssignment
from .system_model import (KEEP, LINE, MODES, CommParams, ConsensusParams,
                           RobotView)


def nearest_obstacle_clearance(view: RobotView) -> float:
    """Robot i's own minimum obstacle clearance. Local, not the global minimum."""
    if not view.obstacles:
        return float("inf")
    return min(float(np.hypot(ox, oy)) - float(r) for ox, oy, r in view.obstacles)


def _robot_decision(view: RobotView, cfg: Config, selector, mode_rule: str) -> Tuple[float, float]:
    """Robot i's own pre-consensus (q_keep, q_line). Sees only its RobotView."""
    if mode_rule == "always_keep":
        return (1.0, 0.0)
    if mode_rule == "always_line":
        return (0.0, 1.0)
    if mode_rule == "clearance":
        # Communication-free local heuristic: go single file when robot i's own
        # sensed clearance is tight relative to the formation width it needs.
        c = nearest_obstacle_clearance(view)
        tight = c < 2.0 * cfg.env.nominal_spacing
        return (0.0, 1.0) if tight else (1.0, 0.0)
    with torch.no_grad():
        gk = build_ego_graph(view, cfg, KEEP)
        gl = build_ego_graph(view, cfg, LINE)
        b = lambda g: {"node_x": g.node_x, "edge_index": g.edge_index,
                       "edge_attr": g.edge_attr,
                       "center_index": torch.tensor([g.center_index])}
        return (float(selector.score(b(gk))[0]), float(selector.score(b(gl))[0]))


def simulate_decentralized_episode(
    cfg: Config, layout, n: int, seed: int, *,
    selector=None, mode_rule: str = "learned",
    k_score: int = 4, use_consensus: bool = True,
    comm: Optional[CommParams] = None,
    cons: Optional[ConsensusParams] = None,
    decision_interval: int = 25,
    role_source: str = "initial_formation",
    forced_mode: Optional[int] = None,
) -> Dict[str, object]:
    """BOUNDARY: run one closed-loop decentralized episode.

    `use_consensus=False` runs the identical pipeline with K=0, i.e. every robot
    decides from its own logits alone -- the reference arm for Gate D3.
    """
    comm = comm or CommParams()
    cons = cons or ConsensusParams()
    env = SwarmFormationEnv(cfg)
    obs = env.reset(n, "cluttered", seed=seed, layout=layout)
    mission = (float(obs["corridor_dx"]), float(obs["corridor_dy"]))
    roles = (RoleAssignment.simulate_mission_setup_from_initial_formation(
                obs["positions"], mission, cfg.env.nominal_spacing)
             if role_source == "initial_formation"
             else RoleAssignment.from_index(n, cfg.env.nominal_spacing))
    states = make_radio_states(range(n), comm)
    channel = RadioChannel(comm, seed=int(seed))
    acc = EpisodeAccumulator(formation_tolerance=cfg.env.formation_tolerance, dt=cfg.env.dt)

    committed = [KEEP] * n if forced_mode is None else [forced_mode] * n
    epoch_ids = [0] * n
    since = [0] * n
    agree_full, agree_comp, residuals, decisions_log = [], [], [], []
    disagreement_steps = 0
    collisions_during_disagreement = 0
    step, done, last = 0, False, None

    while not done:
        views = simulate_broadcast_round(
            step, obs["positions"], obs["velocities"], roles, committed, epoch_ids,
            since, states, channel, obs["obstacles"], cfg.env.obstacle_radius,
            (float(obs["goal"][0]), float(obs["goal"][1])), mission, comm)
        adj = {i: list(views[i].neighbour_ids()) for i in range(n)}

        if forced_mode is None and step % decision_interval == 0:
            q = {i: _robot_decision(views[i], cfg, selector, mode_rule) for i in range(n)}
            nodes = {i: ConsensusNode.from_logits(i, q[i][0], q[i][1],
                                                  len(adj[i]), epoch_ids[i], cons)
                     for i in range(n)}
            k = k_score if use_consensus else 0
            res = simulate_consensus(nodes, adj, k, start_step=step,
                                     delta_stale_steps=comm.delta_stale_steps,
                                     packet_loss=comm.packet_loss,
                                     delay_steps=comm.delay_steps,
                                     seed=int(seed) + step, record_history=False)
            committed = [res["decisions"][i] for i in range(n)]
            comps = connected_components(adj)
            agree_full.append(agreement_rate(res["decisions"]))
            agree_comp.append(component_agreement(res["decisions"], comps))
            residuals.append(consensus_residual(nodes))
            decisions_log.append(dict(res["decisions"]))
            epoch_ids = [e + 1 for e in epoch_ids]
            since = [0] * n
        else:
            since = [s + 1 for s in since]

        disagree = len(set(committed)) > 1
        disagreement_steps += int(disagree)

        actions = np.stack([local_controller(views[i], cfg, committed[i])
                            for i in range(n)])
        env_mode = Counter(committed).most_common(1)[0][0]   # bookkeeping only
        obs, _, done, last = env.step(actions, env_mode)
        acc.update(last)
        if disagree and last.get("collision", False):
            collisions_during_disagreement += 1
        step += 1

    m = acc.finalize(last)
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
        "n_decisions": len(decisions_log),
        "final_modes": list(committed),
    }
