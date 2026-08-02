"""Persistent role identity is separate from topology-specific geometry."""

from __future__ import annotations

import dataclasses

import pytest

from rvt_swarm.runtime_configuration import RuntimeConfig
from rvt_swarm.topology_registry import (
    COMPACT,
    KEEP,
    LINE,
    TopologyRegistryError,
    construct_primary_templates,
    dump_persistent_roles,
    generate_persistent_roles,
    load_persistent_roles,
)

TEAM_SIZES = (5, 6, 8, 12, 16, 24)


@pytest.mark.parametrize("n", TEAM_SIZES)
def test_role_ids_are_unique_and_have_no_leader(n: int) -> None:
    roles = generate_persistent_roles(n)
    ids = tuple(role.role_id for role in roles.roles)
    assert len(ids) == len(set(ids)) == n
    assert not any("leader" in role_id.lower() for role_id in ids)


@pytest.mark.parametrize("n", TEAM_SIZES)
def test_roles_are_stable_across_keep_compact_line(n: int) -> None:
    config = RuntimeConfig.for_team_size(n)
    roles = generate_persistent_roles(n)
    templates = construct_primary_templates(config.formation, role_set=roles)
    assert tuple(template.topology_id for template in templates) == (KEEP, COMPACT, LINE)
    assert all(template.role_ids == templates[0].role_ids for template in templates)


def test_construction_depends_on_robot_identity_not_input_array_order() -> None:
    robot_keys = ("robot-c", "robot-a", "robot-e", "robot-b", "robot-d")
    first = generate_persistent_roles(robot_keys)
    second = generate_persistent_roles(tuple(reversed(robot_keys)))
    assert first == second
    for key in robot_keys:
        assert first.role_for_robot(key) == second.role_for_robot(key)


def test_numeric_robot_keys_have_stable_numeric_order() -> None:
    roles = generate_persistent_roles((10, 2, 1, 0, 5))
    assert tuple(role.robot_key for role in roles.roles) == tuple(
        f"int:{value:020d}" for value in (0, 1, 2, 5, 10)
    )


def test_role_serialization_round_trip_is_immutable_and_deterministic() -> None:
    roles = generate_persistent_roles(("charlie", "alpha", "bravo", "delta", "echo"))
    payload = dump_persistent_roles(roles)
    assert payload == dump_persistent_roles(roles)
    loaded = load_persistent_roles(payload)
    assert loaded == roles
    with pytest.raises(dataclasses.FrozenInstanceError):
        loaded.roles = tuple()  # type: ignore[misc]


@pytest.mark.parametrize(
    "keys",
    [(), ("duplicate", "duplicate"), (-1, 0, 1), (True, "robot")],
)
def test_invalid_role_sources_are_rejected(keys) -> None:
    with pytest.raises(TopologyRegistryError):
        generate_persistent_roles(keys)


def test_invalid_role_lookup_is_rejected() -> None:
    roles = generate_persistent_roles(5)
    with pytest.raises(TopologyRegistryError, match="unknown persistent role"):
        roles.role("role-does-not-exist")
    with pytest.raises(TopologyRegistryError, match="unknown robot key"):
        roles.role_for_robot(99)
