"""The clean-room calibration contract.

Calibration is a secondary diagnostic and selects nothing. The pilot programme
wrapped the frozen estimator in a broad ``except CalibrationContractError`` and
reinterpreted whatever it caught as non-identifiability, which disarmed a
fail-closed guard across every family and wrote an unverified explanation into a
sealed record. Here identifiability is TESTED FIRST and explicitly; every other
contract violation propagates and hard-fails.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import torch

from rvt_swarm.openloop_v3.calibration import (
    calibration_intercept_slope, reliability_and_ece,
)

MINIMUM_DISTINCT_LOGITS_FOR_IDENTIFIABILITY = 2

# Prospectively frozen: temperature scaling is NOT activated anywhere in the
# clean-room programme, and no stage may activate it.
TEMPERATURE_SCALING_ACTIVATED = False


@dataclass(frozen=True)
class CleanRoomCalibration:
    identifiable: bool
    intercept: Optional[float]
    slope: Optional[float]
    distinct_logits: int
    expected_calibration_error: float
    empty_bins: int
    bins: tuple


def clean_room_calibration(logits: torch.Tensor, targets: torch.Tensor,
                           weights: torch.Tensor) -> CleanRoomCalibration:
    """Reliability, ECE, and the intercept/slope when they are identifiable.

    A predictor with fewer than two distinct logits has no spread to regress the
    outcome against: the frozen objective depends on (a, b) only through a + b z,
    so the argmin is a whole line and the pair is undefined. That case is
    recognised BEFORE the estimator is called, never by catching its failure.
    """
    if logits.ndim != 1:
        raise ValueError("clean-room calibration expects one-dimensional logits")
    distinct = int(torch.unique(logits).numel())
    bins, ece, empty = reliability_and_ece(torch.sigmoid(logits), targets, weights)
    if distinct < MINIMUM_DISTINCT_LOGITS_FOR_IDENTIFIABILITY:
        return CleanRoomCalibration(
            identifiable=False, intercept=None, slope=None, distinct_logits=distinct,
            expected_calibration_error=ece, empty_bins=empty, bins=tuple(bins))
    # No try/except here on purpose: any remaining contract violation is a real
    # data-integrity failure and must fail closed rather than be relabelled.
    intercept, slope = calibration_intercept_slope(logits, targets, weights)
    return CleanRoomCalibration(
        identifiable=True, intercept=float(intercept), slope=float(slope),
        distinct_logits=distinct, expected_calibration_error=ece,
        empty_bins=empty, bins=tuple(bins))
