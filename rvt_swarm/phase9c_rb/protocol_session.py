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
    evaluate_lifecycle_status_agreement, evaluate_readiness_agreement,
    evaluate_score_agreement, flood_transition_messages,
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
    # Match the frozen `adopt_intent` precondition exactly rather than being
    # stricter: it permits STABLE_TOPOLOGY, REARMED and COMPLETE. Requiring only
    # STABLE_TOPOLOGY silently blocked any second lifecycle after a completed
    # transition -- including LINE -> COMPACT after S2's forced initialization.
    if robot.protocol_node.state not in ("STABLE_TOPOLOGY", "REARMED", "COMPLETE"):
        return False
    # The frozen `adopt_intent` internally calls `abort("conflicting_lifecycle")`
    # when a node still holds an active intent -- and `abort` raises from
    # COMPLETE. A node in COMPLETE is only genuinely adoptable once `try_rearm`
    # has retired its intent, so require that here rather than letting the
    # frozen guard raise.
    if robot.protocol_node.active_intent is not None:
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
    if event_type != "externally_forced_diagnostic":
        session.topology_selection_epoch_count += 1
    session.event_log.append({
        "control_step": session.control_step, "time_seconds": session.time_seconds,
        "originator": robot.robot_id, "lifecycle_id": lifecycle_id,
        "candidate_topology": candidate_topology, "event_type": event_type,
    })
    return True


# Terminal lifecycle states. A node here has finished its epoch; the frozen
# `try_rearm` is what retires its intent and agreement flags.
_TERMINAL_STATES = ("COMPLETE", "ABORTED", "REARMED", "STABLE_TOPOLOGY")


def _retire_finished_lifecycles(session) -> None:
    """Defect 12: invoke the FROZEN retirement step.

    `mark_complete` advances to COMPLETE but deliberately leaves `active_intent`,
    `_score_agreed`, `_all_ready`, `_confirmed` and the dwell clock latched --
    the frozen `try_rearm` is what clears them, after `rearm_inactive_seconds`.
    The adapter never called it, so a completed epoch kept its intent forever,
    `_active_intent` returned that stale intent, and no second epoch could run.

    This calls the frozen method per robot; it invents no reset rule and applies
    no central shortcut.
    """
    for robot in session.robots:
        if robot.protocol_node.state in ("COMPLETE", "ABORTED"):
            if robot.protocol_node.try_rearm(session.time_seconds):
                robot.transition_executor = None
                robot.transition_source_topology = None
                robot.transition_commit_seconds = None


def _active_intent(session):
    """The intent of a lifecycle that is still running.

    Nodes in a terminal state are skipped: during the rearm window a COMPLETE
    node still holds its finished intent, and driving that would re-run the
    previous epoch.
    """
    for robot in session.robots:
        node = robot.protocol_node
        if node.active_intent is not None and node.state not in _TERMINAL_STATES:
            return node.active_intent
    return None


def advance_transition_lifecycle(session) -> None:
    """Advance every node one protocol phase using the frozen evaluators."""
    _retire_finished_lifecycles(session)
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
        # Adopt from the frozen `adopt_intent` precondition set. After a
        # completed epoch is retired by `try_rearm` a node sits in REARMED, not
        # STABLE_TOPOLOGY, so restricting adoption to STABLE_TOPOLOGY left it
        # without an active lifecycle and the next phase raised
        # "score requires active lifecycle".
        for node in nodes.values():
            if (node.state in ("STABLE_TOPOLOGY", "REARMED", "COMPLETE")
                    and node.active_intent is None):
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
                   for rid, node in nodes.items() if node.active_intent is not None}
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

    # 3. All-ready agreement. Each robot evaluates the AUTHORITATIVE frozen
    # robot-local readiness certificate from its own permitted inputs; no
    # readiness state is asserted, and no central "if all safe then commit"
    # shortcut exists outside the frozen agreement machinery.
    if any(node.state == "ALL_READY_AGREEMENT" for node in nodes.values()):
        # TS-4: a robot that is not yet MOTION_SETTLED has simply not submitted
        # an eligible readiness certificate for this transition stage. The node
        # waits in ALL_READY_AGREEMENT; no timeout is extended and readiness
        # itself is untouched.
        from .staging import motion_settled
        unsettled = [robot.robot_id for robot in session.robots
                     if not motion_settled(robot, session.runtime_config)]
        if unsettled:
            session.unsettled_robots = tuple(unsettled)
            return
        session.unsettled_robots = ()
        certificates = {robot.robot_id: local_readiness_certificate(session, robot, intent)
                        for robot in session.robots}
        session.readiness_certificates = {
            rid: {"readiness_state": c.readiness_state,
                  "readiness_margin_meters": float(c.readiness_margin_meters),
                  "blocking_reasons": list(c.blocking_reasons),
                  "unknown_reasons": list(c.unknown_reasons)}
            for rid, c in certificates.items()}
        initial = {rid: (node.readiness_message(
                       certificates[rid].readiness_state,
                       float(certificates[rid].readiness_margin_meters), now),)
                   for rid, node in nodes.items() if node.active_intent is not None}
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
                   for rid, node in nodes.items() if node.active_intent is not None}
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
                source_topology = int(robot.committed_topology)
                node.commit(now)
                robot.committed_topology = int(node.committed_topology)
                robot.steps_since_decision = 0
                robot.transition_source_topology = source_topology
                robot.transition_commit_seconds = now
                robot.transition_executor = _build_transition_executor(
                    session, robot, source_topology, int(node.committed_topology), now)
                node.begin_execution(now)
        return

    # 5. Execution and target dwell, then DISTRIBUTED completion.
    #
    # Defect 13. The qualified runtime (transition_runtime.py:880-918) does not
    # complete a lifecycle from local dwell alone. Only once every node reports
    # `local_dwell_complete` does each emit
    # `status_message("COMPLETE", "local_target_dwell", now)`; those are flooded
    # over the one-hop graph for `k_confirm_rounds`, and
    # `evaluate_lifecycle_status_agreement(..., "COMPLETE", ...)` decides. On
    # agreement every node calls `mark_complete(completion_agreement_time)`; on
    # disagreement every node aborts with the agreement's own reason.
    if any(node.state in ("TRANSITION_EXECUTION", "TARGET_DWELL")
           for node in nodes.values()):
        inside = _inside_candidate_tube(session, int(intent.candidate_topology))
        for robot in session.robots:
            node = robot.protocol_node
            if robot.transition_executor is not None:
                robot.transition_progress = float(
                    robot.transition_executor.progress(now))
            if node.state in ("TRANSITION_EXECUTION", "TARGET_DWELL"):
                node.observe_target_tube(inside, now)

        if not all(node.local_dwell_complete for node in nodes.values()):
            return                       # local dwell is necessary, not sufficient

        config = session.runtime_config
        completion_messages = {
            rid: (node.status_message("COMPLETE", "local_target_dwell", now),)
            for rid, node in nodes.items()}
        completion_flood = flood_transition_messages(
            member_ids, completion_messages, adjacency,
            int(config.derived.k_confirm_rounds))
        completion_agreement_time = (
            now + config.derived.k_confirm_rounds
            * config.communication.communication_period_seconds)
        agreement = evaluate_lifecycle_status_agreement(
            completion_flood, member_ids, intent, "COMPLETE",
            now_seconds=completion_agreement_time,
            maximum_age_seconds=(
                config.derived.k_confirm_rounds
                * config.communication.communication_period_seconds
                + config.communication.maximum_message_age_seconds))
        session.completion_agreements.append({
            "lifecycle_id": int(intent.lifecycle_id),
            "epoch_id": int(intent.epoch_id),
            "agreed": bool(agreement.agreed),
            "reason": agreement.reason,
            "local_dwell_complete_time_seconds": float(now),
            "status_agreement_time_seconds": float(completion_agreement_time),
            "control_step": int(session.control_step),
        })
        if agreement.agreed:
            for robot in session.robots:
                robot.protocol_node.mark_complete(completion_agreement_time)
                robot.transition_executor = None
            return
        for robot in session.robots:
            if robot.protocol_node.state not in ("STABLE_TOPOLOGY", "COMPLETE", "REARMED"):
                robot.protocol_node.abort(agreement.reason, completion_agreement_time)
                robot.transition_executor = None
        return


def _abort_all(session, nodes, cause: str) -> None:
    # The frozen node refuses to abort from COMPLETE or REARMED, and there is
    # nothing to abort from STABLE_TOPOLOGY. Honour that precondition exactly
    # rather than forcing a state change the protocol forbids.
    for robot in session.robots:
        if robot.protocol_node.state in ("STABLE_TOPOLOGY", "COMPLETE", "REARMED"):
            continue
        robot.protocol_node.abort(cause, session.time_seconds)
        robot.transition_executor = None


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


def _build_transition_executor(session, robot, source_topology: int,
                               target_topology: int, now_seconds: float):
    """Bind the FROZEN generic role-space profile for one robot.

    Everything here is a call into `transition_execution`; no interpolation
    equation, displacement rule or progress law is restated in this package.
    """
    import math

    from ..decentralized.transition_execution import (
        RobotLocalTransitionExecutor, derive_transition_motion_profile,
        prepare_robot_local_role_space_path,
    )
    path = prepare_robot_local_role_space_path(
        session.role_set, robot.robot_id, session.runtime_config.formation,
        source_topology, target_topology)
    displacement = math.dist(path.source_role_offset_meters,
                             path.target_role_offset_meters)
    if displacement <= 0.0:
        return None                      # this role does not move; nothing to profile
    profile = derive_transition_motion_profile(displacement, session.runtime_config)
    return RobotLocalTransitionExecutor(
        session.runtime_config, robot.local_topology_metadata, path, profile,
        now_seconds)


def local_readiness_certificate(session, robot, intent):
    """The frozen robot-local readiness certificate for one robot.

    `evaluate_robot_local_transition_readiness` is genuinely robot-local: its
    input carries own state, own source/target role slices, ego-relative peer
    and obstacle observations and local projection flags -- never joint state,
    never the layout, never a global formation error.
    """
    from ..decentralized.transition_readiness import (
        RobotLocalTransitionInput, evaluate_robot_local_transition_readiness,
    )
    view = session._build_robot_view(robot)
    adapter = robot.adapter_by_topology[int(intent.source_topology)]
    controller_input = adapter.build_input(view, session.time_seconds)
    dynamic_states = session._dynamic_obstacle_relative_states(robot)
    obstacles = controller_input.obstacle_states + dynamic_states
    output = adapter.controller.evaluate(controller_input)
    metadata = robot.local_topology_metadata
    local_input = RobotLocalTransitionInput(
        observer_robot_id=robot.robot_id,
        observer_role_id=metadata.observer_role_id,
        team_size=session.team_size,
        timestamp_seconds=float(session.time_seconds),
        lifecycle_id=int(intent.lifecycle_id),
        epoch_id=int(intent.epoch_id),
        committed_topology_id=int(robot.committed_topology),
        source_topology_id=int(intent.source_topology),
        candidate_topology_id=int(intent.candidate_topology),
        mission_direction=tuple(map(float, view.mission_dir)),
        own_position_meters=tuple(map(float, robot.position)),
        own_velocity_meters_per_second=tuple(map(float, robot.velocity)),
        source_topology=metadata.candidate(int(intent.source_topology)),
        target_topology=metadata.candidate(int(intent.candidate_topology)),
        peer_states=controller_input.peer_states,
        obstacle_states=obstacles,
        observed_extent_meters=float(
            session.runtime_config.sensing.obstacle_sensing_range_meters),
        projection_infeasible=bool(output.projection_infeasible),
        projection_solver_failed=bool(output.projection_solver_failed),
        projection_failure_persistent=bool(robot.safety_unresolved),
        proposed_action_meters_per_second_squared=tuple(
            map(float, output.projected_action)),
    )
    session.readiness_evaluation_count += 1
    return evaluate_robot_local_transition_readiness(
        local_input, session.runtime_config)
