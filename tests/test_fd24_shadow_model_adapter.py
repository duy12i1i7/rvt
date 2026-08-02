"""Disabled-by-default shadow inference cannot affect current runtime."""

import inspect

import pytest
import torch

from rvt_swarm.decentralized import runtime
from rvt_swarm.decentralized.fd24_shadow_adapter import (
    FD24ShadowInferenceAdapter,
    FD24ShadowInferenceConfig,
)
from rvt_swarm.decentralized.ego_graph_v2 import build_robot_local_ego_graph
from rvt_swarm.fd24.configuration import FD24ModelConfig
from rvt_swarm.fd24.model import FD24ModelContractError
from rvt_swarm.topology_registry import COMPACT, KEEP, LINE


def test_shadow_inference_is_disabled_by_default():
    config = FD24ShadowInferenceConfig()
    result = FD24ShadowInferenceAdapter(config).evaluate(())
    assert config.model_shadow_inference_enabled is False
    assert result.enabled is False
    assert result.model_output is None
    assert result.graph_count == 0


def test_enabled_shadow_adapter_preserves_candidate_association(
    ego_v2_factory, fd24_model_factory
):
    case = ego_v2_factory()
    graphs = tuple(build_robot_local_ego_graph(
        case.view, case.config, case.local_topology, candidate,
        case.observation_step,
    ) for candidate in (KEEP, COMPACT, LINE))
    model = fd24_model_factory(case.config)
    adapter = FD24ShadowInferenceAdapter(
        FD24ShadowInferenceConfig(model_shadow_inference_enabled=True),
        model,
    )
    result = adapter.evaluate(tuple(reversed(graphs)))
    assert result.enabled is True
    assert result.graph_count == result.candidate_count == 3
    assert result.all_valid is True
    assert set(result.model_output.candidate_topology_id.tolist()) == {
        KEEP, COMPACT, LINE
    }
    assert result.output_shapes == (
        ("recoverability_logit", (3,)),
        ("residual_action", (3, 2)),
        ("candidate_topology_id", (3,)),
    )


def test_shadow_adapter_restores_model_training_state(
    fd24_graph_factory, fd24_model_factory
):
    case, graph = fd24_graph_factory()
    model = fd24_model_factory(case.config)
    model.train(True)
    adapter = FD24ShadowInferenceAdapter(
        FD24ShadowInferenceConfig(model_shadow_inference_enabled=True), model
    )
    adapter.evaluate((graph,))
    assert model.training is True


def test_diagnostic_embedding_requires_explicit_model_and_adapter_flags(
    fd24_graph_factory, fd24_model_factory
):
    case, graph = fd24_graph_factory()
    enabled_model = fd24_model_factory(
        case.config,
        model_config=FD24ModelConfig(diagnostic_embedding_enabled=True),
    )
    enabled = FD24ShadowInferenceAdapter(
        FD24ShadowInferenceConfig(True, True), enabled_model
    ).evaluate((graph,))
    assert enabled.model_output.encoder_embedding_optional is not None

    disabled_model = fd24_model_factory(case.config)
    with pytest.raises(FD24ModelContractError, match="diagnostic embedding"):
        FD24ShadowInferenceAdapter(
            FD24ShadowInferenceConfig(True, True), disabled_model
        ).evaluate((graph,))


def test_current_robot_decision_has_no_shadow_or_fd24_import():
    source = inspect.getsource(runtime)
    decision_source = inspect.getsource(runtime._robot_decision)
    assert "fd24_shadow" not in source
    assert "RVTFD24LocalModel" not in source
    assert "build_robot_local_ego_graph" not in decision_source
    assert "build_ego_graph(view, cfg" in decision_source


def test_shadow_output_cannot_change_scripted_current_decision(
    fd24_graph_factory, fd24_model_factory
):
    case, graph = fd24_graph_factory()
    model = fd24_model_factory(case.config)
    before = runtime._robot_decision(case.view, case.config, None, "always_keep")
    shadow = FD24ShadowInferenceAdapter(
        FD24ShadowInferenceConfig(model_shadow_inference_enabled=True), model
    ).evaluate((graph,))
    after = runtime._robot_decision(case.view, case.config, None, "always_keep")
    assert shadow.model_output is not None
    assert before == after == (1.0, 0.0)


def test_fd24_modules_contain_no_later_phase_or_scientific_runtime_imports():
    from rvt_swarm.fd24 import checkpoint, configuration, model
    from rvt_swarm.decentralized import fd24_shadow_adapter

    prohibited_imports = (
        "rvt_swarm.training", "rvt_swarm.train", "rvt_swarm.layouts",
        "rvt_swarm.environment", "rvt_swarm.controllers", "rvt_swarm.safety",
        "reconfiguration_metrics", "readiness", "dagger", "final_test",
    )
    source = "\n".join(inspect.getsource(module) for module in (
        checkpoint, configuration, model, fd24_shadow_adapter
    )).lower()
    assert all(token not in source for token in prohibited_imports)
