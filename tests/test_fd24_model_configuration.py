"""Immutable FD24 model configuration and derivation tests."""

from dataclasses import FrozenInstanceError, replace
import inspect

import pytest

from rvt_swarm.fd24.configuration import (
    FD24_MODEL_CONFIG_SCHEMA_VERSION,
    ROBOT_LOCAL_ACTION_COMPONENTS,
    FD24ModelConfig,
    FD24ModelConfigurationError,
    canonical_model_config_hash,
    canonical_model_config_source,
    fd24_model_config_from_source,
    residual_action_limits,
)
from rvt_swarm.runtime_configuration import RuntimeConfig


def test_default_configuration_is_frozen_and_versioned():
    config = FD24ModelConfig()
    assert config.schema_version == FD24_MODEL_CONFIG_SCHEMA_VERSION
    assert config.action_dimension == len(ROBOT_LOCAL_ACTION_COMPONENTS) == 2
    assert config.numerical_dtype == "float32"
    assert config.normalization == "layer_norm"
    assert config.dropout_probability == 0.0
    with pytest.raises(FrozenInstanceError):
        config.hidden_dimension = 1


def test_residual_limits_derive_from_immutable_physical_configuration():
    model_config = FD24ModelConfig(
        residual_limit_fractions_of_maximum_acceleration=(0.25, 0.5)
    )
    runtime = RuntimeConfig.for_team_size(6)
    maximum = runtime.physical.maximum_acceleration_meters_per_second_squared
    assert residual_action_limits(model_config, runtime) == (
        0.25 * maximum,
        0.5 * maximum,
    )


def test_config_hash_and_closed_source_round_trip_are_deterministic():
    config = FD24ModelConfig()
    source = canonical_model_config_source(config)
    restored = fd24_model_config_from_source(source)
    assert restored == config
    assert canonical_model_config_hash(restored) == canonical_model_config_hash(config)
    assert len(canonical_model_config_hash(config)) == 64
    source["unknown"] = 1
    with pytest.raises(FD24ModelConfigurationError):
        fd24_model_config_from_source(source)


@pytest.mark.parametrize(
    "change",
    (
        {"hidden_dimension": 0},
        {"message_passing_blocks": 0},
        {"candidate_embedding_dimension": 0},
        {"activation": "tuned"},
        {"normalization": "batch_norm"},
        {"dropout_probability": 1.0},
        {"attention_leaky_relu_slope": 0.0},
        {"residual_limit_fractions_of_maximum_acceleration": (0.2,)},
        {"residual_limit_fractions_of_maximum_acceleration": (0.0, 0.2)},
        {"numerical_dtype": "float64"},
    ),
)
def test_invalid_architecture_configuration_is_rejected(change):
    with pytest.raises(FD24ModelConfigurationError):
        FD24ModelConfig(**change)


def test_deployable_model_configuration_has_no_training_hyperparameters():
    fields = set(FD24ModelConfig.__dataclass_fields__)
    assert fields.isdisjoint({
        "learning_rate", "optimizer", "epochs", "batch_size", "weight_decay",
        "training_seed", "scenario", "layout", "label_source",
    })
    source = inspect.getsource(__import__(
        "rvt_swarm.fd24.configuration", fromlist=["configuration"]
    ))
    assert "TrainingConfig" not in source
