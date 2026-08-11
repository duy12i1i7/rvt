#!/usr/bin/env python3
"""Resolve every held Phase 9 command without executing scientific work."""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path

from rvt_swarm.phase8.common import attach_canonical_hash, sha256_document


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    results = root / "results/rvt_fd24"
    plan = json.loads(
        (results / "phase9_official_command_plan_v2.json").read_text(
            encoding="ascii"
        )
    )
    plan_hash = str(plan["phase9_official_command_plan_sha256"])
    body = dict(plan)
    body.pop("phase9_official_command_plan_sha256")
    if sha256_document(body) != plan_hash:
        raise SystemExit("command plan canonical hash mismatch")

    resolutions = []
    for launch in plan["launch_specifications"]:
        command = shlex.split(str(launch["resolution_command"]))
        command[0] = sys.executable
        command[1] = str(root / "scripts/run_phase9_official_generation.py")
        for index, value in enumerate(command):
            if value == "/opt/rvt":
                command[index] = str(root)
            elif value.startswith("/rvt-data/authorization/"):
                command[index] = str(results / Path(value).name)
        completed = subprocess.run(
            command,
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
        resolution = json.loads(completed.stdout)
        if resolution["scientific_execution"] is not False:
            raise SystemExit("resolve-only command entered scientific execution")
        if resolution["official_generation_execution_authorized"] is not False:
            raise SystemExit("held command unexpectedly became authorized")
        resolutions.append(resolution)

    artifact = attach_canonical_hash({
        "schema_version": "rvt-phase9g0r-command-plan-resolution/v1",
        "command_plan_sha256": plan_hash,
        "resolution_count": len(resolutions),
        "resolutions": resolutions,
        "all_real_producers_resolved": len(resolutions) == 8,
        "scientific_commands_executed": 0,
        "official_staging_writes": 0,
        "status": "PASS",
    }, "phase9g0r_command_plan_resolution_sha256")
    output = results / "phase9g0r_command_plan_resolution_v1.json"
    output.write_text(
        json.dumps(artifact, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )
    print(output)


if __name__ == "__main__":
    main()
