"""Primary model-candidate contract for the reduced publication scope."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Sequence, Tuple

from ..topology_registry import COMPACT, KEEP, LINE, PRIMARY_TOPOLOGY_IDS


PRIMARY_MODEL_CANDIDATE_SCOPE_SCHEMA_VERSION = "rvt-primary-candidate-scope/v1"

# This order is a publication contract, not a projection of registry order.
PRIMARY_MODEL_CANDIDATE_IDS: Tuple[int, ...] = (COMPACT, LINE)

CANDIDATE_SET_ADMITTED = "CANDIDATE_SET_ADMITTED"
CANDIDATE_SET_REJECTED = "CANDIDATE_SET_REJECTED"
CANDIDATE_ADMITTED = "CANDIDATE_ADMITTED"
CANDIDATE_REJECTED = "CANDIDATE_REJECTED"
CHECKPOINT_COMPATIBLE = "CHECKPOINT_COMPATIBLE"
CHECKPOINT_INCOMPATIBLE = "CHECKPOINT_INCOMPATIBLE"


@dataclass(frozen=True)
class PrimaryCandidateDecision:
    schema_version: str
    status: str
    admitted: bool
    canonical_candidate_ids: Tuple[int, ...]
    rejected_candidate_id: Optional[int]
    reason: str


@dataclass(frozen=True)
class CandidateScore:
    candidate_topology: int
    score: float

    def __post_init__(self) -> None:
        if not math.isfinite(self.score):
            raise ValueError("candidate score must be finite")


@dataclass(frozen=True)
class PrimaryScoreAgreementInput:
    schema_version: str
    candidate_scores: Tuple[CandidateScore, ...]


@dataclass(frozen=True)
class CheckpointVocabularyDecision:
    schema_version: str
    status: str
    compatible: bool
    checkpoint_topology_ids: Tuple[int, ...]
    activated_primary_candidate_ids: Tuple[int, ...]
    inactive_compatibility_ids: Tuple[int, ...]
    reason: str


def primary_candidate_batch() -> Tuple[int, ...]:
    """Return the exact candidate batch for one primary selector query."""
    return PRIMARY_MODEL_CANDIDATE_IDS


def validate_primary_candidate_batch(
    candidate_topology_ids: Sequence[int],
) -> PrimaryCandidateDecision:
    supplied = tuple(candidate_topology_ids)
    if (
        len(supplied) == len(PRIMARY_MODEL_CANDIDATE_IDS)
        and len(set(supplied)) == len(supplied)
        and set(supplied) == set(PRIMARY_MODEL_CANDIDATE_IDS)
    ):
        return PrimaryCandidateDecision(
            PRIMARY_MODEL_CANDIDATE_SCOPE_SCHEMA_VERSION,
            CANDIDATE_SET_ADMITTED,
            True,
            PRIMARY_MODEL_CANDIDATE_IDS,
            None,
            "batch contains exactly COMPACT and LINE",
        )
    rejected = next(
        (item for item in supplied if item not in PRIMARY_MODEL_CANDIDATE_IDS),
        None,
    )
    return PrimaryCandidateDecision(
        PRIMARY_MODEL_CANDIDATE_SCOPE_SCHEMA_VERSION,
        CANDIDATE_SET_REJECTED,
        False,
        (),
        rejected,
        "primary batches must contain exactly one COMPACT and one LINE candidate",
    )


def authorize_primary_score_candidate(
    candidate_topology: int,
) -> PrimaryCandidateDecision:
    if candidate_topology in PRIMARY_MODEL_CANDIDATE_IDS:
        return PrimaryCandidateDecision(
            PRIMARY_MODEL_CANDIDATE_SCOPE_SCHEMA_VERSION,
            CANDIDATE_ADMITTED,
            True,
            (candidate_topology,),
            None,
            "candidate may enter primary distributed score agreement",
        )
    reason = (
        "KEEP is compatibility-only and cannot enter primary score agreement"
        if candidate_topology == KEEP
        else "candidate is outside the primary model scope"
    )
    return PrimaryCandidateDecision(
        PRIMARY_MODEL_CANDIDATE_SCOPE_SCHEMA_VERSION,
        CANDIDATE_REJECTED,
        False,
        (),
        candidate_topology,
        reason,
    )


def prepare_primary_score_agreement(
    candidate_scores: Sequence[CandidateScore],
) -> PrimaryScoreAgreementInput:
    supplied = tuple(candidate_scores)
    decision = validate_primary_candidate_batch(
        tuple(item.candidate_topology for item in supplied)
    )
    if not decision.admitted:
        raise ValueError(decision.reason)
    by_candidate = {item.candidate_topology: item for item in supplied}
    return PrimaryScoreAgreementInput(
        PRIMARY_MODEL_CANDIDATE_SCOPE_SCHEMA_VERSION,
        tuple(by_candidate[item] for item in PRIMARY_MODEL_CANDIDATE_IDS),
    )


def validate_checkpoint_vocabulary(
    checkpoint_topology_ids: Sequence[int],
) -> CheckpointVocabularyDecision:
    supplied = tuple(checkpoint_topology_ids)
    valid = (
        len(set(supplied)) == len(supplied)
        and all(item in PRIMARY_TOPOLOGY_IDS for item in supplied)
        and all(item in supplied for item in PRIMARY_MODEL_CANDIDATE_IDS)
    )
    if not valid:
        return CheckpointVocabularyDecision(
            PRIMARY_MODEL_CANDIDATE_SCOPE_SCHEMA_VERSION,
            CHECKPOINT_INCOMPATIBLE,
            False,
            supplied,
            (),
            (),
            "checkpoint vocabulary must contain both active primary candidates",
        )
    inactive = tuple(
        item for item in supplied if item not in PRIMARY_MODEL_CANDIDATE_IDS
    )
    return CheckpointVocabularyDecision(
        PRIMARY_MODEL_CANDIDATE_SCOPE_SCHEMA_VERSION,
        CHECKPOINT_COMPATIBLE,
        True,
        supplied,
        PRIMARY_MODEL_CANDIDATE_IDS,
        inactive,
        "extra registry topology IDs remain inactive compatibility vocabulary",
    )
