from rvt_swarm.phase8.contracts import (
    PracticalSignificanceGates,
    StatisticalAnalysisContract,
)


def test_episode_pairing_and_resampling_are_predeclared():
    contract = StatisticalAnalysisContract()
    assert "layout_sha256" in contract.pairing_key
    assert "evaluation_seed" in contract.pairing_key
    assert contract.bootstrap_resamples == 10000
    assert contract.confidence_level == 0.95
    assert len(contract.primary_comparison_family) == 6
    assert contract.multiple_comparison_correction == "Holm_familywise_alpha_0.05"


def test_robot_timestep_pseudoreplication_and_missing_pair_deletion_are_forbidden():
    contract = StatisticalAnalysisContract()
    assert contract.bootstrap_unit.startswith("paired_episode")
    assert contract.missing_episode_handling.startswith("no_pair_deletion")


def test_practical_significance_thresholds_are_numeric_and_stricter_than_zero():
    gates = PracticalSignificanceGates()
    assert gates.h1_minimum_absolute_task_success_gain == 0.08
    assert gates.h2_minimum_absolute_task_success_gain == 0.10
    assert gates.maximum_collision_free_degradation == 0.01
    assert gates.minimum_centralized_performance_retention == 0.85
    assert gates.maximum_local_inference_fraction_of_control_period == 0.10
