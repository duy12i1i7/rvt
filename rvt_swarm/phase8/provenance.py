"""Future dataset provenance schemas and rejection rules."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict, Tuple

from ..topology_registry import COMPACT, KEEP, LINE
from .common import ONLINE_TOPOLOGY_SCOPE_SHA256, sha256_document


RECOVERABILITY_DATASET_SCHEMA_VERSION = "rvt-recoverability-dataset/v1"
RESIDUAL_ACTION_DATASET_SCHEMA_VERSION = "rvt-residual-action-dataset/v1"
DATA_PROVENANCE_SCHEMA_VERSION = "rvt-data-provenance/v1"
PRIMARY_DATASET_CANDIDATES: Tuple[int, ...] = (COMPACT, LINE)


@dataclass(frozen=True)
class DatasetProvenance:
    provenance_schema_version: str
    dataset_schema_version: str
    source_commit: str
    mechanical_scope_sha256: str
    topology_registry_schema_version: str
    online_scope_sha256: str
    ego_graph_schema_version: str
    feature_sha256: str
    model_schema_version: str
    runtime_config_sha256: str
    controller_config_sha256: str
    safety_config_sha256: str
    protocol_config_sha256: str
    scenario_manifest_sha256: str
    split_manifest_sha256: str
    split: str
    seed_namespace_schema_version: str
    generation_command: str
    generation_timestamp_utc: str
    generator_version: str
    row_count: int
    event_count: int
    episode_count: int
    file_sha256: Tuple[Tuple[str, str], ...]
    aggregate_dataset_sha256: str
    experiment_protocol_sha256: str
    candidate_topology_ids: Tuple[int, ...]


def validate_dataset_provenance(
    provenance: DatasetProvenance,
    *,
    expected_dataset_schema: str,
    expected_feature_sha256: str,
    expected_split: str,
    expected_split_manifest_sha256: str,
    expected_experiment_protocol_sha256: str,
) -> Tuple[str, ...]:
    issues = []
    if provenance.provenance_schema_version != DATA_PROVENANCE_SCHEMA_VERSION:
        issues.append("wrong_provenance_schema")
    if provenance.dataset_schema_version != expected_dataset_schema:
        issues.append("wrong_dataset_schema")
    if provenance.feature_sha256 != expected_feature_sha256:
        issues.append("wrong_feature_hash")
    if provenance.online_scope_sha256 != ONLINE_TOPOLOGY_SCOPE_SHA256:
        issues.append("wrong_online_topology_scope")
    if provenance.split != expected_split:
        issues.append("split_mismatch")
    if provenance.split_manifest_sha256 != expected_split_manifest_sha256:
        issues.append("split_manifest_mismatch")
    if provenance.experiment_protocol_sha256 != expected_experiment_protocol_sha256:
        issues.append("experiment_protocol_mismatch")
    if expected_split in ("train", "validation") and provenance.split == "final_test":
        issues.append("final_test_record_in_training_data")
    if expected_dataset_schema == RECOVERABILITY_DATASET_SCHEMA_VERSION:
        if tuple(provenance.candidate_topology_ids) != PRIMARY_DATASET_CANDIDATES:
            issues.append("primary_candidate_scope_mismatch")
        if KEEP in provenance.candidate_topology_ids:
            issues.append("keep_in_primary_candidate_dataset")
    for name, digest in provenance.file_sha256:
        if not name or len(digest) != 64:
            issues.append("invalid_per_file_hash")
    if len(provenance.aggregate_dataset_sha256) != 64:
        issues.append("tampered_or_missing_aggregate_hash")
    required_strings = (
        provenance.source_commit,
        provenance.mechanical_scope_sha256,
        provenance.topology_registry_schema_version,
        provenance.ego_graph_schema_version,
        provenance.model_schema_version,
        provenance.runtime_config_sha256,
        provenance.controller_config_sha256,
        provenance.safety_config_sha256,
        provenance.protocol_config_sha256,
        provenance.scenario_manifest_sha256,
        provenance.seed_namespace_schema_version,
        provenance.generation_command,
        provenance.generation_timestamp_utc,
        provenance.generator_version,
    )
    if any(not item for item in required_strings):
        issues.append("missing_provenance")
    if min(provenance.row_count, provenance.event_count, provenance.episode_count) < 0:
        issues.append("negative_count")
    return tuple(sorted(set(issues)))


def provenance_sha256(provenance: DatasetProvenance) -> str:
    return sha256_document(asdict(provenance))


def provenance_schema_document() -> Dict[str, object]:
    document: Dict[str, object] = {
        "schema_version": DATA_PROVENANCE_SCHEMA_VERSION,
        "recoverability_dataset_schema": RECOVERABILITY_DATASET_SCHEMA_VERSION,
        "residual_action_dataset_schema": RESIDUAL_ACTION_DATASET_SCHEMA_VERSION,
        "required_fields": list(DatasetProvenance.__dataclass_fields__),
        "primary_candidate_topology_ids": list(PRIMARY_DATASET_CANDIDATES),
        "loader_rejections": [
            "wrong_feature_hash",
            "wrong_online_topology_scope",
            "keep_in_primary_candidate_dataset",
            "split_mismatch",
            "missing_provenance",
            "tampered_or_missing_aggregate_hash",
            "final_test_record_in_training_data",
        ],
    }
    document["schema_sha256"] = sha256_document(document)
    return document
