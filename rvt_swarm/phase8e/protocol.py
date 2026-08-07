"""Canonical builders for the additive Phase 8E execution specification."""

from __future__ import annotations

import hashlib
import math
from pathlib import Path
from typing import Dict, Iterable, Mapping, Sequence, Tuple

from ..phase8.common import (
    attach_canonical_hash,
    canonical_json_bytes,
    file_sha256,
    verify_canonical_hash,
)
from ..phase8.scenario import SUPPORTED_TEAM_SIZES
from ..runtime_configuration import RuntimeConfig, canonical_runtime_hash
from ..topology_registry import COMPACT, LINE
from .target import TERMINATION_CAUSES, TARGET_DISPOSITIONS


EXECUTABLE_PROTOCOL_SCHEMA_VERSION = "rvt-executable-scientific-protocol/v1"
SOURCE_POLICY_CONTRACT_SCHEMA_VERSION = "rvt-source-policy-contracts/v1"
TARGET_V4_EXECUTION_CONTRACT_SCHEMA_VERSION = "rvt-target-v4-execution-contract/v1"
LAYOUT_EXECUTION_SPECIFICATION_SCHEMA_VERSION = (
    "rvt-layout-execution-specification/v1"
)

PHASE8_PROTOCOL_SHA256 = (
    "0bb68dd56ef0837f83c44dcf5281498f8c0ea934b00bbb9b3d3f298264d32147"
)
GENERATION_BUDGET_SHA256 = (
    "3853b8ad4484d733de9be7d0e27bf273f33e14054f3089f6b5454cc17815846e"
)
COMPOSITE_GENERATION_PROTOCOL_SHA256 = (
    "d928a7f614434b4d99395c5b75398b6277ec407cbf206e332a621f553022be57"
)
FROZEN_JOB_MANIFEST_SHA256 = (
    "801fe4e2bd694da0dda7c310226906e59d9bc5435d657fab2e3f132432aa2dc3"
)
PHASE8_PROTOCOL_COMMIT = "c17081fe1cf58cc2d3f929e35ff4bca811c75c58"
PHASE9B_BUDGET_COMMIT = "20a7541a4ae946c2ca051cde0c353c396d2c1241"
PHASE9C_BLOCKED_AUDIT_COMMIT = "62698414a9e2f0f1b388d1e9ee6401964862d86e"

WORLD_BOUNDS_METERS = ((-18.0, 18.0), (-6.0, 6.0))
OBSTACLE_REFERENCE_RADIUS_METERS = 0.35
OBSTACLE_SURFACE_MARGIN_METERS = 0.02
NUMERICAL_GEOMETRY_TOLERANCE_METERS = 1e-9
PRF_VERSION = "sha256-canonical-counter-uint64/v1"
SOURCE_POLICY_IDS: Tuple[str, ...] = (
    "S0_SCRIPTED_DIAGNOSTIC",
    "S1_ALWAYS_COMPACT",
    "S2_ALWAYS_LINE",
    "S3_FROZEN_LOCAL_GEOMETRIC_SELECTOR",
    "S4_FROZEN_TRANSITION_PROTOCOL",
    "S5_BOUNDED_PERTURBATION",
)

_PROTOCOL_KEYS = frozenset({
    "schema_version",
    "phase8_protocol_hash",
    "generation_budget_hash",
    "composite_generation_protocol_hash",
    "frozen_job_manifest_hash",
    "source_commits",
    "scenario_geometry_contract",
    "initialization_contract",
    "static_obstacle_contract",
    "dynamic_obstacle_contract",
    "communication_degradation_contract",
    "disturbance_contract",
    "source_policy_contracts",
    "target_v4_execution_contract",
    "counterfactual_execution_contract",
    "simulator_semantics",
    "seed_binding",
    "final_test_access_policy",
    "configuration_hashes",
    "category_d_count",
    "protocol_hash",
})

_SOURCE_POLICY_REQUIRED_KEYS = {
    "S0_SCRIPTED_DIAGNOSTIC": {
        "deployability", "initial_topology", "action_source", "topology_behavior",
        "event_rule", "machine_readable_script", "communication", "retry",
    },
    "S1_ALWAYS_COMPACT": {
        "deployability", "initial_topology", "action_source", "topology_behavior",
        "event_rule", "communication", "hold_semantics",
    },
    "S2_ALWAYS_LINE": {
        "deployability", "initial_topology", "action_source", "topology_behavior",
        "event_rule", "communication", "hold_semantics",
    },
    "S3_FROZEN_LOCAL_GEOMETRIC_SELECTOR": {
        "deployability", "initial_topology", "action_source", "local_inputs",
        "width_statistic", "required_width_formula", "compact_to_line_rule",
        "line_to_compact_rule", "hysteresis_meters", "minimum_commitment_seconds",
        "unknown_behavior", "tie_behavior", "origination", "transition",
    },
    "S4_FROZEN_TRANSITION_PROTOCOL": {
        "deployability", "initial_topology", "action_source", "local_event_source",
        "diagnostic_score", "score_semantics", "aggregation", "candidate_selection",
        "lifecycle_origination", "transition", "timeout", "abort_rearm", "no_event",
    },
    "S5_BOUNDED_PERTURBATION": {
        "deployability", "base_policy", "initial_topology", "action_source",
        "perturbation_target", "frame", "distribution", "maximum_magnitude_formula",
        "start_time", "duration", "repeat_count", "seed", "invalidity",
        "event_eligibility",
    },
}


def _exact_keys(value: object, expected: Iterable[str], path: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{path} must be an object")
    expected_set = frozenset(expected)
    actual = frozenset(str(key) for key in value)
    if actual != expected_set:
        missing = sorted(expected_set - actual)
        unknown = sorted(actual - expected_set)
        raise ValueError(f"{path} key mismatch: missing={missing}, unknown={unknown}")
    return value


def _runtime_configuration_hashes() -> Dict[str, str]:
    return {
        str(team_size): canonical_runtime_hash(RuntimeConfig.for_team_size(team_size))
        for team_size in SUPPORTED_TEAM_SIZES
    }


def _layout_field_dispositions() -> Tuple[Dict[str, object], ...]:
    entries = (
        ("schema_version", "validate rvt-scenario-layout/v1", "audit_only"),
        ("generator_version", "validate frozen geometry generator", "audit_only"),
        ("layout_id", "canonical episode identity", "audit_only"),
        ("family_id", "select one F1-F10 compiler", "global_simulator"),
        ("split", "nonfinal access guard and identity", "audit_only"),
        ("variant_index", "canonical identity", "audit_only"),
        ("generation_seed_commitment", "provenance commitment", "audit_only"),
        ("start_center_meters", "mission and initial topology origin", "shared_mission"),
        ("goal_center_meters", "goal-region center", "shared_mission"),
        ("corridor_centerline_meters", "passage or bypass reference path", "global_simulator"),
        ("nominal_passage_width_meters", "free width between analytic inner boundaries", "global_simulator"),
        ("static_obstacles", "compile analytic occupied sets", "global_simulator"),
        ("dynamic_obstacle_paths", "compile timestamp-authoritative motion", "global_simulator"),
        ("bypass_available", "validate F6 bypass declaration", "audit_only"),
        ("communication_profile", "select nominal, bounded, or disconnection process", "global_simulator"),
        ("initial_topology_id", "initial committed topology and role template", "robot_local_metadata"),
        ("episode_horizon_seconds", "absolute source and mission timeout", "global_simulator"),
        ("canonical_parameters", "compiler inputs and cross-checks", "global_simulator"),
        ("diagnostic_headroom_by_team_size", "never execution or label input", "audit_only"),
    )
    return tuple(
        {"field": field, "consumption": consumption, "visibility": visibility}
        for field, consumption, visibility in entries
    )


def _geometry_contract() -> Dict[str, object]:
    return {
        "world_frame": {
            "frame_id": "world",
            "origin_meters": [0.0, 0.0],
            "x_axis": [1.0, 0.0],
            "y_axis": [0.0, 1.0],
            "bounds_meters": [list(WORLD_BOUNDS_METERS[0]), list(WORLD_BOUNDS_METERS[1])],
            "bounds_rationale": (
                "contains the N=24 LINE half-length at both frozen start and goal, "
                "all declared family geometry ranges, and configured clearances"
            ),
        },
        "mission_frame": {
            "origin_formula": "ScenarioLayout.start_center_meters",
            "heading_formula": "unit(goal_center_meters-start_center_meters)",
            "longitudinal_axis_formula": "heading",
            "lateral_axis_formula": "(-heading_y,heading_x)",
            "zero_length_goal_vector": "GEOMETRY_INVALID",
        },
        "goal_region": {
            "center_formula": "ScenarioLayout.goal_center_meters",
            "origin_tolerance_formula": "formation_tolerance_ratio*nominal_spacing_meters",
            "required_goal_dwell_seconds": "control_period_seconds",
        },
        "centerline_semantics": {
            "representation": "piecewise_linear_polyline_with_euclidean_tube",
            "join_semantics": "closed round distance-to-polyline join",
            "passage_length_formula": "sum Euclidean segment lengths after entry/exit clipping",
            "rejected_spline_alternative": (
                "rejected because spline tension and endpoint derivatives are absent "
                "from ScenarioLayout"
            ),
        },
        "family_compilers": {
            "F1": "explicit static circles; no confining passage",
            "F2": "one straight_corridor active on stored x0..x1",
            "F3": "polyline tube active from first interior x to its reflected exit x",
            "F4": "piecewise-linear S tube active between first and last interior control points",
            "F5": "two independent straight_corridor tubes in declaration order",
            "F6": "central circle plus declared polyline bypass with circular fillet radius parameter",
            "F7": "explicit static circles; no confining passage",
            "F8": "one straight_corridor plus the F8 communication contract",
            "F9": "no static passage; one timestamp-authoritative moving circle",
            "F10": "one straight_corridor below clearance requirement",
        },
        "layout_field_dispositions": list(_layout_field_dispositions()),
        "invalidity_conditions": [
            "unknown schema, generator, split, family, topology, or primitive",
            "nonfinite value, nonpositive width/radius/horizon, or nonmonotone waypoint time",
            "start equals goal or centreline x is not monotone",
            "primitive or inflated robot center leaves the declared world bounds",
            "initial role state collides or lies outside robot-center bounds",
            "declared passage width disagrees with primitive width",
            "bypass flag or family-specific canonical parameter is inconsistent",
        ],
        "geometry_tolerance_meters": NUMERICAL_GEOMETRY_TOLERANCE_METERS,
        "headroom_use": "audit_only_prohibited_from_compilation_and_execution",
    }


def _initialization_contract() -> Dict[str, object]:
    return {
        "initial_topology": {
            "required_layout_value": COMPACT,
            "line_exception": "only an explicit frozen narrow-start declaration; none exists in v1 layouts",
            "keep_status": "prohibited",
        },
        "topology_origin_formula": "ScenarioLayout.start_center_meters",
        "topology_orientation_formula": "mission heading",
        "role_assignment": "generate_persistent_roles(sorted canonical integer robot keys)",
        "nominal_pose_formula": "origin + R(mission_heading)*COMPACT_role_offset",
        "position_perturbation": {
            "enabled": True,
            "distribution": "independent_uniform_closed",
            "bounds_formula_meters": "[-spacing_margin_meters,+spacing_margin_meters] per mission-frame component",
            "frame": "mission",
            "seed": "source_job.seeds.initial_condition",
            "draw_key": ["initial_position", "robot_id", "longitudinal_or_lateral"],
            "shared": False,
            "clipping": "none",
        },
        "velocity_perturbation": {
            "enabled": True,
            "distribution": "independent_uniform_closed",
            "bounds_formula_meters_per_second": "[-maximum_speed*control_period,+maximum_speed*control_period] per mission-frame component",
            "frame": "mission",
            "seed": "source_job.seeds.initial_condition",
            "draw_key": ["initial_velocity", "robot_id", "longitudinal_or_lateral"],
            "shared": False,
            "clipping": "reject if Euclidean speed exceeds maximum_speed",
        },
        "initial_acceleration_meters_per_second_squared": [0.0, 0.0],
        "controller_local_state": "new RobotLocalController per robot with empty mutable history",
        "protocol_state": {
            "state": "STABLE_TOPOLOGY",
            "committed_topology": COMPACT,
            "active_intent": None,
            "mode_epoch_count": 0,
            "duplicate_intent_count": 0,
            "state_entered_seconds": 0.0,
        },
        "message_queues": "empty per directed link",
        "communication_state": "sequence counters zero; neighbour tables empty; PRF counter zero",
        "dynamic_obstacle_phase": "absolute episode time zero",
        "mission_progress": "zero with maximum-progress origin at initial fitted topology origin",
        "invalidity_handling": "record one rejected scientific slot; never resample or replace",
    }


def _static_obstacle_contract() -> Dict[str, object]:
    return {
        "truth_geometry": {
            "circle": "closed disk(center,radius)",
            "central_blocker": "closed disk(center,radius)",
            "corridor": (
                "inside active longitudinal slab, occupied space is the world-bound "
                "complement of the closed centreline tube of half-width width/2"
            ),
            "boundary_contact": "collision",
        },
        "collision_inflation": {
            "circle_center_threshold_formula": (
                "robot_radius + max(safety.obstacle_clearance_margin, circle_radius)"
            ),
            "analytic_wall_surface_threshold_formula": (
                "robot_radius + obstacle_surface_margin"
            ),
            "obstacle_surface_margin_meters": OBSTACLE_SURFACE_MARGIN_METERS,
        },
        "sensor_conversion": {
            "circle": "relative center and true radius when center distance <= R_obs",
            "analytic_boundary": (
                "sample each visible inner boundary component by arc length, include "
                "endpoints, and place support-disc centers one support radius into occupied space"
            ),
            "support_disc_radius_meters": OBSTACLE_REFERENCE_RADIUS_METERS,
            "maximum_arc_spacing_meters": OBSTACLE_REFERENCE_RADIUS_METERS / 2.0,
            "sampling_anchor": "component start in canonical primitive order",
            "ordering": "distance, primitive index, boundary side, arc index",
            "robot_visibility": "only ego-relative current support discs within R_obs",
        },
        "collision_truth_is_analytic": True,
        "sensor_tokens_are_not_collision_truth": True,
    }


def _dynamic_obstacle_contract() -> Dict[str, object]:
    return {
        "applicable_family": "F9",
        "primitive": "closed circle using stored radius_meters",
        "authoritative_motion_fields": "timestamped DynamicObstaclePath.waypoints",
        "position_update": "linear interpolation in absolute episode time on each waypoint segment",
        "velocity_update": "constant segment displacement divided by segment duration",
        "acceleration": "zero inside a segment; velocity changes atomically at waypoint timestamps",
        "before_first_waypoint": "hold first pose with zero velocity",
        "after_last_waypoint": "hold final pose with zero velocity",
        "looping": False,
        "reflection": False,
        "phase_seconds": 0.0,
        "declared_obstacle_speed_disposition": (
            "audit-only family-range descriptor; waypoint timestamps win because they "
            "form complete position-time pairs"
        ),
        "rejected_speed_alternative": (
            "constant declared speed cannot satisfy the frozen waypoint endpoint times"
        ),
        "collision": "continuous swept circle against linearly interpolated robot centers",
        "observation": {
            "range_formula": "center distance <= obstacle_sensing_range_meters",
            "latency_seconds": 0.0,
            "position_noise": "disabled",
            "velocity_noise": "disabled",
            "future_waypoints_robot_visible": False,
        },
        "snapshot_fields": ["segment_index", "episode_time", "position", "velocity"],
        "candidate_matching": "identical snapshot and dynamic_obstacle seed for both candidates",
        "invalidity": "nonpositive radius, nonfinite waypoint, or nonincreasing waypoint time",
    }


def _communication_contract() -> Dict[str, object]:
    return {
        "base_graph": {
            "edge_rule": "symmetric Euclidean distance <= communication_range_meters",
            "update_period": "communication_period_seconds",
            "directed_delivery": True,
            "message_emission": "one message per required schema per communication tick",
        },
        "nominal": {
            "delay_seconds": 0.0,
            "packet_drop_probability": 0.0,
            "assumption_class": "inside_method_assumptions",
        },
        "bounded_delay_loss": {
            "delay_distribution": "independent_uniform_closed[0,layout.delay_s] per directed message",
            "delivery_quantization": "first communication tick at or after send_time+delay",
            "drop_distribution": "independent Bernoulli(layout.packet_loss) per directed message",
            "draw_key": ["communication_seed", "sender", "receiver", "sequence", "message_type", "delay_or_drop"],
            "assumption_class": "inside_method_assumptions",
        },
        "temporary_disconnection_then_restore": {
            "base_delay_and_loss": "same stored F8 delay_s and packet_loss process",
            "start_formula": (
                "ceil(distance(start_center,first_passage_entry)/maximum_speed/communication_period)"
                "*communication_period"
            ),
            "duration_formula": "2*(D_max+1)*communication_period_seconds",
            "cut_rule": "drop every cross-partition message between role ordinals below and above ceil(N/2)",
            "queued_cross_cut_messages": "drop, never deliver after restoration",
            "restoration": "resume distance graph with empty cross-cut queues at first tick after duration",
            "assumption_class": "explicit_assumption_violation_stress",
            "outcome_treatment": "valid task-negative when the violation prevents completion; never generation-invalid by itself",
        },
        "diameter": {
            "D_max_formula": "team_size-1 for any connected component",
            "protocol_rounds": "derived from the declared component-diameter bound",
        },
        "freshness": {
            "maximum_age_seconds": "runtime communication.maximum_message_age_seconds",
            "stale_behavior": "exclude from local neighbour table and all agreements",
        },
        "schedule_seed": "source_job.seeds.communication",
        "snapshot_fields": ["tick", "per-link sequence", "queued messages", "PRF identity", "cut active"],
        "candidate_matching": "same counter-keyed schedule for both candidates; range gating may differ with candidate state",
    }


def _disturbance_contract() -> Dict[str, object]:
    return {
        "robot_acceleration": {
            "source_episode": "disabled except S5",
            "counterfactual_rollout": (
                "independent per-robot per-control-step uniform disk with maximum "
                "magnitude 0.05*maximum_acceleration, added before safety projection"
            ),
            "update_period": "control_period_seconds",
            "temporal_correlation": "zero; counter-keyed independent draws",
            "seed": "candidate_replica.seeds.matched_disturbance_seed",
            "draw_key": ["robot_acceleration", "robot_id", "control_step", "radius_or_angle"],
            "snapshot_state": "seed identity and control-step index",
            "candidate_matching": "same vector for matching robot and step",
        },
        "initial_velocity": "defined only by initialization_contract",
        "runtime_velocity_disturbance": "disabled",
        "robot_sensing_noise": "disabled",
        "obstacle_observation_noise": "disabled",
        "obstacle_observation_delay": "disabled",
        "dynamic_obstacle_uncertainty": "disabled",
        "communication_disturbance": "defined only by communication_degradation_contract",
        "reset": "all counter identities reset to the frozen episode or replica seed",
        "invalidity": "nonfinite generated value or magnitude outside the declared bound",
    }


def build_source_policy_contracts() -> Dict[str, object]:
    common = {
        "typed_interface": {
            "inputs": [
                "policy_id", "robot_local_view", "robot_local_lifecycle_state",
                "immutable_local_topology_metadata", "shared_mission_clock",
                "source_job_seed", "episode_horizon_seconds",
            ],
            "outputs": ["local_action_source", "optional_candidate_request", "event_eligibility"],
            "prohibited_inputs": [
                "headroom_category", "candidate_outcome", "future_obstacle_trajectory",
                "future_disturbance", "global_task_result", "final_test_metadata",
            ],
        },
        "decision_state_sampling": (
            "use only predeclared Phase 9B slots that occur while the episode is active; "
            "never move or replace an unavailable slot"
        ),
        "termination": "goal completion, declared horizon, or typed terminal failure",
    }
    scripts = {
        "F1": [],
        "F2": [[0.20, LINE], [0.65, COMPACT]],
        "F3": [[0.20, LINE], [0.65, COMPACT]],
        "F4": [[0.20, LINE], [0.70, COMPACT]],
        "F5": [[0.15, LINE], [0.35, COMPACT], [0.55, LINE], [0.75, COMPACT]],
        "F6": [[0.50, LINE]],
        "F7": [[0.33, LINE], [0.67, COMPACT]],
        "F8": [[0.20, LINE], [0.70, COMPACT]],
        "F9": [[0.33, LINE], [0.67, COMPACT]],
        "F10": [[0.40, LINE]],
    }
    policies = {
        "S0_SCRIPTED_DIAGNOSTIC": {
            "deployability": "offline_collection_only",
            "initial_topology": COMPACT,
            "action_source": "Phase 6 local controller plus safety projection",
            "topology_behavior": (
                "scripted desired topology follows the frozen smooth transition profile; "
                "offline oracle bypasses Phase 7 agreement but never safety projection"
            ),
            "event_rule": "one-shot normalized-horizon script table",
            "machine_readable_script": scripts,
            "communication": "normal episode communication; not used to select script events",
            "retry": "none; skipped or blocked script entries are not moved",
        },
        "S1_ALWAYS_COMPACT": {
            "deployability": "diagnostic_and_collection",
            "initial_topology": COMPACT,
            "action_source": "Phase 6 COMPACT local controller plus safety projection",
            "topology_behavior": "COMPACT remains committed for the complete episode",
            "event_rule": "no online candidate request",
            "communication": "normal local peer messages",
            "hold_semantics": "continue mission and obstacle response in COMPACT",
        },
        "S2_ALWAYS_LINE": {
            "deployability": "diagnostic_and_collection",
            "initial_topology": COMPACT,
            "action_source": "Phase 6 local controller plus safety projection",
            "topology_behavior": (
                "at time zero use the offline forced-topology qualification interface to "
                "initialize LINE role targets; no online request or epoch is created"
            ),
            "event_rule": "no online candidate request",
            "communication": "normal local peer messages",
            "hold_semantics": "LINE remains committed for the complete episode",
        },
        "S3_FROZEN_LOCAL_GEOMETRIC_SELECTOR": {
            "deployability": "robot_local",
            "initial_topology": COMPACT,
            "action_source": "Phase 6 controller plus safety projection in committed topology",
            "local_inputs": [
                "own state", "fresh one-hop messages", "ego-relative obstacle support discs",
                "mission direction", "local COMPACT and LINE role metadata", "local lifecycle state",
            ],
            "width_statistic": (
                "minimum free inner-surface separation from paired left/right boundary "
                "supports in the role-dependent lookahead sector"
            ),
            "required_width_formula": (
                "candidate lateral role span + 2*(robot_radius+obstacle_surface_margin)"
            ),
            "compact_to_line_rule": (
                "after evidence_persistence, request LINE iff measured width is at least "
                "LINE required width and less than COMPACT required width+spacing_margin"
            ),
            "line_to_compact_rule": (
                "after evidence_persistence, request COMPACT iff complete observation is "
                "open or measured width >= COMPACT required width+2*spacing_margin"
            ),
            "hysteresis_meters": "spacing_margin_meters",
            "minimum_commitment_seconds": "protocol.commitment_seconds",
            "unknown_behavior": "hold current topology and emit no intent",
            "tie_behavior": "hold current topology",
            "origination": (
                "each robot may originate only on its own threshold crossing; an adopted "
                "active intent suppresses later local origins"
            ),
            "transition": "every request uses Phase 7 readiness, agreement, confirmation and profile",
        },
        "S4_FROZEN_TRANSITION_PROTOCOL": {
            "deployability": "offline_collection_only",
            "initial_topology": COMPACT,
            "action_source": "Phase 6 controller plus safety projection",
            "local_event_source": (
                "role-0000 local mission clock at 0.25*horizon requests LINE and at "
                "0.65*horizon requests COMPACT if different from committed topology"
            ),
            "diagnostic_score": 1.0,
            "score_semantics": "bounded_diagnostic_candidate_available",
            "aggregation": "existing Phase 7 min/max score agreement",
            "candidate_selection": "the one candidate named by the scheduled local event",
            "lifecycle_origination": "role-0000 only; propagation and all decisions remain leaderless",
            "transition": "complete Phase 7 intent, score, readiness, all-ready, confirmation, profile and dwell",
            "timeout": "remaining episode horizon",
            "abort_rearm": "unchanged Phase 7 abort and rearm rules; no event retry",
            "no_event": "hold committed topology",
        },
        "S5_BOUNDED_PERTURBATION": {
            "deployability": "offline_collection_only",
            "base_policy": "S1_ALWAYS_COMPACT",
            "initial_topology": COMPACT,
            "action_source": "S1 action plus one bounded pre-projection acceleration perturbation",
            "perturbation_target": "one robot selected by seed modulo team size",
            "frame": "mission",
            "distribution": "uniform disk",
            "maximum_magnitude_formula": "0.25*maximum_acceleration_meters_per_second_squared",
            "start_time": "first control tick at or after 0.40*episode_horizon_seconds",
            "duration": "one control period",
            "repeat_count": 1,
            "seed": "source_job.seeds.initial_condition with S5 perturbation draw keys",
            "invalidity": "record invalid without resampling if perturbed command is nonfinite",
            "event_eligibility": "all predeclared active slots, including but not moved toward the perturbation",
        },
    }
    document: Dict[str, object] = {
        "schema_version": SOURCE_POLICY_CONTRACT_SCHEMA_VERSION,
        "phase8_protocol_hash": PHASE8_PROTOCOL_SHA256,
        "policy_ids": list(SOURCE_POLICY_IDS),
        "common_contract": common,
        "policies": policies,
        "category_d_count": 0,
    }
    return attach_canonical_hash(document, "source_policy_contract_sha256")


def build_target_v4_execution_contract() -> Dict[str, object]:
    base = RuntimeConfig()
    document: Dict[str, object] = {
        "schema_version": TARGET_V4_EXECUTION_CONTRACT_SCHEMA_VERSION,
        "phase8_protocol_hash": PHASE8_PROTOCOL_SHA256,
        "conditions": {
            "collision_free_complete_horizon": {
                "predicate": (
                    "no robot-robot, robot-static, robot-dynamic, or world-boundary "
                    "contact over every closed control interval"
                ),
                "robot_robot_threshold_meters": base.derived.robot_robot_required_clearance_meters,
                "continuous_check": "minimum distance of linearly interpolated centers over each interval",
                "tolerance_meters": NUMERICAL_GEOMETRY_TOLERANCE_METERS,
            },
            "no_persistent_deadlock": {
                "progress": "fitted topology-origin displacement along mission longitudinal axis",
                "threshold_meters": base.formation.spacing_margin_meters,
                "window_seconds": base.protocol.decision_reference_seconds,
                "paused_states": [
                    "INTENT_ACTIVE", "CANDIDATE_SCORE_AGREEMENT", "WAITING_FOR_LOCAL_READINESS",
                    "ALL_READY_AGREEMENT", "TOPOLOGY_CONFIRMATION", "TRANSITION_EXECUTION", "TARGET_DWELL",
                ],
                "predicate": "every complete unpaused window advances by at least threshold",
            },
            "candidate_commitment_valid": {
                "required": "candidate differs from committed topology after any active lifecycle resolves",
                "success": "all robot nodes commit the candidate in one lifecycle with no partial commitment",
                "candidate_equals_current": "true without creating an epoch",
            },
            "transition_execution_valid": {
                "candidate_equals_current": "true; continue hold behavior",
                "candidate_differs": "Phase 7 profile reaches candidate Metric V3 tube without abort or timeout",
                "projection_infeasibility": "false until a later successful projection resolves it; collision still latches",
            },
            "target_metric_v3_dwell_complete": {
                "target": "candidate topology",
                "entry": "Metric V3 e_inf <= formation_tolerance_meters",
                "duration_seconds": base.mission.recovery_dwell_seconds,
                "clock": "continuous physical time sampled at control boundaries",
                "interruption": "reset dwell clock to zero",
            },
            "downstream_goal_complete": {
                "quantity": "least-squares candidate topology origin",
                "target": "ScenarioLayout.goal_center_meters",
                "tolerance_meters": base.derived.formation_tolerance_meters,
                "required_dwell_seconds": base.physical.control_period_seconds,
            },
            "protocol_resolved": {
                "success_states": ["STABLE_TOPOLOGY", "COMPLETE", "REARMED"],
                "failure_states": ["ABORTED", "active_state_at_horizon", "partial_commitment"],
                "assumption_violation": "valid task-negative, not generation-invalid",
            },
            "safety_projection_resolved": {
                "infeasible_or_solver_failure": "latch unresolved",
                "conservative_fallback": "finite zero action; latch clears after next feasible successful projection",
                "persistent_intervention": "not failure by itself when every projection is feasible",
            },
            "numerically_valid": {
                "predicate": "all state, action, geometry, queue time and metric values are finite and schema-valid",
                "failure": "generation-invalid",
            },
            "no_irreversible_progress_loss": {
                "predicate": (
                    "after any drop greater than nominal_spacing from maximum attained "
                    "longitudinal progress, progress returns within spacing_margin of that maximum before termination"
                ),
                "temporary_delay": "does not fail unless the terminal recovery condition remains unmet",
            },
        },
        "evaluation_precedence": [
            "generation validity", "collision", "irreversible progress", "deadlock",
            "protocol and commitment", "safety and transition", "Metric V3 dwell", "goal",
        ],
        "termination_causes": list(TERMINATION_CAUSES),
        "dispositions": list(TARGET_DISPOSITIONS),
        "positive_rule": "GOAL_COMPLETE and all ten predicates true",
        "valid_negative_rule": "generation valid and positive rule false",
        "generation_invalid_rule": (
            "initialization, geometry, schedule, numerical, schema, or executor validity failure"
        ),
        "exception_policy": "every exception becomes typed EXECUTOR_EXCEPTION; never an implicit label",
        "category_d_count": 0,
    }
    return attach_canonical_hash(document, "target_v4_execution_contract_sha256")


def _counterfactual_contract() -> Dict[str, object]:
    return {
        "rollout_start": "resolved decision-event timestamp after source step completion",
        "snapshot_contents": [
            "time and control index", "positions velocities accelerations", "roles",
            "committed topologies", "transition profile and protocol nodes", "controller state",
            "safety latches", "message queues and timestamps", "communication schedule state",
            "disturbance counters", "dynamic obstacle state", "mission progress", "event state",
        ],
        "clone_rule": "two independent deep clones with byte-identical canonical snapshot hash",
        "candidate_injection_time": "same next communication tick in both clones",
        "candidate_equals_current": "hold or continue; no source-equals-target epoch",
        "candidate_differs_stable": "originate candidate through Phase 7",
        "candidate_matches_active_target": "continue the existing lifecycle",
        "candidate_differs_from_active_target": (
            "do not supersede; resolve or abort active lifecycle, wait for REARMED, then issue candidate if horizon remains"
        ),
        "protocol_initialization": "preserve source lifecycle exactly",
        "horizon": "remaining time to ScenarioLayout.episode_horizon_seconds",
        "candidate_timeout": "remaining episode horizon; no independent hidden timeout",
        "mission_timeout": "absolute family episode horizon",
        "replicas": "one except three matched replicas for F8 and F9",
        "aggregation": "all_success",
        "matching": [
            "initial snapshot hash", "source lifecycle hash", "horizon", "communication schedule identity",
            "matched disturbance seed", "dynamic obstacle snapshot and seed", "runtime configuration hash",
        ],
        "invalid_pair": "generation-invalid pair; emit no training row and never replace",
    }


def _seed_binding() -> Dict[str, object]:
    return {
        "prf_version": PRF_VERSION,
        "uniform_formula": (
            "u=uint64_be(SHA256(canonical_json([prf_version,seed,process,*counter]))[0:8])/2^64"
        ),
        "closed_interval_mapping": "a+(b-a)*u; upper endpoint is approached but not exceeded",
        "uniform_disk_mapping": "radius=max_radius*sqrt(u_radius), angle=2*pi*u_angle",
        "job_order_independent": True,
        "streams": {
            "initial_condition": "source_job.seeds.initial_condition",
            "communication": "source_job.seeds.communication",
            "dynamic_obstacle": "source_job.seeds.dynamic_obstacle; deterministic v1 path uses no random draw",
            "data_sampling": "source_job.seeds.data_sampling",
            "counterfactual_disturbance": "candidate_replica.seeds.matched_disturbance_seed",
        },
        "final_test": "seed construction rejected without the existing one-time authorization gate",
    }


def build_executable_protocol(root: Path) -> Dict[str, object]:
    root = root.resolve()
    source_contract = build_source_policy_contracts()
    target_contract = build_target_v4_execution_contract()
    document: Dict[str, object] = {
        "schema_version": EXECUTABLE_PROTOCOL_SCHEMA_VERSION,
        "phase8_protocol_hash": PHASE8_PROTOCOL_SHA256,
        "generation_budget_hash": GENERATION_BUDGET_SHA256,
        "composite_generation_protocol_hash": COMPOSITE_GENERATION_PROTOCOL_SHA256,
        "frozen_job_manifest_hash": FROZEN_JOB_MANIFEST_SHA256,
        "source_commits": {
            "phase8_protocol": PHASE8_PROTOCOL_COMMIT,
            "phase9b_budget": PHASE9B_BUDGET_COMMIT,
            "phase9c_blocked_audit": PHASE9C_BLOCKED_AUDIT_COMMIT,
        },
        "scenario_geometry_contract": _geometry_contract(),
        "initialization_contract": _initialization_contract(),
        "static_obstacle_contract": _static_obstacle_contract(),
        "dynamic_obstacle_contract": _dynamic_obstacle_contract(),
        "communication_degradation_contract": _communication_contract(),
        "disturbance_contract": _disturbance_contract(),
        "source_policy_contracts": {
            "schema_version": source_contract["schema_version"],
            "sha256": source_contract["source_policy_contract_sha256"],
        },
        "target_v4_execution_contract": {
            "schema_version": target_contract["schema_version"],
            "sha256": target_contract["target_v4_execution_contract_sha256"],
        },
        "counterfactual_execution_contract": _counterfactual_contract(),
        "simulator_semantics": {
            "specification_only": True,
            "control_period_seconds": RuntimeConfig().physical.control_period_seconds,
            "integration": "frozen semi-implicit acceleration step",
            "collision_checking": "continuous swept check plus control-boundary state checks",
            "clock": "integer control step multiplied by control period",
            "timeout": "first control boundary at or beyond absolute horizon",
            "runtime_binding_implemented": False,
            "simulator_steps_executed": 0,
        },
        "seed_binding": _seed_binding(),
        "final_test_access_policy": {
            "geometry_compilation": "prohibited",
            "permitted_metadata": {
                "layout_count": 10,
                "family_count": 10,
                "manifest_sha256": "e225a3114dfb2d74e8a691f24484898de1481a6f8f243bcc3eabbfba5aff8d0f",
                "schema_compatibility": "rvt-layout-split/v1 metadata only",
            },
            "metadata_source": "approved Phase 8 protocol manifest and split contract; sealed layout records not opened",
            "runtime_access_count": 0,
        },
        "configuration_hashes": {
            "runtime_by_team_size": _runtime_configuration_hashes(),
            "scenario_schema_source_sha256": file_sha256(root / "rvt_swarm/phase8/scenario.py"),
            "topology_registry_source_sha256": file_sha256(root / "rvt_swarm/topology_registry.py"),
            "phase8_experiment_manifest_file_sha256": file_sha256(
                root / "results/rvt_fd24/experiment_protocol_manifest.json"
            ),
        },
        "category_d_count": 0,
    }
    return attach_canonical_hash(document, "protocol_hash")


def validate_executable_protocol(document: object) -> None:
    doc = _exact_keys(document, _PROTOCOL_KEYS, "protocol")
    if doc["schema_version"] != EXECUTABLE_PROTOCOL_SCHEMA_VERSION:
        raise ValueError("unknown executable protocol schema")
    references = {
        "phase8_protocol_hash": PHASE8_PROTOCOL_SHA256,
        "generation_budget_hash": GENERATION_BUDGET_SHA256,
        "composite_generation_protocol_hash": COMPOSITE_GENERATION_PROTOCOL_SHA256,
        "frozen_job_manifest_hash": FROZEN_JOB_MANIFEST_SHA256,
    }
    for field, expected in references.items():
        if doc[field] != expected:
            raise ValueError(f"invalid protocol provenance: {field}")
    if doc["category_d_count"] != 0:
        raise ValueError("executable protocol contains unresolved Category D values")
    geometry = _exact_keys(
        doc["scenario_geometry_contract"],
        {
            "world_frame", "mission_frame", "goal_region", "centerline_semantics",
            "family_compilers", "layout_field_dispositions", "invalidity_conditions",
            "geometry_tolerance_meters", "headroom_use",
        },
        "scenario_geometry_contract",
    )
    _exact_keys(
        geometry["world_frame"],
        {"frame_id", "origin_meters", "x_axis", "y_axis", "bounds_meters", "bounds_rationale"},
        "scenario_geometry_contract.world_frame",
    )
    if geometry["headroom_use"] != "audit_only_prohibited_from_compilation_and_execution":
        raise ValueError("headroom execution use is prohibited")
    major_contract_keys = {
        "initialization_contract": {
            "initial_topology", "topology_origin_formula", "topology_orientation_formula",
            "role_assignment", "nominal_pose_formula", "position_perturbation",
            "velocity_perturbation", "initial_acceleration_meters_per_second_squared",
            "controller_local_state", "protocol_state", "message_queues",
            "communication_state", "dynamic_obstacle_phase", "mission_progress",
            "invalidity_handling",
        },
        "static_obstacle_contract": {
            "truth_geometry", "collision_inflation", "sensor_conversion",
            "collision_truth_is_analytic", "sensor_tokens_are_not_collision_truth",
        },
        "dynamic_obstacle_contract": {
            "applicable_family", "primitive", "authoritative_motion_fields",
            "position_update", "velocity_update", "acceleration", "before_first_waypoint",
            "after_last_waypoint", "looping", "reflection", "phase_seconds",
            "declared_obstacle_speed_disposition", "rejected_speed_alternative",
            "collision", "observation", "snapshot_fields", "candidate_matching",
            "invalidity",
        },
        "communication_degradation_contract": {
            "base_graph", "nominal", "bounded_delay_loss",
            "temporary_disconnection_then_restore", "diameter", "freshness",
            "schedule_seed", "snapshot_fields", "candidate_matching",
        },
        "disturbance_contract": {
            "robot_acceleration", "initial_velocity", "runtime_velocity_disturbance",
            "robot_sensing_noise", "obstacle_observation_noise",
            "obstacle_observation_delay", "dynamic_obstacle_uncertainty",
            "communication_disturbance", "reset", "invalidity",
        },
        "counterfactual_execution_contract": {
            "rollout_start", "snapshot_contents", "clone_rule", "candidate_injection_time",
            "candidate_equals_current", "candidate_differs_stable",
            "candidate_matches_active_target", "candidate_differs_from_active_target",
            "protocol_initialization", "horizon", "candidate_timeout", "mission_timeout",
            "replicas", "aggregation", "matching", "invalid_pair",
        },
        "seed_binding": {
            "prf_version", "uniform_formula", "closed_interval_mapping",
            "uniform_disk_mapping", "job_order_independent", "streams", "final_test",
        },
        "final_test_access_policy": {
            "geometry_compilation", "permitted_metadata", "metadata_source",
            "runtime_access_count",
        },
        "configuration_hashes": {
            "runtime_by_team_size", "scenario_schema_source_sha256",
            "topology_registry_source_sha256", "phase8_experiment_manifest_file_sha256",
        },
    }
    for field, keys in major_contract_keys.items():
        _exact_keys(doc[field], keys, field)
    simulator = _exact_keys(
        doc["simulator_semantics"],
        {
            "specification_only", "control_period_seconds", "integration",
            "collision_checking", "clock", "timeout", "runtime_binding_implemented",
            "simulator_steps_executed",
        },
        "simulator_semantics",
    )
    if simulator["specification_only"] is not True:
        raise ValueError("Phase 8E must remain specification-only")
    if simulator["runtime_binding_implemented"] is not False:
        raise ValueError("Phase 8E cannot implement the runtime binding")
    if simulator["simulator_steps_executed"] != 0:
        raise ValueError("Phase 8E cannot execute simulator steps")
    if not verify_canonical_hash(dict(doc), "protocol_hash"):
        raise ValueError("invalid executable protocol hash")


def validate_source_policy_contracts(document: object) -> None:
    doc = _exact_keys(
        document,
        {
            "schema_version", "phase8_protocol_hash", "policy_ids",
            "common_contract", "policies", "category_d_count",
            "source_policy_contract_sha256",
        },
        "source_policy_contracts",
    )
    if doc["schema_version"] != SOURCE_POLICY_CONTRACT_SCHEMA_VERSION:
        raise ValueError("unknown source-policy contract schema")
    if tuple(doc["policy_ids"]) != SOURCE_POLICY_IDS:
        raise ValueError("source-policy ID set or order is invalid")
    policies = doc["policies"]
    if not isinstance(policies, Mapping) or frozenset(policies) != frozenset(SOURCE_POLICY_IDS):
        raise ValueError("every S0-S5 source policy must be defined exactly once")
    if doc["category_d_count"] != 0:
        raise ValueError("source policy contains unresolved Category D")
    for policy_id, expected_keys in _SOURCE_POLICY_REQUIRED_KEYS.items():
        _exact_keys(policies[policy_id], expected_keys, f"policies.{policy_id}")
    if not verify_canonical_hash(dict(doc), "source_policy_contract_sha256"):
        raise ValueError("invalid source-policy contract hash")


def validate_target_v4_execution_contract(document: object) -> None:
    doc = _exact_keys(
        document,
        {
            "schema_version", "phase8_protocol_hash", "conditions",
            "evaluation_precedence", "termination_causes", "dispositions",
            "positive_rule", "valid_negative_rule", "generation_invalid_rule",
            "exception_policy", "category_d_count",
            "target_v4_execution_contract_sha256",
        },
        "target_v4_execution_contract",
    )
    if doc["schema_version"] != TARGET_V4_EXECUTION_CONTRACT_SCHEMA_VERSION:
        raise ValueError("unknown Target V4 execution contract schema")
    if frozenset(doc["conditions"]) != frozenset({
        "collision_free_complete_horizon", "no_persistent_deadlock",
        "candidate_commitment_valid", "transition_execution_valid",
        "target_metric_v3_dwell_complete", "downstream_goal_complete",
        "protocol_resolved", "safety_projection_resolved", "numerically_valid",
        "no_irreversible_progress_loss",
    }):
        raise ValueError("Target V4 must define exactly ten conditions")
    condition_keys = {
        "collision_free_complete_horizon": {
            "predicate", "robot_robot_threshold_meters", "continuous_check",
            "tolerance_meters",
        },
        "no_persistent_deadlock": {
            "progress", "threshold_meters", "window_seconds", "paused_states", "predicate",
        },
        "candidate_commitment_valid": {"required", "success", "candidate_equals_current"},
        "transition_execution_valid": {
            "candidate_equals_current", "candidate_differs", "projection_infeasibility",
        },
        "target_metric_v3_dwell_complete": {
            "target", "entry", "duration_seconds", "clock", "interruption",
        },
        "downstream_goal_complete": {
            "quantity", "target", "tolerance_meters", "required_dwell_seconds",
        },
        "protocol_resolved": {"success_states", "failure_states", "assumption_violation"},
        "safety_projection_resolved": {
            "infeasible_or_solver_failure", "conservative_fallback", "persistent_intervention",
        },
        "numerically_valid": {"predicate", "failure"},
        "no_irreversible_progress_loss": {"predicate", "temporary_delay"},
    }
    for condition, expected_keys in condition_keys.items():
        _exact_keys(doc["conditions"][condition], expected_keys, f"conditions.{condition}")
    if tuple(doc["termination_causes"]) != TERMINATION_CAUSES:
        raise ValueError("Target V4 termination vocabulary is incomplete")
    if tuple(doc["dispositions"]) != TARGET_DISPOSITIONS:
        raise ValueError("Target V4 disposition vocabulary is incomplete")
    if doc["category_d_count"] != 0:
        raise ValueError("Target V4 contains unresolved Category D")
    if not verify_canonical_hash(dict(doc), "target_v4_execution_contract_sha256"):
        raise ValueError("invalid Target V4 execution contract hash")


def counter_uniform(seed: int, process: str, *counter: object) -> float:
    """Exact order-independent uniform primitive declared by the seed contract."""
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise ValueError("counter PRF seed must be a nonnegative integer")
    if not process:
        raise ValueError("counter PRF process must be nonempty")
    payload = [PRF_VERSION, seed, process, *counter]
    integer = int.from_bytes(
        hashlib.sha256(canonical_json_bytes(payload)).digest()[:8], "big"
    )
    return integer / float(1 << 64)


def s3_local_geometric_decision(
    committed_topology: int,
    *,
    measured_width_meters: float | None,
    complete_open_observation: bool,
    complete_observation: bool,
    line_required_width_meters: float,
    compact_required_width_meters: float,
    spacing_margin_meters: float,
    evidence_duration_seconds: float,
    evidence_persistence_seconds: float,
) -> str:
    """Total pure rule for the frozen S3 local geometric selector."""
    if committed_topology not in (COMPACT, LINE):
        raise ValueError("S3 committed topology must be COMPACT or LINE")
    values = (
        line_required_width_meters,
        compact_required_width_meters,
        spacing_margin_meters,
        evidence_duration_seconds,
        evidence_persistence_seconds,
    )
    if not all(math.isfinite(value) and value >= 0.0 for value in values):
        raise ValueError("S3 geometry and time inputs must be finite and nonnegative")
    if line_required_width_meters > compact_required_width_meters:
        raise ValueError("LINE required width cannot exceed COMPACT required width")
    if evidence_duration_seconds < evidence_persistence_seconds:
        return "HOLD_INSUFFICIENT_EVIDENCE"
    if complete_open_observation and complete_observation:
        return "REQUEST_COMPACT" if committed_topology == LINE else "HOLD_COMPACT"
    if not complete_observation or measured_width_meters is None:
        return "HOLD_UNKNOWN"
    width = float(measured_width_meters)
    if not math.isfinite(width) or width < 0.0:
        raise ValueError("S3 measured width must be finite and nonnegative")
    if width < line_required_width_meters:
        return "HOLD_UNKNOWN"
    if committed_topology == COMPACT:
        if width < compact_required_width_meters + spacing_margin_meters:
            return "REQUEST_LINE"
        return "HOLD_COMPACT"
    if width >= compact_required_width_meters + 2.0 * spacing_margin_meters:
        return "REQUEST_COMPACT"
    return "HOLD_LINE"


def mission_axes(start: Sequence[float], goal: Sequence[float]) -> Tuple[Tuple[float, float], Tuple[float, float]]:
    dx = float(goal[0]) - float(start[0])
    dy = float(goal[1]) - float(start[1])
    norm = math.hypot(dx, dy)
    if not math.isfinite(norm) or norm <= 0.0:
        raise ValueError("start and goal must define a finite mission heading")
    longitudinal = (dx / norm, dy / norm)
    return longitudinal, (-longitudinal[1], longitudinal[0])
