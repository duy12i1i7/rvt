from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Dict, Iterable

from .config import Config
from .evaluate import evaluate_method, summarize
from .policy_runtime import is_learned_method


def _save_json(obj, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)


def _clone_cfg(cfg: Config, episodes_per_setting: int | None = None) -> Config:
    clone = deepcopy(cfg)
    if episodes_per_setting is not None:
        clone.eval.episodes_per_setting = int(episodes_per_setting)
    return clone


def _attach_deltas(reference: Dict[str, float], current: Dict[str, float]) -> Dict[str, float]:
    out = dict(current)
    for key in (
        "success",
        "goal_reached",
        "collision_free",
        "form_ok",
        "stall_rate",
        "deadlock",
        "formation_recovery_time",
        "irreversible_collapse",
    ):
        out[f"delta_{key}"] = float(current[key] - reference[key])
    return out


def _checkpoint_exists(method: str, ckpt_dir: str) -> bool:
    if not is_learned_method(method):
        return True
    return (Path(ckpt_dir) / f"{method}.pt").exists()


def zero_retune_variants(base_cfg: Config, episodes_per_setting: int | None = None) -> Dict[str, Config]:
    variants: Dict[str, Config] = {}

    default = _clone_cfg(base_cfg, episodes_per_setting)
    variants["default"] = default

    dense = _clone_cfg(base_cfg, episodes_per_setting)
    dense.env.obstacle_count = max(dense.env.obstacle_count + 2, int(round(dense.env.obstacle_count * 1.5)))
    dense.env.dynamic_obstacle_count = max(
        dense.env.dynamic_obstacle_count + 1,
        int(round(dense.env.dynamic_obstacle_count * 1.5)),
    )
    variants["dense_obstacles"] = dense

    lidar = _clone_cfg(base_cfg, episodes_per_setting)
    lidar.env.lidar_range *= 0.75
    lidar.env.sensing_radius = max(lidar.env.lidar_range, lidar.env.sensing_radius * 0.75)
    variants["short_range_lidar"] = lidar

    actuation = _clone_cfg(base_cfg, episodes_per_setting)
    actuation.env.max_speed *= 0.85
    actuation.env.max_accel *= 0.85
    variants["tight_actuation"] = actuation

    workspace = _clone_cfg(base_cfg, episodes_per_setting)
    workspace.env.world_size *= 1.20
    workspace.env.max_steps = max(workspace.env.max_steps, int(round(workspace.env.max_steps * 1.15)))
    variants["wide_workspace"] = workspace

    dynamic = _clone_cfg(base_cfg, episodes_per_setting)
    dynamic.env.dynamic_obstacle_speed *= 1.40
    variants["fast_dynamic_obstacles"] = dynamic

    return variants


def derived_scale_sensitivity_variants(base_cfg: Config, episodes_per_setting: int | None = None) -> Dict[str, Config]:
    variants: Dict[str, Config] = {}

    default = _clone_cfg(base_cfg, episodes_per_setting)
    variants["default"] = default

    tighter_spacing = _clone_cfg(base_cfg, episodes_per_setting)
    tighter_spacing.env.nominal_spacing *= 0.85
    variants["tighter_spacing"] = tighter_spacing

    wider_spacing = _clone_cfg(base_cfg, episodes_per_setting)
    wider_spacing.env.nominal_spacing *= 1.15
    variants["wider_spacing"] = wider_spacing

    shorter_sensing = _clone_cfg(base_cfg, episodes_per_setting)
    shorter_sensing.env.sensing_radius *= 0.80
    variants["shorter_sensing"] = shorter_sensing

    wider_clearance = _clone_cfg(base_cfg, episodes_per_setting)
    wider_clearance.env.min_rr_distance *= 1.15
    wider_clearance.env.min_ro_distance *= 1.15
    variants["wider_clearance"] = wider_clearance

    shorter_horizon = _clone_cfg(base_cfg, episodes_per_setting)
    shorter_horizon.train.recover_horizon = max(4, int(round(shorter_horizon.train.recover_horizon * 0.75)))
    variants["shorter_horizon"] = shorter_horizon

    longer_horizon = _clone_cfg(base_cfg, episodes_per_setting)
    longer_horizon.train.recover_horizon = max(
        longer_horizon.train.recover_horizon + 1,
        int(round(longer_horizon.train.recover_horizon * 1.25)),
    )
    variants["longer_horizon"] = longer_horizon

    return variants


def run_variant_suite(
    suite_name: str,
    methods: Iterable[str],
    variants: Dict[str, Config],
    ckpt_dir: str,
    out_dir: str,
) -> Dict[str, object]:
    if "default" not in variants:
        raise ValueError("Variant suites must include a 'default' config.")

    suite_dir = Path(out_dir)
    suite_dir.mkdir(parents=True, exist_ok=True)
    results: Dict[str, object] = {
        "suite": suite_name,
        "reference_variant": "default",
        "variants": list(variants.keys()),
        "methods": {},
    }

    for method in methods:
        if not _checkpoint_exists(method, ckpt_dir):
            results["methods"][method] = {
                "status": "missing_checkpoint",
                "checkpoint": str(Path(ckpt_dir) / f"{method}.pt"),
            }
            continue

        method_results: Dict[str, Dict[str, float]] = {}
        reference_summary: Dict[str, float] | None = None
        for variant_name, cfg in variants.items():
            rows = evaluate_method(method, cfg, ckpt_dir)
            _save_json(rows, suite_dir / f"{suite_name}_{method}_{variant_name}_rows.json")
            summary = summarize(rows)
            if reference_summary is None:
                reference_summary = dict(summary)
            method_results[variant_name] = _attach_deltas(reference_summary, summary)
        results["methods"][method] = method_results

    _save_json(results, suite_dir / f"{suite_name}.json")
    return results
