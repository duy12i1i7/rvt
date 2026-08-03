from rvt_swarm.phase8.contracts import (
    LOSS_CONTRACT_SCHEMA_VERSION,
    HyperparameterBudget,
    LossContract,
)


def test_loss_contract_is_frozen_before_training_and_has_no_class_reweighting():
    contract = LossContract()
    assert contract.schema_version == LOSS_CONTRACT_SCHEMA_VERSION
    assert contract.recoverability_loss == "binary_cross_entropy_with_logits"
    assert contract.residual_loss == "smooth_l1_beta_0.05_mps2"
    assert contract.class_weighting == "none_before_label_audit"
    assert contract.local_consistency_loss == "disabled_initially"


def test_reductions_prevent_large_teams_or_long_episodes_from_dominating():
    contract = LossContract()
    assert "within_event_then_mean_events" in contract.recoverability_reduction
    assert "within_episode_then_mean_episodes" in contract.residual_reduction
    assert contract.candidate_reduction.startswith("equal_COMPACT_LINE")


def test_search_grid_has_exactly_twelve_predeclared_configurations():
    budget = HyperparameterBudget()
    loss = LossContract()
    count = len(budget.learning_rates) * len(budget.weight_decays) * len(loss.weight_choices)
    assert count == budget.maximum_searched_configurations == 12
