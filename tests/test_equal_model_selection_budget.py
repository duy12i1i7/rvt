"""Task 5 — every learned method receives an identical training and selection budget.

Supersedes tests/test_training_budget.py (kept for the historical epoch check) by
asserting parity across every dimension of the budget, not just epochs.
"""

from __future__ import annotations

import json

import pytest

from rvt_swarm.config import Config
from rvt_swarm.train import LEARNED_METHOD_NAMES, training_budget_report


BUDGET_FIELDS = [
    "epochs",
    "max_optimizer_steps",
    "validation_interval_epochs",
    "max_validation_calls",
    "checkpoints_considered",
    "early_stopping_patience",
    "early_stopping_min_delta",
    "checkpoint_selection_rule",
    "hyperparameter_trials",
    "validation_scenarios",
    "validation_team_sizes",
    "validation_episodes_per_setting",
    "recheck_episodes_per_setting",
]


@pytest.fixture()
def report() -> dict:
    return training_budget_report(Config(), steps_per_epoch=100)


def test_report_covers_every_learned_method(report: dict) -> None:
    assert set(report) == set(LEARNED_METHOD_NAMES)


@pytest.mark.parametrize("field", BUDGET_FIELDS)
def test_budget_field_is_equal_across_methods(report: dict, field: str) -> None:
    values = {m: report[m][field] for m in report}
    distinct = {json.dumps(v, sort_keys=True) for v in values.values()}
    assert len(distinct) == 1, f"unequal {field} across learned methods: {values}"


def test_proposed_method_has_no_advantage_over_the_gnn_baseline(report: dict) -> None:
    ours, baseline = report["rvt_swarm"], report["gnn_only"]
    assert ours["max_optimizer_steps"] == baseline["max_optimizer_steps"]
    assert ours["max_validation_calls"] == baseline["max_validation_calls"]
    assert ours["checkpoints_considered"] == baseline["checkpoints_considered"]


def test_no_hyperparameter_tuning_was_performed(report: dict) -> None:
    """If tuning is ever added, the budget must be equal and this test updated."""
    for method, entry in report.items():
        assert entry["hyperparameter_trials"] == 0, (
            f"{method} declares {entry['hyperparameter_trials']} tuning trials; "
            "the budget must be equalised and the protocol document updated"
        )


def test_optimizer_steps_scale_with_epochs_and_are_reported(report: dict) -> None:
    for entry in report.values():
        assert entry["max_optimizer_steps"] == entry["epochs"] * entry["steps_per_epoch"]


def test_report_is_json_serialisable(report: dict) -> None:
    """It must be machine-readable, per the protocol."""
    assert json.loads(json.dumps(report)) == report


def test_validation_budget_uses_the_validation_split_only(report: dict) -> None:
    from rvt_swarm.splits import TEST_TEAM_SIZES

    for method, entry in report.items():
        overlap = set(entry["validation_team_sizes"]) & set(TEST_TEAM_SIZES)
        assert not overlap, f"{method} validates on final-test team sizes {sorted(overlap)}"
