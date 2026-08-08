"""PCA-16 -- four-epoch runtime stress. TEST-ONLY fixture.

PCA-16A provenance, stated up front: this fixture is **not** evidence that any
F1-F10 scientific mission contains four transitions. Scientific scenario event
counts are unchanged. It answers exactly one question:

    can the frozen publication runtime execute arbitrarily repeated transition
    epochs without stale-state contamination?

The fixture pushes the goal *reference* far along the mission axis so the run is
not terminated by GOAL_COMPLETE (approach C). No scientific layout, horizon,
split, job, dataset, headroom count or paper result is touched, and this fixture
never enters any manifest.
"""
from __future__ import annotations
import math, pytest
from rvt_swarm.phase9c_rb import policies as P
from rvt_swarm.phase9c_rb.policies import SourcePolicy
from rvt_swarm.topology_registry import COMPACT, LINE
from tests.test_phase9c_publication_executor import build_session
from tests.test_phase9c_two_epoch_transition import _run_epoch, _settle

SEQUENCE = (COMPACT, LINE, COMPACT)          # after epoch 1 establishes LINE


def _stress_harness():
    session = build_session("train-f1-00", policy_id=P.S2)
    ex, ey = session.mission_direction
    # TEST-ONLY: non-terminal mission reference so goal completion does not
    # preempt the lifecycle stress. Never used by any scientific evaluation.
    session.goal_center = (session.mission_origin[0] + ex * 500.0,
                           session.mission_origin[1] + ey * 500.0)
    session.horizon_seconds = 600.0
    assert _settle(session), "epoch 1 (S2 forced conversion) did not complete"
    session.source_policy = SourcePolicy({}, 0, session.horizon_seconds, session.team_size)
    return session


def test_four_complete_epochs_execute() -> None:
    session = _stress_harness()
    assert {r.protocol_node.mode_epoch_count for r in session.robots} == {1}
    for index, target in enumerate(SEQUENCE, start=2):
        assert _run_epoch(session, target, steps=900), f"epoch {index} failed"
        assert {r.protocol_node.mode_epoch_count for r in session.robots} == {index}
        assert {r.committed_topology for r in session.robots} == {target}
    assert {r.protocol_node.mode_epoch_count for r in session.robots} == {4}


def test_epoch_identifiers_are_strictly_monotonic() -> None:
    session = _stress_harness()
    observed = [sorted({r.protocol_node.mode_epoch_count for r in session.robots})[0]]
    for target in SEQUENCE:
        _run_epoch(session, target, steps=900)
        observed.append(sorted({r.protocol_node.mode_epoch_count for r in session.robots})[0])
    assert observed == [1, 2, 3, 4]


def test_topology_sequence_alternates_correctly() -> None:
    session = _stress_harness()
    observed = [sorted({r.committed_topology for r in session.robots})[0]]
    for target in SEQUENCE:
        _run_epoch(session, target, steps=900)
        observed.append(sorted({r.committed_topology for r in session.robots})[0])
    assert observed == [LINE, COMPACT, LINE, COMPACT]


def test_every_epoch_records_its_own_distributed_completion() -> None:
    session = _stress_harness()
    for target in SEQUENCE:
        _run_epoch(session, target, steps=900)
    agreements = session.completion_agreements
    assert len(agreements) == 4
    assert all(a["agreed"] for a in agreements)
    assert len({a["lifecycle_id"] for a in agreements}) == 4
    assert len({a["epoch_id"] for a in agreements}) == 4
    times = [a["status_agreement_time_seconds"] for a in agreements]
    assert times == sorted(times)
    for record in agreements:
        assert record["status_agreement_time_seconds"] > record[
            "local_dwell_complete_time_seconds"]


def test_no_stale_state_survives_any_rearm() -> None:
    session = _stress_harness()
    for target in SEQUENCE:
        _run_epoch(session, target, steps=900)
        for _ in range(60):
            session.step()
            if all(r.protocol_node.state in ("REARMED", "STABLE_TOPOLOGY")
                   for r in session.robots):
                break
        for robot in session.robots:
            node = robot.protocol_node
            assert node.active_intent is None
            assert node._score_agreed is False
            assert node._all_ready is False
            assert node._confirmed is False
            assert node.dwell_started_seconds is None
            assert node.local_dwell_complete is False
            assert robot.transition_executor is None


def test_the_four_epoch_chain_is_collision_free() -> None:
    session = _stress_harness()
    for target in SEQUENCE:
        _run_epoch(session, target, steps=900)
    minimum = min(math.dist(a.position, b.position)
                  for i, a in enumerate(session.robots) for b in session.robots[i + 1:])
    required = float(session.runtime_config.derived.robot_robot_required_clearance_meters)
    assert minimum >= required
    assert session.termination is None or session.termination.cause != "COLLISION"


def test_the_fixture_is_test_only_and_not_a_scientific_scenario() -> None:
    """PCA-16A: the harness must not resemble a compiled scientific cell."""
    import json, pathlib
    session = _stress_harness()
    spec = json.loads(pathlib.Path(
        "results/rvt_fd24/layout_execution_specifications/train/train-f1-00.json").read_text())
    assert session.goal_center != tuple(spec["goal_contract"]["center_meters"]), (
        "the stress harness must not reuse the scientific goal")
    assert session.horizon_seconds != spec["episode_horizon_seconds"]
