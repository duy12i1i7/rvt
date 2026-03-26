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
    min_rr_distance: float = 0.40
    min_ro_distance: float = 0.55
    obstacle_count: int = 8
    dynamic_obstacle_count: int = 2
    dynamic_obstacle_speed: float = 0.35
    # LiDAR sensor parameters
    lidar_num_rays: int = 36
    lidar_range: float = 3.0
    lidar_fov: float = 4.712389  # 270° in radians
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
    epochs_gnn_only: int = 120
    epochs_instant_cert: int = 120
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
    rollout_val_team_sizes: List[int] = field(default_factory=lambda: [8, 16])
    n_workers: int = 0  # 0 = auto (3/4 of cpu_count)


@dataclass
class EvalConfig:
    episodes_per_setting: int = 25


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
