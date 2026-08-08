"""UTILITY-1..16 -- the frozen V2 utility reducers.

These four pure functions define how the four scalar values consumed by the
**unchanged** V1 selector are produced. They are reducers over an already
executed counterfactual trace: nothing here snapshots, rolls out, enumerates
candidates or calls the selector, so this module is not the RB-15 producer.

Every normalizer is read from the authoritative configuration inside the
function rather than accepted as an argument, so a caller cannot substitute a
scale. No numeric normalizer is written in this file.

Frozen information classes (UTILITY-16):

    normalized_progress          OFFLINE_LABEL_ORACLE
    normalized_clearance_margin  OFFLINE_LABEL_ORACLE
    normalized_formation_error   OFFLINE_LABEL_ORACLE
    normalized_action_deviation  LOCAL_ACTION_INFORMATION
"""

from __future__ import annotations

import math
from typing import Mapping, Sequence, Tuple

from ..fd24.configuration import FD24ModelConfig, residual_action_limits
from ..runtime_configuration import RuntimeConfig

Vec2 = Tuple[float, float]

RESIDUAL_UTILITY_V2_SCHEMA_VERSION = "rvt-residual-utility/v2"

LOCAL_ACTION_INFORMATION = "LOCAL_ACTION_INFORMATION"
OFFLINE_LABEL_ORACLE = "OFFLINE_LABEL_ORACLE"

UTILITY_INFORMATION_CLASS: Mapping[str, str] = {
    "normalized_progress": OFFLINE_LABEL_ORACLE,
    "normalized_clearance_margin": OFFLINE_LABEL_ORACLE,
    "normalized_formation_error": OFFLINE_LABEL_ORACLE,
    "normalized_action_deviation": LOCAL_ACTION_INFORMATION,
}


class ResidualUtilityError(ValueError):
    """A trace that the frozen reducers cannot score without inventing a value."""


def _finite(values: Sequence[float], name: str) -> None:
    if not all(math.isfinite(float(value)) for value in values):
        raise ResidualUtilityError(f"{name} must be finite")


def normalized_progress(progress_meters: Sequence[float],
                        runtime_config: RuntimeConfig) -> float:
    """UTILITY-2/3 -- signed mean per-control-interval progress increment.

    `progress_meters` is `p_0 ... p_K`: the longitudinal progress at the
    snapshot instant followed by its value after each executed control
    interval. There is no clipping, no absolute value and no maximum: a
    counterfactual that loses ground scores negative, which is the point.

    `K == 0` raises rather than defaulting. It cannot arise on the authoritative
    path -- a dense row exists only where the controller produced an action, and
    the frozen `step()` returns immediately once an episode has terminated, so
    restoring such an instant always executes at least one interval.
    """
    values = [float(value) for value in progress_meters]
    _finite(values, "progress")
    intervals = len(values) - 1
    if intervals < 1:
        raise ResidualUtilityError(
            "the counterfactual executed no control interval; K == 0 has no "
            "frozen reduction and no fallback denominator is permitted")
    spacing = float(runtime_config.formation.nominal_spacing_meters)
    total = sum((values[k + 1] - values[k]) / spacing for k in range(intervals))
    return total / intervals


def clearance_slack(distance_meters: float, minimum_admissible_meters: float) -> float:
    """UTILITY-4 -- one signed normalized safety slack.

    Positive is above the frozen physical threshold, zero is exactly at it and
    negative is a violation. Nothing is clipped.
    """
    threshold = float(minimum_admissible_meters)
    if not math.isfinite(threshold) or threshold <= 0.0:
        raise ResidualUtilityError("a clearance threshold must be finite and positive")
    distance = float(distance_meters)
    if not math.isfinite(distance):
        raise ResidualUtilityError("a clearance distance must be finite")
    return (distance - threshold) / threshold


def normalized_clearance_margin(
    per_interval_constraints: Sequence[Sequence[Tuple[float, float]]],
) -> float:
    """UTILITY-4 -- worst signed normalized slack over the counterfactual.

    `per_interval_constraints[t]` is the applicable `(distance, threshold)`
    pairs at trace sample `t`, covering every robot-robot pair and every
    robot-obstacle relation. The reduction is `min over t of min over
    constraints`.

    An empty constraint set raises. On the authoritative path it cannot occur:
    the smallest qualified team size is 5, so at least ten robot-robot pairs
    are always applicable regardless of geometry.
    """
    if not per_interval_constraints:
        raise ResidualUtilityError("the counterfactual trace is empty")
    worst = math.inf
    for index, constraints in enumerate(per_interval_constraints):
        if not constraints:
            raise ResidualUtilityError(
                f"trace sample {index} has an empty applicable clearance set; no "
                "sentinel, fallback radius or synthetic obstacle is permitted")
        for distance, threshold in constraints:
            worst = min(worst, clearance_slack(distance, threshold))
    return worst


def normalized_formation_error(errors_meters: Sequence[Vec2],
                               runtime_config: RuntimeConfig) -> float:
    """UTILITY-9/10/11 -- RMS Euclidean formation error over the trace.

    `errors_meters` is the per-robot formation-error 2-vector at each trace
    sample. The scalarization is the Euclidean norm and the temporal reduction
    is the root mean square, normalized by the frozen geometric scale of the
    formation.

    `M` follows the frozen runtime's own trace convention: every per-step
    statistic in `SimulatorEpisodeSession.step` -- collision truth, progress,
    Metric V3 dwell, deadlock and goal dwell -- is evaluated *after* the
    integration, so the samples are the post-step states and the pre-step
    snapshot state is excluded. `M == K`.
    """
    samples = [(float(error[0]), float(error[1])) for error in errors_meters]
    if not samples:
        raise ResidualUtilityError("formation RMS needs at least one trace sample")
    _finite([component for sample in samples for component in sample], "formation error")
    spacing = float(runtime_config.formation.nominal_spacing_meters)
    mean_square = sum(x * x + y * y for x, y in samples) / len(samples)
    return math.sqrt(mean_square) / spacing


def normalized_action_deviation(delta_u_world: Vec2,
                                model_config: FD24ModelConfig,
                                runtime_config: RuntimeConfig) -> float:
    """UTILITY-13 -- Euclidean residual magnitude over the Euclidean bound norm.

    Both norms are Euclidean and the denominator is the norm of the full bound
    vector, so an axis-edge candidate and a corner candidate are distinguished.
    No constant is written here: the bound comes from
    `residual_action_limits`.
    """
    delta = (float(delta_u_world[0]), float(delta_u_world[1]))
    _finite(delta, "residual")
    limits = residual_action_limits(model_config, runtime_config)
    if len(limits) != 2:
        raise ResidualUtilityError("the residual bound must have two components")
    bound_norm = math.hypot(float(limits[0]), float(limits[1]))
    if not math.isfinite(bound_norm) or bound_norm <= 0.0:
        raise ResidualUtilityError("the residual bound norm must be finite and positive")
    return math.hypot(*delta) / bound_norm
