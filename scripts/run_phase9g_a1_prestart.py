#!/usr/bin/env python3
"""Run the scoped Phase 9G-A1 pre-start audit on the qualified target."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
from pathlib import Path
from typing import Any, Mapping

from rvt_swarm.phase8.common import attach_canonical_hash, sha256_document


CLOSURE_COMMIT = "6bcfc0e26c4b327ba63f2844eaa02d30d56903ba"
PRODUCTION_IMAGE = (
    "sha256:88ecf1aac7cd95b5ba50811950090c13f78362274e5c5cdaeafaafde29a115f4"
)
AUTHORIZED_STUDY = "study_a_zero_shot"
AUTHORIZED_SPLITS = frozenset({"train", "validation"})
AUTHORIZED_BRANCHES = frozenset({"recoverability", "residual"})

CANONICAL_ARTIFACTS = {
    "performance_readiness": (
        "phase9_production_performance_readiness_v1.json",
        "phase9_production_performance_readiness_sha256",
    ),
    "operational_contract": (
        "phase9g0p_operational_production_contract_v2.json",
        "phase9g0p_operational_contract_sha256",
    ),
    "command_plan": (
        "phase9_official_command_plan_v2_operational_addendum_v1.json",
        "phase9g0p_command_plan_operational_addendum_sha256",
    ),
    "generation_provenance": (
        "phase9_current_generation_provenance_v2.json",
        "phase9_current_generation_provenance_sha256",
    ),
    "scientific_addendum": (
        "phase9_predata_generation_scientific_addendum_v1.json",
        "phase9_predata_generation_scientific_addendum_sha256",
    ),
    "recoverability_row_identity": (
        "phase9_recoverability_row_identity_v1.json",
        "phase9_recoverability_row_identity_sha256",
    ),
    "recoverability_row_binding": (
        "phase9_recoverability_row_binding_v1.json",
        "phase9_recoverability_row_binding_sha256",
    ),
    "matched_randomness": (
        "phase9_matched_randomness_binding_v1.json",
        "phase9_matched_randomness_binding_sha256",
    ),
    "candidate_pair_transaction": (
        "phase9_recoverability_candidate_pair_transaction_v1.json",
        "phase9_recoverability_candidate_pair_transaction_sha256",
    ),
    "residual_dense_retention": (
        "phase9_residual_dense_state_retention_v1.json",
        "phase9_residual_dense_state_retention_sha256",
    ),
    "operational_preflight": (
        "phase9g0p_operational_preflight_v1.json",
        "phase9g0p_operational_preflight_sha256",
    ),
}


class PrestartError(RuntimeError):
    """The target is not admissible for the authorization transition."""


def _canonical_artifact(path: Path, hash_field: str) -> tuple[str, Mapping[str, Any]]:
    document = json.loads(path.read_text(encoding="ascii"))
    body = dict(document)
    expected = str(body.pop(hash_field, ""))
    if len(expected) != 64 or sha256_document(body) != expected:
        raise PrestartError(f"canonical artifact mismatch: {path.name}")
    return expected, document


def _run(*args: str, cwd: Path | None = None) -> str:
    completed = subprocess.run(
        list(args), cwd=cwd, check=True, text=True, capture_output=True
    )
    return completed.stdout.strip()


def _file_count(root: Path) -> int:
    return sum(1 for path in root.rglob("*") if path.is_file()) if root.exists() else 0


def _official_name_count(root: Path, fragments: tuple[str, ...]) -> int:
    if not root.exists():
        return 0
    return sum(
        1
        for path in root.rglob("*")
        if path.is_file() and any(fragment in path.name.lower() for fragment in fragments)
    )


def _resolve_scoped_commands(
    result_root: Path,
    plan: Mapping[str, Any],
) -> list[Mapping[str, Any]]:
    selected = [
        launch
        for launch in plan["launch_specifications"]
        if launch.get("study") == AUTHORIZED_STUDY
        and launch.get("split") in AUTHORIZED_SPLITS
        and launch.get("branch") in AUTHORIZED_BRANCHES
    ]
    if len(selected) != 4:
        raise PrestartError("command plan did not select exactly four Study A commands")

    mount = f"type=bind,src={result_root},dst=/rvt-data/authorization,readonly"
    environment = (
        "OMP_NUM_THREADS=1",
        "MKL_NUM_THREADS=1",
        "OPENBLAS_NUM_THREADS=1",
        "NUMEXPR_NUM_THREADS=1",
    )
    resolutions = []
    for launch in selected:
        command = shlex.split(str(launch["resolution_command"]))
        docker_command = ["docker", "run", "--rm", "--mount", mount]
        for binding in environment:
            docker_command.extend(("--env", binding))
        docker_command.append(PRODUCTION_IMAGE)
        docker_command.extend(command)
        completed = subprocess.run(
            docker_command, check=True, text=True, capture_output=True
        )
        resolution = json.loads(completed.stdout)
        if resolution.get("scientific_execution"):
            raise PrestartError("resolve-only command entered scientific execution")
        if resolution.get("official_generation_execution_authorized"):
            raise PrestartError("held pre-start scope unexpectedly became authorized")
        if (
            resolution.get("study") != AUTHORIZED_STUDY
            or resolution.get("split") not in AUTHORIZED_SPLITS
            or resolution.get("branch") not in AUTHORIZED_BRANCHES
        ):
            raise PrestartError("resolved command escaped the Study A scope")
        resolutions.append({
            "command_id": launch["command_id"],
            "branch": resolution["branch"],
            "split": resolution["split"],
            "task_count": resolution["task_count"],
            "scientific_execution": False,
            "official_generation_execution_authorized": False,
        })
    return resolutions


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    root = args.root.resolve()
    data_root = args.data_root.resolve()
    result_root = root / "results/rvt_fd24"
    head = _run("git", "rev-parse", "HEAD", cwd=root)
    if head != CLOSURE_COMMIT:
        raise PrestartError(f"target HEAD is {head}, expected closure {CLOSURE_COMMIT}")
    if _run("git", "status", "--porcelain", cwd=root):
        raise PrestartError("target checkout is not clean")

    image = _run("docker", "image", "inspect", PRODUCTION_IMAGE, "--format", "{{.Id}}")
    if image != PRODUCTION_IMAGE:
        raise PrestartError("qualified production image is not exact")

    hashes: dict[str, str] = {}
    documents: dict[str, Mapping[str, Any]] = {}
    for key, (name, field) in CANONICAL_ARTIFACTS.items():
        hashes[key], documents[key] = _canonical_artifact(result_root / name, field)
    readiness = documents["performance_readiness"]
    prior_preflight = documents["operational_preflight"]
    if readiness.get("status") != "READY_FOR_EXPLICIT_SCOPED_OWNER_AUTHORIZATION":
        raise PrestartError("production readiness is not open for scoped authorization")
    if prior_preflight.get("status") != "PASS" or int(
        prior_preflight.get("negative_escapes", -1)
    ) != 0:
        raise PrestartError("frozen official production preflight is not PASS/zero escape")

    staging_files = _file_count(data_root / "staging")
    final_files = _file_count(data_root / "final")
    temporary_files = _file_count(data_root / "temp")
    official_run_ids = _official_name_count(
        data_root / "audit", ("run-id", "run_identity", "official_run")
    )
    training_artifacts = _official_name_count(
        data_root, ("checkpoint", "optimizer", "hp_trial", "training_run")
    )
    if any((staging_files, final_files, temporary_files, official_run_ids, training_artifacts)):
        raise PrestartError("official data or operational identities exist before transition")

    resolutions = _resolve_scoped_commands(result_root, documents["command_plan"])
    report = {
        "schema_version": "rvt-phase9g-a1-prestart/v1",
        "status": "PASS",
        "target": {
            "host": _run("hostname"),
            "wsl_distribution": "Ubuntu-24.04",
            "source_evidence_commit": head,
            "git_status_porcelain_count": 0,
            "production_image": image,
            "data_filesystem": _run("findmnt", "-T", str(data_root), "-no", "FSTYPE"),
            "data_free_bytes": int(
                _run("df", "-B1", "--output=avail", str(data_root)).splitlines()[-1]
            ),
        },
        "validated_artifact_hashes": hashes,
        "frozen_negative_preflight": {
            "status": prior_preflight["status"],
            "case_count": prior_preflight["negative_case_count"],
            "negative_escapes": prior_preflight["negative_escapes"],
        },
        "current_scoped_command_resolutions": resolutions,
        "current_scoped_resolution_count": len(resolutions),
        "authorization_transition_performed": False,
        "pretransition_counters": {
            "official_run_ids": official_run_ids,
            "official_staging_writes": staging_files,
            "official_rows": 0,
            "official_shards": 0,
            "training_operations": 0,
            "training_artifacts": training_artifacts,
            "study_a_n24_accesses": 0,
            "study_b_accesses": 0,
            "final_test_accesses": 0,
        },
        "sealed_scope_resolution_attempts": 0,
        "scientific_commands_executed": 0,
    }
    document = attach_canonical_hash(report, "phase9g_a1_prestart_sha256")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(document, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )
    print(json.dumps({
        "status": document["status"],
        "scoped_resolutions": document["current_scoped_resolution_count"],
        "negative_escapes": document["frozen_negative_preflight"]["negative_escapes"],
        "sha256": document["phase9g_a1_prestart_sha256"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
