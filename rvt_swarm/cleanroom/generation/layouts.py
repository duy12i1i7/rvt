"""Clean-room layout-role registry.

The historical V3 layout registry is untouched and remains the authority for
pilot membership. This is a SEPARATE registry recording clean-room role
membership. Geometry itself is never recomputed here: every layout is produced
by the frozen scientific core (phase8.scenario) and its hash by the frozen
ScenarioLayout.geometry_sha256().
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Tuple

from rvt_swarm.cleanroom.composition import FAMILIES
from rvt_swarm.cleanroom.generation.roles import ROLES, role
from rvt_swarm.phase8 import scenario as _scenario


class LayoutAuthorityError(ValueError):
    """A clean-room layout-authority violation that must fail closed."""


# Layout ids consumed by the pilot's official V3 datasets, refused here.
HISTORICAL_V3_LAYOUT_OFFSETS = (0.22, 0.54, 0.65)
HISTORICAL_RESERVE_OFFSETS = (0.33,)
FORBIDDEN_OFFSETS = (0.76, 0.77, 0.87)


@dataclass(frozen=True)
class CleanRoomLayout:
    role: str
    family_id: str
    layout_id: str
    layout_sha256: str
    generator_split_namespace: str
    variant_index: int
    offset: float
    generation_seed_commitment: str


def resolve_layout(role_name: str, family_id: str) -> CleanRoomLayout:
    """Resolve one role/family layout by calling the frozen scientific core."""
    r = role(role_name)
    if family_id not in FAMILIES:
        raise LayoutAuthorityError(f"unknown scenario family {family_id!r}")
    layout = _scenario._layout(family_id, r.generator_split_namespace, r.layout_variant_index)
    offset = round(_scenario._SPLIT_OFFSETS[r.generator_split_namespace]
                   + 0.11 * r.layout_variant_index, 10)
    if abs(offset - r.offset) > 1e-9:
        raise LayoutAuthorityError(
            f"{role_name}/{family_id}: resolved offset {offset} disagrees with the frozen "
            f"role offset {r.offset}")
    if offset in HISTORICAL_V3_LAYOUT_OFFSETS:
        raise LayoutAuthorityError(f"offset {offset} is consumed by the historical V3 registry")
    if offset in HISTORICAL_RESERVE_OFFSETS:
        raise LayoutAuthorityError(f"offset {offset} is the untouched historical reserve")
    if offset in FORBIDDEN_OFFSETS:
        raise LayoutAuthorityError(f"offset {offset} lies in the forbidden band")
    return CleanRoomLayout(
        role=role_name, family_id=family_id, layout_id=layout.layout_id,
        layout_sha256=layout.geometry_sha256(),
        generator_split_namespace=r.generator_split_namespace,
        variant_index=r.layout_variant_index, offset=offset,
        generation_seed_commitment=layout.generation_seed_commitment)


def role_layouts(role_name: str) -> Tuple[CleanRoomLayout, ...]:
    """Exactly one layout instance per family, in canonical family order."""
    out = tuple(resolve_layout(role_name, f) for f in FAMILIES)
    if len({item.layout_sha256 for item in out}) != len(FAMILIES):
        raise LayoutAuthorityError(f"{role_name}: layout hashes are not distinct per family")
    return out


def all_role_layouts() -> Mapping[str, Tuple[CleanRoomLayout, ...]]:
    return {name: role_layouts(name) for name in ROLES}


def assert_layouts_disjoint_across_roles() -> None:
    seen: dict[str, str] = {}
    for name, items in all_role_layouts().items():
        for item in items:
            if item.layout_sha256 in seen:
                raise LayoutAuthorityError(
                    f"layout hash shared by {seen[item.layout_sha256]} and {name}")
            seen[item.layout_sha256] = name
