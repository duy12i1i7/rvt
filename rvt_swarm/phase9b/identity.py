"""Canonical Phase 9B cells, jobs, seeds, timestamps and dense selection."""

from __future__ import annotations

import hashlib
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Mapping, Optional, Sequence, Tuple

from ..phase8.common import canonical_json_bytes, sha256_document
from ..phase8.seeds import SEED_NAMESPACES
from ..phase8.splits import load_nonfinal_split_manifest
from .budget import (
    DATASET_IDS,
    DENSE_SELECTION_VERSION,
    EVENT_TIMESTAMP_SCHEDULES,
    GENERATION_BUDGET_SCHEMA_VERSION,
    GENERATION_JOB_ID_SCHEMA_VERSION,
    GENERATION_SEED_DERIVATION_VERSION,
    SOURCE_CLASSES,
    STUDY_A_N24_EVALUATION,
    STUDY_A_TRAIN,
    STUDY_B_TRAIN,
    STUDY_B_VALIDATION,
    DatasetBudgetSpec,
    dataset_budget,
)


_SEED_ROOT = {item.name: item.root_seed for item in SEED_NAMESPACES}


@dataclass(frozen=True)
class DatasetCell:
    dataset_id: str
    study: str
    split: str
    family_id: str
    layout_sha256: str
    team_size: int

    def __post_init__(self) -> None:
        if self.dataset_id not in DATASET_IDS:
            raise ValueError("unknown dataset cell")
        if self.split == "final_test" or "final_test" in self.dataset_id:
            raise PermissionError("final-test jobs cannot be constructed")
        spec = dataset_budget(self.dataset_id)
        if self.study != spec.study or self.split != spec.split:
            raise ValueError("dataset cell study/split differs from its budget")
        if self.team_size not in spec.team_sizes:
            raise ValueError("team size is outside the dataset budget")
        if self.family_id not in {f"F{index}" for index in range(1, 11)}:
            raise ValueError("unknown scenario family")
        if len(self.layout_sha256) != 64:
            raise ValueError("layout hash is invalid")

    def canonical_hash(self) -> str:
        return sha256_document({
            "schema_version": GENERATION_JOB_ID_SCHEMA_VERSION,
            "kind": "dataset_cell",
            **asdict(self),
        })


@dataclass(frozen=True)
class SourceEpisodeIdentity:
    cell: DatasetCell
    source_class: str
    episode_index: int

    def __post_init__(self) -> None:
        if self.source_class not in SOURCE_CLASSES or self.episode_index < 0:
            raise ValueError("source episode identity is invalid")

    def job_id(self) -> str:
        return "/".join((
            GENERATION_JOB_ID_SCHEMA_VERSION,
            "source_episode",
            self.cell.study,
            self.cell.split,
            self.cell.family_id,
            self.cell.layout_sha256,
            f"N{self.cell.team_size}",
            self.source_class,
            f"episode-{self.episode_index}",
        ))


@dataclass(frozen=True)
class DecisionEventIdentity:
    source_episode: SourceEpisodeIdentity
    event_slot_index: int

    def job_id(self) -> str:
        if self.event_slot_index < 0:
            raise ValueError("event slot index must be nonnegative")
        return f"{self.source_episode.job_id()}/event-{self.event_slot_index}"


@dataclass(frozen=True)
class CandidateReplicaIdentity:
    decision_event: DecisionEventIdentity
    candidate_topology: int
    replica_index: int

    def job_id(self) -> str:
        if self.candidate_topology not in (5, 2) or self.replica_index < 0:
            raise ValueError("candidate replica identity is invalid")
        return (
            f"{self.decision_event.job_id()}/candidate-{self.candidate_topology}"
            f"/replica-{self.replica_index}"
        )


@dataclass(frozen=True)
class EventSlot:
    slot_index: int
    normalized_horizon_position: float
    requested_timestamp_seconds: float
    scheduled_control_step: int
    scheduled_timestamp_seconds: float
    available: bool
    unavailable_reason: Optional[str]


@dataclass(frozen=True)
class DenseRecordIdentity:
    episode_id: str
    timestep: int
    robot_id: int
    topology_id: int
    graph_fingerprint: str

    def __post_init__(self) -> None:
        if not self.episode_id or min(self.timestep, self.robot_id) < 0:
            raise ValueError("dense identity indices are invalid")
        if self.topology_id not in (5, 2) or len(self.graph_fingerprint) != 64:
            raise ValueError("dense identity topology or graph hash is invalid")

    def canonical_key(self) -> Tuple[object, ...]:
        return (
            self.episode_id,
            self.timestep,
            self.robot_id,
            self.topology_id,
            self.graph_fingerprint,
        )


@dataclass(frozen=True)
class DenseSelection:
    selected: Tuple[DenseRecordIdentity, ...]
    valid_candidate_count: int
    quota: int
    shortfall: int


def build_dataset_cells(root: Path, dataset_id: str) -> Tuple[DatasetCell, ...]:
    spec = dataset_budget(dataset_id)
    if spec.layout_source_split not in ("train", "validation"):
        raise PermissionError("final-test layouts are not a Phase 9B source")
    manifest = load_nonfinal_split_manifest(
        root / f"results/rvt_fd24/splits/{spec.layout_source_split}_layouts.json"
    )
    records = manifest["layout_records"]
    return tuple(sorted(
        (
            DatasetCell(
                spec.dataset_id,
                spec.study,
                spec.split,
                str(record["family_id"]),
                str(record["geometry_sha256"]),
                team_size,
            )
            for record in records
            for team_size in spec.team_sizes
        ),
        key=lambda item: item.canonical_hash(),
    ))


def source_episode_counts(
    cell: DatasetCell, all_dataset_cells: Sequence[DatasetCell],
) -> Tuple[int, ...]:
    if cell.dataset_id == STUDY_A_TRAIN:
        return (2, 2, 2, 2, 2, 2)
    if cell.dataset_id != STUDY_B_TRAIN:
        return (1, 1, 1, 1, 1, 1)
    ordered = tuple(sorted(all_dataset_cells, key=lambda item: item.canonical_hash()))
    if len(ordered) != 120 or any(item.dataset_id != STUDY_B_TRAIN for item in ordered):
        raise ValueError("Study B train rotation requires all 120 canonical cells")
    hashes = [item.canonical_hash() for item in ordered]
    if len(set(hashes)) != len(hashes) or cell.canonical_hash() not in hashes:
        raise ValueError("Study B train cells are duplicate or incomplete")
    rank = hashes.index(cell.canonical_hash())
    phase = int(sha256_document({
        "schema_version": GENERATION_BUDGET_SCHEMA_VERSION,
        "dataset_id": STUDY_B_TRAIN,
        "allocation": "balanced_cyclic_four_source_window",
    })[:8], 16) % len(SOURCE_CLASSES)
    start = (rank + phase) % len(SOURCE_CLASSES)
    doubled = {(start + offset) % len(SOURCE_CLASSES) for offset in range(4)}
    return tuple(2 if index in doubled else 1 for index in range(len(SOURCE_CLASSES)))


def source_episode_identities(
    cell: DatasetCell, all_dataset_cells: Sequence[DatasetCell],
) -> Tuple[SourceEpisodeIdentity, ...]:
    counts = source_episode_counts(cell, all_dataset_cells)
    return tuple(
        SourceEpisodeIdentity(cell, source_class, episode_index)
        for source_class, count in zip(SOURCE_CLASSES, counts)
        for episode_index in range(count)
    )


def event_slot_count(cell: DatasetCell, source_class: str) -> int:
    if cell.dataset_id != STUDY_B_VALIDATION:
        return 5
    selected = int(cell.canonical_hash(), 16) % len(SOURCE_CLASSES)
    return 5 if SOURCE_CLASSES[selected] == source_class else 4


def map_event_slots(
    *,
    horizon_seconds: float,
    control_period_seconds: float,
    slot_count: int,
    termination_step: Optional[int] = None,
    termination_cause: Optional[str] = None,
) -> Tuple[EventSlot, ...]:
    if slot_count not in EVENT_TIMESTAMP_SCHEDULES:
        raise ValueError("only the frozen four-slot and five-slot schedules exist")
    if not math.isfinite(horizon_seconds) or horizon_seconds <= 0.0:
        raise ValueError("horizon must be finite and positive")
    if not math.isfinite(control_period_seconds) or control_period_seconds <= 0.0:
        raise ValueError("control period must be finite and positive")
    if termination_step is not None and (termination_step < 0 or not termination_cause):
        raise ValueError("early termination requires a nonnegative step and cause")
    slots = []
    for index, normalized in enumerate(EVENT_TIMESTAMP_SCHEDULES[slot_count]):
        requested = normalized * horizon_seconds
        step = int(math.ceil(requested / control_period_seconds - 1e-12))
        available = termination_step is None or step <= termination_step
        slots.append(EventSlot(
            index,
            normalized,
            requested,
            step,
            step * control_period_seconds,
            available,
            None if available else termination_cause,
        ))
    return tuple(slots)


def derive_generation_seed(
    namespace: str,
    *,
    study: str,
    split: str,
    scenario_family: str,
    layout_sha256: str,
    team_size: int,
    source_class: str,
    episode_index: int,
    event_slot_index: Optional[int] = None,
    candidate_topology: Optional[int] = None,
    replica_index: Optional[int] = None,
) -> int:
    if namespace not in _SEED_ROOT:
        raise ValueError("unknown approved seed namespace")
    if split == "final_test" or "final_test" in split:
        raise PermissionError("final-test generation seeds cannot be derived")
    if source_class not in SOURCE_CLASSES:
        raise ValueError("unknown source trajectory class")
    payload = {
        "seed_namespace": namespace,
        "seed_namespace_root": _SEED_ROOT[namespace],
        "seed_derivation_version": GENERATION_SEED_DERIVATION_VERSION,
        "generation_budget_schema": GENERATION_BUDGET_SCHEMA_VERSION,
        "study": study,
        "split": split,
        "scenario_family": scenario_family,
        "layout_sha256": layout_sha256,
        "team_size": team_size,
        "source_trajectory_class": source_class,
        "episode_index": episode_index,
        "event_slot_index": event_slot_index,
        "candidate_topology": candidate_topology,
        "replica_index": replica_index,
    }
    return int.from_bytes(hashlib.sha256(canonical_json_bytes(payload)).digest()[:4], "big")


def reject_duplicate_semantic_identities(identities: Iterable[str]) -> None:
    seen = set()
    for identity in identities:
        if identity in seen:
            raise ValueError(f"duplicate semantic job identity: {identity}")
        seen.add(identity)


def select_dense_records(
    records: Sequence[DenseRecordIdentity],
    *,
    quota: int,
    cell_sha256: str,
    generation_budget_sha256: str,
) -> DenseSelection:
    if quota < 0 or len(cell_sha256) != 64 or len(generation_budget_sha256) != 64:
        raise ValueError("dense selection quota or provenance hash is invalid")
    canonical = tuple(sorted(records, key=lambda item: item.canonical_key()))
    if len({item.canonical_key() for item in canonical}) != len(canonical):
        raise ValueError("duplicate dense record identity")

    def rank(item: DenseRecordIdentity) -> Tuple[str, Tuple[object, ...]]:
        digest = sha256_document({
            "selection_version": DENSE_SELECTION_VERSION,
            "generation_budget_sha256": generation_budget_sha256,
            "cell_sha256": cell_sha256,
            "identity": asdict(item),
        })
        return digest, item.canonical_key()

    selected = tuple(sorted(canonical, key=rank)[:quota])
    return DenseSelection(
        selected,
        len(canonical),
        quota,
        max(0, quota - len(canonical)),
    )
