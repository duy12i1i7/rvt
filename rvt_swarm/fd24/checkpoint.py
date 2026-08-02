"""Versioned, strict checkpoint contract for the robot-local FD24 model."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional

import torch

from ..decentralized.ego_graph_v2 import (
    EGO_GRAPH_FEATURE_SCHEMA_SHA256,
    EGO_GRAPH_SCHEMA_VERSION,
)
from ..runtime_configuration import (
    RuntimeConfig,
    canonical_runtime_hash,
)
from ..topology_registry import TOPOLOGY_REGISTRY_SCHEMA_VERSION
from .configuration import (
    FD24ModelConfig,
    canonical_model_config_hash,
    canonical_model_config_source,
    fd24_model_config_from_source,
    residual_action_limits,
)
from .model import (
    FD24_MODEL_SCHEMA_VERSION,
    FD24_TOPOLOGY_VOCABULARY,
    RVTFD24LocalModel,
)


FD24_CHECKPOINT_SCHEMA_VERSION = "rvt-fd24-checkpoint/v1"
FD24_MODEL_INFORMATION_SCOPE = "robot-local-ego-v2"
FD24_TRAINING_STATUSES = frozenset({
    "untrained",
    "synthetic-mechanical",
    "scientifically-trained",
})
FD24_DEPLOYMENT_CLASSIFICATIONS = frozenset({
    "shadow-disabled",
    "diagnostic-only",
    "deployable-candidate",
})


class FD24CheckpointError(ValueError):
    """FD24 checkpoint metadata or tensor content is incompatible."""


@dataclass(frozen=True)
class LoadedFD24Checkpoint:
    model: RVTFD24LocalModel
    model_config: FD24ModelConfig
    metadata: Mapping[str, object]


def canonical_state_dict_hash(value: object) -> str:
    """Hash names, dtype, shape, and canonical CPU bytes for every tensor."""
    if not isinstance(value, Mapping):
        raise FD24CheckpointError("state dict must be an object")
    digest = hashlib.sha256()
    for name in sorted(value):
        tensor = value[name]
        if not isinstance(name, str) or not isinstance(tensor, torch.Tensor):
            raise FD24CheckpointError("state dict must map names to tensors")
        cpu = tensor.detach().cpu().contiguous()
        descriptor = json.dumps(
            {
                "name": name,
                "dtype": str(cpu.dtype),
                "shape": list(cpu.shape),
            },
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
        digest.update(len(descriptor).to_bytes(8, "big"))
        digest.update(descriptor)
        raw = cpu.numpy().tobytes(order="C")
        digest.update(len(raw).to_bytes(8, "big"))
        digest.update(raw)
    return digest.hexdigest()


def _topology_vocabulary_source() -> list[dict[str, object]]:
    return [
        {"topology_id": topology_id, "canonical_name": name}
        for topology_id, name in FD24_TOPOLOGY_VOCABULARY
    ]


def build_fd24_checkpoint(
    model: RVTFD24LocalModel,
    runtime_config: RuntimeConfig,
    source_commit: str,
    *,
    training_status: str = "untrained",
    deployment_classification: str = "shadow-disabled",
) -> dict[str, object]:
    if not isinstance(model, RVTFD24LocalModel):
        raise TypeError("FD24 checkpoint requires RVTFD24LocalModel")
    if not isinstance(runtime_config, RuntimeConfig):
        raise TypeError("FD24 checkpoint requires RuntimeConfig")
    if training_status not in FD24_TRAINING_STATUSES:
        raise FD24CheckpointError("unknown training status")
    if deployment_classification not in FD24_DEPLOYMENT_CLASSIFICATIONS:
        raise FD24CheckpointError("unknown deployment classification")
    if (
        not isinstance(source_commit, str)
        or len(source_commit) != 40
        or any(character not in "0123456789abcdef" for character in source_commit)
    ):
        raise FD24CheckpointError("source commit must be a 40-character SHA-1")
    model_config = model.model_config
    state = {
        name: tensor.detach().cpu().clone()
        for name, tensor in model.state_dict().items()
    }
    return {
        "checkpoint_schema_version": FD24_CHECKPOINT_SCHEMA_VERSION,
        "model_schema_version": FD24_MODEL_SCHEMA_VERSION,
        "ego_graph_schema_version": EGO_GRAPH_SCHEMA_VERSION,
        "ego_feature_schema_sha256": EGO_GRAPH_FEATURE_SCHEMA_SHA256,
        "topology_registry_schema_version": TOPOLOGY_REGISTRY_SCHEMA_VERSION,
        "topology_vocabulary": _topology_vocabulary_source(),
        "model_config": canonical_model_config_source(model_config),
        "model_config_sha256": canonical_model_config_hash(model_config),
        "runtime_config_sha256": canonical_runtime_hash(runtime_config),
        "action_dimension": model.action_dimension,
        "residual_action_limits_meters_per_second_squared": list(
            residual_action_limits(model_config, runtime_config)
        ),
        "source_commit": source_commit,
        "state_dict_sha256": canonical_state_dict_hash(state),
        "training_status": training_status,
        "deployment_classification": deployment_classification,
        "model_information_scope": FD24_MODEL_INFORMATION_SCOPE,
        "state_dict": state,
    }


def save_fd24_checkpoint(
    path: Path | str,
    model: RVTFD24LocalModel,
    runtime_config: RuntimeConfig,
    source_commit: str,
    *,
    training_status: str = "untrained",
    deployment_classification: str = "shadow-disabled",
) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = build_fd24_checkpoint(
        model,
        runtime_config,
        source_commit,
        training_status=training_status,
        deployment_classification=deployment_classification,
    )
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    torch.save(payload, temporary)
    temporary.replace(destination)


def _closed_checkpoint(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise FD24CheckpointError("checkpoint root must be an object")
    expected = {
        "checkpoint_schema_version",
        "model_schema_version",
        "ego_graph_schema_version",
        "ego_feature_schema_sha256",
        "topology_registry_schema_version",
        "topology_vocabulary",
        "model_config",
        "model_config_sha256",
        "runtime_config_sha256",
        "action_dimension",
        "residual_action_limits_meters_per_second_squared",
        "source_commit",
        "state_dict_sha256",
        "training_status",
        "deployment_classification",
        "model_information_scope",
        "state_dict",
    }
    actual = set(value)
    if actual != expected:
        raise FD24CheckpointError(
            "checkpoint fields differ: "
            f"missing={sorted(expected - actual)}, unknown={sorted(actual - expected)}"
        )
    return value


def load_fd24_checkpoint(
    path: Path | str,
    runtime_config: RuntimeConfig,
    *,
    expected_model_config: Optional[FD24ModelConfig] = None,
    map_location: str | torch.device = "cpu",
) -> LoadedFD24Checkpoint:
    if not isinstance(runtime_config, RuntimeConfig):
        raise TypeError("FD24 checkpoint loading requires RuntimeConfig")
    try:
        raw = torch.load(path, map_location=map_location, weights_only=True)
    except Exception as exc:
        raise FD24CheckpointError(f"checkpoint could not be read: {exc}") from exc
    payload = _closed_checkpoint(raw)
    exact = {
        "checkpoint_schema_version": FD24_CHECKPOINT_SCHEMA_VERSION,
        "model_schema_version": FD24_MODEL_SCHEMA_VERSION,
        "ego_graph_schema_version": EGO_GRAPH_SCHEMA_VERSION,
        "ego_feature_schema_sha256": EGO_GRAPH_FEATURE_SCHEMA_SHA256,
        "topology_registry_schema_version": TOPOLOGY_REGISTRY_SCHEMA_VERSION,
        "topology_vocabulary": _topology_vocabulary_source(),
        "runtime_config_sha256": canonical_runtime_hash(runtime_config),
        "model_information_scope": FD24_MODEL_INFORMATION_SCOPE,
    }
    for field, expected in exact.items():
        if payload[field] != expected:
            raise FD24CheckpointError(f"checkpoint {field} is incompatible")
    if payload["training_status"] not in FD24_TRAINING_STATUSES:
        raise FD24CheckpointError("checkpoint training status is unknown")
    if payload["deployment_classification"] not in FD24_DEPLOYMENT_CLASSIFICATIONS:
        raise FD24CheckpointError("checkpoint deployment classification is unknown")
    source_commit = payload["source_commit"]
    if (
        not isinstance(source_commit, str)
        or len(source_commit) != 40
        or any(character not in "0123456789abcdef" for character in source_commit)
    ):
        raise FD24CheckpointError("checkpoint source commit is invalid")
    model_config = fd24_model_config_from_source(payload["model_config"])
    if payload["model_config_sha256"] != canonical_model_config_hash(model_config):
        raise FD24CheckpointError("model-config hash mismatch")
    if (
        expected_model_config is not None
        and model_config != expected_model_config
    ):
        raise FD24CheckpointError("checkpoint model configuration is unexpected")
    if payload["action_dimension"] != model_config.action_dimension:
        raise FD24CheckpointError("checkpoint action dimension is incompatible")
    limits = payload["residual_action_limits_meters_per_second_squared"]
    if not isinstance(limits, (list, tuple)):
        raise FD24CheckpointError("checkpoint residual bounds are invalid")
    expected_limits = residual_action_limits(model_config, runtime_config)
    if len(limits) != len(expected_limits) or any(
        not math.isclose(float(actual), expected, rel_tol=0.0, abs_tol=0.0)
        for actual, expected in zip(limits, expected_limits)
    ):
        raise FD24CheckpointError("checkpoint residual bounds are incompatible")
    state = payload["state_dict"]
    if payload["state_dict_sha256"] != canonical_state_dict_hash(state):
        raise FD24CheckpointError("checkpoint state-dict hash mismatch")
    model = RVTFD24LocalModel(model_config, runtime_config)
    try:
        model.load_state_dict(state, strict=True)
    except (RuntimeError, TypeError, ValueError) as exc:
        raise FD24CheckpointError(f"state dict is incompatible: {exc}") from exc
    metadata = {
        key: value
        for key, value in payload.items()
        if key != "state_dict"
    }
    return LoadedFD24Checkpoint(model, model_config, metadata)
