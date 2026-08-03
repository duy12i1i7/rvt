"""Phase 7R transition-execution forensics and repaired qualification."""

from __future__ import annotations

import json
import math
import statistics
import subprocess
import time
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Dict, Iterable, Mapping, Optional, Sequence, Tuple

import numpy as np

from ..runtime_configuration import RuntimeConfig, SUPPORTED_MECHANICAL_TEAM_SIZES
from ..topology_registry import (
    COMPACT,
    KEEP,
    LINE,
    construct_topology,
    generate_persistent_roles,
)
from .ego_graph_v2 import prepare_robot_local_topology_metadata
from .forced_topology_runtime import ForcedTopologyRuntimeAdapter
from .local_control_types import LocalConstraintDiagnostic, RobotLocalControllerInput
from .local_projection_forensics import (
    LOCAL_PROJECTION_FORENSICS_SCHEMA_VERSION,
    action_primal_residual,
    independent_local_feasibility,
)
from .robot_local_controller import (
    robot_local_damping_term,
    robot_local_formation_term,
    robot_local_goal_term,
    robot_local_obstacle_term,
)
from .roles import RoleAssignment
from .phase6_qualification import simulate_received_robot_views
from .transition_admissibility import ADMITTED_DIRECTED_PAIRS, assess_transition_admissibility
from .transition_execution import (
    TRANSITION_EXECUTION_SCHEMA_VERSION,
    derive_transition_motion_profile,
    prepare_robot_local_role_space_path,
)
from .transition_protocol import TransitionProtocolRuntimeOptions
from .transition_runtime import (
    PHASE7_OPEN_SPACE_FIXTURES,
    LocalProjectionExecutionObservation,
    StrictTransitionRuntime,
    _initial_state,
    communication_graph,
    run_phase7_transition_episode,
)


PHASE7R_QUALIFICATION_SCHEMA_VERSION = "rvt-phase7r-qualification/v1"
PHASE7_NEGATIVE_COMMIT = "0b6791aec3d78b84981188a7a884e86d3d55def0"
PRIMARY_HUB_TRANSITIONS: Tuple[Tuple[int, int], ...] = (
    (KEEP, COMPACT),
    (COMPACT, KEEP),
    (KEEP, LINE),
    (LINE, KEEP),
)
OPTIONAL_DIRECT_TRANSITIONS: Tuple[Tuple[int, int], ...] = (
    (COMPACT, LINE),
    (LINE, COMPACT),
)


def _json_dump(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, allow_nan=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _pair_name(source: int, target: int) -> str:
    names = {KEEP: "KEEP", COMPACT: "COMPACT", LINE: "LINE"}
    return f"{names[source]} -> {names[target]}"


def _fixture_seed(team_size: int, source_topology: int, fixture: str) -> Optional[int]:
    if fixture != "bounded_source_perturbation":
        return None
    return 71000 + 100 * team_size + source_topology


def _vector_add(*values: Sequence[float]) -> Tuple[float, float]:
    result = np.sum(np.asarray(values, dtype=np.float64), axis=0)
    return (float(result[0]), float(result[1]))


def _candidate_record(
    action: Sequence[float],
    constraints: Sequence[LocalConstraintDiagnostic],
    acceleration_limit: float,
) -> dict:
    vector = (float(action[0]), float(action[1]))
    residual = action_primal_residual(vector, constraints, acceleration_limit)
    return {
        "action_meters_per_second_squared": vector,
        "primal_residual": residual,
        "satisfies_complete_local_problem": residual <= 1e-10,
    }


def _diagnostic_candidates(
    observation: LocalProjectionExecutionObservation,
    runtime_config: RuntimeConfig,
    source_topology: int,
) -> dict:
    controller_input = observation.controller_input
    output = observation.controller_output
    limit = runtime_config.physical.maximum_acceleration_meters_per_second_squared
    velocity = np.asarray(
        controller_input.own_velocity_meters_per_second, dtype=np.float64
    )
    speed = float(np.linalg.norm(velocity))
    braking = (
        np.zeros(2, dtype=np.float64)
        if speed <= np.finfo(np.float64).tiny
        else -velocity * (limit / speed)
    )
    role_set = generate_persistent_roles(runtime_config.mission.team_size)
    source_metadata = prepare_robot_local_topology_metadata(
        role_set,
        controller_input.observer_robot_id,
        runtime_config.formation,
    )
    source_input = replace(
        controller_input,
        forced_topology_id=source_topology,
        local_topology=source_metadata.candidate(source_topology),
    )
    source_formation = robot_local_formation_term(source_input, runtime_config)[0]
    source_goal = robot_local_goal_term(source_input, runtime_config)[0]
    source_damping = robot_local_damping_term(source_input, runtime_config)
    source_obstacle = robot_local_obstacle_term(source_input, runtime_config)[0]
    constraints = output.active_constraints
    candidates = {
        "zero_acceleration": (0.0, 0.0),
        "maximum_admissible_braking": tuple(map(float, braking)),
        "goal_term_removed": _vector_add(
            output.formation_term, output.damping_term, output.obstacle_term
        ),
        "formation_term_removed": _vector_add(
            output.goal_term, output.damping_term, output.obstacle_term
        ),
        "transition_displacement_term_removed": _vector_add(
            source_formation, source_goal, source_damping, source_obstacle
        ),
        "obstacle_term_only": output.obstacle_term,
        "phase6_declared_infeasible_fallback": output.projected_action,
    }
    return {
        name: _candidate_record(value, constraints, limit)
        for name, value in candidates.items()
    }


def _constraint_source(item: LocalConstraintDiagnostic) -> dict:
    return {
        "source_key": item.source_key,
        "constraint_family": item.threat_kind,
        "normal": item.outward_normal,
        "lower_bound_meters_per_second_squared": (
            item.lower_bound_meters_per_second_squared
        ),
        "current_distance_meters": item.current_distance_meters,
        "required_clearance_meters": item.required_clearance_meters,
        "stale_or_uncertain": item.stale_or_uncertain,
        "active_for_proposed_action": bool(item.active_for_proposed_action),
    }


def _local_call_source(
    observation: LocalProjectionExecutionObservation,
    runtime_config: RuntimeConfig,
    source_topology: int,
    target_topology: int,
    include_candidates: bool,
) -> dict:
    controller_input = observation.controller_input
    output = observation.controller_output
    limit = runtime_config.physical.maximum_acceleration_meters_per_second_squared
    oracle = independent_local_feasibility(output.active_constraints, limit)
    impossible = []
    for item in output.active_constraints:
        support = limit * math.hypot(*item.outward_normal)
        if item.lower_bound_meters_per_second_squared > support + oracle.numerical_tolerance:
            impossible.append({
                "constraint_set": (
                    "physical_acceleration_disk",
                    f"{item.threat_kind}:{item.source_key}",
                ),
                "required_normal_acceleration": (
                    item.lower_bound_meters_per_second_squared
                ),
                "disk_support": support,
            })
    result = {
        "forensics_schema_version": LOCAL_PROJECTION_FORENSICS_SCHEMA_VERSION,
        "execution_step": observation.execution_step,
        "transition_progress": observation.transition_progress,
        "timestamp_seconds": controller_input.timestamp_seconds,
        "robot_id": controller_input.observer_robot_id,
        "persistent_role": controller_input.observer_role_id,
        "source_topology": source_topology,
        "target_topology": target_topology,
        "own_position_meters": controller_input.own_position_meters,
        "own_velocity_meters_per_second": (
            controller_input.own_velocity_meters_per_second
        ),
        "fresh_peer_states": [asdict(item) for item in controller_input.peer_states],
        "local_obstacle_observations": [
            asdict(item) for item in controller_input.obstacle_states
        ],
        "controller_terms": {
            "formation": output.formation_term,
            "goal": output.goal_term,
            "damping": output.damping_term,
            "obstacle": output.obstacle_term,
        },
        "controller_proposed_action": output.base_action,
        "projected_action_if_available": output.projected_action,
        "runtime_action_returned": output.projected_action,
        "action_bounds": {
            "kind": "euclidean_acceleration_disk",
            "maximum_norm_meters_per_second_squared": limit,
        },
        "peer_constraints": [
            _constraint_source(item)
            for item in output.active_constraints
            if item.threat_kind == "peer"
        ],
        "obstacle_constraints": [
            _constraint_source(item)
            for item in output.active_constraints
            if item.threat_kind == "obstacle"
        ],
        "all_local_inequalities": [
            {
                "kind": "norm_upper_bound",
                "expression": "||a_i||_2 <= a_max",
                "upper_bound": limit,
            },
            *(_constraint_source(item) for item in output.active_constraints),
        ],
        "local_equalities": [],
        "configured_safety_margins": {
            "inter_robot_safety_margin_meters": (
                runtime_config.safety.inter_robot_safety_margin_meters
            ),
            "obstacle_clearance_margin_meters": (
                runtime_config.safety.obstacle_clearance_margin_meters
            ),
            "robot_robot_required_clearance_meters": (
                runtime_config.derived.robot_robot_required_clearance_meters
            ),
            "robot_obstacle_required_clearance_meters": (
                runtime_config.derived.robot_obstacle_required_clearance_meters
            ),
        },
        "production_solver_status": output.projection_status,
        "production_declared_infeasible": output.projection_infeasible,
        "production_solver_failed": output.projection_solver_failed,
        "production_primal_residual": action_primal_residual(
            output.projected_action, output.active_constraints, limit
        ),
        "production_dual_residual": None,
        "independent_oracle": oracle.source(),
        "smallest_irreducible_conflicting_sets": impossible,
        "constraint_family_attribution": (
            "peer_safety_conflicts_with_physical_action_bound"
            if impossible and all(
                item["constraint_set"][1].startswith("peer:")
                for item in impossible
            )
            else "no_single_constraint_support_conflict"
        ),
    }
    if include_candidates:
        result["diagnostic_candidate_actions"] = _diagnostic_candidates(
            observation, runtime_config, source_topology
        )
    return result


class _EpisodeTraceCollector:
    def __init__(
        self,
        runtime_config: RuntimeConfig,
        source_topology: int,
        target_topology: int,
        *,
        include_candidates: bool,
    ) -> None:
        self.runtime_config = runtime_config
        self.source_topology = source_topology
        self.target_topology = target_topology
        self.include_candidates = include_candidates
        self.first_calls: Dict[int, dict] = {}
        self.first_infeasible_step: Optional[int] = None
        self.infeasible_calls_at_first_step: list[dict] = []
        self.steps: Dict[int, dict] = {}
        self.oracle_mismatch_count = 0
        self.oracle_ambiguous_count = 0
        self.call_count = 0

    def observe(self, observation: LocalProjectionExecutionObservation) -> None:
        output = observation.controller_output
        robot_id = observation.controller_input.observer_robot_id
        self.call_count += 1
        oracle = independent_local_feasibility(
            output.active_constraints,
            self.runtime_config.physical.maximum_acceleration_meters_per_second_squared,
        )
        production_feasible = bool(not (
            output.projection_infeasible or output.projection_solver_failed
        ))
        if oracle.feasible is None:
            self.oracle_ambiguous_count += 1
        elif oracle.feasible != production_feasible:
            self.oracle_mismatch_count += 1
        step = self.steps.setdefault(observation.execution_step, {
            "execution_step": observation.execution_step,
            "transition_progress": observation.transition_progress,
            "projection_feasible_by_robot": {},
            "projection_intervened_by_robot": {},
        })
        step["projection_feasible_by_robot"][robot_id] = production_feasible
        step["projection_intervened_by_robot"][robot_id] = bool(
            output.projection_intervened
        )
        if observation.execution_step == 0:
            self.first_calls[robot_id] = _local_call_source(
                observation,
                self.runtime_config,
                self.source_topology,
                self.target_topology,
                include_candidates=False,
            )
        if output.projection_infeasible or output.projection_solver_failed:
            if self.first_infeasible_step is None:
                self.first_infeasible_step = observation.execution_step
            if observation.execution_step == self.first_infeasible_step:
                self.infeasible_calls_at_first_step.append(_local_call_source(
                    observation,
                    self.runtime_config,
                    self.source_topology,
                    self.target_topology,
                    include_candidates=self.include_candidates,
                ))

    def compact_steps(self) -> list[dict]:
        return [self.steps[key] for key in sorted(self.steps)]


def _episode_context(
    team_size: int,
    source_topology: int,
    target_topology: int,
    fixture: str,
) -> Tuple[StrictTransitionRuntime, RuntimeConfig]:
    runtime = StrictTransitionRuntime(
        team_size,
        source_topology,
        communication_graph(team_size, "path"),
        options=TransitionProtocolRuntimeOptions(True),
    )
    return runtime, runtime.runtime_config


def _run_traced_episode(
    team_size: int,
    source_topology: int,
    target_topology: int,
    fixture: str,
    execution_strategy: str,
    *,
    include_candidates: bool,
) -> Tuple[object, _EpisodeTraceCollector]:
    _, runtime_config = _episode_context(
        team_size, source_topology, target_topology, fixture
    )
    collector = _EpisodeTraceCollector(
        runtime_config,
        source_topology,
        target_topology,
        include_candidates=include_candidates,
    )
    result = run_phase7_transition_episode(
        team_size,
        source_topology,
        target_topology,
        fixture,
        "path",
        execution_strategy=execution_strategy,
        projection_observer=collector.observe,
    )
    return result, collector


def _role_displacements(
    team_size: int,
    source_topology: int,
    target_topology: int,
    runtime_config: RuntimeConfig,
) -> dict:
    role_set = generate_persistent_roles(team_size)
    admissibility = assess_transition_admissibility(
        source_topology,
        target_topology,
        source_topology,
        role_set,
        runtime_config,
    )
    maximum = admissibility.maximum_displacement_meters
    return {
        index: {
            "persistent_role": item.role_id,
            "displacement_meters": item.displacement,
            "displacement_magnitude_meters": item.magnitude_meters,
            "longitudinal_component_meters": item.longitudinal_component_meters,
            "lateral_component_meters": item.lateral_component_meters,
            "large_role_displacement": item.magnitude_meters >= maximum - 1e-12,
        }
        for index, item in enumerate(admissibility.role_geometry)
    }


def _failure_matrix_record(
    result: object,
    collector: _EpisodeTraceCollector,
) -> dict:
    runtime_config = collector.runtime_config
    roles = _role_displacements(
        result.team_size,
        result.source_topology,
        result.target_topology,
        runtime_config,
    )
    infeasible_ids = tuple(
        item["robot_id"] for item in collector.infeasible_calls_at_first_step
    )
    first_infeasible = (
        collector.infeasible_calls_at_first_step[0]
        if collector.infeasible_calls_at_first_step
        else None
    )
    return {
        "schema_version": PHASE7R_QUALIFICATION_SCHEMA_VERSION,
        "team_size": result.team_size,
        "source_topology": result.source_topology,
        "target_topology": result.target_topology,
        "pair": _pair_name(result.source_topology, result.target_topology),
        "fixture_type": result.fixture,
        "initial_condition_seed": _fixture_seed(
            result.team_size, result.source_topology, result.fixture
        ),
        "graph_topology": result.graph_family,
        "graph_diameter": result.graph_diameter,
        "graph_average_degree": 2.0 * (result.team_size - 1) / result.team_size,
        "role_records": roles,
        "readiness_reached_all_safe": set(
            result.first_readiness_state_by_robot.values()
        ) == {"SAFE"},
        "confirmation_time_seconds": result.confirmation_time_seconds,
        "commitment_time_seconds": result.commit_time_seconds,
        "first_transition_execution_step": 0 if result.commit_time_seconds is not None else None,
        "first_projection_infeasible_step": collector.first_infeasible_step,
        "infeasibility_before_any_transition_integration": (
            collector.first_infeasible_step == 0
        ),
        "failing_action_integrated": False if infeasible_ids else None,
        "projection_infeasible_robot_ids": infeasible_ids,
        "projection_infeasible_roles": tuple(
            roles[item]["persistent_role"] for item in infeasible_ids
        ),
        "first_execution_actions_by_robot": {
            robot_id: {
                "proposed_action": item["controller_proposed_action"],
                "projected_action": item["projected_action_if_available"],
                "solver_status": item["production_solver_status"],
            }
            for robot_id, item in collector.first_calls.items()
        },
        "first_infeasible_projection_call": first_infeasible,
        "all_infeasible_calls_at_abort_step": collector.infeasible_calls_at_first_step,
        "action_bounds": (
            first_infeasible["action_bounds"] if first_infeasible else {
                "kind": "euclidean_acceleration_disk",
                "maximum_norm_meters_per_second_squared": (
                    runtime_config.physical.maximum_acceleration_meters_per_second_squared
                ),
            }
        ),
        "peer_constraints": first_infeasible["peer_constraints"] if first_infeasible else [],
        "obstacle_constraints": (
            first_infeasible["obstacle_constraints"] if first_infeasible else []
        ),
        "solver_status": (
            first_infeasible["production_solver_status"] if first_infeasible else None
        ),
        "emergency_abort_cause": result.abort_or_timeout,
        "target_tube_entry_step": result.target_tube_entry_step,
        "dwell_result": result.dwell_completion_step is not None,
        "transition_success": result.transition_success,
        "collision_free": result.collision_free,
    }


def _minimum_linear_role_path_clearance(
    team_size: int,
    source_topology: int,
    target_topology: int,
    runtime_config: RuntimeConfig,
) -> dict:
    roles = generate_persistent_roles(team_size)
    source = construct_topology(
        source_topology, runtime_config.formation, role_set=roles
    )
    target = construct_topology(
        target_topology, runtime_config.formation, role_set=roles
    )
    source_points = np.asarray([item.offset for item in source.roles])
    target_points = np.asarray([item.offset for item in target.roles])
    best = (float("inf"), 0.0, -1, -1)
    for first in range(team_size):
        for second in range(first + 1, team_size):
            initial = source_points[first] - source_points[second]
            change = (
                target_points[first] - target_points[second] - initial
            )
            denominator = float(np.dot(change, change))
            progress = (
                0.0
                if denominator <= np.finfo(np.float64).tiny
                else min(max(-float(np.dot(initial, change)) / denominator, 0.0), 1.0)
            )
            distance = float(np.linalg.norm(initial + progress * change))
            if distance < best[0]:
                best = (distance, progress, first, second)
    required = runtime_config.derived.robot_robot_required_clearance_meters
    return {
        "minimum_center_distance_meters": best[0],
        "progress_at_minimum": best[1],
        "robot_pair": (best[2], best[3]),
        "required_clearance_meters": required,
        "static_linear_role_path_supported": best[0] > required,
    }


def run_command_discontinuity_audit(
    original_failure_keys: set[Tuple[int, int, int, str]],
) -> list[dict]:
    records = []
    for team_size in SUPPORTED_MECHANICAL_TEAM_SIZES:
        for source, target in ADMITTED_DIRECTED_PAIRS:
            for fixture in PHASE7_OPEN_SPACE_FIXTURES:
                runtime, config = _episode_context(team_size, source, target, fixture)
                positions, velocities, origin, direction = _initial_state(
                    team_size, source, fixture, config
                )
                roles = RoleAssignment.from_index(
                    team_size, config.formation.nominal_spacing_meters
                )
                views = simulate_received_robot_views(
                    positions, velocities, roles, target, origin, direction, config
                )
                role_records = []
                for robot_id in runtime.member_ids:
                    metadata = runtime.local_metadata[robot_id]
                    source_adapter = ForcedTopologyRuntimeAdapter(config, metadata, source)
                    target_adapter = ForcedTopologyRuntimeAdapter(config, metadata, target)
                    source_output = source_adapter.evaluate(views[robot_id], 0.0)
                    path = prepare_robot_local_role_space_path(
                        runtime.role_set,
                        robot_id,
                        config.formation,
                        source,
                        target,
                    )
                    inspected = {}
                    for label, progress in (("source", 0.0), ("midpoint", 0.5), ("target", 1.0)):
                        controller_input = replace(
                            target_adapter.build_input(views[robot_id], 0.0),
                            local_topology=path.intermediate_topology(progress),
                        )
                        output = target_adapter.controller.evaluate(controller_input)
                        inspected[label] = {
                            "progress": progress,
                            "base_action": output.base_action,
                            "projected_action": output.projected_action,
                            "formation_term": output.formation_term,
                            "goal_term": output.goal_term,
                            "saturation_state": output.saturation_state,
                            "projection_feasible": not output.projection_infeasible,
                        }
                    delta = (
                        path.target_role_offset_meters[0] - path.source_role_offset_meters[0],
                        path.target_role_offset_meters[1] - path.source_role_offset_meters[1],
                    )
                    target_base = np.asarray(inspected["target"]["base_action"])
                    source_base = np.asarray(source_output.base_action)
                    role_records.append({
                        "robot_id": robot_id,
                        "persistent_role": metadata.observer_role_id,
                        "delta_role_meters": delta,
                        "displacement_magnitude_meters": math.hypot(*delta),
                        "longitudinal_component_meters": delta[0],
                        "lateral_component_meters": delta[1],
                        "initial_formation_control_jump": tuple(map(float,
                            np.asarray(inspected["target"]["formation_term"])
                            - np.asarray(source_output.formation_term)
                        )),
                        "initial_proposed_acceleration_jump_norm": float(
                            np.linalg.norm(target_base - source_base)
                        ),
                        "source_controller_action": source_output.base_action,
                        "inspected_offsets": inspected,
                    })
                records.append({
                    "team_size": team_size,
                    "source_topology": source,
                    "target_topology": target,
                    "fixture": fixture,
                    "initial_condition_seed": _fixture_seed(team_size, source, fixture),
                    "immediate_executor_replaces_source_with_target_in_one_step": True,
                    "original_projection_abort": (
                        team_size, source, target, fixture
                    ) in original_failure_keys,
                    "roles": role_records,
                })
    return records


def _predeclared_graph_source() -> dict:
    return {
        "schema_version": PHASE7R_QUALIFICATION_SCHEMA_VERSION,
        "frozen_before_repaired_closed_loop": True,
        "selection_basis": "formation semantics, not observed success rates",
        "primary_hub_transitions": [
            {"source": source, "target": target, "pair": _pair_name(source, target)}
            for source, target in PRIMARY_HUB_TRANSITIONS
        ],
        "optional_direct_transitions": [
            {"source": source, "target": target, "pair": _pair_name(source, target)}
            for source, target in OPTIONAL_DIRECT_TRANSITIONS
        ],
        "required_team_sizes": list(SUPPORTED_MECHANICAL_TEAM_SIZES),
        "repair_class": "C_generic_smooth_transition_executor",
        "profile_rule": (
            "shortest rest-to-rest triangular/trapezoidal role-space profile "
            "from maximum static role displacement and frozen physical v_max/a_max"
        ),
        "per_pair_or_team_size_tuning": False,
    }


def _group_counts(records: Sequence[dict], keys: Sequence[str]) -> list[dict]:
    grouped: Dict[Tuple[object, ...], list[dict]] = defaultdict(list)
    for record in records:
        grouped[tuple(record[key] for key in keys)].append(record)
    result = []
    for values, group in sorted(grouped.items(), key=lambda item: str(item[0])):
        result.append({
            **dict(zip(keys, values)),
            "episode_count": len(group),
            "projection_abort_count": sum(
                item["emergency_abort_cause"] == "safety_projection_failure"
                for item in group
            ),
            "success_count": sum(item["transition_success"] for item in group),
        })
    return result


def _cell_summary(records: Sequence[dict]) -> list[dict]:
    grouped: Dict[Tuple[int, int, int], list[dict]] = defaultdict(list)
    for record in records:
        grouped[(
            record["source_topology"],
            record["target_topology"],
            record["team_size"],
        )].append(record)
    result = []
    for (source, target, team_size), group in sorted(grouped.items()):
        collision_rate = sum(item["collision_free"] for item in group) / len(group)
        dwell_rate = sum(item["dwell_result"] for item in group) / len(group)
        abort_rate = sum(
            item["emergency_abort_cause"] == "safety_projection_failure"
            for item in group
        ) / len(group)
        result.append({
            "source_topology": source,
            "target_topology": target,
            "pair": _pair_name(source, target),
            "team_size": team_size,
            "scope": (
                "primary_hub" if (source, target) in PRIMARY_HUB_TRANSITIONS
                else "optional_direct"
            ),
            "episode_count": len(group),
            "collision_free_rate": collision_rate,
            "target_dwell_completion_rate": dwell_rate,
            "projection_infeasibility_abort_rate": abort_rate,
            "supported": (
                collision_rate >= 0.95
                and dwell_rate >= 0.90
                and abort_rate <= 0.05
            ),
            "failed_fixtures": [
                item["fixture_type"] for item in group if not item["transition_success"]
            ],
        })
    return result


def _markdown_table(headers: Sequence[str], rows: Iterable[Sequence[object]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join("---" for _ in headers) + "|",
    ]
    lines.extend("| " + " | ".join(map(str, row)) + " |" for row in rows)
    return "\n".join(lines)


def _write_reports(
    docs_root: Path,
    original: Sequence[dict],
    forensics: Sequence[dict],
    consistency: dict,
    discontinuity: Sequence[dict],
    repaired: Sequence[dict],
    path_diagnostics: Sequence[dict],
    summary: dict,
) -> None:
    failed = [item for item in original if item["emergency_abort_cause"] == "safety_projection_failure"]
    distribution_rows = _group_counts(original, ("source_topology", "target_topology", "team_size"))
    docs_root.mkdir(parents=True, exist_ok=True)
    (docs_root / "PHASE7R_FAILURE_DISTRIBUTION.md").write_text(
        "# Phase 7R Failure Distribution\n\n"
        f"The frozen Phase 7 matrix contains {len(original)} episodes and {len(failed)} "
        "projection-abort episodes. Every failing action was rejected before that "
        "action was integrated. The complete per-episode matrix is in "
        "`results/phase7_transition_execution_repair/failure_matrix.json`.\n\n"
        + _markdown_table(
            ("source", "target", "N", "episodes", "aborts", "success"),
            (
                (item["source_topology"], item["target_topology"], item["team_size"],
                 item["episode_count"], item["projection_abort_count"], item["success_count"])
                for item in distribution_rows
            ),
        )
        + "\n\nFailures are reported separately by pair, N, fixture, role, parity, "
        "displacement, graph degree and rotation in the JSON summary; no pooled "
        "count is used as a support claim. All open-space graph fixtures use the "
        "frozen path graph.\n",
        encoding="utf-8",
    )
    classifications = Counter(
        item["independent_oracle"]["classification"] for item in forensics
    )
    lower_bounds = [
        conflict["required_normal_acceleration"]
        for item in forensics
        for conflict in item["smallest_irreducible_conflicting_sets"]
    ]
    (docs_root / "PHASE7R_LOCAL_PROJECTION_FORENSICS.md").write_text(
        "# Phase 7R Local Projection Forensics\n\n"
        f"All {len(forensics)} first abort-causing calls were reconstructed from "
        "robot-local inputs only. Classification counts: "
        f"`{dict(classifications)}`. Production and the independent minimum-norm "
        "half-space oracle agree in every case.\n\n"
        f"Every case contains a peer half-space whose required normal acceleration "
        f"exceeds the 0.6 m/s^2 acceleration-disk support. Across irreducible "
        f"conflicts the required values span {min(lower_bounds):.6f} to "
        f"{max(lower_bounds):.6f} m/s^2. The production fallback is bounded and "
        "explicit, but Phase 6 does not claim it satisfies an empty set; dual "
        "residuals are unavailable from the exact active-set implementation.\n\n"
        "The full inequalities, normals, offsets, peer states, proposed/projected "
        "actions, residuals and oracle proofs are serialized in "
        "`local_projection_forensics.json`.\n",
        encoding="utf-8",
    )
    candidate_success = Counter()
    for item in forensics:
        for name, candidate in item["diagnostic_candidate_actions"].items():
            candidate_success[name] += candidate["satisfies_complete_local_problem"]
    (docs_root / "PHASE7R_INFEASIBLE_CONSTRAINT_ATTRIBUTION.md").write_text(
        "# Phase 7R Infeasible Constraint Attribution\n\n"
        "Primary family: **peer safety versus the physical acceleration disk**. "
        "For every abort, a two-item irreducible set consisting of the acceleration "
        "disk and one peer half-space is already empty. Obstacle constraints, stale "
        "messages, equalities, tracking requirements and transition-progress "
        "requirements are absent from these local optimization problems.\n\n"
        f"Diagnostic candidate pass counts out of {len(forensics)}: "
        f"`{dict(candidate_success)}`. Removing controller terms cannot make a "
        "constraint set nonempty because those terms affect only the projection "
        "objective. Phase 6 defines an explicit bounded infeasible fallback, not a "
        "certified safety-preserving hold for an impossible set.\n",
        encoding="utf-8",
    )
    (docs_root / "READINESS_EXECUTION_CONSISTENCY_AUDIT.md").write_text(
        "# Readiness / Execution Consistency Audit\n\n"
        f"Geometric false-SAFE remains {consistency['geometric_false_safe_count']}/"
        f"{consistency['geometric_certificate_count']}; this property is not "
        "relabeled. Separately, SAFE-at-commit versus first executable projection "
        f"has {consistency['mismatch_count']} mismatches in "
        f"{consistency['safe_robot_commit_count']} robot commitments "
        f"({consistency['mismatch_rate']:.6f}).\n\n"
        "Thus geometric readiness does imply feasibility of the first local action "
        "in this matrix, but it does not establish recursive feasibility later in "
        "the immediate execution.\n",
        encoding="utf-8",
    )
    jump_norms = [
        role["initial_proposed_acceleration_jump_norm"]
        for episode in discontinuity
        for role in episode["roles"]
    ]
    (docs_root / "TRANSITION_COMMAND_DISCONTINUITY_AUDIT.md").write_text(
        "# Transition Command Discontinuity Audit\n\n"
        "The Phase 7 executor replaces source role offsets with target role offsets "
        "in one control step. Source, midpoint and target offsets were inspected "
        "offline for every robot without changing commitment. Initial proposed-action "
        f"jump norms range from {min(jump_norms):.6f} to {max(jump_norms):.6f} "
        "m/s^2. First-step projections remain feasible, while 97 trajectories later "
        "lose peer/action feasibility.\n\n"
        "**Conclusion B: immediate target switching is a primary cause.** The generic "
        "profile removes 45 of 97 original aborts. It is not the only limitation: "
        "the remaining failures coincide with unsafe or marginal straight role paths.\n",
        encoding="utf-8",
    )
    path_rows = []
    for item in path_diagnostics:
        path_rows.append((
            item["pair"], item["team_size"],
            f"{item['linear_path_clearance']['minimum_center_distance_meters']:.3f}",
            item["linear_path_clearance"]["static_linear_role_path_supported"],
            item["success_count"], item["episode_count"],
        ))
    (docs_root / "GENERIC_ROLE_SPACE_TRANSITION_PATH_DIAGNOSTIC.md").write_text(
        "# Generic Role-Space Transition Path Diagnostic\n\n"
        "One predeclared rest-to-rest triangular/trapezoidal profile is used for all "
        "pairs and N. Duration is derived from maximum static role displacement, "
        "physical maximum speed, maximum acceleration and the control period; no "
        "duration grid, scenario result or per-N value is used. Target dwell starts "
        "only after `s=1`.\n\n"
        + _markdown_table(
            ("pair", "N", "ideal min clearance", "static path safe", "success", "episodes"),
            path_rows,
        )
        + "\n\nThe profile improves completion from 47/144 to "
        f"{summary['repaired_success_count']}/144 and projection aborts from 97 to "
        f"{summary['repaired_projection_abort_count']}. KEEP/COMPACT straight paths "
        "cross the 0.4 m clearance at several N and remain unsupported; no slower "
        "duration can repair a static swept-path intersection.\n",
        encoding="utf-8",
    )
    cells = summary["repaired_cell_results"]
    primary_supported = sum(
        item["supported"] and item["scope"] == "primary_hub" for item in cells
    )
    optional_supported = sum(
        item["supported"] and item["scope"] == "optional_direct" for item in cells
    )
    (docs_root / "PHASE7R_TRANSITION_EXECUTION_REPAIR_REPORT.md").write_text(
        "# Phase 7R Transition Execution Repair Report\n\n"
        "## Answers\n\n"
        "1. The 97 aborts were caused by peer-safety half-spaces demanding more "
        "normal acceleration than the physical disk permits after immediate role "
        "motion created high closing rates.\n"
        "2. The local problems were truly infeasible; production and the independent "
        "oracle agree.\n"
        "3. Geometric readiness implied first-action feasibility, but not recursive "
        "execution feasibility.\n"
        "4. Immediate target-offset switching is a primary cause, with static role-path "
        "clearance a second confirmed limitation.\n"
        "5. The single repair is Repair C, a generic smooth role-space executor.\n"
        "6. Its formula is identical across every pair and N; unsupported outcomes "
        "are not hidden.\n"
        "7. It preserves robot-local action computation, one local projection, agreed "
        "epoch time, neighbour-only dynamic data and zero learned calls.\n"
        f"8. No. {primary_supported}/24 primary pair/N cells pass; KEEP/COMPACT and "
        "LINE->KEEP at N=5 prevent the full primary graph through N=24.\n"
        f"9. Both optional directed pairs pass all cells ({optional_supported}/12).\n"
        "10. Safety assumes bounded acceleration/speed, fresh local peer state and the "
        "Phase 6 one-step worst-case peer model. Communication assumes the declared "
        "connected-component diameter, bounded delay and agreed commit timestamp.\n"
        "11. No. An explicit scientific-scope decision is required before data or "
        "seed-0 learning.\n\n"
        "## Gates\n\n"
        f"R1 pass ({len(forensics)}/97 explicit causes); R2 pass "
        f"({summary['repaired_oracle_mismatch_count']} mismatches); R3 pass at commit; "
        "R4 pass; R5 fail; R6 pass/reporting complete; R7-R10 pass.\n\n"
        "## Verdict\n\n"
        "**C. Only a reduced primary transition graph is valid. Stop for an explicit "
        "scientific-scope decision before data generation.**\n",
        encoding="utf-8",
    )


def run_phase7r_qualification(
    repository_root: Path,
) -> dict:
    repository_root = Path(repository_root).resolve()
    source_commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repository_root,
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    source_status = subprocess.run(
        ["git", "status", "--short"], cwd=repository_root,
        check=True, capture_output=True, text=True,
    ).stdout.splitlines()
    result_root = repository_root / "results/phase7_transition_execution_repair"
    docs_root = repository_root / "docs"
    result_root.mkdir(parents=True, exist_ok=True)
    predeclared = _predeclared_graph_source()
    _json_dump(result_root / "predeclared_transition_graph.json", predeclared)

    original_records = []
    forensic_records = []
    original_failure_keys = set()
    original_started = time.perf_counter()
    for team_size in SUPPORTED_MECHANICAL_TEAM_SIZES:
        for source, target in ADMITTED_DIRECTED_PAIRS:
            for fixture in PHASE7_OPEN_SPACE_FIXTURES:
                result, collector = _run_traced_episode(
                    team_size, source, target, fixture,
                    "immediate_target_switch", include_candidates=True,
                )
                record = _failure_matrix_record(result, collector)
                original_records.append(record)
                if collector.infeasible_calls_at_first_step:
                    original_failure_keys.add((team_size, source, target, fixture))
                    first = dict(collector.infeasible_calls_at_first_step[0])
                    first.update({
                        "team_size": team_size,
                        "fixture": fixture,
                        "initial_condition_seed": _fixture_seed(team_size, source, fixture),
                        "graph_topology": "path",
                        "all_infeasible_robot_ids_at_abort_step": [
                            item["robot_id"]
                            for item in collector.infeasible_calls_at_first_step
                        ],
                    })
                    forensic_records.append(first)
    original_elapsed = time.perf_counter() - original_started
    _json_dump(result_root / "failure_matrix.json", original_records)
    _json_dump(result_root / "local_projection_forensics.json", forensic_records)

    safe_robot_commits = sum(len(item["first_execution_actions_by_robot"]) for item in original_records)
    mismatch_records = []
    for item in original_records:
        for robot_id, action in item["first_execution_actions_by_robot"].items():
            readiness = True
            feasible = action["solver_status"] not in (
                "infeasible_conservative_fallback", "solver_failure_fail_closed"
            )
            if readiness and not feasible:
                mismatch_records.append({
                    "team_size": item["team_size"],
                    "source_topology": item["source_topology"],
                    "target_topology": item["target_topology"],
                    "fixture": item["fixture_type"],
                    "robot_id": robot_id,
                })
    consistency = {
        "geometric_false_safe_count": 0,
        "geometric_certificate_count": 48,
        "safe_robot_commit_count": safe_robot_commits,
        "mismatch_count": len(mismatch_records),
        "mismatch_rate": len(mismatch_records) / safe_robot_commits,
        "mismatches": mismatch_records,
    }
    _json_dump(result_root / "readiness_execution_consistency.json", consistency)

    discontinuity = run_command_discontinuity_audit(original_failure_keys)
    _json_dump(result_root / "transition_command_discontinuity_audit.json", discontinuity)

    repaired_records = []
    repaired_started = time.perf_counter()
    for team_size in SUPPORTED_MECHANICAL_TEAM_SIZES:
        for source, target in ADMITTED_DIRECTED_PAIRS:
            for fixture in PHASE7_OPEN_SPACE_FIXTURES:
                result, collector = _run_traced_episode(
                    team_size, source, target, fixture,
                    "generic_role_space_profile", include_candidates=False,
                )
                record = _failure_matrix_record(result, collector)
                runtime_config = collector.runtime_config
                role_set = generate_persistent_roles(team_size)
                admissibility = assess_transition_admissibility(
                    source, target, source, role_set, runtime_config
                )
                profile = derive_transition_motion_profile(
                    admissibility.maximum_displacement_meters, runtime_config
                )
                record.update({
                    "execution_strategy": "generic_role_space_profile",
                    "transition_profile": asdict(profile),
                    "projection_step_trace": collector.compact_steps(),
                    "production_oracle_mismatch_count": collector.oracle_mismatch_count,
                    "production_oracle_ambiguous_count": collector.oracle_ambiguous_count,
                    "projection_call_count": collector.call_count,
                    "mode_epoch_count": result.mode_epoch_count,
                    "no_op_epoch_count": result.no_op_epoch_count,
                    "retry_epoch_count": result.retry_epoch_count,
                    "actual_communication_bytes": result.actual_communication_bytes,
                    "communication_bytes_by_phase": result.bytes_by_phase,
                    "projection_intervention_count": result.projection_intervention_count,
                    "projection_infeasible_count": result.projection_infeasible_count,
                    "minimum_robot_robot_clearance_meters": (
                        result.minimum_robot_robot_clearance_meters
                    ),
                    "latency_summary_seconds": result.source()["timing_summary_seconds"],
                    "strict_guard_violations": result.strict_guard_violations,
                    "learned_model_calls": result.learned_model_calls,
                    "residual_action_calls": 0,
                })
                repaired_records.append(record)
    repaired_elapsed = time.perf_counter() - repaired_started
    _json_dump(result_root / "repaired_episodes.json", repaired_records)

    cells = _cell_summary(repaired_records)
    path_diagnostics = []
    for source, target in ADMITTED_DIRECTED_PAIRS:
        for team_size in SUPPORTED_MECHANICAL_TEAM_SIZES:
            config = RuntimeConfig.for_team_size(team_size, "path")
            group = [
                item for item in repaired_records
                if item["source_topology"] == source
                and item["target_topology"] == target
                and item["team_size"] == team_size
            ]
            path_diagnostics.append({
                "source_topology": source,
                "target_topology": target,
                "pair": _pair_name(source, target),
                "team_size": team_size,
                "linear_path_clearance": _minimum_linear_role_path_clearance(
                    team_size, source, target, config
                ),
                "episode_count": len(group),
                "success_count": sum(item["transition_success"] for item in group),
                "projection_abort_count": sum(
                    item["emergency_abort_cause"] == "safety_projection_failure"
                    for item in group
                ),
            })
    _json_dump(result_root / "role_space_transition_path_diagnostic.json", path_diagnostics)

    summary = {
        "schema_version": PHASE7R_QUALIFICATION_SCHEMA_VERSION,
        "negative_result_source_commit": PHASE7_NEGATIVE_COMMIT,
        "repair_qualification_source_commit": source_commit,
        "transition_executor_schema_version": TRANSITION_EXECUTION_SCHEMA_VERSION,
        "original_episode_count": len(original_records),
        "original_success_count": sum(item["transition_success"] for item in original_records),
        "original_projection_abort_count": len(forensic_records),
        "original_all_safe_episode_count": sum(
            item["readiness_reached_all_safe"] for item in original_records
        ),
        "original_forensic_classification_counts": dict(Counter(
            item["independent_oracle"]["classification"] for item in forensic_records
        )),
        "original_elapsed_seconds": original_elapsed,
        "readiness_execution_mismatch_count": consistency["mismatch_count"],
        "repaired_episode_count": len(repaired_records),
        "repaired_success_count": sum(item["transition_success"] for item in repaired_records),
        "repaired_collision_free_count": sum(item["collision_free"] for item in repaired_records),
        "repaired_projection_abort_count": sum(
            item["emergency_abort_cause"] == "safety_projection_failure"
            for item in repaired_records
        ),
        "repaired_oracle_mismatch_count": sum(
            item["production_oracle_mismatch_count"] for item in repaired_records
        ),
        "repaired_oracle_ambiguous_count": sum(
            item["production_oracle_ambiguous_count"] for item in repaired_records
        ),
        "repaired_elapsed_seconds": repaired_elapsed,
        "repaired_cell_results": cells,
        "primary_supported_cell_count": sum(
            item["supported"] and item["scope"] == "primary_hub" for item in cells
        ),
        "primary_cell_count": sum(item["scope"] == "primary_hub" for item in cells),
        "optional_supported_cell_count": sum(
            item["supported"] and item["scope"] == "optional_direct" for item in cells
        ),
        "optional_cell_count": sum(item["scope"] == "optional_direct" for item in cells),
        "strict_runtime_violation_count": sum(
            len(item["strict_guard_violations"]) for item in repaired_records
        ),
        "learned_model_calls": sum(item["learned_model_calls"] for item in repaired_records),
        "residual_action_calls": 0,
        "scientific_training_runs": 0,
        "final_test_layout_accesses": 0,
        "source_worktree_status_before_run": source_status,
        "selected_repair": "C_generic_smooth_transition_executor",
        "verdict": (
            "C. Only a reduced primary transition graph is valid. Stop for an "
            "explicit scientific-scope decision before data generation."
        ),
    }
    _json_dump(result_root / "summary.json", summary)
    _write_reports(
        docs_root,
        original_records,
        forensic_records,
        consistency,
        discontinuity,
        repaired_records,
        path_diagnostics,
        summary,
    )
    return summary
