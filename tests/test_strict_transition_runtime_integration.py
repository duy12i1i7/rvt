import pytest

from rvt_swarm.decentralized.transition_protocol import TransitionProtocolRuntimeOptions
from rvt_swarm.decentralized.transition_runtime import (
    StrictTransitionRuntime,
    communication_graph,
    run_phase7_transition_episode,
)


def test_strict_runtime_is_disabled_by_default():
    with pytest.raises(RuntimeError):
        StrictTransitionRuntime(5, 0, communication_graph(5, "path"))


def test_one_independent_protocol_instance_per_robot():
    runtime = StrictTransitionRuntime(
        8, 0, communication_graph(8, "ring"),
        options=TransitionProtocolRuntimeOptions(True),
    )
    assert len(runtime.nodes) == 8
    assert len({id(node) for node in runtime.nodes}) == 8
    assert len({id(node.__dict__) for node in runtime.nodes}) == 8


def test_real_runtime_changes_topology_only_after_agreements_and_uses_no_model():
    result = run_phase7_transition_episode(5, 0, 2, "exact_source", "complete")
    assert result.transition_success
    assert result.mode_epoch_count == 1
    assert not result.partial_commitment
    assert result.actual_communication_bytes == sum(result.bytes_by_phase.values())
    assert result.learned_model_calls == 0
    assert result.protocol_instance_count == 5
    for trace in result.state_trace_by_robot.values():
        assert trace.index("TOPOLOGY_COMMITTED") > trace.index("TOPOLOGY_CONFIRMATION")
        assert trace.index("TRANSITION_EXECUTION") > trace.index("TOPOLOGY_COMMITTED")
