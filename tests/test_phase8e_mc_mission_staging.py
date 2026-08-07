"""TS -- mission-staged topology transition (owner decision 1)."""
from __future__ import annotations
import ast, inspect, math, pathlib, re, pytest
from rvt_swarm.phase9c_rb import policies as P
from rvt_swarm.phase9c_rb import staging as S
from rvt_swarm.phase9c_rb.counterfactual import canonical_execution_hash, snapshot
from rvt_swarm.phase9c_rb.policies import SourcePolicy
from rvt_swarm.runtime_configuration import DEFAULT_RUNTIME_CONFIG as CONFIG
from rvt_swarm.topology_registry import COMPACT, LINE
from tests.test_phase9c_publication_executor import build_session, run

PACKAGE = pathlib.Path("rvt_swarm/phase9c_rb")


def _staged(candidate=LINE, source=P.S1, warmup=12):
    session = run(build_session("train-f1-00", policy_id=source), steps=warmup)
    live = snapshot(session).restore()
    live.source_policy = SourcePolicy({}, 0, live.horizon_seconds, live.team_size)
    live.request_candidate(live.robots[0], candidate, "externally_forced_diagnostic")
    return live


# -- TS-1: derived threshold, no new constant --------------------------------
def test_v_settle_is_a_max_times_dt() -> None:
    expected = (float(CONFIG.physical.maximum_acceleration_meters_per_second_squared)
                * float(CONFIG.physical.control_period_seconds))
    assert S.settle_speed_threshold(CONFIG) == pytest.approx(expected)
    assert expected == pytest.approx(0.09)


def test_no_independent_numeric_settle_threshold_is_written() -> None:
    source = inspect.getsource(S)
    assert "0.09" not in source, "the threshold must be derived, never literal"
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Constant) and isinstance(node.value, float):
            raise AssertionError(f"float literal {node.value} in staging module")


def test_the_predicate_has_no_scaling_coefficient_or_epsilon() -> None:
    source = inspect.getsource(S.motion_settled)
    assert not re.search(r"\*\s*0?\.\d", source)
    assert "1e-" not in source


def test_motion_settled_matches_the_derived_threshold_exactly() -> None:
    live = _staged()
    threshold = S.settle_speed_threshold(live.runtime_config)
    robot = live.robots[0]
    robot.velocity = (threshold, 0.0)
    assert S.motion_settled(robot, live.runtime_config) is True
    robot.velocity = (threshold * 1.0001, 0.0)
    assert S.motion_settled(robot, live.runtime_config) is False


# -- TS-2 / TS-3: what stages, and what does not -----------------------------
def test_hold_candidate_never_stages() -> None:
    live = _staged(candidate=COMPACT)          # already COMPACT
    for robot in live.robots:
        assert S.mission_staged(robot) is False
    live.step()
    assert not any(r.mission_staged for r in live.robots)


def test_changed_candidate_stages_locally() -> None:
    live = _staged()
    live.step()
    assert any(r.mission_staged for r in live.robots)


def test_staging_is_gated_by_the_robots_own_lifecycle_state_only() -> None:
    source = inspect.getsource(S.mission_staged)
    assert "protocol_node.state" in source
    assert "session" not in source, "the gate must not consult global state"


def test_staged_states_are_existing_frozen_names() -> None:
    from rvt_swarm.decentralized.transition_protocol import TransitionProtocolNode
    node_source = inspect.getsource(TransitionProtocolNode)
    for state in S.MISSION_STAGED_STATES + S.MISSION_RESUMED_STATES:
        assert f'"{state}"' in node_source, state


def test_no_centralized_pause_command_exists() -> None:
    text = "\n".join(p.read_text(encoding="ascii") for p in PACKAGE.glob("*.py"))
    for forbidden in ("PAUSE_ALL", "pause_all", "global_pause", "freeze_all"):
        assert forbidden not in text, forbidden


# -- TS-2: only the goal term is suppressed ----------------------------------
def test_only_the_goal_term_is_removed_from_the_base_action() -> None:
    source = inspect.getsource(
        __import__("rvt_swarm.phase9c_rb.session", fromlist=["x"]).SimulatorEpisodeSession.step)
    assert "output.goal_term" in source
    for retained in ("formation_term", "damping_term", "obstacle_term"):
        assert f"output.{retained}" not in source, (
            f"{retained} must remain untouched, not be re-composed")


def test_safety_projection_is_reapplied_to_the_staged_base() -> None:
    source = inspect.getsource(
        __import__("rvt_swarm.phase9c_rb.session", fromlist=["x"]).SimulatorEpisodeSession.step)
    assert "projection.project(staged_base, controller_input)" in source


def test_controller_gains_and_bounds_are_unchanged() -> None:
    assert float(CONFIG.controller.goal_gain) == 1.0
    assert float(CONFIG.controller.formation_gain) == 1.0
    assert float(CONFIG.controller.damping_gain) == 1.0
    assert float(CONFIG.physical.maximum_acceleration_meters_per_second_squared) == 0.6
    assert float(CONFIG.physical.maximum_speed_meters_per_second) == 0.9


# -- TS-5: decentralization ---------------------------------------------------
def test_the_settle_predicate_uses_only_own_velocity_and_frozen_config() -> None:
    source = inspect.getsource(S.motion_settled)
    assert "robot.velocity" in source
    assert "session" not in source and "robots" not in source


# -- TS-8: staging is not free ------------------------------------------------
def test_simulator_time_continues_during_staging() -> None:
    live = _staged()
    before = live.time_seconds
    for _ in range(6):
        live.step()
    assert live.time_seconds > before


def test_velocity_is_not_zeroed_instantaneously() -> None:
    live = _staged()
    speeds = [math.hypot(*r.velocity) for r in live.robots]
    live.step()
    after = [math.hypot(*r.velocity) for r in live.robots]
    assert all(a > 0.0 for a in after), "robots must decelerate, not teleport to rest"
    assert any(a < b for a, b in zip(after, speeds))


def test_a_staged_transition_costs_mission_time() -> None:
    hold = run(build_session("train-f1-00", policy_id=P.S1), steps=600)
    live = _staged()
    for _ in range(600):
        live.step()
        if live.termination is not None:
            break
    assert live.control_step > hold.control_step, (
        "staging plus profile plus dwell must cost time relative to a hold")


# -- TS-9: snapshot ------------------------------------------------------------
def test_mid_staging_snapshot_reproduces_the_future_trace() -> None:
    live = _staged()
    for _ in range(4):
        live.step()
    assert any(r.mission_staged for r in live.robots)
    assert not all(S.motion_settled(r, live.runtime_config) for r in live.robots)
    snap = snapshot(live)
    restored = snap.restore()
    for _ in range(12):
        live.step()
        restored.step()
        assert canonical_execution_hash(live) == canonical_execution_hash(restored)


# -- TS-4 / TS-6 / TS-7 --------------------------------------------------------
def test_readiness_implementation_is_untouched() -> None:
    from rvt_swarm.decentralized import transition_readiness as R
    assert hasattr(R, "evaluate_robot_local_transition_readiness")
    text = "\n".join(p.read_text(encoding="ascii") for p in PACKAGE.glob("*.py"))
    assert "def evaluate_robot_local_transition_readiness" not in text


def _min_separation(live, steps=600):
    minimum = float("inf")
    for _ in range(steps):
        live.step()
        minimum = min(minimum, min(
            math.dist(a.position, b.position)
            for i, a in enumerate(live.robots) for b in live.robots[i + 1:]))
        if live.termination is not None:
            break
    return minimum, live


def test_open_space_compact_to_line_clears_the_frozen_requirement() -> None:
    minimum, live = _min_separation(_staged(candidate=LINE, source=P.S1))
    required = float(live.runtime_config.derived.robot_robot_required_clearance_meters)
    assert minimum >= required, f"{minimum:.4f} < {required}"
    assert live.termination.cause == "GOAL_COMPLETE"


def test_line_to_compact_clears_the_frozen_requirement() -> None:
    minimum, live = _min_separation(_staged(candidate=COMPACT, source=P.S2))
    required = float(live.runtime_config.derived.robot_robot_required_clearance_meters)
    assert minimum >= required, f"{minimum:.4f} < {required}"
    assert live.termination.cause == "GOAL_COMPLETE"
