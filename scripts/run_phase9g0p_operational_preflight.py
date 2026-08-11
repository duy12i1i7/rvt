#!/usr/bin/env python3
"""Resolve every held command and execute the Phase 9G0-P negative matrix."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

from rvt_swarm.phase8.common import attach_canonical_hash
from rvt_swarm.phase9g0p.preflight import positive_preflight, run_negative_preflight


def _localize(command: str, root: Path) -> list[str]:
    result = shlex.split(command)
    replacements = {
        "python": sys.executable,
        "/opt/rvt/scripts/run_phase9_official_generation.py": str(
            root / "scripts/run_phase9_official_generation.py"
        ),
        "/opt/rvt": str(root),
        "/rvt-data/authorization": str(root / "results/rvt_fd24"),
    }
    localized = []
    for value in result:
        for source, target in replacements.items():
            if value == source:
                value = target
                break
            if value.startswith(source + "/"):
                value = target + value[len(source):]
                break
        localized.append(value)
    return localized


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    positive = positive_preflight(root)
    negative = run_negative_preflight(root)
    if negative["escapes"]:
        raise SystemExit("operational negative preflight escaped")
    plan = json.loads((
        root / "results/rvt_fd24/phase9_official_command_plan_v2_operational_addendum_v1.json"
    ).read_text(encoding="ascii"))
    resolutions = []
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(root)
    for launch in plan["launch_specifications"]:
        completed = subprocess.run(
            _localize(str(launch["resolution_command"]), root),
            cwd=root,
            env=environment,
            check=True,
            text=True,
            capture_output=True,
        )
        resolution = json.loads(completed.stdout)
        if resolution["scientific_execution"] or resolution[
            "official_generation_execution_authorized"
        ]:
            raise SystemExit("held resolution became executable")
        resolutions.append({
            "command_id": launch["command_id"],
            "task_count": resolution["task_count"],
            "operational_profile": resolution["operational_profile"],
            "scientific_execution": False,
            "official_generation_execution_authorized": False,
            "resolved": True,
        })
    report = {
        "schema_version": "rvt-phase9g0p-operational-preflight/v1",
        "status": "PASS",
        "positive": positive,
        "negative_case_count": negative["case_count"],
        "negative_escapes": negative["escapes"],
        "negative_cases": negative["cases"],
        "resolution_count": len(resolutions),
        "all_commands_resolved": all(item["resolved"] for item in resolutions),
        "resolutions": resolutions,
        "authorization_remains_false": True,
        "commands_executed": 0,
        "official_staging_writes": 0,
        "study_a_n24_accesses": 0,
        "final_test_accesses": 0,
    }
    document = attach_canonical_hash(
        report, "phase9g0p_operational_preflight_sha256"
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(document, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )
    print(json.dumps({
        "status": document["status"],
        "resolutions": document["resolution_count"],
        "negative_cases": document["negative_case_count"],
        "escapes": document["negative_escapes"],
        "sha256": document["phase9g0p_operational_preflight_sha256"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
