#!/usr/bin/env python3
"""Freeze target W=1 evidence and worker matrices before scaling observations."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

from rvt_swarm.phase8.common import attach_canonical_hash, sha256_document


BASE_IMAGE = "sha256:5e13c21aaa20f2ac02eff36172aea467720b9c925d13882708e3e90686655d9c"
UPDATED_IMAGE = "sha256:a1051285a9eb5c314c0d200287bcd04097a1d30d7ebda41a9045ec63225b365a"
EXECUTION_COMMIT = "b4d2eec40da8ec0c554e397c08eaf2245c1b3d90"


def _load_result(path: Path) -> Mapping[str, Any]:
    document = json.loads(path.read_text(encoding="ascii"))
    expected = str(document["phase9g0p_benchmark_result_sha256"])
    body = dict(document)
    body.pop("phase9g0p_benchmark_result_sha256")
    if sha256_document(body) != expected:
        raise RuntimeError(f"W=1 result hash mismatch: {path}")
    return document


def _write(path: Path, body: Mapping[str, Any], field: str) -> str:
    document = attach_canonical_hash(dict(body), field)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(document, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )
    return str(document[field])


def _compact_result(document: Mapping[str, Any]) -> Mapping[str, Any]:
    result = dict(document)
    raw_hash = str(result.pop("phase9g0p_benchmark_result_sha256"))
    projection = result.pop("scientific_semantic_projection")
    if sha256_document(projection) != result["scientific_semantic_digest"]:
        raise RuntimeError("embedded scientific projection does not match its digest")
    result.update({
        "raw_target_result_sha256": raw_hash,
        "scientific_semantic_projection_embedded": False,
        "scientific_semantic_projection_reconstructable": True,
    })
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--recoverability-w1", type=Path, required=True)
    parser.add_argument("--residual-w1", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    output = root / "results/rvt_fd24/phase9g0p_benchmarks"
    recoverability = _load_result(args.recoverability_w1)
    residual = _load_result(args.residual_w1)
    if recoverability["branch"] != "recoverability" or residual["branch"] != "residual":
        raise RuntimeError("W=1 branch result binding is invalid")
    if recoverability["workers"] != 1 or residual["workers"] != 1:
        raise RuntimeError("worker predeclaration requires W=1 evidence")

    recoverability_hash = _write(
        output / "recoverability_w1_target_v1.json",
        _compact_result(recoverability),
        "phase9g0p_compact_benchmark_result_sha256",
    )
    residual_hash = _write(
        output / "residual_w1_target_v1.json",
        _compact_result(residual),
        "phase9g0p_compact_benchmark_result_sha256",
    )

    environment = {
        "schema_version": "rvt-phase9g0p-target-environment/v1",
        "target_host": "100.71.102.9",
        "windows": {
            "cpu_model": "Intel(R) Core(TM) Ultra 9 285K",
            "physical_cores": 24,
            "logical_cpus": 24,
            "physical_memory_bytes": 68053331968,
        },
        "wsl": {
            "distribution": "Ubuntu-24.04",
            "kernel": "6.18.33.2-microsoft-standard-WSL2",
            "visible_logical_cpus": 24,
            "visible_memory_bytes": 33323397120,
            "available_memory_bytes_before_benchmark": 31691128832,
            "swap_bytes": 8589934592,
            "root_filesystem_bytes": 1081101176832,
            "root_filesystem_available_bytes": 1024089227264,
        },
        "docker": {
            "desktop_version": "4.80.0",
            "engine_client_version": "29.6.1",
            "engine_server_version": "29.6.1",
            "api_version": "1.55",
            "visible_cpuset": "0-23",
            "cpu_quota": "max 100000",
            "memory_limit": "max",
            "swap_limit": "max",
            "overlay_available_bytes": 422363889664,
        },
        "gpu": {
            "model": "NVIDIA RTX 5000 Ada Generation",
            "uuid": "GPU-262a5f7e-fa85-a213-98ed-2761941b4e9a",
            "vram_mib": 32760,
            "driver_version": "536.96",
            "container_nvidia_smi_visible": True,
            "generation_pytorch_cuda_available": False,
            "generation_pytorch_cuda_device_count": 0,
            "generation_cpu_authoritative": True,
        },
        "images": {
            "qualified_phase9g0r_base": BASE_IMAGE,
            "updated_phase9g0p_execution_image": UPDATED_IMAGE,
            "updated_image_parent_is_exact_qualified_base": True,
        },
        "execution_commit": EXECUTION_COMMIT,
    }
    environment_hash = _write(
        root / "results/rvt_fd24/phase9g0p_target_environment_v1.json",
        environment,
        "phase9g0p_target_environment_sha256",
    )

    reserve_bytes = 8 * 1024 ** 3
    available_bytes = int(environment["wsl"]["available_memory_bytes_before_benchmark"])
    usable_bytes = available_bytes - reserve_bytes
    recoverability_rss = int(
        recoverability["memory"]["peak_aggregate_rss_upper_bound_bytes"]
    )
    residual_rss = int(residual["memory"]["peak_aggregate_rss_upper_bound_bytes"])
    cpu_ceiling = int(environment["wsl"]["visible_logical_cpus"]) - 2
    matrix = {
        "schema_version": "rvt-phase9g0p-worker-matrix-predeclaration/v1",
        "predeclared_before_worker_scaling_results": True,
        "target_environment_sha256": environment_hash,
        "w1_evidence": {
            "recoverability_compact_result_sha256": recoverability_hash,
            "residual_compact_result_sha256": residual_hash,
        },
        "headroom_contract": {
            "logical_cpus_reserved_for_wsl_docker_writer": 2,
            "memory_headroom_bytes": reserve_bytes,
            "memory_available_for_workers_bytes": usable_bytes,
            "cpu_worker_ceiling": cpu_ceiling,
        },
        "recoverability": {
            "profile_id": "PROFILE_RECOVERABILITY_V1",
            "w1_peak_rss_bytes": recoverability_rss,
            "memory_worker_ceiling": usable_bytes // recoverability_rss,
            "effective_worker_ceiling": min(cpu_ceiling, usable_bytes // recoverability_rss),
            "worker_matrix": [1, 6, 12, 18, 22],
            "matrix_rationale": (
                "24 atomic units permit direct half/quarter occupancy observations; "
                "W=22 preserves two logical CPUs for WSL, Docker and the parent writer"
            ),
        },
        "residual": {
            "profile_id": "PROFILE_RESIDUAL_V2_V1",
            "w1_peak_rss_bytes": residual_rss,
            "memory_worker_ceiling": usable_bytes // residual_rss,
            "effective_worker_ceiling": min(cpu_ceiling, usable_bytes // residual_rss),
            "worker_matrix": [1, 4, 8, 12, 18, 22],
            "matrix_rationale": (
                "25 heavy-tailed atomic units require denser low/mid concurrency "
                "observations and retain W=22 as the CPU-headroom ceiling"
            ),
        },
        "numeric_threads_per_worker": 1,
        "chunk_size_during_worker_scaling": 1,
        "scientific_semantic_digest_must_equal_w1": True,
        "selection_uses_worker_scaling_results": False,
    }
    matrix_hash = _write(
        root / "results/rvt_fd24/phase9g0p_worker_matrix_predeclaration_v1.json",
        matrix,
        "phase9g0p_worker_matrix_predeclaration_sha256",
    )
    print(json.dumps({
        "target_environment": environment_hash,
        "worker_matrix": matrix_hash,
        "recoverability_w1": recoverability_hash,
        "residual_w1": residual_hash,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
