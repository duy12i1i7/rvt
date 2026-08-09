"""Immutable architecture configuration for the robot-local FD24 model."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from typing import Mapping, Tuple

from ..runtime_configuration import RuntimeConfig


FD24_MODEL_CONFIG_SCHEMA_VERSION = "rvt-fd24-model-config/v1"

# The verified controller and environment exchange planar acceleration vectors.
# The model derives its output width from this named contract, never from N.
# RB16R owner decision: the primary residual output frame is WORLD. The
# historical mission-named declaration is preserved in
# results/rvt_fd24/model_residual_output_frame_v2.json, not here.
ROBOT_LOCAL_ACTION_COMPONENTS: Tuple[str, ...] = (
    "world_x_acceleration",
    "world_y_acceleration",
)


class FD24ModelConfigurationError(ValueError):
    """Model configuration is unknown, incomplete, or outside its contract."""


@dataclass(frozen=True)
class FD24ModelConfig:
    """Frozen architecture choices made before scientific training.

    Hidden dimensions and block count are ordinary model hyperparameters. The
    defaults reuse the approved local V1 compute scale; they were not selected
    from Phase 5 outcomes. Residual fractions are explicit per action component
    and are converted to SI limits from immutable physical configuration.
    """

    schema_version: str = FD24_MODEL_CONFIG_SCHEMA_VERSION
    hidden_dimension: int = 96
    message_passing_blocks: int = 3
    candidate_embedding_dimension: int = 16
    activation: str = "relu"
    normalization: str = "layer_norm"
    dropout_probability: float = 0.0
    attention_leaky_relu_slope: float = 0.2
    residual_limit_fractions_of_maximum_acceleration: Tuple[float, ...] = (
        0.25,
        0.25,
    )
    numerical_dtype: str = "float32"
    diagnostic_embedding_enabled: bool = False

    def __post_init__(self) -> None:
        if self.schema_version != FD24_MODEL_CONFIG_SCHEMA_VERSION:
            raise FD24ModelConfigurationError("unknown FD24 model-config schema")
        if isinstance(self.hidden_dimension, bool) or self.hidden_dimension <= 0:
            raise FD24ModelConfigurationError("hidden dimension must be positive")
        if (
            isinstance(self.message_passing_blocks, bool)
            or self.message_passing_blocks <= 0
        ):
            raise FD24ModelConfigurationError(
                "message-passing block count must be positive"
            )
        if (
            isinstance(self.candidate_embedding_dimension, bool)
            or self.candidate_embedding_dimension <= 0
        ):
            raise FD24ModelConfigurationError(
                "candidate embedding dimension must be positive"
            )
        if self.activation != "relu":
            raise FD24ModelConfigurationError(
                "model v1 supports only the predeclared relu activation"
            )
        if self.normalization != "layer_norm":
            raise FD24ModelConfigurationError(
                "model v1 requires per-node layer normalization"
            )
        dropout = float(self.dropout_probability)
        if not math.isfinite(dropout) or not 0.0 <= dropout < 1.0:
            raise FD24ModelConfigurationError(
                "dropout probability must be finite in [0, 1)"
            )
        slope = float(self.attention_leaky_relu_slope)
        if not math.isfinite(slope) or not 0.0 < slope <= 1.0:
            raise FD24ModelConfigurationError(
                "attention slope must be finite in (0, 1]"
            )
        fractions = self.residual_limit_fractions_of_maximum_acceleration
        if len(fractions) != len(ROBOT_LOCAL_ACTION_COMPONENTS):
            raise FD24ModelConfigurationError(
                "one residual fraction is required per action component"
            )
        if any(
            not math.isfinite(float(value)) or not 0.0 < float(value) <= 1.0
            for value in fractions
        ):
            raise FD24ModelConfigurationError(
                "residual fractions must be finite in (0, 1]"
            )
        if self.numerical_dtype != "float32":
            raise FD24ModelConfigurationError(
                "model v1 supports only deterministic float32 tensors"
            )
        if not isinstance(self.diagnostic_embedding_enabled, bool):
            raise FD24ModelConfigurationError(
                "diagnostic embedding flag must be Boolean"
            )

    @property
    def action_dimension(self) -> int:
        return len(ROBOT_LOCAL_ACTION_COMPONENTS)


def canonical_model_config_source(config: FD24ModelConfig) -> dict[str, object]:
    if not isinstance(config, FD24ModelConfig):
        raise TypeError("FD24 model config source requires FD24ModelConfig")
    return asdict(config)


def canonical_model_config_hash(config: FD24ModelConfig) -> str:
    payload = json.dumps(
        canonical_model_config_source(config),
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


def fd24_model_config_from_source(source: object) -> FD24ModelConfig:
    if not isinstance(source, Mapping):
        raise FD24ModelConfigurationError("model config source must be an object")
    expected = set(FD24ModelConfig.__dataclass_fields__)
    actual = set(source)
    if actual != expected:
        raise FD24ModelConfigurationError(
            "model config fields differ: "
            f"missing={sorted(expected - actual)}, unknown={sorted(actual - expected)}"
        )
    values = dict(source)
    fractions = values["residual_limit_fractions_of_maximum_acceleration"]
    if not isinstance(fractions, (list, tuple)):
        raise FD24ModelConfigurationError("residual fractions must be a sequence")
    values["residual_limit_fractions_of_maximum_acceleration"] = tuple(
        float(value) for value in fractions
    )
    try:
        return FD24ModelConfig(**values)
    except (TypeError, ValueError) as exc:
        raise FD24ModelConfigurationError(str(exc)) from exc


def residual_action_limits(
    model_config: FD24ModelConfig,
    runtime_config: RuntimeConfig,
) -> Tuple[float, ...]:
    """Derive SI acceleration limits from immutable physical configuration."""
    if not isinstance(model_config, FD24ModelConfig):
        raise TypeError("residual limits require FD24ModelConfig")
    if not isinstance(runtime_config, RuntimeConfig):
        raise TypeError("residual limits require RuntimeConfig")
    maximum = runtime_config.physical.maximum_acceleration_meters_per_second_squared
    return tuple(
        float(fraction) * maximum
        for fraction in model_config.residual_limit_fractions_of_maximum_acceleration
    )
