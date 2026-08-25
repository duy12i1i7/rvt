"""The episode-universe contract.

The pilot programme derived its bootstrap population from the episodes that
happened to produce events, which silently dropped six zero-yield episodes and
made one layout resample 24 draws where the frozen rule required 30. The fix is
structural: a manifest enumerates the universe up front, and the analysis refuses
to run until what it observes matches what the manifest declared.
"""
from __future__ import annotations

from typing import Iterable, Mapping, Sequence


class UniverseContractError(ValueError):
    """A dataset-universe violation that must fail closed."""


def assert_episode_universe(
    manifest_episode_ids: Iterable[str],
    manifest_episode_layout: Mapping[str, str],
    observed_event_episode_ids: Sequence[str],
    *,
    expected_count: int,
) -> Mapping[str, str]:
    """Return the resampling universe, or refuse.

    ``manifest_episode_ids`` is the declared universe -- every source episode of
    the role, including any that yielded no event. ``observed_event_episode_ids``
    is the per-event episode column actually loaded. A zero-yield episode is a
    legitimate member that contributes nothing, so the observed set is allowed to
    be a strict subset; anything observed but undeclared is a hard failure.
    """
    declared = list(manifest_episode_ids)
    universe = {str(e) for e in declared}
    if len(declared) != len(universe):
        duplicates = sorted({e for e in declared if declared.count(e) > 1})
        raise UniverseContractError(
            f"the manifest declares duplicate source episodes: {duplicates}")
    if len(universe) != int(expected_count):
        raise UniverseContractError(
            f"the manifest declares {len(universe)} source episodes but its own "
            f"expected count is {expected_count}")
    if not universe:
        raise UniverseContractError("the episode universe is empty")

    missing_stratum = sorted(universe - set(manifest_episode_layout))
    if missing_stratum:
        raise UniverseContractError(
            f"declared episodes carry no layout membership: {missing_stratum}")
    undeclared_stratum = sorted(set(manifest_episode_layout) - universe)
    if undeclared_stratum:
        raise UniverseContractError(
            f"layout membership names episodes outside the universe: {undeclared_stratum}")

    observed = {str(e) for e in observed_event_episode_ids}
    extra = sorted(observed - universe)
    if extra:
        raise UniverseContractError(
            f"events reference source episodes the manifest never declared: {extra}")
    return {e: str(manifest_episode_layout[e]) for e in sorted(universe)}


def zero_yield_episodes(universe: Mapping[str, str],
                        observed_event_episode_ids: Sequence[str]) -> Sequence[str]:
    """Episodes that are in the universe and produced no event. Reported, never dropped."""
    observed = {str(e) for e in observed_event_episode_ids}
    return tuple(sorted(set(universe) - observed))
