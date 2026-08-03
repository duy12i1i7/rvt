"""Frozen loss, tuning, checkpoint, baseline, metric and statistical contracts."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict, Tuple

from .common import sha256_document


LOSS_CONTRACT_SCHEMA_VERSION = "rvt-fd24-loss/v1"
HYPERPARAMETER_BUDGET_SCHEMA_VERSION = "rvt-fd24-hyperparameter-budget/v1"
CHECKPOINT_SELECTION_SCHEMA_VERSION = "rvt-checkpoint-selection/v1"
BASELINE_FAIRNESS_SCHEMA_VERSION = "rvt-baseline-fairness/v1"
METRIC_CONTRACT_SCHEMA_VERSION = "rvt-fd24-metrics/v1"
STATISTICAL_CONTRACT_SCHEMA_VERSION = "rvt-statistical-analysis/v1"
PRACTICAL_SIGNIFICANCE_SCHEMA_VERSION = "rvt-practical-significance/v1"


@dataclass(frozen=True)
class LossWeightChoice:
    lambda_rec: float
    lambda_res: float
    lambda_magnitude: float
    lambda_local_consistency: float


@dataclass(frozen=True)
class LossContract:
    schema_version: str = LOSS_CONTRACT_SCHEMA_VERSION
    recoverability_loss: str = "binary_cross_entropy_with_logits"
    residual_loss: str = "smooth_l1_beta_0.05_mps2"
    magnitude_regularization: str = "mean_absolute_bounded_residual"
    local_consistency_loss: str = "disabled_initially"
    class_weighting: str = "none_before_label_audit"
    recoverability_reduction: str = "mean_robot_candidate_within_event_then_mean_events"
    residual_reduction: str = "mean_components_then_robot_samples_within_episode_then_mean_episodes"
    candidate_reduction: str = "equal_COMPACT_LINE_weight_within_decision_event"
    invalid_sample_handling: str = "mask_and_report_never_relabel"
    residual_mask: str = "valid_robot_local_expert_and_safety_compatible"
    weight_choices: Tuple[LossWeightChoice, ...] = (
        LossWeightChoice(1.0, 0.5, 0.01, 0.0),
        LossWeightChoice(1.0, 1.0, 0.05, 0.0),
    )


@dataclass(frozen=True)
class HyperparameterBudget:
    schema_version: str = HYPERPARAMETER_BUDGET_SCHEMA_VERSION
    optimizer: str = "AdamW"
    learning_rates: Tuple[float, ...] = (1e-4, 3e-4, 1e-3)
    weight_decays: Tuple[float, ...] = (0.0, 1e-4)
    batch_construction: str = "16_decision_event_groups_plus_at_most_256_action_samples"
    maximum_optimizer_steps: int = 50000
    warmup_steps: int = 2000
    gradient_clip_norm: float = 1.0
    dropout_probabilities: Tuple[float, ...] = (0.0,)
    validation_frequency_steps: int = 1000
    early_stopping_patience_validations: int = 8
    early_stopping_minimum_task_success_delta: float = 0.002
    maximum_searched_configurations: int = 12
    model_seeds: Tuple[int, ...] = (11, 29, 47)
    mechanical_dry_run_seed: int = 0
    maximum_data_aggregation_repair_cycles: int = 1
    maximum_dagger_rounds: int = 2


@dataclass(frozen=True)
class CheckpointSelectionContract:
    schema_version: str = CHECKPOINT_SELECTION_SCHEMA_VERSION
    validation_frequency_steps: int = 1000
    minimum_closed_loop_validation_episodes: int = 120
    minimum_episodes_per_primary_family: int = 10
    collision_free_point_estimate_floor: float = 0.95
    maximum_collision_free_degradation: float = 0.01
    eligible_pool: str = "scheduled_checkpoints_from_one_predeclared_configuration_and_seed"
    primary_order: Tuple[str, ...] = (
        "collision_constraint_satisfied",
        "episode_task_success_maximized",
        "recoverability_Brier_score_minimized",
        "decisive_state_ranking_accuracy_maximized",
        "required_transition_completion_maximized",
        "earlier_optimizer_step",
    )
    task_success_tie_tolerance: float = 0.005
    failed_run_handling: str = "ineligible_and_reported"
    residual_variant_handling: str = "separate_pool_then_H4_paired_validation_gate"
    zero_shot_n24_handling: str = "never_used_for_checkpoint_selection"


@dataclass(frozen=True)
class BaselineDefinition:
    baseline_id: str
    category: str
    input_information: str
    runtime_locality: str
    model_capacity: str
    training_budget: str
    checkpoint_opportunities: str
    tuning_budget: str
    communication: str
    controller: str
    safety_projection: str
    scenario_access: str
    deployable: bool


def baseline_definitions() -> Tuple[BaselineDefinition, ...]:
    frozen_control = "frozen_Phase6_robot_local_controller"
    frozen_safety = "frozen_robot_local_safety_projection"
    common_scenarios = "identical_paired_split_and_episode_seeds"
    return (
        BaselineDefinition("always_COMPACT", "fixed", "local_runtime_state", "robot_local", "none", "none", "none", "none", "none", frozen_control, frozen_safety, common_scenarios, True),
        BaselineDefinition("always_LINE", "fixed", "local_runtime_state", "robot_local", "none", "none", "none", "none", "none", frozen_control, frozen_safety, common_scenarios, True),
        BaselineDefinition("always_KEEP_fixed_reference", "fixed_reference", "local_runtime_state", "robot_local", "none", "none", "none", "none", "none", frozen_control, frozen_safety, common_scenarios, True),
        BaselineDefinition("local_geometric_selector", "selector", "local_geometry_only", "robot_local", "none", "none", "none", "same_validation_episode_budget", "none", frozen_control, frozen_safety, common_scenarios, True),
        BaselineDefinition("direct_local_classifier", "learned_selector", "same_local_ego_graph", "robot_local", "matched_FD24_encoder_width", "same_max_steps_and_seeds", "same_validation_frequency", "same_12_configuration_cap", "none", frozen_control, frozen_safety, common_scenarios, True),
        BaselineDefinition("recoverability_without_consensus", "learned_selector", "same_local_ego_graph", "robot_local", "same_FD24_model", "same_max_steps_and_seeds", "same_validation_frequency", "same_12_configuration_cap", "none", frozen_control, frozen_safety, common_scenarios, True),
        BaselineDefinition("recoverability_with_consensus", "learned_selector", "local_ego_graph_and_one_hop_scores", "leaderless", "same_FD24_model", "same_max_steps_and_seeds", "same_validation_frequency", "same_12_configuration_cap", "frozen_score_protocol", frozen_control, frozen_safety, common_scenarios, True),
        BaselineDefinition("full_base_controller", "full_method", "local_ego_graph_and_peer_protocol", "leaderless", "same_FD24_model", "same_max_steps_and_seeds", "same_validation_frequency", "same_12_configuration_cap", "frozen_full_protocol", frozen_control, frozen_safety, common_scenarios, True),
        BaselineDefinition("full_with_residual", "optional_full_method", "local_ego_graph_and_peer_protocol", "leaderless", "same_FD24_model", "same_max_steps_and_seeds", "same_validation_frequency", "same_12_configuration_cap", "frozen_full_protocol", frozen_control, frozen_safety, common_scenarios, True),
        BaselineDefinition("centralized_COMPACT_LINE_selector", "diagnostic", "joint_offline_state", "centralized_offline", "matched_or_stronger_reported", "diagnostic_only", "none", "none", "global", frozen_control, frozen_safety, common_scenarios, False),
        BaselineDefinition("counterfactual_rollout_oracle", "diagnostic", "matched_future_rollouts", "centralized_offline", "none", "diagnostic_only", "none", "none", "offline", frozen_control, frozen_safety, common_scenarios, False),
        BaselineDefinition("best_fixed_per_episode", "diagnostic", "post_episode_fixed_outcomes", "centralized_offline", "none", "none", "none", "none", "none", frozen_control, frozen_safety, common_scenarios, False),
    )


PRIMARY_EPISODE_METRICS: Tuple[str, ...] = (
    "task_success",
    "episode_collision_free",
    "final_required_topology_metric_v3_dwell",
    "required_transition_sequence_success",
    "deadlock",
    "completion_time_seconds",
)
RECOVERABILITY_METRICS: Tuple[str, ...] = (
    "Brier_score", "NLL", "AUROC", "AUPRC", "ECE_10_equal_mass_bins",
    "decisive_state_candidate_ranking_accuracy", "decisive_state_coverage",
)
CONTROL_METRICS: Tuple[str, ...] = (
    "residual_action_RMSE_mps2", "normalized_RMSE", "action_saturation_rate",
    "safety_projection_intervention_rate", "forced_topology_closed_loop_success",
    "base_vs_residual_closed_loop_task_success",
)
SCALING_METRICS: Tuple[str, ...] = (
    "bytes_per_robot", "messages_per_transition", "agreement_latency_seconds",
    "inference_latency_per_robot_seconds", "total_simulator_latency_seconds",
    "graph_construction_latency_seconds", "memory_bytes", "average_degree",
    "maximum_degree",
)


@dataclass(frozen=True)
class PracticalSignificanceGates:
    schema_version: str = PRACTICAL_SIGNIFICANCE_SCHEMA_VERSION
    h1_minimum_absolute_task_success_gain: float = 0.08
    h2_minimum_absolute_task_success_gain: float = 0.10
    maximum_collision_free_degradation: float = 0.01
    minimum_centralized_performance_retention: float = 0.85
    maximum_bytes_per_robot_per_transition: int = 500000
    maximum_local_inference_fraction_of_control_period: float = 0.10
    minimum_model_seeds_with_positive_effect: int = 2
    total_model_seed_count: int = 3
    maximum_single_family_or_team_size_gain_fraction: float = 0.50


@dataclass(frozen=True)
class StatisticalAnalysisContract:
    schema_version: str = STATISTICAL_CONTRACT_SCHEMA_VERSION
    pairing_key: Tuple[str, ...] = (
        "split", "family", "layout_sha256", "team_size",
        "initial_condition_seed", "communication_seed",
        "dynamic_obstacle_seed", "evaluation_seed",
    )
    bootstrap_unit: str = "paired_episode_with_layout_cluster_sensitivity"
    bootstrap_resamples: int = 10000
    confidence_level: float = 0.95
    binary_test: str = "McNemar_exact_when_discordant_count_below_25_else_chi_square"
    continuous_test: str = "paired_permutation_10000_sign_flips_or_Wilcoxon_if_ties_dominate"
    multiple_comparison_correction: str = "Holm_familywise_alpha_0.05"
    primary_comparison_family: Tuple[str, ...] = (
        "full_base_vs_local_geometric",
        "full_base_vs_direct_classifier",
        "full_base_vs_strongest_fixed",
        "online_full_vs_always_COMPACT",
        "online_full_vs_always_LINE",
        "decentralized_full_vs_centralized_reference",
    )
    missing_episode_handling: str = "no_pair_deletion_failed_episode_is_task_failure_and_horizon_time"
    invalid_geometry_handling: str = "exclude_only_by_predeclared_validity_rule_and_publish_reason"
    seed_aggregation: str = "report_each_seed_and_equal_weight_seed_aggregate"
    effect_size_reporting: str = "paired_absolute_difference_relative_difference_and_confidence_interval"


def contract_hash(value: object) -> str:
    return sha256_document(asdict(value) if hasattr(value, "__dataclass_fields__") else value)


def metric_contract_document() -> Dict[str, object]:
    document: Dict[str, object] = {
        "schema_version": METRIC_CONTRACT_SCHEMA_VERSION,
        "episode_level_primary": list(PRIMARY_EPISODE_METRICS),
        "recoverability": list(RECOVERABILITY_METRICS),
        "control": list(CONTROL_METRICS),
        "decentralization_and_scaling": list(SCALING_METRICS),
        "promotion_rule": "secondary metrics cannot become primary after results",
    }
    document["metric_contract_sha256"] = sha256_document(document)
    return document
