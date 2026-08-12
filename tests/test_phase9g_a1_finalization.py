"""Mechanical tests for fail-closed Phase 9G-A1 finalization."""

from __future__ import annotations

import hashlib
import json

from scripts.finalize_phase9g_a1_recoverability import (
    ROWS_PER_SHARD,
    _ShardWriter,
    _candidate_dispositions,
)


def test_shard_writer_rotates_only_at_the_frozen_row_boundary(tmp_path) -> None:
    writer = _ShardWriter(tmp_path, "train")
    locations = [writer.write({"scientific_row_id": f"row-{index}"})
                 for index in range(ROWS_PER_SHARD + 1)]
    writer.close()
    assert [item["row_count"] for item in writer.descriptors] == [
        ROWS_PER_SHARD, 1
    ]
    assert locations[0] == ("train-recoverability-00000.jsonl", 0)
    assert locations[-1] == ("train-recoverability-00001.jsonl", 0)
    for descriptor in writer.descriptors:
        path = tmp_path / descriptor["path"].removeprefix("shards/")
        assert hashlib.sha256(path.read_bytes()).hexdigest() == descriptor[
            "content_sha256"
        ]


def test_candidate_audit_counts_retries_without_relabeling() -> None:
    document = {
        "audit": {
            "candidate_audits": [{
                "candidate_topology_id": 5,
                "replicas": [{
                    "infrastructure_attempts": [
                        {"attempt_index": 0, "status": "INFRASTRUCTURE_EXCEPTION"},
                        {"attempt_index": 1, "status": "COMPLETED"},
                    ]
                }],
            }]
        }
    }
    candidates, replicas, retries, failures = _candidate_dispositions(document)
    assert set(candidates) == {5}
    assert replicas == 1
    assert retries == 1
    assert failures == 1


def test_shard_lines_are_canonical_json(tmp_path) -> None:
    writer = _ShardWriter(tmp_path, "validation")
    writer.write({"z": 2, "a": 1})
    writer.close()
    line = (tmp_path / "validation-recoverability-00000.jsonl").read_text(
        encoding="ascii"
    ).strip()
    assert line == '{"a":1,"z":2}'
    assert json.loads(line) == {"a": 1, "z": 2}
