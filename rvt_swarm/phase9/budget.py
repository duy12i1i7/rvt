"""Phase 9 budget extraction and mandatory incompleteness gate."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, NoReturn

from ..phase8.common import file_sha256
from .common import (
    EXPERIMENT_PROTOCOL_SHA256,
    PHASE8_SOURCE_COMMIT,
    PHASE9_BUDGET_SCHEMA_VERSION,
    PHASE9_GENERATOR_VERSION,
    PHASE9_JOB_MANIFEST_SCHEMA_VERSION,
)


class ProtocolIncompletenessError(RuntimeError):
    """The frozen protocol cannot identify one unique generation plan."""


_MISSING_FIELDS = (
    {
        "field": "study_a_episode_budget_by_split_family_team_size",
        "why_required": "job identity and the 12-events-per-episode cap require an episode allocation",
        "approved_phase8_state": "not declared",
    },
    {
        "field": "decision_event_episode_layout_seed_timestamp_mapping",
        "why_required": "120/30 cell caps do not define which episode, layout, seed, or timestamp produces each event",
        "approved_phase8_state": "not declared",
    },
    {
        "field": "study_a_n24_evaluation_budget",
        "why_required": "the sealed non-final N=24 evaluation namespace has no event or action-row budget",
        "approved_phase8_state": "not declared",
    },
    {
        "field": "study_b_generation_budget",
        "why_required": "Study B names N=24 inclusion but declares no event, episode, or dense-row counts",
        "approved_phase8_state": "not declared",
    },
    {
        "field": "dense_action_exact_cell_allocation_and_episode_budget",
        "why_required": "250000/50000 are caps; the exact row count and episode allocation are unspecified",
        "approved_phase8_state": "upper bounds only",
    },
    {
        "field": "maximum_generation_retries",
        "why_required": "Phase 9C requires this value and forbids resampling until success",
        "approved_phase8_state": "not declared",
    },
    {
        "field": "generation_job_timeout_policy",
        "why_required": "family rollout horizons exist, but no wall-clock/job timeout is defined",
        "approved_phase8_state": "not declared",
    },
    {
        "field": "initialization_rejection_denominator_and_replacement_policy",
        "why_required": "the exact retained budget after deterministic initialization rejection is not defined",
        "approved_phase8_state": "invalid rollout masking is declared; initialization treatment is not",
    },
)


def _known_study_a_bounds() -> Dict[str, object]:
    return {
        "team_sizes": [5, 6, 8, 12, 16],
        "scenario_family_count": 10,
        "candidate_topologies": [5, 2],
        "train": {
            "maximum_decision_events": 6000,
            "maximum_events_per_family_team_cell": 120,
            "maximum_candidate_replica_rollouts": 16800,
            "maximum_local_recoverability_records": 112800,
            "maximum_dense_action_records": 250000,
        },
        "validation": {
            "maximum_decision_events": 1500,
            "maximum_events_per_family_team_cell": 30,
            "maximum_candidate_replica_rollouts": 4200,
            "maximum_local_recoverability_records": 28200,
            "maximum_dense_action_records": 50000,
        },
        "rollout_replica_rule": {
            "F8": 3,
            "F9": 3,
            "all_other_families": 1,
            "aggregation": "all_success",
        },
        "decision_state_limits": {
            "maximum_events_per_episode": 12,
            "minimum_temporal_spacing_seconds": 1.5,
            "sampling_mix": {
                "event_balanced_fraction": 0.70,
                "trajectory_uniform_fraction": 0.30,
            },
            "trajectory_source_fraction_each": 0.20,
        },
        "dense_action_limits": {
            "maximum_retained_timesteps_per_episode": 64,
            "minimum_temporal_spacing_seconds": 0.45,
        },
    }


def build_generation_budget(root: Path) -> Dict[str, object]:
    sampling = root / "docs/RVT_DECISION_STATE_SAMPLING_PROTOCOL.md"
    dense = root / "docs/RVT_DENSE_ACTION_DATA_CONTRACT.md"
    rollout = root / "docs/RVT_COUNTERFACTUAL_ROLLOUT_PROTOCOL.md"
    return {
        "schema_version": PHASE9_BUDGET_SCHEMA_VERSION,
        "status": "BLOCKED_PROTOCOL_INCOMPLETENESS",
        "source_commit": PHASE8_SOURCE_COMMIT,
        "experiment_protocol_sha256": EXPERIMENT_PROTOCOL_SHA256,
        "generator_version": PHASE9_GENERATOR_VERSION,
        "authoritative_sources": [
            {"path": str(path.relative_to(root)), "sha256": file_sha256(path)}
            for path in (sampling, dense, rollout)
        ],
        "known_frozen_upper_bounds": {"study_a_zero_shot": _known_study_a_bounds()},
        "study_a_n24_eval_sealed": {"purpose": "zero_shot_size_evaluation_only", "budget": None},
        "study_b_with_n24": {"team_sizes": [5, 6, 8, 12, 16, 24], "budget": None},
        "maximum_generation_retries": None,
        "rollout_timeout_policy": "family_episode_horizon",
        "generation_job_timeout_policy": None,
        "invalid_record_policy": "mask_and_report_never_relabel",
        "expected_total_upper_bound": None,
        "missing_required_declarations": list(_MISSING_FIELDS),
        "post_observation_budget_change_permitted": False,
        "generation_authorized": False,
        "stop_rule": (
            "Phase 9C requires an immediate stop when the approved Phase 8 "
            "documents do not determine one unique generation budget."
        ),
    }


def assert_generation_budget_complete(budget: Dict[str, object]) -> None:
    missing = budget.get("missing_required_declarations")
    if budget.get("generation_authorized") is not True or missing:
        names = ", ".join(
            str(item.get("field")) for item in missing if isinstance(item, dict)
        ) if isinstance(missing, list) else "unknown"
        raise ProtocolIncompletenessError(
            f"Phase 9 generation budget is incomplete: {names}"
        )


def build_generation_job_manifest(root: Path) -> NoReturn:
    """Refuse job construction before any final-test or simulator access."""
    budget = build_generation_budget(root)
    assert_generation_budget_complete(budget)
    raise AssertionError(PHASE9_JOB_MANIFEST_SCHEMA_VERSION)
