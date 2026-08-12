#!/usr/bin/env python3
"""Execute one mechanically activated official command in the exact image."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic
from typing import Any, Mapping

from rvt_swarm.phase8.common import attach_canonical_hash, sha256_document


def _canonical(path: Path, field: str) -> Mapping[str, Any]:
    document = json.loads(path.read_text(encoding="ascii"))
    body = dict(document)
    expected = str(body.pop(field, ""))
    if len(expected) != 64 or sha256_document(body) != expected:
        raise RuntimeError(f"canonical artifact mismatch: {path.name}")
    return document


def _timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _write_status(path: Path, body: Mapping[str, Any], hash_field: str) -> None:
    document = attach_canonical_hash(dict(body), hash_field)
    temporary = path.with_suffix(path.suffix + ".partial")
    temporary.write_text(
        json.dumps(document, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )
    temporary.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--activation", type=Path, required=True)
    parser.add_argument("--command-id", required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--status-output", type=Path, required=True)
    parser.add_argument("--resolve-only", action="store_true")
    args = parser.parse_args()

    branch = json.loads(args.activation.read_text(encoding="ascii"))["branch"]
    activation = _canonical(
        args.activation, f"phase9g_a1_{branch}_command_activation_sha256"
    )
    commands = {
        command["command_id"]: command for command in activation["commands"]
    }
    if args.command_id not in commands:
        raise RuntimeError("command ID is not present in the activated scope")
    command = commands[args.command_id]
    image = str(activation["production_image"])
    observed_image = subprocess.run(
        ["docker", "image", "inspect", image, "--format", "{{.Id}}"],
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()
    if observed_image != image:
        raise RuntimeError("production image digest mismatch")

    data_root = args.data_root.resolve()
    status_path = args.status_output.resolve()
    status_path.parent.mkdir(parents=True, exist_ok=True)
    log_root = status_path.parent
    mode = "RESOLVE_ONLY" if args.resolve_only else "OFFICIAL_EXECUTION"
    argv = list(
        command["resolve_command_argv"]
        if args.resolve_only
        else command["official_command_argv"]
    )
    container_name = (
        f"phase9g-a1-{branch}-{command['split']}"
        .replace("_", "-")
        .replace("/", "-")
    )
    docker_argv = [
        "docker", "run", "--rm", "--name", container_name,
        "--mount", f"type=bind,src={data_root},dst=/rvt-data",
    ]
    for variable in (
        "OMP_NUM_THREADS=1",
        "MKL_NUM_THREADS=1",
        "OPENBLAS_NUM_THREADS=1",
        "NUMEXPR_NUM_THREADS=1",
    ):
        docker_argv.extend(("--env", variable))
    docker_argv.append(image)
    docker_argv.extend(argv)

    started_at = _timestamp()
    status = {
        "schema_version": "rvt-phase9g-a1-command-lifecycle/v1",
        "run_id": activation["run_id"],
        "command_id": args.command_id,
        "branch": branch,
        "split": command["split"],
        "mode": mode,
        "state": "RUNNING",
        "started_at_utc": started_at,
        "completed_at_utc": None,
        "exit_code": None,
        "wall_seconds": None,
        "production_image": image,
        "container_name": container_name,
        "scientific_command_from_activation": True,
    }
    hash_field = "phase9g_a1_command_lifecycle_sha256"
    _write_status(status_path, status, hash_field)
    stdout_path = log_root / f"{args.command_id}.stdout.jsonl"
    stderr_path = log_root / f"{args.command_id}.stderr.log"
    started = monotonic()
    with stdout_path.open("w", encoding="ascii") as stdout, stderr_path.open(
        "w", encoding="ascii"
    ) as stderr:
        completed = subprocess.run(docker_argv, stdout=stdout, stderr=stderr)
    status["state"] = "COMPLETE" if completed.returncode == 0 else "FAILED"
    status["completed_at_utc"] = _timestamp()
    status["exit_code"] = completed.returncode
    status["wall_seconds"] = monotonic() - started
    _write_status(status_path, status, hash_field)
    if completed.returncode:
        raise SystemExit(completed.returncode)
    print(json.dumps({
        "command_id": args.command_id,
        "state": status["state"],
        "wall_seconds": status["wall_seconds"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
