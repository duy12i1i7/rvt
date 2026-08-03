"""Retry and invalid-record rules with no scientific resampling."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from .budget import INFRASTRUCTURE_RETRY_REASONS


SCIENTIFIC_FAILURE_REASONS: Tuple[str, ...] = (
    "collision",
    "rollout_failure",
    "simulator_timeout",
    "protocol_failure",
    "safety_projection_failure",
    "residual_expert_infeasibility",
    "invalid_candidate_outcome",
)


@dataclass(frozen=True)
class GenerationAttempt:
    job_id: str
    seed: int
    input_sha256: str
    configuration_sha256: str
    output_destination: str
    attempt_index: int = 0


@dataclass(frozen=True)
class InfrastructureRetry:
    original: GenerationAttempt
    retry: GenerationAttempt
    reason: str
    attempts_logged: Tuple[int, int]
    scientific_denominator_delta: int


@dataclass(frozen=True)
class RecoverabilityEmission:
    pair_valid: bool
    emit_training_records: bool
    label: Optional[int]
    preserve_failure_traces: bool
    retain_audit_denominator: bool
    replacement_event: bool


@dataclass(frozen=True)
class ResidualEmission:
    emit_training_record: bool
    preserve_base_sample_and_failure: bool
    retain_expert_invalid_denominator: bool
    replacement_sample: bool


def plan_infrastructure_retry(
    original: GenerationAttempt, reason: str,
) -> InfrastructureRetry:
    if reason in SCIENTIFIC_FAILURE_REASONS:
        raise ValueError("scientific failures never authorize a retry")
    if reason not in INFRASTRUCTURE_RETRY_REASONS:
        raise ValueError("retry reason is not in the frozen infrastructure set")
    if original.attempt_index != 0:
        raise ValueError("at most one infrastructure retry is permitted")
    retry = GenerationAttempt(
        original.job_id,
        original.seed,
        original.input_sha256,
        original.configuration_sha256,
        original.output_destination,
        1,
    )
    return InfrastructureRetry(original, retry, reason, (0, 1), 0)


def recoverability_emission(
    *,
    both_candidate_groups_executed: bool,
    every_required_replica_present: bool,
    rollout_matching_valid: bool,
    ego_graphs_valid: bool,
    provenance_complete: bool,
    task_succeeded: bool,
) -> RecoverabilityEmission:
    valid = all((
        both_candidate_groups_executed,
        every_required_replica_present,
        rollout_matching_valid,
        ego_graphs_valid,
        provenance_complete,
    ))
    return RecoverabilityEmission(
        valid,
        valid,
        int(task_succeeded) if valid else None,
        not valid,
        True,
        False,
    )


def residual_emission(*, expert_feasible_and_valid: bool) -> ResidualEmission:
    return ResidualEmission(
        expert_feasible_and_valid,
        not expert_feasible_and_valid,
        not expert_feasible_and_valid,
        False,
    )
