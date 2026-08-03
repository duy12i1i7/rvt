from dataclasses import replace

from rvt_swarm.phase8.common import ONLINE_TOPOLOGY_SCOPE_SHA256
from rvt_swarm.phase8.provenance import (
    DATA_PROVENANCE_SCHEMA_VERSION,
    RECOVERABILITY_DATASET_SCHEMA_VERSION,
    DatasetProvenance,
    validate_dataset_provenance,
)
from rvt_swarm.topology_registry import COMPACT, KEEP, LINE


def _provenance():
    return DatasetProvenance(
        DATA_PROVENANCE_SCHEMA_VERSION,
        RECOVERABILITY_DATASET_SCHEMA_VERSION,
        "a" * 40, "b" * 64, "rvt-topology-registry/v1",
        ONLINE_TOPOLOGY_SCOPE_SHA256, "rvt-ego-graph/v2", "c" * 64,
        "rvt-fd24-model/v1", "d" * 64, "e" * 64, "f" * 64,
        "1" * 64, "2" * 64, "3" * 64, "train",
        "rvt-seed-namespaces/v1", "python generate.py", "2030-01-01T00:00:00Z",
        "generator/v1", 100, 10, 5, (("part-0", "4" * 64),),
        "5" * 64, "6" * 64, (COMPACT, LINE),
    )


def _issues(provenance):
    return validate_dataset_provenance(
        provenance,
        expected_dataset_schema=RECOVERABILITY_DATASET_SCHEMA_VERSION,
        expected_feature_sha256="c" * 64,
        expected_split="train",
        expected_split_manifest_sha256="3" * 64,
        expected_experiment_protocol_sha256="6" * 64,
    )


def test_complete_primary_dataset_provenance_is_admitted():
    assert _issues(_provenance()) == ()


def test_loader_rejects_keep_wrong_feature_split_and_protocol():
    assert "keep_in_primary_candidate_dataset" in _issues(
        replace(_provenance(), candidate_topology_ids=(KEEP, COMPACT, LINE))
    )
    assert "wrong_feature_hash" in _issues(replace(_provenance(), feature_sha256="x" * 64))
    assert "split_mismatch" in _issues(replace(_provenance(), split="validation"))
    assert "experiment_protocol_mismatch" in _issues(
        replace(_provenance(), experiment_protocol_sha256="x" * 64)
    )


def test_loader_rejects_final_test_records_and_tampered_hashes():
    issues = _issues(replace(
        _provenance(), split="final_test", aggregate_dataset_sha256="bad"
    ))
    assert "final_test_record_in_training_data" in issues
    assert "tampered_or_missing_aggregate_hash" in issues
