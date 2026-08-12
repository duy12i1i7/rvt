#!/usr/bin/env python3
"""Collect read-only target observations for the A1R resume preflight."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import subprocess
from pathlib import Path
from typing import Any


IMAGE = "sha256:88ecf1aac7cd95b5ba50811950090c13f78362274e5c5cdaeafaafde29a115f4"


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, allow_nan=False, ensure_ascii=True, separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")


def _sha(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run(*argv: str) -> str:
    return subprocess.run(
        argv, check=True, text=True, capture_output=True
    ).stdout.strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--deploy-root", type=Path, required=True)
    parser.add_argument("--target-endpoint", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    data = args.data_root.resolve()
    deploy = args.deploy_root.resolve()
    train = data / "staging/study_a_zero_shot-train-recoverability"
    validation = data / "staging/study_a_zero_shot-validation-recoverability"
    manifest = json.loads(
        (root / "results/rvt_fd24/datasets/phase9_job_manifest.json")
        .read_text(encoding="ascii")
    )
    image_id = _run("docker", "image", "inspect", IMAGE, "--format", "{{.Id}}")
    image_env = json.loads(_run(
        "docker", "image", "inspect", IMAGE, "--format", "{{json .Config.Env}}"
    ))
    phase_containers = [
        line for line in _run(
            "docker", "ps", "-a", "--format", "{{.Names}} {{.Status}}"
        ).splitlines()
        if "phase9g" in line.lower()
    ]
    source_jobs = list(manifest["source_episode_jobs"])
    event_jobs = list(manifest["decision_event_jobs"])
    n24_sources = [
        job for job in source_jobs
        if job.get("study") == "study_a_zero_shot"
        and job.get("split") == "n24_evaluation"
    ]
    deploy_files = [
        deploy / "scripts/run_phase9g_a1r_recoverability_continuation.py",
        deploy / "results/rvt_fd24/phase9g_a1r_operational_contract_amendment_v1.json",
        deploy / "results/rvt_fd24/phase9g_a1r_authorization_continuation_v1.json",
        deploy / "results/rvt_fd24/phase9g_a1r_continuation_run_identity_v1.json",
        deploy / "results/rvt_fd24/phase9g_a1r_staging_checkpoint_v1.json",
    ]
    filesystem = shutil.disk_usage(data)
    report = {
        "schema_version": "rvt-phase9g-a1r-target-preflight-observation/v1",
        "status": "PASS_READ_ONLY_OBSERVATION",
        "target_endpoint": args.target_endpoint,
        "hostname": _run("hostname"),
        "wsl_distribution": os.environ.get("WSL_DISTRO_NAME"),
        "production_image": image_id,
        "production_image_expected": IMAGE,
        "production_image_env": image_env,
        "checkout_commit": _run("git", "-C", str(root), "rev-parse", "HEAD"),
        "checkout_status_porcelain": _run(
            "git", "-C", str(root), "status", "--porcelain"
        ),
        "active_or_stopped_phase9g_containers": phase_containers,
        "staging": {
            "train_exists": train.is_dir(),
            "train_mode": stat.filemode(train.stat().st_mode),
            "train_writable": os.access(train, os.W_OK),
            "train_transaction_files": len(tuple(
                (train / "recoverability").glob("event-*.json")
            )),
            "train_partial_files": len(tuple(train.rglob("*.partial"))),
            "validation_exists": validation.exists(),
            "validation_writable": (
                os.access(validation, os.W_OK) if validation.exists() else False
            ),
            "validation_transaction_files": (
                len(tuple((validation / "recoverability").glob("event-*.json")))
                if validation.exists() else 0
            ),
        },
        "deploy_file_sha256": {
            str(path.relative_to(deploy)): _file_sha(path) for path in deploy_files
        },
        "frozen_manifest_scope": {
            "job_manifest_sha256": manifest["job_manifest_sha256"],
            "final_test_jobs_present": manifest["final_test_jobs_present"],
            "study_a_n24_source_job_count": len(n24_sources),
            "study_a_n24_all_sealed": all(
                bool(job.get("sealed")) for job in n24_sources
            ),
            "study_b_processes_started": 0,
            "final_test_processes_started": 0,
            "residual_processes_started": 0,
            "training_processes_started": 0,
            "source_job_count_metadata_only": len(source_jobs),
            "decision_event_count_metadata_only": len(event_jobs),
        },
        "storage": {
            "total_bytes": filesystem.total,
            "used_bytes": filesystem.used,
            "free_bytes": filesystem.free,
        },
    }
    if image_id != IMAGE or report["staging"]["train_writable"]:
        raise RuntimeError("target preflight observation failed")
    report["phase9g_a1r_target_preflight_observation_sha256"] = _sha(report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )


if __name__ == "__main__":
    main()
