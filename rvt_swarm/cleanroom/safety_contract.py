"""The confirmatory safety decision rule, frozen before any clean-room data.

Every margin here is anchored to a number that already existed in the frozen
configuration or the pilot's frozen collision gate. None was chosen by looking
at an outcome, because no clean-room outcome exists.

Frozen physical constants this file depends on (rvt_swarm/config.py,
rvt_swarm/runtime_configuration.py):

    robot_radius                    0.18 m
    obstacle_radius                 0.35 m
    inter_robot_safety_margin       0.04 m
    obstacle_clearance_margin       0.37 m  (0.35 obstacle radius + 0.02 surface)
    min_rr_distance                 0.40 m  = 2*0.18 + 0.04
    min_ro_distance                 0.55 m  = 0.18 + 0.37
    maximum_speed                   0.90 m/s
    maximum_acceleration            0.60 m/s^2

The four primary endpoints are combined by an INTERSECTION-UNION TEST: the
safety hypothesis passes only if every endpoint passes. Under an IUT the
composite test holds the nominal level without an alpha correction, because
rejection of the union null requires rejecting each component null.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

ROBOT_RADIUS_M = 0.18
OBSTACLE_RADIUS_M = 0.35
MIN_RR_DISTANCE_M = 0.40
MIN_RO_DISTANCE_M = 0.55
MAX_SPEED_MPS = 0.90
MAX_ACCEL_MPS2 = 0.60

# Physical body contact, strictly inside the clearance gates above.
RR_CONTACT_M = 2.0 * ROBOT_RADIUS_M                    # 0.36
RO_CONTACT_M = ROBOT_RADIUS_M + OBSTACLE_RADIUS_M      # 0.53
# The tightest engineered surface margin anywhere in the frozen configuration.
TIGHTEST_SURFACE_MARGIN_M = MIN_RO_DISTANCE_M - RO_CONTACT_M   # 0.02

# Full braking time from top speed; below this a collision cannot be avoided by
# braking alone, which is what makes it the physically meaningful TTC threshold.
TTC_VIOLATION_THRESHOLD_S = MAX_SPEED_MPS / MAX_ACCEL_MPS2     # 1.5

# Frozen pilot collision gate, results/rvt_fd24/phase9d_h1_requirement_map_v1.json
COLLISION_FREE_POINT_ESTIMATE_MINIMUM = 0.95
COLLISION_ABSOLUTE_DEGRADATION_MAXIMUM = 0.01

CONFIDENCE_LEVEL = 0.95            # one-sided bound per endpoint


class SafetyContractError(ValueError):
    """A safety-contract violation that must fail closed."""


@dataclass(frozen=True)
class SafetyEndpoint:
    key: str
    definition: str
    unit: str
    aggregation_unit: str
    direction_of_harm: str          # "decrease" or "increase"
    margin: float
    margin_justification: str
    role: str                       # "PRIMARY" or "SECONDARY_DIAGNOSTIC"
    absolute_floor: float | None = None


PRIMARY_ENDPOINTS: tuple[SafetyEndpoint, ...] = (
    SafetyEndpoint(
        key="collision_free_rate",
        definition="per-episode indicator that no robot-robot separation fell below "
                   f"{MIN_RR_DISTANCE_M} m and no robot-obstacle separation fell below "
                   f"{MIN_RO_DISTANCE_M} m at any control step; the frozen simulator "
                   "predicate collision_free",
        unit="episode rate in [0, 1]", aggregation_unit="source episode",
        direction_of_harm="decrease", margin=COLLISION_ABSOLUTE_DEGRADATION_MAXIMUM,
        margin_justification="the pilot's frozen collision gate already fixes "
            "absolute_degradation_maximum = 0.01; reused verbatim, not re-derived",
        role="PRIMARY", absolute_floor=COLLISION_FREE_POINT_ESTIMATE_MINIMUM),
    SafetyEndpoint(
        key="minimum_clearance_m",
        definition="per-episode minimum over all control steps and all pairs of "
                   "(separation minus the required clearance for that pair type), "
                   "reported jointly for robot-robot and robot-obstacle",
        unit="meters", aggregation_unit="source episode",
        direction_of_harm="decrease", margin=0.01,
        margin_justification="one half of the tightest engineered surface margin in "
            f"the frozen configuration ({TIGHTEST_SURFACE_MARGIN_M} m = min_ro_distance "
            "0.55 minus physical contact 0.53), so at worst-allowed degradation at "
            "least half of that engineered buffer survives",
        role="PRIMARY"),
    SafetyEndpoint(
        key="ttc_violation_rate",
        definition=f"per-episode fraction of control steps whose minimum pairwise "
                   f"time-to-collision is below {TTC_VIOLATION_THRESHOLD_S} s, computed "
                   "by the frozen rvt_swarm.safety.time_to_collision",
        unit="step fraction in [0, 1]", aggregation_unit="source episode",
        direction_of_harm="increase", margin=0.01,
        margin_justification="the same engineering tolerance class as the frozen "
            "collision gate's absolute_degradation_maximum, applied to a precursor "
            "endpoint; the threshold itself is the physical braking time "
            "max_speed / max_acceleration = 0.9 / 0.6",
        role="PRIMARY"),
    SafetyEndpoint(
        key="severe_near_collision_rate",
        definition="per-episode indicator of actual geometric body overlap: robot-robot "
                   f"separation below {RR_CONTACT_M} m or robot-obstacle separation below "
                   f"{RO_CONTACT_M} m",
        unit="episode rate in [0, 1]", aggregation_unit="source episode",
        direction_of_harm="increase", margin=0.005,
        margin_justification="half the frozen collision-gate margin, because this "
            "endpoint is physical contact and is strictly more severe than a clearance-"
            "gate violation; the margin is monotone in severity",
        role="PRIMARY"),
)

SECONDARY_ENDPOINTS: tuple[SafetyEndpoint, ...] = (
    SafetyEndpoint(
        key="safety_projection_intervention_rate",
        definition="per-episode fraction of control steps at which the local safety "
                   "projection altered the nominal command",
        unit="step fraction in [0, 1]", aggregation_unit="source episode",
        direction_of_harm="increase", margin=float("nan"),
        margin_justification="diagnostic only; it carries no pass/fail rule because a "
            "higher intervention rate is not itself a harm",
        role="SECONDARY_DIAGNOSTIC"),
)


@dataclass(frozen=True)
class EndpointVerdict:
    key: str
    passed: bool
    reason: str


def endpoint_passes(endpoint: SafetyEndpoint, *, point_difference: float,
                    one_sided_bound: float,
                    treatment_point_estimate: float | None = None) -> EndpointVerdict:
    """Non-inferiority for one endpoint.

    ``one_sided_bound`` is the 95 percent bound on (treatment - comparator) on the
    harmful side: the LOWER bound when harm is a decrease, the UPPER bound when
    harm is an increase.
    """
    if endpoint.role != "PRIMARY":
        raise SafetyContractError(f"{endpoint.key} is not a primary endpoint and has no pass rule")
    if endpoint.direction_of_harm == "decrease":
        ok = one_sided_bound > -endpoint.margin
        detail = f"lower95({point_difference:.6g}) = {one_sided_bound:.6g} > -{endpoint.margin}"
    elif endpoint.direction_of_harm == "increase":
        ok = one_sided_bound < endpoint.margin
        detail = f"upper95({point_difference:.6g}) = {one_sided_bound:.6g} < {endpoint.margin}"
    else:
        raise SafetyContractError(f"unknown direction of harm for {endpoint.key}")
    if ok and endpoint.absolute_floor is not None:
        if treatment_point_estimate is None:
            raise SafetyContractError(
                f"{endpoint.key} carries an absolute floor and needs a treatment point estimate")
        if treatment_point_estimate < endpoint.absolute_floor:
            return EndpointVerdict(endpoint.key, False,
                f"non-inferiority held but the absolute floor failed: "
                f"{treatment_point_estimate:.6g} < {endpoint.absolute_floor}")
    return EndpointVerdict(endpoint.key, ok, detail)


def safety_hypothesis_passes(verdicts: Mapping[str, EndpointVerdict]) -> bool:
    """H-CL2. Intersection-union: every primary endpoint must pass."""
    required = {e.key for e in PRIMARY_ENDPOINTS}
    missing = sorted(required - set(verdicts))
    if missing:
        raise SafetyContractError(f"no verdict for primary safety endpoints: {missing}")
    return all(verdicts[k].passed for k in required)


def central_closed_loop_claim(benefit_passes: bool, safety_passes: bool) -> str:
    """The frozen conjunction. Progress without safety is a failure, not a trade."""
    if benefit_passes and safety_passes:
        return "CENTRAL_CLOSED_LOOP_CLAIM_SUPPORTED"
    if benefit_passes and not safety_passes:
        return "CENTRAL_CLAIM_FAILS_SAFETY_NON_INFERIORITY_NOT_MET"
    return "CENTRAL_CLAIM_FAILS_BENEFIT_NOT_DEMONSTRATED"
