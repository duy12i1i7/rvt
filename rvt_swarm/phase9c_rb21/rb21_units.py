"""Atomic scientific work units and operationally invariant digests for RB-21."""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterable, Mapping, Sequence, Tuple

from ..phase8.common import sha256_document
from ..phase9c_rb.counterfactual import replica_count_for_family

RESIDUAL_CANDIDATE_INDICES: Tuple[int, ...] = tuple(range(9))

OPERATIONAL_METADATA_KEYS = frozenset({
    "aggregation_seconds",
    "attempt_id",
    "attempt_index",
    "candidate_seconds",
    "chunk_id",
    "chunk_size",
    "cpu_seconds",
    "cpu_utilization_percent",
    "max_rss_bytes",
    "pid",
    "replica_seconds",
    "scientific_seconds",
    "selector_target_reduction_seconds",
    "serialized_bytes",
    "serialization_seconds",
    "seconds",
    "thread_settings",
    "wall_seconds",
    "worker_count",
    "worker_id",
})


class AtomicUnitError(ValueError):
    """A scheduler request would violate an atomic scientific boundary."""


@dataclass(frozen=True)
class DiagnosticCase:
    case_id: str
    split: str
    layout_id: str
    family: str
    team_size: int
    source_policy: str
    seeds: Mapping[str, int]
    decision_steps: Tuple[int, ...]
    robot_ids: Tuple[int, ...]
    structural_roles: Tuple[str, ...]

    def __post_init__(self) -> None:
        if self.split not in ("train", "validation"):
            raise AtomicUnitError("RB-21 diagnostics may use only train/validation")
        if self.team_size == 24:
            raise AtomicUnitError("Study A N=24 is sealed during RB-21")
        if self.family not in ("F1", "F5", "F8", "F9"):
            raise AtomicUnitError("the RB-21 benchmark family is outside its freeze")
        if not self.decision_steps or min(self.decision_steps) < 0:
            raise AtomicUnitError("a diagnostic case needs nonnegative decision steps")
        if not self.robot_ids or min(self.robot_ids) < 0:
            raise AtomicUnitError("a diagnostic case needs robot identities")
        if max(self.robot_ids) >= self.team_size:
            raise AtomicUnitError("a robot identity is outside the team")


@dataclass(frozen=True)
class ResidualAtomicUnit:
    """One robot decision containing all nine frozen candidate continuations."""

    case: DiagnosticCase
    decision_step: int
    robot_id: int
    candidate_indices: Tuple[int, ...] = RESIDUAL_CANDIDATE_INDICES

    def __post_init__(self) -> None:
        if tuple(self.candidate_indices) != RESIDUAL_CANDIDATE_INDICES:
            raise AtomicUnitError(
                "a residual atomic unit must own all nine candidates in canonical order")
        if self.decision_step not in self.case.decision_steps:
            raise AtomicUnitError("decision step is not predeclared by the case")
        if self.robot_id not in self.case.robot_ids:
            raise AtomicUnitError("robot is not predeclared by the case")

    @property
    def unit_kind(self) -> str:
        return "RESIDUAL"

    @property
    def atomic_unit_id(self) -> str:
        return sha256_document({
            "kind": self.unit_kind,
            "case_id": self.case.case_id,
            "decision_step": self.decision_step,
            "robot_id": self.robot_id,
            "candidate_indices": list(self.candidate_indices),
        })

    def as_dict(self) -> Dict[str, Any]:
        return {"unit_kind": self.unit_kind, "atomic_unit_id": self.atomic_unit_id,
                **asdict(self)}


@dataclass(frozen=True)
class RecoverabilityAtomicUnit:
    """One decision state and candidate topology with its complete replica set."""

    case: DiagnosticCase
    decision_step: int
    candidate_topology: int
    replica_indices: Tuple[int, ...]

    def __post_init__(self) -> None:
        if self.decision_step not in self.case.decision_steps:
            raise AtomicUnitError("decision step is not predeclared by the case")
        if self.candidate_topology not in (2, 5):
            raise AtomicUnitError("recoverability candidates are frozen to COMPACT/LINE")
        expected = tuple(range(replica_count_for_family(self.case.family)))
        if tuple(self.replica_indices) != expected:
            raise AtomicUnitError(
                f"{self.case.family} requires the complete replica set {expected}")

    @property
    def unit_kind(self) -> str:
        return "RECOVERABILITY"

    @property
    def atomic_unit_id(self) -> str:
        return sha256_document({
            "kind": self.unit_kind,
            "case_id": self.case.case_id,
            "decision_step": self.decision_step,
            "candidate_topology": self.candidate_topology,
            "replica_indices": list(self.replica_indices),
        })

    def as_dict(self) -> Dict[str, Any]:
        return {"unit_kind": self.unit_kind, "atomic_unit_id": self.atomic_unit_id,
                **asdict(self)}


def reject_intra_unit_split(unit: object, selected_indices: Sequence[int]) -> None:
    """Reject scheduler-level candidate or replica subsets."""
    if isinstance(unit, ResidualAtomicUnit):
        if tuple(selected_indices) != unit.candidate_indices:
            raise AtomicUnitError("scheduler candidate splitting is prohibited")
        return
    if isinstance(unit, RecoverabilityAtomicUnit):
        if tuple(selected_indices) != unit.replica_indices:
            raise AtomicUnitError("scheduler replica splitting is prohibited")
        return
    raise AtomicUnitError("unknown atomic unit")


def _scientific_projection(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _scientific_projection(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
            if str(key) not in OPERATIONAL_METADATA_KEYS
        }
    if isinstance(value, (list, tuple)):
        return [_scientific_projection(item) for item in value]
    return value


def scientific_semantic_projection(results: Iterable[Mapping[str, Any]]) -> list:
    """Canonical science only; worker, chunk, attempt and timing data are removed."""
    projected = [_scientific_projection(dict(result)) for result in results]
    return sorted(projected, key=lambda item: str(item["atomic_unit_id"]))


def scientific_semantic_digest(results: Iterable[Mapping[str, Any]]) -> str:
    return sha256_document(scientific_semantic_projection(results))


@dataclass(frozen=True)
class ThreadSettings:
    omp_num_threads: int = 1
    mkl_num_threads: int = 1
    openblas_num_threads: int = 1
    torch_num_threads: int = 1
    torch_num_interop_threads: int = 1

    def __post_init__(self) -> None:
        if min(asdict(self).values()) < 1:
            raise ValueError("nested thread counts must be positive")

    def apply(self) -> Mapping[str, int]:
        os.environ["OMP_NUM_THREADS"] = str(self.omp_num_threads)
        os.environ["MKL_NUM_THREADS"] = str(self.mkl_num_threads)
        os.environ["OPENBLAS_NUM_THREADS"] = str(self.openblas_num_threads)
        try:
            import torch
            torch.set_num_threads(self.torch_num_threads)
            try:
                torch.set_num_interop_threads(self.torch_num_interop_threads)
            except RuntimeError:
                if torch.get_num_interop_threads() != self.torch_num_interop_threads:
                    raise
            observed = {
                "torch_num_threads": int(torch.get_num_threads()),
                "torch_num_interop_threads": int(torch.get_num_interop_threads()),
            }
        except ImportError:
            observed = {
                "torch_num_threads": self.torch_num_threads,
                "torch_num_interop_threads": self.torch_num_interop_threads,
            }
        return {
            "omp_num_threads": int(os.environ["OMP_NUM_THREADS"]),
            "mkl_num_threads": int(os.environ["MKL_NUM_THREADS"]),
            "openblas_num_threads": int(os.environ["OPENBLAS_NUM_THREADS"]),
            **observed,
        }


def infrastructure_timeout_result(unit_id: str, timeout_seconds: float) -> Dict[str, Any]:
    """Timeout is operational failure only; it emits no target or task outcome."""
    return {
        "atomic_unit_id": unit_id,
        "status": "INFRASTRUCTURE_FAILURE",
        "infrastructure_failure_reason": "OPERATIONAL_TIMEOUT",
        "timeout_seconds": float(timeout_seconds),
        "scientific_horizon_changed": False,
        "target_v4_evaluated_from_timeout": False,
        "target_row_emitted": False,
        "semantic_retry_count": 0,
    }
