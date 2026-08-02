"""Phase 2 deterministic manifest serialization and tamper rejection."""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError

import pytest

from rvt_swarm.configuration import ExperimentConfiguration
from rvt_swarm.configuration_serialization import (
    DERIVATION_VERSION,
    EXPERIMENT_MANIFEST_SCHEMA_VERSION,
    ManifestValidationError,
    canonical_runtime_hash,
    dump_experiment_manifest,
    load_experiment_manifest,
)


SOURCE_COMMIT = "ed7c72771a25a3797a8c14f75119451e84adc0e5"


def manifest_text() -> str:
    return dump_experiment_manifest(ExperimentConfiguration(), SOURCE_COMMIT)


def test_round_trip_is_equal_immutable_and_deterministic() -> None:
    source = ExperimentConfiguration()
    first = dump_experiment_manifest(source, SOURCE_COMMIT)
    second = dump_experiment_manifest(source, SOURCE_COMMIT)
    assert first == second
    loaded = load_experiment_manifest(first)
    assert loaded == source
    with pytest.raises(FrozenInstanceError):
        loaded.runtime.mission.team_size = 8  # type: ignore[misc]


def test_manifest_has_separate_source_derived_runtime_and_evaluation_sections() -> None:
    raw = json.loads(manifest_text())
    assert raw["schema_version"] == EXPERIMENT_MANIFEST_SCHEMA_VERSION
    assert raw["derivation_version"] == DERIVATION_VERSION
    assert raw["source_commit"] == SOURCE_COMMIT
    assert set(raw["configurable"]) == {"runtime", "training", "evaluation"}
    assert set(raw["derived"]) == {"runtime"}
    assert "control_period_seconds" in raw["configurable"]["runtime"]["physical"]
    assert raw["units"]["runtime"]["physical"]["control_period_seconds"] == "s"


def test_canonical_hash_is_reproducible() -> None:
    left = ExperimentConfiguration().runtime
    right = ExperimentConfiguration().runtime
    assert canonical_runtime_hash(left) == canonical_runtime_hash(right)
    assert len(canonical_runtime_hash(left)) == 64


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema_version", "unknown/v9"),
        ("runtime_schema_version", "unknown/v9"),
        ("derivation_version", "unknown/v9"),
    ],
)
def test_schema_mismatch_is_rejected(field: str, value: str) -> None:
    raw = json.loads(manifest_text())
    raw[field] = value
    with pytest.raises(ManifestValidationError):
        load_experiment_manifest(json.dumps(raw))


def test_unknown_root_and_nested_fields_are_rejected() -> None:
    root = json.loads(manifest_text())
    root["unknown"] = 1
    with pytest.raises(ManifestValidationError, match="unknown"):
        load_experiment_manifest(json.dumps(root))

    nested = json.loads(manifest_text())
    nested["configurable"]["runtime"]["physical"]["mystery_meters"] = 1.0
    with pytest.raises(ManifestValidationError, match="unknown"):
        load_experiment_manifest(json.dumps(nested))


def test_missing_required_field_is_rejected_not_defaulted() -> None:
    raw = json.loads(manifest_text())
    del raw["configurable"]["runtime"]["communication"]["communication_period_seconds"]
    with pytest.raises(ManifestValidationError, match="missing"):
        load_experiment_manifest(json.dumps(raw))


def test_tampered_derived_value_is_rejected() -> None:
    raw = json.loads(manifest_text())
    raw["derived"]["runtime"]["commitment_steps"] += 1
    with pytest.raises(ManifestValidationError, match="derived"):
        load_experiment_manifest(json.dumps(raw))


def test_source_change_with_stale_hash_is_rejected() -> None:
    raw = json.loads(manifest_text())
    raw["configurable"]["runtime"]["physical"]["control_period_seconds"] = 0.075
    with pytest.raises(ManifestValidationError, match="hash"):
        load_experiment_manifest(json.dumps(raw))


def test_missing_source_commit_is_rejected() -> None:
    raw = json.loads(manifest_text())
    del raw["source_commit"]
    with pytest.raises(ManifestValidationError, match="missing"):
        load_experiment_manifest(json.dumps(raw))

