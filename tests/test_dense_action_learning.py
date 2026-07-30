"""Repair 6 — the dense action head must be able to learn.

v1 failed closed-loop at 0.000 with action RMSE 0.150 against a target standard
deviation of 0.15 — the head was predicting approximately zero. Before trusting
any closed-loop number we assert the head can actually fit action targets, so
that a future 0.000 is attributable to compounding error rather than to a head
that never learned at all.
"""

from __future__ import annotations

import numpy as np
import pytest
import torch

from rvt_swarm.binary_pilot import (
    MODES, build_action_dataset, collate, compute_pilot_loss,
)
from rvt_swarm.config import Config
from rvt_swarm.models import build_model

METHODS = ("topology_agnostic_gnn", "direct_keep_line_classifier", "rvt_binary_recovery")


@pytest.fixture(scope="module")
def dense():
    cfg = Config()
    cfg.train.device = "cpu"
    cfg.env.scenarios = ["cluttered"]
    return cfg, build_action_dataset(cfg, "train")


def test_dense_dataset_is_large_enough_to_train_an_action_head(dense) -> None:
    """The predeclared range is 2500-4000 states; v1 had 457."""
    _, samples = dense
    assert 2500 <= len(samples) <= 4000, f"{len(samples)} outside the predeclared range"
    assert len(samples) > 5 * 457, "must be materially denser than the starved v1 set"


def test_targets_carry_real_signal(dense) -> None:
    """A head cannot be blamed for failing to fit targets that are all zero."""
    _, samples = dense
    # per-sample node counts differ (N=4 and N=6), so concatenate over nodes
    tgt = np.concatenate([s.action_targets.numpy() for s in samples], axis=0)
    assert tgt.std() > 0.05, "action targets are near-constant"
    # keep and line targets must actually differ, or mode-conditioning is vacuous
    keep, line = tgt[:, 0, :], tgt[:, 1, :]
    assert np.abs(keep - line).mean() > 1e-3, "keep and line targets are identical"


@pytest.mark.parametrize("method", METHODS)
def test_micro_overfit_a_fixed_dense_batch(dense, method: str) -> None:
    """Each method's action head must memorise a small fixed batch.

    This isolates capacity/plumbing from generalisation: if it cannot fit 16
    states it will never work in closed loop, and a closed-loop 0.000 would be
    uninformative.
    """
    cfg, samples = dense
    torch.manual_seed(0)
    batch = collate(samples[:16])
    model = build_model(method, cfg.train.hidden_dim, cfg.train.message_passes)
    opt = torch.optim.Adam(model.parameters(), lr=3e-3)

    def action_loss() -> float:
        model.eval()
        with torch.no_grad():
            return float(compute_pilot_loss(model(batch), batch, method)["action"])

    before = action_loss()
    model.train(True)
    for _ in range(150):
        opt.zero_grad(set_to_none=True)
        loss = compute_pilot_loss(model(batch), batch, method)["action"]
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
    after = action_loss()

    assert after < 0.2 * before, (
        f"{method}: action loss {before:.5f} -> {after:.5f}; the head cannot fit "
        "16 states, so any closed-loop result is uninterpretable"
    )


@pytest.mark.parametrize("method", ("direct_keep_line_classifier", "rvt_binary_recovery"))
def test_both_modes_are_predicted_not_just_keep(dense, method: str) -> None:
    """Mode-conditioned heads must emit distinct keep and line actions."""
    cfg, samples = dense
    torch.manual_seed(0)
    batch = collate(samples[:16])
    model = build_model(method, cfg.train.hidden_dim, cfg.train.message_passes)
    opt = torch.optim.Adam(model.parameters(), lr=3e-3)
    for _ in range(150):
        opt.zero_grad(set_to_none=True)
        compute_pilot_loss(model(batch), batch, method)["action"].backward()
        opt.step()
    model.eval()
    with torch.no_grad():
        pred = model(batch)["actions_by_topology"]
    assert pred.shape[1] == len(MODES)
    gap = float((pred[:, 0, :] - pred[:, 1, :]).abs().mean())
    assert gap > 1e-3, "keep and line predictions collapsed to the same action"


def test_executed_action_head_is_bound_to_the_environment_mode(dense) -> None:
    """The head that produces the action must match the mode given to env.step.

    infer_learned_action() selects the head by its own argmax. That agrees with
    the chosen mode on the end-to-end path, but a forced-mode probe would
    otherwise execute line actions while telling the environment "keep".
    """
    from rvt_swarm.binary_pilot import learned_action_for_mode
    from rvt_swarm.environment import SwarmFormationEnv
    from rvt_swarm.layouts import build_layouts

    cfg, _ = dense
    torch.manual_seed(0)
    model = build_model("rvt_binary_recovery", cfg.train.hidden_dim, cfg.train.message_passes)
    lay = [l for l in build_layouts("val") if l.family == "line_corridor"][0]
    obs = SwarmFormationEnv(cfg).reset(4, "cluttered", seed=20000001, layout=lay)

    a_keep = learned_action_for_mode(model, obs, cfg, "rvt_binary_recovery", 0)
    a_line = learned_action_for_mode(model, obs, cfg, "rvt_binary_recovery", 2)
    assert not np.allclose(a_keep, a_line), "forcing the mode did not change the head"
    assert np.abs(a_keep).max() <= cfg.env.max_accel + 1e-6, "actions exceed max_accel"
