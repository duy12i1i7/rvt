"""Operational metadata, threads and timeouts cannot alter RB-21 science."""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

from rvt_swarm.phase9c_rb21.rb21_manifest import TARGET_V4_HASH
from rvt_swarm.phase9c_rb21.rb21_units import (
    ThreadSettings, infrastructure_timeout_result, scientific_semantic_digest,
    scientific_semantic_projection,
)

ROOT = pathlib.Path("results/rvt_fd24")
RB18 = json.loads((ROOT / "rb18_structural_generation_canary_v1.json").read_text())
PERFORMANCE = json.loads((ROOT / "rb21_performance_benchmark_v1.json").read_text())


def _records():
    records = []
    for record in RB18["residual"]:
        records.append({"atomic_unit_id": record["scientific_row_id"],
                        "payload": record})
    return records


def test_scientific_digest_is_worker_and_chunk_independent() -> None:
    low = [{**item, "worker_id": 0, "chunk_id": "a", "attempt_index": 0,
            "wall_seconds": 10.0} for item in _records()]
    high = [{**item, "worker_id": index % 4, "chunk_id": f"b-{index}",
             "attempt_index": 1, "wall_seconds": 1.0}
            for index, item in enumerate(reversed(_records()))]
    assert scientific_semantic_projection(low) == scientific_semantic_projection(high)
    assert scientific_semantic_digest(low) == scientific_semantic_digest(high)
    assert PERFORMANCE["semantic_digest_helper"]["identical"] is True


def test_target_v4_and_world_target_survive_performance_metadata() -> None:
    target = json.loads((ROOT / "target_v4_execution_contract_v1.json").read_text())
    assert target["target_v4_execution_contract_sha256"] == TARGET_V4_HASH
    labeled = next(record for record in RB18["residual"]
                   if record["disposition"] == "LABELED")
    original = labeled["residual_target_world_acceleration"]
    changed_operations = [{"atomic_unit_id": labeled["scientific_row_id"],
                           "target_world": original, "worker_id": 8,
                           "chunk_id": "different", "wall_seconds": 0.01}]
    projection = scientific_semantic_projection(changed_operations)[0]
    assert projection["target_world"] == original
    assert len(original) == 2


def test_no_eligible_disposition_survives_resume_projection() -> None:
    record = next(item for item in RB18["residual"]
                  if item["disposition"] == "NO_ELIGIBLE_ACTION")
    before = [{"atomic_unit_id": record["scientific_row_id"], "payload": record,
               "attempt_index": 0}]
    replay = [{"atomic_unit_id": record["scientific_row_id"], "payload": record,
               "attempt_index": 1, "worker_id": 5}]
    assert scientific_semantic_digest(before) == scientific_semantic_digest(replay)
    assert scientific_semantic_projection(replay)[0]["payload"]["disposition"] == (
        "NO_ELIGIBLE_ACTION")


def test_nested_thread_controls_apply_in_a_fresh_process() -> None:
    code = (
        "import json; from rvt_swarm.phase9c_rb21.rb21_units import ThreadSettings; "
        "print(json.dumps(ThreadSettings().apply(), sort_keys=True))"
    )
    observed = json.loads(subprocess.check_output(
        [sys.executable, "-c", code], text=True))
    assert set(observed.values()) == {1}


def test_timeout_is_infrastructure_only_and_emits_no_target() -> None:
    result = infrastructure_timeout_result("u" * 64, 123.0)
    assert result["status"] == "INFRASTRUCTURE_FAILURE"
    assert result["scientific_horizon_changed"] is False
    assert result["target_v4_evaluated_from_timeout"] is False
    assert result["target_row_emitted"] is False
    assert result["semantic_retry_count"] == 0
    assert "VALID_TASK_NEGATIVE" not in result.values()
