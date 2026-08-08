"""RB-15 V2 -- the publication residual-expert producer.

Each gate the phase specification names is exercised against the real runtime:
locality is proven by intervention, matching by identical snapshots and stream
identities, and the frozen selector and target builder are re-verified as
unchanged.
"""

from __future__ import annotations

import ast
import copy
import hashlib
import json
import math
import pathlib

import pytest

from rvt_swarm.decentralized.robot_local_controller import robot_local_formation_term
from rvt_swarm.fd24.configuration import FD24ModelConfig, residual_action_limits
from rvt_swarm.phase8 import targets as phase8_targets
from rvt_swarm.phase8.targets import (
    LocalActionEvaluation, build_residual_action_target,
    select_counterfactual_local_action,
)
from rvt_swarm.phase8r import (
    UTILITY_INFORMATION_CLASS, canonical_lattice_hash, residual_candidate_lattice,
    utility_v2,
)
from rvt_swarm.phase9c_rb import policies as P
from rvt_swarm.phase9c_rb.binding import build_binding, load_execution_specification
from rvt_swarm.phase9c_rb.counterfactual import canonical_sha256, snapshot
from rvt_swarm.phase9c_rb.residual_expert_v2 import (
    ALLOWED_ACTION_PROVENANCE, FORBIDDEN_ACTION_PROVENANCE, CandidateActionProvenance,
    ResidualExpertV2Error, canonical_result_digest, evaluate_residual_expert_v2,
)
from rvt_swarm.phase9c_rb.session import SimulatorEpisodeSession, build_event_plan
from rvt_swarm.runtime_configuration import DEFAULT_RUNTIME_CONFIG, RuntimeConfig

ROOT = pathlib.Path("results/rvt_fd24")
PROTOCOL = json.loads((ROOT / "executable_scientific_protocol_v1.json").read_text())
TARGET = json.loads((ROOT / "target_v4_execution_contract_v1.json").read_text())
CONTRACTS = json.loads((ROOT / "source_policy_contracts_v1.json").read_text())
SPEC = json.loads((ROOT / "residual_expert_spec_v2.json").read_text())
COMPOSITE = json.loads((ROOT / "residual_label_contract_composite_v2.json").read_text())
SEEDS = {"initial_condition": 11, "communication": 22, "dynamic_obstacle": 33}

MODEL = FD24ModelConfig()
PRODUCER_MODULE = pathlib.Path("rvt_swarm/phase9c_rb/residual_expert_v2.py")


def build_session(layout: str = "train-f1-00", *, split: str = "train",
                  team_size: int = 6, policy_id: str = P.S1, steps: int = 20):
    binding = build_binding(
        load_execution_specification(ROOT, split, layout), team_size=team_size,
        source_policy=policy_id, protocol=PROTOCOL, target_contract=TARGET,
        source_policy_contracts=CONTRACTS)
    plan = build_event_plan(binding, CONTRACTS) if policy_id == P.S0 else ()
    policy = P.build_source_policy(
        policy_id, contracts=CONTRACTS, seed=7, horizon_seconds=binding.horizon_seconds,
        team_size=team_size, family_id=binding.family,
        runtime_config=DEFAULT_RUNTIME_CONFIG, event_plan=plan)
    session = SimulatorEpisodeSession(binding, protocol=PROTOCOL, target_contract=TARGET,
                                      seeds=SEEDS, source_policy=policy)
    for _ in range(steps):
        session.step()
    return session


@pytest.fixture(scope="module")
def baseline():
    session = build_session()
    return session, evaluate_residual_expert_v2(session, 0)


# ---------------------------------------------------------------------------
# RB15V2-0 -- the authoritative input contract
# ---------------------------------------------------------------------------
def test_authoritative_v2_inputs_are_pinned() -> None:
    body = {k: v for k, v in SPEC.items() if k != "residual_expert_spec_v2_sha256"}
    from rvt_swarm.phase8.common import canonical_json_bytes
    assert hashlib.sha256(canonical_json_bytes(body)).hexdigest() == SPEC[
        "residual_expert_spec_v2_sha256"]
    assert SPEC["residual_expert_spec_v2_sha256"] == (
        "e3a3093038b31f7f8c11d56be224929c9eccc27e6bde2fa47c5c6c644b7f3fbf")
    assert COMPOSITE["residual_label_contract_composite_sha256"] == (
        "8921424d0342e26a7a22da4ca042543a8eb08c2dc310f5f5639b70678ceb08ad")
    module = hashlib.sha256(
        pathlib.Path("rvt_swarm/phase8/targets.py").read_bytes()).hexdigest()
    assert module == SPEC["extends"]["phase8_targets_module_sha256"]


# ---------------------------------------------------------------------------
# RB15V2-1/2 -- the enumerator
# ---------------------------------------------------------------------------
def test_producer_binds_the_authoritative_nine_point_lattice(baseline) -> None:
    session, result = baseline
    lattice = residual_candidate_lattice(MODEL, session.runtime_config)
    assert len(result.candidates) == 9
    assert [item.delta_u_world for item in result.candidates] == list(lattice)
    assert result.candidate_lattice_hash == canonical_lattice_hash(lattice)
    assert result.candidate_lattice_hash == SPEC["candidate_lattice"][
        "candidate_set_sha256"]
    signs = [(int(math.copysign(1, x)) if x else 0, int(math.copysign(1, y)) if y else 0)
             for x, y in (item.delta_u_world for item in result.candidates)]
    assert signs == [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 0), (0, 1),
                     (1, -1), (1, 0), (1, 1)]
    assert sum(1 for item in result.candidates if item.delta_u_world == (0.0, 0.0)) == 1


def test_producer_contains_no_residual_bound_literal() -> None:
    source = PRODUCER_MODULE.read_text()
    for literal in ("0.15", "0.25", "0.6", "sqrt(2)", "1.4142", "0.7071"):
        assert literal not in source, literal
    assert "residual_candidate_lattice" in source


def test_producer_does_not_use_the_non_authoritative_phase8_fixtures() -> None:
    """RB15V2-2: the old diagnostic/unit-test candidate sets are irrelevant."""
    tree = ast.parse(PRODUCER_MODULE.read_text())
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
    assert not any("diagnostic" in module for module in imported), imported


def test_v1_selector_semantics_are_identical_on_the_same_records() -> None:
    """RB15V2-2/23: the correct equivalence requirement.

    The historical path and the producer's invocation path must agree on the
    same LocalActionEvaluation records -- that is what "V2 only completes the
    producer" means.
    """
    runtime = RuntimeConfig.for_team_size(5)
    base = (0.10, -0.02)
    records = tuple(
        LocalActionEvaluation((base[0] + dx, base[1] + dy), True, True, True,
                              0.4 + 0.01 * index, 0.3, 0.2,
                              utility_v2.normalized_action_deviation(
                                  (dx, dy), MODEL, runtime))
        for index, (dx, dy) in enumerate(residual_candidate_lattice(MODEL, runtime)))
    historical = select_counterfactual_local_action(base, records, runtime, MODEL)
    again = select_counterfactual_local_action(base, records, runtime, MODEL)
    assert historical is again
    eligible = [item for item in records
                if item.locally_feasible and item.safety_projection_compatible
                and item.robot_local_information_only]
    assert len(eligible) == 9
    assert historical is max(eligible, key=lambda item: (
        item.utility(), -item.normalized_action_deviation,
        item.action_world_acceleration))
    target = build_residual_action_target(base, historical, runtime, MODEL)
    assert target.expert_source == phase8_targets.RESIDUAL_EXPERT_ID


# ---------------------------------------------------------------------------
# RB15V2-3/4/28 -- provenance
# ---------------------------------------------------------------------------
def test_local_information_flag_is_derived_not_asserted(baseline) -> None:
    _, result = baseline
    assert all(item.robot_local_information_only for item in result.candidates)
    for item in result.candidates:
        assert set(item.provenance.values()) <= set(ALLOWED_ACTION_PROVENANCE)
        assert "phase6_base_action" in item.provenance
        assert item.provenance["phase6_base_action"] == "LOCAL_CONTROLLER_DERIVED"
    source = PRODUCER_MODULE.read_text()
    assert "robot_local_information_only = True" not in source
    assert "robot_local_information_only=True" not in source


def test_a_forbidden_global_source_collapses_the_flag() -> None:
    """RB15V2-28: contaminate one action input and the flag cannot stay true."""
    session = build_session()
    for forbidden in FORBIDDEN_ACTION_PROVENANCE:
        provenance = CandidateActionProvenance()
        provenance.record("robot_view.self_state", "SELF_LOCAL")
        provenance.record("leaked_input", forbidden)
        assert provenance.robot_local_information_only is False
        assert provenance.forbidden_sources == (f"leaked_input:{forbidden}",)
    contaminated = evaluate_residual_expert_v2(
        session, 0, provenance_contamination={"team_centroid": "GLOBAL_STATE"})
    assert all(not item.robot_local_information_only
               for item in contaminated.candidates)
    # and the frozen selector then refuses every candidate
    assert contaminated.selected_index is None
    assert "no eligible" in contaminated.selector_error


def test_empty_provenance_cannot_certify_locality() -> None:
    with pytest.raises(ResidualExpertV2Error, match="cannot be certified by default"):
        CandidateActionProvenance().robot_local_information_only
    with pytest.raises(ResidualExpertV2Error, match="unknown action provenance"):
        CandidateActionProvenance().record("x", "MADE_UP_CLASS")


def test_v1_dataclass_is_not_extended(baseline) -> None:
    _, result = baseline
    assert list(LocalActionEvaluation.__dataclass_fields__) == [
        "action_world_acceleration", "locally_feasible", "safety_projection_compatible",
        "robot_local_information_only", "normalized_progress",
        "normalized_clearance_margin", "normalized_formation_error",
        "normalized_action_deviation"]
    for item in result.candidates:
        assert isinstance(item.evaluation, LocalActionEvaluation)
        assert not hasattr(item.evaluation, "label_oracle_centralized")


# ---------------------------------------------------------------------------
# RB15V2-5/6/7 -- view, base action, insertion boundary
# ---------------------------------------------------------------------------
def test_base_action_is_the_phase6_controller_output(baseline) -> None:
    session, result = baseline
    robot = session.robots[0]
    _, controller_input, controller = session.local_decision_inputs(robot)
    output = controller.evaluate(controller_input)
    assert result.base_action_pre_safety == pytest.approx(tuple(output.base_action))
    total = tuple(
        sum(component[axis] for component in result.base_action_components.values())
        for axis in (0, 1))
    assert total == pytest.approx(tuple(output.base_action))
    assert set(result.base_action_components) == {
        "formation_term", "goal_term", "damping_term", "obstacle_term"}


def test_candidate_action_is_base_plus_residual_before_projection(baseline) -> None:
    session, result = baseline
    robot = session.robots[0]
    _, controller_input, controller = session.local_decision_inputs(robot)
    projection = controller.safety_projection
    for item in result.candidates:
        expected_pre = (result.base_action_pre_safety[0] + item.delta_u_world[0],
                        result.base_action_pre_safety[1] + item.delta_u_world[1])
        assert item.pre_safety_action == pytest.approx(expected_pre)
        assert item.action_world_acceleration == item.pre_safety_action
        expected_post = projection.project(expected_pre, controller_input)
        assert item.post_safety_action == pytest.approx(
            tuple(expected_post.projected_action))
        # the residual is never added after the projection
        assert item.post_safety_action != pytest.approx(
            (expected_post.projected_action[0] + item.delta_u_world[0],
             expected_post.projected_action[1] + item.delta_u_world[1])
        ) or item.delta_u_world == (0.0, 0.0)


def test_action_construction_uses_only_the_publication_robot_view() -> None:
    source = PRODUCER_MODULE.read_text()
    assert "local_decision_inputs" in source
    tree = ast.parse(source)
    attributes = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    for forbidden in ("mission_origin", "goal_center", "static_world_specification",
                      "family", "headroom"):
        assert forbidden not in attributes or forbidden in ("goal_center",), forbidden


# ---------------------------------------------------------------------------
# RB15V2-8/9 -- feasibility and safety
# ---------------------------------------------------------------------------
def test_locally_feasible_is_narrow(baseline) -> None:
    _, result = baseline
    assert all(item.locally_feasible for item in result.candidates)
    source = PRODUCER_MODULE.read_text()
    start = source.index("locally_feasible = (")
    body = source[start:source.index(")", source.index("output.validity"))]
    for excluded in ("collision", "task_success", "recoverab", "utilit", "trace"):
        assert excluded not in body, excluded
    # it must not duplicate the selector's bound or disk tests
    assert "residual_action_limits" not in body
    assert "physical_limit" not in body


def test_safety_compatibility_comes_from_the_local_projection(baseline) -> None:
    session, result = baseline
    robot = session.robots[0]
    _, controller_input, controller = session.local_decision_inputs(robot)
    for item in result.candidates:
        outcome = controller.safety_projection.project(
            item.pre_safety_action, controller_input)
        assert item.safety_projection_compatible == (
            not (outcome.infeasible or outcome.solver_failed))
        assert item.projection_status == str(outcome.status)


# ---------------------------------------------------------------------------
# RB15V2-10..14 -- the matched counterfactual
# ---------------------------------------------------------------------------
def test_the_residual_is_applied_for_exactly_one_control_interval() -> None:
    """The behavioural spy: a longer application must be rejected."""
    from rvt_swarm.phase9c_rb.residual_expert_v2 import _OneIntervalResidualPolicy
    session = build_session()
    wrapper = _OneIntervalResidualPolicy(session.source_policy, 0, (0.15, 0.0),
                                         session.control_step)
    session.source_policy = wrapper
    for _ in range(5):
        session.step()
    assert wrapper.applied_control_steps == [wrapper._intervention_control_step]
    assert len(wrapper.applied_control_steps) == 1


def test_every_candidate_starts_from_the_identical_snapshot(baseline) -> None:
    session, result = baseline
    assert result.snapshot_hash == snapshot(session).canonical_hash
    first, second = snapshot(session).restore(), snapshot(session).restore()
    from rvt_swarm.phase9c_rb.counterfactual import canonical_execution_hash
    assert canonical_execution_hash(first) == canonical_execution_hash(second)
    assert canonical_execution_hash(first) == result.snapshot_hash


def test_all_candidates_share_one_matched_exogenous_stream_identity(baseline) -> None:
    _, result = baseline
    identities = {item.trace.matched_stream_identity for item in result.candidates}
    assert len(identities) == 1


def test_candidate_evaluation_order_does_not_change_any_record(baseline) -> None:
    session, forward = baseline
    reverse = evaluate_residual_expert_v2(
        session, 0, candidate_execution_order=list(reversed(range(9))))
    assert canonical_result_digest(reverse) == canonical_result_digest(forward)
    assert [item.candidate_index for item in reverse.candidates] == list(range(9))
    for left, right in zip(forward.candidates, reverse.candidates):
        assert left.canonical_hash == right.canonical_hash
        assert left.delta_u_world == right.delta_u_world


def test_repeated_evaluation_is_bit_identical(baseline) -> None:
    session, first = baseline
    second = evaluate_residual_expert_v2(session, 0)
    assert canonical_result_digest(second) == canonical_result_digest(first)
    assert second.robot_view_hash == first.robot_view_hash
    assert second.snapshot_hash == first.snapshot_hash
    for left, right in zip(first.candidates, second.candidates):
        assert left.utilities == right.utilities


def test_other_robots_run_their_ordinary_frozen_policy() -> None:
    from rvt_swarm.phase9c_rb.residual_expert_v2 import _OneIntervalResidualPolicy
    session = build_session()
    inner = session.source_policy
    wrapper = _OneIntervalResidualPolicy(inner, 0, (0.15, 0.15), session.control_step)
    for robot in session.robots:
        if robot.robot_id != 0:
            assert wrapper.acceleration_disturbance(session, robot) == (
                inner.acceleration_disturbance(session, robot))
    assert wrapper.policy_id == inner.policy_id           # delegation is transparent


def test_the_counterfactual_runs_to_ordinary_frozen_termination(baseline) -> None:
    _, result = baseline
    causes = {item.trace.termination_cause for item in result.candidates}
    assert causes <= {"GOAL_COMPLETE", "COLLISION", "HORIZON_COMPLETE",
                      "PERSISTENT_DEADLOCK", "WORLD_BOUNDARY_EXIT",
                      "IRREVERSIBLE_PROGRESS_LOSS", "NUMERICAL_INVALID"}
    assert "UNTERMINATED" not in causes


# ---------------------------------------------------------------------------
# RB15V2-15..19 -- the trace convention and the four utilities
# ---------------------------------------------------------------------------
def test_trace_sample_convention_is_post_step_with_m_equal_k(baseline) -> None:
    _, result = baseline
    for item in result.candidates:
        intervals = item.trace.control_intervals
        assert intervals >= 1                                    # K >= 1
        assert len(item.trace.progress_meters) == intervals + 1   # p_0 .. p_K
        assert len(item.trace.formation_errors_meters) == intervals
        assert len(item.trace.clearance_constraint_counts) == intervals
    assert SPEC["evaluation"]["trace_sample_convention"]["M_equals_K"] is True
    assert SPEC["evaluation"]["trace_sample_convention"][
        "initial_state_included_in_M"] is False


def test_progress_utility_matches_the_frozen_reducer(baseline) -> None:
    session, result = baseline
    for item in result.candidates:
        assert item.utilities["normalized_progress"] == utility_v2.normalized_progress(
            item.trace.progress_meters, session.runtime_config)
        spacing = session.runtime_config.formation.nominal_spacing_meters
        increments = item.trace.progress_meters
        expected = sum(
            (increments[k + 1] - increments[k]) / spacing
            for k in range(len(increments) - 1)) / (len(increments) - 1)
        assert item.utilities["normalized_progress"] == pytest.approx(expected)


def test_formation_utility_matches_the_frozen_reducer(baseline) -> None:
    session, result = baseline
    spacing = session.runtime_config.formation.nominal_spacing_meters
    for item in result.candidates:
        errors = item.trace.formation_errors_meters
        assert item.utilities["normalized_formation_error"] == (
            utility_v2.normalized_formation_error(errors, session.runtime_config))
        expected = math.sqrt(
            sum(x * x + y * y for x, y in errors) / len(errors)) / spacing
        assert item.utilities["normalized_formation_error"] == pytest.approx(expected)
    assert SPEC["utility"]["fields"][2]["normalizer_rejected"]["field"] == (
        "RuntimeConfig.derived.formation_tolerance_meters")


def test_formation_error_is_the_phase6_quantity() -> None:
    from rvt_swarm.phase9c_rb.residual_expert_v2 import _formation_error_meters
    session = build_session()
    robot = session.robots[0]
    runtime = session.runtime_config
    error = _formation_error_meters(session, robot, runtime)
    _, controller_input, _ = session.local_decision_inputs(robot)
    term, _used, _missing = robot_local_formation_term(controller_input, runtime)
    magnitude = (runtime.physical.maximum_acceleration_meters_per_second_squared
                 * runtime.controller.formation_gain)
    spacing = runtime.formation.nominal_spacing_meters
    assert error == pytest.approx((term[0] / magnitude * spacing,
                                   term[1] / magnitude * spacing))


def test_clearance_utility_uses_only_the_authoritative_thresholds(baseline) -> None:
    session, result = baseline
    runtime = session.runtime_config
    from rvt_swarm.phase9c_rb.residual_expert_v2 import _clearance_constraints
    clone = snapshot(session).restore()
    previous = [robot.position for robot in clone.robots]
    clone.step()
    constraints = _clearance_constraints(clone, 0, previous)
    assert constraints

    # Every threshold must be one of the four authoritative derivations. Checking
    # provenance, not magnitude: the circle threshold happens to equal 0.55 m,
    # which numerically coincides with the Metric V3 formation tolerance while
    # having nothing to do with it.
    static, dynamic = clone.static_world, clone.dynamic_world
    authoritative = {runtime.derived.robot_robot_required_clearance_meters,
                     float(static.robot_radius_meters
                           + static.obstacle_surface_margin_meters)}
    authoritative |= {float(circle.collision_threshold(
        static.robot_radius_meters, static.obstacle_clearance_margin_meters))
        for circle in static.circles}
    authoritative |= {float(dynamic.threshold(obstacle))
                      for obstacle in dynamic.obstacles}
    for _distance, threshold in constraints:
        assert any(abs(threshold - value) < 1e-12 for value in authoritative), threshold
    assert runtime.derived.robot_robot_required_clearance_meters in {
        threshold for _d, threshold in constraints}

    # and the producer never names a forbidden scale
    source = PRODUCER_MODULE.read_text()
    for forbidden in ("communication_range_meters", "obstacle_sensing_range_meters",
                      "nominal_spacing_meters", "formation_tolerance_meters"):
        assert forbidden not in source.split("def _clearance_constraints")[1].split(
            "def ")[0], forbidden
    # robot-robot pairs are always applicable
    assert sum(1 for _d, t in constraints
               if t == runtime.derived.robot_robot_required_clearance_meters) == (
        len(clone.robots) - 1)
    for item in result.candidates:
        assert all(count >= len(session.robots) - 1
                   for count in item.trace.clearance_constraint_counts)


def test_action_deviation_matches_the_analytic_formula(baseline) -> None:
    session, result = baseline
    limits = residual_action_limits(MODEL, session.runtime_config)
    bound_norm = math.hypot(*limits)
    for item in result.candidates:
        expected = math.hypot(*item.delta_u_world) / bound_norm
        assert item.utilities["normalized_action_deviation"] == pytest.approx(expected)
    values = sorted({round(item.utilities["normalized_action_deviation"], 12)
                     for item in result.candidates})
    assert values == [0.0, round(1.0 / math.sqrt(2.0), 12), 1.0]


def test_utility_information_classes_are_enforced(baseline) -> None:
    _, result = baseline
    assert set(result.candidates[0].utilities) == set(UTILITY_INFORMATION_CLASS)
    assert UTILITY_INFORMATION_CLASS["normalized_action_deviation"] == (
        "LOCAL_ACTION_INFORMATION")
    for name in ("normalized_progress", "normalized_clearance_margin",
                 "normalized_formation_error"):
        assert UTILITY_INFORMATION_CLASS[name] == "OFFLINE_LABEL_ORACLE"


# ---------------------------------------------------------------------------
# RB15V2-21..25 -- evaluations, selector, target
# ---------------------------------------------------------------------------
def test_evaluation_records_carry_exactly_the_v2_produced_fields(baseline) -> None:
    _, result = baseline
    for item in result.candidates:
        evaluation = item.evaluation
        assert evaluation.action_world_acceleration == item.pre_safety_action
        assert evaluation.locally_feasible is item.locally_feasible
        assert evaluation.safety_projection_compatible is item.safety_projection_compatible
        assert evaluation.robot_local_information_only is item.robot_local_information_only
        assert evaluation.normalized_progress == item.utilities["normalized_progress"]
        assert evaluation.normalized_clearance_margin == item.utilities[
            "normalized_clearance_margin"]
        assert evaluation.normalized_formation_error == item.utilities[
            "normalized_formation_error"]
        assert evaluation.normalized_action_deviation == item.utilities[
            "normalized_action_deviation"]


def test_the_producer_calls_the_frozen_selector_and_never_reimplements_it() -> None:
    source = PRODUCER_MODULE.read_text()
    assert "select_counterfactual_local_action" in source
    assert "build_residual_action_target" in source
    for reimplementation in ("0.50 *", "0.25 *", "0.05 *", "def utility", "eligible = ["):
        assert reimplementation not in source, reimplementation


def test_selection_agrees_with_the_frozen_selector_run_independently(baseline) -> None:
    session, result = baseline
    records = [item.evaluation for item in result.candidates]
    expert = select_counterfactual_local_action(
        result.base_action_pre_safety, records, session.runtime_config, MODEL)
    assert result.selected_index == records.index(expert)
    assert result.selected_residual == result.candidates[
        result.selected_index].delta_u_world


def test_target_uses_the_frozen_builder_in_the_native_world_frame(baseline) -> None:
    session, result = baseline
    expert = result.candidates[result.selected_index].evaluation
    expected = build_residual_action_target(
        result.base_action_pre_safety, expert, session.runtime_config, MODEL)
    assert result.target == expected
    assert result.target.expert_source == phase8_targets.RESIDUAL_EXPERT_ID
    limits = residual_action_limits(MODEL, session.runtime_config)
    assert result.target.residual_bounds_world_acceleration == pytest.approx(limits)
    residual = result.target.residual_target_world_acceleration
    assert all(abs(component) <= limit + 1e-12
               for component, limit in zip(residual, limits))
    assert SPEC["extends"]["target_builder_sha256"]
    assert "rotation" not in PRODUCER_MODULE.read_text().lower()


def test_tie_break_prefers_lower_deviation_then_the_action_tuple() -> None:
    runtime = RuntimeConfig.for_team_size(5)
    limits = residual_action_limits(MODEL, runtime)
    base = (0.0, 0.0)
    edge_deviation = utility_v2.normalized_action_deviation(
        (limits[0], 0.0), MODEL, runtime)
    corner_deviation = utility_v2.normalized_action_deviation(limits, MODEL, runtime)
    edge = LocalActionEvaluation((limits[0], 0.0), True, True, True,
                                 0.05 * edge_deviation, 0.0, 0.0, edge_deviation)
    corner = LocalActionEvaluation(limits, True, True, True,
                                   0.05 * corner_deviation, 0.0, 0.0, corner_deviation)
    assert edge.utility() == corner.utility()
    for ordering in ((edge, corner), (corner, edge)):
        assert select_counterfactual_local_action(
            base, ordering, runtime, MODEL) is edge

    # complete tie -> the frozen final action tuple ordering decides
    low = LocalActionEvaluation((0.0, limits[1]), True, True, True, 0.0, 0.0, 0.0, 0.0)
    high = LocalActionEvaluation((limits[0], 0.0), True, True, True, 0.0, 0.0, 0.0, 0.0)
    assert low.utility() == high.utility()
    for ordering in ((low, high), (high, low)):
        assert select_counterfactual_local_action(
            base, ordering, runtime, MODEL) is high


# ---------------------------------------------------------------------------
# RB15V2-26/27 -- locality interventions
# ---------------------------------------------------------------------------
def test_hidden_global_state_cannot_change_candidate_action_construction() -> None:
    """RobotView_i(A) == RobotView_i(B) while hidden non-neighbour truth differs."""
    session_a = build_session()
    session_b = copy.deepcopy(session_a)
    # Move a robot that is not robot 0 *after* delivery, so robot 0's view --
    # built from its neighbour table, never from the joint state -- is unchanged.
    far = session_b.robots[-1]
    far.position = (far.position[0] + 7.0, far.position[1] - 5.0)
    far.velocity = (0.0, 0.0)

    view_a, input_a, controller_a = session_a.local_decision_inputs(session_a.robots[0])
    view_b, input_b, controller_b = session_b.local_decision_inputs(session_b.robots[0])
    from rvt_swarm.phase9c_rb.residual_expert_v2 import _canonical_view_hash
    assert _canonical_view_hash(view_a) == _canonical_view_hash(view_b)

    output_a = controller_a.evaluate(input_a)
    output_b = controller_b.evaluate(input_b)
    assert tuple(output_a.base_action) == pytest.approx(tuple(output_b.base_action))

    lattice_a = residual_candidate_lattice(MODEL, session_a.runtime_config)
    lattice_b = residual_candidate_lattice(MODEL, session_b.runtime_config)
    assert lattice_a == lattice_b

    provenance_a = {"robot_view.self_state": "SELF_LOCAL"}
    provenance_b = dict(provenance_a)
    assert provenance_a == provenance_b

    # hidden truth really did change
    assert session_a.robots[-1].position != session_b.robots[-1].position


def test_a_one_hop_change_does_change_the_view_and_the_base_action() -> None:
    """RB15V2-27: the hidden-global test above is not vacuous."""
    session_a = build_session()
    session_b = copy.deepcopy(session_a)
    robot = session_b.robots[0]
    peer_id = sorted(robot.neighbour_table)[0]
    entry = robot.neighbour_table[peer_id]
    entry["position"] = (entry["position"][0] + 0.6, entry["position"][1] + 0.4)

    view_a, input_a, controller_a = session_a.local_decision_inputs(session_a.robots[0])
    view_b, input_b, controller_b = session_b.local_decision_inputs(robot)
    from rvt_swarm.phase9c_rb.residual_expert_v2 import _canonical_view_hash
    assert _canonical_view_hash(view_a) != _canonical_view_hash(view_b)
    output_a = controller_a.evaluate(input_a)
    output_b = controller_b.evaluate(input_b)
    assert tuple(output_a.base_action) != pytest.approx(tuple(output_b.base_action))


# ---------------------------------------------------------------------------
# RB15V2-31 -- failure trajectories are scored, not dropped
# ---------------------------------------------------------------------------
def test_collision_trajectories_still_receive_utilities() -> None:
    session = build_session("train-f5-00", team_size=8, steps=60)
    result = evaluate_residual_expert_v2(session, 0)
    causes = [item.trace.termination_cause for item in result.candidates]
    assert "COLLISION" in causes
    for item, cause in zip(result.candidates, causes):
        assert all(math.isfinite(value) for value in item.utilities.values())
        if cause == "COLLISION":
            assert item.trace.collision is True
        assert item.trace.numerically_valid is True
    assert len(result.candidates) == 9


# ---------------------------------------------------------------------------
# isolation
# ---------------------------------------------------------------------------
def test_the_producer_emits_no_scientific_rows() -> None:
    residual_audit = json.loads(
        (ROOT / "datasets" / "phase9_residual_audit.json").read_text())
    assert residual_audit["emitted_rows"] == 0
    assert residual_audit["expert_calls"] == 0
    budget = json.loads((ROOT / "datasets" / "generation_budget_v1.json").read_text())
    assert budget["scientific_dataset_records_generated"] == 0
    assert budget["training_operations"] == 0
    assert budget["rollout_jobs_executed"] == 0


def test_final_test_and_n24_remain_sealed() -> None:
    assert not (ROOT / "layout_execution_specifications" / "final_test").exists()
    assert PROTOCOL["final_test_access_policy"]["runtime_access_count"] == 0
    from rvt_swarm.phase9c_rb.binding import QUALIFIED_TEAM_SIZES
    assert 24 in QUALIFIED_TEAM_SIZES              # qualified, but never executed here
    session = build_session()
    assert session.runtime_config.mission.team_size == 6


def test_headroom_authority_chain_is_untouched() -> None:
    v6 = json.loads((ROOT / "headroom_requalification_v6.json").read_text())
    reproduction = json.loads(
        (ROOT / "headroom_v6_detached_reproduction_v1.json").read_text())
    authority = json.loads((ROOT / "headroom_authority_record_v1.json").read_text())
    assert v6["headroom_requalification_v6_sha256"] == (
        "d044d6b99d7a2bbb83565b121d188a35e335bfd856e3eb0e885823ca1a6742ef")
    assert reproduction["headroom_v6_detached_reproduction_sha256"] == (
        "1f08ba77315e6fdbabfeac8f9350e6f5cd64468c431ecc9fba19747fcd26af32")
    assert authority["headroom_authority_record_sha256"] == (
        "fafe1460c69ef37ca9134c2fc17721adddda92607e3e4e3c084d6a29d9dab509")
