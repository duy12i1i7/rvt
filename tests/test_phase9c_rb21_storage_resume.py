"""Atomic staging, resume, duplicate and partial-write behavior."""

from __future__ import annotations

import json

import pytest

from rvt_swarm.phase9c_rb21.rb21_storage import AtomicUnitStore, StorageContractError


def _payload(disposition="LABELED"):
    row = {"scientific_identity": "s" * 64, "disposition": disposition,
           "target_world": None if disposition == "NO_ELIGIBLE_ACTION" else [0.1, -0.2]}
    sidecar = {"scientific_identity": "s" * 64,
               "candidate_ids": [f"candidate-{index}" for index in range(9)]}
    return row, sidecar


@pytest.mark.parametrize("point", ["after_record", "after_sidecar", "before_promotion"])
def test_partial_transactions_are_never_complete(tmp_path, point) -> None:
    store = AtomicUnitStore(tmp_path / "staging")
    record, sidecar = _payload()
    with pytest.raises(StorageContractError, match="injected failure"):
        store.commit("unit-a", record, sidecar, attempt_id=f"attempt-{point}",
                     failure_point=point)
    assert store.completed_unit_ids() == set()
    assert store.incomplete_attempts()[f"attempt-{point}"]["state"] == (
        "INFRASTRUCTURE_FAILURE")


def test_resume_tracks_complete_atomic_identity_not_chunk_position(tmp_path) -> None:
    root = tmp_path / "staging"
    record, sidecar = _payload()
    first = AtomicUnitStore(root)
    assert first.commit("unit-a", record, sidecar, attempt_id="attempt-1") == (
        "ACKNOWLEDGED")
    resumed = AtomicUnitStore(root)
    assert resumed.completed_unit_ids() == {"unit-a"}
    assert resumed.validate_complete(["unit-a"])["valid"] is True
    assert resumed.validate_complete(["unit-a", "unit-b"])["missing"] == ["unit-b"]


def test_duplicate_retry_is_idempotent_but_changed_science_is_rejected(tmp_path) -> None:
    store = AtomicUnitStore(tmp_path / "staging")
    record, sidecar = _payload()
    store.commit("unit-a", record, sidecar, attempt_id="attempt-1")
    assert store.commit("unit-a", record, sidecar, attempt_id="attempt-2") == (
        "DUPLICATE_IDEMPOTENT")
    changed = {**record, "target_world": [0.2, -0.2]}
    with pytest.raises(StorageContractError, match="different science"):
        store.commit("unit-a", changed, sidecar, attempt_id="attempt-3")
    assert store.completed_unit_ids() == {"unit-a"}


def test_no_eligible_action_is_preserved_as_a_terminal_attempt(tmp_path) -> None:
    store = AtomicUnitStore(tmp_path / "staging")
    record, sidecar = _payload("NO_ELIGIBLE_ACTION")
    store.commit("unit-no-eligible", record, sidecar, attempt_id="attempt-no-eligible")
    stored = json.loads((tmp_path / "staging/units/unit-no-eligible/record.json")
                        .read_text())
    assert stored["disposition"] == "NO_ELIGIBLE_ACTION"
    assert stored["target_world"] is None
    assert len(sidecar["candidate_ids"]) == 9


def test_incomplete_staging_cannot_be_promoted(tmp_path) -> None:
    store = AtomicUnitStore(tmp_path / "staging")
    record, sidecar = _payload()
    store.commit("unit-a", record, sidecar, attempt_id="attempt-1")
    with pytest.raises(StorageContractError, match="incomplete"):
        store.promote(tmp_path / "final", ["unit-a", "unit-b"])
    assert not (tmp_path / "final").exists()
