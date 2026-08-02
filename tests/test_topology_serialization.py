"""Versioned deterministic topology and role serialization."""

from __future__ import annotations

import dataclasses
import json

import pytest

from rvt_swarm.runtime_configuration import RuntimeConfig
from rvt_swarm.topology_registry import (
    COMPACT,
    TOPOLOGY_REGISTRY_SCHEMA_VERSION,
    TopologySerializationError,
    construct_topology,
    dump_topology_template,
    generate_persistent_roles,
    load_topology_template,
)


@pytest.mark.parametrize("n", (5, 6, 8, 12, 16, 24))
def test_template_serialization_round_trip_is_deterministic(n: int) -> None:
    config = RuntimeConfig.for_team_size(n)
    roles = generate_persistent_roles(tuple(f"robot-{i:02d}" for i in range(n)))
    template = construct_topology(COMPACT, config.formation, role_set=roles)
    payload = dump_topology_template(template, roles)
    assert payload == dump_topology_template(template, roles)
    loaded, loaded_roles = load_topology_template(payload)
    assert loaded == template
    assert loaded_roles == roles
    with pytest.raises(dataclasses.FrozenInstanceError):
        loaded.topology_id = 99  # type: ignore[misc]


def test_template_serialization_rejects_unknown_missing_and_schema_fields() -> None:
    config = RuntimeConfig.for_team_size(6)
    roles = generate_persistent_roles(6)
    payload = json.loads(dump_topology_template(
        construct_topology(COMPACT, config.formation, role_set=roles), roles
    ))
    unknown = dict(payload, surprise=True)
    with pytest.raises(TopologySerializationError, match="unknown fields"):
        load_topology_template(json.dumps(unknown))
    missing = dict(payload)
    missing.pop("source")
    with pytest.raises(TopologySerializationError, match="missing fields"):
        load_topology_template(json.dumps(missing))
    mismatch = dict(payload, registry_schema_version="future-schema")
    with pytest.raises(TopologySerializationError, match="schema mismatch"):
        load_topology_template(json.dumps(mismatch))
    assert payload["registry_schema_version"] == TOPOLOGY_REGISTRY_SCHEMA_VERSION


def test_tampered_derived_geometry_and_source_are_rejected() -> None:
    config = RuntimeConfig.for_team_size(6)
    roles = generate_persistent_roles(6)
    raw = json.loads(dump_topology_template(
        construct_topology(COMPACT, config.formation, role_set=roles), roles
    ))
    raw["derived"]["roles"][0]["offset"][0] += 0.1
    with pytest.raises(TopologySerializationError, match="tampered"):
        load_topology_template(json.dumps(raw))

    raw = json.loads(dump_topology_template(
        construct_topology(COMPACT, config.formation, role_set=roles), roles
    ))
    raw["source"]["nominal_spacing_meters"] = 1.1
    with pytest.raises(TopologySerializationError, match="source hash"):
        load_topology_template(json.dumps(raw))
