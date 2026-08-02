"""No complete-swarm graph or pooling path may enter deployable V2."""

import inspect

import torch

from rvt_swarm.decentralized import ego_graph_v2, guards
from rvt_swarm.decentralized.ego_graph_v2 import build_robot_local_ego_graph
from rvt_swarm.topology_registry import KEEP


def test_strict_decentralization_and_global_graph_import_guards_are_green():
    assert guards.audit() == []
    assert guards.scan_global_pooling_paths() == []


def test_v2_builder_has_no_known_global_pooling_or_joint_graph_call():
    source = inspect.getsource(ego_graph_v2)
    forbidden = (
        "global_mean_pool(", "global_max_pool(", "global_add_pool(",
        "global_attention_pool(", "pooled_graph_features(",
        "build_legacy_global_graph(", "build_graph_arrays(",
    )
    assert all(token not in source for token in forbidden)


def test_physical_edges_are_root_incident_and_never_peer_to_peer(
    ego_v2_factory,
):
    case = ego_v2_factory(
        n=12,
        root=4,
        peer_ids=(0, 1, 2, 3, 5, 6, 7),
        obstacles=((1.0, 0.0, 0.1), (1.4, 0.2, 0.2)),
    )
    graph = build_robot_local_ego_graph(
        case.view, case.config, case.local_topology, KEEP, case.observation_step
    )
    root_incident = (graph.edge_index[0] == 0) | (graph.edge_index[1] == 0)
    assert bool(root_incident.all())
    assert not bool(((graph.edge_index[0] != 0) & (graph.edge_index[1] != 0)).any())


def test_consumer_contract_retains_one_root_per_batched_local_graph(
    ego_v2_factory,
):
    from rvt_swarm.decentralized.ego_graph_v2 import batch_robot_local_ego_graphs

    graphs = []
    for root in range(3):
        case = ego_v2_factory(root=root, peer_ids=tuple(i for i in range(3) if i != root))
        graphs.append(build_robot_local_ego_graph(
            case.view, case.config, case.local_topology, KEEP, case.observation_step
        ))
    batch = batch_robot_local_ego_graphs(graphs)
    assert batch.root_index.numel() == len(graphs)
    assert torch.equal(
        batch.graph_index[batch.root_index],
        torch.arange(len(graphs), dtype=torch.int64),
    )
