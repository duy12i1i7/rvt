"""The single qualified entry point for the confirmatory closed-loop analysis.

Orchestration calls `evaluate_closed_loop` and reports what it returns. It may
not recompute, reinterpret or override any of the three verdicts, and it may not
restate any rule this package defines.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from rvt_swarm.cleanroom.benefit_contract import (
    BOOTSTRAP_REPLICATES, BOOTSTRAP_SEED, COMPARATOR_ARM, CONFIDENCE_LEVEL,
    PRIMARY, SEQUENCE, TREATMENT_ARM, BenefitContractError, EndpointResult,
    EndpointVerdict, fixed_sequence_verdicts, invalid_fraction_acceptable,
)
from rvt_swarm.cleanroom.safety_contract import (
    PRIMARY_ENDPOINTS as SAFETY_ENDPOINTS, EndpointVerdict as SafetyVerdict,
    central_closed_loop_claim, safety_hypothesis_passes,
)
from rvt_swarm.cleanroom.universe import assert_episode_universe

CLAIM_SUPPORTED = "CENTRAL_CLAIM_SUPPORTED"
CLAIM_NOT_SUPPORTED = "CENTRAL_CLAIM_NOT_SUPPORTED"


@dataclass(frozen=True)
class ClosedLoopVerdict:
    h_cl1_pass: bool
    h_cl2_pass: bool
    central_claim: str
    central_claim_detail: str
    benefit_verdicts: Mapping[str, EndpointVerdict]
    safety_verdicts: Mapping[str, SafetyVerdict]
    episodes_declared: int
    episodes_invalid: int


def evaluate_closed_loop(
    *,
    manifest_episode_ids: Sequence[str],
    manifest_episode_layout: Mapping[str, str],
    observed_event_episode_ids: Sequence[str],
    expected_episode_count: int,
    treatment_arm: str,
    comparator_arm: str,
    benefit_results: Mapping[str, EndpointResult],
    safety_verdicts: Mapping[str, SafetyVerdict],
    invalid_episode_count: int,
    bootstrap_replicates: int,
    bootstrap_seed: int,
    confidence_level: float,
) -> ClosedLoopVerdict:
    """Return H-CL1, H-CL2 and the central-claim verdict. Fails closed on any mismatch."""
    if treatment_arm != TREATMENT_ARM or comparator_arm != COMPARATOR_ARM:
        raise BenefitContractError(
            f"the frozen contrast is {TREATMENT_ARM} minus {COMPARATOR_ARM}; "
            f"got {treatment_arm} minus {comparator_arm}")
    if (bootstrap_replicates != BOOTSTRAP_REPLICATES or bootstrap_seed != BOOTSTRAP_SEED
            or confidence_level != CONFIDENCE_LEVEL):
        raise BenefitContractError(
            "the bootstrap parameters do not match the frozen contract")
    extra = sorted(set(benefit_results) - {e.key for e in SEQUENCE})
    if extra:
        raise BenefitContractError(
            f"endpoints outside the frozen benefit sequence were supplied: {extra}")

    universe = assert_episode_universe(
        manifest_episode_ids, manifest_episode_layout, observed_event_episode_ids,
        expected_count=expected_episode_count)
    if not invalid_fraction_acceptable(invalid_episode_count, len(universe)):
        raise BenefitContractError(
            f"{invalid_episode_count} of {len(universe)} episodes were invalid, above "
            "the frozen maximum; the analysis refuses to report")

    benefit_verdicts, h1 = fixed_sequence_verdicts(benefit_results)
    h2 = safety_hypothesis_passes(safety_verdicts)
    detail = central_closed_loop_claim(h1, h2)
    return ClosedLoopVerdict(
        h_cl1_pass=h1, h_cl2_pass=h2,
        central_claim=CLAIM_SUPPORTED if (h1 and h2) else CLAIM_NOT_SUPPORTED,
        central_claim_detail=detail,
        benefit_verdicts=benefit_verdicts, safety_verdicts=safety_verdicts,
        episodes_declared=len(universe), episodes_invalid=invalid_episode_count)
