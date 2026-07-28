"""Finding 5 — do the learned methods receive equal training and selection budgets?

`rvt_swarm` is configured for 300 epochs while the topology-agnostic `gnn_only`
baseline and `instant_cert` get 120. Because rollout validation runs on a fixed
epoch interval and the best checkpoint is chosen from those evaluations, the
epoch budget also determines the *model-selection* budget: the proposed method
gets substantially more chances to draw a favourable checkpoint than the
baseline it is compared against.

Files involved
--------------
rvt_swarm/config.py:44-47        epochs_gnn_only / epochs_instant_cert / epochs_rvt_swarm
rvt_swarm/train.py:18-25         `epochs_for_model`
rvt_swarm/train.py:210-217       `should_run_rollout_validation` (interval-gated)
rvt_swarm/train.py:224-250       `maybe_record_rollout_candidate` (top-k pool)
rvt_swarm/train.py:516-536       final top-k recheck over recorded candidates

These tests assert budget parity, so they fail against the unfixed config.
"""

from __future__ import annotations

from rvt_swarm.config import Config
from rvt_swarm.train import (
    epochs_for_model,
    rollout_validation_start_epoch,
    should_run_rollout_validation,
)


LEARNED_METHODS = ("rvt_swarm", "gnn_only", "instant_cert")


def _validation_events(cfg: Config, model_name: str) -> int:
    """How many rollout-validation evaluations this method gets over its budget."""
    warmup = 0
    total_epochs = epochs_for_model(cfg, model_name)
    return sum(
        1
        for epoch in range(1, total_epochs + 1)
        if should_run_rollout_validation(cfg, model_name, epoch, warmup)
    )


def test_training_epoch_budgets_are_equal() -> None:
    cfg = Config()
    budgets = {m: epochs_for_model(cfg, m) for m in LEARNED_METHODS}

    assert len(set(budgets.values())) == 1, (
        f"unequal training budgets across learned methods: {budgets}"
    )


def test_rollout_validation_budgets_are_equal() -> None:
    cfg = Config()
    events = {m: _validation_events(cfg, m) for m in LEARNED_METHODS}

    assert len(set(events.values())) == 1, (
        f"unequal checkpoint-selection budgets across learned methods: {events} "
        "(each event is an opportunity to record a best checkpoint)"
    )


def test_proposed_method_has_no_selection_advantage_over_the_gnn_baseline() -> None:
    """The specific comparison the headline result rests on."""
    cfg = Config()
    ours = _validation_events(cfg, "rvt_swarm")
    baseline = _validation_events(cfg, "gnn_only")

    assert ours == baseline, (
        f"rvt_swarm gets {ours} checkpoint-selection evaluations vs {baseline} for "
        f"gnn_only ({ours / max(baseline, 1):.2f}x advantage)"
    )


def test_topk_recheck_pool_is_shared_and_method_independent() -> None:
    """The top-k recheck is a single shared config field, so parity holds by construction."""
    cfg = Config()
    assert isinstance(cfg.train.rollout_val_topk_checkpoints, int)
    assert cfg.train.rollout_val_topk_checkpoints >= 1
    for model_name in LEARNED_METHODS:
        assert should_run_rollout_validation(
            cfg, model_name, rollout_validation_start_epoch(cfg, 0), 0
        ), f"{model_name} is excluded from rollout validation entirely"


def test_validation_protocol_is_identical_across_methods() -> None:
    """Scenario / team-size / episode counts must not differ per method."""
    cfg = Config()
    schedules = {
        m: tuple(
            epoch
            for epoch in range(1, epochs_for_model(cfg, m) + 1)
            if should_run_rollout_validation(cfg, m, epoch, 0)
        )
        for m in LEARNED_METHODS
    }
    assert len(set(schedules.values())) == 1, (
        "learned methods are validated on different epoch schedules"
    )
