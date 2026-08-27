"""Clean-room source-episode identity.

The clean-room analogue of the historical DatasetCell / SourceEpisodeIdentity,
independent of the pilot DATASET_IDS allowlist. The atomic cell is

    role x family x team size x source policy x episode index

with the role's layout resolved separately and bound alongside.
"""
from __future__ import annotations

from dataclasses import dataclass

from rvt_swarm.cleanroom.composition import FAMILIES, SOURCE_POLICIES, TEAM_SIZES
from rvt_swarm.cleanroom.generation.budget import budget
from rvt_swarm.cleanroom.generation.roles import CLEAN_ROOM_STUDY, authorize, role


class IdentityError(ValueError):
    """A clean-room identity violation that must fail closed."""


@dataclass(frozen=True)
class CleanRoomCell:
    dataset_id: str
    study: str
    split: str
    family_id: str
    layout_sha256: str
    team_size: int

    def __post_init__(self) -> None:
        authorize(self.study, self.split, self.dataset_id)     # refuses pilot identities
        if self.family_id not in FAMILIES:
            raise IdentityError(f"unknown scenario family {self.family_id!r}")
        if self.team_size not in TEAM_SIZES:
            raise IdentityError(f"unauthorized team size {self.team_size!r}")
        if len(self.layout_sha256) != 64 or not all(
                c in "0123456789abcdef" for c in self.layout_sha256):
            raise IdentityError("layout_sha256 must be a lowercase sha256 hex digest")


@dataclass(frozen=True)
class CleanRoomSourceEpisodeIdentity:
    cell: CleanRoomCell
    source_class: str
    episode_index: int
    layout_id: str

    def __post_init__(self) -> None:
        if self.source_class not in SOURCE_POLICIES:
            raise IdentityError(f"unknown source policy {self.source_class!r}")
        role_name = next(r.role for r in __import__(
            "rvt_swarm.cleanroom.generation.roles", fromlist=["x"]).ROLES.values()
            if r.split == self.cell.split)
        limit = budget(role_name).episodes_per_cell
        if not 0 <= self.episode_index < limit:
            raise IdentityError(
                f"episode_index {self.episode_index} outside the frozen cell budget "
                f"[0, {limit}) for {role_name}")

    @property
    def role(self) -> str:
        from rvt_swarm.cleanroom.generation.roles import ROLES
        return next(r.role for r in ROLES.values() if r.split == self.cell.split)

    def source_episode_id(self) -> str:
        """The V4 identity schema, one-to-one with the frozen composition fields."""
        from rvt_swarm.cleanroom.composition import episode_id
        return episode_id(self.role, self.cell.family_id, self.cell.team_size,
                          self.source_class, self.episode_index)


def make_identity(role_name: str, family: str, team_size: int, source_policy: str,
                  episode_index: int, layout_id: str,
                  layout_sha256: str) -> CleanRoomSourceEpisodeIdentity:
    r = role(role_name)
    return CleanRoomSourceEpisodeIdentity(
        cell=CleanRoomCell(dataset_id=r.dataset_id, study=CLEAN_ROOM_STUDY, split=r.split,
                           family_id=family, layout_sha256=layout_sha256, team_size=team_size),
        source_class=source_policy, episode_index=episode_index, layout_id=layout_id)
