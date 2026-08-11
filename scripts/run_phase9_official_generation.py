#!/usr/bin/env python3
"""Resolve or execute the real official Phase-9 generation producers."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from rvt_swarm.phase9g0r.compiler import (
    compile_recoverability_tasks,
    compile_residual_tasks,
)
from rvt_swarm.phase9g0r.producer import (
    plan_residual_retained_states,
    produce_recoverability_event,
    produce_residual_state,
)
from rvt_swarm.phase8.common import sha256_document
from rvt_swarm.phase9g0r.preflight import validate_authorization_scope
from rvt_swarm.phase9g0r.writer import CanonicalGenerationWriter


def _source_is_ancestor(root: Path, source_commit: str) -> bool:
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
    parser.add_argument("--resolve-only", action="store_true")
    args = parser.parse_args()

    root = args.root.resolve()
    if not _source_is_ancestor(root, args.source_commit):
        raise SystemExit("source commit is not an ancestor of this checkout")
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
    writer = CanonicalGenerationWriter(
        args.writer_root,
        mode=args.mode,
        official_execution_authorized=execution_authorized,
    )
    if args.branch == "recoverability":
        for task in tasks:
            produce_recoverability_event(root, task, writer=writer)
    else:
        for task in tasks:
            retained = plan_residual_retained_states(root, task.source)
            for robot_id, timesteps in retained.items():
                for timestep in timesteps:
                    produce_residual_state(
                        root,
                        task.source,
                        robot_id=robot_id,
                        timestep=timestep,
                        source_commit=args.source_commit,
                        scientific_addendum_sha256=args.scientific_addendum_sha256,
                        writer=writer,
                    )


if __name__ == "__main__":
    main()
