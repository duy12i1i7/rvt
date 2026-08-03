"""Study A N=24 is isolated until a checkpoint-selection boundary exists."""

import json
from pathlib import Path

import pytest

from rvt_swarm.phase9b.access import (
    N24EvaluationAuthorization,
    StudyAN24AccessError,
    require_study_a_n24_access,
)
from rvt_swarm.phase9b.identity import build_dataset_cells


ROOT = Path(__file__).resolve().parents[1]


def test_study_team_size_separation_is_exact():
    assert {item.team_size for item in build_dataset_cells(ROOT, "study_a_train")} == {5, 6, 8, 12, 16}
    assert {item.team_size for item in build_dataset_cells(ROOT, "study_a_validation")} == {5, 6, 8, 12, 16}
    assert {item.team_size for item in build_dataset_cells(ROOT, "study_a_n24_evaluation")} == {24}
    assert 24 in {item.team_size for item in build_dataset_cells(ROOT, "study_b_train")}
    assert 24 in {item.team_size for item in build_dataset_cells(ROOT, "study_b_validation")}


def test_n24_access_before_checkpoint_freeze_fails_and_is_logged(tmp_path):
    log = tmp_path / "access.jsonl"
    authorization = N24EvaluationAuthorization("", "", False)
    with pytest.raises(StudyAN24AccessError):
        require_study_a_n24_access(
            purpose="training", authorization=authorization, access_log=log
        )
    event = json.loads(log.read_text(encoding="ascii"))
    assert event["admitted"] is False


def test_n24_access_requires_all_three_approved_conditions(tmp_path):
    authorization = N24EvaluationAuthorization("a" * 64, "b" * 64, True)
    log = tmp_path / "access.jsonl"
    require_study_a_n24_access(
        purpose="zero_shot_size_evaluation_only",
        authorization=authorization,
        access_log=log,
    )
    event = json.loads(log.read_text(encoding="ascii"))
    assert event["admitted"] is True
