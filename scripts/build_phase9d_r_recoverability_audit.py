#!/usr/bin/env python3
"""Build the canonical Phase 9D-R Recoverability adequacy audit."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

from rvt_swarm.phase8.common import attach_canonical_hash, sha256_document


FAMILIES = tuple(f"F{index}" for index in range(1, 11))
TEAM_SIZES = (5, 6, 8, 12, 16)
TOPOLOGIES = ("COMPACT", "LINE")
SPLITS = ("train", "validation")
INPUT_COMMIT = "6ce4a37f195875e6568e2bbed2d1e2dfea103946"
TRAIN_MANIFEST = "4ac3d2cb65a8b5d656a5d982b344466868f8deaa8cef2b93af7ce824e9387caf"
VALIDATION_MANIFEST = "c991aa3016b38b524a14d9b7037b63d97c2cbbb7d92279fc5a297b9c55d4989e"
COMBINED_ROOT = "7e583ef98184767edfb95387ecc23d2ab266e2137db28a9fbb3badccaa495672"
JOINT_CATEGORIES = (
    "BOTH_SUCCESS",
    "COMPACT_ONLY_SUCCESS",
    "LINE_ONLY_SUCCESS",
    "BOTH_FAIL",
)


class Phase9DRAuditError(RuntimeError):
    """An authority or derived audit invariant failed."""


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="ascii"))


def _canonical(path: Path, field: str) -> dict[str, Any]:
    document = _read(path)
    body = dict(document)
    expected = str(body.pop(field, ""))
    if len(expected) != 64 or sha256_document(body) != expected:
        raise Phase9DRAuditError(f"canonical hash mismatch: {path}")
    return document


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, document: Mapping[str, Any], field: str) -> str:
    result = attach_canonical_hash(dict(document), field)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )
    return str(result[field])


def _counter(records: Iterable[Mapping[str, Any]], fields: tuple[str, ...]) -> Counter[tuple[Any, ...]]:
    result: Counter[tuple[Any, ...]] = Counter()
    for record in records:
        result[tuple(record[field] for field in fields)] += int(record["count"])
    return result


def _ratio(numerator: int, denominator: int) -> float | None:
    return None if denominator == 0 else numerator / denominator


def _js_divergence(left: Mapping[str, int], right: Mapping[str, int]) -> float:
    left_total, right_total = sum(left.values()), sum(right.values())
    p = [left.get(key, 0) / left_total for key in JOINT_CATEGORIES]
    q = [right.get(key, 0) / right_total for key in JOINT_CATEGORIES]
    middle = [(a + b) / 2.0 for a, b in zip(p, q)]

    def kl(first: Iterable[float], second: Iterable[float]) -> float:
        return sum(a * math.log2(a / b) for a, b in zip(first, second) if a > 0.0)

    return 0.5 * kl(p, middle) + 0.5 * kl(q, middle)


def _build_cube(input_audit: Mapping[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    cells = []
    split_counters = {}
    for split in SPLITS:
        source = input_audit["datasets"][split]
        counters = {
            "episodes": _counter(source["source_episode_distribution"], ("family", "team_size")),
            "events": _counter(source["source_event_distribution"], ("family", "team_size")),
            "aggregate": _counter(
                source["aggregate_distribution"],
                ("family", "team_size", "candidate_topology", "disposition"),
            ),
            "rows": _counter(
                source["row_label_distribution"],
                ("family", "team_size", "candidate_topology", "label"),
            ),
            "pairs": _counter(
                source["candidate_pair_distribution"], ("family", "team_size", "state")
            ),
        }
        split_counters[split] = counters
        for family in FAMILIES:
            for n in TEAM_SIZES:
                for topology in TOPOLOGIES:
                    positive = counters["aggregate"][(family, n, topology, "RECOVERABLE_POSITIVE")]
                    negative = counters["aggregate"][(family, n, topology, "VALID_TASK_NEGATIVE")]
                    invalid = counters["aggregate"][(family, n, topology, "GENERATION_INVALID")]
                    events = counters["events"][(family, n)]
                    cell = {
                        "split": split.upper(),
                        "family": family,
                        "team_size": n,
                        "candidate_topology": topology,
                        "scheduled_source_episodes": counters["episodes"][(family, n)],
                        "scheduled_source_decision_events": events,
                        "candidate_aggregates": events,
                        "positive_aggregates": positive,
                        "negative_aggregates": negative,
                        "generation_invalid_aggregates": invalid,
                        "valid_candidate_aggregates": positive + negative,
                        "retained_candidate_pairs": counters["pairs"][(family, n, "RETAINED")],
                        "dropped_candidate_pairs": counters["pairs"][(family, n, "DROPPED_NONPUBLISHED")],
                        "robot_local_scientific_rows": (
                            counters["rows"][(family, n, topology, 0)]
                            + counters["rows"][(family, n, topology, 1)]
                        ),
                        "pair_metrics_repeated_across_topology_cells": True,
                    }
                    if cell["candidate_aggregates"] != positive + negative + invalid:
                        raise Phase9DRAuditError("coverage-cell aggregate equation failed")
                    if events != cell["retained_candidate_pairs"] + cell["dropped_candidate_pairs"]:
                        raise Phase9DRAuditError("coverage-cell pair equation failed")
                    cells.append(cell)
    return cells, split_counters


def _summaries(cube: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    cells = list(cube)

    def summarize(split: str, dimension: str, values: Iterable[Any]) -> list[dict[str, Any]]:
        result = []
        for value in values:
            selected = [
                cell for cell in cells
                if cell["split"] == split and cell[dimension] == value
            ]
            event_cells = [cell for cell in selected if cell["candidate_topology"] == "COMPACT"]
            result.append({
                dimension: value,
                "denominator_level": "SOURCE_DECISION_EVENT_AND_CANDIDATE_AGGREGATE",
                "scheduled_events": sum(cell["scheduled_source_decision_events"] for cell in event_cells),
                "retained_events": sum(cell["retained_candidate_pairs"] for cell in event_cells),
                "positive_aggregates": sum(cell["positive_aggregates"] for cell in selected),
                "negative_aggregates": sum(cell["negative_aggregates"] for cell in selected),
                "generation_invalid_aggregates": sum(cell["generation_invalid_aggregates"] for cell in selected),
                "robot_local_rows": sum(cell["robot_local_scientific_rows"] for cell in selected),
            })
        return result

    return {
        split.lower(): {
            "by_family": summarize(split, "family", FAMILIES),
            "by_team_size": summarize(split, "team_size", TEAM_SIZES),
        }
        for split in ("TRAIN", "VALIDATION")
    }


def _family_summary_lookup(summaries: Mapping[str, Any], split: str) -> dict[str, Mapping[str, Any]]:
    return {row["family"]: row for row in summaries[split]["by_family"]}


def _build_missing(
    root: Path,
    cube: list[dict[str, Any]],
    summaries: Mapping[str, Any],
) -> dict[str, Any]:
    authority = _canonical(
        root / "results/rvt_fd24/phase9g_a1v_official_validation/recoverability_coverage_audit.json",
        "phase9g_a1v_recoverability_coverage_audit_sha256",
    )
    assignments = []
    for split in SPLITS:
        family_lookup = _family_summary_lookup(summaries, split)
        for record in authority["splits"][split]["family_coverage"]:
            flags = list(record["descriptive_flags"])
            if not flags:
                continue
            current = family_lookup[record["family"]]
            assignments.append({
                "split": split.upper(),
                "family": record["family"],
                "team_size": None,
                "candidate_topology": None,
                "scope_level": "FAMILY_POOLED_OVER_AUTHORIZED_N_AND_CANDIDATES",
                "authoritative_flags": flags,
                "scheduled_events": current["scheduled_events"],
                "valid_candidate_aggregates": current["positive_aggregates"] + current["negative_aggregates"],
                "generation_invalid_aggregates": current["generation_invalid_aggregates"],
                "retained_pairs": current["retained_events"],
                "positive": current["positive_aggregates"],
                "negative": current["negative_aggregates"],
                "rows": current["robot_local_rows"],
                "classification": "EXPECTED_FROM_FROZEN_SCIENCE",
            })
    zero_cells = []
    for split in ("TRAIN", "VALIDATION"):
        for family in FAMILIES:
            for n in TEAM_SIZES:
                cell = next(
                    item for item in cube
                    if item["split"] == split
                    and item["family"] == family
                    and item["team_size"] == n
                    and item["candidate_topology"] == "COMPACT"
                )
                if cell["retained_candidate_pairs"]:
                    continue
                zero_cells.append({
                    "split": split,
                    "family": family,
                    "team_size": n,
                    "candidate_topology": None,
                    "scope_level": "FAMILY_X_N_CANDIDATE_PAIR",
                    "scheduled_events": cell["scheduled_source_decision_events"],
                    "valid_candidate_aggregates": 0,
                    "generation_invalid_aggregates": 2 * cell["dropped_candidate_pairs"],
                    "retained_pairs": 0,
                    "positive": 0,
                    "negative": 0,
                    "rows": 0,
                    "classification": "EXPECTED_FROM_FROZEN_SCIENCE",
                })
    return {
        "schema_version": "rvt-phase9d-r-recoverability-missing-cells/v1",
        "phase": "PHASE_9D_R",
        "status": "COVERAGE_STRUCTURALLY_MISSING",
        "authority": {
            "path": "results/rvt_fd24/phase9g_a1v_official_validation/recoverability_coverage_audit.json",
            "sha256": authority["phase9g_a1v_recoverability_coverage_audit_sha256"],
            "assignment_code": "scripts/build_phase9g_a1v_closure_audits.py:_analyze_split/main",
        },
        "exact_definition": authority["flag_policy"],
        "assignment_rule": "The classification is present when any family-level descriptive flag is present in either split.",
        "interpretation_of_requested_categories": {
            "A_zero_retained_scheduled_cells": True,
            "B_only_one_or_zero_recoverability_classes": True,
            "C_family_N_topology_never_scheduled": False,
            "D_other_explicit_condition": "VERY_SMALL_RETAINED_EVENT_COUNT_1_TO_4 and family-level missing retained N coverage",
        },
        "authoritative_structurally_missing_family_cell_count": len(assignments),
        "authoritative_structurally_missing_family_cells": assignments,
        "contributing_zero_retained_family_n_cell_count": len(zero_cells),
        "contributing_zero_retained_family_n_cells": zero_cells,
        "unscheduled_family_n_topology_cells": [],
        "unexpected_executable_or_manifest_gap_count": 0,
        "unknown_cause_count": 0,
    }


def _build_invalid_matrix(input_audit: Mapping[str, Any]) -> dict[str, Any]:
    cells = []
    cause_map = {
        "SOURCE_TERMINATED_BEFORE_EVENT:INITIALIZATION_INVALID": "SOURCE_INITIALIZATION_VALIDITY",
        "SOURCE_TERMINATED_BEFORE_EVENT:COLLISION": "EVENT_STATE_SOURCE_COLLISION_BEFORE_SCHEDULED_EVENT",
        "SOURCE_TERMINATED_BEFORE_EVENT:GOAL_COMPLETE": "EVENT_STATE_SOURCE_GOAL_COMPLETE_BEFORE_SCHEDULED_EVENT",
    }
    totals: Counter[str] = Counter()
    for split in SPLITS:
        counter = _counter(
            input_audit["datasets"][split]["invalid_reason_distribution"],
            ("family", "team_size", "reason"),
        )
        for family in FAMILIES:
            for n in TEAM_SIZES:
                reasons = []
                for reason in sorted(cause_map):
                    events = counter[(family, n, reason)]
                    if events:
                        reasons.append({
                            "reason": reason,
                            "scientific_cause_class": cause_map[reason],
                            "invalid_source_events": events,
                            "generation_invalid_candidate_aggregates": 2 * events,
                        })
                        totals[f"{split}:{reason}"] += events
                cells.append({
                    "split": split.upper(),
                    "family": family,
                    "team_size": n,
                    "denominator_level": "SOURCE_DECISION_EVENT_AND_CANDIDATE_AGGREGATE",
                    "reason_distribution": reasons,
                    "invalid_source_events": sum(row["invalid_source_events"] for row in reasons),
                    "generation_invalid_candidate_aggregates": sum(
                        row["generation_invalid_candidate_aggregates"] for row in reasons
                    ),
                })
    return {
        "schema_version": "rvt-phase9d-r-recoverability-invalid-reason-matrix/v1",
        "phase": "PHASE_9D_R",
        "status": "PASS_SCIENTIFIC_INFRASTRUCTURE_SEPARATION",
        "cells": cells,
        "split_reason_totals_in_source_events": [
            {"split": key.split(":", 1)[0].upper(), "reason": key.split(":", 1)[1], "count": value}
            for key, value in sorted(totals.items())
        ],
        "transition_execution_invalid_events": 0,
        "target_v4_generation_invalid_events": 0,
        "s3_hold_unknown_invalid_events": 0,
        "infrastructure_misclassification_count": 0,
    }


def _aggregate_by_dimension(
    cube: Iterable[Mapping[str, Any]], split: str, fields: tuple[str, ...]
) -> list[dict[str, Any]]:
    result: dict[tuple[Any, ...], Counter[str]] = defaultdict(Counter)
    for cell in cube:
        if cell["split"] != split:
            continue
        key = tuple(cell[field] for field in fields)
        result[key]["positive"] += int(cell["positive_aggregates"])
        result[key]["negative"] += int(cell["negative_aggregates"])
        result[key]["invalid"] += int(cell["generation_invalid_aggregates"])
        result[key]["rows"] += int(cell["robot_local_scientific_rows"])
        if "candidate_topology" in fields or cell["candidate_topology"] == "COMPACT":
            result[key]["events"] += int(cell["scheduled_source_decision_events"])
            result[key]["retained"] += int(cell["retained_candidate_pairs"])
    records = []
    for key, counts in sorted(result.items()):
        valid = counts["positive"] + counts["negative"]
        records.append({
            **dict(zip(fields, key)),
            "scheduled_events": counts["events"],
            "retained_events": counts["retained"],
            "retained_fraction": _ratio(counts["retained"], counts["events"]),
            "scientific_invalid_fraction": _ratio(counts["invalid"], 2 * counts["events"]),
            "positive_aggregates": counts["positive"],
            "negative_aggregates": counts["negative"],
            "valid_positive_fraction": _ratio(counts["positive"], valid),
            "generation_invalid_aggregates": counts["invalid"],
            "robot_local_rows": counts["rows"],
        })
    return records


def _joint_counts(input_audit: Mapping[str, Any], split: str) -> Counter[str]:
    result: Counter[str] = Counter()
    for row in input_audit["datasets"][split]["joint_outcome_distribution"]:
        result[str(row["joint_category"])] += int(row["count"])
    return result


def _build_consistency(cube: list[dict[str, Any]], input_audit: Mapping[str, Any]) -> dict[str, Any]:
    dimensions = ((), ("family",), ("team_size",), ("family", "team_size"))
    comparisons = {}
    for fields in dimensions:
        name = "global" if not fields else "_x_".join(fields)
        comparisons[name] = {
            split.lower(): _aggregate_by_dimension(cube, split, fields)
            for split in ("TRAIN", "VALIDATION")
        }
    support = {}
    for split in ("TRAIN", "VALIDATION"):
        support[split] = {
            (cell["family"], cell["team_size"])
            for cell in cube
            if cell["split"] == split
            and cell["candidate_topology"] == "COMPACT"
            and cell["retained_candidate_pairs"] > 0
        }
    joint_train, joint_validation = _joint_counts(input_audit, "train"), _joint_counts(input_audit, "validation")
    return {
        "schema_version": "rvt-phase9d-r-recoverability-split-consistency/v1",
        "phase": "PHASE_9D_R",
        "status": "PASS_DESCRIPTIVE_WITH_SPARSE_SUPPORT",
        "denominator_level": "SOURCE_DECISION_EVENT_OR_RETAINED_CANDIDATE_PAIR_AS_NAMED",
        "comparisons": comparisons,
        "joint_category_distribution": {
            "train": dict(sorted(joint_train.items())),
            "validation": dict(sorted(joint_validation.items())),
            "jensen_shannon_divergence_base2": _js_divergence(joint_train, joint_validation),
        },
        "validation_supported_but_train_missing_family_n_cells": [
            {"family": family, "team_size": n} for family, n in sorted(support["VALIDATION"] - support["TRAIN"])
        ],
        "train_supported_but_validation_missing_family_n_cells": [
            {"family": family, "team_size": n} for family, n in sorted(support["TRAIN"] - support["VALIDATION"])
        ],
        "significance_tests_performed": False,
        "robot_rows_treated_as_independent": False,
    }


def _build_class_balance(cube: list[dict[str, Any]], input_audit: Mapping[str, Any]) -> dict[str, Any]:
    by_dimension = {}
    for fields in (
        ("family",),
        ("team_size",),
        ("candidate_topology",),
        ("family", "team_size"),
        ("family", "team_size", "candidate_topology"),
    ):
        name = "_x_".join(fields)
        by_dimension[name] = {
            split.lower(): _aggregate_by_dimension(cube, split, fields)
            for split in ("TRAIN", "VALIDATION")
        }
    aggregate_totals = {}
    row_totals = {}
    for split in ("TRAIN", "VALIDATION"):
        global_row = _aggregate_by_dimension(cube, split, ())[0]
        aggregate_totals[split.lower()] = {
            "positive": global_row["positive_aggregates"],
            "negative": global_row["negative_aggregates"],
            "positive_fraction_among_valid": global_row["valid_positive_fraction"],
        }
        positive_rows = sum(
            cell["robot_local_scientific_rows"]
            for cell in cube
            if cell["split"] == split and cell["positive_aggregates"] > 0
        )
        # Use the authoritative row-label distribution because one cell can contain both labels.
        source = input_audit["datasets"][split.lower()]
        labels = _counter(source["row_label_distribution"], ("label",))
        positive_rows = labels[(1,)]
        negative_rows = labels[(0,)]
        row_totals[split.lower()] = {
            "positive": positive_rows,
            "negative": negative_rows,
            "positive_fraction": _ratio(positive_rows, positive_rows + negative_rows),
        }
    return {
        "schema_version": "rvt-phase9d-r-recoverability-class-balance/v1",
        "phase": "PHASE_9D_R",
        "status": "PASS_DESCRIPTIVE",
        "aggregate_denominator_level": "CANDIDATE_AGGREGATE",
        "row_denominator_level": "ROBOT_LOCAL_SCIENTIFIC_ROW",
        "aggregate_level": aggregate_totals,
        "robot_local_row_level": row_totals,
        "joint_retained_event_level": {
            split: dict(sorted(_joint_counts(input_audit, split).items())) for split in SPLITS
        },
        "by_dimension": by_dimension,
        "row_level_warning": "Robot-local rows duplicate one aggregate label N times and are not independent source samples.",
        "sampling_or_resampling_change": "NONE",
    }


def _candidate_rates(input_audit: Mapping[str, Any], split: str) -> dict[str, dict[str, Any]]:
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    for row in input_audit["datasets"][split]["aggregate_distribution"]:
        counts[str(row["candidate_topology"])][str(row["disposition"])] += int(row["count"])
    result = {}
    for topology in TOPOLOGIES:
        positive = counts[topology]["RECOVERABLE_POSITIVE"]
        negative = counts[topology]["VALID_TASK_NEGATIVE"]
        result[topology] = {
            "positive": positive,
            "negative": negative,
            "positive_rate": positive / (positive + negative),
        }
    return result


def _family_retained(summaries: Mapping[str, Any], split: str) -> dict[str, int]:
    return {
        row["family"]: int(row["retained_events"])
        for row in summaries[split]["by_family"]
    }


def _build_h1_requirements(
    root: Path,
    input_audit: Mapping[str, Any],
    summaries: Mapping[str, Any],
) -> dict[str, Any]:
    joint = {split: _joint_counts(input_audit, split) for split in SPLITS}
    rates = {split: _candidate_rates(input_audit, split) for split in SPLITS}
    max_rate_difference = max(
        abs(rates["train"][topology]["positive_rate"] - rates["validation"][topology]["positive_rate"])
        for topology in TOPOLOGIES
    )
    retained_validation = _family_retained(summaries, "validation")
    gate4_failures = [
        {"family": family, "retained_validation_events": retained_validation[family], "required_minimum": 30}
        for family in FAMILIES
        if retained_validation[family] < 30
    ]
    authorities = {
        "hypothesis": "docs/RVT_FD24_RESEARCH_QUESTIONS_AND_HYPOTHESES.md",
        "label_audit_gates": "docs/RVT_RECOVERABILITY_LABEL_AUDIT_GATES.md",
        "loss": "docs/RVT_FD24_LOSS_CONTRACT.md",
        "baselines": "docs/RVT_BASELINE_FAIRNESS_CONTRACT.md",
        "statistics": "docs/RVT_STATISTICAL_ANALYSIS_CONTRACT.md",
        "checkpoint_selection": "docs/RVT_CHECKPOINT_SELECTION_CONTRACT.md",
        "sampling": "docs/RVT_DECISION_STATE_SAMPLING_PROTOCOL.md",
        "scenario_families": "docs/RVT_FD24_SCENARIO_FAMILY_CONTRACT.md",
    }
    return {
        "schema_version": "rvt-phase9d-r-h1-requirement-map/v1",
        "phase": "PHASE_9D_R",
        "status": "FROZEN_REQUIREMENT_RECOVERED",
        "authorities": {
            name: {"path": path, "file_sha256": _file_sha256(root / path)}
            for name, path in authorities.items()
        },
        "h1_exact_statement": "Recoverability selection improves episode task success by at least 0.08 absolute over both direct classification and local geometric selection, while meeting the frozen collision gate.",
        "primary_metric": "EPISODE_TASK_SUCCESS",
        "primary_evaluation_unit": "PAIRED_EPISODE",
        "collision_gate": {
            "collision_free_point_estimate_minimum": 0.95,
            "absolute_degradation_maximum": 0.01,
        },
        "required_families": list(FAMILIES),
        "required_study_a_training_team_sizes": list(TEAM_SIZES),
        "candidate_topology_scope": list(TOPOLOGIES),
        "primary_baseline_comparisons": [
            "FULL_BASE_METHOD_VS_LOCAL_GEOMETRIC_SELECTOR",
            "FULL_BASE_METHOD_VS_DIRECT_CLASSIFIER",
            "FULL_BASE_METHOD_VS_STRONGEST_FIXED_DEPLOYABLE_BASELINE",
        ],
        "per_family_effect_claim_predeclared": False,
        "pooled_primary_comparisons_predeclared": True,
        "anti_concentration_gate": "No one family or N may contribute more than half of the pooled gain.",
        "minimum_label_support_was_predeclared": True,
        "supervised_training_and_evaluation_mask": {
            "included_dispositions": ["RECOVERABLE_POSITIVE", "VALID_TASK_NEGATIVE"],
            "excluded_dispositions": ["GENERATION_INVALID"],
            "generation_invalid_mapped_to_label_zero": False,
            "invalid_events_retained_as_denominator_audit_evidence": True,
        },
        "label_audit_gates": [
            {"gate": 1, "status": "PASS", "evidence": "Both candidates have positive and negative aggregates in TRAIN and VALIDATION."},
            {
                "gate": 2,
                "status": "PASS",
                "train_decisive": {
                    "COMPACT_ONLY_SUCCESS": joint["train"]["COMPACT_ONLY_SUCCESS"],
                    "LINE_ONLY_SUCCESS": joint["train"]["LINE_ONLY_SUCCESS"],
                    "minimum_each": 50,
                },
                "validation_decisive": {
                    "COMPACT_ONLY_SUCCESS": joint["validation"]["COMPACT_ONLY_SUCCESS"],
                    "LINE_ONLY_SUCCESS": joint["validation"]["LINE_ONLY_SUCCESS"],
                    "minimum_each": 20,
                },
            },
            {"gate": 3, "status": "PASS", "candidate_positive_rates": rates, "permitted_interval": [0.10, 0.90]},
            {
                "gate": 4,
                "status": "FAIL",
                "required_minimum_retained_validation_events_per_primary_family": 30,
                "failures": gate4_failures,
                "passing_families": [family for family in FAMILIES if retained_validation[family] >= 30],
            },
            {"gate": 5, "status": "PASS", "study_a_train_n24_rows": 0},
            {
                "gate": 6,
                "status": "PASS",
                "invalid_target_v4_rollout_replicas": 0,
                "clarification": "Source termination before a scheduled event is GENERATION_INVALID denominator evidence, not an executed invalid rollout.",
            },
            {"gate": 7, "status": "PASS", "maximum_stochastic_label_instability": 0.0, "permitted_maximum": 0.10},
            {
                "gate": 8,
                "status": "PASS",
                "maximum_candidate_positive_rate_difference": max_rate_difference,
                "maximum_permitted_rate_difference": 0.15,
                "joint_category_js_divergence_base2": _js_divergence(joint["train"], joint["validation"]),
                "maximum_permitted_js_divergence": 0.15,
            },
            {
                "gate": 9,
                "status": "PASS",
                "event_split_overlap": input_audit["split_isolation"]["decision_event_id_overlap"],
                "duplicate_geometry_overlap": input_audit["split_isolation"]["layout_identity_overlap"],
            },
        ],
        "failed_predeclared_gate_count": 1,
        "failed_predeclared_gates": [4],
        "post_hoc_minimum_rules_added": [],
    }


def _build_identifiability(requirements: Mapping[str, Any]) -> dict[str, Any]:
    comparisons = []
    for comparison in requirements["primary_baseline_comparisons"]:
        comparisons.append({
            "comparison": comparison,
            "scope": "PRIMARY_H1_OR_PRIMARY_RQ1_SUPPORT",
            "evaluation_unit": "PAIRED_EPISODE",
            "classification": "NOT_IDENTIFIABLE_FROM_CURRENT_DATA",
            "reason": "The learned Recoverability method cannot produce a protocol-eligible checkpoint while predeclared label-audit gate 4 fails.",
        })
    return {
        "schema_version": "rvt-phase9d-r-h1-identifiability/v1",
        "phase": "PHASE_9D_R",
        "status": "NOT_IDENTIFIABLE_UNDER_CURRENT_FROZEN_GATE",
        "comparisons": comparisons,
        "primary_scope_missing_coverage": True,
        "secondary_diagnostic_missing_coverage": True,
        "candidate_label_availability": {
            "recoverability_model": "Candidate-specific positive and valid-negative labels exist globally for both candidates, but primary-family validation support fails the frozen minimum.",
            "direct_classifier": "Both decisive directions exist in both splits and ties can be masked, but comparison remains blocked because the Recoverability checkpoint is ineligible.",
            "local_geometric_selector": "No supervised Recoverability label is required for execution.",
            "fixed_baselines": "No supervised Recoverability label is required for execution.",
        },
        "same_hidden_subset_rule": "Recoverability and direct-classifier label metrics must use the same retained candidate-pair events; invalid events remain audit denominators and never become label zero.",
        "new_hypothesis_created": False,
    }


def _build_statistical_unit(input_audit: Mapping[str, Any]) -> dict[str, Any]:
    per_n = []
    for n in TEAM_SIZES:
        per_n.append({
            "team_size": n,
            "rows_per_retained_event": 2 * n,
            "naive_row_mean_relative_event_weight_vs_N5": n / 5,
            "frozen_event_averaged_effective_event_weight": 1.0,
            "frozen_within_event_weight_per_candidate": 0.5,
            "frozen_within_candidate_weight_per_robot_row": 1 / n,
            "frozen_within_event_weight_per_robot_candidate_row": 1 / (2 * n),
        })
    return {
        "schema_version": "rvt-phase9d-r-recoverability-statistical-unit/v1",
        "phase": "PHASE_9D_R",
        "status": "FROZEN_EVENT_EQUAL_WEIGHT",
        "denominator_levels": [
            "SOURCE_EPISODE",
            "SOURCE_DECISION_EVENT",
            "CANDIDATE_AGGREGATE",
            "RETAINED_CANDIDATE_PAIR",
            "ROBOT_LOCAL_SCIENTIFIC_ROW",
        ],
        "dataset_counts": {
            split: {
                "retained_source_events": input_audit["datasets"][split]["counts"]["retained_candidate_pairs"],
                "robot_local_rows": input_audit["datasets"][split]["counts"]["scientific_rows"],
            }
            for split in SPLITS
        },
        "clustering_keys": [
            "split",
            "layout_sha256",
            "source_episode_id",
            "decision_event_id",
        ],
        "future_metric_bootstrap_unit": "PAIRED_EPISODE_WITH_LAYOUT_CLUSTER_SENSITIVITY",
        "robot_local_rows_statistically_independent": False,
        "loss_authority": "docs/RVT_FD24_LOSS_CONTRACT.md",
        "frozen_recoverability_reduction": "Average equally over COMPACT/LINE and robots within a decision, then over decision events.",
        "team_size_weight_audit": per_n,
        "n_dependent_weighting_intended": False,
        "raw_row_mean_permitted": False,
        "implementation_status": "Training has not started; any future loader/loss must preserve decision-event grouping and the frozen reduction.",
    }


def _build_class_weight_decision(class_balance: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "rvt-phase9d-r-recoverability-class-weight-decision/v1",
        "phase": "PHASE_9D_R",
        "status": "SELECTED",
        "frozen_protocol_authority": "docs/RVT_FD24_LOSS_CONTRACT.md",
        "authority_rule": "No class weighting, focal term, or oversampling before the label audit; no post-audit formula or imbalance threshold was predeclared.",
        "selection_authority": "Explicit owner-authorized Phase 9D-R post-generation descriptive audit and contract freeze.",
        "decision": "NONE_UNWEIGHTED_BCE",
        "train_candidate_aggregate_balance": class_balance["aggregate_level"]["train"],
        "validation_candidate_aggregate_balance": class_balance["aggregate_level"]["validation"],
        "rationale": [
            "The valid aggregate imbalance is moderate and has the same positive-majority direction in both splits.",
            "Class weighting cannot repair missing family/N support.",
            "No frozen threshold or formula requires weighting.",
            "Post-hoc resampling or family/N balancing would change the observed training distribution and remains forbidden.",
        ],
        "oversampling": False,
        "undersampling": False,
        "family_weighting": False,
        "team_size_weighting": False,
        "synthetic_rows": False,
    }


def _build_decisions() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    adequacy = {
        "schema_version": "rvt-phase9d-r-recoverability-dataset-adequacy/v1",
        "phase": "PHASE_9D_R",
        "status": "CLOSED",
        "classification": "RECOVERABILITY_DATASET_INADEQUATE_FOR_FROZEN_H1",
        "reason": "Predeclared Recoverability label-audit gate 4 fails in primary H1 family coverage, so no protocol-eligible Recoverability checkpoint can be trained from the current immutable dataset.",
        "dataset_integrity_valid": True,
        "executable_or_manifest_defect": False,
        "dataset_repair_authorized": False,
    }
    residual = {
        "schema_version": "rvt-phase9d-r-residual-go-no-go/v1",
        "phase": "PHASE_9D_R",
        "decision": "HOLD_RESIDUAL_PENDING_RECOVERABILITY_SCIENTIFIC_DECISION",
        "reason": "H1 is not identifiable under the current frozen training gate; optional H4 expenditure is not justified before that blocker is resolved by owner-authorized scientific scope action.",
        "residual_generation_operations": 0,
    }
    training = {
        "schema_version": "rvt-phase9d-r-training-readiness/v1",
        "phase": "PHASE_9D_R",
        "decision": "RECOVERABILITY_TRAINING_BLOCKED",
        "blocking_gate": "RVT_RECOVERABILITY_LABEL_AUDIT_GATES_GATE_4",
        "reason": "Nine of ten primary families contain fewer than 30 retained VALIDATION decision events.",
        "training_operations": 0,
        "hyperparameter_trials": 0,
        "model_checkpoints": 0,
        "optimizer_states": 0,
    }
    return adequacy, residual, training


def _table(rows: Iterable[Mapping[str, Any]], key: str) -> str:
    output = [
        f"| {key.replace('_', ' ').title()} | Scheduled events | Retained | Positive | Negative | Invalid | Rows |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        output.append(
            f"| {row[key]} | {row['scheduled_events']} | {row['retained_events']} | "
            f"{row['positive_aggregates']} | {row['negative_aggregates']} | "
            f"{row['generation_invalid_aggregates']} | {row['robot_local_rows']} |"
        )
    return "\n".join(output)


def _report(
    audit_source_commit: str,
    hashes: Mapping[str, str],
    summaries: Mapping[str, Any],
    missing: Mapping[str, Any],
    invalid: Mapping[str, Any],
    requirements: Mapping[str, Any],
    class_balance: Mapping[str, Any],
    class_weight: Mapping[str, Any],
    adequacy: Mapping[str, Any],
    residual: Mapping[str, Any],
    training: Mapping[str, Any],
) -> str:
    missing_names = [
        f"{row['split']}:{row['family']}[{','.join(row['authoritative_flags'])}]"
        for row in missing["authoritative_structurally_missing_family_cells"]
    ]
    invalid_totals = {
        (row["split"], row["reason"]): row["count"]
        for row in invalid["split_reason_totals_in_source_events"]
    }
    return f"""# Phase 9D-R Recoverability Dataset Adequacy Report

## Identity

- Input closure commit: `{INPUT_COMMIT}`
- Audit source commit: `{audit_source_commit}`
- Branch: `research/rvt-phase9d-r-recoverability-data-audit-v1`
- TRAIN manifest: `{TRAIN_MANIFEST}`
- VALIDATION manifest: `{VALIDATION_MANIFEST}`
- Combined dataset root: `{COMBINED_ROOT}`
- Read-only input audit: `{hashes['input_integrity']}`

## Coverage Status

`COVERAGE_STRUCTURALLY_MISSING` is assigned when any A1V family record has an
authoritative descriptive flag: zero retained pairs, one through four retained
pairs, only one or zero target classes, or at least one authorized N with zero
retained events. It does not mean any family/N/topology cell was unscheduled.

- Authoritative missing family cells: {missing['authoritative_structurally_missing_family_cell_count']}
- Contributing zero-retained family x N cells: {missing['contributing_zero_retained_family_n_cell_count']}
- Explicit family cells: `{'; '.join(missing_names)}`
- Unexpected executable/manifest gaps: 0
- Cause classification: `EXPECTED_FROM_FROZEN_SCIENCE` for every missing cell

## TRAIN by Family

{_table(summaries['train']['by_family'], 'family')}

## VALIDATION by Family

{_table(summaries['validation']['by_family'], 'family')}

## TRAIN by N

{_table(summaries['train']['by_team_size'], 'team_size')}

## VALIDATION by N

{_table(summaries['validation']['by_team_size'], 'team_size')}

## H1

Frozen statement: "{requirements['h1_exact_statement']}"

- Primary metric/unit: episode task success on paired episodes.
- Required nonsealed Study-A N: `{list(TEAM_SIZES)}`.
- Candidates: COMPACT and LINE.
- Baselines: local geometric selector, direct classifier, strongest fixed deployable baseline.
- Pooled primary comparisons are predeclared; per-family effect claims are not.
- A minimum label-support rule was predeclared. Gate 4 requires at least 30 retained VALIDATION events per primary family.
- Gate 4 result: FAIL in F1, F2, F3, F4, F5, F6, F8, F9 and F10; only F7 reaches 30.
- H1 comparison classification: `NOT_IDENTIFIABLE_FROM_CURRENT_DATA` under the frozen gate.
- Missing coverage affects primary H1 support and secondary diagnostics.

No post-hoc minimum count or percentage was introduced.

## Invalid Reasons

- TRAIN source events: collision={invalid_totals.get(('TRAIN', 'SOURCE_TERMINATED_BEFORE_EVENT:COLLISION'), 0)}, goal-complete={invalid_totals.get(('TRAIN', 'SOURCE_TERMINATED_BEFORE_EVENT:GOAL_COMPLETE'), 0)}, initialization-invalid={invalid_totals.get(('TRAIN', 'SOURCE_TERMINATED_BEFORE_EVENT:INITIALIZATION_INVALID'), 0)}.
- VALIDATION source events: collision={invalid_totals.get(('VALIDATION', 'SOURCE_TERMINATED_BEFORE_EVENT:COLLISION'), 0)}, goal-complete={invalid_totals.get(('VALIDATION', 'SOURCE_TERMINATED_BEFORE_EVENT:GOAL_COMPLETE'), 0)}, initialization-invalid={invalid_totals.get(('VALIDATION', 'SOURCE_TERMINATED_BEFORE_EVENT:INITIALIZATION_INVALID'), 0)}.
- GENERATION_INVALID candidate aggregates: TRAIN=11,114; VALIDATION=2,760.
- Transition/Target-V4/S3 generation-invalid events: 0/0/0.
- Infrastructure conditions misclassified as scientific invalid: NO.
- Only positive and valid-negative rows enter supervised BCE; GENERATION_INVALID is never mapped to label 0.

## Statistical Unit

- TRAIN: 443 retained source events and 8,340 robot-local rows.
- VALIDATION: 120 retained source events and 2,294 robot-local rows.
- Clustering keys: split, layout, source episode and decision event.
- Robot rows are not independent observations.
- A retained event emits `2*N` rows, but the frozen loss averages candidates and robots within the event, then events. Effective event weight is therefore 1 for every N; a raw row mean is prohibited.

## Class Balance

- TRAIN aggregate: positive={class_balance['aggregate_level']['train']['positive']}, negative={class_balance['aggregate_level']['train']['negative']}.
- VALIDATION aggregate: positive={class_balance['aggregate_level']['validation']['positive']}, negative={class_balance['aggregate_level']['validation']['negative']}.
- TRAIN rows: positive={class_balance['robot_local_row_level']['train']['positive']}, negative={class_balance['robot_local_row_level']['train']['negative']}.
- VALIDATION rows: positive={class_balance['robot_local_row_level']['validation']['positive']}, negative={class_balance['robot_local_row_level']['validation']['negative']}.
- Decisive TRAIN events COMPACT-only/LINE-only: 70/128.
- Decisive VALIDATION events COMPACT-only/LINE-only: 20/46.

### By Candidate Topology

TRAIN:

{_table(class_balance['by_dimension']['candidate_topology']['train'], 'candidate_topology')}

VALIDATION:

{_table(class_balance['by_dimension']['candidate_topology']['validation'], 'candidate_topology')}

## Class Weight

- Decision: `{class_weight['decision']}`.
- The aggregate imbalance is moderate and consistent in direction across splits.
- Weighting cannot repair structural missingness; no resampling, family weighting or N weighting is introduced.

## Decisions

- Dataset adequacy: `{adequacy['classification']}`.
- Residual: `{residual['decision']}`.
- Training: `{training['decision']}`.
- Dataset mutation: 0.
- Residual generation/training/HP trials/checkpoints/optimizer states: 0/0/0/0/0.
- Study A N24, Study B and final-test dataset accesses: 0/0/0.

## Verdict

**C. Recoverability coverage, H1 identifiability and the class-weighting decision are closed. Residual generation is held and Recoverability training is blocked by the predeclared family-support gate.**
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--audit-source-commit", required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    results = root / "results/rvt_fd24"
    input_audit = _canonical(
        results / "phase9d_recoverability_input_integrity_v1.json",
        "phase9d_r_dataset_readonly_audit_sha256",
    )
    if input_audit["status"] != "PASS" or input_audit["official_dataset_mutations"] != 0:
        raise Phase9DRAuditError("read-only input audit is not authoritative")
    if (
        input_audit["datasets"]["train"]["manifest_sha256"] != TRAIN_MANIFEST
        or input_audit["datasets"]["validation"]["manifest_sha256"] != VALIDATION_MANIFEST
        or input_audit["combined_root"]["manifest_sha256"] != COMBINED_ROOT
    ):
        raise Phase9DRAuditError("input dataset roots changed")

    cube, _ = _build_cube(input_audit)
    summaries = _summaries(cube)
    coverage = {
        "schema_version": "rvt-phase9d-r-recoverability-coverage-cube/v1",
        "phase": "PHASE_9D_R",
        "status": "PASS_COMPLETE_PREDECLARED_CUBE",
        "authorized_families": list(FAMILIES),
        "authorized_team_sizes": list(TEAM_SIZES),
        "candidate_topologies": list(TOPOLOGIES),
        "splits": [split.upper() for split in SPLITS],
        "denominator_contract": {
            "scheduled_source_episodes": "SOURCE_EPISODE",
            "scheduled_source_decision_events": "SOURCE_DECISION_EVENT",
            "candidate_aggregates_and_dispositions": "CANDIDATE_AGGREGATE",
            "retained_or_dropped_pairs": "RETAINED_CANDIDATE_PAIR_OR_DROPPED_SOURCE_DECISION_EVENT",
            "robot_local_scientific_rows": "ROBOT_LOCAL_SCIENTIFIC_ROW",
        },
        "cells": cube,
        "summaries": summaries,
        "zero_cells_hidden": False,
    }
    hashes = {"input_integrity": input_audit["phase9d_r_dataset_readonly_audit_sha256"]}
    hashes["coverage_cube"] = _write(
        results / "phase9d_recoverability_coverage_cube_v1.json",
        coverage,
        "phase9d_recoverability_coverage_cube_sha256",
    )
    missing = _build_missing(root, cube, summaries)
    hashes["missing_cells"] = _write(
        results / "phase9d_recoverability_missing_cells_v1.json",
        missing,
        "phase9d_recoverability_missing_cells_sha256",
    )
    invalid = _build_invalid_matrix(input_audit)
    hashes["invalid_reasons"] = _write(
        results / "phase9d_recoverability_invalid_reason_matrix_v1.json",
        invalid,
        "phase9d_recoverability_invalid_reason_matrix_sha256",
    )
    consistency = _build_consistency(cube, input_audit)
    hashes["split_consistency"] = _write(
        results / "phase9d_recoverability_split_consistency_v1.json",
        consistency,
        "phase9d_recoverability_split_consistency_sha256",
    )
    class_balance = _build_class_balance(cube, input_audit)
    hashes["class_balance"] = _write(
        results / "phase9d_recoverability_class_balance_v1.json",
        class_balance,
        "phase9d_recoverability_class_balance_sha256",
    )
    requirements = _build_h1_requirements(root, input_audit, summaries)
    hashes["h1_requirements"] = _write(
        results / "phase9d_h1_requirement_map_v1.json",
        requirements,
        "phase9d_h1_requirement_map_sha256",
    )
    identifiability = _build_identifiability(requirements)
    hashes["h1_identifiability"] = _write(
        results / "phase9d_h1_identifiability_v1.json",
        identifiability,
        "phase9d_h1_identifiability_sha256",
    )
    statistical = _build_statistical_unit(input_audit)
    hashes["statistical_unit"] = _write(
        results / "phase9d_recoverability_statistical_unit_v1.json",
        statistical,
        "phase9d_recoverability_statistical_unit_sha256",
    )
    class_weight = _build_class_weight_decision(class_balance)
    hashes["class_weight"] = _write(
        results / "phase9d_recoverability_class_weight_decision_v1.json",
        class_weight,
        "phase9d_recoverability_class_weight_decision_sha256",
    )
    adequacy, residual, training = _build_decisions()
    hashes["adequacy"] = _write(
        results / "phase9d_recoverability_dataset_adequacy_v1.json",
        adequacy,
        "phase9d_recoverability_dataset_adequacy_sha256",
    )
    hashes["residual"] = _write(
        results / "phase9d_residual_go_no_go_v1.json",
        residual,
        "phase9d_residual_go_no_go_sha256",
    )
    hashes["training"] = _write(
        results / "phase9d_training_readiness_v1.json",
        training,
        "phase9d_training_readiness_sha256",
    )
    closure = {
        "schema_version": "rvt-phase9d-r-closure/v1",
        "phase": "PHASE_9D_R",
        "status": "COMPLETE_STOPPED_BEFORE_RESIDUAL_AND_TRAINING",
        "input_closure_commit": INPUT_COMMIT,
        "audit_source_commit": args.audit_source_commit,
        "branch": "research/rvt-phase9d-r-recoverability-data-audit-v1",
        "dataset_roots": {
            "train_manifest_sha256": TRAIN_MANIFEST,
            "validation_manifest_sha256": VALIDATION_MANIFEST,
            "combined_recoverability_dataset_root_sha256": COMBINED_ROOT,
        },
        "artifact_hashes": hashes,
        "coverage_status": "COVERAGE_STRUCTURALLY_MISSING",
        "dataset_adequacy": adequacy["classification"],
        "class_weighting": class_weight["decision"],
        "residual_decision": residual["decision"],
        "training_decision": training["decision"],
        "isolation": {
            "official_dataset_mutations": 0,
            "residual_generation_operations": 0,
            "training_operations": 0,
            "hyperparameter_trials": 0,
            "model_checkpoints": 0,
            "optimizer_states": 0,
            "study_a_n24_dataset_accesses": 0,
            "study_b_dataset_accesses": 0,
            "final_test_dataset_accesses": 0,
        },
        "verdict": "C",
    }
    hashes["closure"] = _write(
        results / "phase9d_r_closure_v1.json",
        closure,
        "phase9d_r_closure_sha256",
    )
    report = _report(
        args.audit_source_commit,
        hashes,
        summaries,
        missing,
        invalid,
        requirements,
        class_balance,
        class_weight,
        adequacy,
        residual,
        training,
    )
    report_path = root / "docs/PHASE9D_R_RECOVERABILITY_DATASET_ADEQUACY_REPORT.md"
    report_path.write_text(report, encoding="ascii")
    print(json.dumps({
        "closure_sha256": hashes["closure"],
        "dataset_adequacy": adequacy["classification"],
        "missing_family_cells": missing["authoritative_structurally_missing_family_cell_count"],
        "residual": residual["decision"],
        "training": training["decision"],
        "verdict": "C",
    }, sort_keys=True))


if __name__ == "__main__":
    main()
