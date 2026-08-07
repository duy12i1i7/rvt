"""RB-8 -- deep candidate clone isolation and matched initial state."""
from __future__ import annotations
import pytest
from rvt_swarm.phase9c_rb import policies as P
from rvt_swarm.phase9c_rb.counterfactual import (
    canonical_execution_hash, clone_pair, snapshot)
from rvt_swarm.topology_registry import COMPACT, LINE
from tests.test_phase9c_publication_executor import build_session, run


def _snapshot(layout="train-f8-01", policy_id=P.S0, steps=15):
    return snapshot(run(build_session(layout, policy_id=policy_id), steps=steps))


def test_clone_hashes_match_source_before_injection() -> None:
    snap = _snapshot()
    a, b = clone_pair(snap)
    assert canonical_execution_hash(a) == canonical_execution_hash(b) == snap.canonical_hash


@pytest.mark.parametrize("layout", ["train-f1-00", "train-f2-00", "train-f5-00",
                                    "train-f8-01", "train-f9-00"])
def test_clone_equality_holds_across_families(layout) -> None:
    snap = _snapshot(layout)
    a, b = clone_pair(snap)
    assert canonical_execution_hash(a) == canonical_execution_hash(b)


def test_aggressive_mutation_of_one_clone_leaves_the_other_untouched() -> None:
    snap = _snapshot()
    a, b = clone_pair(snap)
    for robot in a.robots:
        robot.position = (42.0, -42.0)
        robot.committed_topology = LINE
        robot.neighbour_table.clear()
        robot.protocol_node.state = "ABORTED"
        robot.safety_unresolved = True
    a.channel.tick += 25
    a.channel.queue.clear()
    a.channel.sequence_by_link.clear()
    a.max_longitudinal_progress = -99.0
    a.metric_v3_dwell[COMPACT] = 12.0
    a.event_log.append({"injected": True})
    a.dynamic_world.obstacles  # touched, not mutated
    assert canonical_execution_hash(b) == snap.canonical_hash
    assert canonical_execution_hash(snap._session) == snap.canonical_hash


def test_message_queues_are_not_shared_between_clones() -> None:
    snap = _snapshot()
    a, b = clone_pair(snap)
    assert a.channel is not b.channel
    assert a.channel.queue is not b.channel.queue
    assert a.channel.sequence_by_link is not b.channel.sequence_by_link


def test_protocol_nodes_are_not_shared_between_clones() -> None:
    a, b = clone_pair(_snapshot())
    for left, right in zip(a.robots, b.robots):
        assert left.protocol_node is not right.protocol_node
        assert left.neighbour_table is not right.neighbour_table


def test_stream_objects_are_distinct_and_carry_no_mutable_rng() -> None:
    a, b = clone_pair(_snapshot())
    assert a.position_stream is not b.position_stream
    # Frozen dataclasses: identity only, nothing to advance.
    with pytest.raises(Exception):
        a.position_stream.seed = 5


def test_dynamic_and_evaluator_state_are_not_shared() -> None:
    a, b = clone_pair(_snapshot("train-f9-00"))
    assert a.dynamic_world is not b.dynamic_world
    assert a.metric_v3_dwell is not b.metric_v3_dwell
    assert a.event_log is not b.event_log


def test_source_policy_state_is_not_shared() -> None:
    a, b = clone_pair(_snapshot())
    assert a.source_policy is not b.source_policy
