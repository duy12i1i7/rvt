from dataclasses import dataclass, field
from typing import Dict, List


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
    min_rr_distance: float = 0.45
    min_ro_distance: float = 0.45
    obstacle_count: int = 8
    dynamic_obstacle_count: int = 2
    dynamic_obstacle_speed: float = 0.35
    team_sizes: List[int] = field(default_factory=lambda: [4, 8, 12, 16])
    scenarios: List[str] = field(default_factory=lambda: [
        "open_field",
        "cluttered",
        "narrow_passage",
        "dynamic_obstacles",
    ])


@dataclass
class TrainConfig:
    seed: int = 42
    device: str = "cpu"
    expert_episodes: int = 500
    batch_size: int = 32
    epochs: int = 30
    epochs_gnn_only: int = 30
    epochs_instant_cert: int = 30
    epochs_rvt_swarm: int = 100
    lr: float = 3e-4
    weight_decay: float = 1e-5
    hidden_dim: int = 128
    message_passes: int = 3
    dropout: float = 0.0
    recover_horizon: int = 14
    graph_k: int = 6
    lambda_action: float = 5.0
    lambda_recover: float = 0.15
    lambda_topology: float = 0.10
    lambda_aux: float = 0.05
    early_stopping_patience: int = 20
    early_stopping_min_delta: float = 1e-4
    save_best_only: bool = True
    curriculum_warmup_epochs: int = 12
    aux_gradient_scale: float = 0.0


@dataclass
class EvalConfig:
    episodes_per_setting: int = 25


@dataclass
class MethodConfig:
    use_recoverability: bool = True
    use_topology: bool = True
    use_counterfactual_topology: bool = True
    use_progress_shield: bool = True
    shield_gain: float = 0.25
    progress_weight: float = 0.10
    topology_temperature: float = 1.5
    switch_hysteresis: float = 0.50
    shield_risk_threshold: float = 0.50
    topology_cooldown: int = 15
    max_shield_blend: float = 0.10


@dataclass
class Config:
    env: EnvConfig = field(default_factory=EnvConfig)
    train: TrainConfig = field(default_factory=TrainConfig)
    eval: EvalConfig = field(default_factory=EvalConfig)
    method: MethodConfig = field(default_factory=MethodConfig)


TOPOLOGY_ACTIONS: Dict[int, str] = {
    0: "keep",
    1: "compress",
    2: "line",
    3: "split_hint",
    4: "recover",
}

TOPOLOGY_IDS: List[int] = sorted(TOPOLOGY_ACTIONS.keys())
