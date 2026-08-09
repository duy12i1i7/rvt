"""The target workload is frozen before target performance timing."""

import hashlib
import json
from pathlib import Path

from rvt_swarm.phase8.common import canonical_json_bytes
from rvt_swarm.phase9c_rb21.rb21_manifest import (
    RB21P_QUALIFIED_IMAGE,
    build_target_benchmark_manifest,
)


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = json.loads(
    (ROOT / "results/rvt_fd24/rb21_target_benchmark_manifest_v1.json")
    .read_text(encoding="ascii")
)


def test_target_manifest_is_canonical_and_reconstructable() -> None:
    body = {key: value for key, value in MANIFEST.items()
            if key != "rb21_target_benchmark_manifest_sha256"}
    assert hashlib.sha256(canonical_json_bytes(body)).hexdigest() == MANIFEST[
        "rb21_target_benchmark_manifest_sha256"]
    assert MANIFEST == build_target_benchmark_manifest()


def test_target_manifest_freezes_complete_nonsealed_workload() -> None:
    assert MANIFEST["freeze_state"]["frozen_before_target_timing"] is True
    assert MANIFEST["qualified_target_image"] == RB21P_QUALIFIED_IMAGE
    assert MANIFEST["sample_counts"]["residual_atomic_units"] == 32
    assert MANIFEST["sample_counts"]["recoverability_atomic_units"] == 32
    assert MANIFEST["coverage"]["team_sizes"] == [5, 8, 12, 16]
    assert MANIFEST["coverage"]["families"] == ["F1", "F5", "F8", "F9"]
    assert MANIFEST["sealed_domains"] == {
        "study_a_n24": "SEALED_NOT_INCLUDED",
        "final_test": "SEALED_NOT_INCLUDED",
    }


def test_worker_and_chunk_matrices_remain_result_independent() -> None:
    assert MANIFEST["worker_matrix_declaration"]["state"] == (
        "DERIVE_AND_FREEZE_AFTER_W1_BEFORE_SCALING")
    assert MANIFEST["chunk_matrix_declaration"]["state"] == (
        "FREEZE_AFTER_WORKER_SELECTION_BEFORE_CHUNK_TIMING")
    profile = MANIFEST["controlled_cpu_profile"]
    assert all(profile[key] == 1 for key in (
        "OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS",
        "NUMEXPR_NUM_THREADS", "torch_num_threads", "torch_num_interop_threads"))
    assert profile["scientific_cuda_execution"] is False
