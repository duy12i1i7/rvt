"""Intervention tests for the deployable graph information boundary."""

from dataclasses import replace
import inspect

import pytest
import torch

from rvt_swarm.decentralized.ego_graph_v2 import (
    NODE_FEATURE_SLICES,
    LocalCandidateTopologySlice,
    RobotLocalTopologyMetadata,
    build_robot_local_ego_graph,
)
from rvt_swarm.decentralized.system_model import CentralizedAccessError
from rvt_swarm.topology_registry import KEEP, LINE


def _build(case, candidate=KEEP, local_topology=None):
    return build_robot_local_ego_graph(
        case.view,
        case.config,
        case.local_topology if local_topology is None else local_topology,
        candidate,
        case.observation_step,
    )


@pytest.mark.parametrize("bulk", ({"positions": [(0.0, 0.0)]}, [[0.0, 0.0]]))
def test_builder_rejects_joint_or_mapping_observations(ego_v2_factory, bulk):
    case = ego_v2_factory()
    with pytest.raises(CentralizedAccessError):
        build_robot_local_ego_graph(
            bulk, case.config, case.local_topology, KEEP, case.observation_step
        )


def test_builder_signature_has_no_global_runtime_input():
    parameters = set(inspect.signature(build_robot_local_ego_graph).parameters)
    assert parameters == {
        "view", "runtime_config", "local_topology", "candidate_topology_id",
        "observation_step",
    }


@pytest.mark.parametrize(
    "intervention",
    (
        "out_of_range_robot_position",
        "out_of_range_robot_velocity",
        "unobserved_obstacle",
        "global_swarm_centroid",
        "global_formation_error",
        "unobserved_robot_role",
        "unobserved_robot_topology",
        "evaluation_passage_label",
        "final_mission_outcome",
        "simulator_global_obstacle_ordering",
    ),
)
def test_unobservable_interventions_have_no_graph_channel(
    ego_v2_factory, intervention
):
    case = ego_v2_factory(peer_ids=(), obstacles=())
    external_simulator_state = {intervention: "before"}
    before = _build(case).fingerprint()
    external_simulator_state[intervention] = "after"
    after = _build(case).fingerprint()
    assert external_simulator_state[intervention] == "after"
    assert before == after


def test_changing_fresh_in_range_peer_changes_peer_row(ego_v2_factory):
    a = _build(ego_v2_factory(peer_ids=(1,), peer_local_positions={1: (1.0, 0.0)}))
    b = _build(ego_v2_factory(peer_ids=(1,), peer_local_positions={1: (1.3, 0.0)}))
    assert a.node_source_key == b.node_source_key
    assert not torch.equal(a.node_x[1], b.node_x[1])
    assert torch.equal(a.node_x[0], b.node_x[0])


def test_changing_local_obstacle_changes_only_obstacle_geometry(ego_v2_factory):
    a = _build(ego_v2_factory(peer_ids=(), obstacles=((1.4, 0.0, 0.2),)))
    b = _build(ego_v2_factory(peer_ids=(), obstacles=((1.8, 0.0, 0.2),)))
    assert torch.equal(a.node_x[0], b.node_x[0])
    assert not torch.equal(a.node_x[1], b.node_x[1])


def test_candidate_role_displacement_changes_only_declared_root_blocks(
    ego_v2_factory,
):
    case = ego_v2_factory(peer_ids=(), obstacles=())
    original = case.local_topology.candidate(LINE)
    moved = replace(
        original,
        own_role_offset_meters=(
            original.own_role_offset_meters[0] + 0.2,
            original.own_role_offset_meters[1] - 0.1,
        ),
    )
    local = replace(
        case.local_topology,
        candidates=tuple(
            moved if item.topology_id == LINE else item
            for item in case.local_topology.candidates
        ),
    )
    before = _build(case, LINE)
    after = _build(case, LINE, local)
    changed = set(torch.nonzero(before.node_x[0] != after.node_x[0]).flatten().tolist())
    intended = set()
    for name in (
        "candidate_role_offset_spacing",
        "candidate_role_displacement_spacing",
        "candidate_transition_magnitude_spacing",
        "candidate_observation_extent_range",
    ):
        block = NODE_FEATURE_SLICES[name]
        intended.update(range(block.start, block.stop))
    assert changed
    assert changed <= intended
    assert before.n_nodes == after.n_nodes == 1


def test_local_metadata_cannot_contain_an_unobserved_full_template(ego_v2_factory):
    case = ego_v2_factory(n=8, root=0, peer_ids=())
    fields = set(RobotLocalTopologyMetadata.__dataclass_fields__)
    candidate_fields = set(LocalCandidateTopologySlice.__dataclass_fields__)
    assert "templates" not in fields
    assert "role_offsets" not in fields
    assert "complete_template" not in candidate_fields
    assert _build(case).fingerprint() == _build(case).fingerprint()
