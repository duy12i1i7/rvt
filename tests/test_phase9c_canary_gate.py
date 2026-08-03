"""The canonical canary aborts before invalid scientific generation."""

import json
from pathlib import Path

from rvt_swarm.phase8.common import verify_canonical_hash
from rvt_swarm.phase9c.canary import FATAL_BINDING_CODE, select_canonical_canary
from rvt_swarm.phase9c.manifest import build_phase9_job_manifest


ROOT = Path(__file__).resolve().parents[1]


def _stored_audit():
    return json.loads(
        (ROOT / "results/rvt_fd24/datasets/phase9_canary_audit.json").read_text(
            encoding="ascii"
        )
    )


def test_canary_selection_covers_the_predeclared_nonsealed_prefix():
    manifest = build_phase9_job_manifest(ROOT)
    selection = select_canonical_canary(manifest)
    coverage = selection["coverage"]
    assert coverage["datasets"] == [
        "study_a_train", "study_a_validation",
        "study_b_train", "study_b_validation",
    ]
    assert len(coverage["families"]) >= 2
    assert len(coverage["team_sizes"]) >= 2
    assert coverage["candidates"] == [2, 5]
    assert sorted(coverage["replicas_per_candidate"].values()) == [3, 3]
    assert coverage["study_a_n24_opened"] is False


def test_canary_confirms_the_missing_scenario_runtime_binding():
    audit = _stored_audit()
    finding = audit["fatal_findings"][0]
    assert audit["canary_status"] == "FAIL_FATAL_EXECUTION_BINDING"
    assert audit["abort_generation"] is True
    assert finding["code"] == FATAL_BINDING_CODE
    assert finding["confirmed"] is True
    assert audit["attempts"][0]["exception_type"] == "AttributeError"
    assert "start_center" in audit["attempts"][0]["exception_message"]
    assert verify_canonical_hash(audit, "canary_audit_sha256")


def test_failed_canary_retry_is_identical_and_emits_no_scientific_rows():
    audit = _stored_audit()
    assert audit["attempts"][0] == audit["attempts"][1]
    assert audit["infrastructure_retry"]["byte_identical_deterministic_result"]
    assert audit["scientific_source_episodes_completed"] == 0
    assert audit["scientific_candidate_replicas_completed"] == 0
    assert audit["recoverability_records_emitted"] == 0
    assert audit["residual_records_emitted"] == 0


def test_canary_does_not_claim_unexecuted_checks_passed():
    audit = _stored_audit()
    assert not audit["normal_completion_observed"]
    assert not audit["semantic_failure_observed"]
    assert not audit["resume_behavior_verified"]
    assert not audit["counterfactual_matching_verified"]
    assert not audit["residual_expert_locality_verified"]
    assert not audit["deterministic_sharding_verified"]
    assert audit["study_a_n24_access_count"] == 0
    assert audit["final_test_runtime_access_count"] == 0
