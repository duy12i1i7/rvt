"""Phase 7 session adapter (RB-6).

Additive. It manages *when* the frozen protocol is invoked and *which serialized
messages reach whom*; it never decides anything the protocol decides.

Permitted here: per-control-step invocation, message delivery over the current
one-hop graph, lifecycle initialization, candidate injection for offline
counterfactual evaluation, timeout propagation, completion observation.

Forbidden here, and absent: central candidate selection, central readiness
computation, altered score aggregation, altered confirmation, altered
commitment, altered profile, altered abort/rearm, or one global lifecycle state
written into every robot. Each robot owns a `TransitionProtocolNode`; agreement
is evaluated by each node from its own received set using the frozen
`evaluate_*` functions.
"""

from __future__ import annotations

from typing import Dict, List, Mapping, Optional, Sequence, Tuple

from ..decentralized.transition_protocol import (
    evaluate_confirmation_agreement, evaluate_intent_propagation,
    evaluate_readiness_agreement, evaluate_score_agreement,
    flood_transition_messages,
)
from ..topology_registry import COMPACT, LINE

DIAGNOSTIC_SCORE = 1.0
# Frozen vocabulary: SCORE_SEMANTICS = (probability_like, bounded_diagnostic,
# unavailable). S4's contract calls for a bounded diagnostic score of 1.0.
DIAGNOSTIC_SCORE_SEMANTICS = "bounded_diagnostic"


def _adjacency(session) -> Dict[int, Tuple[int, ...]]:
    """Current one-hop graph, range-gated and cut-aware.

    The F8 partition is applied here so the protocol experiences exactly the
    declared assumption violation rather than a separate abstract fixture cut.
    """
    channel = session.channel
    cut_active = channel.cut_active_at(channel.tick)
    adjacency: Dict[int, Tuple[int, ...]] = {}
    for robot in session.robots:
        peers: List[int] = []
        for other in session.robots:
            if other.robot_id == robot.robot_id:
                continue
            if not channel.physical_edge(robot.position, other.position):
                continue
            if cut_active and channel.crosses_cut(robot.robot_id, other.robot_id):
                continue
            peers.append(other.robot_id)
        adjacency[robot.robot_id] = tuple(peers)
    return adjacency


def originate_candidate(session, robot, candidate_topology: int, event_type: str) -> bool:
    """One robot originates on its own evidence. Adoption suppresses later origins."""
    if candidate_topology not in (COMPACT, LINE):
        return False
    if robot.protocol_node.state != "STABLE_TOPOLOGY":
        return False
    if candidate_topology == robot.committed_topology:
        return False                      # no source-equals-target epoch, ever
    session.lifecycle_counter += 1
    lifecycle_id = session.lifecycle_counter
    intent = robot.protocol_node.request_intent(
        lifecycle_id, candidate_topology, event_type, session.time_seconds)
    if intent is None:
        return False
    # The frozen `request_intent` only *constructs* the intent; entering
    # INTENT_ACTIVE is `adopt_intent`. The originator adopts its own intent
    # first, exactly as every peer will. Without this the node stays in
    # STABLE_TOPOLOGY, `_active_intent` finds nothing, and the whole lifecycle
    # silently never advances.
    if not robot.protocol_node.adopt_intent(intent, session.time_seconds):
        return False
    session.event_log.append({
        "control_step": session.control_step, "time_seconds": session.time_seconds,
        "originator": robot.robot_id, "lifecycle_id": lifecycle_id,
        "candidate_topology": candidate_topology, "event_type": event_type,
    })
    return True


def _active_intent(session):
    for robot in session.robots:
        if robot.protocol_node.active_intent is not None:
            return robot.protocol_node.active_intent
    return None


def advance_transition_lifecycle(session) -> None:
    """Advance every node one protocol phase using the frozen evaluators."""
    intent = _active_intent(session)
    if intent is None:
        return

    member_ids = tuple(range(len(session.robots)))
    adjacency = _adjacency(session)
    rounds = int(session.runtime_config.derived.k_intent_rounds)
    now = session.time_seconds
    maximum_age = float(session.runtime_config.communication.maximum_message_age_seconds)

    nodes = {robot.robot_id: robot.protocol_node for robot in session.robots}

    # 1. Intent propagation and adoption.
    if any(node.state == "INTENT_ACTIVE" for node in nodes.values()):
        flood = flood_transition_messages(
            member_ids, {intent.originator_robot_id: (intent,)}, adjacency, rounds)
        result = evaluate_intent_propagation(
            flood, member_ids, now_seconds=now, maximum_age_seconds=maximum_age)
        for node in nodes.values():
            if node.state == "STABLE_TOPOLOGY":
                node.adopt_intent(intent, now)
        if result.agreed:
            for node in nodes.values():
                if node.state == "INTENT_ACTIVE":
                    node.begin_score_agreement(now)
        else:
            _abort_all(session, nodes, "INTENT_PROPAGATION_INCOMPLETE")
        return

    # 2. Score agreement -- every node emits its own score.
    if any(node.state == "CANDIDATE_SCORE_AGREEMENT" for node in nodes.values()):
        initial = {rid: (node.score_message(DIAGNOSTIC_SCORE, DIAGNOSTIC_SCORE_SEMANTICS, now),)
                   for rid, node in nodes.items()}
        flood = flood_transition_messages(member_ids, initial, adjacency, rounds)
        result = evaluate_score_agreement(
            flood, member_ids, intent, now_seconds=now, maximum_age_seconds=maximum_age,
            threshold=float(nodes[0].options.deterministic_score_threshold))
        for node in nodes.values():
            node.accept_score_agreement(result, now)
        if not result.agreed:
            _abort_all(session, nodes, "SCORE_AGREEMENT_FAILED")
        else:
            for node in nodes.values():
                if node.state == "WAITING_FOR_LOCAL_READINESS":
                    node.begin_all_ready_agreement(now)
        return

    # 3. All-ready agreement.
    if any(node.state == "ALL_READY_AGREEMENT" for node in nodes.values()):
        initial = {rid: (node.readiness_message("SAFE", 0.0, now),)
                   for rid, node in nodes.items()}
        flood = flood_transition_messages(member_ids, initial, adjacency, rounds)
        result = evaluate_readiness_agreement(
            flood, member_ids, intent, now_seconds=now, maximum_age_seconds=maximum_age)
        for node in nodes.values():
            node.accept_all_ready(result, now)
        if not result.agreed:
            _abort_all(session, nodes, "READINESS_AGREEMENT_FAILED")
        return

    # 4. Confirmation, then per-node commit.
    if any(node.state == "TOPOLOGY_CONFIRMATION" for node in nodes.values()):
        initial = {rid: (node.confirmation_message("ACCEPT", now),)
                   for rid, node in nodes.items()}
        flood = flood_transition_messages(member_ids, initial, adjacency, rounds)
        result = evaluate_confirmation_agreement(
            flood, member_ids, intent, now_seconds=now, maximum_age_seconds=maximum_age)
        for node in nodes.values():
            node.accept_confirmation(result, now)
        if not result.agreed:
            _abort_all(session, nodes, "CONFIRMATION_FAILED")
            return
        # `accept_confirmation` only records unanimity; `commit` is the frozen
        # call that advances to TOPOLOGY_COMMITTED and bumps the epoch. Each
        # node commits for itself -- nothing is written centrally.
        for robot in session.robots:
            node = robot.protocol_node
            if node.state == "TOPOLOGY_CONFIRMATION":
                node.commit(now)
                robot.committed_topology = int(node.committed_topology)
                robot.steps_since_decision = 0
                node.begin_execution(now)
        return

    # 5. Execution and target dwell, judged by Metric V3 per robot.
    if any(node.state in ("TRANSITION_EXECUTION", "TARGET_DWELL") for node in nodes.values()):
        inside = _inside_candidate_tube(session, int(intent.candidate_topology))
        for robot in session.robots:
            node = robot.protocol_node
            robot.transition_progress = 1.0 if inside else robot.transition_progress
            if node.state in ("TRANSITION_EXECUTION", "TARGET_DWELL"):
                if node.observe_target_tube(inside, now):
                    node.mark_complete(now)
        return


def _abort_all(session, nodes, cause: str) -> None:
    for node in nodes.values():
        if node.state not in ("STABLE_TOPOLOGY", "COMPLETE"):
            node.abort(cause, session.time_seconds)


def _inside_candidate_tube(session, candidate_topology: int) -> bool:
    """Metric V3 tube membership for the candidate topology.

    Offline evaluator scope: it reads the joint state, which
    `formation_metric_v3` explicitly permits and `guards.OFFLINE_MODULES`
    records. No robot receives this value.
    """
    import numpy as np

    from ..decentralized.formation_metric_v3 import EPSILON_FORM
    from ..decentralized.roles import rotation

    positions = np.asarray([robot.position for robot in session.robots], dtype=np.float64)
    template = np.asarray([robot.role_offset(candidate_topology) for robot in session.robots],
                          dtype=np.float64)
    template = template - template.mean(axis=0)
    centre = positions.mean(axis=0)
    rotated = (rotation(session.mission_direction).astype(np.float64) @ template.T).T
    errors = np.linalg.norm((positions - centre) - rotated, axis=1)
    return bool(errors.max() <= EPSILON_FORM)
