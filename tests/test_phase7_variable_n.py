import pytest

from rvt_swarm.runtime_configuration import RuntimeConfig
from rvt_swarm.topology_registry import PRIMARY_TOPOLOGY_IDS
from rvt_swarm.decentralized.transition_protocol import (
    TransitionProtocolNode,
    TransitionProtocolRuntimeOptions,
)
from rvt_swarm.decentralized.transition_runtime import (
    StrictTransitionRuntime,
    communication_graph,
)


@pytest.mark.parametrize("n", (5, 6, 8, 12, 16, 24))
def test_protocol_constructs_one_local_node_and_three_slices_per_robot(n):
    runtime = StrictTransitionRuntime(
        n, 0, communication_graph(n, "path"),
        options=TransitionProtocolRuntimeOptions(True),
    )
    assert len(runtime.nodes) == n
    assert all(
        tuple(item.topology_id for item in metadata.candidates)
        == PRIMARY_TOPOLOGY_IDS
        for metadata in runtime.local_metadata
    )
    derived = runtime.runtime_config.derived
    assert derived.k_intent_rounds >= derived.component_diameter_bound_hops
    assert derived.k_score_rounds >= derived.component_diameter_bound_hops
    assert derived.k_ready_rounds >= derived.component_diameter_bound_hops
    assert derived.k_confirm_rounds >= derived.component_diameter_bound_hops


@pytest.mark.parametrize("topology", PRIMARY_TOPOLOGY_IDS)
def test_source_equals_target_request_creates_zero_mode_epochs(topology):
    node = TransitionProtocolNode(
        0, tuple(range(5)), RuntimeConfig.for_team_size(5), topology,
        TransitionProtocolRuntimeOptions(True),
    )
    assert node.request_intent(
        1, topology, "externally_forced_diagnostic", 0.0
    ) is None
    assert node.mode_epoch_count == 0
    assert node.state == "STABLE_TOPOLOGY"
