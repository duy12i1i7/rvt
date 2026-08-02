"""Immutable offline configuration that wraps the deployable runtime contract.

Deployable modules must import :mod:`rvt_swarm.runtime_configuration` directly;
this module owns training and evaluation settings and may wrap, but cannot
mutate, the frozen runtime hierarchy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Tuple

from .runtime_configuration import RuntimeConfig


@dataclass(frozen=True)
class TrainingConfig:
    """Training-only defaults retained for reproducible future reconstruction."""

    model_seed: int = 0
    training_data_seed: int = 0
    counterfactual_rollout_seed: int = 0
    device: str = "cpu"
    batch_size: int = 32
    learning_rate: float = 3e-4
    weight_decay: float = 1e-5
    hyperparameter_trials: int = 0


@dataclass(frozen=True)
class EvaluationConfig:
    """Offline simulator/evaluator settings; never a robot input."""

    episodes_per_setting: int = 25
    maximum_control_steps: int = 120
    world_size_meters: float = 12.0
    obstacle_radius_meters: float = 0.35
    spawn_jitter_standard_deviation_meters: float = 0.12
    goal_tolerance_meters: float = 0.55
    downstream_recovery_margin_meters: float = 0.5
    evaluation_schema_version: int = 2
    scenarios: Tuple[str, ...] = (
        "open_field",
        "cluttered",
        "narrow_passage",
        "dynamic_obstacles",
    )


@dataclass(frozen=True)
class ExperimentConfiguration:
    """Offline experiment wrapper around an immutable runtime configuration."""

    runtime: RuntimeConfig = field(default_factory=RuntimeConfig)
    training: TrainingConfig = field(default_factory=TrainingConfig)
    evaluation: EvaluationConfig = field(default_factory=EvaluationConfig)

