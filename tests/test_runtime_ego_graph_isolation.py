"""Runtime adapter and historical compatibility-path isolation."""

import ast
import inspect

import torch

from rvt_swarm.config import Config
from rvt_swarm.dataset import build_graph as historical_build_graph
from rvt_swarm.decentralized import runtime
from rvt_swarm.decentralized.ego_graph_v2 import (
    RobotLocalTopologyMetadata,
    build_robot_local_ego_graph,
)
from rvt_swarm.decentralized.ego_graph_runtime_adapter import (
    RobotLocalEgoGraphRuntimeAdapter,
)
from rvt_swarm.environment import SwarmFormationEnv
from rvt_swarm.legacy_global_graph import (
    LEGACY_GLOBAL_GRAPH_SCHEMA,
    build_legacy_global_graph,
)
from rvt_swarm.policy_runtime import batch_from_obs
from rvt_swarm.topology_registry import KEEP


def test_phase4_does_not_replace_active_v1_selector_path():
    source = inspect.getsource(runtime._robot_decision)
    assert "build_ego_graph(view, cfg" in source
    assert "build_robot_local_ego_graph" not in source
    assert "ego_graph_v2" not in inspect.getsource(runtime)


def test_v2_builder_is_the_compatibility_adapter_for_current_robot_view(
    ego_v2_factory,
):
    case = ego_v2_factory()
    graph = build_robot_local_ego_graph(
        case.view, case.config, case.local_topology, KEEP, case.observation_step
    )
    assert graph.observer_robot_id == case.view.robot_id
    assert graph.lifecycle_id == case.view.epoch_id
    assert graph.committed_topology_id == case.view.committed_mode
    assert graph.observer_role_id == case.local_topology.observer_role_id


def test_named_runtime_adapter_binds_only_immutable_local_context(ego_v2_factory):
    case = ego_v2_factory()
    adapter = RobotLocalEgoGraphRuntimeAdapter(case.config, case.local_topology)
    graph = adapter.build(case.view, KEEP, case.observation_step)
    direct = build_robot_local_ego_graph(
        case.view, case.config, case.local_topology, KEEP, case.observation_step
    )
    assert graph.fingerprint() == direct.fingerprint()


def test_runtime_local_metadata_has_no_complete_template_payload():
    assert set(RobotLocalTopologyMetadata.__dataclass_fields__) == {
        "topology_registry_schema_version", "observer_robot_id",
        "observer_role_id", "team_size", "candidates",
    }


def test_historical_global_graph_is_explicit_and_bitwise_compatible():
    cfg = Config()
    obs = SwarmFormationEnv(cfg).reset(4, "open_field", seed=123)
    direct = historical_build_graph(obs, cfg)
    isolated = build_legacy_global_graph(obs, cfg)
    assert LEGACY_GLOBAL_GRAPH_SCHEMA == "legacy-global-graph/68x11-unversioned"
    for expected, actual in zip(direct, isolated):
        assert torch.equal(expected, actual)


def test_policy_runtime_marks_global_checkpoint_adapter_explicitly():
    source = inspect.getsource(batch_from_obs)
    assert "build_legacy_global_graph" in source
    assert "Historical global-checkpoint adapter" in source
    assert "build_graph(" not in source


def test_phase4_v2_modules_do_not_implement_later_phase_algorithms():
    from rvt_swarm.decentralized import ego_graph_runtime_adapter, ego_graph_v2

    prohibited_modules = {
        "models", "training", "epoch", "local_controller", "safety",
        "environment", "metrics", "reconfiguration_metrics",
    }
    for module in (ego_graph_v2, ego_graph_runtime_adapter):
        tree = ast.parse(inspect.getsource(module))
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.rsplit(".", 1)[-1] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.rsplit(".", 1)[-1])
        assert imports.isdisjoint(prohibited_modules)
        assert not any(
            isinstance(node, ast.ClassDef) and any(
                token in node.name.lower()
                for token in ("head", "selector", "certificate", "projection")
            )
            for node in ast.walk(tree)
        )
