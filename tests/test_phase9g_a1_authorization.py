"""Phase 9G-A1 authorization is exact, additive, and outcome-free."""

from __future__ import annotations

import json
import shlex
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


def test_recoverability_run_identity_is_operational_and_separate() -> None:
    run = _canonical(
        "phase9g_a1_recoverability_run_identity_v1.json",
        "phase9g_a1_recoverability_run_identity_sha256",
    )
    assert run["identity_class"] == "OPERATIONAL_NOT_SCIENTIFIC"
    assert run["scientific_row_identity_includes_run_id"] is False
    assert run["label_branch"] == "recoverability"
    assert run["splits"] == ["train", "validation"]
    assert set(run["initial_counters"].values()) == {0}
    assert run["operational_profile"]["workers"] == 12
    assert run["operational_profile"]["numeric_threads"] == 1
    assert run["operational_profile"]["chunk_size_atomic_units"] == 1
    assert run["operational_profile"]["infrastructure_timeout_seconds"] == 60.0


def test_command_activation_changes_only_owner_placeholders() -> None:
    activation = _canonical(
        "phase9g_a1_recoverability_command_activation_v1.json",
        "phase9g_a1_recoverability_command_activation_sha256",
    )
    assert activation["command_count"] == 2
    assert activation["sealed_scope_commands_activated"] == 0
    assert activation["allowed_activation_options"] == [
        "--authorization-scope-sha256",
        "--authorization-scope",
        "--run-id",
    ]
    for command in activation["commands"]:
        original = shlex.split(command["base_official_command"])
        activated = command["official_command_argv"]
        changed_value_indices = {
            original.index(item["option"]) + 1
            for item in command["activation_changes"]
        }
        assert len(original) == len(activated)
        assert {
            item["option"] for item in command["activation_changes"]
        } == set(activation["allowed_activation_options"])
        assert all(
            old == new or index in changed_value_indices
            for index, (old, new) in enumerate(zip(original, activated))
        )
        assert command["resolve_command_argv"] == activated + ["--resolve-only"]


def test_operational_stop_is_canonical_and_keeps_all_closed_domains_zero() -> None:
    stop = _canonical(
        "phase9g_a1_operational_stop_v1.json",
        "phase9g_a1_operational_stop_sha256",
    )
    assert stop["status"] == "STOPPED_UNRESOLVED_OPERATIONAL_TIMEOUT"
    assert stop["verdict"] == "D"
    assert stop["attempt_count"] == 2
    assert stop["run_level_resume_count"] == 1
    assert stop["infrastructure_timeouts"] == 2
    assert stop["unresolved_infrastructure_failures"] == 1
    assert stop["datasets"]["recoverability_finalized"] is False
    assert stop["datasets"]["residual_finalized"] is False
    assert set(stop["sealed_domains"].values()) == {0}
    assert stop["training"] == {
        "training_operations": 0,
        "checkpoints": 0,
        "optimizer_states": 0,
        "hp_trials": 0,
        "class_weighting": "NOT_SELECTED",
    }
    observed = stop["partial_staging_audit"]["observed"]
    assert observed["decision_events_completed"] == 127
    assert observed["scientific_rows"] == 318
    assert observed["partial_candidate_pair_publications"] == 0
    assert observed["duplicate_scientific_identities"] == 0
    assert observed["hash_failures"] == 0
    assert observed["schema_failures"] == 0
