"""Clean-room role registry, study and split authority.

These identifiers are deliberately disjoint from every historical pilot value.
They are NOT added to any historical allowlist; they are authorized only here.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

CLEAN_ROOM_STUDY = "rvt_cleanroom_final_v1"

# The generator's own split namespace that supplies each role's geometry, and the
# variant index that produces the role's frozen offset under the frozen formula
# offset = _SPLIT_OFFSETS[generator_split] + 0.11 * variant_index.
TRAIN_NS, FINAL_TEST_NS = "train", "final_test"


class RoleAuthorityError(ValueError):
    """A clean-room role-authority violation that must fail closed."""


@dataclass(frozen=True)
class CleanRoomRole:
    role: str
    dataset_id: str
    split: str
    generator_split_namespace: str
    layout_variant_index: int
    offset: float


ROLES: Mapping[str, CleanRoomRole] = {
    "TRAIN-R":     CleanRoomRole("TRAIN-R", "cleanroom_train_r", "train_r", TRAIN_NS, 0, 0.00),
    "SELECT-R":    CleanRoomRole("SELECT-R", "cleanroom_select_r", "select_r", TRAIN_NS, 1, 0.11),
    "CL-DEV-R":    CleanRoomRole("CL-DEV-R", "cleanroom_cl_dev_r", "cl_dev_r", TRAIN_NS, 4, 0.44),
    "MAIN-R":      CleanRoomRole("MAIN-R", "cleanroom_main_r", "main_r", TRAIN_NS, 5, 0.55),
    "MECH-R":      CleanRoomRole("MECH-R", "cleanroom_mech_r", "mech_r", TRAIN_NS, 6, 0.66),
    "PROTECTED-R": CleanRoomRole("PROTECTED-R", "cleanroom_protected_r", "protected_r",
                                 FINAL_TEST_NS, 0, 0.79),
}

CLEAN_ROOM_DATASET_IDS: tuple[str, ...] = tuple(r.dataset_id for r in ROLES.values())
CLEAN_ROOM_SPLITS: tuple[str, ...] = tuple(r.split for r in ROLES.values())

# Historical pilot vocabulary, reproduced here ONLY so this layer can refuse it.
_HISTORICAL_STUDIES = frozenset({"study_a_zero_shot", "study_b_with_n24",
                                 "study_a_n24_evaluation", "final_test"})
_HISTORICAL_SPLITS = frozenset({"train", "validation", "n24_evaluation", "final_test", "test"})
_HISTORICAL_DATASET_IDS = frozenset({"study_a_train", "study_a_validation",
                                     "study_a_n24_evaluation", "study_b_train",
                                     "study_b_validation"})


def role(name: str) -> CleanRoomRole:
    try:
        return ROLES[name]
    except KeyError as exc:
        raise RoleAuthorityError(f"unknown clean-room role {name!r}") from exc


def authorize(study: str, split: str, dataset_id: str) -> CleanRoomRole:
    """Accept only a clean-room triple. A pilot identity is refused, never reused."""
    if study in _HISTORICAL_STUDIES or split in _HISTORICAL_SPLITS \
            or dataset_id in _HISTORICAL_DATASET_IDS:
        raise RoleAuthorityError(
            f"historical pilot identity may not be used as clean-room authority: "
            f"{study}/{split}/{dataset_id}")
    if study != CLEAN_ROOM_STUDY:
        raise RoleAuthorityError(
            f"unknown clean-room study {study!r}; expected {CLEAN_ROOM_STUDY!r}")
    for item in ROLES.values():
        if item.split == split:
            if item.dataset_id != dataset_id:
                raise RoleAuthorityError(
                    f"split {split!r} belongs to dataset {item.dataset_id!r}, not {dataset_id!r}")
            return item
    raise RoleAuthorityError(f"unknown clean-room split {split!r}")


def assert_disjoint_from_history() -> None:
    """This layer must never overlap the pilot vocabulary."""
    if set(CLEAN_ROOM_DATASET_IDS) & _HISTORICAL_DATASET_IDS:
        raise RoleAuthorityError("a clean-room dataset id collides with a pilot dataset id")
    if set(CLEAN_ROOM_SPLITS) & _HISTORICAL_SPLITS:
        raise RoleAuthorityError("a clean-room split collides with a pilot split")
    if CLEAN_ROOM_STUDY in _HISTORICAL_STUDIES:
        raise RoleAuthorityError("the clean-room study collides with a pilot study")
