"""Fail-closed Phase 9 shard and recoverability-record validation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Mapping

from ..decentralized.ego_graph_v2 import EGO_GRAPH_FEATURE_SCHEMA_SHA256
from ..phase9.common import EXPERIMENT_PROTOCOL_SHA256, ONLINE_SCOPE_SHA256
from ..topology_registry import COMPACT, LINE
from .manifest import (
    COMPOSITE_GENERATION_PROTOCOL_SHA256,
    GENERATION_BUDGET_SHA256,
)


class DatasetNotReadyError(RuntimeError):
    """Raised when an invalid or incomplete Phase 9 dataset is opened."""


class DatasetRecordError(ValueError):
    """Raised when a record crosses the frozen training boundary."""


_GROUPING_FIELDS = (
    "episode_group",
    "decision_event_group",
    "layout_group",
    "candidate_pair_group",
)


def validate_recoverability_record(
    record: Mapping[str, object],
    *,
    expected_study: str,
    expected_split: str,
) -> None:
    if record.get("study") != expected_study or record.get("split") != expected_split:
        raise DatasetRecordError("record study or split differs from loader scope")
    if record.get("split") == "final_test" or record.get("final_test"):
        raise DatasetRecordError("final-test records are prohibited")
    if record.get("candidate_topology") not in (COMPACT, LINE):
        raise DatasetRecordError("candidate must be COMPACT or LINE; KEEP is prohibited")
    if record.get("phase8_experiment_protocol_sha256") != EXPERIMENT_PROTOCOL_SHA256:
        raise DatasetRecordError("wrong Phase 8 protocol hash")
    if record.get("phase9b_generation_budget_sha256") != GENERATION_BUDGET_SHA256:
        raise DatasetRecordError("wrong Phase 9B budget hash")
    if (
        record.get("composite_generation_protocol_sha256")
        != COMPOSITE_GENERATION_PROTOCOL_SHA256
    ):
        raise DatasetRecordError("wrong composite protocol hash")
    if record.get("ego_graph_feature_sha256") != EGO_GRAPH_FEATURE_SCHEMA_SHA256:
        raise DatasetRecordError("wrong ego-graph feature hash")
    if record.get("online_topology_scope_sha256") != ONLINE_SCOPE_SHA256:
        raise DatasetRecordError("wrong online topology scope hash")
    if any(not record.get(field) for field in _GROUPING_FIELDS):
        raise DatasetRecordError("missing correlated-sample grouping metadata")
    team_size = int(record.get("team_size", -1))
    if expected_study == "study_a_zero_shot" and team_size == 24:
        raise DatasetRecordError("Study A train/validation cannot contain N=24")
    if record.get("sealed"):
        raise DatasetRecordError("sealed evaluation records are not training-visible")


def validate_complete_shard(descriptor: Mapping[str, object], path: Path) -> None:
    if descriptor.get("completion_state") != "COMPLETE":
        raise DatasetRecordError("partial shard is not readable")
    if not path.is_file():
        raise DatasetRecordError("shard file is missing")
    observed = hashlib.sha256(path.read_bytes()).hexdigest()
    if observed != descriptor.get("content_sha256"):
        raise DatasetRecordError("corrupted shard content hash")


def load_dataset_manifest(path: Path) -> Mapping[str, object]:
    document = json.loads(path.read_text(encoding="ascii"))
    if document.get("status") != "VALID_FROZEN":
        raise DatasetNotReadyError(
            f"Phase 9 dataset is not training-ready: {document.get('status')}"
        )
    return document
