"""The oracle-ceiling go/no-go rule, frozen before CL-DEV-R exists.

V2 said the oracle must "materially improve" the development endpoints. That
was a judgement call and is replaced here by an exact rule using the SAME
primary endpoint, the SAME comparator and the SAME practical threshold as
H-CL1, so the headroom question is asked on the same scale as the confirmatory
question and no new quantity is introduced.

The oracle is DEVELOPMENT-ONLY. It diagnoses possibility, never final evidence.
"""
from __future__ import annotations

from dataclasses import dataclass

from rvt_swarm.cleanroom.benefit_contract import (
    COMPARATOR_ARM, PRACTICAL_BENEFIT_THRESHOLD, BenefitContractError, EndpointResult,
    PRIMARY,
)

ORACLE_ARM = "O1_oracle_recoverability"
ORACLE_COMPARATOR_ARM = COMPARATOR_ARM
ORACLE_ENDPOINT_KEY = PRIMARY.key
ORACLE_PRACTICAL_THRESHOLD = PRACTICAL_BENEFIT_THRESHOLD

ORACLE_HEADROOM_PASS = "ORACLE_HEADROOM_PASS"
ORACLE_HEADROOM_FAIL = "ORACLE_HEADROOM_FAIL"
PREMISE_AT_RISK = "CORE_RECOVERABILITY_DECISION_PREMISE_AT_RISK"


@dataclass(frozen=True)
class OracleVerdict:
    outcome: str
    magnitude_ok: bool
    direction_ok: bool
    safety_ok: bool
    reason: str
    premise_status: str
    may_proceed_automatically_to_main_r: bool


def oracle_headroom(result: EndpointResult, *, oracle_safety_passes: bool) -> OracleVerdict:
    """Exact three-way conjunction on CL-DEV-R.

    PASS requires all three:
      * magnitude  -- the point difference reaches the frozen practical threshold,
      * direction  -- the lower 95 percent bound is strictly above zero, so the
                      sign is established even where the magnitude is not,
      * safety     -- the oracle arm itself satisfies the frozen H-CL2 safety
                      non-inferiority rule against the same comparator, so
                      headroom bought by degrading safety does not count.
    """
    if result.key != ORACLE_ENDPOINT_KEY:
        raise BenefitContractError(
            f"the oracle rule is defined on {ORACLE_ENDPOINT_KEY}, not {result.key}")
    magnitude = result.point_difference >= ORACLE_PRACTICAL_THRESHOLD
    direction = result.ci_lower > 0.0
    safety = bool(oracle_safety_passes)
    ok = magnitude and direction and safety
    reason = (f"point={result.point_difference:.6g} "
              f"({'>=' if magnitude else '<'} {ORACLE_PRACTICAL_THRESHOLD}); "
              f"lower95={result.ci_lower:.6g} ({'>' if direction else '<='} 0); "
              f"safety={'PASS' if safety else 'FAIL'}")
    return OracleVerdict(
        outcome=ORACLE_HEADROOM_PASS if ok else ORACLE_HEADROOM_FAIL,
        magnitude_ok=magnitude, direction_ok=direction, safety_ok=safety, reason=reason,
        premise_status="CORE_RECOVERABILITY_DECISION_PREMISE_RETAINED" if ok else PREMISE_AT_RISK,
        may_proceed_automatically_to_main_r=ok)


def learned_system_interpretation(oracle: OracleVerdict, learned_development_passes: bool) -> str:
    """The frozen reading of the oracle/learned combination on development data."""
    if oracle.outcome == ORACLE_HEADROOM_FAIL:
        return PREMISE_AT_RISK
    if learned_development_passes:
        return "ORACLE_AND_LEARNED_BOTH_SHOW_HEADROOM"
    return ("CORE_POSSIBILITY_CLAIM_RETAINED_AS_A_DEVELOPMENT_HYPOTHESIS; the predictor, "
            "candidate ranking, selector or controller integration is the open problem")
