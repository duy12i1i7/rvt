"""Strict FD24 checkpoint metadata, content hashing, and rejection matrix."""

from pathlib import Path

import pytest
import torch

from rvt_swarm.fd24.checkpoint import (
    FD24_CHECKPOINT_SCHEMA_VERSION,
    FD24CheckpointError,
    build_fd24_checkpoint,
    canonical_state_dict_hash,
    load_fd24_checkpoint,
    save_fd24_checkpoint,
)
from rvt_swarm.fd24.configuration import FD24ModelConfig
from rvt_swarm.fd24.model import prepare_fd24_model_batch
from rvt_swarm.runtime_configuration import RuntimeConfig


SOURCE_COMMIT = "6f23ca180d964bf55750ba2e7397de13b3e4de3c"


def _checkpoint(tmp_path, fd24_graph_factory, fd24_model_factory):
    case, graph = fd24_graph_factory()
    model = fd24_model_factory(case.config)
    path = tmp_path / "fd24.pt"
    save_fd24_checkpoint(path, model, case.config, SOURCE_COMMIT)
    return case, graph, model, path


def _rewrite(path, mutate):
    payload = torch.load(path, map_location="cpu", weights_only=True)
    mutate(payload)
    torch.save(payload, path)


def test_checkpoint_round_trip_preserves_model_output_and_required_metadata(
    tmp_path, fd24_graph_factory, fd24_model_factory
):
    case, graph, model, path = _checkpoint(
        tmp_path, fd24_graph_factory, fd24_model_factory
    )
    loaded = load_fd24_checkpoint(
        path, case.config, expected_model_config=model.model_config
    )
    model.eval()
    loaded.model.eval()
    local_batch = prepare_fd24_model_batch((graph,))
    expected = model(local_batch)
    actual = loaded.model(local_batch)
    torch.testing.assert_close(expected.recoverability_logit, actual.recoverability_logit)
    torch.testing.assert_close(expected.residual_action, actual.residual_action)
    metadata = loaded.metadata
    assert metadata["checkpoint_schema_version"] == FD24_CHECKPOINT_SCHEMA_VERSION
    assert metadata["source_commit"] == SOURCE_COMMIT
    assert metadata["training_status"] == "untrained"
    assert metadata["deployment_classification"] == "shadow-disabled"
    assert "state_dict" not in metadata


def test_state_dict_hash_is_deterministic(fd24_graph_factory, fd24_model_factory):
    case, _ = fd24_graph_factory()
    model = fd24_model_factory(case.config)
    state_a = model.state_dict()
    state_b = {name: state_a[name].clone() for name in reversed(tuple(state_a))}
    assert canonical_state_dict_hash(state_a) == canonical_state_dict_hash(state_b)
    assert len(canonical_state_dict_hash(state_a)) == 64


@pytest.mark.parametrize(
    "field,value",
    (
        ("checkpoint_schema_version", "unknown"),
        ("model_schema_version", "legacy-global-model"),
        ("ego_graph_schema_version", "legacy-global-graph/68x11-unversioned"),
        ("ego_feature_schema_sha256", "0" * 64),
        ("topology_registry_schema_version", "unknown"),
        ("topology_vocabulary", [
            {"topology_id": 0, "canonical_name": "KEEP"},
            {"topology_id": 2, "canonical_name": "LINE"},
            {"topology_id": 3, "canonical_name": "split_hint"},
        ]),
        ("action_dimension", 12),
        ("model_information_scope", "whole-swarm-global"),
        ("deployment_classification", "legacy-global-runtime"),
        ("residual_action_limits_meters_per_second_squared", [9.0, 9.0]),
        ("source_commit", "unknown"),
    ),
)
def test_incompatible_checkpoint_metadata_is_rejected(
    tmp_path, fd24_graph_factory, fd24_model_factory, field, value
):
    case, _, _, path = _checkpoint(
        tmp_path, fd24_graph_factory, fd24_model_factory
    )
    _rewrite(path, lambda payload: payload.__setitem__(field, value))
    with pytest.raises(FD24CheckpointError):
        load_fd24_checkpoint(path, case.config)


def test_missing_or_unknown_checkpoint_field_is_rejected(
    tmp_path, fd24_graph_factory, fd24_model_factory
):
    case, _, _, path = _checkpoint(
        tmp_path, fd24_graph_factory, fd24_model_factory
    )
    _rewrite(path, lambda payload: payload.pop("topology_vocabulary"))
    with pytest.raises(FD24CheckpointError, match="fields differ"):
        load_fd24_checkpoint(path, case.config)
    _, _, _, path = _checkpoint(tmp_path, fd24_graph_factory, fd24_model_factory)
    _rewrite(path, lambda payload: payload.__setitem__("legacy_output_width", 3))
    with pytest.raises(FD24CheckpointError, match="fields differ"):
        load_fd24_checkpoint(path, case.config)


def test_tampered_state_dict_is_rejected_before_loading(
    tmp_path, fd24_graph_factory, fd24_model_factory
):
    case, _, _, path = _checkpoint(
        tmp_path, fd24_graph_factory, fd24_model_factory
    )
    def tamper(payload):
        first = next(iter(payload["state_dict"]))
        payload["state_dict"][first].view(-1)[0] += 1.0
    _rewrite(path, tamper)
    with pytest.raises(FD24CheckpointError, match="state-dict hash"):
        load_fd24_checkpoint(path, case.config)


def test_model_config_hash_and_expected_config_are_enforced(
    tmp_path, fd24_graph_factory, fd24_model_factory
):
    case, _, _, path = _checkpoint(
        tmp_path, fd24_graph_factory, fd24_model_factory
    )
    _rewrite(path, lambda payload: payload.__setitem__("model_config_sha256", "0" * 64))
    with pytest.raises(FD24CheckpointError, match="model-config hash"):
        load_fd24_checkpoint(path, case.config)
    _, _, _, path = _checkpoint(tmp_path, fd24_graph_factory, fd24_model_factory)
    with pytest.raises(FD24CheckpointError, match="configuration is unexpected"):
        load_fd24_checkpoint(
            path,
            case.config,
            expected_model_config=FD24ModelConfig(hidden_dimension=48),
        )


def test_runtime_configuration_hash_is_enforced(
    tmp_path, fd24_graph_factory, fd24_model_factory
):
    _, _, _, path = _checkpoint(tmp_path, fd24_graph_factory, fd24_model_factory)
    with pytest.raises(FD24CheckpointError, match="runtime_config_sha256"):
        load_fd24_checkpoint(path, RuntimeConfig.for_team_size(8))


def test_historical_global_checkpoint_cannot_load_as_fd24(tmp_path):
    legacy = {
        "model": {"backbone.enc.0.weight": torch.zeros((128, 68))},
        "model_name": "rvt_swarm",
        "output_width": 3,
    }
    path = tmp_path / "legacy.pt"
    torch.save(legacy, path)
    with pytest.raises(FD24CheckpointError):
        load_fd24_checkpoint(path, RuntimeConfig.for_team_size(6))


def test_checkpoint_builder_rejects_ambiguous_status_and_source(
    fd24_graph_factory, fd24_model_factory
):
    case, _ = fd24_graph_factory()
    model = fd24_model_factory(case.config)
    with pytest.raises(FD24CheckpointError):
        build_fd24_checkpoint(
            model, case.config, SOURCE_COMMIT, training_status="probably-trained"
        )
    with pytest.raises(FD24CheckpointError):
        build_fd24_checkpoint(model, case.config, "unknown")
