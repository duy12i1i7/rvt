"""Legacy IDs and checkpoint heads never receive silent new semantics."""

from __future__ import annotations

import pytest

from rvt_swarm.topology_registry import (
    COMPACT,
    KEEP,
    LINE,
    LegacyTopologyMigrationError,
    checkpoint_topology_vocabulary,
    migrate_legacy_topology,
)


@pytest.mark.parametrize(
    "value,vocabulary,expected",
    [
        (0, "decentralized-binary-v1", KEEP),
        (2, "decentralized-binary-v1", LINE),
        (0, "centralized-actions-v1", KEEP),
        (2, "centralized-actions-v1", LINE),
        (0, "binary-keep-line-head-v1", KEEP),
        (1, "binary-keep-line-head-v1", LINE),
        ("two_column", "legacy-name-aliases-v1", COMPACT),
    ],
)
def test_explicit_legacy_vocabulary_maps_supported_values(
    value, vocabulary: str, expected: int,
) -> None:
    result = migrate_legacy_topology(value, vocabulary)
    assert result.supported
    assert result.canonical_topology_id == expected


@pytest.mark.parametrize(
    "value,vocabulary,disposition",
    [
        (1, "decentralized-binary-v1", "retired-split"),
        (1, "centralized-actions-v1", "compress-action"),
        (3, "centralized-actions-v1", "retired-split"),
        (4, "centralized-actions-v1", "recover-action"),
        ("wedge", "centralized-actions-v1", "unknown"),
    ],
)
def test_non_topologies_and_retired_modes_do_not_silently_map(
    value, vocabulary: str, disposition: str,
) -> None:
    result = migrate_legacy_topology(value, vocabulary)
    assert not result.supported
    assert result.canonical_topology_id is None
    assert result.disposition == disposition


def test_numeric_one_has_different_declared_historical_meanings() -> None:
    retired = migrate_legacy_topology(1, "decentralized-binary-v1")
    compress = migrate_legacy_topology(1, "centralized-actions-v1")
    line_head = migrate_legacy_topology(1, "binary-keep-line-head-v1")
    assert retired.disposition == "retired-split"
    assert compress.disposition == "compress-action"
    assert line_head.canonical_topology_id == LINE


@pytest.mark.parametrize(
    "metadata,expected",
    [
        ({"method": "rvt_binary_recovery"}, "binary-keep-line-head-v1"),
        ({"method": "decentralized_direct_selector"}, "binary-keep-line-head-v1"),
        ({"model_name": "rvt_swarm"}, "legacy-structural-head-v1"),
        ({"topology_vocabulary_version": "centralized-actions-v1"}, "centralized-actions-v1"),
    ],
)
def test_checkpoint_vocabulary_requires_explicit_or_recognized_provenance(
    metadata, expected: str,
) -> None:
    assert checkpoint_topology_vocabulary(metadata) == expected


def test_tensor_width_alone_is_rejected_as_checkpoint_provenance() -> None:
    with pytest.raises(LegacyTopologyMigrationError, match="tensor width"):
        checkpoint_topology_vocabulary({"output_width": 2})


def test_unknown_vocabulary_fails_explicitly() -> None:
    with pytest.raises(LegacyTopologyMigrationError, match="unknown"):
        migrate_legacy_topology(0, "unversioned")
