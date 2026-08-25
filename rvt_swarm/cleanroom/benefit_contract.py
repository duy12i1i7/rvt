"""H-CL1 -- the closed-loop benefit contract, frozen before any clean-room data.

Nothing here is a new metric. Every endpoint is already emitted by the frozen
evaluator (rvt_swarm/metrics.py) and every threshold is inherited from the
pilot's own frozen H1 requirement, so no quantity was chosen by looking at a
clean-room outcome -- none exists.

PRIMARY endpoint: episode task success, the pilot's H1 endpoint.

    success = goal_reached AND collision_free AND form_ok      (environment.py)

Its dependence on collision_free is deliberate and CONSERVATIVE: an unsafe
episode cannot be credited as a benefit, so a safety-degrading system is
penalised in the benefit endpoint before H-CL2 is ever consulted. The
conjunction with H-CL2 is therefore doubly protective rather than circular.

Secondary endpoints are tested in a FIXED SEQUENCE. Each is tested at the full
level only if every preceding endpoint passed, and testing stops at the first
failure. A fixed-sequence procedure controls the family-wise error rate without
any alpha correction, for the same reason the safety intersection-union test
does: no endpoint is ever tested unless the ones before it were rejected.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

# Inherited verbatim from results/rvt_fd24/phase9d_h1_requirement_map_v1.json,
# whose frozen H1 reads: "Recoverability selection improves episode task success
# by at least 0.08 absolute over both direct classification and local geometric
# selection, while meeting the frozen collision gate."
PRACTICAL_BENEFIT_THRESHOLD = 0.08

CONFIDENCE_LEVEL = 0.95
BOOTSTRAP_REPLICATES = 10000
BOOTSTRAP_SEED = 20260901          # the clean-room seed, as everywhere else

TREATMENT_ARM = "R1_full_recoverability_aware_rvt"
COMPARATOR_ARM = "B1_reactive_topology_adaptation_no_recoverability"


class BenefitContractError(ValueError):
    """A benefit-contract violation that must fail closed."""


@dataclass(frozen=True)
class BenefitEndpoint:
    key: str
    concept: str
    metric_key: str
    definition: str
    unit: str
    aggregation_unit: str
    direction_of_benefit: str      # "increase" or "decrease"
    rank: int                      # 1 is primary; the rest are the fixed sequence
    invalid_episode_imputation: float


PRIMARY = BenefitEndpoint(
    key="episode_task_success_rate", concept="task progress",
    metric_key="success",
    definition="per-episode indicator that the goal was reached, the episode was "
               "collision free, and terminal formation error was inside tolerance; "
               "the frozen evaluator's `success`",
    unit="episode rate in [0, 1]", aggregation_unit="source episode",
    direction_of_benefit="increase", rank=1, invalid_episode_imputation=0.0)

SEQUENCE: tuple[BenefitEndpoint, ...] = (
    PRIMARY,
    BenefitEndpoint(
        key="deadlock_rate", concept="liveness / deadlock", metric_key="deadlock",
        definition="per-episode indicator that accumulated stalled distance reached "
                   "max(goal_tolerance, nominal_spacing) without the goal being reached",
        unit="episode rate in [0, 1]", aggregation_unit="source episode",
        direction_of_benefit="decrease", rank=2, invalid_episode_imputation=1.0),
    BenefitEndpoint(
        key="irreversible_collapse_rate", concept="recovery",
        metric_key="irreversible_collapse",
        definition="per-episode indicator that the team entered an irrecoverable "
                   "condition, the frozen evaluator's `irreversible_collapse`",
        unit="episode rate in [0, 1]", aggregation_unit="source episode",
        direction_of_benefit="decrease", rank=3, invalid_episode_imputation=1.0),
    BenefitEndpoint(
        key="goal_reached_rate", concept="task progress, decoupled from formation and safety",
        metric_key="goal_reached",
        definition="per-episode indicator that the goal region was reached and held, "
                   "independent of collision-freeness and formation tolerance",
        unit="episode rate in [0, 1]", aggregation_unit="source episode",
        direction_of_benefit="increase", rank=4, invalid_episode_imputation=0.0),
)

# The maximum share of episodes that may fail to simulate before the analysis
# refuses to report. Invalid episodes are never silently dropped.
MAXIMUM_INVALID_EPISODE_FRACTION = 0.02


@dataclass(frozen=True)
class EndpointResult:
    key: str
    point_difference: float
    ci_lower: float
    ci_upper: float


@dataclass(frozen=True)
class EndpointVerdict:
    key: str
    passed: bool
    tested: bool
    reason: str


def impute_invalid(endpoint: BenefitEndpoint, values: Sequence[float | None]) -> list[float]:
    """Worst-case imputation. An episode that did not simulate counts against its own arm."""
    return [endpoint.invalid_episode_imputation if v is None else float(v) for v in values]


def invalid_fraction_acceptable(invalid: int, total: int) -> bool:
    if total <= 0:
        raise BenefitContractError("no episodes were supplied")
    return (invalid / total) <= MAXIMUM_INVALID_EPISODE_FRACTION


def _benefit_bound(endpoint: BenefitEndpoint, result: EndpointResult) -> float:
    """The bound on the beneficial side of (treatment - comparator)."""
    return result.ci_lower if endpoint.direction_of_benefit == "increase" else -result.ci_upper


def primary_passes(result: EndpointResult) -> bool:
    """H-CL1's primary rule: superiority by the frozen practical margin, strictly.

    lower95( success_treatment - success_comparator ) > 0.08
    """
    if result.key != PRIMARY.key:
        raise BenefitContractError(f"{result.key} is not the primary endpoint")
    return result.ci_lower > PRACTICAL_BENEFIT_THRESHOLD


def fixed_sequence_verdicts(results: Mapping[str, EndpointResult]
                            ) -> tuple[dict[str, EndpointVerdict], bool]:
    """Test in rank order, stopping at the first failure. Returns (verdicts, H-CL1)."""
    missing = [e.key for e in SEQUENCE if e.key not in results]
    if missing:
        raise BenefitContractError(f"no result for benefit endpoints: {missing}")
    verdicts: dict[str, EndpointVerdict] = {}
    still_testing = True
    for endpoint in SEQUENCE:
        r = results[endpoint.key]
        if not still_testing:
            verdicts[endpoint.key] = EndpointVerdict(
                endpoint.key, False, False,
                "not tested: an earlier endpoint in the fixed sequence failed")
            continue
        if endpoint.rank == 1:
            ok = primary_passes(r)
            reason = (f"lower95 = {r.ci_lower:.6g} "
                      f"{'>' if ok else '<='} {PRACTICAL_BENEFIT_THRESHOLD}")
        else:
            ok = _benefit_bound(endpoint, r) > 0.0
            reason = f"beneficial-side 95% bound = {_benefit_bound(endpoint, r):.6g} > 0"
        verdicts[endpoint.key] = EndpointVerdict(endpoint.key, ok, True, reason)
        still_testing = ok
    return verdicts, verdicts[PRIMARY.key].passed


# ---------------------------------------------------------- claim language ---

CLAIM_IMPROVES = "improves"
CLAIM_SUBSTANTIALLY = "substantially improves"


def permitted_benefit_language(result: EndpointResult) -> tuple[str, ...]:
    """What may be written about the primary endpoint, and nothing beyond it."""
    if result.key != PRIMARY.key:
        raise BenefitContractError(f"{result.key} is not the primary endpoint")
    if result.ci_lower > PRACTICAL_BENEFIT_THRESHOLD:
        # The frozen margin IS the practical-effect threshold, so clearing it
        # licenses the magnitude wording as well as the directional wording.
        return (CLAIM_IMPROVES, CLAIM_SUBSTANTIALLY)
    if result.ci_lower > 0.0:
        # Directionally positive but below the frozen practical margin. H-CL1
        # has failed; only a descriptive statement is permitted.
        return ()
    return ()


FORBIDDEN_WITHOUT_PRIMARY_PASS = (
    "improves", "substantially improves", "materially improves", "large improvement",
    "outperforms", "is better than", "advances the state of the art")
PERMITTED_DESCRIPTION_WHEN_SUBTHRESHOLD = (
    "a positive but sub-threshold difference was observed; the preregistered "
    "benefit criterion was not met")
