"""PCA-15 -- the real frozen timeout path.

PCA-15.0 finding: `TransitionProtocolNode` has **no** timeout method and **no**
deadline config field. The frozen "timeout" is outer-loop budget exhaustion --
`transition_runtime.py:926` assigns `abort = "transition_or_dwell_timeout"` when
`dwell_completion is None` after the episode's step budget runs out, and
`:657` labels a failed readiness agreement `"readiness_timeout:<reason>"`.

There is therefore no runtime-required frozen timeout *method* for the adapter
to bind, and no class-A omission. The publication equivalent is the episode
horizon: a lifecycle still active when the horizon is reached fails Target V4's
`protocol_resolved` predicate through its frozen failure state
`active_state_at_horizon`.

The fixture here is RUNTIME_CONFORMANCE_ONLY: it shortens only its own session's
horizon. No scientific layout, horizon, ET schedule, geometry, safety margin,
readiness threshold or communication parameter is touched.
"""
from __future__ import annotations
import json, pathlib, pytest
from rvt_swarm.phase8e.target import evaluate_target_v4
from rvt_swarm.phase9c_rb import policies as P
from rvt_swarm.phase9c_rb.counterfactual import (
    build_execution_summary, canonical_execution_hash, snapshot)
from rvt_swarm.phase9c_rb.policies import SourcePolicy
from rvt_swarm.topology_registry import COMPACT, LINE
from tests.test_phase9c_publication_executor import build_session

ROOT = pathlib.Path("results/rvt_fd24")
TARGET = json.loads((ROOT / "target_v4_execution_contract_v1.json").read_text())


def _stalled_lifecycle(margin_seconds=1.5):
    """A transition that cannot finish before its horizon. TEST-ONLY."""
    session = build_session("train-f1-00", policy_id=P.S1)
    for _ in range(12):
        session.step()
    session.source_policy = SourcePolicy({}, 0, session.horizon_seconds, session.team_size)
    assert session.request_candidate(
        session.robots[0], LINE, "externally_forced_diagnostic")
    session.horizon_seconds = session.time_seconds + margin_seconds
    return session


def _run(session, steps=400):
    for _ in range(steps):
        session.step()
        if session.termination is not None:
            break
    return session


# -- PCA-15.0: the frozen contract ---------------------------------------------
def test_the_node_has_no_timeout_method_or_deadline_field() -> None:
    from rvt_swarm.decentralized.transition_protocol import TransitionProtocolNode
    from rvt_swarm.runtime_configuration import DEFAULT_RUNTIME_CONFIG as CONFIG
    import dataclasses
    methods = {n for n in vars(TransitionProtocolNode) if not n.startswith("__")}
    assert not any("timeout" in n or "deadline" in n for n in methods), methods
    fields = {f.name for f in dataclasses.fields(CONFIG.protocol)}
    assert not any("timeout" in f or "deadline" in f for f in fields), fields


def test_active_state_at_horizon_is_a_frozen_failure_state() -> None:
    assert "active_state_at_horizon" in TARGET["conditions"][
        "protocol_resolved"]["failure_states"]


def test_the_frozen_timeout_causes_exist_in_the_vocabulary() -> None:
    for cause in ("PROTOCOL_TIMEOUT", "TRANSITION_TIMEOUT"):
        assert cause in TARGET["termination_causes"]


# -- PCA-15.2/15.5: triggered through normal execution -------------------------
def test_a_stalled_lifecycle_reaches_the_horizon_without_state_mutation() -> None:
    session = _run(_stalled_lifecycle())
    assert session.termination.cause == "HORIZON_COMPLETE"
    # The lifecycle is genuinely still active -- not forced into a terminal state.
    assert any(r.protocol_node.state not in
               ("STABLE_TOPOLOGY", "COMPLETE", "REARMED", "ABORTED")
               for r in session.robots)
    assert all(r.protocol_node.active_intent is not None for r in session.robots)


def test_the_lifecycle_progressed_before_stalling() -> None:
    """Non-vacuity: the fixture must not fail before the protocol starts."""
    session = _stalled_lifecycle()
    states = set()
    for _ in range(400):
        session.step()
        states.update(r.protocol_node.state for r in session.robots)
        if session.termination is not None:
            break
    assert "CANDIDATE_SCORE_AGREEMENT" in states
    assert "ALL_READY_AGREEMENT" in states


# -- PCA-15.6: Target V4 disposition -------------------------------------------
def test_the_timeout_is_a_valid_task_negative_not_generation_invalid() -> None:
    session = _run(_stalled_lifecycle())
    summary = build_execution_summary(session, LINE)
    result = evaluate_target_v4(summary)
    assert summary.predicates.protocol_resolved is False
    assert result.disposition == "VALID_TASK_NEGATIVE"
    assert result.label == 0
    assert "protocol_resolved" in result.failed_predicates


def test_executor_and_numerical_validity_are_untouched_by_the_timeout() -> None:
    session = _run(_stalled_lifecycle())
    summary = build_execution_summary(session, LINE)
    assert summary.executor_completed is True
    assert summary.geometry_valid is True
    assert summary.schedule_conformant is True
    assert summary.predicates.numerically_valid is True


# -- PCA-15.7: no stale success leaks -----------------------------------------
def test_a_timed_out_transition_claims_no_success_from_stale_state() -> None:
    session = _run(_stalled_lifecycle())
    predicates = build_execution_summary(session, LINE).predicates
    assert predicates.candidate_commitment_valid is False
    assert predicates.transition_execution_valid is False
    assert predicates.target_metric_v3_dwell_complete is False
    assert session.completion_agreements == [], (
        "no distributed completion may be recorded for a stalled lifecycle")


# -- PCA-15.10: snapshot/replay reproduces the timeout -------------------------
def test_snapshot_before_the_horizon_reproduces_the_timeout_exactly() -> None:
    session = _stalled_lifecycle()
    for _ in range(3):
        session.step()
    assert session.termination is None
    snap = snapshot(session)
    restored = snap.restore()
    for _ in range(400):
        session.step()
        restored.step()
        assert canonical_execution_hash(session) == canonical_execution_hash(restored)
        if session.termination is not None:
            break
    assert restored.termination is not None
    assert session.termination.cause == restored.termination.cause
    assert session.termination.time_seconds == restored.termination.time_seconds
    assert (evaluate_target_v4(build_execution_summary(session, LINE)).disposition
            == evaluate_target_v4(build_execution_summary(restored, LINE)).disposition)


# -- PCA-15.11: boundary --------------------------------------------------------
def test_the_horizon_boundary_uses_the_authoritative_field() -> None:
    session = _stalled_lifecycle(margin_seconds=10.0)
    _run(session)
    assert session.termination.cause == "HORIZON_COMPLETE"
    assert session.time_seconds >= session.horizon_seconds
    # A generous horizon lets the same lifecycle finish instead.
    generous = _stalled_lifecycle(margin_seconds=200.0)
    _run(generous, steps=900)
    assert generous.completion_agreements, (
        "with enough horizon the same lifecycle completes -- the timeout is the "
        "horizon, not a protocol defect")


# -- PCA-15.12: fixture provenance ---------------------------------------------
def test_the_fixture_is_runtime_conformance_only() -> None:
    session = _stalled_lifecycle()
    spec = json.loads((ROOT / "layout_execution_specifications" / "train"
                       / "train-f1-00.json").read_text())
    assert session.horizon_seconds != spec["episode_horizon_seconds"], (
        "only the harness horizon is shortened; the scientific horizon is intact"
    )
    assert spec["episode_horizon_seconds"] == 90.0
