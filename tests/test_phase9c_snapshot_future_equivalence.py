"""RB-7 -- a restored snapshot continues identically to the original."""
from __future__ import annotations
import pytest
from rvt_swarm.phase9c_rb import policies as P
from rvt_swarm.phase9c_rb.counterfactual import canonical_execution_hash, snapshot
from tests.test_phase9c_publication_executor import build_session, run


@pytest.mark.parametrize("layout,policy_id", [
    ("train-f1-00", P.S1), ("train-f2-00", P.S0), ("train-f8-01", P.S3),
    ("train-f9-00", P.S5), ("train-f5-00", P.S2)])
def test_restored_state_produces_an_identical_future_trace(layout, policy_id) -> None:
    original = run(build_session(layout, policy_id=policy_id), steps=12)
    snap = snapshot(original)
    restored = snap.restore()
    for _ in range(15):
        original.step()
        restored.step()
        assert canonical_execution_hash(original) == canonical_execution_hash(restored)


def test_two_independent_restores_stay_identical() -> None:
    snap = snapshot(run(build_session("train-f9-00", policy_id=P.S0), steps=10))
    a, b = snap.restore(), snap.restore()
    for _ in range(20):
        a.step()
        b.step()
    assert canonical_execution_hash(a) == canonical_execution_hash(b)


def test_a_mutated_restore_diverges_so_the_check_is_not_vacuous() -> None:
    snap = snapshot(run(build_session("train-f1-00", policy_id=P.S1), steps=10))
    a, b = snap.restore(), snap.restore()
    b.robots[0].velocity = (b.robots[0].velocity[0] + 0.05, b.robots[0].velocity[1])
    for _ in range(10):
        a.step()
        b.step()
    assert canonical_execution_hash(a) != canonical_execution_hash(b)
