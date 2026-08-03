"""Authoritative Phase 9 job planning is exact and outcome-independent."""

from collections import Counter
from pathlib import Path

from rvt_swarm.phase8.common import verify_canonical_hash
from rvt_swarm.phase9c.manifest import (
    COMPOSITE_GENERATION_PROTOCOL_SHA256,
    GENERATION_BUDGET_SHA256,
    PROTOCOL_REFERENCE_ID,
    build_phase9_job_manifest,
)


ROOT = Path(__file__).resolve().parents[1]


def _manifest():
    return build_phase9_job_manifest(ROOT)


def test_authoritative_manifest_reproduces_every_frozen_capacity():
    manifest = _manifest()
    assert manifest["planned_capacity"] == {
        "source_episode_slots": 3120,
        "decision_event_slots": 15300,
        "candidate_replica_rollout_slots": 42840,
        "recoverability_record_capacity": 332900,
        "dense_residual_record_capacity": 536000,
        "residual_cell_jobs": 340,
    }
    assert verify_canonical_hash(manifest, "job_manifest_sha256")


def test_every_job_resolves_to_the_approved_protocol_hashes():
    manifest = _manifest()
    reference = manifest["protocol_references"][PROTOCOL_REFERENCE_ID]
    assert reference["phase9b_generation_budget_sha256"] == GENERATION_BUDGET_SHA256
    assert (
        reference["composite_generation_protocol_sha256"]
        == COMPOSITE_GENERATION_PROTOCOL_SHA256
    )
    jobs = (
        manifest["source_episode_jobs"]
        + manifest["decision_event_jobs"]
        + manifest["candidate_replica_jobs"]
        + manifest["residual_cell_jobs"]
    )
    assert all(item["protocol_reference_id"] == PROTOCOL_REFERENCE_ID for item in jobs)


def test_manifest_identity_split_and_n24_guards():
    manifest = _manifest()
    sources = manifest["source_episode_jobs"]
    assert not manifest["final_test_jobs_present"]
    assert len({item["job_id"] for item in sources}) == len(sources)
    assert all(item["split"] != "final_test" for item in sources)
    assert all(
        item["team_size"] != 24
        for item in sources
        if item["dataset_id"] in ("study_a_train", "study_a_validation")
    )
    assert all(
        item["sealed"] and item["team_size"] == 24
        for item in sources
        if item["dataset_id"] == "study_a_n24_evaluation"
    )
    for split in ("train", "validation"):
        assert any(
            item["dataset_id"] == f"study_b_{split}" and item["team_size"] == 24
            for item in sources
        )


def test_family_source_and_replica_allocations_are_exact():
    manifest = _manifest()
    events = manifest["decision_event_jobs"]
    family = Counter((item["dataset_id"], item["family_id"]) for item in events)
    expected = {
        "study_a_train": 600,
        "study_a_validation": 150,
        "study_a_n24_evaluation": 30,
        "study_b_train": 600,
        "study_b_validation": 150,
    }
    assert all(family[(dataset_id, f"F{index}")] == count
               for dataset_id, count in expected.items()
               for index in range(1, 11))
    for event in events:
        expected_replicas = 3 if event["family_id"] in ("F8", "F9") else 1
        assert event["replicas_per_candidate"] == expected_replicas


def test_candidate_job_seed_is_distinct_but_matched_disturbance_seed_is_shared():
    manifest = _manifest()
    jobs = manifest["candidate_replica_jobs"]
    first_event = jobs[0]["decision_event_job_id"]
    pair = [item for item in jobs
            if item["decision_event_job_id"] == first_event]
    assert len(pair) == 2
    assert len({item["seeds"]["candidate_replica_job_seed"] for item in pair}) == 2
    assert len({item["seeds"]["matched_disturbance_seed"] for item in pair}) == 1
