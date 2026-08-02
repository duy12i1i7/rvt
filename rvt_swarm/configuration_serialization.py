"""Deterministic serialization and verification for experiment manifests."""

from __future__ import annotations

import json
from dataclasses import asdict, fields
from typing import Any, Dict, Mapping, Type, TypeVar

from .configuration import EvaluationConfig, ExperimentConfiguration, TrainingConfig
from .runtime_configuration import (
    DERIVATION_VERSION,
    RUNTIME_CONFIGURATION_SCHEMA_VERSION,
    CommunicationConfig,
    ControllerConfig,
    FormationConfig,
    MissionConfig,
    ModelConfig,
    PhysicalPlatformConfig,
    ProtocolConfig,
    RuntimeConfig,
    SafetyConfig,
    SensingConfig,
    canonical_runtime_hash,
    canonical_runtime_source,
    derive_runtime_configuration,
)


EXPERIMENT_MANIFEST_SCHEMA_VERSION = "rvt-experiment-manifest/v1"

_RUNTIME_SECTIONS = {
    "physical": PhysicalPlatformConfig,
    "mission": MissionConfig,
    "formation": FormationConfig,
    "sensing": SensingConfig,
    "communication": CommunicationConfig,
    "protocol": ProtocolConfig,
    "controller": ControllerConfig,
    "safety": SafetyConfig,
    "model": ModelConfig,
}

_UNITS = {
    "physical": {
        "robot_radius_meters": "m",
        "maximum_speed_meters_per_second": "m/s",
        "maximum_acceleration_meters_per_second_squared": "m/s^2",
        "control_period_seconds": "s",
    },
    "mission": {
        "team_size": "count",
        "recovery_dwell_seconds": "s",
        "shared_frame_id": "identifier",
        "heading_alignment": "identifier",
    },
    "formation": {
        "nominal_spacing_meters": "m",
        "formation_tolerance_ratio": "dimensionless",
        "spacing_margin_meters": "m",
    },
    "sensing": {
        "obstacle_sensing_range_meters": "m",
        "peer_sensing_range_meters": "m",
        "lidar_number_of_rays": "count",
        "lidar_field_of_view_radians": "rad",
    },
    "communication": {
        "communication_range_meters": "m",
        "communication_period_seconds": "s",
        "maximum_message_age_seconds": "s",
        "maximum_message_delay_seconds": "s",
        "symmetric_links": "boolean",
        "packet_loss_probability": "probability",
        "asynchronous_offset_seconds": "s",
    },
    "protocol": {
        "maximum_team_size": "count",
        "declared_maximum_component_diameter_hops": "hops_or_null",
        "intent_rounds": "rounds_or_null",
        "score_rounds": "rounds_or_null",
        "readiness_rounds": "rounds_or_null",
        "confirmation_rounds": "rounds_or_null",
        "evidence_persistence_seconds": "s",
        "event_collection_seconds": "s",
        "commitment_seconds": "s",
        "rearm_inactive_seconds": "s",
        "decision_reference_seconds": "s",
        "minimum_confirmation_margin": "score",
        "duplicate_sequence_horizon": "packets",
        "peer_support_required_for_origination": "boolean",
        "temporary_disconnection_policy": "identifier",
    },
    "controller": {
        "goal_gain": "dimensionless",
        "formation_gain": "dimensionless",
        "damping_gain": "dimensionless",
        "robot_clearance_gain": "dimensionless",
        "robot_ttc_gain": "dimensionless",
        "obstacle_clearance_gain": "dimensionless",
        "obstacle_ttc_gain": "dimensionless",
        "velocity_consensus_gain": "dimensionless",
        "progress_window_seconds": "s",
        "transition_response_lateral_bound_meters": "m",
        "protocol_lateral_drift_bound_meters": "m",
    },
    "safety": {
        "obstacle_clearance_margin_meters": "m",
        "inter_robot_safety_margin_meters": "m",
        "transition_observation_margin_meters": "m",
    },
    "model": {
        "hidden_dimension": "count",
        "message_passing_steps": "count",
        "attention_leaky_relu_slope": "dimensionless",
        "input_schema_version": "identifier",
    },
}


class ManifestValidationError(ValueError):
    """Raised when a serialized manifest is unknown, incomplete, or tampered."""


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )


def build_experiment_manifest(
    configuration: ExperimentConfiguration,
    source_commit: str,
) -> Dict[str, Any]:
    if not isinstance(source_commit, str) or not source_commit.strip():
        raise ValueError("source_commit must be a nonempty immutable identifier")
    derived = asdict(derive_runtime_configuration(configuration.runtime))
    return {
        "schema_version": EXPERIMENT_MANIFEST_SCHEMA_VERSION,
        "runtime_schema_version": RUNTIME_CONFIGURATION_SCHEMA_VERSION,
        "derivation_version": DERIVATION_VERSION,
        "source_commit": source_commit,
        "canonical_runtime_sha256": canonical_runtime_hash(configuration.runtime),
        "configurable": {
            "runtime": canonical_runtime_source(configuration.runtime),
            "training": asdict(configuration.training),
            "evaluation": asdict(configuration.evaluation),
        },
        "derived": {"runtime": derived},
        "units": {"runtime": _UNITS},
    }


def dump_experiment_manifest(
    configuration: ExperimentConfiguration,
    source_commit: str,
) -> str:
    return _canonical_json(build_experiment_manifest(configuration, source_commit)) + "\n"


T = TypeVar("T")


def _strict_dataclass(cls: Type[T], raw: object, path: str) -> T:
    if not isinstance(raw, Mapping):
        raise ManifestValidationError(f"{path} must be an object")
    expected = {item.name for item in fields(cls)}
    actual = set(raw.keys())
    unknown = sorted(actual - expected)
    missing = sorted(expected - actual)
    if unknown:
        raise ManifestValidationError(f"{path} has unknown fields: {unknown}")
    if missing:
        raise ManifestValidationError(f"{path} is missing required fields: {missing}")
    values = dict(raw)
    for item in fields(cls):
        default_value = getattr(cls(), item.name)
        if isinstance(default_value, tuple) and isinstance(values[item.name], list):
            values[item.name] = tuple(values[item.name])
    try:
        return cls(**values)
    except (TypeError, ValueError) as exc:
        raise ManifestValidationError(f"invalid {path}: {exc}") from exc


def _load_runtime(raw: object) -> RuntimeConfig:
    if not isinstance(raw, Mapping):
        raise ManifestValidationError("configurable.runtime must be an object")
    expected = set(_RUNTIME_SECTIONS)
    actual = set(raw.keys())
    if actual - expected:
        raise ManifestValidationError(
            f"configurable.runtime has unknown sections: {sorted(actual - expected)}"
        )
    if expected - actual:
        raise ManifestValidationError(
            f"configurable.runtime is missing sections: {sorted(expected - actual)}"
        )
    sections = {
        name: _strict_dataclass(cls, raw[name], f"configurable.runtime.{name}")
        for name, cls in _RUNTIME_SECTIONS.items()
    }
    try:
        return RuntimeConfig(**sections)
    except (TypeError, ValueError) as exc:
        raise ManifestValidationError(f"invalid configurable.runtime: {exc}") from exc


def load_experiment_manifest(payload: str) -> ExperimentConfiguration:
    try:
        raw = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ManifestValidationError(f"invalid JSON: {exc}") from exc
    if not isinstance(raw, Mapping):
        raise ManifestValidationError("manifest root must be an object")
    expected_root = {
        "schema_version",
        "runtime_schema_version",
        "derivation_version",
        "source_commit",
        "canonical_runtime_sha256",
        "configurable",
        "derived",
        "units",
    }
    actual_root = set(raw.keys())
    if actual_root - expected_root:
        raise ManifestValidationError(
            f"manifest has unknown fields: {sorted(actual_root - expected_root)}"
        )
    if expected_root - actual_root:
        raise ManifestValidationError(
            f"manifest is missing required fields: {sorted(expected_root - actual_root)}"
        )
    if raw["schema_version"] != EXPERIMENT_MANIFEST_SCHEMA_VERSION:
        raise ManifestValidationError("unsupported experiment manifest schema")
    if raw["runtime_schema_version"] != RUNTIME_CONFIGURATION_SCHEMA_VERSION:
        raise ManifestValidationError("unsupported runtime configuration schema")
    if raw["derivation_version"] != DERIVATION_VERSION:
        raise ManifestValidationError("unsupported derivation version")
    if not isinstance(raw["source_commit"], str) or not raw["source_commit"]:
        raise ManifestValidationError("source_commit must be nonempty")

    configurable = raw["configurable"]
    if not isinstance(configurable, Mapping):
        raise ManifestValidationError("configurable must be an object")
    expected_sections = {"runtime", "training", "evaluation"}
    actual_sections = set(configurable.keys())
    if actual_sections != expected_sections:
        raise ManifestValidationError(
            "configurable sections must be exactly runtime, training, evaluation"
        )
    runtime = _load_runtime(configurable["runtime"])
    training = _strict_dataclass(
        TrainingConfig, configurable["training"], "configurable.training"
    )
    evaluation = _strict_dataclass(
        EvaluationConfig, configurable["evaluation"], "configurable.evaluation"
    )
    configuration = ExperimentConfiguration(runtime, training, evaluation)

    expected_hash = canonical_runtime_hash(runtime)
    if raw["canonical_runtime_sha256"] != expected_hash:
        raise ManifestValidationError("canonical runtime hash does not match source values")
    expected_derived = {"runtime": asdict(derive_runtime_configuration(runtime))}
    if _canonical_json(raw["derived"]) != _canonical_json(expected_derived):
        raise ManifestValidationError(
            "serialized derived values do not match recalculation from source values"
        )
    if _canonical_json(raw["units"]) != _canonical_json({"runtime": _UNITS}):
        raise ManifestValidationError("units table is missing, unknown, or altered")
    return configuration
