"""Phase 9G-A1 authorization is exact, additive, and outcome-free."""

from __future__ import annotations

import json
from pathlib import Path

from rvt_swarm.phase8.common import sha256_document


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results/rvt_fd24"


def _canonical(name: str, field: str):
    document = json.loads((RESULTS / name).read_text(encoding="ascii"))
    body = dict(document)
    expected = body.pop(field)
    assert sha256_document(body) == expected
    return document


def test_prestart_is_passed_without_an_authorization_transition() -> None:
    document = _canonical(
        "phase9g_a1_prestart_v1.json", "phase9g_a1_prestart_sha256"
    )
    assert document["status"] == "PASS"
    assert document["authorization_transition_performed"] is False
    assert document["scientific_commands_executed"] == 0
    assert document["current_scoped_resolution_count"] == 4
    assert document["sealed_scope_resolution_attempts"] == 0
    assert set(document["pretransition_counters"].values()) == {0}


def test_owner_authorization_enables_only_four_study_a_scopes() -> None:
    event = _canonical(
        "phase9g_a1_owner_authorization_v1.json",
        "phase9g_a1_owner_authorization_sha256",
    )
    assert event["broad_authorization"] is False
    assert event["enabled_scope_count"] == 4
    assert event["scientific_outcomes_present"] is False
    assert event["required_branch_order"] == ["recoverability", "residual"]
    assert event["scope_status"] == {
        "RECOVERABILITY_GENERATION": "AUTHORIZED_STUDY_A_TRAIN_VALIDATION_ONLY",
        "RESIDUAL_V2_GENERATION": "AUTHORIZED_STUDY_A_TRAIN_VALIDATION_ONLY",
        "STUDY_A_TRAIN_VALIDATION": "AUTHORIZED",
        "STUDY_A_N24_ZERO_SHOT": "SEALED_NOT_AUTHORIZED",
        "STUDY_B": "NOT_AUTHORIZED",
        "FINAL_TEST": "SEALED_NOT_AUTHORIZED",
        "TRAINING": "NOT_AUTHORIZED",
    }
    observed = {
        (item["study"], item["split"], item["branch"])
        for item in event["authorized_scope_artifacts"]
    }
    assert observed == {
        ("study_a_zero_shot", split, branch)
        for split in ("train", "validation")
        for branch in ("recoverability", "residual")
    }


def test_every_enabled_scope_is_canonical_and_exactly_bound() -> None:
    event = _canonical(
        "phase9g_a1_owner_authorization_v1.json",
        "phase9g_a1_owner_authorization_sha256",
    )
    for item in event["authorized_scope_artifacts"]:
        scope = _canonical(item["artifact"], "phase9_authorization_scope_sha256")
        assert scope["phase9_authorization_scope_sha256"] == item["sha256"]
        assert scope["official_generation_execution_authorized"] is True
        assert scope["broad_authorization"] is False
        assert scope["scientific_outcomes_present"] is False
        assert scope["binding"]["study"] == "study_a_zero_shot"
        assert scope["binding"]["split"] in {"train", "validation"}
        assert scope["binding"]["branch"] in {"recoverability", "residual"}
        assert set(scope["sealed_exclusions"]) == {
            "study_a_n24_zero_shot",
            "study_b",
            "final_test",
            "training",
        }
