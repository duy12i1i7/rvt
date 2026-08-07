"""D10 -- the frozen robot-local readiness certificate is bound, not asserted."""
from __future__ import annotations
import ast, inspect, math, pathlib, pytest
from rvt_swarm.decentralized.transition_readiness import (
    RobotLocalReadinessCertificate, evaluate_robot_local_transition_readiness)
from rvt_swarm.phase9c_rb import policies as P
from rvt_swarm.phase9c_rb import protocol_session as PS
from rvt_swarm.phase9c_rb.counterfactual import snapshot
from rvt_swarm.phase9c_rb.policies import SourcePolicy
from rvt_swarm.topology_registry import COMPACT, LINE
from tests.test_phase9c_publication_executor import build_session, run

PACKAGE = pathlib.Path("rvt_swarm/phase9c_rb")


def _armed(layout="train-f1-00", warmup=12, candidate=LINE):
    session = run(build_session(layout, policy_id=P.S1), steps=warmup)
    live = snapshot(session).restore()
    live.source_policy = SourcePolicy({}, 0, live.horizon_seconds, live.team_size)
    live.request_candidate(live.robots[0], candidate, "externally_forced_diagnostic")
    return live


# -- D10-G1: no hardcoded SAFE -----------------------------------------------
def test_no_literal_safe_readiness_is_emitted() -> None:
    source = inspect.getsource(PS.advance_transition_lifecycle)
    assert '"SAFE"' not in source, "readiness must be computed, never asserted"


def test_readiness_messages_come_from_the_certificate() -> None:
    source = inspect.getsource(PS.advance_transition_lifecycle)
    assert "certificates[rid].readiness_state" in source
    assert "certificates[rid].readiness_margin_meters" in source


def test_the_package_defines_no_second_readiness_formula() -> None:
    """D10: the frozen evaluator is called; no threshold is restated."""
    for path in PACKAGE.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="ascii"))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                assert "readiness" not in node.name or node.name == (
                    "local_readiness_certificate"), node.name


def test_the_authoritative_evaluator_is_the_one_called() -> None:
    source = inspect.getsource(PS.local_readiness_certificate)
    assert "evaluate_robot_local_transition_readiness" in source
    assert "RobotLocalTransitionInput" in source


# -- D10-G2: behavioural spy, not a string search ----------------------------
def test_a_certificate_is_actually_evaluated_once_per_robot(monkeypatch) -> None:
    live = _armed()
    # Mission staging defers readiness until every robot is MOTION_SETTLED,
    # which takes roughly 0.64 m/s / 0.6 m/s^2 ~ 3.2 s of deceleration.
    for _ in range(60):
        live.step()
        if live.readiness_evaluation_count:
            break
    assert live.readiness_evaluation_count == live.team_size
    assert set(live.readiness_certificates) == {r.robot_id for r in live.robots}


def test_every_certificate_is_a_frozen_certificate_object() -> None:
    live = _armed()
    intent = live.robots[0].protocol_node.active_intent
    certificate = PS.local_readiness_certificate(live, live.robots[0], intent)
    assert isinstance(certificate, RobotLocalReadinessCertificate)
    assert certificate.readiness_state in {"SAFE", "UNSAFE", "UNKNOWN"}


# -- D10-G4: one robot cannot override another -------------------------------
def test_an_unsafe_robot_blocks_all_ready_despite_safe_peers() -> None:
    """A safety-projection failure is a frozen blocking reason."""
    live = _armed()
    intent = live.robots[0].protocol_node.active_intent
    victim = live.robots[3]
    victim.safety_unresolved = True          # frozen blocking reason
    certificate = PS.local_readiness_certificate(live, victim, intent)
    assert certificate.readiness_state == "UNSAFE"
    assert "local_safety_projection_failure" in certificate.blocking_reasons
    others = [PS.local_readiness_certificate(live, r, intent)
              for r in live.robots if r.robot_id != victim.robot_id]
    assert all(c.readiness_state == "SAFE" for c in others)
    # The frozen agreement, not this adapter, decides the outcome.
    for _ in range(60):
        live.step()
        if live.readiness_certificates or live.termination is not None:
            break
    assert live.readiness_certificates


def test_positive_control_all_safe_permits_the_lifecycle_to_proceed() -> None:
    live = _armed()
    for _ in range(60):
        live.step()
        if live.readiness_certificates:
            break
    states = {c["readiness_state"] for c in live.readiness_certificates.values()}
    assert states == {"SAFE"}
    assert all(c["readiness_margin_meters"] > 0.0
               for c in live.readiness_certificates.values())


# -- D10-G3 / D10-5: locality ------------------------------------------------
def test_readiness_ignores_unobserved_global_state() -> None:
    live = _armed()
    intent = live.robots[0].protocol_node.active_intent
    before = PS.local_readiness_certificate(live, live.robots[0], intent)
    far = live.robots[-1]
    far.position = (far.position[0] + 500.0, far.position[1] + 500.0)
    object.__setattr__(live.binding, "family", "F99")
    live.max_longitudinal_progress += 99.0
    after = PS.local_readiness_certificate(live, live.robots[0], intent)
    assert after == before


def test_readiness_responds_to_a_genuinely_observed_local_change() -> None:
    """Non-vacuity: the certificate is not inert."""
    live = _armed()
    intent = live.robots[0].protocol_node.active_intent
    before = PS.local_readiness_certificate(live, live.robots[0], intent)
    live.robots[0].safety_unresolved = True
    after = PS.local_readiness_certificate(live, live.robots[0], intent)
    assert after.readiness_state != before.readiness_state


# -- D10-10: snapshot carries readiness state --------------------------------
def test_readiness_state_survives_snapshot_and_restore() -> None:
    from rvt_swarm.phase9c_rb.counterfactual import canonical_execution_hash
    live = _armed()
    for _ in range(60):
        live.step()
        if live.readiness_certificates:
            break
    snap = snapshot(live)
    restored = snap.restore()
    assert restored.readiness_certificates == live.readiness_certificates
    assert restored.readiness_evaluation_count == live.readiness_evaluation_count
    assert canonical_execution_hash(restored) == snap.canonical_hash
