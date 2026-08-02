"""Run the frozen Phase 6 forced-topology matrix and mechanical benchmarks."""

from __future__ import annotations

import csv
import json
import math
import sys
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from rvt_swarm.decentralized.phase6_qualification import (
    PHASE6_SEEDS,
    PHASE6_STABILIZATION_FIXTURES,
    PHASE6_TRANSLATION_HEADINGS_RADIANS,
    benchmark_phase6_controller_stack,
    run_phase6_episode,
    run_phase6_safety_stress_case,
)
from rvt_swarm.runtime_configuration import SUPPORTED_MECHANICAL_TEAM_SIZES
from rvt_swarm.topology_registry import PRIMARY_TOPOLOGY_IDS


FORCED_ROOT = ROOT / "results" / "phase6_forced_topology"
STABILIZATION_ROOT = FORCED_ROOT / "stabilization"
TRANSLATION_ROOT = FORCED_ROOT / "open_translation"
STRESS_ROOT = ROOT / "results" / "phase6_local_safety_stress"
APPROVED_BASELINE = "b47a95fe238550e7fb7492c6fafd8427c1b572ec"


def _episode_task(task: Tuple[int, int, str, int, float]):
    return run_phase6_episode(*task)


def _json_safe(value):
    if isinstance(value, float) and not math.isfinite(value):
        return "infinity" if value > 0.0 else "-infinity"
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_json_safe(value), allow_nan=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_csv(path: Path, rows: List[Dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(rows[0]),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def _aggregate(rows: List[Dict[str, object]], include_heading: bool) -> List[Dict[str, object]]:
    groups: Dict[Tuple[object, ...], List[Dict[str, object]]] = {}
    for row in rows:
        key = (
            row["team_size"],
            row["topology_id"],
            row["fixture_class"],
        ) + ((row["heading_radians"],) if include_heading else ())
        groups.setdefault(key, []).append(row)
    summary = []
    for key in sorted(groups):
        episodes = groups[key]
        result = {
            "team_size": key[0],
            "topology_id": key[1],
            "fixture_class": key[2],
        }
        if include_heading:
            result["heading_radians"] = key[3]
        result.update({
            "episode_count": len(episodes),
            "valid_initial_condition_rate": sum(bool(item["valid_initial_condition"]) for item in episodes) / len(episodes),
            "collision_free_rate": sum(bool(item["collision_free"]) for item in episodes) / len(episodes),
            "dwell_completion_rate": sum(bool(item["dwell_completed"]) for item in episodes) / len(episodes),
            "goal_reaching_rate": sum(bool(item["goal_reached"]) for item in episodes) / len(episodes),
            "deadlock_rate": sum(bool(item["deadlock"]) for item in episodes) / len(episodes),
            "numerical_failure_rate": sum(bool(item["numerical_failure"]) for item in episodes) / len(episodes),
            "minimum_robot_robot_distance_meters": min(float(item["minimum_robot_robot_distance_meters"]) for item in episodes),
            "mean_initial_formation_error_meters": sum(float(item["initial_formation_error_meters"]) for item in episodes) / len(episodes),
            "mean_maximum_formation_error_meters": sum(float(item["maximum_formation_error_meters"]) for item in episodes) / len(episodes),
            "mean_final_formation_error_meters": sum(float(item["final_formation_error_meters"]) for item in episodes) / len(episodes),
            "mean_final_goal_error_meters": sum(float(item["final_goal_error_meters"]) for item in episodes) / len(episodes),
            "mean_saturation_rate": sum(float(item["saturation_rate"]) for item in episodes) / len(episodes),
            "mean_projection_intervention_rate": sum(float(item["projection_intervention_rate"]) for item in episodes) / len(episodes),
            "projection_infeasible_count": sum(int(item["projection_infeasible_count"]) for item in episodes),
            "solver_failure_count": sum(int(item["solver_failure_count"]) for item in episodes),
            "median_of_episode_controller_latency_seconds": sorted(float(item["per_robot_latency_median_seconds"]) for item in episodes)[len(episodes) // 2],
        })
        summary.append(result)
    return summary


def _run_tasks(tasks: Iterable[Tuple[int, int, str, int, float]]):
    ordered = tuple(tasks)
    with ProcessPoolExecutor() as executor:
        return list(executor.map(_episode_task, ordered))


def main() -> None:
    stabilization_tasks = (
        (team_size, topology_id, fixture, seed, 0.0)
        for team_size in SUPPORTED_MECHANICAL_TEAM_SIZES
        for topology_id in PRIMARY_TOPOLOGY_IDS
        for fixture in PHASE6_STABILIZATION_FIXTURES
        for seed in PHASE6_SEEDS
    )
    stabilization = _run_tasks(stabilization_tasks)
    stabilization_rows = [result.source() for result in stabilization]
    _write_json(STABILIZATION_ROOT / "episodes.json", stabilization_rows)
    _write_csv(STABILIZATION_ROOT / "episodes.csv", stabilization_rows)
    stabilization_summary = _aggregate(stabilization_rows, include_heading=False)
    _write_json(STABILIZATION_ROOT / "cell_summary.json", stabilization_summary)
    _write_csv(STABILIZATION_ROOT / "cell_summary.csv", stabilization_summary)

    translation_tasks = (
        (team_size, topology_id, "open_translation", seed, heading)
        for team_size in SUPPORTED_MECHANICAL_TEAM_SIZES
        for topology_id in PRIMARY_TOPOLOGY_IDS
        for heading in PHASE6_TRANSLATION_HEADINGS_RADIANS
        for seed in PHASE6_SEEDS
    )
    translation = _run_tasks(translation_tasks)
    translation_rows = [result.source() for result in translation]
    _write_json(TRANSLATION_ROOT / "episodes.json", translation_rows)
    _write_csv(TRANSLATION_ROOT / "episodes.csv", translation_rows)
    translation_summary = _aggregate(translation_rows, include_heading=True)
    _write_json(TRANSLATION_ROOT / "cell_summary.json", translation_summary)
    _write_csv(TRANSLATION_ROOT / "cell_summary.csv", translation_summary)

    stress_cases = (
        "safe_open",
        "static_obstacle_uncertain",
        "two_sided_restriction",
        "fresh_peer_approach",
        "stale_peer",
        "moving_obstacle",
        "infeasible_constraints",
    )
    stress = [
        asdict(run_phase6_safety_stress_case(case, projection_enabled=enabled))
        for case in stress_cases
        for enabled in (False, True)
    ]
    _write_json(STRESS_ROOT / "stress_results.json", stress)
    _write_csv(STRESS_ROOT / "stress_results.csv", stress)

    scaling = []
    for team_size in SUPPORTED_MECHANICAL_TEAM_SIZES:
        for dense in (False, True):
            scaling.append(asdict(benchmark_phase6_controller_stack(
                team_size,
                dense_communication=dense,
                local_obstacle_count=1,
            )))
    # The primary bounded-degree matrix already contains the one-obstacle N=24
    # point; add only the two endpoints of the obstacle-count diagnostic.
    for obstacle_count in (0, 4):
        scaling.append(asdict(benchmark_phase6_controller_stack(
            SUPPORTED_MECHANICAL_TEAM_SIZES[-1],
            dense_communication=False,
            local_obstacle_count=obstacle_count,
        )))
    _write_json(FORCED_ROOT / "controller_scaling.json", scaling)
    _write_csv(FORCED_ROOT / "controller_scaling.csv", scaling)

    manifest = {
        "approved_phase5_baseline": APPROVED_BASELINE,
        "team_sizes": list(SUPPORTED_MECHANICAL_TEAM_SIZES),
        "topology_ids": list(PRIMARY_TOPOLOGY_IDS),
        "seeds": list(PHASE6_SEEDS),
        "stabilization_fixtures": list(PHASE6_STABILIZATION_FIXTURES),
        "translation_headings_radians": list(PHASE6_TRANSLATION_HEADINGS_RADIANS),
        "stabilization_episode_count": len(stabilization_rows),
        "translation_episode_count": len(translation_rows),
        "resampling": False,
        "learned_model_active": False,
        "online_topology_transition": False,
        "final_test_access": False,
    }
    _write_json(FORCED_ROOT / "qualification_manifest.json", manifest)


if __name__ == "__main__":
    main()
