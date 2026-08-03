"""Materialize the Phase 9 preflight and budget-completeness artifacts."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rvt_swarm.phase8.common import write_json
from rvt_swarm.phase9 import build_generation_budget, build_preflight_audit


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    root = args.root.resolve()
    output = root / "results/rvt_fd24/datasets"
    write_json(output / "phase9_preflight_audit.json", build_preflight_audit(root))
    write_json(output / "phase9_generation_budget.json", build_generation_budget(root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
