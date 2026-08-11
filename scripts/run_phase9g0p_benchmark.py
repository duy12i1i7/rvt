#!/usr/bin/env python3
"""Run one predeclared diagnostic Phase 9G0-P benchmark profile."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from rvt_swarm.phase9g0p.benchmark import run_recoverability, run_residual


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--branch", choices=("recoverability", "residual"), required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--workers", type=int, required=True)
    parser.add_argument("--chunk-size", type=int, required=True)
    parser.add_argument("--diagnostic-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.workers < 1 or args.chunk_size < 1:
        raise SystemExit("workers and chunk size must be positive")
    runner = run_recoverability if args.branch == "recoverability" else run_residual
    result = runner(
        args.root.resolve(),
        manifest_path=args.manifest.resolve(),
        workers=args.workers,
        chunk_size=args.chunk_size,
        diagnostic_root=args.diagnostic_root.resolve(),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )
    print(json.dumps({
        "branch": args.branch,
        "workers": args.workers,
        "chunk_size": args.chunk_size,
        "semantic_digest": result["scientific_semantic_digest"],
        "wall_seconds": result["wall_seconds"],
        "output": str(args.output),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
