"""F5-R re-run under the CORRECTLY BOUND frozen readiness certificate.

BLOCKING FINDING. Every assertion below records verified behaviour after
Defect 10 was fixed. Nothing was retuned to make F5 pass; the frozen readiness
certificate simply refuses F5's COMPACT -> LINE transition.
"""
from __future__ import annotations
import pytest
from rvt_swarm.phase9c_rb import policies as P
from rvt_swarm.topology_registry import COMPACT, LINE
from tests.test_phase9c_publication_executor import build_session

BOTTLENECK_0 = (2.00, 3.50)
BOTTLENECK_1 = (6.50, 8.00)


def _run(policy_id=P.S0, steps=700):
    session = build_session("train-f5-00", policy_id=policy_id)
    for _ in range(steps):
        session.step()
        if session.termination is not None:
            break
    return session


def test_the_first_constriction_event_is_still_originated() -> None:
    session = _run(steps=40)
    first = session.source_policy.dispositions[0]
    assert first["disposition"] == "ORIGINATED"
    assert first["candidate_topology"] == LINE


def test_the_lifecycle_reaches_all_ready_and_evaluates_real_certificates() -> None:
    session = _run(steps=40)
    assert session.readiness_certificates
    assert session.readiness_evaluation_count == session.team_size


def test_at_least_one_robot_is_unsafe_with_a_frozen_blocking_reason() -> None:
    session = _run(steps=40)
    unsafe = [c for c in session.readiness_certificates.values()
              if c["readiness_state"] == "UNSAFE"]
    assert unsafe, "the readiness gate must actually bite here"
    assert any("local_obstacle_envelope_clearance" in c["blocking_reasons"]
               for c in unsafe)
    assert any(c["readiness_margin_meters"] < 0.0 for c in unsafe)


def test_one_unsafe_robot_blocks_the_transition_despite_safe_peers() -> None:
    session = _run(steps=40)
    states = [c["readiness_state"] for c in session.readiness_certificates.values()]
    assert "SAFE" in states and "UNSAFE" in states
    assert sorted({r.committed_topology for r in session.robots}) == [COMPACT]


def test_the_lifecycle_aborts_rather_than_committing() -> None:
    session = _run(steps=40)
    assert any(r.protocol_node.state == "ABORTED" for r in session.robots)


def test_f5_cannot_perform_even_its_first_online_reconfiguration() -> None:
    """The blocking result: F5 never leaves COMPACT under correct mechanics."""
    session = _run()
    assert sorted({r.committed_topology for r in session.robots}) == [COMPACT]
    assert session.termination.cause == "COLLISION"
    assert session.max_longitudinal_progress < BOTTLENECK_0[0]


def test_fixed_line_still_completes_so_the_geometry_itself_is_feasible() -> None:
    """Geometry feasibility is unchanged; only the online path is blocked."""
    session = _run(policy_id=P.S2)
    assert session.termination.cause == "GOAL_COMPLETE"
    assert session.max_longitudinal_progress >= BOTTLENECK_1[1]


def test_fixed_compact_still_fails_at_the_first_bottleneck() -> None:
    session = _run(policy_id=P.S1)
    assert session.termination.cause == "COLLISION"
    assert session.max_longitudinal_progress < BOTTLENECK_0[0]


def test_no_readiness_threshold_was_retuned() -> None:
    from rvt_swarm.runtime_configuration import DEFAULT_RUNTIME_CONFIG as CONFIG
    assert float(CONFIG.derived.robot_robot_required_clearance_meters) == 0.4
    assert float(CONFIG.derived.robot_obstacle_required_clearance_meters) == 0.55
    assert float(CONFIG.physical.maximum_speed_meters_per_second) == 0.9
