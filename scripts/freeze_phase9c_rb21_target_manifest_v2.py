#!/usr/bin/env python3
"""Freeze the reachability-corrected target benchmark manifest."""

import json
from pathlib import Path

from rvt_swarm.phase9c_rb21.rb21_manifest import (
    build_target_benchmark_manifest_v2,
    write_json,
)


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    reachability = json.loads(
        (ROOT / "results/rvt_fd24/rb21_target_manifest_reachability_v1.json")
        .read_text(encoding="ascii")
    )
    write_json(
        ROOT / "results/rvt_fd24/rb21_target_benchmark_manifest_v2.json",
        build_target_benchmark_manifest_v2(reachability),
    )


if __name__ == "__main__":
    main()
