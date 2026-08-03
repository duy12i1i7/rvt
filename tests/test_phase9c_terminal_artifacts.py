"""Terminal Phase 9 artifacts preserve the failed-canary denominator."""

import json
from pathlib import Path

import pytest

from rvt_swarm.decentralized.ego_graph_v2 import EGO_GRAPH_FEATURE_SCHEMA_SHA256
from rvt_swarm.phase9.common import EXPERIMENT_PROTOCOL_SHA256, ONLINE_SCOPE_SHA256
from rvt_swarm.phase9c.loader import (
    DatasetNotReadyError,
    DatasetRecordError,
    load_dataset_manifest,
    validate_complete_shard,
    validate_recoverability_record,
)
from rvt_swarm.phase9c.artifacts import (
    build_dataset_manifest,
    build_failure_attribution,
    build_label_audit,
    build_reproducibility_audit,
    build_residual_audit,
    build_training_readiness_audit,
)
from rvt_swarm.phase9c.manifest import (
    COMPOSITE_GENERATION_PROTOCOL_SHA256,
    GENERATION_BUDGET_SHA256,
)


ROOT = Path(__file__).resolve().parents[1]
DATASET_ROOT = ROOT / "results/rvt_fd24/datasets"


def test_terminal_manifest_reports_planned_separately_from_actual():
    manifest = json.loads(
        (DATASET_ROOT / "phase9_dataset_manifest.json").read_text(encoding="ascii")
    )
    assert manifest["status"] == "INVALID_NOT_GENERATED"
    assert manifest["verdict"] == "D"
    assert manifest["planned_capacity"]["source_episode_slots"] == 3120
    assert manifest["actual_execution"]["source_episode_unique_jobs_started"] == 1
    assert manifest["actual_execution"]["source_episode_jobs_completed"] == 0
    assert manifest["records"] == {
        "recoverability_emitted": 0,
        "dense_residual_emitted": 0,
    }
    assert manifest["shards"]["count"] == 0


def test_invalid_terminal_manifest_is_fail_closed():
    with pytest.raises(DatasetNotReadyError, match="INVALID_NOT_GENERATED"):
        load_dataset_manifest(DATASET_ROOT / "phase9_dataset_manifest.json")


def _valid_record():
    return {
        "study": "study_a_zero_shot",
        "split": "train",
        "candidate_topology": 5,
        "team_size": 8,
        "phase8_experiment_protocol_sha256": EXPERIMENT_PROTOCOL_SHA256,
        "phase9b_generation_budget_sha256": GENERATION_BUDGET_SHA256,
        "composite_generation_protocol_sha256": COMPOSITE_GENERATION_PROTOCOL_SHA256,
        "ego_graph_feature_sha256": EGO_GRAPH_FEATURE_SCHEMA_SHA256,
        "online_topology_scope_sha256": ONLINE_SCOPE_SHA256,
        "episode_group": "episode",
        "decision_event_group": "event",
        "layout_group": "layout",
        "candidate_pair_group": "pair",
        "sealed": False,
        "final_test": False,
    }


@pytest.mark.parametrize(
    "field,value,message",
    (
        ("candidate_topology", 0, "KEEP"),
        ("phase8_experiment_protocol_sha256", "bad", "Phase 8"),
        ("phase9b_generation_budget_sha256", "bad", "Phase 9B"),
        ("composite_generation_protocol_sha256", "bad", "composite"),
        ("ego_graph_feature_sha256", "bad", "feature"),
        ("online_topology_scope_sha256", "bad", "scope"),
        ("episode_group", None, "grouping"),
        ("team_size", 24, "N=24"),
        ("sealed", True, "sealed"),
        ("final_test", True, "final-test"),
    ),
)
def test_strict_record_validator_rejects_prohibited_inputs(field, value, message):
    record = _valid_record()
    record[field] = value
    with pytest.raises(DatasetRecordError, match=message):
        validate_recoverability_record(
            record,
            expected_study="study_a_zero_shot",
            expected_split="train",
        )


def test_namespace_manifests_keep_study_a_n24_sealed_and_study_b_empty():
    sealed = json.loads(
        (DATASET_ROOT / "study_a_n24_eval_sealed/namespace_manifest.json").read_text(
            encoding="ascii"
        )
    )
    study_b = json.loads(
        (DATASET_ROOT / "study_b_with_n24/namespace_manifest.json").read_text(
            encoding="ascii"
        )
    )
    assert sealed["status"] == "SEALED_GENERATION_INCOMPLETE"
    assert sealed["record_count"] == sealed["access_count"] == 0
    assert study_b["n24_train_records"] == study_b["n24_validation_records"] == 0


def test_terminal_machine_audits_match_their_deterministic_builders():
    job = json.loads((DATASET_ROOT / "phase9_job_manifest.json").read_text())
    canary = json.loads((DATASET_ROOT / "phase9_canary_audit.json").read_text())
    audits = {
        "label": build_label_audit(job, canary),
        "residual": build_residual_audit(job, canary),
        "reproducibility": build_reproducibility_audit(job, canary),
        "failure": build_failure_attribution(job, canary),
        "training": build_training_readiness_audit(job, canary),
    }
    expected = {
        "label": "phase9_label_audit.json",
        "residual": "phase9_residual_audit.json",
        "reproducibility": "phase9_reproducibility_audit.json",
        "failure": "phase9_generation_failure_attribution.json",
        "training": "phase9_training_readiness_audit.json",
    }
    for name, filename in expected.items():
        assert audits[name] == json.loads((DATASET_ROOT / filename).read_text())
    assert build_dataset_manifest(job, canary, audits) == json.loads(
        (DATASET_ROOT / "phase9_dataset_manifest.json").read_text()
    )


def test_shard_validator_rejects_partial_and_corrupt_content(tmp_path):
    path = tmp_path / "shard.jsonl"
    path.write_text("record\n", encoding="ascii")
    with pytest.raises(DatasetRecordError, match="partial"):
        validate_complete_shard({"completion_state": "PARTIAL"}, path)
    with pytest.raises(DatasetRecordError, match="corrupted"):
        validate_complete_shard(
            {"completion_state": "COMPLETE", "content_sha256": "bad"}, path
        )
