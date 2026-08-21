"""Seed-0 mechanical training: determinism, residual freezing, no official data."""

import pytest
import torch

from rvt_swarm.fd24.checkpoint import canonical_state_dict_hash
from rvt_swarm.fd24.loader_v3 import load_v3_event_groups
from rvt_swarm.openloop_v3 import synthetic
from rvt_swarm.openloop_v3.authorization import (
    MODE_INSPECT, MODE_MECHANICAL, MODE_SCIENTIFIC, OfficialOptimizationRefused,
    ScientificTrainingNotAuthorized,
)
from rvt_swarm.openloop_v3.driver import (
    FAMILY_M1, FAMILY_M2, DriverContractError, GraphCache, build_model,
    dataset_brier, dataset_nll, event_terms, optimized_parameters, run_training,
)
from rvt_swarm.openloop_v3.folds import build_train_internal_folds, split_by_fold

SHORT = dict(maximum_steps=6, evaluation_interval=2, warmup_steps=3,
             events_per_batch=2)


@pytest.fixture(scope="module")
def groups():
    return load_v3_event_groups(synthetic.synthetic_transactions(),
                                split=synthetic.SYNTHETIC_SPLIT)


def _run(family, tmp_path, groups, **overrides):
    options = dict(SHORT)
    options.update(overrides)
    folds = build_train_internal_folds(synthetic.synthetic_fold_manifest())
    split = split_by_fold(groups, folds)
    return run_training(
        family=family, mode=MODE_MECHANICAL, fit_groups=split["A"],
        held_out_groups=split["B"], cache=GraphCache(), dataset_root=tmp_path,
        seed=0, learning_rate=1e-3, weight_decay=0.0, **options)


@pytest.mark.parametrize("family", [FAMILY_M1, FAMILY_M2])
def test_mechanical_run_is_bit_identical_across_two_runs(family, tmp_path, groups):
    first = _run(family, tmp_path, groups)
    second = _run(family, tmp_path, groups)
    assert first.state_dict_sha256 == second.state_dict_sha256
    assert first.metric_trace == second.metric_trace
    assert first.event_order == second.event_order
    assert first.best_step == second.best_step
    assert first.steps == second.steps


def test_the_residual_head_receives_no_update(tmp_path, groups):
    result = _run(FAMILY_M2, tmp_path, groups)
    assert result.residual_state_sha256_before is not None
    assert result.residual_state_sha256_before == result.residual_state_sha256_after


def test_the_residual_head_is_excluded_from_the_optimizer():
    model = build_model(FAMILY_M2)
    trainable = optimized_parameters(model, FAMILY_M2)
    residual = list(model.residual_action_head.parameters())
    identifiers = {id(parameter) for parameter in trainable}
    assert identifiers
    assert not any(id(parameter) in identifiers for parameter in residual)
    assert all(parameter.requires_grad is False for parameter in residual)


def test_training_actually_moves_the_recoverability_path(tmp_path, groups):
    model = build_model(FAMILY_M1)
    before = canonical_state_dict_hash(
        {name: tensor.detach().clone() for name, tensor in model.state_dict().items()})
    folds = build_train_internal_folds(synthetic.synthetic_fold_manifest())
    split = split_by_fold(groups, folds)
    result = run_training(
        family=FAMILY_M1, mode=MODE_MECHANICAL, fit_groups=split["A"],
        held_out_groups=split["B"], cache=GraphCache(), dataset_root=tmp_path,
        seed=0, learning_rate=1e-3, weight_decay=0.0, model=model, **SHORT)
    assert result.state_dict_sha256 != before
    assert result.steps == 6


def test_event_terms_carry_both_candidates_and_the_frozen_supervision(groups):
    cache = GraphCache()
    terms = event_terms(build_model(FAMILY_M1), FAMILY_M1, groups[:2], cache)
    assert len(terms) == 2
    for term, group in zip(terms, groups[:2]):
        assert term["compact_k"] == group.compact.k
        assert term["compact_R"] == group.compact.R
        assert term["line_k"] == group.line.k
        assert term["line_R"] == group.line.R
        assert term["compact_logits"].shape == (group.team_size,)
        assert term["line_logits"].shape == (group.team_size,)


def test_m2_logits_map_back_to_their_candidate_groups(groups):
    """The canonical batch permutation must not scramble candidate membership."""
    cache = GraphCache()
    model = build_model(FAMILY_M2)
    mixed = [group for group in groups if group.team_size == 5][:2]
    mixed += [group for group in groups if group.team_size == 16][:1]
    terms = event_terms(model, FAMILY_M2, mixed, cache)
    for term, group in zip(terms, mixed):
        assert term["compact_logits"].numel() == group.team_size
        assert term["line_logits"].numel() == group.team_size


def test_evaluation_is_event_equal_not_batch_equal(groups):
    cache = GraphCache()
    model = build_model(FAMILY_M1)
    a = dataset_nll(model, FAMILY_M1, groups, cache, events_per_batch=2)
    b = dataset_nll(model, FAMILY_M1, groups, cache, events_per_batch=3)
    c = dataset_nll(model, FAMILY_M1, groups, cache, events_per_batch=len(groups))
    assert a == pytest.approx(c, abs=1e-6)
    assert b == pytest.approx(c, abs=1e-6)


def test_brier_evaluation_runs_and_is_bounded(groups):
    value = dataset_brier(build_model(FAMILY_M1), FAMILY_M1, groups, GraphCache())
    assert 0.0 <= value <= 1.0


def test_inspect_mode_cannot_train(tmp_path, groups):
    with pytest.raises(DriverContractError):
        run_training(family=FAMILY_M1, mode=MODE_INSPECT, fit_groups=groups,
                     held_out_groups=groups, cache=GraphCache(),
                     dataset_root=tmp_path, seed=0, learning_rate=1e-3,
                     weight_decay=0.0, **SHORT)


def test_official_train_cannot_be_optimized_in_mechanical_mode(tmp_path, groups):
    """The guard runs before a model or optimizer is constructed."""
    official = tmp_path / "official-v3-train"
    (official / "ops").mkdir(parents=True)
    (official / "ops" / "authority.json").write_text('{"v3_split": "v3_train"}')
    with pytest.raises(OfficialOptimizationRefused):
        run_training(family=FAMILY_M1, mode=MODE_MECHANICAL, fit_groups=groups,
                     held_out_groups=groups, cache=GraphCache(),
                     dataset_root=official, seed=0, learning_rate=1e-3,
                     weight_decay=0.0, **SHORT)


def test_scientific_mode_is_refused_end_to_end(tmp_path, groups):
    official = tmp_path / "official-v3-train"
    (official / "ops").mkdir(parents=True)
    (official / "ops" / "authority.json").write_text('{"v3_split": "v3_train"}')
    with pytest.raises(ScientificTrainingNotAuthorized):
        run_training(family=FAMILY_M2, mode=MODE_SCIENTIFIC, fit_groups=groups,
                     held_out_groups=groups, cache=GraphCache(),
                     dataset_root=official, seed=11, learning_rate=1e-3,
                     weight_decay=0.0, **SHORT)


def test_batching_is_by_event_never_by_row(groups):
    from rvt_swarm.fd24.loader_v3 import batch_event_groups
    batches = batch_event_groups(tuple(groups), events_per_batch=16)
    assert len(batches) == 1
    assert all(hasattr(item, "compact") for item in batches[0])
