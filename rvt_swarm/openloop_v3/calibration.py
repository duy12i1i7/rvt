"""Frozen calibration diagnostics for fractional (k, R) supervision.

Everything here is a DIAGNOSTIC. None of it selects a model, breaks a tie, or
modifies a prediction; the frozen family-selection rule reads only the NLL and
its bootstrap interval.

The observation pairs are robot-level ``(q, k/R)`` with weight
``1 / (2 * N_e * E)``, which reproduces the frozen loss weighting exactly rather
than approximating it with a candidate-level average.

The intercept/slope fit is the standard Cox calibration regression generalized
to fractional targets: minimize the SAME frozen grouped-Bernoulli objective over
an affine map of the logit. Perfect calibration is (a, b) = (0, 1), and at R = 1
the fractional targets become {0, 1} and this degenerates to ordinary Cox
calibration.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence, Tuple

import torch

ECE_BIN_COUNT = 10
ECE_BIN_EDGES: Tuple[float, ...] = tuple(index / 10.0 for index in range(11))


class CalibrationContractError(ValueError):
    """A calibration-contract violation that must fail closed."""


@dataclass(frozen=True)
class ReliabilityBin:
    index: int
    lower: float
    upper: float
    right_closed: bool
    weight: float
    mean_probability: float
    mean_target: float
    empty: bool


@dataclass(frozen=True)
class CalibrationReport:
    bins: Tuple[ReliabilityBin, ...]
    expected_calibration_error: float
    empty_bins: int
    intercept: float
    slope: float
    total_weight: float


def _check(probabilities: torch.Tensor, targets: torch.Tensor,
           weights: torch.Tensor) -> None:
    if not (probabilities.ndim == targets.ndim == weights.ndim == 1):
        raise CalibrationContractError("calibration inputs must be one-dimensional")
    if not (probabilities.numel() == targets.numel() == weights.numel()):
        raise CalibrationContractError("calibration inputs must align")
    if probabilities.numel() == 0:
        raise CalibrationContractError("calibration requires at least one observation")
    if bool((probabilities < 0.0).any()) or bool((probabilities > 1.0).any()):
        raise CalibrationContractError("probabilities must lie in [0, 1]")
    if bool((targets < 0.0).any()) or bool((targets > 1.0).any()):
        raise CalibrationContractError("targets must lie in [0, 1]")
    if bool((weights < 0.0).any()) or float(weights.sum()) <= 0.0:
        raise CalibrationContractError("weights must be nonnegative and sum positive")


def bin_index(probability: float) -> int:
    """Ten fixed bins, [b, b+0.1), with the final bin closed on the right."""
    if not 0.0 <= probability <= 1.0:
        raise CalibrationContractError("probability outside [0, 1]")
    if probability >= 1.0:
        return ECE_BIN_COUNT - 1
    return min(ECE_BIN_COUNT - 1, int(math.floor(probability * ECE_BIN_COUNT)))


def reliability_and_ece(probabilities: torch.Tensor, targets: torch.Tensor,
                        weights: torch.Tensor,
                        ) -> Tuple[Tuple[ReliabilityBin, ...], float, int]:
    _check(probabilities, targets, weights)
    total = float(weights.sum())
    bins = []
    ece = 0.0
    empty = 0
    assignment = torch.tensor(
        [bin_index(float(value)) for value in probabilities], dtype=torch.int64)
    for index in range(ECE_BIN_COUNT):
        selected = assignment == index
        bin_weight = float(weights[selected].sum()) if bool(selected.any()) else 0.0
        if bin_weight <= 0.0:
            empty += 1
            bins.append(ReliabilityBin(
                index=index, lower=ECE_BIN_EDGES[index], upper=ECE_BIN_EDGES[index + 1],
                right_closed=index == ECE_BIN_COUNT - 1, weight=0.0,
                mean_probability=float("nan"), mean_target=float("nan"), empty=True))
            continue                                  # empty bins contribute exactly 0
        w = weights[selected]
        mean_probability = float((w * probabilities[selected]).sum() / bin_weight)
        mean_target = float((w * targets[selected]).sum() / bin_weight)
        ece += (bin_weight / total) * abs(mean_probability - mean_target)
        bins.append(ReliabilityBin(
            index=index, lower=ECE_BIN_EDGES[index], upper=ECE_BIN_EDGES[index + 1],
            right_closed=index == ECE_BIN_COUNT - 1, weight=bin_weight,
            mean_probability=mean_probability, mean_target=mean_target, empty=False))
    return tuple(bins), ece, empty


def calibration_intercept_slope(logits: torch.Tensor, targets: torch.Tensor,
                                weights: torch.Tensor, *, iterations: int = 100,
                                tolerance: float = 1e-12) -> Tuple[float, float]:
    """Newton's method on the weighted fractional-target logistic objective.

    The objective is convex in (a, b) and its gradient and Hessian are closed
    form, so a fixed-iteration Newton solve is exact to machine precision and
    fully deterministic -- no line search, no optimizer state, no seed.
    """
    if logits.ndim != 1:
        raise CalibrationContractError("logits must be one-dimensional")
    probabilities = torch.sigmoid(logits.double())
    _check(probabilities.to(torch.float32), targets, weights)
    z = logits.double()
    t = targets.double()
    w = weights.double()
    a = torch.tensor(0.0, dtype=torch.float64)
    b = torch.tensor(1.0, dtype=torch.float64)
    for _ in range(iterations):
        p = torch.sigmoid(a + b * z)
        residual = w * (p - t)
        gradient = torch.stack([residual.sum(), (residual * z).sum()])
        variance = w * p * (1.0 - p)
        h11 = variance.sum()
        h12 = (variance * z).sum()
        h22 = (variance * z * z).sum()
        determinant = h11 * h22 - h12 * h12
        if float(torch.abs(determinant)) < 1e-30:
            raise CalibrationContractError(
                "the calibration Hessian is singular; the logits carry no spread")
        step_a = (h22 * gradient[0] - h12 * gradient[1]) / determinant
        step_b = (-h12 * gradient[0] + h11 * gradient[1]) / determinant
        a = a - step_a
        b = b - step_b
        if float(torch.abs(step_a)) < tolerance and float(torch.abs(step_b)) < tolerance:
            break
    return float(a), float(b)


def calibration_report(logits: torch.Tensor, targets: torch.Tensor,
                       weights: torch.Tensor) -> CalibrationReport:
    probabilities = torch.sigmoid(logits)
    bins, ece, empty = reliability_and_ece(probabilities, targets, weights)
    intercept, slope = calibration_intercept_slope(logits, targets, weights)
    return CalibrationReport(bins=bins, expected_calibration_error=ece,
                             empty_bins=empty, intercept=intercept, slope=slope,
                             total_weight=float(weights.sum()))


def event_equal_observation_weights(team_sizes: Sequence[int]) -> torch.Tensor:
    """Weight 1 / (2 * N_e * E) per robot-level observation, twice per event."""
    events = len(team_sizes)
    if events == 0:
        raise CalibrationContractError("at least one event is required")
    weights = []
    for team_size in team_sizes:
        if team_size < 1:
            raise CalibrationContractError("team size must be positive")
        weights.extend([1.0 / (2.0 * team_size * events)] * (2 * team_size))
    return torch.tensor(weights, dtype=torch.float32)
