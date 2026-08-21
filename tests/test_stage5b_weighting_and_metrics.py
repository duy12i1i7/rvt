"""Frozen event-equal weighting, the Brier anchor, and calibration diagnostics."""

import math

import pytest
import torch

from rvt_swarm.fd24 import loss_v3, metrics_v3
from rvt_swarm.openloop_v3.calibration import (
    CalibrationContractError, ECE_BIN_COUNT, bin_index,
    calibration_intercept_slope, calibration_report,
    event_equal_observation_weights, reliability_and_ece,
)


def _event(team_size, k, R, logit=0.0):
    logits = torch.full((team_size,), float(logit))
    return {"compact_logits": logits, "compact_k": k, "compact_R": R,
            "line_logits": logits, "line_k": k, "line_R": R}


@pytest.mark.parametrize("team_size,k,R", [(5, 1, 1), (16, 1, 1), (5, 1, 3), (16, 1, 3)])
def test_one_event_weighs_exactly_one_whatever_n_and_r(team_size, k, R):
    """W(N=5,R=1) = W(N=16,R=1) = W(N=5,R=3) = W(N=16,R=3).

    The per-replica NLL of a constant p against (k, R) does not depend on N, and
    dividing by R makes it the MEAN per-replica likelihood, so the four cells
    that share a (k/R) ratio must agree exactly.
    """
    value = float(loss_v3.dataset_loss([_event(team_size, k, R)]))
    reference = -(k * math.log(0.5) + (R - k) * math.log(0.5)) / R
    assert value == pytest.approx(reference, rel=0.0, abs=1e-6)


def test_the_four_weighting_cells_agree_when_k_over_r_agrees():
    a = float(loss_v3.dataset_loss([_event(5, 1, 3)]))
    b = float(loss_v3.dataset_loss([_event(16, 1, 3)]))
    assert a == pytest.approx(b, abs=1e-7)
    c = float(loss_v3.dataset_loss([_event(5, 1, 1)]))
    d = float(loss_v3.dataset_loss([_event(16, 1, 1)]))
    assert c == pytest.approx(d, abs=1e-7)


def test_a_large_event_does_not_outweigh_a_small_one():
    small = _event(5, 1, 1, logit=2.0)
    large = _event(16, 0, 1, logit=2.0)
    mixed = float(loss_v3.dataset_loss([small, large]))
    swapped = float(loss_v3.dataset_loss([large, small]))
    average = 0.5 * (float(loss_v3.dataset_loss([small]))
                     + float(loss_v3.dataset_loss([large])))
    assert mixed == pytest.approx(average, abs=1e-6)
    assert mixed == pytest.approx(swapped, abs=1e-7)


def test_r3_does_not_receive_three_times_the_weight():
    deterministic = _event(5, 1, 1, logit=0.4)
    stochastic = _event(5, 3, 3, logit=0.4)
    assert float(loss_v3.dataset_loss([deterministic])) == pytest.approx(
        float(loss_v3.dataset_loss([stochastic])), abs=1e-6)


def test_brier_anchor_is_one_quarter_not_the_shortcut():
    probability = torch.tensor([0.5])
    value = float(metrics_v3.brier_robot(probability, k=1, R=3))
    assert value == pytest.approx(0.25, abs=1e-12)
    shortcut = (0.5 - 1.0 / 3.0) ** 2
    assert shortcut == pytest.approx(0.0277777777, abs=1e-6)
    assert abs(value - shortcut) > 0.2


def test_brier_matches_the_replica_definition():
    probability = torch.tensor([0.37])
    for outcomes in ([1, 0, 0], [1, 1, 0], [0], [1]):
        k = sum(outcomes)
        direct = float(metrics_v3.brier_robot(probability, k=k, R=len(outcomes)))
        literal = float(metrics_v3.brier_from_replica_outcomes(probability, outcomes))
        assert direct == pytest.approx(literal, abs=1e-6)


def test_brier_split_is_event_equal():
    def event(team_size, k, R):
        p = torch.full((team_size,), 0.5)
        return {"compact_probabilities": p, "compact_k": k, "compact_R": R,
                "line_probabilities": p, "line_k": k, "line_R": R}
    assert float(metrics_v3.brier_split([event(5, 1, 3)])) == pytest.approx(
        float(metrics_v3.brier_split([event(16, 1, 3)])), abs=1e-7)


# ------------------------------------------------------------- calibration
def test_bin_boundaries_are_the_frozen_ten_with_the_last_right_closed():
    assert ECE_BIN_COUNT == 10
    assert bin_index(0.0) == 0
    assert bin_index(0.0999) == 0
    assert bin_index(0.1) == 1
    assert bin_index(0.8999) == 8
    assert bin_index(0.9) == 9
    assert bin_index(1.0) == 9                      # final bin closed on the right


def test_empty_bins_are_reported_and_contribute_zero():
    probabilities = torch.tensor([0.05, 0.05, 0.95])
    targets = torch.tensor([0.0, 0.0, 1.0])
    weights = torch.tensor([1.0, 1.0, 1.0])
    bins, ece, empty = reliability_and_ece(probabilities, targets, weights)
    assert len(bins) == 10 and empty == 8
    assert sum(1 for item in bins if item.empty) == 8
    assert ece == pytest.approx(0.05, abs=1e-6)


def test_perfect_calibration_gives_intercept_zero_and_slope_one():
    logits = torch.tensor([-2.0, -1.0, 0.0, 1.0, 2.0])
    targets = torch.sigmoid(logits)
    weights = torch.ones(5)
    intercept, slope = calibration_intercept_slope(logits, targets, weights)
    # targets come from a float32 sigmoid, so agreement is to float32 precision
    assert intercept == pytest.approx(0.0, abs=1e-6)
    assert slope == pytest.approx(1.0, abs=1e-6)


def test_a_scaled_logit_recovers_the_scale():
    logits = torch.tensor([-2.0, -1.0, 0.0, 1.0, 2.0])
    targets = torch.sigmoid(2.0 * logits)
    intercept, slope = calibration_intercept_slope(logits, targets, torch.ones(5))
    assert slope == pytest.approx(2.0, abs=1e-6)
    assert intercept == pytest.approx(0.0, abs=1e-6)


def test_calibration_works_with_fractional_targets():
    logits = torch.tensor([-1.0, 0.0, 1.0, 2.0])
    targets = torch.tensor([0.0, 1.0 / 3.0, 2.0 / 3.0, 1.0])
    report = calibration_report(logits, targets, torch.ones(4))
    assert math.isfinite(report.intercept) and math.isfinite(report.slope)
    assert 0.0 <= report.expected_calibration_error <= 1.0


def test_event_equal_observation_weights_sum_to_one():
    weights = event_equal_observation_weights([5, 16, 5])
    assert float(weights.sum()) == pytest.approx(1.0, abs=1e-6)
    assert weights.numel() == 2 * (5 + 16 + 5)
    # every event contributes exactly 1/E regardless of N
    assert float(weights[:10].sum()) == pytest.approx(1.0 / 3.0, abs=1e-6)
    assert float(weights[10:42].sum()) == pytest.approx(1.0 / 3.0, abs=1e-6)


def test_calibration_refuses_degenerate_input():
    with pytest.raises(CalibrationContractError):
        reliability_and_ece(torch.tensor([1.5]), torch.tensor([0.0]), torch.tensor([1.0]))
    with pytest.raises(CalibrationContractError):
        reliability_and_ece(torch.tensor([0.5]), torch.tensor([0.0]), torch.tensor([0.0]))
