#!/usr/bin/env python3
"""Resolve or execute the real official Phase-9 generation producers."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path

from rvt_swarm.phase9g0r.compiler import (
    compile_recoverability_tasks,
    compile_residual_tasks,
)
from rvt_swarm.phase9g0p.executor import execute_recoverability, execute_residual
from rvt_swarm.phase8.common import sha256_document
from rvt_swarm.phase9g0r.preflight import validate_authorization_scope
from rvt_swarm.phase9g0r.writer import CanonicalGenerationWriter


def _source_binding_matches(root: Path, source_commit: str) -> bool:
    image_commit = os.environ.get("RVT_SOURCE_COMMIT")
    if image_commit is not None:
        return image_commit == source_commit
    return subprocess.run(
        ["git", "merge-base", "--is-ancestor", source_commit, "HEAD"],
        cwd=root,
        check=False,
    ).returncode == 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--study", required=True)
    parser.add_argument("--split", required=True)
    parser.add_argument("--branch", choices=("recoverability", "residual"), required=True)
    parser.add_argument("--mode", choices=("DIAGNOSTIC", "OFFICIAL_STAGING"), required=True)
    parser.add_argument("--writer-root", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--docker-image", required=True)
    parser.add_argument("--job-manifest-sha256", required=True)
    parser.add_argument("--scientific-addendum-sha256", required=True)
    parser.add_argument("--generation-provenance-root", required=True)
    parser.add_argument("--authorization-scope-sha256", required=True)
    parser.add_argument("--authorization-scope", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--operational-profile", type=Path)
    parser.add_argument("--operational-profile-sha256")
    parser.add_argument("--workers", type=int)
    parser.add_argument("--numeric-threads", type=int)
    parser.add_argument("--chunk-size", type=int)
    parser.add_argument("--infrastructure-timeout-seconds", type=float)
    parser.add_argument("--resolve-only", action="store_true")
    args = parser.parse_args()

    root = args.root.resolve()
    if not _source_binding_matches(root, args.source_commit):
        raise SystemExit("source commit does not match the immutable execution source")
    for name, value in (
        ("scientific addendum", args.scientific_addendum_sha256),
        ("job manifest", args.job_manifest_sha256),
        ("generation provenance root", args.generation_provenance_root),
        ("authorization scope", args.authorization_scope_sha256),
    ):
        if len(value) != 64:
            raise SystemExit(f"{name} must be a SHA-256 digest")
    if not args.docker_image.startswith("sha256:") or len(args.docker_image) != 71:
        raise SystemExit("Docker image must be an exact sha256 image ID")
    from rvt_swarm.phase9g0r.compiler import JOB_MANIFEST_SHA256
    if args.job_manifest_sha256 != JOB_MANIFEST_SHA256:
        raise SystemExit("official job manifest binding mismatch")

    operational = None
    supplied_operational_arguments = (
        args.operational_profile,
        args.operational_profile_sha256,
        args.workers,
        args.numeric_threads,
        args.chunk_size,
        args.infrastructure_timeout_seconds,
    )
    if any(value is not None for value in supplied_operational_arguments):
        if any(value is None for value in supplied_operational_arguments):
            raise SystemExit("operational profile arguments must be supplied together")
        operational_document = json.loads(
            args.operational_profile.read_text(encoding="ascii")
        )
        supplied_hash = str(
            operational_document.pop("phase9g0p_operational_contract_sha256", "")
        )
        if supplied_hash != args.operational_profile_sha256 or (
            sha256_document(operational_document) != supplied_hash
        ):
            raise SystemExit("operational profile artifact hash mismatch")
        operational = dict(operational_document["profiles"][args.branch])
        expected = {
            "workers": int(args.workers),
            "numeric_threads": int(args.numeric_threads),
            "chunk_size_atomic_units": int(args.chunk_size),
            "infrastructure_timeout_seconds": float(
                args.infrastructure_timeout_seconds
            ),
        }
        if any(operational.get(key) != value for key, value in expected.items()):
            raise SystemExit("branch operational profile binding mismatch")
        if int(args.chunk_size) != 1:
            raise SystemExit("qualified production executor requires atomic chunk size 1")

    tasks = (
        compile_recoverability_tasks(root, study=args.study, split=args.split)
        if args.branch == "recoverability"
        else compile_residual_tasks(root, study=args.study, split=args.split)
    )
    resolution = {
        "schema_version": "rvt-official-command-resolution/v2",
        "run_id": args.run_id,
        "study": args.study,
        "split": args.split,
        "branch": args.branch,
        "mode": args.mode,
        "task_count": len(tasks),
        "source_commit": args.source_commit,
        "docker_image": args.docker_image,
        "job_manifest_sha256": args.job_manifest_sha256,
        "scientific_addendum_sha256": args.scientific_addendum_sha256,
        "generation_provenance_root": args.generation_provenance_root,
        "authorization_scope_sha256": args.authorization_scope_sha256,
        "writer_root": str(args.writer_root),
        "scientific_execution": not args.resolve_only,
        "operational_profile": operational,
        "operational_profile_sha256": args.operational_profile_sha256,
    }
    scope = json.loads(args.authorization_scope.read_text(encoding="ascii"))
    supplied_scope_hash = str(scope.pop("phase9_authorization_scope_sha256", ""))
    if supplied_scope_hash != args.authorization_scope_sha256 or (
        sha256_document(scope) != supplied_scope_hash
    ):
        raise SystemExit("authorization scope artifact hash mismatch")
    execution_authorized = validate_authorization_scope(
        scope,
        study=args.study,
        split=args.split,
        branch=args.branch,
        source_commit=args.source_commit,
        docker_image=args.docker_image,
        addendum_sha256=args.scientific_addendum_sha256,
        provenance_root=args.generation_provenance_root,
    )
    resolution["official_generation_execution_authorized"] = execution_authorized
    if args.resolve_only:
        print(json.dumps(resolution, sort_keys=True))
        return
    if operational is None:
        raise SystemExit("official execution requires the qualified operational profile")
    writer = CanonicalGenerationWriter(
        args.writer_root,
        mode=args.mode,
        official_execution_authorized=execution_authorized,
    )
    if args.branch == "recoverability":
        execution = execute_recoverability(
            root,
            tasks,
            writer,
            workers=int(args.workers),
            timeout_seconds=float(args.infrastructure_timeout_seconds),
        )
    else:
        execution = execute_residual(
            root,
            tasks,
            writer,
            workers=int(args.workers),
            timeout_seconds=float(args.infrastructure_timeout_seconds),
            source_commit=args.source_commit,
            scientific_addendum_sha256=args.scientific_addendum_sha256,
        )
    resolution["execution_summary"] = execution
    print(json.dumps(resolution, sort_keys=True))


if __name__ == "__main__":
    main()
