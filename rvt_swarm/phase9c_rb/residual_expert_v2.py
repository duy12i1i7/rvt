"""RB-15 V2 -- the publication residual-expert producer.

This is the piece RB-15 found missing: the thing that *produces*
`LocalActionEvaluation` records for the unchanged frozen selector. Everything it
does is fixed by `results/rvt_fd24/residual_expert_spec_v2.json`; nothing here
reinterprets that specification.

    snapshot -> RobotView -> Phase-6 base action -> 9 residual candidates
    -> one-control-interval intervention at the pre-safety boundary
    -> matched continuation to ordinary termination -> utility reduction
    -> LocalActionEvaluation -> frozen V1 selector -> frozen V1 target builder

Two boundaries are load-bearing and are therefore never re-implemented here:

* the candidate residual is injected through `SourcePolicy.acceleration_disturbance`,
  which the runtime adds to `base_action` *before* the unchanged safety
  projection -- the exact insertion point the V2 erratum fixes;
* the four utility scalars come from `rvt_swarm.phase8r.utility_v2`, the frozen
  reducers, applied to the single matched counterfactual trace.

`robot_local_information_only` is *derived* from recorded provenance. It is
never assigned a literal.
"""

from __future__ import annotations

import copy
import math
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from ..decentralized.robot_local_controller import robot_local_formation_term
from ..fd24.configuration import FD24ModelConfig, residual_action_limits
from ..phase8.targets import (
    LocalActionEvaluation, ResidualActionTarget, build_residual_action_target,
    select_counterfactual_local_action,
)
from ..phase8r import (
    CANDIDATE_COUNT, UTILITY_INFORMATION_CLASS, canonical_lattice_hash,
    residual_candidate_lattice, zero_residual_index,
)
from ..phase8r import utility_v2
from ..runtime_configuration import RuntimeConfig
from .counterfactual import canonical_sha256, snapshot
from .world import _moving_point_min_distance

Vec2 = Tuple[float, float]

RESIDUAL_EXPERT_V2_PRODUCER_SCHEMA_VERSION = "rvt-rb15-v2-producer/v1"

# ---------------------------------------------------------------------------
# RB15V2-3 -- action-side provenance
# ---------------------------------------------------------------------------
ALLOWED_ACTION_PROVENANCE: Tuple[str, ...] = (
    "SELF_LOCAL",
    "ONE_HOP_LOCAL",
    "LOCAL_OBSTACLE",
    "LOCAL_PROTOCOL_STATE",
    "LOCAL_CONTROLLER_DERIVED",
    "LOCAL_SAFETY_DERIVED",
    "IMMUTABLE_FROZEN_CONFIG",
)

FORBIDDEN_ACTION_PROVENANCE: Tuple[str, ...] = (
    "GLOBAL_STATE",
    "NON_NEIGHBOR_STATE",
    "OFFLINE_LABEL_ORACLE",
    "FINAL_OUTCOME",
    "SEALED_LABEL",
)


class ResidualExpertV2Error(RuntimeError):
    """The producer refuses to invent a value the specification does not define."""


@dataclass
class CandidateActionProvenance:
    """Every input used to *construct* a candidate action, with its class.

    `robot_local_information_only` is a property computed from these records.
    There is deliberately no setter: a caller cannot assert locality.
    """

    records: Dict[str, str] = field(default_factory=dict)

    def record(self, field_name: str, source_class: str) -> None:
        known = set(ALLOWED_ACTION_PROVENANCE) | set(FORBIDDEN_ACTION_PROVENANCE)
        if source_class not in known:
            raise ResidualExpertV2Error(
                f"unknown action provenance class {source_class!r}")
        previous = self.records.get(field_name)
        if previous is not None and previous != source_class:
            raise ResidualExpertV2Error(
                f"conflicting provenance for {field_name!r}: {previous} vs {source_class}")
        self.records[field_name] = source_class

    @property
    def forbidden_sources(self) -> Tuple[str, ...]:
        return tuple(sorted({
            f"{name}:{cls}" for name, cls in self.records.items()
            if cls in FORBIDDEN_ACTION_PROVENANCE
        }))

    @property
    def robot_local_information_only(self) -> bool:
        if not self.records:
            raise ResidualExpertV2Error(
                "provenance is empty; locality cannot be certified by default")
        return not self.forbidden_sources

    def as_dict(self) -> Dict[str, str]:
        return dict(sorted(self.records.items()))


# ---------------------------------------------------------------------------
# one-control-interval residual injection at the pre-safety boundary
# ---------------------------------------------------------------------------
class _OneIntervalResidualPolicy:
    """Delegating wrapper that adds the candidate residual for exactly one step.

    The runtime adds `acceleration_disturbance` to `base_action` and re-projects,
    which is precisely `local_safety_projection(u_base_pre_safety + delta)`. The
    wrapper is transparent for every other robot, every other control step and
    every other policy method, so the counterfactual is the ordinary frozen
    policy everywhere else.

    `applied_control_steps` is the behavioural spy RB15V2-10 requires.
    """

    def __init__(self, inner: Any, robot_id: int, delta_u_world: Vec2,
                 intervention_control_step: int) -> None:
        self._inner = inner
        self._robot_id = int(robot_id)
        self._delta = (float(delta_u_world[0]), float(delta_u_world[1]))
        self._intervention_control_step = int(intervention_control_step)
        self.applied_control_steps: List[int] = []

    # -- the one method whose behaviour changes ---------------------------
    def acceleration_disturbance(self, session, robot) -> Vec2:
        inner = self._inner.acceleration_disturbance(session, robot)
        if (robot.robot_id != self._robot_id
                or session.control_step != self._intervention_control_step):
            return inner
        self.applied_control_steps.append(int(session.control_step))
        return (float(inner[0]) + self._delta[0], float(inner[1]) + self._delta[1])

    # -- everything else is the frozen policy -----------------------------
    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


# ---------------------------------------------------------------------------
# trace sampling (RB15V2-15/17/18)
# ---------------------------------------------------------------------------
def _formation_error_meters(session, robot, runtime_config: RuntimeConfig) -> Vec2:
    """The authoritative Phase-6 per-robot formation-error 2-vector, in metres.

    `robot_local_formation_term` returns `mean(residual)/spacing * a_max * gain`
    with no clipping, so the mean residual is recovered exactly by dividing by
    that frozen magnitude. The equation itself is never restated here.
    """
    _, controller_input, _ = session.local_decision_inputs(robot)
    term, _used, _missing = robot_local_formation_term(controller_input, runtime_config)
    magnitude = (
        float(runtime_config.physical.maximum_acceleration_meters_per_second_squared)
        * float(runtime_config.controller.formation_gain))
    if magnitude <= 0.0:
        raise ResidualExpertV2Error(
            "the frozen formation magnitude is zero; the residual cannot be inverted")
    spacing = float(runtime_config.formation.nominal_spacing_meters)
    return (float(term[0]) / magnitude * spacing, float(term[1]) / magnitude * spacing)


def _clearance_constraints(session, robot_index: int,
                           previous_positions: Sequence[Vec2]) -> List[Tuple[float, float]]:
    """Applicable `(distance, minimum_admissible)` pairs for one control interval.

    Exactly the four constraint classes the V2 specification freezes, each with
    the distance definition and threshold the frozen collision truth uses.
    Boundary exit is deliberately not one of them.
    """
    static = session.static_world
    dynamic = session.dynamic_world
    robot = session.robots[robot_index]
    start, end = previous_positions[robot_index], robot.position
    constraints: List[Tuple[float, float]] = []

    # ROBOT_ROBOT -- swept minimum centre-to-centre distance, always applicable.
    threshold = float(session.runtime_config.derived.robot_robot_required_clearance_meters)
    for other_index, other in enumerate(session.robots):
        if other_index == robot_index:
            continue
        distance = _moving_point_min_distance(
            start, end, previous_positions[other_index], other.position)
        constraints.append((float(distance), threshold))

    # ROBOT_STATIC_CIRCLE -- centre-to-centre distance at the post-step state.
    for circle in static.circles:
        constraints.append((
            math.dist(end, circle.center_meters),
            float(circle.collision_threshold(static.robot_radius_meters,
                                             static.obstacle_clearance_margin_meters)),
        ))

    # ROBOT_CORRIDOR_WALL -- surface distance at the post-step state.
    wall_threshold = float(static.robot_radius_meters
                           + static.obstacle_surface_margin_meters)
    for corridor in static.corridors:
        constraints.append((float(corridor.surface_distance(end)), wall_threshold))

    # ROBOT_DYNAMIC_CIRCLE -- swept minimum centre-to-centre distance.
    time_b = session.time_seconds
    time_a = time_b - session.control_period
    for obstacle in dynamic.obstacles:
        centre_a, _ = obstacle.state(time_a)
        centre_b, _ = obstacle.state(time_b)
        distance = _moving_point_min_distance(start, end, centre_a, centre_b)
        constraints.append((float(distance), float(dynamic.threshold(obstacle))))

    return constraints


@dataclass(frozen=True)
class CandidateTrace:
    """One matched counterfactual continuation."""

    control_intervals: int
    progress_meters: Tuple[float, ...]
    formation_errors_meters: Tuple[Vec2, ...]
    clearance_constraint_counts: Tuple[int, ...]
    termination_cause: str
    terminal_control_step: int
    terminal_time_seconds: float
    matched_stream_identity: Tuple[Tuple[str, ...], ...]
    numerically_valid: bool
    collision: bool


@dataclass(frozen=True)
class CandidateEvaluation:
    candidate_index: int
    delta_u_world: Vec2
    action_world_acceleration: Vec2
    pre_safety_action: Vec2
    post_safety_action: Vec2
    projection_status: str
    projection_intervened: bool
    projection_infeasible: bool
    projection_solver_failed: bool
    locally_feasible: bool
    safety_projection_compatible: bool
    robot_local_information_only: bool
    provenance: Mapping[str, str]
    utilities: Mapping[str, float]
    evaluation: LocalActionEvaluation
    trace: CandidateTrace
    seconds: float
    canonical_hash: str


@dataclass(frozen=True)
class ResidualExpertV2Result:
    schema_version: str
    robot_id: int
    decision_control_step: int
    decision_time_seconds: float
    snapshot_hash: str
    robot_view_hash: str
    candidate_lattice_hash: str
    base_action_pre_safety: Vec2
    base_action_components: Mapping[str, Vec2]
    candidates: Tuple[CandidateEvaluation, ...]
    selected_index: Optional[int]
    selected_action: Optional[Vec2]
    selected_residual: Optional[Vec2]
    target: Optional[ResidualActionTarget]
    selector_error: Optional[str]
    seconds: float


def _canonical_view_hash(view) -> str:
    return canonical_sha256({
        "robot_id": int(view.robot_id),
        "position": [float(v) for v in view.position],
        "velocity": [float(v) for v in view.velocity],
        "role_keep": [float(v) for v in view.role_keep],
        "role_line": [float(v) for v in view.role_line],
        "committed_mode": int(view.committed_mode),
        "epoch_id": int(view.epoch_id),
        "steps_since_decision": int(view.steps_since_decision),
        "local_progress": float(view.local_progress),
        "goal": [float(v) for v in view.goal],
        "mission_dir": [float(v) for v in view.mission_dir],
        "neighbours": [
            {
                "robot_id": int(nb.robot_id),
                "rel_position": [float(v) for v in nb.rel_position],
                "rel_velocity": [float(v) for v in nb.rel_velocity],
                "role_keep": [float(v) for v in nb.role_keep],
                "role_line": [float(v) for v in nb.role_line],
                "committed_mode": int(nb.committed_mode),
                "epoch_id": int(nb.epoch_id),
                "message_age_steps": int(nb.message_age_steps),
                "degree": int(nb.degree),
            }
            for nb in view.neighbours
        ],
        "obstacles": [[float(v) for v in token] for token in view.obstacles],
    })


def _matched_stream_identity(session) -> Tuple[Tuple[str, ...], ...]:
    identity: List[Tuple[str, ...]] = [
        tuple(str(part) for part in session.position_stream.identity()),
        tuple(str(part) for part in session.velocity_stream.identity()),
        tuple(str(part) for part in session.s5_stream.identity()),
    ]
    if session.disturbance_stream is not None:
        identity.append(tuple(str(part) for part in session.disturbance_stream.identity()))
    identity.append(("communication", canonical_sha256(session.channel.snapshot())))
    return tuple(identity)


def _run_candidate(clone, robot_id: int, delta: Vec2,
                   runtime_config: RuntimeConfig) -> CandidateTrace:
    """One matched counterfactual: intervene for one interval, then continue."""
    intervention_step = int(clone.control_step)
    clone.source_policy = _OneIntervalResidualPolicy(
        clone.source_policy, robot_id, delta, intervention_step)
    stream_identity = _matched_stream_identity(clone)

    robot_index = next(index for index, robot in enumerate(clone.robots)
                       if robot.robot_id == robot_id)
    progress: List[float] = [float(clone.robots[robot_index].local_progress)]
    formation: List[Vec2] = []
    constraint_counts: List[int] = []
    worst_constraints: List[List[Tuple[float, float]]] = []

    guard = int(clone.horizon_seconds / clone.control_period) + 16
    for _ in range(guard):
        if clone.termination is not None:
            break
        previous_positions = [robot.position for robot in clone.robots]
        clone.step()
        progress.append(float(clone.robots[robot_index].local_progress))
        formation.append(_formation_error_meters(
            clone, clone.robots[robot_index], runtime_config))
        constraints = _clearance_constraints(clone, robot_index, previous_positions)
        worst_constraints.append(constraints)
        constraint_counts.append(len(constraints))
    else:
        if clone.termination is None:
            raise ResidualExpertV2Error(
                "the counterfactual did not terminate inside the frozen horizon guard")

    applied = clone.source_policy.applied_control_steps
    if applied != [intervention_step] and delta != (0.0, 0.0):
        raise ResidualExpertV2Error(
            f"the candidate residual was applied on {applied}, not exactly once")

    trace = CandidateTrace(
        control_intervals=len(formation),
        progress_meters=tuple(progress),
        formation_errors_meters=tuple(formation),
        clearance_constraint_counts=tuple(constraint_counts),
        termination_cause=(clone.termination.cause if clone.termination is not None
                           else "UNTERMINATED"),
        terminal_control_step=int(clone.control_step),
        terminal_time_seconds=float(clone.time_seconds),
        matched_stream_identity=stream_identity,
        numerically_valid=bool(clone.numerically_valid),
        collision=bool(clone.collision_detected),
    )
    return trace, worst_constraints


def evaluate_residual_expert_v2(
    session,
    robot_id: int,
    *,
    model_config: Optional[FD24ModelConfig] = None,
    provenance_contamination: Optional[Mapping[str, str]] = None,
    candidate_execution_order: Optional[Sequence[int]] = None,
) -> ResidualExpertV2Result:
    """Produce all nine evaluations, then run the frozen selector and builder.

    `provenance_contamination` exists only so the negative locality test can
    inject a forbidden action-side source and prove the derived flag collapses.
    Normal execution never passes it.

    `candidate_execution_order` changes the order in which the counterfactuals
    are *executed*, never the canonical order in which they are stored. Because
    every candidate restores the same snapshot with the same matched streams,
    the stored records must come out identical either way -- which is what
    RB15V2-30 asks to be demonstrated rather than assumed.
    """
    started = time.perf_counter()
    runtime_config = session.runtime_config
    model = model_config or FD24ModelConfig()
    robot = next(item for item in session.robots if item.robot_id == robot_id)

    # -- decision inputs, from the runtime's own locality boundary ---------
    view, controller_input, controller = session.local_decision_inputs(robot)
    output = controller.evaluate(controller_input)
    base_action = (float(output.base_action[0]), float(output.base_action[1]))

    provenance = CandidateActionProvenance()
    provenance.record("robot_view.self_state", "SELF_LOCAL")
    provenance.record("robot_view.neighbours", "ONE_HOP_LOCAL")
    provenance.record("robot_view.obstacles", "LOCAL_OBSTACLE")
    provenance.record("robot_view.committed_topology", "LOCAL_PROTOCOL_STATE")
    provenance.record("runtime_configuration", "IMMUTABLE_FROZEN_CONFIG")
    provenance.record("model_configuration", "IMMUTABLE_FROZEN_CONFIG")
    provenance.record("phase6_base_action", "LOCAL_CONTROLLER_DERIVED")
    provenance.record("local_safety_projection", "LOCAL_SAFETY_DERIVED")
    provenance.record("residual_candidate", "IMMUTABLE_FROZEN_CONFIG")
    for name, source_class in (provenance_contamination or {}).items():
        provenance.record(name, source_class)
    local_information_only = provenance.robot_local_information_only

    lattice = residual_candidate_lattice(model, runtime_config)
    if len(lattice) != CANDIDATE_COUNT:
        raise ResidualExpertV2Error("the candidate lattice is not the frozen nine points")
    limits = residual_action_limits(model, runtime_config)
    physical_limit = float(
        runtime_config.physical.maximum_acceleration_meters_per_second_squared)
    projection = controller.safety_projection
    base_snapshot = snapshot(session)

    order = (list(range(len(lattice))) if candidate_execution_order is None
             else [int(index) for index in candidate_execution_order])
    if sorted(order) != list(range(len(lattice))):
        raise ResidualExpertV2Error("the candidate execution order is not a permutation")

    by_index: Dict[int, CandidateEvaluation] = {}
    for index in order:
        delta = lattice[index]
        candidate_started = time.perf_counter()
        pre_safety = (base_action[0] + delta[0], base_action[1] + delta[1])

        # RB15V2-8 -- narrow local feasibility. No rollout, safety or task terms.
        locally_feasible = (
            all(math.isfinite(float(value)) for value in view.position)
            and all(math.isfinite(float(value)) for value in view.velocity)
            and math.isfinite(float(view.local_progress))
            and all(math.isfinite(value) for value in base_action)
            and all(math.isfinite(value) for value in delta)
            and all(math.isfinite(value) for value in pre_safety)
            and bool(output.validity)
        )

        # RB15V2-9 -- own-action local projection only.
        result = projection.project(pre_safety, controller_input)
        post_safety = (float(result.projected_action[0]),
                       float(result.projected_action[1]))
        safety_compatible = not (bool(result.infeasible) or bool(result.solver_failed))

        # RB15V2-10..14 -- matched counterfactual from the identical snapshot.
        clone = base_snapshot.restore()
        trace, constraints = _run_candidate(clone, robot_id, delta, runtime_config)

        utilities = {
            "normalized_progress": utility_v2.normalized_progress(
                trace.progress_meters, runtime_config),
            "normalized_clearance_margin": utility_v2.normalized_clearance_margin(
                constraints),
            "normalized_formation_error": utility_v2.normalized_formation_error(
                trace.formation_errors_meters, runtime_config),
            "normalized_action_deviation": utility_v2.normalized_action_deviation(
                delta, model, runtime_config),
        }

        evaluation = LocalActionEvaluation(
            pre_safety,
            locally_feasible,
            safety_compatible,
            local_information_only,
            utilities["normalized_progress"],
            utilities["normalized_clearance_margin"],
            utilities["normalized_formation_error"],
            utilities["normalized_action_deviation"],
        )
        record = {
            "candidate_index": index,
            "delta_u_world": [float(v) for v in delta],
            "action_world_acceleration": [float(v) for v in pre_safety],
            "post_safety_action": [float(v) for v in post_safety],
            "projection_status": str(result.status),
            "locally_feasible": locally_feasible,
            "safety_projection_compatible": safety_compatible,
            "robot_local_information_only": local_information_only,
            "utilities": {key: float(value) for key, value in sorted(utilities.items())},
            "termination": trace.termination_cause,
            "control_intervals": trace.control_intervals,
        }
        by_index[index] = CandidateEvaluation(
            candidate_index=index,
            delta_u_world=delta,
            action_world_acceleration=pre_safety,
            pre_safety_action=pre_safety,
            post_safety_action=post_safety,
            projection_status=str(result.status),
            projection_intervened=bool(result.intervened),
            projection_infeasible=bool(result.infeasible),
            projection_solver_failed=bool(result.solver_failed),
            locally_feasible=locally_feasible,
            safety_projection_compatible=safety_compatible,
            robot_local_information_only=local_information_only,
            provenance=provenance.as_dict(),
            utilities=utilities,
            evaluation=evaluation,
            trace=trace,
            seconds=time.perf_counter() - candidate_started,
            canonical_hash=canonical_sha256(record),
        )

    # Stored order is always canonical, whatever the execution order was.
    candidates: List[CandidateEvaluation] = [by_index[index]
                                             for index in range(len(lattice))]

    # -- RB15V2-22/25 -- the unchanged frozen selector and target builder ---
    selected_index: Optional[int] = None
    target: Optional[ResidualActionTarget] = None
    selector_error: Optional[str] = None
    selected_action: Optional[Vec2] = None
    selected_residual: Optional[Vec2] = None
    try:
        expert = select_counterfactual_local_action(
            base_action, [item.evaluation for item in candidates], runtime_config, model)
        selected_index = next(
            index for index, item in enumerate(candidates) if item.evaluation is expert)
        selected_action = candidates[selected_index].action_world_acceleration
        selected_residual = candidates[selected_index].delta_u_world
        target = build_residual_action_target(base_action, expert, runtime_config, model)
    except ValueError as error:                # the frozen no-eligible-candidate path
        selector_error = str(error)

    return ResidualExpertV2Result(
        schema_version=RESIDUAL_EXPERT_V2_PRODUCER_SCHEMA_VERSION,
        robot_id=int(robot_id),
        decision_control_step=int(session.control_step),
        decision_time_seconds=float(session.time_seconds),
        snapshot_hash=base_snapshot.canonical_hash,
        robot_view_hash=_canonical_view_hash(view),
        candidate_lattice_hash=canonical_lattice_hash(lattice),
        base_action_pre_safety=base_action,
        base_action_components={
            "formation_term": tuple(float(v) for v in output.formation_term),
            "goal_term": tuple(float(v) for v in output.goal_term),
            "damping_term": tuple(float(v) for v in output.damping_term),
            "obstacle_term": tuple(float(v) for v in output.obstacle_term),
        },
        candidates=tuple(candidates),
        selected_index=selected_index,
        selected_action=selected_action,
        selected_residual=selected_residual,
        target=target,
        selector_error=selector_error,
        seconds=time.perf_counter() - started,
    )


def canonical_result_digest(result: ResidualExpertV2Result) -> str:
    """Order-sensitive digest of everything a determinism test must pin."""
    return canonical_sha256({
        "robot_id": result.robot_id,
        "decision_control_step": result.decision_control_step,
        "snapshot_hash": result.snapshot_hash,
        "robot_view_hash": result.robot_view_hash,
        "candidate_lattice_hash": result.candidate_lattice_hash,
        "base_action": [float(v) for v in result.base_action_pre_safety],
        "candidates": [item.canonical_hash for item in result.candidates],
        "selected_index": result.selected_index,
        "selected_residual": (None if result.selected_residual is None
                              else [float(v) for v in result.selected_residual]),
        "target": (None if result.target is None else [
            [float(v) for v in result.target.base_action_world_acceleration],
            [float(v) for v in result.target.expert_action_world_acceleration],
            [float(v) for v in result.target.residual_target_world_acceleration],
            [float(v) for v in result.target.residual_bounds_world_acceleration],
            bool(result.target.finite), bool(result.target.nonzero),
            bool(result.target.saturated),
            bool(result.target.safety_projection_compatible),
        ]),
        "selector_error": result.selector_error,
        "utility_information_class": dict(sorted(UTILITY_INFORMATION_CLASS.items())),
        "zero_residual_index": zero_residual_index(),
    })
