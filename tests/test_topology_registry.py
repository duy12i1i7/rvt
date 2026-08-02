"""Phase 3 authoritative topology-registry contract."""

from __future__ import annotations

import dataclasses
import inspect

import pytest

from rvt_swarm.topology_registry import (
    COMPACT,
    KEEP,
    LINE,
    PRIMARY_TOPOLOGY_IDS,
    TOPOLOGY_DEFINITION_SERIALIZATION_VERSION,
    TOPOLOGY_REGISTRY_SCHEMA_VERSION,
    TopologyRegistryError,
    get_topology_definition,
    iter_topology_definitions,
    topology_registry_fingerprint,
)


def test_registry_has_exactly_the_predeclared_primary_topologies() -> None:
    definitions = iter_topology_definitions()
    assert tuple(item.topology_id for item in definitions) == PRIMARY_TOPOLOGY_IDS
    assert tuple(item.canonical_name for item in definitions) == (
        "keep", "compact", "line",
    )
    assert PRIMARY_TOPOLOGY_IDS == (KEEP, COMPACT, LINE) == (0, 5, 2)


def test_existing_keep_line_ids_are_preserved_and_compact_does_not_collide() -> None:
    assert KEEP == 0
    assert LINE == 2
    assert COMPACT not in {0, 1, 2, 3, 4}


@pytest.mark.parametrize("topology", [KEEP, COMPACT, LINE, "keep", "compact", "line"])
def test_canonical_lookup_is_stable(topology) -> None:
    definition = get_topology_definition(topology)
    assert definition.serialization_version == TOPOLOGY_DEFINITION_SERIALIZATION_VERSION
    assert definition.topology_id in PRIMARY_TOPOLOGY_IDS


@pytest.mark.parametrize("alias", ["grid", "nominal", "two_column", "single_file"])
def test_aliases_require_explicit_compatibility_migration(alias: str) -> None:
    with pytest.raises(TopologyRegistryError, match="explicit migration"):
        get_topology_definition(alias)


def test_topology_definitions_are_immutable() -> None:
    definition = get_topology_definition(KEEP)
    with pytest.raises(dataclasses.FrozenInstanceError):
        definition.canonical_name = "changed"  # type: ignore[misc]


def test_registry_fingerprint_is_deterministic() -> None:
    assert topology_registry_fingerprint() == topology_registry_fingerprint()
    assert len(topology_registry_fingerprint()) == 64


def test_registry_iteration_order_is_explicit_not_mapping_order() -> None:
    source = inspect.getsource(iter_topology_definitions)
    assert "_DEFINITIONS" in source
    assert ".values()" not in source


def test_registry_contains_no_selection_or_runtime_protocol() -> None:
    import rvt_swarm.topology_registry as registry

    source = inspect.getsource(registry)
    forbidden = (
        "learned_topology_selection",
        "readiness_consensus",
        "safety_projection",
        "residual_action",
    )
    assert not any(token in source for token in forbidden)
    assert TOPOLOGY_REGISTRY_SCHEMA_VERSION == "rvt-topology-registry/v1"


def test_selected_controller_and_metric_have_no_private_template_generator() -> None:
    from rvt_swarm.decentralized import formation_metric_v3, local_controller, roles

    controller_source = inspect.getsource(local_controller)
    metric_source = inspect.getsource(formation_metric_v3)
    role_source = inspect.getsource(roles)
    assert "ceil(math.sqrt" not in controller_source
    assert "ceil(math.sqrt" not in metric_source
    assert "construct_topology_from_spacing" in role_source
