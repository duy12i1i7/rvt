from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .splits import VALIDATION_TEAM_SIZES


@dataclass
class EnvConfig:
    world_size: float = 12.0
    dt: float = 0.15
    max_steps: int = 120
    robot_radius: float = 0.18
    obstacle_radius: float = 0.35
    sensing_radius: float = 4.0
    max_speed: float = 0.9
    max_accel: float = 0.6
    goal_tolerance: float = 0.55
    formation_tolerance: float = 0.55
    nominal_spacing: float = 0.9
    min_rr_distance: float = 0.40
    min_ro_distance: float = 0.55
    # Clearance the commanded formation keeps above the robot-robot collision
    # threshold. Without it the fully compressed template commands a spacing
    # exactly equal to min_rr_distance, i.e. the controller's own set-point sits
    # on the failure boundary.
    spacing_margin: float = 0.05
    # Std-dev of the seeded jitter applied to spawn positions. Zero reproduces the
    # old deterministic lattice, in which every seed shared one initial state.
    spawn_jitter: float = 0.12

    @property
    def min_formation_scale(self) -> float:
        """Smallest formation scale whose commanded spacing clears min_rr_distance.

        Shared by `SwarmFormationEnv.apply_topology` and
        `controllers._project_topology_state`, which previously computed this
        floor independently and could drift apart.

        `getattr` keeps this working for `EnvConfig` instances unpickled from
        checkpoints written before `spacing_margin` existed (`train.py` stores the
        whole `Config` in each checkpoint).
        """
        margin = float(getattr(self, "spacing_margin", 0.0))
        floor = (self.min_rr_distance + margin) / max(self.nominal_spacing, 1e-6)
        return float(min(max(floor, 0.0), 1.0))
    obstacle_count: int = 8
    dynamic_obstacle_count: int = 2
    dynamic_obstacle_speed: float = 0.35
    # LiDAR sensor parameters
    lidar_num_rays: int = 36
    lidar_range: float = 3.0
    lidar_fov: float = 4.712389  # 270° in radians
    team_sizes: List[int] = field(
        default_factory=lambda: [2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24]
    )
    scenarios: List[str] = field(default_factory=lambda: [
        "open_field",
        "cluttered",
        "narrow_passage",
        "dynamic_obstacles",
    ])


@dataclass
class SeedConfig:
    """Explicit seed roles.

    Each role is independent: changing `model_seed` must not perturb the final
    test episodes, and changing `final_test_seed` must not perturb model
    initialisation. Proven by `tests/test_seed_independence.py`.
    """

    model_seed: int = 0              # network init, batch order
    training_data_seed: int = 0      # expert-episode generation
    validation_seed: int = 0         # validation episode set
    final_test_seed: int = 0         # final test episode set (shared by all methods)
    counterfactual_rollout_seed: int = 0  # stochastic rollout labelling
    environment_noise_seed: int = 0  # sensor/actuation noise, when enabled


@dataclass
class TrainConfig:
    # DEPRECATED: retained only so that older checkpoints unpickle. It no longer
    # drives model init, data generation, or episode selection -- see SeedConfig.
    seed: int = 42
    device: str = "cpu"
    expert_episodes: int = 500
    batch_size: int = 32
    epochs: int = 30
    # Equal budgets across learned methods. Because the best checkpoint is chosen
    # from interval-gated rollout validations, the epoch budget also sets the
    # model-selection budget: at 300 vs 120 epochs the proposed method received
    # 30 selection opportunities against the baseline's 12 (a 2.5x advantage) for
    # a reported success margin of 0.005. Early stopping (patience 40) still ends
    # runs that stop improving, so raising the baselines does not force 300 epochs.
    epochs_gnn_only: int = 300
    epochs_instant_cert: int = 300
    epochs_rvt_swarm: int = 300
    lr: float = 3e-4
    weight_decay: float = 1e-5
    hidden_dim: int = 128
    message_passes: int = 3
    recover_horizon: int = 14
    graph_k: int = 6
    early_stopping_patience: int = 40
    early_stopping_min_delta: float = 1e-4
    save_best_only: bool = True
    rollout_val_enabled: bool = True
    rollout_val_interval: int = 10
    rollout_val_episodes_per_setting: int = 4
    rollout_val_topk_checkpoints: int = 5
    rollout_val_recheck_episodes_per_setting: int = 8
    rollout_val_recheck_seed_offset: int = 80_000
    rollout_val_scenarios: List[str] = field(default_factory=lambda: [
        "narrow_passage",
        "dynamic_obstacles",
    ])
    # Validation team sizes come from the validation split and are disjoint from
    # the final test sweep, so a validation episode can never coincide with a test
    # episode. Previously [8, 16, 24] -- all three are final-test sizes.
    rollout_val_team_sizes: List[int] = field(
        default_factory=lambda: list(VALIDATION_TEAM_SIZES)
    )
    # Hyperparameter trials per method. Kept at 0 (no tuning was performed) and
    # asserted equal across methods by tests/test_equal_model_selection_budget.py.
    hyperparameter_trials: int = 0
    n_workers: int = 0  # 0 = auto (3/4 of cpu_count)


@dataclass
class EvalConfig:
    episodes_per_setting: int = 25


@dataclass
class AuditConfig:
    """Diagnostic knobs for the method audit.

    Every default reproduces the shipped behaviour exactly, so enabling audit
    instrumentation cannot change any Evaluation Protocol V2 result. These are
    swept on TRAINING and VALIDATION scenarios only.
    """

    # Safety filter: override the geometry-derived risk trigger (None = derived).
    risk_threshold_override: Optional[float] = None
    disable_safety_filter: bool = False
    # Topology selector variant:
    #   "lexicographic" (shipped) | "logits_argmax" | "score_argmax" | "fixed"
    selector_mode: str = "lexicographic"
    min_dwell_steps: int = 0          # 0 = no dwell constraint (shipped)
    hysteresis_margin: float = 0.0    # 0 = no hysteresis (shipped)
    use_uncertainty_adjustment: bool = True


@dataclass
class MethodConfig:
    use_recoverability: bool = True
    use_topology: bool = True
    use_counterfactual_topology: bool = True
    use_progress_shield: bool = True
    use_adaptive_formation_scale: bool = True


@dataclass
class Config:
    env: EnvConfig = field(default_factory=EnvConfig)
    train: TrainConfig = field(default_factory=TrainConfig)
    eval: EvalConfig = field(default_factory=EvalConfig)
    method: MethodConfig = field(default_factory=MethodConfig)
    seeds: SeedConfig = field(default_factory=SeedConfig)
    audit: AuditConfig = field(default_factory=AuditConfig)

    def audit_config(self) -> AuditConfig:
        """Tolerate Config objects unpickled from checkpoints predating AuditConfig."""
        existing = getattr(self, "audit", None)
        return existing if existing is not None else AuditConfig()

    def seed_config(self) -> SeedConfig:
        """Tolerate Config objects unpickled from checkpoints predating SeedConfig."""
        existing = getattr(self, "seeds", None)
        return existing if existing is not None else SeedConfig()


TOPOLOGY_ACTIONS: Dict[int, str] = {
    0: "keep",
    1: "compress",
    2: "line",
    3: "split_hint",
    4: "recover",
}

TOPOLOGY_IDS: List[int] = sorted(TOPOLOGY_ACTIONS.keys())
# RVT only needs persistent structural topology choices. Continuous
# formation-scale adaptation already covers compress/recover semantics, so
# learning them as extra discrete classes makes switching noisier without
# adding structural benefit.
LEARNED_TOPOLOGY_IDS: List[int] = [0, 2, 3]
