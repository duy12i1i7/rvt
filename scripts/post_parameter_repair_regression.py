"""Frozen post-parameter-repair regression (Tasks P1-P8).

The harness is diagnostic and evaluation-only.  It does not modify the
controller, runtime protocol, scenario geometry, or any frozen parameter.
Run ``--manifest-only`` before any closed-loop mode; later phases refuse to
start unless the immutable manifest matches the current frozen inputs.
"""

from __future__ import annotations

import argparse
import contextlib
import dataclasses
import hashlib
import json
import math
import statistics
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping

import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from rvt_swarm.decentralized.env_geometry import (  # noqa: E402
    build_passage, required_half_separation)
from rvt_swarm.decentralized.formation_metric_v3 import (  # noqa: E402
    EPSILON_FORM, e_inf)
from rvt_swarm.decentralized import epoch as E  # noqa: E402
from rvt_swarm.decentralized import guards  # noqa: E402
from rvt_swarm.decentralized.comms import simulate_local_obstacles  # noqa: E402
from rvt_swarm.decentralized.parameters import (  # noqa: E402
    MissionParams, PlatformParams, ProtocolParams, check_team_size,
    default_parameters, derived_commitment_steps, derived_component_diameter,
    derived_event_collection_steps, derived_evidence_persistence_steps,
    derived_forward_sector_half_width,
    derived_k_trigger, derived_lookahead_distance,
    derived_max_message_age_steps, derived_rearm_inactive_steps,
    derived_recovery_dwell_steps, normalized_ratios)
from rvt_swarm.decentralized.qualification_fixtures import (  # noqa: E402
    SPAWN_JITTER, Fixture, fixture_config, fixture_layout,
    simulate_reset_to_fixture, template_spawn, validate_initial_conditions)
from rvt_swarm.decentralized.roles import RoleAssignment  # noqa: E402
from rvt_swarm.decentralized.runtime import (  # noqa: E402
    simulate_decentralized_episode)
from rvt_swarm.decentralized.system_model import (  # noqa: E402
    KEEP, LINE, CommParams, ConsensusParams)
from rvt_swarm.environment import SwarmFormationEnv  # noqa: E402


OUT = REPO / "results" / "post_parameter_repair_regression"
MANIFEST_PATH = OUT / "experiment_manifest.json"
DETECTOR_PATH = OUT / "role_dependent_detector_validation.json"
MECHANICAL_PATH = OUT / "mechanical_parameterization_checks.json"
CLOSED_LOOP_PATH = OUT / "closed_loop_results.json"
ATTRIBUTION_PATH = OUT / "failure_attribution.json"
GATES_PATH = OUT / "regression_gates.json"
SOURCE_TAG = "decentralized-parameter-semantics-v1"
PRE_REPAIR_RESULTS = (
    REPO / "results" / "recovery_propagation_latency_repair"
    / "four_arm_comparison.json"
)

TEAM_SIZE = 6
ALPHAS: Mapping[str, float] = {
    "alpha_025": 0.25,
    "alpha_035": 0.35,
    "alpha_045": 0.45,
}
GEOMETRY_VARIANTS = (
    {"id": "len1.0_off0.0", "corridor_length_m": 1.0,
     "entry_offset_m": 0.0, "centre_y_m": 0.0},
    {"id": "len2.0_off0.5", "corridor_length_m": 2.0,
     "entry_offset_m": 0.5, "centre_y_m": 0.0},
)
INITIAL_CONDITION_SEEDS = (0, 1, 2, 3, 4)
# The published harness used the same episode seed for initial jitter, the
# simulator RNG, and the radio channel.  The nominal channel is deterministic,
# but the seed roles are preserved explicitly rather than silently conflated.
DISTURBANCE_SEEDS = (0, 1, 2, 3, 4)
COMMUNICATION_SEEDS = (0, 1, 2, 3, 4)
OLD_FORWARD_SECTOR_HALF_WIDTH_M = 1.2


def _git(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=REPO, text=True).strip()


def _jsonable(value: Any) -> Any:
    if dataclasses.is_dataclass(value):
        return {k: _jsonable(v) for k, v in dataclasses.asdict(value).items()}
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Mapping):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [_jsonable(v) for v in value]
    return value


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        _jsonable(value), sort_keys=True, separators=(",", ":"),
        ensure_ascii=True, allow_nan=False).encode("ascii")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(
        _jsonable(value), indent=2, sort_keys=True,
        ensure_ascii=True, allow_nan=False) + "\n")


def _derived(*, sources: Mapping[str, Any], formula: str, value: Any,
             unit: str, normalized: Any = None) -> Dict[str, Any]:
    return {
        "source_parameters": _jsonable(sources),
        "derivation_formula": formula,
        "result": {"value": _jsonable(value), "unit": unit},
        "normalized_value": _jsonable(normalized),
    }


def _scenario_records(cfg) -> list[Dict[str, Any]]:
    half_world = cfg.env.world_size / 2.0
    h_line = required_half_separation(TEAM_SIZE, LINE, cfg)
    h_keep = required_half_separation(TEAM_SIZE, KEEP, cfg)
    records: list[Dict[str, Any]] = []
    for alpha_name, alpha in ALPHAS.items():
        half_separation = h_line + alpha * (h_keep - h_line)
        for variant in GEOMETRY_VARIANTS:
            geo = build_passage(
                TEAM_SIZE, cfg, half_separation, half_world=half_world,
                corridor_length=variant["corridor_length_m"],
                entry_offset=variant["entry_offset_m"],
                centre_y=variant["centre_y_m"])
            layout = fixture_layout(dataclasses.make_dataclass(
                "ManifestFixture",
                [("name", str), ("n", int), ("spawn_centre", tuple),
                 ("goal", tuple), ("obstacles", np.ndarray),
                 ("corridor_width", float), ("entry_x", float),
                 ("exit_x", float), ("recovery_x0", float),
                 ("recovery_width", float)],
                frozen=True)(
                    f"{alpha_name}_{variant['id']}", TEAM_SIZE,
                    geo.spawn_centre, geo.goal, geo.obstacles, geo.free_width,
                    geo.entry_x, geo.exit_x, geo.recovery_x0,
                    geo.recovery_width))
            initial_hashes = {}
            for seed in INITIAL_CONDITION_SEEDS:
                pos = template_spawn(
                    TEAM_SIZE, cfg, geo.spawn_centre, seed,
                    jitter=SPAWN_JITTER)
                initial_hashes[str(seed)] = _sha256_bytes(
                    np.round(pos.astype(np.float64), 12).tobytes())
            records.append({
                "alpha_cell": alpha_name,
                "alpha": alpha,
                "variant": _jsonable(variant),
                "team_size": TEAM_SIZE,
                "half_separation_m": half_separation,
                "free_width_m": geo.free_width,
                "corridor_x0_m": geo.corridor_x0,
                "corridor_x1_m": geo.corridor_x1,
                "entry_x_m": geo.entry_x,
                "exit_x_m": geo.exit_x,
                "recovery_x0_m": geo.recovery_x0,
                "goal_m": list(geo.goal),
                "spawn_centre_m": list(geo.spawn_centre),
                "obstacle_count": int(len(geo.obstacles)),
                "geometry_sha256": layout.geometry_hash(),
                "initial_condition_sha256_by_seed": initial_hashes,
            })
    return records


def _passage_fixture(alpha_name: str, alpha: float,
                     variant: Mapping[str, Any], cfg) -> tuple[Any, Fixture]:
    half_world = cfg.env.world_size / 2.0
    h_line = required_half_separation(TEAM_SIZE, LINE, cfg)
    h_keep = required_half_separation(TEAM_SIZE, KEEP, cfg)
    half_separation = h_line + alpha * (h_keep - h_line)
    geo = build_passage(
        TEAM_SIZE, cfg, half_separation, half_world=half_world,
        corridor_length=float(variant["corridor_length_m"]),
        entry_offset=float(variant["entry_offset_m"]),
        centre_y=float(variant["centre_y_m"]))
    fixture = Fixture(
        name=f"{alpha_name}_{variant['id']}", n=TEAM_SIZE,
        spawn_centre=geo.spawn_centre, goal=geo.goal,
        obstacles=geo.obstacles, corridor_width=geo.free_width,
        entry_x=geo.entry_x, exit_x=geo.exit_x,
        recovery_x0=geo.recovery_x0, recovery_width=geo.recovery_width)
    return geo, fixture


def build_manifest() -> Dict[str, Any]:
    cfg = fixture_config()
    platform, mission, protocol = default_parameters(cfg.env)
    comm = CommParams()
    consensus = ConsensusParams()
    source_commit = _git("rev-parse", f"{SOURCE_TAG}^{{commit}}")
    head_commit = _git("rev-parse", "HEAD")
    if head_commit != source_commit:
        runtime_diff = _git(
            "diff", "--name-only", source_commit, "--",
            "rvt_swarm/decentralized", "rvt_swarm/config.py",
            "rvt_swarm/environment.py")
        if runtime_diff:
            raise RuntimeError(
                "deployable/runtime sources differ from the frozen parameter "
                f"commit: {runtime_diff}")

    graph_diameter = derived_component_diameter(protocol)
    k_trigger = derived_k_trigger(protocol)
    # Confirmation is min/max propagation over the same component and therefore
    # uses the same declared diameter derivation.  Assert the runtime binding.
    k_confirm = graph_diameter
    evidence_steps = derived_evidence_persistence_steps(protocol, platform)
    collection_steps = derived_event_collection_steps(protocol, platform)
    commitment_steps = derived_commitment_steps(protocol, platform)
    recovery_steps = derived_recovery_dwell_steps(mission, platform)
    stale_steps = derived_max_message_age_steps(protocol, platform)
    rearm_steps = derived_rearm_inactive_steps(protocol, platform)
    lookahead = derived_lookahead_distance(platform, mission, protocol)

    runtime_bindings = {
        "communication_range_m": (comm.r_comm, platform.communication_range),
        "obstacle_sensing_range_m": (comm.r_obs, platform.obstacle_sensor_range),
        "control_period_s": (comm.t_ctrl, platform.control_period),
        "communication_period_s": (comm.t_comm, platform.communication_period),
        "max_message_age_steps": (comm.delta_stale_steps, stale_steps),
        "k_trigger": (consensus.k_trigger, k_trigger),
        "k_confirm": (consensus.k_confirm, k_confirm),
        "commitment_steps": (consensus.h_commit, commitment_steps),
    }
    mismatches = {
        key: {"runtime": actual, "derived": expected}
        for key, (actual, expected) in runtime_bindings.items()
        if actual != expected
    }
    if mismatches:
        raise RuntimeError(f"runtime/config derivation mismatch: {mismatches}")

    roles = RoleAssignment.from_index(TEAM_SIZE, mission.nominal_spacing)
    role_widths = []
    for robot_id in range(TEAM_SIZE):
        keep_role = roles.role_of(robot_id, KEEP)
        line_role = roles.role_of(robot_id, LINE)
        displacement = abs(float(keep_role[1]) - float(line_role[1]))
        width = derived_forward_sector_half_width(
            keep_role, line_role, platform, mission)
        role_widths.append(_derived(
            sources={
                "robot_id": robot_id,
                "keep_role_m": keep_role,
                "line_role_m": line_role,
                "lateral_displacement_m": displacement,
                "collision_clearance_obstacle_m":
                    platform.collision_clearance_obstacle,
                "safety_margin_m": mission.safety_margin,
            },
            formula=("abs(keep_role_lateral - line_role_lateral) + "
                     "collision_clearance_obstacle + safety_margin"),
            value=width, unit="m",
            normalized=width / mission.nominal_spacing))

    derived = {
        "graph_diameter_bound": _derived(
            sources={
                "max_team_size": protocol.max_team_size,
                "max_component_diameter": protocol.max_component_diameter,
                "connectivity_assumption": protocol.connectivity_assumption,
            },
            formula=("max_component_diameter if declared, otherwise "
                     "max_team_size - 1"),
            value=graph_diameter, unit="hops",
            normalized=graph_diameter / max(protocol.max_team_size - 1, 1)),
        "k_trigger": _derived(
            sources={"graph_diameter_bound_hops": graph_diameter},
            formula="k_trigger = graph_diameter_bound",
            value=k_trigger, unit="rounds",
            normalized=k_trigger / max(graph_diameter, 1)),
        "k_confirm": _derived(
            sources={"graph_diameter_bound_hops": graph_diameter},
            formula="k_confirm = graph_diameter_bound",
            value=k_confirm, unit="rounds",
            normalized=k_confirm / max(graph_diameter, 1)),
        "evidence_persistence": _derived(
            sources={
                "evidence_persistence_seconds":
                    protocol.evidence_persistence_seconds,
                "control_period_seconds": platform.control_period,
            },
            formula="ceil(evidence_persistence_seconds / control_period_seconds)",
            value={"seconds": protocol.evidence_persistence_seconds,
                   "steps": evidence_steps}, unit="s_and_steps",
            normalized=protocol.evidence_persistence_seconds
            / platform.control_period),
        "commitment": _derived(
            sources={
                "commitment_seconds": protocol.commitment_seconds,
                "control_period_seconds": platform.control_period,
            },
            formula="ceil(commitment_seconds / control_period_seconds)",
            value={"seconds": protocol.commitment_seconds,
                   "steps": commitment_steps}, unit="s_and_steps",
            normalized=protocol.commitment_seconds / platform.control_period),
        "recovery_dwell": _derived(
            sources={
                "recovery_dwell_seconds": mission.recovery_dwell_seconds,
                "control_period_seconds": platform.control_period,
            },
            formula="ceil(recovery_dwell_seconds / control_period_seconds)",
            value={"seconds": mission.recovery_dwell_seconds,
                   "steps": recovery_steps}, unit="s_and_steps",
            normalized=mission.recovery_dwell_seconds / platform.control_period),
        "max_message_age": _derived(
            sources={
                "max_message_age_seconds": protocol.max_message_age_seconds,
                "control_period_seconds": platform.control_period,
            },
            formula="ceil(max_message_age_seconds / control_period_seconds)",
            value={"seconds": protocol.max_message_age_seconds,
                   "steps": stale_steps}, unit="s_and_steps",
            normalized=protocol.max_message_age_seconds / platform.control_period),
        "rearm_inactive": _derived(
            sources={
                "rearm_inactive_seconds": protocol.rearm_inactive_seconds,
                "control_period_seconds": platform.control_period,
            },
            formula="ceil(rearm_inactive_seconds / control_period_seconds)",
            value={"seconds": protocol.rearm_inactive_seconds,
                   "steps": rearm_steps}, unit="s_and_steps",
            normalized=protocol.rearm_inactive_seconds / platform.control_period),
        "role_dependent_forward_sector_half_widths": role_widths,
        "lookahead_distance": _derived(
            sources={
                "max_speed_m_s": platform.max_speed,
                "max_accel_m_s2": platform.max_accel,
                "evidence_persistence_steps": evidence_steps,
                "event_collection_steps": collection_steps,
                "k_trigger_rounds": k_trigger,
                "control_period_seconds": platform.control_period,
                "obstacle_sensor_range_m": platform.obstacle_sensor_range,
                "safety_margin_m": mission.safety_margin,
            },
            formula=("min(R_obs, v^2/(2*a) + "
                     "v*(persistence_steps + collection_steps + k_trigger)"
                     "*T_ctrl + safety_margin)"),
            value=lookahead, unit="m",
            normalized=lookahead / mission.nominal_spacing),
    }

    core = {
        "schema_version": "post_parameter_repair_regression_manifest_v1",
        "immutability_rule": (
            "The harness refuses to overwrite this file unless the canonical "
            "manifest content is byte-for-byte identical."),
        "scope": {
            "closed_loop_team_size": TEAM_SIZE,
            "final_test_layout_access": False,
            "learned_selector": False,
            "controller_changes": False,
            "protocol_phase_changes": False,
            "parameter_tuning_from_results": False,
        },
        "source": {
            "runtime_commit": source_commit,
            "runtime_tag": SOURCE_TAG,
            "parameter_repair_report":
                "docs/PARAMETER_SEMANTICS_REPAIR_REPORT.md",
            "parameter_repair_report_sha256": _sha256_file(
                REPO / "docs" / "PARAMETER_SEMANTICS_REPAIR_REPORT.md"),
            "preserved_pre_parameter_repair_results": str(
                PRE_REPAIR_RESULTS.relative_to(REPO)),
            "preserved_pre_parameter_repair_results_sha256":
                _sha256_file(PRE_REPAIR_RESULTS),
        },
        "physical_platform_configuration": _jsonable(platform),
        "environment_configuration": {
            "world_size_m": cfg.env.world_size,
            "max_control_steps": cfg.env.max_steps,
            "obstacle_radius_m": cfg.env.obstacle_radius,
            "lidar_num_rays": cfg.env.lidar_num_rays,
            "lidar_fov_rad": cfg.env.lidar_fov,
            "spawn_jitter_m": SPAWN_JITTER,
        },
        "mission_configuration": _jsonable(mission),
        "protocol_configuration": _jsonable(protocol),
        "communication_configuration": _jsonable(comm),
        "consensus_runtime_binding": _jsonable(consensus),
        "normalized_platform_and_mission": normalized_ratios(platform, mission),
        "derived_quantities": derived,
        "frozen_experiment_cells": {
            "alphas": _jsonable(ALPHAS),
            "geometry_variants": _jsonable(GEOMETRY_VARIANTS),
            "initial_condition_seeds": list(INITIAL_CONDITION_SEEDS),
            "disturbance_seeds": list(DISTURBANCE_SEEDS),
            "communication_seeds": list(COMMUNICATION_SEEDS),
            "seed_binding": (
                "Published harness variable sd is used unchanged for initial "
                "jitter, simulator RNG, and RadioChannel RNG. Nominal packet "
                "loss and delay are both zero."),
            "episode_count": (
                len(ALPHAS) * len(GEOMETRY_VARIANTS)
                * len(INITIAL_CONDITION_SEEDS)),
            "scenarios": _scenario_records(cfg),
        },
    }
    return {
        "manifest_content_sha256": _sha256_bytes(_canonical_bytes(core)),
        **core,
    }


def write_immutable_manifest(manifest: Mapping[str, Any]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(
        _jsonable(manifest), indent=2, sort_keys=True,
        ensure_ascii=True, allow_nan=False) + "\n"
    if MANIFEST_PATH.exists():
        existing = MANIFEST_PATH.read_text()
        if existing != encoded:
            raise RuntimeError(
                f"immutable manifest already exists with different content: "
                f"{MANIFEST_PATH}")
        return
    MANIFEST_PATH.write_text(encoded)


def verify_manifest() -> Dict[str, Any]:
    expected = build_manifest()
    if not MANIFEST_PATH.exists():
        raise RuntimeError("run --manifest-only before any regression phase")
    actual = json.loads(MANIFEST_PATH.read_text())
    if _canonical_bytes(actual) != _canonical_bytes(expected):
        raise RuntimeError("frozen manifest no longer matches source/configuration")
    return actual


@contextlib.contextmanager
def _preserved_old_detector():
    """Diagnostic-only binding of the retired 1.2 m detector."""
    original = E.forward_opening_evidence

    def old_forward_opening(view, cfg, half_width=None):
        return original(
            view, cfg, half_width=OLD_FORWARD_SECTOR_HALF_WIDTH_M)

    E.forward_opening_evidence = old_forward_opening
    try:
        yield
    finally:
        E.forward_opening_evidence = original


def _frozen_trace_rows(seed: int) -> list[Dict[str, Any]]:
    path = (REPO / "results" / "recovery_propagation_latency"
            / "alpha_025_trace.jsonl")
    rows = []
    with path.open() as handle:
        for line in handle:
            row = json.loads(line)
            if int(row["seed"]) == int(seed):
                rows.append(row)
    if not rows:
        raise RuntimeError(f"no frozen alpha 0.25 trace for seed {seed}")
    return rows


def _first_step(flags: Iterable[tuple[int, bool]]) -> int | None:
    return next((int(step) for step, flag in flags if flag), None)


def _role_detector_geometry() -> list[Dict[str, Any]]:
    cfg = fixture_config()
    platform, mission, _ = default_parameters(cfg.env)
    roles = RoleAssignment.from_index(TEAM_SIZE, mission.nominal_spacing)
    rows = []
    for robot_id in range(TEAM_SIZE):
        keep = roles.role_of(robot_id, KEEP)
        line = roles.role_of(robot_id, LINE)
        displacement = abs(float(keep[1]) - float(line[1]))
        width = derived_forward_sector_half_width(
            keep, line, platform, mission)
        rows.append({
            "robot_id": robot_id,
            "line_role_lateral_m": float(line[1]),
            "keep_role_lateral_m": float(keep[1]),
            "required_lateral_expansion_displacement_m": displacement,
            "collision_clearance_m":
                platform.collision_clearance_obstacle,
            "safety_margin_m": mission.safety_margin,
            "derived_forward_sector_half_width_m": width,
            "maximum_width_observable_under_R_obs_m":
                platform.obstacle_sensor_range,
            "complete_future_expansion_region_observed": bool(
                width <= platform.obstacle_sensor_range),
        })
    return rows


def run_detector_validation() -> Dict[str, Any]:
    """Apply old A and corrected B to the same preserved alpha 0.25 traces."""
    verify_manifest()
    guards.set_strict(True)
    cfg = fixture_config()
    platform, mission, _ = default_parameters(cfg.env)
    variant = GEOMETRY_VARIANTS[0]
    geo, fixture = _passage_fixture(
        "alpha_025", ALPHAS["alpha_025"], variant, cfg)
    roles = RoleAssignment.from_index(TEAM_SIZE, mission.nominal_spacing)
    widths = {
        i: derived_forward_sector_half_width(
            roles.role_of(i, KEEP), roles.role_of(i, LINE), platform, mission)
        for i in range(TEAM_SIZE)
    }
    episodes = []
    for seed in INITIAL_CONDITION_SEEDS:
        env = SwarmFormationEnv(cfg)
        obs = simulate_reset_to_fixture(env, fixture, seed, cfg)
        # The preserved trace generator used persistent-index roles and the
        # pre-repair four-round propagation settings.  Only this diagnostic
        # context binds the retired detector.
        old_consensus = ConsensusParams(k_trigger=4, k_confirm=4)
        with _preserved_old_detector():
            result = simulate_decentralized_episode(
                cfg, fixture_layout(fixture), TEAM_SIZE, seed,
                mode_rule="geometric", recovery_event="v3",
                role_source="index", cons=old_consensus,
                trace_positions=True, trace_modes=True,
                preset_env=env, preset_obs=obs)

        frozen = _frozen_trace_rows(seed)
        positions = result["position_trace"]
        common = min(len(frozen), len(positions))
        max_along_error = 0.0
        old_raw_mismatches = 0
        per_step: list[Dict[int, Dict[str, Any]]] = []
        for step, pos in enumerate(positions):
            robot_rows: Dict[int, Dict[str, Any]] = {}
            for robot_id in range(TEAM_SIZE):
                local = simulate_local_obstacles(
                    tuple(pos[robot_id]), result["obstacles"],
                    cfg.env.obstacle_radius, platform.obstacle_sensor_range)
                blocked_a = [p for p in local
                             if p[0] > 0.0
                             and abs(p[1]) <= OLD_FORWARD_SECTOR_HALF_WIDTH_M]
                blocked_b = [p for p in local
                             if p[0] > 0.0 and abs(p[1]) <= widths[robot_id]]
                robot_rows[robot_id] = {
                    "old_open": not blocked_a,
                    "new_open": not blocked_b,
                    "local_obstacles": local,
                }
                if step < common:
                    saved = frozen[step]["robots"][robot_id]
                    max_along_error = max(
                        max_along_error,
                        abs(float(pos[robot_id][0]) - float(saved["along"])))
                    old_raw_mismatches += int(
                        bool(saved["raw_opening"]) != (not blocked_a))
            per_step.append(robot_rows)

        line_steps = [int(s) for s, modes in result["mode_trace"]
                      if all(int(m) == LINE for m in modes)]
        keep_steps = [int(s) for s, modes in result["mode_trace"]
                      if all(int(m) == KEEP for m in modes)]
        entry_commit = min(line_steps) if line_steps else None
        recovery_commit = min(
            (s for s in keep_steps
             if entry_commit is not None and s > entry_commit), default=None)
        if entry_commit is None:
            raise RuntimeError(f"old frozen trace seed {seed} never entered LINE")

        robot_reports = []
        for robot_id in range(TEAM_SIZE):
            first_a = _first_step(
                (step, per_step[step][robot_id]["old_open"])
                for step in range(entry_commit, len(per_step)))
            first_b = _first_step(
                (step, per_step[step][robot_id]["new_open"])
                for step in range(entry_commit, len(per_step)))
            b_only: Dict[int, Dict[str, Any]] = {}
            for step in range(entry_commit, len(per_step)):
                pos = positions[step][robot_id]
                for obstacle_index, obstacle in enumerate(result["obstacles"]):
                    rel = np.asarray(obstacle, dtype=float) - np.asarray(pos, dtype=float)
                    admitted_b = (rel[0] > 0.0
                                  and abs(float(rel[1])) <= widths[robot_id]
                                  and float(np.linalg.norm(rel))
                                  <= platform.obstacle_sensor_range)
                    excluded_a = abs(float(rel[1])) > OLD_FORWARD_SECTOR_HALF_WIDTH_M
                    if not (admitted_b and excluded_a):
                        continue
                    item = b_only.setdefault(obstacle_index, {
                        "obstacle_index": obstacle_index,
                        "world_point_m": [float(obstacle[0]), float(obstacle[1])],
                        "first_admitted_step": step,
                        "last_admitted_step": step,
                        "relative_point_at_first_admission_m":
                            [float(rel[0]), float(rel[1])],
                        "intersects_future_keep_expansion_region": True,
                    })
                    item["last_admitted_step"] = step
            robot_reports.append({
                "robot_id": robot_id,
                "detector_A_half_width_m": OLD_FORWARD_SECTOR_HALF_WIDTH_M,
                "detector_B_half_width_m": widths[robot_id],
                "first_forward_opening_evidence_step_A": first_a,
                "first_forward_opening_evidence_step_B": first_b,
                "timing_difference_B_minus_A_steps": (
                    None if first_a is None or first_b is None
                    else first_b - first_a),
                "obstacle_points_admitted_by_B_excluded_by_A":
                    list(b_only.values()),
                "B_only_point_count": len(b_only),
                "any_B_only_point_intersects_future_KEEP_expansion_region":
                    bool(b_only),
            })
        episodes.append({
            "seed": seed,
            "variant": variant["id"],
            "frozen_trace_source":
                "results/recovery_propagation_latency/alpha_025_trace.jsonl",
            "frozen_trace_steps": len(frozen),
            "diagnostic_replay_steps": len(positions),
            "exact_trace_common_steps": common,
            "maximum_along_coordinate_error_m": max_along_error,
            "old_raw_opening_mismatch_count": old_raw_mismatches,
            "entry_commit_step": entry_commit,
            "old_recovery_commit_step": recovery_commit,
            "robots": robot_reports,
        })

    validation = {
        "schema_version": "role_dependent_opening_detector_validation_v1",
        "source_commit": _git("rev-parse", f"{SOURCE_TAG}^{{commit}}"),
        "diagnostic_only": True,
        "deployable_runtime_detector": "B_role_dependent",
        "detector_A": {
            "name": "preserved_old_literal",
            "half_width_m": OLD_FORWARD_SECTOR_HALF_WIDTH_M,
        },
        "detector_B": {
            "name": "role_dependent_geometric_derivation",
            "formula": ("abs(KEEP_lateral - LINE_lateral) + "
                        "collision_clearance + safety_margin"),
        },
        "role_geometry": _role_detector_geometry(),
        "alpha_025_frozen_trace_comparison": episodes,
        "strict_runtime_guard_violations": guards.audit(),
    }
    _write_json(DETECTOR_PATH, validation)
    return validation


def _path_graph(n: int) -> Dict[int, list[int]]:
    return {i: [j for j in (i - 1, i + 1) if 0 <= j < n]
            for i in range(n)}


def _propagation_check(n: int, rounds: int) -> Dict[str, Any]:
    graph = _path_graph(n)
    epochs = {i: E.EpochState(robot_id=i) for i in range(n)}
    epochs[0].arm_trigger(0)
    E.simulate_trigger_consensus(
        epochs, graph, rounds, start_step=0, record_history=False)
    trigger_ok = all(e.trigger_token is not None for e in epochs.values())
    epoch_ids = {e.epoch_id for e in epochs.values()}

    for e in epochs.values():
        e.begin_scoring()
        e.begin_confirming(LINE, 1.0)
    E.simulate_confirm_consensus(
        epochs, graph, rounds, start_step=0, record_history=False)
    unanimous_commits = [E.commit_or_retain(e, 0, ConsensusParams(
        k_trigger=rounds, k_confirm=rounds)) for e in epochs.values()]

    disagreement = {i: E.EpochState(robot_id=i) for i in range(n)}
    disagreement[0].arm_trigger(0)
    E.simulate_trigger_consensus(
        disagreement, graph, rounds, start_step=0, record_history=False)
    for i, e in disagreement.items():
        e.begin_scoring()
        e.begin_confirming(KEEP if i == n - 1 else LINE, 1.0)
    E.simulate_confirm_consensus(
        disagreement, graph, rounds, start_step=0, record_history=False)
    refused = [not E.commit_or_retain(e, 0, ConsensusParams(
        k_trigger=rounds, k_confirm=rounds)) for e in disagreement.values()]
    return {
        "topology": "path",
        "diameter_hops": n - 1,
        "configured_rounds": rounds,
        "trigger_reached_all": trigger_ok,
        "trigger_epoch_agreement": len(epoch_ids) == 1,
        "unanimous_confirmation_committed_all": all(unanimous_commits),
        "one_dissenter_refused_all_commits": all(refused),
        "contract_satisfied": bool(
            trigger_ok and len(epoch_ids) == 1
            and all(unanimous_commits) and all(refused)),
    }


def run_mechanical_checks() -> Dict[str, Any]:
    verify_manifest()
    guards.set_strict(True)
    base_platform, base_mission, _ = default_parameters(fixture_config().env)
    records = []
    for n in (5, 6, 8):
        protocol = ProtocolParams(max_team_size=n)
        rounds = derived_k_trigger(protocol)
        support = check_team_size(
            n, base_platform, base_mission, protocol)
        roles = RoleAssignment.from_index(n, base_mission.nominal_spacing)
        K = np.asarray(roles.coords(KEEP), dtype=float)
        L = np.asarray(roles.coords(LINE), dtype=float)
        K -= K.mean(axis=0)
        L -= L.mean(axis=0)
        widths = [derived_forward_sector_half_width(
            tuple(K[i]), tuple(L[i]), base_platform, base_mission)
            for i in range(n)]
        wider_spacing = dataclasses.replace(
            base_mission,
            nominal_spacing=1.5 * base_mission.nominal_spacing)
        spacing_roles = RoleAssignment.from_index(
            n, wider_spacing.nominal_spacing)
        Ks = np.asarray(spacing_roles.coords(KEEP), dtype=float)
        Ls = np.asarray(spacing_roles.coords(LINE), dtype=float)
        Ks -= Ks.mean(axis=0)
        Ls -= Ls.mean(axis=0)
        spacing_widths = [derived_forward_sector_half_width(
            tuple(Ks[i]), tuple(Ls[i]), base_platform, wider_spacing)
            for i in range(n)]
        wider_clearance_platform = dataclasses.replace(
            base_platform,
            collision_clearance_obstacle=(
                base_platform.collision_clearance_obstacle + 0.25))
        clearance_widths = [derived_forward_sector_half_width(
            tuple(K[i]), tuple(L[i]), wider_clearance_platform, base_mission)
            for i in range(n)]
        width_rows = []
        for i, width in enumerate(widths):
            width_rows.append({
                "robot_id": i,
                "keep_role_m": K[i].tolist(),
                "line_role_m": L[i].tolist(),
                "derived_half_width_m": width,
                "observable_under_R_obs": bool(
                    width <= base_platform.obstacle_sensor_range),
            })
        records.append({
            "team_size": n,
            "roles_generated": len(roles.keep) == n and len(roles.line) == n,
            "role_count": n,
            "widths": width_rows,
            "outer_roles_wider_than_centre_when_required": bool(
                max(widths) > min(widths)),
            "widths_increase_with_spacing": bool(
                max(spacing_widths) > max(widths)),
            "widths_increase_with_collision_clearance": bool(
                all(math.isclose(clearance_widths[i] - widths[i], 0.25,
                                 abs_tol=1e-12) for i in range(n))),
            "maximum_required_half_width_m": max(widths),
            "R_obs_m": base_platform.obstacle_sensor_range,
            "all_required_sectors_observable": bool(
                all(w <= base_platform.obstacle_sensor_range for w in widths)),
            "unsupported_configuration_result": _jsonable(support),
            "propagation": _propagation_check(n, rounds),
        })
    result = {
        "schema_version": "mechanical_parameterization_checks_v1",
        "closed_loop_claim": "N=6 only; these are construction tests",
        "team_sizes": records,
        "strict_runtime_guard_violations": guards.audit(),
    }
    _write_json(MECHANICAL_PATH, result)
    return result


def _transition_records(result: Mapping[str, Any]) -> list[Dict[str, Any]]:
    current = KEEP
    transitions = []
    for step, modes in result["mode_trace"]:
        unique = {int(mode) for mode in modes}
        if len(unique) != 1:
            continue
        new_mode = unique.pop()
        if new_mode == current:
            continue
        transitions.append({
            "step": int(step),
            "from": "KEEP" if current == KEEP else "LINE",
            "to": "KEEP" if new_mode == KEEP else "LINE",
        })
        current = new_mode
    return transitions


def _first_run(values: list[bool], length: int,
               start: int = 0) -> tuple[int | None, int | None]:
    streak = 0
    for step in range(max(0, int(start)), len(values)):
        streak = streak + 1 if values[step] else 0
        if streak >= length:
            return step - length + 1, step
    return None, None


def _local_obstacles_at(position: np.ndarray, obstacles: np.ndarray,
                        cfg, platform: PlatformParams):
    return simulate_local_obstacles(
        (float(position[0]), float(position[1])), obstacles,
        cfg.env.obstacle_radius, platform.obstacle_sensor_range)


def _wall_constraint_at_commit(
        position: np.ndarray, obstacles: np.ndarray, keep_role,
        line_role, width: float, cfg, platform: PlatformParams,
        mission: MissionParams) -> Dict[str, Any]:
    local = _local_obstacles_at(position, obstacles, cfg, platform)
    delta = float(keep_role[1]) - float(line_role[1])
    lo, hi = sorted((0.0, delta))
    forward = []
    swept = []
    for index, point in enumerate(local):
        x, y, _ = point
        if x > 0.0 and abs(y) <= width:
            forward.append({"local_obstacle_index": index,
                            "relative_point_m": [x, y]})
        nearest_lateral = min(max(y, lo), hi)
        distance_to_swept_segment = math.hypot(x, y - nearest_lateral)
        if distance_to_swept_segment <= (
                platform.collision_clearance_obstacle
                + mission.safety_margin):
            swept.append({
                "local_obstacle_index": index,
                "relative_point_m": [x, y],
                "distance_to_lateral_swept_segment_m":
                    distance_to_swept_segment,
            })
    return {
        "forward_sector_wall_material_present": bool(forward),
        "forward_sector_wall_points": forward,
        "lateral_swept_region_wall_material_present": bool(swept),
        "lateral_swept_region_wall_points": swept,
        "still_locally_wall_constrained": bool(forward or swept),
    }


def _score_episode(result: Mapping[str, Any], geo, roles: RoleAssignment,
                   cfg, *, detailed: bool) -> Dict[str, Any]:
    positions = [np.asarray(p, dtype=float) for p in result["position_trace"]]
    mission = np.asarray(result["mission_dir"], dtype=float)
    mission /= max(float(np.linalg.norm(mission)), 1e-12)
    lateral_axis = np.array([-mission[1], mission[0]], dtype=float)
    e_keep = [float(e_inf(p, roles, KEEP, result["mission_dir"]))
              for p in positions]
    crossed_step = next((
        step for step, pos in enumerate(positions)
        if float((pos @ mission).min()) >= geo.exit_x), None)
    goal = np.asarray(result["goal"], dtype=float)
    goal_step = next((
        step for step, pos in enumerate(positions)
        if float(np.linalg.norm(goal - pos.mean(axis=0)))
        < cfg.env.goal_tolerance), None)
    in_keep_recovery_tube = [
        bool(e_keep[step] <= EPSILON_FORM
             and float((pos @ mission).min()) >= geo.recovery_x0)
        for step, pos in enumerate(positions)
    ]
    platform, mission_params, protocol = default_parameters(cfg.env)
    dwell_steps = derived_recovery_dwell_steps(mission_params, platform)
    keep_entry = next((
        step for step, inside in enumerate(in_keep_recovery_tube)
        if inside), None)
    dwell_start, dwell_complete = _first_run(
        in_keep_recovery_tube, dwell_steps,
        start=0 if crossed_step is None else crossed_step)
    transitions = _transition_records(result)
    k2l = [x["step"] for x in transitions
           if x["from"] == "KEEP" and x["to"] == "LINE"]
    l2k = [x["step"] for x in transitions
           if x["from"] == "LINE" and x["to"] == "KEEP"]
    successful_epochs = len(transitions)
    total_epochs = int(result["n_decisions"])
    no_op_epochs = int(result["n_noop_epochs"])
    retry_epochs = max(total_epochs - successful_epochs - no_op_epochs, 0)
    protocol_bytes = int(sum(
        int(category["bytes"])
        for category in result["comm"]["categories"].values()))
    collision_free = bool(float(result["collision_free"]) > 0.5)
    goal_reached = bool(float(result["goal_reached"]) > 0.5)
    full = bool(crossed_step is not None and collision_free and goal_reached
                and dwell_complete is not None)
    row: Dict[str, Any] = {
        "bottleneck_crossing": crossed_step is not None,
        "bottleneck_crossing_step": crossed_step,
        "collision_free": collision_free,
        "goal_reaching": goal_reached,
        "goal_reaching_step": goal_step,
        "KEEP_tube_entry": keep_entry is not None,
        "KEEP_tube_entry_step": keep_entry,
        "recovery_dwell_completion": dwell_complete is not None,
        "recovery_dwell_start_step": dwell_start,
        "recovery_dwell_completion_step": dwell_complete,
        "full_reconfiguration_success": full,
        "successful_epochs": successful_epochs,
        "retry_epochs": retry_epochs,
        "no_op_epochs": no_op_epochs,
        "total_epochs": total_epochs,
        "protocol_bytes": protocol_bytes,
        "transitions": transitions,
        "KEEP_to_LINE_transition_count": len(k2l),
        "LINE_to_KEEP_transition_count": len(l2k),
    }
    if not detailed:
        return row

    entry_commit = k2l[0] if k2l else None
    recovery_commit = l2k[0] if l2k else None
    role_widths = {
        i: derived_forward_sector_half_width(
            roles.role_of(i, KEEP), roles.role_of(i, LINE),
            platform, mission_params)
        for i in range(TEAM_SIZE)
    }
    first_opening: Dict[int, int | None] = {}
    recovery_evidence: Dict[int, int | None] = {}
    lock_release = (None if entry_commit is None else
                    entry_commit + derived_commitment_steps(protocol, platform))
    persistence = derived_evidence_persistence_steps(protocol, platform)
    for robot_id in range(TEAM_SIZE):
        raw = []
        for step, pos in enumerate(positions):
            local = _local_obstacles_at(
                pos[robot_id], np.asarray(result["obstacles"]), cfg, platform)
            blocked = any(
                x > 0.0 and abs(y) <= role_widths[robot_id]
                for x, y, _ in local)
            raw.append(not blocked)
        start = 0 if entry_commit is None else entry_commit
        first_opening[robot_id] = next((
            step for step in range(start, len(raw)) if raw[step]), None)
        if lock_release is None:
            recovery_evidence[robot_id] = None
        else:
            _, completed = _first_run(raw, persistence, start=lock_release)
            recovery_evidence[robot_id] = completed

    wall_constraints = []
    expansion_velocity = []
    if recovery_commit is not None and recovery_commit < len(positions):
        for robot_id in range(TEAM_SIZE):
            constraint = _wall_constraint_at_commit(
                positions[recovery_commit][robot_id],
                np.asarray(result["obstacles"]),
                roles.role_of(robot_id, KEEP),
                roles.role_of(robot_id, LINE), role_widths[robot_id],
                cfg, platform, mission_params)
            constraint["robot_id"] = robot_id
            constraint["outer_role"] = bool(
                abs(float(roles.role_of(robot_id, KEEP)[1])
                    - float(roles.role_of(robot_id, LINE)[1])) > 1e-12)
            wall_constraints.append(constraint)
            if recovery_commit + 1 < len(positions):
                velocity = ((positions[recovery_commit + 1][robot_id]
                             - positions[recovery_commit][robot_id])
                            / platform.control_period)
                lateral_velocity = float(velocity @ lateral_axis)
            else:
                lateral_velocity = None
            delta = (float(roles.role_of(robot_id, KEEP)[1])
                     - float(roles.role_of(robot_id, LINE)[1]))
            outward_velocity = (
                None if lateral_velocity is None else
                (abs(lateral_velocity) if abs(delta) <= 1e-12
                 else math.copysign(1.0, delta) * lateral_velocity))
            expansion_velocity.append({
                "robot_id": robot_id,
                "lateral_velocity_m_s": lateral_velocity,
                "outward_expansion_velocity_m_s": outward_velocity,
                "expansion_started": bool(
                    abs(delta) > 1e-12 and outward_velocity is not None
                    and outward_velocity > 1e-9),
            })

    row.update({
        "first_ENTRY_evidence_step": entry_commit,
        "KEEP_to_LINE_proposal_step": entry_commit,
        "KEEP_to_LINE_commitment_step": entry_commit,
        "first_forward_opening_evidence_per_robot": {
            str(i): first_opening[i] for i in range(TEAM_SIZE)},
        "role_dependent_detector_width_m_per_robot": {
            str(i): role_widths[i] for i in range(TEAM_SIZE)},
        "first_RECOVERY_evidence_step": min(
            (step for step in recovery_evidence.values()
             if step is not None), default=None),
        "first_RECOVERY_evidence_step_per_robot": {
            str(i): recovery_evidence[i] for i in range(TEAM_SIZE)},
        "RECOVERY_proposal_step": recovery_commit,
        "LINE_to_KEEP_commitment_step": recovery_commit,
        "robot_positions_at_recovery_commitment_m": (
            None if recovery_commit is None
            else positions[recovery_commit].tolist()),
        "wall_constraint_at_recovery_commitment_per_robot": wall_constraints,
        "lateral_expansion_velocity_after_commitment_per_robot":
            expansion_velocity,
        "simultaneous_mode_commitments_only": all(
            len({int(mode) for mode in modes}) == 1
            for _, modes in result["mode_trace"]),
        "communication_or_confirmation_disagreements": int(
            result["n_disagreement_events"]),
        "disagreement_fraction": float(result["disagreement_fraction"]),
    })
    return row


def _aggregate_rows(rows: list[Mapping[str, Any]]) -> Dict[str, Any]:
    if not rows:
        raise ValueError("cannot aggregate an empty episode list")
    rate_keys = (
        "bottleneck_crossing", "collision_free", "goal_reaching",
        "KEEP_tube_entry", "recovery_dwell_completion",
        "full_reconfiguration_success",
    )
    out = {}
    for key in rate_keys:
        available = [row[key] for row in rows if row.get(key) is not None]
        out[key + "_rate"] = (
            None if not available
            else float(np.mean([bool(value) for value in available])))
    out.update({
        "episode_count": len(rows),
        "median_total_epochs": float(statistics.median(
            int(row["total_epochs"]) for row in rows)),
        "successful_epochs_total": int(sum(
            int(row["successful_epochs"]) for row in rows)),
        "retry_epochs_total": int(sum(
            int(row["retry_epochs"]) for row in rows)),
        "no_op_epochs_total": int(sum(
            int(row["no_op_epochs"]) for row in rows)),
        "mean_protocol_bytes": float(np.mean([
            int(row["protocol_bytes"]) for row in rows])),
    })
    return out


def _arm_record(rows: list[Dict[str, Any]]) -> Dict[str, Any]:
    by_alpha = {}
    for alpha_name in ALPHAS:
        selected = [row for row in rows if row["alpha_cell"] == alpha_name]
        by_alpha[alpha_name] = _aggregate_rows(selected)
    return {
        "per_episode": rows,
        "by_alpha": by_alpha,
        "pooled": _aggregate_rows(rows),
    }


def _preserved_v3_rows() -> list[Dict[str, Any]]:
    published = json.loads(PRE_REPAIR_RESULTS.read_text())
    rows = []
    for alpha_name in ALPHAS:
        arm = published[alpha_name]["arms"]["4_v3_final_repair"]
        for old in arm["per_episode"]:
            row = {
                "alpha_cell": alpha_name,
                "alpha": ALPHAS[alpha_name],
                "variant": old["variant"],
                "initial_condition_seed": int(old["seed"]),
                "disturbance_seed": int(old["seed"]),
                "communication_seed": int(old["seed"]),
                "bottleneck_crossing": bool(old["crossed"]),
                "bottleneck_crossing_step": None,
                "collision_free": bool(old["collision_free"]),
                "goal_reaching": None,
                "goal_reaching_step": None,
                "KEEP_tube_entry": None,
                "KEEP_tube_entry_step": None,
                "recovery_dwell_completion": bool(old["dwell"]),
                "recovery_dwell_start_step": None,
                "recovery_dwell_completion_step": None,
                "full_reconfiguration_success": bool(old["full"]),
                "successful_epochs": int(old["k2l"] + old["l2k"]),
                "retry_epochs": max(
                    int(old["epochs"] - old["k2l"] - old["l2k"]
                        - old["noop"]), 0),
                "no_op_epochs": int(old["noop"]),
                "total_epochs": int(old["epochs"]),
                "protocol_bytes": int(old["bytes"]),
                "transitions": [],
                "KEEP_to_LINE_transition_count": int(old["k2l"]),
                "LINE_to_KEEP_transition_count": int(old["l2k"]),
                "preserved_recovery_commit_step": old["commit_step"],
            }
            rows.append(row)
    return rows


def run_closed_loop_regression() -> Dict[str, Any]:
    verify_manifest()
    if not DETECTOR_PATH.exists() or not MECHANICAL_PATH.exists():
        raise RuntimeError(
            "run --detector-only and --mechanical-only before closed loop")
    guards.set_strict(True)
    if guards.audit():
        raise RuntimeError(f"strict guard violations: {guards.audit()}")
    cfg = fixture_config()
    arms: Dict[str, list[Dict[str, Any]]] = {
        "always_KEEP": [],
        "always_LINE": [],
        "corrected_parameterized_V3": [],
    }
    for alpha_name, alpha in ALPHAS.items():
        for variant in GEOMETRY_VARIANTS:
            geo, fixture = _passage_fixture(alpha_name, alpha, variant, cfg)
            for seed in INITIAL_CONDITION_SEEDS:
                initial_validation = validate_initial_conditions(
                    fixture, seed, cfg, comm_radius=CommParams().r_comm)
                common = {
                    "alpha_cell": alpha_name,
                    "alpha": alpha,
                    "variant": variant["id"],
                    "geometry_sha256": fixture_layout(fixture).geometry_hash(),
                    "initial_condition_seed": seed,
                    "disturbance_seed": seed,
                    "communication_seed": seed,
                    "initial_condition_validation": initial_validation,
                }
                for arm_name, forced_mode, detailed in (
                    ("always_KEEP", KEEP, False),
                    ("always_LINE", LINE, False),
                    ("corrected_parameterized_V3", None, True),
                ):
                    env = SwarmFormationEnv(cfg)
                    obs = simulate_reset_to_fixture(env, fixture, seed, cfg)
                    mission_dir = (float(obs["corridor_dx"]),
                                   float(obs["corridor_dy"]))
                    roles = RoleAssignment.simulate_mission_setup_from_initial_formation(
                        obs["positions"], mission_dir,
                        cfg.env.nominal_spacing)
                    result = simulate_decentralized_episode(
                        cfg, fixture_layout(fixture), TEAM_SIZE, seed,
                        mode_rule="geometric", recovery_event="v3",
                        forced_mode=forced_mode,
                        trace_positions=True, trace_modes=True,
                        preset_env=env, preset_obs=obs)
                    scored = _score_episode(
                        result, geo, roles, cfg, detailed=detailed)
                    arms[arm_name].append({**common, **scored})
                print(
                    alpha_name, variant["id"], f"seed={seed}",
                    "corrected_full=",
                    int(arms["corrected_parameterized_V3"][-1]
                        ["full_reconfiguration_success"]),
                    flush=True)

    all_arms = {
        "always_KEEP": _arm_record(arms["always_KEEP"]),
        "always_LINE": _arm_record(arms["always_LINE"]),
        "preserved_pre_parameter_repair_V3": _arm_record(
            _preserved_v3_rows()),
        "corrected_parameterized_V3": _arm_record(
            arms["corrected_parameterized_V3"]),
    }
    output = {
        "schema_version": "post_parameter_repair_closed_loop_v1",
        "source_commit": _git("rev-parse", f"{SOURCE_TAG}^{{commit}}"),
        "manifest_content_sha256": verify_manifest()[
            "manifest_content_sha256"],
        "frozen_episode_count_per_arm": 30,
        "final_test_layout_access": False,
        "learned_selector": False,
        "controller_changed": False,
        "corridor_geometry_changed": False,
        "parameter_tuning_from_results": False,
        "arms": all_arms,
        "strict_runtime_guard_violations": guards.audit(),
    }
    _write_json(CLOSED_LOOP_PATH, output)
    return output


FAILURE_CATEGORIES = {
    "A": "forward-opening detector still declares safe space too early",
    "B": ("outer-role expansion begins while wall material remains inside "
          "its derived future expansion region"),
    "C": ("detector is correct, but simultaneous KEEP commitment is "
          "physically unsafe"),
    "D": ("recovery begins safely but insufficient downstream distance "
          "remains"),
    "E": "communication or confirmation disagreement",
    "F": "local controller fails to converge",
    "G": "collision avoidance prevents crossing or recovery",
    "H": "invalid initial condition or geometry",
    "I": "metric or evaluator defect",
    "J": "other confirmed cause",
}


def analyze_failures_and_gates() -> tuple[Dict[str, Any], Dict[str, Any]]:
    verify_manifest()
    detector = json.loads(DETECTOR_PATH.read_text())
    mechanical = json.loads(MECHANICAL_PATH.read_text())
    closed = json.loads(CLOSED_LOOP_PATH.read_text())
    corrected = closed["arms"]["corrected_parameterized_V3"]
    failures = []
    for row in corrected["per_episode"]:
        if row["full_reconfiguration_success"]:
            continue
        category = None
        evidence: Dict[str, Any] = {}
        if not row["initial_condition_validation"]["valid"]:
            category = "H"
            evidence = {"initial_condition_validation":
                        row["initial_condition_validation"]}
        elif (row["communication_or_confirmation_disagreements"] > 0
              or not row["simultaneous_mode_commitments_only"]):
            category = "E"
            evidence = {
                "communication_or_confirmation_disagreements":
                    row["communication_or_confirmation_disagreements"],
                "simultaneous_mode_commitments_only":
                    row["simultaneous_mode_commitments_only"],
            }
        else:
            constrained_outer = [
                item for item in
                row["wall_constraint_at_recovery_commitment_per_robot"]
                if item["outer_role"]
                and item["still_locally_wall_constrained"]
            ]
            if (row["LINE_to_KEEP_commitment_step"] is not None
                    and constrained_outer):
                category = "B"
                evidence = {
                    "LINE_to_KEEP_commitment_step":
                        row["LINE_to_KEEP_commitment_step"],
                    "first_RECOVERY_evidence_step":
                        row["first_RECOVERY_evidence_step"],
                    "originating_safe_centre_roles": [
                        int(robot_id) for robot_id, step in
                        row["first_RECOVERY_evidence_step_per_robot"].items()
                        if step == row["first_RECOVERY_evidence_step"]
                    ],
                    "locally_constrained_outer_robot_ids": [
                        item["robot_id"] for item in constrained_outer],
                    "outer_forward_sector_wall_material": {
                        str(item["robot_id"]):
                            item["forward_sector_wall_material_present"]
                        for item in constrained_outer
                    },
                    "mode_commit_begins_KEEP_expansion_for_all_roles": True,
                    "lateral_velocity_after_commitment":
                        row[
                            "lateral_expansion_velocity_after_commitment_per_robot"],
                    "bottleneck_crossing": row["bottleneck_crossing"],
                }
            elif (row["bottleneck_crossing"]
                  and row["LINE_to_KEEP_commitment_step"] is not None
                  and not row["recovery_dwell_completion"]):
                category = "D"
                evidence = {
                    "bottleneck_crossing_step": row["bottleneck_crossing_step"],
                    "LINE_to_KEEP_commitment_step":
                        row["LINE_to_KEEP_commitment_step"],
                    "KEEP_tube_entry_step": row["KEEP_tube_entry_step"],
                    "recovery_dwell_completion": False,
                }
            elif (row["LINE_to_KEEP_commitment_step"] is not None
                  and not row["bottleneck_crossing"]):
                category = "C"
                evidence = {
                    "LINE_to_KEEP_commitment_step":
                        row["LINE_to_KEEP_commitment_step"],
                    "no_outer_wall_constraint_detected": True,
                    "bottleneck_crossing": False,
                }
            else:
                category = "J"
                evidence = {
                    "confirmed_observations": {
                        "bottleneck_crossing": row["bottleneck_crossing"],
                        "LINE_to_KEEP_commitment_step":
                            row["LINE_to_KEEP_commitment_step"],
                        "recovery_dwell_completion":
                            row["recovery_dwell_completion"],
                    }
                }
        if category not in FAILURE_CATEGORIES:
            raise RuntimeError(f"failed episode has no valid category: {row}")
        failures.append({
            "alpha_cell": row["alpha_cell"],
            "variant": row["variant"],
            "seed": row["initial_condition_seed"],
            "primary_category": category,
            "category_definition": FAILURE_CATEGORIES[category],
            "evidence": evidence,
        })
    counts = {key: sum(
        item["primary_category"] == key for item in failures)
        for key in FAILURE_CATEGORIES}
    attribution = {
        "schema_version": "post_parameter_repair_failure_attribution_v1",
        "failed_episode_count": len(failures),
        "primary_category_counts": counts,
        "categories": FAILURE_CATEGORIES,
        "per_failed_episode": failures,
        "safe_expansion_certificate_conclusion_rule": (
            "A certificate is considered only after detector geometry passes "
            "and a failed corrected-runtime episode shows locally constrained "
            "outer roles at the common KEEP commit."),
    }
    _write_json(ATTRIBUTION_PATH, attribution)

    detector_geometry_pass = all(
        role["complete_future_expansion_region_observed"]
        for role in detector["role_geometry"])
    no_unexplained_detector_literal = (
        detector["deployable_runtime_detector"] == "B_role_dependent"
        and not detector["strict_runtime_guard_violations"])
    p1 = detector_geometry_pass and no_unexplained_detector_literal
    p2 = (not closed["strict_runtime_guard_violations"]
          and not detector["strict_runtime_guard_violations"]
          and not mechanical["strict_runtime_guard_violations"])
    p3_mechanical = all(
        item["propagation"]["contract_satisfied"]
        for item in mechanical["team_sizes"])
    p3_runtime = all(
        row["simultaneous_mode_commitments_only"]
        and row["communication_or_confirmation_disagreements"] == 0
        for row in corrected["per_episode"])
    p3 = p3_mechanical and p3_runtime
    pooled = corrected["pooled"]
    p4 = (pooled["bottleneck_crossing_rate"] >= 0.80
          and pooled["collision_free_rate"] >= 0.95)
    p5 = (pooled["recovery_dwell_completion_rate"] >= 0.70
          and pooled["full_reconfiguration_success_rate"] >= 0.70)
    successful = [row for row in corrected["per_episode"]
                  if row["full_reconfiguration_success"]]
    successful_transition_contract = all(
        row["KEEP_to_LINE_transition_count"] == 1
        and row["LINE_to_KEEP_transition_count"] == 1
        for row in successful)
    p6 = (pooled["no_op_epochs_total"] == 0
          and pooled["median_total_epochs"] <= 3
          and successful_transition_contract)
    alpha025 = corrected["by_alpha"]["alpha_025"]

    if p1 and p3 and p4 and p5:
        decision_case = "CASE_1"
        verdict = "C"
        verdict_text = (
            "The detector correction alone makes fully decentralized "
            "reconfiguration mechanically valid across the frozen "
            "three-cell set.")
    elif (p1 and counts["B"] > 0
          and alpha025["full_reconfiguration_success_rate"] < 0.70):
        decision_case = "CASE_2"
        verdict = "B"
        verdict_text = (
            "The detector is now correct, but a distributed safe-expansion "
            "certificate is still necessary.")
    elif p1 and not p4 and counts["C"] == len(failures):
        decision_case = "CASE_3"
        verdict = "A"
        verdict_text = (
            "The parameter repair does not resolve the closed-loop failure, "
            "and the remaining cause is not yet understood.")
    elif counts["H"] or counts["I"]:
        decision_case = "CASE_4"
        verdict = "E" if counts["I"] else "D"
        verdict_text = (
            "The regression evaluation is invalid." if verdict == "E" else
            "The failure is caused by another confirmed controller, geometry, "
            "communication or evaluation defect.")
    else:
        decision_case = "CASE_4"
        verdict = "D"
        verdict_text = (
            "The failure is caused by another confirmed controller, geometry, "
            "communication or evaluation defect.")

    gates = {
        "schema_version": "post_parameter_repair_regression_gates_v1",
        "P1_detector_geometry": {
            "pass": p1,
            "complete_role_specific_coverage": detector_geometry_pass,
            "no_unexplained_runtime_detector_literal":
                no_unexplained_detector_literal,
        },
        "P2_decentralization": {
            "pass": p2,
            "strict_runtime_guard_violations":
                closed["strict_runtime_guard_violations"],
            "global_exit_plane_runtime_access": False,
            "global_centroid_runtime_access": False,
            "centralized_event_trigger": False,
            "robot_local_action_computation": True,
        },
        "P3_propagation_correctness": {
            "pass": p3,
            "mechanical_topology_contract": p3_mechanical,
            "closed_loop_no_partial_commitment": p3_runtime,
        },
        "P4_closed_loop_passage": {
            "pass": p4,
            "thresholds": {"bottleneck_crossing_rate": 0.80,
                           "collision_free_rate": 0.95},
            "measured": {
                "bottleneck_crossing_rate":
                    pooled["bottleneck_crossing_rate"],
                "collision_free_rate": pooled["collision_free_rate"],
            },
        },
        "P5_full_reconfiguration": {
            "pass": p5,
            "thresholds": {"KEEP_recovery_dwell_rate": 0.70,
                           "full_reconfiguration_success_rate": 0.70},
            "measured": {
                "KEEP_recovery_dwell_rate":
                    pooled["recovery_dwell_completion_rate"],
                "full_reconfiguration_success_rate":
                    pooled["full_reconfiguration_success_rate"],
            },
        },
        "P6_epoch_control": {
            "pass": p6,
            "no_op_epochs": pooled["no_op_epochs_total"],
            "median_total_epochs": pooled["median_total_epochs"],
            "successful_episode_transition_contract":
                successful_transition_contract,
        },
        "P7_alpha_025_separate": {
            "pass": True,
            "reported_separately": True,
            "measured": alpha025,
        },
        "per_alpha_corrected_runtime": corrected["by_alpha"],
        "decision_case": decision_case,
        "verdict": verdict,
        "verdict_text": verdict_text,
    }
    _write_json(GATES_PATH, gates)
    return attribution, gates


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest-only", action="store_true")
    parser.add_argument("--detector-only", action="store_true")
    parser.add_argument("--mechanical-only", action="store_true")
    parser.add_argument("--closed-loop", action="store_true")
    parser.add_argument("--analyze-only", action="store_true")
    args = parser.parse_args(argv)
    selected = sum((args.manifest_only, args.detector_only,
                    args.mechanical_only, args.closed_loop,
                    args.analyze_only))
    if selected != 1:
        parser.error("select exactly one phase")
    if args.manifest_only:
        manifest = build_manifest()
        write_immutable_manifest(manifest)
        verify_manifest()
        print(MANIFEST_PATH)
        print(manifest["manifest_content_sha256"])
    elif args.detector_only:
        result = run_detector_validation()
        print(DETECTOR_PATH)
        print(len(result["alpha_025_frozen_trace_comparison"]), "traces")
    elif args.mechanical_only:
        result = run_mechanical_checks()
        print(MECHANICAL_PATH)
        print(len(result["team_sizes"]), "team sizes")
    elif args.closed_loop:
        result = run_closed_loop_regression()
        print(CLOSED_LOOP_PATH)
        pooled = result["arms"]["corrected_parameterized_V3"]["pooled"]
        print(json.dumps(pooled, sort_keys=True))
    elif args.analyze_only:
        attribution, gates = analyze_failures_and_gates()
        print(ATTRIBUTION_PATH)
        print(GATES_PATH)
        print(json.dumps({
            "failure_categories": attribution["primary_category_counts"],
            "decision_case": gates["decision_case"],
            "verdict": gates["verdict"],
        }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
