"""RB-8 / RB-9 -- matched initial state and matched exogenous realizations."""
from __future__ import annotations
import pytest
from rvt_swarm.phase9c_rb import policies as P
from rvt_swarm.phase9c_rb.counterfactual import (
    canonical_execution_hash, execute_candidate, replica_count_for_family, snapshot)
from rvt_swarm.phase9c_rb.streams import CounterStream
from rvt_swarm.topology_registry import COMPACT, LINE
from tests.test_phase9c_publication_executor import build_session, run


def _snapshot(layout="train-f8-01", steps=15):
    return snapshot(run(build_session(layout, policy_id=P.S0), steps=steps))


def test_both_candidates_start_from_the_identical_clone_hash() -> None:
    snap = _snapshot()
    compact = execute_candidate(snap, COMPACT, max_steps=40)
    line = execute_candidate(snap, LINE, max_steps=40)
    assert compact.initial_clone_hash == line.initial_clone_hash == snap.canonical_hash


def test_replica_counts_follow_the_frozen_rule() -> None:
    assert replica_count_for_family("F8") == 3
    assert replica_count_for_family("F9") == 3
    for family in ("F1", "F2", "F3", "F4", "F5", "F6", "F7", "F10"):
        assert replica_count_for_family(family) == 1


def test_replicas_share_the_same_initial_clone_hash() -> None:
    snap = _snapshot()
    hashes = {execute_candidate(snap, COMPACT, replica_index=i,
                                disturbance_seed=99, max_steps=30).initial_clone_hash
              for i in range(3)}
    assert len(hashes) == 1


# -- RB-9 exogenous stream identity, independent of candidate action ---------
def test_counter_streams_are_referentially_transparent() -> None:
    stream = CounterStream(seed=1234, process="robot_acceleration")
    first = [stream.uniform("r", i) for i in range(20)]
    second = [stream.uniform("r", i) for i in range(20)]
    assert first == second, "a draw must not depend on call order"


def test_identical_seed_identity_gives_identical_realizations() -> None:
    a = CounterStream(seed=77, process="communication")
    b = CounterStream(seed=77, process="communication")
    assert [a.uniform(i) for i in range(30)] == [b.uniform(i) for i in range(30)]


def test_a_different_seed_gives_a_different_realization() -> None:
    a = CounterStream(seed=77, process="communication")
    b = CounterStream(seed=78, process="communication")
    assert [a.uniform(i) for i in range(30)] != [b.uniform(i) for i in range(30)]


def test_one_candidate_cannot_advance_the_other_stream() -> None:
    """There is no mutable RNG state, so consumption order cannot leak."""
    a = CounterStream(seed=5, process="robot_acceleration")
    b = CounterStream(seed=5, process="robot_acceleration")
    for i in range(50):
        a.uniform("burned", i)          # candidate A consumes heavily
    assert b.uniform("shared", 0) == a.uniform("shared", 0)


def test_uniform_disk_respects_the_declared_maximum_radius() -> None:
    import math
    stream = CounterStream(seed=9, process="robot_acceleration")
    for i in range(200):
        x, y = stream.uniform_disk(0.03, i)
        assert math.hypot(x, y) <= 0.03 + 1e-12


def test_f8_schedule_is_identical_for_matched_candidates() -> None:
    """Exogenous delay/drop draws match; endogenous divergence is allowed."""
    snap = _snapshot()
    compact = snap.restore()
    line = snap.restore()
    key = (0, 1, 0, "state_broadcast")
    assert compact.channel.stream.identity() == line.channel.stream.identity()
    assert compact.channel.stream.uniform(*key, "delay") == (
        line.channel.stream.uniform(*key, "delay"))
    assert compact.channel.cut_start_tick == line.channel.cut_start_tick
    assert compact.channel.cut_duration_ticks == line.channel.cut_duration_ticks


def test_f9_process_is_identical_for_matched_candidates() -> None:
    snap = _snapshot("train-f9-00")
    a, b = snap.restore(), snap.restore()
    for t in (0.0, 3.0, 6.0, 9.0, 12.0, 20.0):
        assert a.dynamic_world.obstacles[0].state(t) == b.dynamic_world.obstacles[0].state(t)
    assert (a.dynamic_world.obstacles[0].seed_identity
            == b.dynamic_world.obstacles[0].seed_identity)
