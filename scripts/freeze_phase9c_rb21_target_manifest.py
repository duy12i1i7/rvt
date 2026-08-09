#!/usr/bin/env python3
"""Freeze the RB21 target benchmark workload without executing it."""

from pathlib import Path

from rvt_swarm.phase9c_rb21.rb21_manifest import (
    build_target_benchmark_manifest,
    write_json,
)


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    write_json(
        ROOT / "results/rvt_fd24/rb21_target_benchmark_manifest_v1.json",
        build_target_benchmark_manifest(),
    )


if __name__ == "__main__":
    main()
