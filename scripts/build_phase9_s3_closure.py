#!/usr/bin/env python3
"""Build canonical Phase 9G-A1S3 closure artifacts from read-only evidence."""

from __future__ import annotations

import hashlib
import json
import math
import struct
from pathlib import Path

from rvt_swarm.phase8.common import attach_canonical_hash, sha256_document


A1R_COMMIT = "a943ca391fb5feb5c8e90a693f763cc47c4d4e2b"
OLD_IMAGE = "sha256:88ecf1aac7cd95b5ba50811950090c13f78362274e5c5cdaeafaafde29a115f4"
BRANCH = "research/rvt-phase9g-a1s3-scientific-closure-v1"


def _file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical(path: Path, field: str) -> dict:
    document = json.loads(path.read_text(encoding="ascii"))
    body = dict(document)
    expected = str(body.pop(field, ""))
    if sha256_document(body) != expected:
        raise ValueError(f"canonical artifact mismatch: {path.name}")
    return document


def _write(path: Path, document: dict, hash_field: str) -> dict:
    document = attach_canonical_hash(document, hash_field)
    path.write_text(
        json.dumps(document, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )
    return document


def _authority_source(root: Path, relative: str, classification: str,
                      authority_scope: str) -> dict:
    path = root / relative
    return {
        "path": relative,
        "file_sha256": _file_sha(path),
        "classification": classification,
        "authority_scope": authority_scope,
    }


def _selector_width(tokens, direction, lateral, lookahead):
    left = []
    right = []
    for offset, radius, source_key in tokens:
        longitudinal = offset[0] * direction[0] + offset[1] * direction[1]
        lateral_offset = offset[0] * lateral[0] + offset[1] * lateral[1]
        if 0.0 <= longitudinal <= lookahead:
            row = {
                "source_key": source_key,
                "lateral_offset_meters": lateral_offset,
                "inner_surface_projection_meters": abs(lateral_offset) - radius,
            }
            (left if lateral_offset >= 0.0 else right).append(row)
    selected_left = min(left, key=lambda item: item["inner_surface_projection_meters"])
    selected_right = min(right, key=lambda item: item["inner_surface_projection_meters"])
    return (
        selected_left["inner_surface_projection_meters"]
        + selected_right["inner_surface_projection_meters"],
        selected_left,
        selected_right,
    )


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    results = root / "results/rvt_fd24"

    checkpoint = _canonical(
        results / "phase9_s3_staging_checkpoint_v1.json",
        "phase9_s3_staging_checkpoint_sha256",
    )
    width_reference = _canonical(
        results / "phase9_s3_width_derivation_reference_v1.json",
        "phase9_s3_width_derivation_sha256",
    )
    width_docker = _canonical(
        results / "phase9_s3_width_derivation_docker_v1.json",
        "phase9_s3_width_derivation_sha256",
    )
    population_reference = _canonical(
        results / "phase9_s3_population_audit_reference_v1.json",
        "phase9_s3_population_audit_sha256",
    )
    population_docker = _canonical(
        results / "phase9_s3_population_audit_docker_v1.json",
        "phase9_s3_population_audit_sha256",
    )
    dependency = _canonical(
        results / "phase9_s3_staging_dependency_audit_v1.json",
        "phase9_s3_staging_dependency_audit_sha256",
    )

    reference_projection = {
        "blocked_task": width_reference["blocked_task"],
        "failure_call": width_reference["failure_call"],
        "coordinate_frames": width_reference["coordinate_frames"],
        "formula": width_reference["formula"],
        "direct_operands": width_reference["direct_operands"],
        "selected_supports": width_reference["selected_supports"],
        "physical_geometry": width_reference["physical_geometry"],
        "representational_ordering_tests": width_reference[
            "representational_ordering_tests"
        ],
        "call_audit": width_reference["call_audit"],
    }
    docker_projection = {
        key: width_docker[key] for key in reference_projection
    }
    if reference_projection != docker_projection:
        raise ValueError("reference and qualified Docker width projections differ")
    if (
        population_reference["semantic_projection_sha256"]
        != population_docker["semantic_projection_sha256"]
    ):
        raise ValueError("reference and qualified Docker population projections differ")
    expected_width = -0.6143634774571596
    measured = width_reference["direct_operands"]["measured_width"]
    if measured["value"] != expected_width or measured["float_hex"] != (
        "-0x1.3a8dd98712174p-1"
    ):
        raise ValueError("blocked width identity changed")
    layout_path = (
        results / "layout_execution_specifications/train/train-f3-01.json"
    )
    layout = json.loads(layout_path.read_text(encoding="ascii"))
    mission = width_reference["coordinate_frames"]["mission"]
    direction = tuple(mission["longitudinal_axis"])
    lateral = tuple(mission["lateral_axis"])
    lookahead = width_reference["direct_operands"]["lookahead_distance"]["value"]
    tokens = tuple(
        (
            tuple(row["relative_center_meters"]),
            float(row["radius_meters"]),
            str(row["source_key"]),
        )
        for row in width_reference["observable_supports"]
    )
    rotated_tokens = tuple(
        ((-offset[1], offset[0]), radius, source_key)
        for offset, radius, source_key in tokens
    )
    rotated_width, rotated_left, rotated_right = _selector_width(
        rotated_tokens,
        (-direction[1], direction[0]),
        (-lateral[1], lateral[0]),
        lookahead,
    )
    if struct.pack(">d", rotated_width) != struct.pack(">d", expected_width):
        raise ValueError("rigid 90-degree rotation changed blocked width bits")
    robot_position = width_reference["failure_call"]["robot_position_meters"]
    selected_world_centers = {
        side: [
            robot_position[0] + width_reference["selected_supports"][side][
                "relative_center_meters"
            ][0],
            robot_position[1] + width_reference["selected_supports"][side][
                "relative_center_meters"
            ][1],
        ]
        for side in ("left", "right")
    }

    width = _write(
        results / "phase9_s3_width_derivation_v1.json",
        {
            "schema_version": "rvt-phase9-s3-width-derivation-closure/v1",
            "status": "EXACT_NEGATIVE_REPRODUCED",
            "mode": "NON_OFFICIAL_READ_ONLY_DIAGNOSTIC",
            "raw_evidence": {
                "reference": {
                    "artifact": "phase9_s3_width_derivation_reference_v1.json",
                    "canonical_sha256": width_reference[
                        "phase9_s3_width_derivation_sha256"
                    ],
                    "file_sha256": _file_sha(
                        results / "phase9_s3_width_derivation_reference_v1.json"
                    ),
                },
                "qualified_production_docker": {
                    "artifact": "phase9_s3_width_derivation_docker_v1.json",
                    "canonical_sha256": width_docker[
                        "phase9_s3_width_derivation_sha256"
                    ],
                    "file_sha256": _file_sha(
                        results / "phase9_s3_width_derivation_docker_v1.json"
                    ),
                    "image": OLD_IMAGE,
                },
            },
            "blocked_task": width_reference["blocked_task"],
            "failure_call": width_reference["failure_call"],
            "coordinate_frames": width_reference["coordinate_frames"],
            "formula": width_reference["formula"],
            "direct_operands": width_reference["direct_operands"],
            "selected_supports": width_reference["selected_supports"],
            "selected_support_world_centers_meters": selected_world_centers,
            "source_geometry_trace": {
                "layout_id": width_reference["blocked_task"]["layout_id"],
                "layout_sha256": width_reference["blocked_task"]["layout_sha256"],
                "layout_file_sha256": _file_sha(layout_path),
                "source_centerline": layout["centerline"],
                "mission_start_meters": layout["centerline"][
                    "control_points_meters"
                ][0],
                "mission_goal": layout["goal_contract"],
                "canonical_parameters": layout["canonical_parameters"],
                "source_passage": layout["passages"][0],
                "world_bounds_meters": layout["world_bounds_meters"],
                "static_obstacles": layout["static_obstacles"],
                "dynamic_obstacles": layout["dynamic_obstacles"],
                "compiler_transforms": [
                    {
                        "operation": "clip full centerline to active world-x slab",
                        "input": layout["centerline"]["control_points_meters"],
                        "output": width_reference["physical_geometry"][
                            "centerline_control_points_meters"
                        ],
                        "frozen": True,
                    },
                    {
                        "operation": "half_width = free_width / 2",
                        "input_meters": layout["passages"][0]["free_width_meters"],
                        "output_meters": width_reference["physical_geometry"][
                            "half_width_meters"
                        ],
                        "frozen": True,
                    },
                    {
                        "operation": "offset clipped centerline by +/- half_width along vertex normals",
                        "positive_output_meters": width_reference["physical_geometry"][
                            "positive_boundary_control_points_meters"
                        ],
                        "negative_output_meters": width_reference["physical_geometry"][
                            "negative_boundary_control_points_meters"
                        ],
                        "frozen": True,
                    },
                    {
                        "operation": (
                            "sample each boundary by arc length at <=0.175 m and "
                            "place support center 0.35 m into occupied space"
                        ),
                        "output": "observable_supports in raw diagnostic artifact",
                        "frozen": True,
                    },
                    {
                        "operation": "subtract robot world position from support world center",
                        "output_frame": "ego-relative world axes",
                        "frozen": True,
                    },
                ],
                "unit_conversion": {
                    "source_unit": "meters",
                    "runtime_unit": "meters",
                    "scale": 1.0,
                    "conversion_performed": False,
                },
                "numeric_types": {
                    "layout_json_numbers": "JSON number decoded to Python binary64 float",
                    "runtime_geometry": "Python float / IEEE-754 binary64",
                    "projection_operands": "Python float / IEEE-754 binary64",
                },
            },
            "physical_geometry": width_reference["physical_geometry"],
            "representational_ordering_tests": width_reference[
                "representational_ordering_tests"
            ],
            "call_summary": {
                "s3_calls_before_exception": width_reference["call_audit"][
                    "s3_calls_before_exception"
                ],
                "negative_calls_before_exception": width_reference["call_audit"][
                    "negative_calls_before_exception"
                ],
                "first_six_negative_calls_hidden_by_insufficient_evidence": True,
                "seventh_negative_call_reached_totality_guard": True,
            },
            "cross_platform_classification": {
                "result": "SAME_EXACT_NEGATIVE_RESULT",
                "semantic_projection_exact": True,
                "binary64_exact": True,
                "portability_framework_routing_required": False,
            },
            "rigid_layout_rotation_test": {
                "rotation_degrees": 90,
                "rotation_formula": "(x,y)->(-y,x) for tokens and mission axes",
                "physical_geometry_changed": False,
                "rotated_width_meters": rotated_width,
                "rotated_width_float_hex": rotated_width.hex(),
                "rotated_width_binary64_big_endian_hex": struct.pack(
                    ">d", rotated_width
                ).hex(),
                "bit_equal": True,
                "sign_changed": math.copysign(1.0, rotated_width)
                != math.copysign(1.0, expected_width),
                "rotated_left_source_key": rotated_left["source_key"],
                "rotated_right_source_key": rotated_right["source_key"],
            },
            "first_principles_finding": (
                "The selector chose corridor-0-left-4 and corridor-0-left-3. "
                "They are samples of one compiled physical boundary component, "
                "although their ego mission-lateral projections have opposite signs."
            ),
            "scientific_writes": 0,
            "sealed_scope": dict(width_reference["sealed_scope"]),
        },
        "phase9_s3_width_derivation_closure_sha256",
    )

    authority_sources = [
        _authority_source(
            root, "results/rvt_fd24/source_policy_contracts_v1.json",
            "CURRENT_AUTHORITATIVE",
            "Frozen S3 purpose, local inputs, output rules, and width statistic.",
        ),
        _authority_source(
            root, "docs/PHASE8E_SOURCE_POLICY_EXECUTION_CONTRACTS.md",
            "CURRENT_AUTHORITATIVE",
            "Frozen prose rule that contradictory data is UNKNOWN.",
        ),
        _authority_source(
            root, "results/rvt_fd24/executable_scientific_protocol_v1.json",
            "CURRENT_AUTHORITATIVE",
            "Frozen analytic geometry and local support-disc sensor conversion.",
        ),
        _authority_source(
            root, "results/rvt_fd24/source_event_timing_addendum_v1.json",
            "CURRENT_AUTHORITATIVE",
            "Frozen S3/S4 local evidence and event timing semantics.",
        ),
        _authority_source(
            root, "rvt_swarm/phase8e/protocol.py",
            "CURRENT_AUTHORITATIVE",
            "Executable totality guard and S3 decision output semantics.",
        ),
        _authority_source(
            root, "rvt_swarm/phase9c_rb/policies.py",
            "CURRENT_AUTHORITATIVE",
            "Current executable width estimator; implementation is not authority to fill a specification gap.",
        ),
        _authority_source(
            root, "rvt_swarm/phase9c_rb/world.py",
            "CURRENT_AUTHORITATIVE",
            "Current analytic corridor and support-disc construction.",
        ),
        _authority_source(
            root, "rvt_swarm/phase9g0r/compiler.py",
            "CURRENT_AUTHORITATIVE",
            "Frozen task identity and authorized manifest compilation.",
        ),
        _authority_source(
            root, "rvt_swarm/phase9g0r/producer.py",
            "CURRENT_AUTHORITATIVE",
            "Qualified source-session and candidate-production execution path.",
        ),
        _authority_source(
            root, "results/rvt_fd24/phase9g_a1r_continuation_stop_audit_v1.json",
            "HISTORICAL",
            "Immutable evidence of the production hard stop; not new S3 science.",
        ),
        _authority_source(
            root, "results/rvt_fd24/phase9_s3_width_derivation_reference_v1.json",
            "DIAGNOSTIC",
            "Reference-host measurement; evidence, not scientific authority.",
        ),
        _authority_source(
            root, "results/rvt_fd24/phase9_s3_width_derivation_docker_v1.json",
            "DIAGNOSTIC",
            "Qualified-image reproduction; evidence, not scientific authority.",
        ),
    ]
    authority = _write(
        results / "phase9_s3_geometry_authority_v1.json",
        {
            "schema_version": "rvt-phase9-s3-geometry-authority/v1",
            "status": "SCIENTIFIC_DEFINITION_INCOMPLETE",
            "frozen_identity": {
                "a1r_commit": A1R_COMMIT,
                "scientific_source_commit": checkpoint["scientific_binding"][
                    "source_commit"
                ],
                "qualified_image": OLD_IMAGE,
            },
            "s3_executable_contract": {
                "identifier": "S3_FROZEN_LOCAL_GEOMETRIC_SELECTOR",
                "definition": "frozen deployable robot-local geometric topology selector",
                "purpose": (
                    "Originate COMPACT/LINE requests from persistent local geometric "
                    "evidence while retaining Phase-7 readiness, agreement, confirmation, "
                    "profile, abort, rearm, controller, and safety semantics."
                ),
                "inputs": [
                    "own state",
                    "fresh one-hop messages",
                    "ego-relative obstacle support discs",
                    "mission direction",
                    "local COMPACT and LINE role metadata",
                    "local lifecycle state",
                ],
                "outputs": [
                    "HOLD_INSUFFICIENT_EVIDENCE", "HOLD_UNKNOWN", "HOLD_COMPACT",
                    "HOLD_LINE", "REQUEST_LINE", "REQUEST_COMPACT",
                ],
                "direct_consumer": "Phase-7 transition intent origination",
                "downstream_consumers": [
                    "source episode state and event timing",
                    "counterfactual source snapshot",
                    "candidate rollout controller and local safety trajectory",
                    "Target V4 predicates and aggregate disposition",
                    "ego-graph payload, row identity, and label through the resulting trajectory",
                ],
                "target_v4_direct_width_input": False,
            },
            "width_semantics": {
                "authoritative_quantity": (
                    "minimum free inner-surface separation from paired left/right "
                    "boundary supports in the role-dependent lookahead sector"
                ),
                "category": "UNSIGNED_LOCAL_FREE_SPACE_SPAN",
                "negative_value_mathematically_permitted": False,
                "negative_value_executable_totality_rule": (
                    "reject as ValueError; the total decision contract accepts only "
                    "finite nonnegative measured width"
                ),
                "contradictory_or_incomplete_observation_rule": "HOLD_UNKNOWN",
            },
            "runtime_information_loss": {
                "world_support_identity": (
                    "corridor primitive, physical boundary side, and arc index"
                ),
                "robot_view_token": "ego-relative (dx, dy, radius) only",
                "component_identity_available_to_s3": False,
                "blocked_pair": ["corridor-0-left-4", "corridor-0-left-3"],
                "blocked_pair_same_physical_component": True,
            },
            "missing_scientific_definition": (
                "The frozen authority does not define how S3 reconstructs an opposite-"
                "boundary pair from anonymous local support discs when samples from one "
                "curved physical boundary component lie on both signs of the ego mission "
                "normal. It also does not select between treating that observation as "
                "UNKNOWN and introducing a component-reconstruction or identity rule."
            ),
            "case_evaluation": {
                "CASE_I": {
                    "selected": False,
                    "reason": (
                        "Width is unsigned, but the observed value is invariant to lateral-"
                        "axis and token-order reversal; this is not a signed orientation defect."
                    ),
                },
                "CASE_II": {
                    "selected": False,
                    "reason": "The frozen quantity is not defined as signed.",
                },
                "CASE_III": {
                    "selected": False,
                    "reason": (
                        "Independent analytic reconstruction gives a valid 1.361 m passage; "
                        "the source geometry satisfies frozen validity rules."
                    ),
                },
                "CASE_IV": {
                    "selected": True,
                    "reason": "Opposite-component pairing semantics are absent from frozen authority.",
                },
            },
            "classification": "CASE_IV",
            "relevant_sources": authority_sources,
            "superseded_rule_adopted": False,
            "diagnostic_rule_promoted_to_science": False,
            "scientific_writes": 0,
        },
        "phase9_s3_geometry_authority_sha256",
    )

    population = _write(
        results / "phase9_s3_population_audit_v1.json",
        {
            "schema_version": "rvt-phase9-s3-population-audit-closure/v1",
            "status": "AUTHORIZED_UNSEALED_UNIVERSE_ENUMERATED",
            "mode": "NON_OFFICIAL_READ_ONLY_DIAGNOSTIC",
            "selection_contract": population_reference["selection_contract"],
            "reference_artifact": {
                "artifact": "phase9_s3_population_audit_reference_v1.json",
                "canonical_sha256": population_reference[
                    "phase9_s3_population_audit_sha256"
                ],
            },
            "qualified_docker_artifact": {
                "artifact": "phase9_s3_population_audit_docker_v1.json",
                "canonical_sha256": population_docker[
                    "phase9_s3_population_audit_sha256"
                ],
                "image": OLD_IMAGE,
            },
            "cross_platform": {
                "reference_semantic_projection_sha256": population_reference[
                    "semantic_projection_sha256"
                ],
                "docker_semantic_projection_sha256": population_docker[
                    "semantic_projection_sha256"
                ],
                "exact": True,
            },
            "source_instance_distribution": population_reference[
                "source_instance_distribution"
            ],
            "robot_observation_distribution": population_reference[
                "robot_observation_distribution"
            ],
            "by_split_family_team_size_layout": population_reference[
                "by_split_family_team_size_layout"
            ],
            "negative_observations": population_reference["negative_observations"],
            "systematic_sign_audit": population_reference["systematic_sign_audit"],
            "finding": (
                "All 48 negative robot observations occur in curved F3/F4 layouts, "
                "pair supports from one compiled boundary component, retain positive "
                "physical passage width, and are bit-invariant to representational reversal."
            ),
            "official_staging_writes": 0,
            "sealed_scope": dict(population_reference["sealed_scope"]),
        },
        "phase9_s3_population_audit_closure_sha256",
    )

    impact = _write(
        results / "phase9_s3_official_data_impact_v1.json",
        {
            "schema_version": "rvt-phase9-s3-official-data-impact/v1",
            "status": "ALL_EXISTING_ROWS_EXACTLY_AUDITED",
            "staging_checkpoint_sha256": checkpoint[
                "phase9_s3_staging_checkpoint_sha256"
            ],
            "dependency_audit_sha256": dependency[
                "phase9_s3_staging_dependency_audit_sha256"
            ],
            "scientific_rows": checkpoint["prefix"]["scientific_rows"],
            "transaction_count": dependency["transaction_count"],
            "classification_counts": dependency["row_classification_counts"],
            "dependent_transaction_count": dependency[
                "transactions_with_s3_dependency"
            ],
            "dependent_source_replay_count": len(dependency["source_replays"]),
            "all_dependent_replays_exact": dependency["data_action_evidence"][
                "all_dependent_source_snapshots_or_terminations_reproduced"
            ],
            "negative_width_in_committed_dependency_cone": dependency[
                "data_action_evidence"
            ]["negative_width_in_committed_dependency_cone"],
            "current_preservation": {
                "rows_rewritten": 0,
                "rows_deleted": 0,
                "rows_regenerated": 0,
                "rows_compacted": 0,
                "rows_deduplicated": 0,
                "staging_remains_read_only": True,
            },
            "data_action": "OWNER_DECISION_REQUIRED",
            "data_action_explanation": (
                "No existing row is potentially or proven affected, so all 342 remain "
                "preserved official evidence. CASE IV prevents a final continuation/data "
                "policy from being asserted before the owner selects future S3 semantics."
            ),
            "transaction_level_rebuild_plan_required_now": False,
            "scientific_writes": 0,
            "sealed_scope": dict(dependency["sealed_scope"]),
        },
        "phase9_s3_official_data_impact_sha256",
    )

    owner = _write(
        results / "phase9_s3_owner_decision_required_v1.json",
        {
            "schema_version": "rvt-phase9-s3-owner-decision-required/v1",
            "status": "OWNER_SCIENTIFIC_DECISION_REQUIRED",
            "classification": "CASE_IV",
            "missing_definition": authority["missing_scientific_definition"],
            "constraints": {
                "existing_342_rows_remain_read_only": True,
                "physical_geometry_must_remain_unchanged": True,
                "no_outcome_dependent_rule": True,
                "no_sealed_domain_access": True,
                "no_implementation_before_owner_decision": True,
            },
            "alternatives": [
                {
                    "id": "A_CONTRADICTORY_PAIR_IS_UNKNOWN",
                    "definition": (
                        "When the local supports selected by the current statistic cannot "
                        "constitute a nonnegative opposite-boundary span, classify the local "
                        "observation as contradictory/incomplete and emit HOLD_UNKNOWN."
                    ),
                    "implementation_class": "NEW_SCIENTIFIC_RULE",
                    "scientific_interpretation_changes": True,
                    "current_official_rows_proven_affected": 0,
                    "future_effect": (
                        "Curved F3/F4 S3 robots may hold rather than originate a transition "
                        "until a complete noncontradictory pair becomes locally observable."
                    ),
                    "sensor_schema_change": False,
                },
                {
                    "id": "B_LOCAL_SUPPORT_COMPONENT_RECONSTRUCTION",
                    "definition": (
                        "Define a deterministic robot-local clustering rule over observed "
                        "support discs and compute span only between distinct reconstructed "
                        "boundary components."
                    ),
                    "implementation_class": "NEW_SCIENTIFIC_RULE",
                    "scientific_interpretation_changes": True,
                    "current_official_rows_proven_affected": 0,
                    "future_effect": (
                        "Curved F3/F4 S3 evidence may become usable; clustering, occlusion, "
                        "circle interaction, and tie semantics must be frozen explicitly."
                    ),
                    "sensor_schema_change": False,
                },
                {
                    "id": "C_LOCAL_BOUNDARY_COMPONENT_IDENTITY",
                    "definition": (
                        "Extend local obstacle support tokens with an opaque deterministic "
                        "component identity and pair supports only across distinct components."
                    ),
                    "implementation_class": "NEW_SCIENTIFIC_RULE_AND_INPUT_CONTRACT_CHANGE",
                    "scientific_interpretation_changes": True,
                    "current_official_rows_proven_affected": 0,
                    "future_effect": (
                        "Pairing is explicit, but the robot-local sensor interface, graph "
                        "provenance, and portability qualification must be amended."
                    ),
                    "sensor_schema_change": True,
                },
            ],
            "recommended_option": {
                "id": "A_CONTRADICTORY_PAIR_IS_UNKNOWN",
                "basis": (
                    "It reuses the already-frozen UNKNOWN behavior and changes the smallest "
                    "scientific surface, but it is still an owner decision and is not implemented."
                ),
                "implemented": False,
            },
            "existing_row_effect_basis": {
                "rows": 342,
                "negative_widths_in_committed_dependency_cone": 0,
                "potentially_affected": 0,
                "proven_affected": 0,
                "note": (
                    "Counts apply to narrowly scoped rules that activate only for the "
                    "newly identified ambiguous/contradictory pair class."
                ),
            },
            "scientific_writes": 0,
        },
        "phase9_s3_owner_decision_required_sha256",
    )

    coverage = _write(
        results / "phase9_s3_expanded_preflight_coverage_v1.json",
        {
            "schema_version": "rvt-phase9-s3-expanded-preflight-coverage/v1",
            "status": "DECLARED_AND_GENERATION_BLOCKING",
            "historical_miss_analysis": {
                "mechanical_tests": (
                    "Pure S3 totality tests used hand-selected nonnegative widths; geometry "
                    "tests did not execute the runtime estimator over curved support samples."
                ),
                "rb20_replay": (
                    "Four frozen cases covered F1/S1, F9/S0, F8/S1, and F5/S1; "
                    "none exercised S3 or curved F3/F4 support pairing."
                ),
                "phase9g0r_canary": (
                    "Covered F1/F2/F5/F8/F9/F10 and all N classes, but omitted F3/F4; "
                    "its transition-protocol cases were not curved S3 geometry."
                ),
                "phase9g0p_benchmark": (
                    "Used F1/F2/F5/F8/F9/F10; it did not include F3/F4 S3 runtime geometry."
                ),
                "preflight": (
                    "Validated authority, provenance, structure, and pure contracts, but did "
                    "not enumerate S3 runtime geometry over authorized curved layouts."
                ),
                "new_combination_revealed_by_official_order": "F3/train-f3-01/N12/S3",
            },
            "new_fail_fast_coverage": [
                {
                    "test": "test_blocked_source_reproduces_before_official_event",
                    "covers": "exact F3 N12 source validity path and deterministic early exception",
                },
                {
                    "test": "test_width_trace_is_binary64_exact_and_not_orientation_sign_defect",
                    "covers": "negative geometry, frame reversal, selected component identity",
                },
                {
                    "test": "test_population_covers_curved_families_and_multiple_team_sizes",
                    "covers": "F3/F4, N5/N6/N8/N12/N16, positive/negative/unknown classes",
                },
                {
                    "test": "test_positive_straight_control_keeps_unsigned_span",
                    "covers": "positive diagnostic geometry and token ordering invariance",
                },
                {
                    "test": "test_generation_readiness_is_blocked_until_owner_decision",
                    "covers": "prestart refusal before production work",
                },
            ],
            "population_evidence_sha256": population[
                "phase9_s3_population_audit_closure_sha256"
            ],
            "generation_gate": "BLOCKED_SCIENTIFIC_OWNER_DECISION",
            "official_staging_writes": 0,
            "sealed_scope": dict(population["sealed_scope"]),
        },
        "phase9_s3_expanded_preflight_coverage_sha256",
    )

    closure = _write(
        results / "phase9_s3_scientific_closure_v1.json",
        {
            "schema_version": "rvt-phase9-s3-scientific-closure/v1",
            "status": "STOPPED_FOR_OWNER_SCIENTIFIC_DECISION",
            "identity": {
                "a1r_commit": A1R_COMMIT,
                "branch": BRANCH,
                "old_image": OLD_IMAGE,
                "new_image": None,
                "source_code_changed": False,
            },
            "evidence": {
                "staging_checkpoint_sha256": checkpoint[
                    "phase9_s3_staging_checkpoint_sha256"
                ],
                "width_derivation_sha256": width[
                    "phase9_s3_width_derivation_closure_sha256"
                ],
                "geometry_authority_sha256": authority[
                    "phase9_s3_geometry_authority_sha256"
                ],
                "population_audit_sha256": population[
                    "phase9_s3_population_audit_closure_sha256"
                ],
                "staging_dependency_audit_sha256": dependency[
                    "phase9_s3_staging_dependency_audit_sha256"
                ],
                "official_data_impact_sha256": impact[
                    "phase9_s3_official_data_impact_sha256"
                ],
                "owner_decision_sha256": owner[
                    "phase9_s3_owner_decision_required_sha256"
                ],
                "expanded_preflight_coverage_sha256": coverage[
                    "phase9_s3_expanded_preflight_coverage_sha256"
                ],
            },
            "classification": "CASE_IV",
            "repair": {
                "required_before_continuation": True,
                "implemented": False,
                "executable_conformance_repair_available_from_frozen_authority": False,
                "would_be_new_science": True,
                "physical_geometry_changed": False,
                "target_v4_contract_changed": False,
                "candidate_topology_semantics_changed": False,
                "matched_randomness_changed": False,
                "row_identity_rules_changed": False,
                "model_input_semantics_changed": False,
            },
            "data_action": "OWNER_DECISION_REQUIRED",
            "existing_rows_preserved": 342,
            "existing_rows_proven_affected": 0,
            "timeout_and_performance": {
                "qualified_workers": 12,
                "numeric_threads": 1,
                "chunk": 1,
                "qualified_timeout_seconds": 243,
                "reopened": False,
                "reason": "No source or scientific workload change was implemented.",
            },
            "verdict": "A",
            "verdict_text": (
                "S3 remains scientifically under-specified and requires an explicit owner decision."
            ),
            "isolation": {
                "official_generation_resumed": False,
                "recoverability_validation_started": False,
                "residual_v2_started": False,
                "training_operations": 0,
                "study_a_n24_accesses": 0,
                "study_b_accesses": 0,
                "final_test_accesses": 0,
                "official_staging_writes": 0,
            },
        },
        "phase9_s3_scientific_closure_sha256",
    )

    _write(
        results / "phase9_s3_generation_readiness_v1.json",
        {
            "schema_version": "rvt-phase9-s3-generation-readiness/v1",
            "readiness": "BLOCKED_SCIENTIFIC_OWNER_DECISION",
            "may_resume_official_recoverability": False,
            "blocking_classification": "CASE_IV",
            "required_next_authority": "explicit owner scientific decision/addendum",
            "closure_sha256": closure["phase9_s3_scientific_closure_sha256"],
            "owner_decision_sha256": owner[
                "phase9_s3_owner_decision_required_sha256"
            ],
            "staging_checkpoint_sha256": checkpoint[
                "phase9_s3_staging_checkpoint_sha256"
            ],
            "staging_rows": 342,
            "staging_read_only": True,
            "new_image_required_now": False,
            "old_image": OLD_IMAGE,
            "new_image": None,
            "official_operations": {
                "generation_resumes": 0,
                "validation_starts": 0,
                "residual_starts": 0,
                "training_operations": 0,
            },
            "sealed_scope": dict(checkpoint["sealed_domains"]),
        },
        "phase9_s3_generation_readiness_sha256",
    )


if __name__ == "__main__":
    main()
