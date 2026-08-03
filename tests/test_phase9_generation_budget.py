"""Phase 9C must stop rather than invent missing frozen budgets."""

from pathlib import Path

import pytest

from rvt_swarm.phase9.budget import (
    ProtocolIncompletenessError,
    assert_generation_budget_complete,
    build_generation_budget,
    build_generation_job_manifest,
)


ROOT = Path(__file__).resolve().parents[1]


def test_declared_study_a_upper_bounds_are_extracted_without_enlargement():
    known = build_generation_budget(ROOT)["known_frozen_upper_bounds"]["study_a_zero_shot"]
    assert known["train"]["maximum_decision_events"] == 6000
    assert known["validation"]["maximum_decision_events"] == 1500
    assert known["train"]["maximum_dense_action_records"] == 250000
    assert known["validation"]["maximum_dense_action_records"] == 50000


def test_replica_and_local_record_upper_bounds_follow_frozen_rules():
    known = build_generation_budget(ROOT)["known_frozen_upper_bounds"]["study_a_zero_shot"]
    assert known["train"]["maximum_candidate_replica_rollouts"] == 16800
    assert known["validation"]["maximum_candidate_replica_rollouts"] == 4200
    assert known["train"]["maximum_local_recoverability_records"] == 112800
    assert known["validation"]["maximum_local_recoverability_records"] == 28200


def test_missing_study_and_episode_budgets_block_generation():
    budget = build_generation_budget(ROOT)
    missing = {item["field"] for item in budget["missing_required_declarations"]}
    assert "study_a_n24_evaluation_budget" in missing
    assert "study_b_generation_budget" in missing
    assert "study_a_episode_budget_by_split_family_team_size" in missing
    assert budget["expected_total_upper_bound"] is None
    assert budget["generation_authorized"] is False


def test_incomplete_budget_raises_before_job_planning():
    with pytest.raises(ProtocolIncompletenessError, match="budget is incomplete"):
        assert_generation_budget_complete(build_generation_budget(ROOT))
    with pytest.raises(ProtocolIncompletenessError, match="budget is incomplete"):
        build_generation_job_manifest(ROOT)


def test_no_retry_count_is_fabricated():
    budget = build_generation_budget(ROOT)
    assert budget["maximum_generation_retries"] is None
    assert budget["generation_job_timeout_policy"] is None
