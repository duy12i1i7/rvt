"""RB-7 -- complete deterministic snapshot and restore."""
from __future__ import annotations
import json, pytest
from rvt_swarm.phase9c_rb import policies as P
from rvt_swarm.phase9c_rb.counterfactual import (
    canonical_execution_hash, canonical_execution_state, snapshot)
from rvt_swarm.topology_registry import COMPACT, LINE
from tests.test_phase9c_publication_executor import build_session, run

REQUIRED_SECTIONS = {"simulator", "robots", "communication", "dynamic_obstacles",
                     "disturbance", "seed_streams", "mission_and_evaluator",
                     "source_policy", "event_log"}


def _session(layout="train-f9-00", policy_id=P.S0, steps=18):
    return run(build_session(layout, policy_id=policy_id), steps=steps)


def test_snapshot_covers_every_required_subsystem() -> None:
    state = canonical_execution_state(_session())
    assert REQUIRED_SECTIONS <= set(state)


def test_snapshot_is_json_serializable() -> None:
    json.dumps(canonical_execution_state(_session()), sort_keys=True)


@pytest.mark.parametrize("field", [
    "position_meters", "velocity_meters_per_second",
    "acceleration_meters_per_second_squared", "committed_topology",
    "transition_progress", "safety_unresolved", "safety_infeasible_seen",
    "safety_solver_failure_seen", "protocol", "neighbour_table", "policy_state"])
def test_every_robot_field_is_captured(field) -> None:
    for robot in canonical_execution_state(_session())["robots"]:
        assert field in robot


@pytest.mark.parametrize("field", [
    "state", "committed_topology", "mode_epoch_count", "abort_cause",
    "active_intent", "state_entered_seconds"])
def test_protocol_lifecycle_fields_are_captured(field) -> None:
    for robot in canonical_execution_state(_session())["robots"]:
        assert field in robot["protocol"]


@pytest.mark.parametrize("field", [
    "tick", "sequence_by_link", "queued_messages", "cut_active",
    "prf_identity", "assumption_violation_observed"])
def test_communication_state_is_captured(field) -> None:
    assert field in canonical_execution_state(_session("train-f8-01"))["communication"]


@pytest.mark.parametrize("field", [
    "segment_index", "episode_time_seconds", "position_meters",
    "velocity_meters_per_second", "seed_identity"])
def test_dynamic_obstacle_state_is_captured(field) -> None:
    obstacles = canonical_execution_state(_session())["dynamic_obstacles"]
    assert obstacles and field in obstacles[0]


@pytest.mark.parametrize("field", [
    "max_longitudinal_progress", "irreversible_loss_open", "deadlock_window_elapsed",
    "deadlock_window_start_progress", "metric_v3_dwell_seconds", "lifecycle_counter"])
def test_evaluator_windows_and_dwell_clocks_are_captured(field) -> None:
    assert field in canonical_execution_state(_session())["mission_and_evaluator"]


def test_source_policy_event_state_is_captured() -> None:
    policy_state = canonical_execution_state(_session())["source_policy"]
    assert "fired" in policy_state and "dispositions" in policy_state


def test_s3_hysteresis_and_s5_perturbation_state_are_captured() -> None:
    s3 = canonical_execution_state(_session(policy_id=P.S3))["source_policy"]
    assert "evidence_seconds" in s3 and "last_request_time" in s3
    s5 = canonical_execution_state(_session(policy_id=P.S5))["source_policy"]
    assert "s5_applied" in s5 and "s5_target_robot_id" in s5


def test_s4_local_evidence_state_is_captured() -> None:
    s4 = canonical_execution_state(_session(policy_id=P.S4))["source_policy"]
    assert "s4_evidence_seconds" in s4 and "s4_last_request_time" in s4


def test_round_trip_after_aggressive_mutation_is_exact() -> None:
    session = _session()
    snap = snapshot(session)
    before = snap.canonical_hash
    for robot in session.robots:
        robot.position = (999.0, -999.0)
        robot.velocity = (5.0, 5.0)
        robot.committed_topology = LINE
        robot.neighbour_table.clear()
        robot.safety_unresolved = True
        robot.protocol_node.state = "ABORTED"
    session.control_step += 77
    session.time_seconds += 11.5
    session.channel.tick += 40
    session.channel.queue.clear()
    session.max_longitudinal_progress = -5.0
    session.collision_detected = True
    session.metric_v3_dwell[COMPACT] = 99.0
    assert canonical_execution_hash(session) != before
    assert canonical_execution_hash(snap.restore()) == before


def test_the_deep_copy_and_the_canonical_dict_agree() -> None:
    snap = snapshot(_session())
    assert canonical_execution_state(snap.restore()) == snap.canonical_state


def test_restore_yields_an_independent_object() -> None:
    snap = snapshot(_session())
    a, b = snap.restore(), snap.restore()
    a.robots[0].position = (1.0, 2.0)
    assert canonical_execution_hash(b) == snap.canonical_hash
    assert canonical_execution_hash(snap._session) == snap.canonical_hash


def test_snapshot_hash_changes_when_execution_advances() -> None:
    session = _session()
    before = canonical_execution_hash(session)
    session.step()
    assert canonical_execution_hash(session) != before
