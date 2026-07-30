"""Repairs 1 and 2 — decisive-state metrics and the masked classifier target.

The v1 defect: argmax over [keep, line] resolved ties to keep, so an always-keep
predictor scored 0.854 and the degenerate classifier looked twice as good as the
model that learned the signal. These tests make that defect unable to return.
"""

from __future__ import annotations

import math

import numpy as np
import pytest
import torch

from rvt_swarm.binary_pilot import (
    classify_states,
    decisive_mode_metrics,
    recovery_loss,
)

KEEP_ONLY = [1.0, 0.0]
LINE_ONLY = [0.0, 1.0]
BOTH_OK = [1.0, 1.0]
BOTH_FAIL = [0.0, 0.0]
PRED_KEEP = [0.9, 0.1]
PRED_LINE = [0.1, 0.9]


def test_state_classification_is_exhaustive_and_disjoint() -> None:
    L = np.array([KEEP_ONLY, LINE_ONLY, BOTH_OK, BOTH_FAIL])
    c = classify_states(L)
    assert c["keep_only"].tolist() == [True, False, False, False]
    assert c["line_only"].tolist() == [False, True, False, False]
    assert c["both_succeed"].tolist() == [False, False, True, False]
    assert c["both_fail"].tolist() == [False, False, False, True]
    assert c["decisive"].tolist() == [True, True, False, False]
    total = sum(c[k].sum() for k in ("keep_only", "line_only", "both_succeed", "both_fail"))
    assert total == len(L)


# --------------------------------------------------------------------------
# 1 & 2 — non-decisive states are never scored as correct keep decisions
# --------------------------------------------------------------------------
def test_both_succeed_is_not_scored_as_a_correct_keep_decision() -> None:
    m = decisive_mode_metrics(np.array([PRED_KEEP]), np.array([BOTH_OK]))
    assert m["n_decisive"] == 0
    assert math.isnan(m["decisive_accuracy"]), "a both-succeed state must not be scored"


def test_both_fail_is_not_scored_as_a_correct_keep_decision() -> None:
    m = decisive_mode_metrics(np.array([PRED_KEEP]), np.array([BOTH_FAIL]))
    assert m["n_decisive"] == 0
    assert math.isnan(m["decisive_accuracy"])


def test_only_decisive_states_contribute() -> None:
    """Adding non-decisive states must not move decisive accuracy."""
    P = np.array([PRED_KEEP, PRED_LINE])
    L = np.array([KEEP_ONLY, LINE_ONLY])
    base = decisive_mode_metrics(P, L)
    assert base["decisive_accuracy"] == 1.0 and base["n_decisive"] == 2

    P2 = np.array([PRED_KEEP, PRED_LINE, PRED_KEEP, PRED_LINE, PRED_KEEP])
    L2 = np.array([KEEP_ONLY, LINE_ONLY, BOTH_OK, BOTH_FAIL, BOTH_OK])
    pad = decisive_mode_metrics(P2, L2)
    assert pad["decisive_accuracy"] == base["decisive_accuracy"]
    assert pad["n_decisive"] == 2
    assert pad["decisive_coverage"] == pytest.approx(2 / 5)
    assert pad["both_succeed_prevalence"] == pytest.approx(2 / 5)
    assert pad["both_fail_prevalence"] == pytest.approx(1 / 5)


# --------------------------------------------------------------------------
# 4 — ordering invariance
# --------------------------------------------------------------------------
def test_metric_is_invariant_to_candidate_ordering() -> None:
    rng = np.random.default_rng(0)
    L = np.array([KEEP_ONLY, LINE_ONLY, LINE_ONLY, BOTH_OK, BOTH_FAIL, KEEP_ONLY])
    P = rng.random((len(L), 2))
    a = decisive_mode_metrics(P, L)
    b = decisive_mode_metrics(P[:, ::-1].copy(), L[:, ::-1].copy())
    assert a["decisive_accuracy"] == pytest.approx(b["decisive_accuracy"])
    assert a["decisive_balanced_accuracy"] == pytest.approx(b["decisive_balanced_accuracy"])
    # keep and line recalls swap roles under reordering
    assert a["decisive_keep_recall"] == pytest.approx(b["decisive_line_recall"])
    assert a["decisive_line_recall"] == pytest.approx(b["decisive_keep_recall"])


def test_exact_prediction_ties_score_half_and_are_counted() -> None:
    m = decisive_mode_metrics(np.array([[0.5, 0.5], [0.5, 0.5]]),
                              np.array([KEEP_ONLY, LINE_ONLY]))
    assert m["decisive_accuracy"] == pytest.approx(0.5)
    assert m["n_prediction_ties"] == 2


# --------------------------------------------------------------------------
# 5 — the v1 defect reproduced as a guard
# --------------------------------------------------------------------------
def test_always_keep_scores_exactly_the_keep_only_share() -> None:
    """The reference policies must make a degenerate predictor obvious."""
    L = np.array([KEEP_ONLY] + [LINE_ONLY] * 3 + [BOTH_OK] * 6)
    P = np.tile(np.array([PRED_KEEP]), (len(L), 1))
    m = decisive_mode_metrics(P, L)
    assert m["decisive_accuracy"] == pytest.approx(0.25)      # 1 of 4 decisive
    assert m["always_keep_accuracy"] == pytest.approx(0.25)
    assert m["always_line_accuracy"] == pytest.approx(0.75)
    assert m["majority_class_accuracy"] == pytest.approx(0.75)
    assert m["decisive_accuracy"] <= m["majority_class_accuracy"], (
        "an always-keep predictor must not beat the majority-class reference"
    )


def test_legacy_degenerate_metric_is_retained_only_under_a_warning_name() -> None:
    from rvt_swarm.binary_pilot import prediction_metrics

    L = np.array([BOTH_OK] * 8 + [LINE_ONLY] * 2)
    P = np.tile(np.array([PRED_KEEP]), (len(L), 1))
    m = prediction_metrics(P, L)
    assert "top1_mode_accuracy" not in m, "the degenerate name must not be reported"
    assert m["top1_mode_accuracy_LEGACY_DEGENERATE"] == pytest.approx(0.8)
    assert m["decisive_accuracy"] == pytest.approx(0.0), (
        "on the decisive subset the always-keep predictor is simply wrong"
    )


# --------------------------------------------------------------------------
# Repair 2 — masked classifier loss
# --------------------------------------------------------------------------
def _cls_out(n, logits=None):
    return {"class_logits": torch.zeros(n, 2) if logits is None else logits}


def test_ambiguous_states_contribute_zero_classifier_loss() -> None:
    batch = {"recovery_labels": torch.tensor([BOTH_OK, BOTH_FAIL, BOTH_OK]),
             "node_x": torch.zeros(3, 4)}
    loss = recovery_loss(_cls_out(3), batch, "direct_keep_line_classifier")
    assert float(loss) == 0.0, "non-decisive-only batch must give exactly zero"
    assert torch.isfinite(loss), "must not be NaN or Inf"


def test_classifier_loss_uses_only_decisive_states() -> None:
    logits = torch.tensor([[5.0, -5.0], [-5.0, 5.0], [5.0, -5.0], [5.0, -5.0]])
    # keep_only + line_only both predicted correctly; the two non-decisive rows
    # are predicted "keep" and must not change the loss.
    decisive_only = {"recovery_labels": torch.tensor([KEEP_ONLY, LINE_ONLY]),
                     "node_x": torch.zeros(2, 4)}
    with_padding = {"recovery_labels": torch.tensor([KEEP_ONLY, LINE_ONLY, BOTH_OK, BOTH_FAIL]),
                    "node_x": torch.zeros(4, 4)}
    a = recovery_loss({"class_logits": logits[:2]}, decisive_only, "direct_keep_line_classifier")
    b = recovery_loss({"class_logits": logits}, with_padding, "direct_keep_line_classifier")
    assert float(a) == pytest.approx(float(b), abs=1e-6)


def test_classifier_target_is_never_an_arbitrary_tie_break() -> None:
    """A model that always predicts keep must be penalised on line_only states."""
    always_keep_logits = torch.tensor([[5.0, -5.0], [5.0, -5.0]])
    batch = {"recovery_labels": torch.tensor([LINE_ONLY, LINE_ONLY]),
             "node_x": torch.zeros(2, 4)}
    loss = recovery_loss({"class_logits": always_keep_logits}, batch,
                         "direct_keep_line_classifier")
    assert float(loss) > 1.0, "always-keep must incur a large loss on line_only states"


def test_recovery_model_bce_uses_both_heads_on_all_states() -> None:
    """BCE is a proper scoring rule over both labels; it is NOT masked."""
    out = {"recovery_logits": torch.zeros(3, 2)}
    batch = {"recovery_labels": torch.tensor([BOTH_OK, BOTH_FAIL, LINE_ONLY]),
             "node_x": torch.zeros(3, 4)}
    loss = recovery_loss(out, batch, "rvt_binary_recovery")
    assert float(loss) == pytest.approx(math.log(2), abs=1e-5)
