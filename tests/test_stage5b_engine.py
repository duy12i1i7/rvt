"""Schedule, hyperparameter selection, refit rounding, M0, folds and selection."""

import math

import pytest

from rvt_swarm.openloop_v3 import synthetic
from rvt_swarm.openloop_v3.folds import (
    FOLD_A, FOLD_B, V3FoldError, build_train_internal_folds, split_by_fold,
)
from rvt_swarm.openloop_v3.hp import (
    HyperparameterSelectionError, choose_hyperparameters, hyperparameter_score,
    refit_step,
)
from rvt_swarm.openloop_v3.m0 import M0ContractError, m0_constant_probability
from rvt_swarm.openloop_v3.schedule import (
    EarlyStopping, ScheduleContractError, hyperparameter_grid, learning_rate_at,
    scheduled_evaluation_steps,
)
from rvt_swarm.openloop_v3.selection import (
    M0, M1, M2, SelectionContractError, designate_downstream_seed,
    per_seed_cross_validation_nll, select_family,
)
from rvt_swarm.fd24.loader_v3 import load_v3_event_groups


# ------------------------------------------------------------------ schedule
def test_warmup_is_linear_then_constant():
    assert learning_rate_at(0, base_learning_rate=1e-3, warmup_steps=1000) == pytest.approx(1e-6)
    assert learning_rate_at(499, base_learning_rate=1e-3, warmup_steps=1000) == pytest.approx(5e-4)
    assert learning_rate_at(999, base_learning_rate=1e-3, warmup_steps=1000) == 1e-3
    assert learning_rate_at(5000, base_learning_rate=1e-3, warmup_steps=1000) == 1e-3


def test_scheduled_evaluations_are_every_thousand_steps():
    steps = scheduled_evaluation_steps()
    assert steps[0] == 1000 and steps[-1] == 50000 and len(steps) == 50


def test_grid_is_the_frozen_six_in_the_frozen_tie_order():
    assert hyperparameter_grid() == (
        (1e-4, 0.0), (1e-4, 1e-4), (3e-4, 0.0), (3e-4, 1e-4), (1e-3, 0.0), (1e-3, 1e-4))


def test_early_stopping_requires_strict_improvement():
    stopper = EarlyStopping()
    assert stopper.update(1000, 1.0) is False
    for index in range(1, 8):
        assert stopper.update(1000 + 1000 * index, 1.0) is False
    assert stopper.update(9000, 1.0) is True
    assert stopper.best_step == 1000                      # earliest on equality


def test_early_stopping_resets_on_a_strict_improvement():
    stopper = EarlyStopping()
    stopper.update(1000, 1.0)
    stopper.update(2000, 1.0)
    stopper.update(3000, 0.9)
    assert stopper.evaluations_since_improvement == 0
    assert stopper.best_step == 3000 and stopper.best_value == 0.9


def test_a_nonzero_min_delta_is_refused():
    with pytest.raises(ScheduleContractError):
        EarlyStopping(min_delta=1e-4)


# ----------------------------------------------------------- hyperparameters
def test_hyperparameter_score_is_the_mean():
    assert hyperparameter_score([1.0, 2.0, 3.0]) == pytest.approx(2.0)


def test_hyperparameter_tie_breaks_to_lower_lr_then_lower_decay():
    scores = {configuration: 1.0 for configuration in hyperparameter_grid()}
    assert choose_hyperparameters(scores) == (1e-4, 0.0)
    scores[(1e-4, 0.0)] = 2.0
    assert choose_hyperparameters(scores) == (1e-4, 1e-4)
    scores[(1e-4, 1e-4)] = 2.0
    assert choose_hyperparameters(scores) == (3e-4, 0.0)


def test_an_incomplete_grid_is_refused():
    with pytest.raises(HyperparameterSelectionError):
        choose_hyperparameters({(1e-4, 0.0): 1.0})


@pytest.mark.parametrize("a,b,expected", [
    (4000, 4000, 4000),          # same step
    (3000, 4000, 4000),          # half-multiple rounds UP
    (1000, 2000, 2000),
    (0, 0, 1000),                # lower clamp
    (50000, 50000, 50000),       # upper clamp
    (49000, 50000, 50000),       # clamped after ceiling
    (1000, 1000, 1000),          # exact tie
])
def test_refit_step_ceiling_rule(a, b, expected):
    assert refit_step(a, b) == expected


def test_refit_step_refuses_unscheduled_steps():
    with pytest.raises(HyperparameterSelectionError):
        refit_step(1500, 2000)


# -------------------------------------------------------------------- M0
def _groups():
    return load_v3_event_groups(synthetic.synthetic_transactions(),
                                split=synthetic.SYNTHETIC_SPLIT)


class _Candidate:
    def __init__(self, k, R):
        self.k, self.R = k, R


class _Event:
    def __init__(self, compact, line):
        self.compact, self.line = compact, line


def test_m0_is_the_mean_of_k_over_r():
    events = [_Event(_Candidate(1, 1), _Candidate(0, 1)),
              _Event(_Candidate(2, 3), _Candidate(1, 3))]
    assert m0_constant_probability(events) == pytest.approx(
        (1.0 + 0.0 + 2.0 / 3.0 + 1.0 / 3.0) / 4.0)


def test_m0_does_not_depend_on_order_or_team_size():
    events = _groups()
    baseline = m0_constant_probability(events)
    assert m0_constant_probability(list(reversed(events))) == pytest.approx(baseline)
    swapped = [_Event(event.line, event.compact) for event in events]
    assert m0_constant_probability(swapped) == pytest.approx(baseline)
    for size in {group.team_size for group in events}:
        subset = [g for g in events if g.team_size == size]
        assert 0.0 <= m0_constant_probability(subset) <= 1.0


def test_m0_r1_only_reduces_to_the_positive_fraction():
    events = [_Event(_Candidate(1, 1), _Candidate(1, 1)),
              _Event(_Candidate(0, 1), _Candidate(1, 1))]
    assert m0_constant_probability(events) == pytest.approx(0.75)


def test_m0_refuses_impossible_observations():
    with pytest.raises(M0ContractError):
        m0_constant_probability([_Event(_Candidate(2, 1), _Candidate(0, 1))])
    with pytest.raises(M0ContractError):
        m0_constant_probability([])


# ------------------------------------------------------------------- folds
def test_synthetic_folds_partition_the_events():
    manifest = synthetic.synthetic_fold_manifest()
    folds = build_train_internal_folds(manifest)
    groups = _groups()
    split = split_by_fold(groups, folds)
    assert len(split[FOLD_A]) + len(split[FOLD_B]) == len(groups)
    a_ids = {group.decision_event_id for group in split[FOLD_A]}
    b_ids = {group.decision_event_id for group in split[FOLD_B]}
    assert not (a_ids & b_ids)


def test_fold_membership_is_by_layout_hash_not_name():
    manifest = synthetic.synthetic_fold_manifest()
    folds = build_train_internal_folds(manifest)
    digest = synthetic.synthetic_digest("layout::alpha")
    assert folds.fold_of(digest) == FOLD_A
    with pytest.raises(V3FoldError):
        folds.fold_of("0" * 64)


def test_a_layout_in_two_folds_is_refused():
    manifest = synthetic.synthetic_fold_manifest()
    manifest["folds"]["B"]["entries"][0]["layout_sha256"] = (
        manifest["folds"]["A"]["entries"][0]["layout_sha256"])
    with pytest.raises(V3FoldError):
        build_train_internal_folds(manifest)


def test_a_fold_missing_a_family_is_refused():
    manifest = synthetic.synthetic_fold_manifest()
    manifest["folds"]["A"]["entries"][1]["family"] = "F1"
    with pytest.raises(V3FoldError):
        build_train_internal_folds(manifest)


def test_a_manifest_without_the_disjointness_assertion_is_refused():
    manifest = synthetic.synthetic_fold_manifest()
    manifest["assertions"]["geometry_disjoint"] = False
    with pytest.raises(V3FoldError):
        build_train_internal_folds(manifest)


def test_an_event_spanning_two_layouts_is_refused():
    manifest = synthetic.synthetic_fold_manifest()
    folds = build_train_internal_folds(manifest)
    groups = list(_groups())
    victim = groups[0]
    victim.line.rows[0]["scientific_identity"]["layout_sha256"] = (
        synthetic.synthetic_digest("layout::beta"))
    try:
        with pytest.raises(V3FoldError):
            split_by_fold(groups, folds)
    finally:
        victim.line.rows[0]["scientific_identity"]["layout_sha256"] = (
            synthetic.synthetic_digest("layout::alpha"))


# --------------------------------------------------------------- selection
def test_all_four_selection_cases():
    assert select_family(upper_ci_delta_10=0.5, upper_ci_delta_20=0.5,
                         upper_ci_delta_21=-1.0).winner == M0
    assert select_family(upper_ci_delta_10=-0.5, upper_ci_delta_20=0.5,
                         upper_ci_delta_21=1.0).winner == M1
    assert select_family(upper_ci_delta_10=0.5, upper_ci_delta_20=-0.5,
                         upper_ci_delta_21=-0.5).winner == M2
    assert select_family(upper_ci_delta_10=-0.5, upper_ci_delta_20=-0.5,
                         upper_ci_delta_21=-0.1).winner == M2
    assert select_family(upper_ci_delta_10=-0.5, upper_ci_delta_20=-0.5,
                         upper_ci_delta_21=0.1).winner == M1


def test_case_one_does_not_support_learnability():
    outcome = select_family(upper_ci_delta_10=0.1, upper_ci_delta_20=0.1,
                            upper_ci_delta_21=0.0)
    assert outcome.case == 1 and outcome.learnability_supported is False


def test_a_confidence_bound_of_exactly_zero_is_not_eligible():
    outcome = select_family(upper_ci_delta_10=0.0, upper_ci_delta_20=0.0,
                            upper_ci_delta_21=0.0)
    assert outcome.winner == M0
    assert outcome.m1_eligible is False and outcome.m2_eligible is False
    both = select_family(upper_ci_delta_10=-0.2, upper_ci_delta_20=-0.2,
                         upper_ci_delta_21=0.0)
    assert both.winner == M1                          # exactly zero -> parsimony


def test_median_seed_is_chosen_not_the_best():
    assert designate_downstream_seed({11: 0.30, 29: 0.10, 47: 0.20}) == 47
    assert designate_downstream_seed({11: 0.10, 29: 0.20, 47: 0.30}) == 29


def test_median_seed_tie_goes_to_the_lower_seed():
    assert designate_downstream_seed({11: 0.5, 29: 0.5, 47: 0.5}) == 29
    assert designate_downstream_seed({11: 0.1, 29: 0.5, 47: 0.5}) == 29


def test_per_seed_cv_nll_averages_the_two_folds():
    values = per_seed_cross_validation_nll({11: (0.2, 0.4), 29: (0.3, 0.3), 47: (0.1, 0.9)})
    assert values == {11: pytest.approx(0.3), 29: pytest.approx(0.3), 47: pytest.approx(0.5)}
    with pytest.raises(SelectionContractError):
        per_seed_cross_validation_nll({11: (0.2,)})
