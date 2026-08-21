"""TRAIN-internal fold membership, resolved from the frozen fold manifest.

Fold membership is a set of LAYOUT HASHES, never layout names. Ten of the twenty
official TRAIN layouts are named ``validation-fX-01``; a name-based split would
put them in the wrong place, and worse, would look plausible while doing it.

Because a fold is a set of layouts and every episode belongs to exactly one
layout, layout grouping makes episode, event, candidate-pair, robot-row and
replica crossing structurally impossible. This module verifies that property
rather than assuming it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Sequence, Tuple

FOLD_A = "A"
FOLD_B = "B"
FOLDS: Tuple[str, ...] = (FOLD_A, FOLD_B)
FOLD_REGISTRY_OFFSETS = {FOLD_A: 0.22, FOLD_B: 0.54}


class V3FoldError(ValueError):
    """A fold-membership invariant that must fail closed."""


@dataclass(frozen=True)
class TrainInternalFolds:
    """Layout-hash membership for the two frozen TRAIN-internal folds."""

    fold_of_layout_sha256: Mapping[str, str]
    layouts_by_fold: Mapping[str, Tuple[str, ...]]
    manifest_sha256: str

    def fold_of(self, layout_sha256: str) -> str:
        try:
            return self.fold_of_layout_sha256[str(layout_sha256)]
        except KeyError:
            raise V3FoldError(
                f"layout {str(layout_sha256)[:16]}... is not a member of either "
                "frozen TRAIN-internal fold") from None

    def complement(self, fold: str) -> str:
        if fold not in FOLDS:
            raise V3FoldError(f"unknown fold {fold!r}")
        return FOLD_B if fold == FOLD_A else FOLD_A


def build_train_internal_folds(manifest: Mapping[str, Any]) -> TrainInternalFolds:
    """Resolve fold membership from the verified manifest, or fail closed."""
    field = "open_loop_v3_train_internal_fold_manifest_v1_sha256"
    if field not in manifest:
        raise V3FoldError("the fold manifest carries no canonical root")
    folds = manifest.get("folds")
    if not isinstance(folds, Mapping) or set(folds) != set(FOLDS):
        raise V3FoldError("the fold manifest must define exactly folds A and B")
    membership: Dict[str, str] = {}
    by_fold: Dict[str, Tuple[str, ...]] = {}
    for name in FOLDS:
        block = folds[name]
        offset = float(block["registry_offset"])
        if abs(offset - FOLD_REGISTRY_OFFSETS[name]) > 1e-12:
            raise V3FoldError(
                f"fold {name} declares registry offset {offset}, expected "
                f"{FOLD_REGISTRY_OFFSETS[name]}")
        entries = block["entries"]
        if len(entries) != 10:
            raise V3FoldError(f"fold {name} must carry exactly 10 layouts")
        families = [str(entry["family"]) for entry in entries]
        if len(set(families)) != 10:
            raise V3FoldError(f"fold {name} must carry exactly one layout per family")
        layouts = []
        for entry in entries:
            digest = str(entry["layout_sha256"])
            if len(digest) != 64:
                raise V3FoldError("a fold entry carries a malformed layout hash")
            if abs(float(entry["offset"]) - FOLD_REGISTRY_OFFSETS[name]) > 1e-12:
                raise V3FoldError("a fold entry offset disagrees with its fold")
            if digest in membership:
                raise V3FoldError(
                    f"layout {digest[:16]}... appears in more than one fold")
            membership[digest] = name
            layouts.append(digest)
        by_fold[name] = tuple(layouts)
    if len(membership) != 20:
        raise V3FoldError("the two folds must partition exactly 20 TRAIN layouts")
    assertions = manifest.get("assertions") or {}
    if assertions.get("geometry_overlap") not in (0, None) or not assertions.get(
            "geometry_disjoint", False):
        raise V3FoldError("the fold manifest does not assert geometry disjointness")
    if assertions.get("row_event_candidate_or_episode_can_cross_a_fold") is not False:
        raise V3FoldError("the fold manifest does not assert crossing impossibility")
    return TrainInternalFolds(
        fold_of_layout_sha256=dict(membership),
        layouts_by_fold=by_fold,
        manifest_sha256=str(manifest[field]))


def assign_events_to_folds(groups: Sequence[Any], folds: TrainInternalFolds,
                           ) -> Mapping[str, str]:
    """Map every decision event to exactly one fold, or fail closed.

    The layout hash is read from the frozen row identity, and every row of the
    event -- both candidates, every robot -- must agree on it. A disagreement
    would mean one event spanned two layouts, which the generator cannot produce
    and which this loader must therefore refuse rather than silently resolve.
    """
    assignment: Dict[str, str] = {}
    for group in groups:
        digests = {
            str(row["scientific_identity"]["layout_sha256"])
            for candidate in (group.compact, group.line)
            for row in candidate.rows
        }
        if len(digests) != 1:
            raise V3FoldError(
                f"decision event {group.decision_event_id} spans "
                f"{len(digests)} layouts")
        event_fold = folds.fold_of(next(iter(digests)))
        if group.decision_event_id in assignment:
            raise V3FoldError(
                f"decision event {group.decision_event_id} appears twice")
        assignment[group.decision_event_id] = event_fold
    return assignment


def split_by_fold(groups: Sequence[Any], folds: TrainInternalFolds,
                  ) -> Mapping[str, Tuple[Any, ...]]:
    """Partition events into the two folds, preserving the given order."""
    assignment = assign_events_to_folds(groups, folds)
    out: Dict[str, list] = {FOLD_A: [], FOLD_B: []}
    for group in groups:
        out[assignment[group.decision_event_id]].append(group)
    return {name: tuple(items) for name, items in out.items()}
