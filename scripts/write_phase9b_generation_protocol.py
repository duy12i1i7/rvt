"""Write the deterministic Phase 9B addendum manifests only."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rvt_swarm.phase8.common import write_json  # noqa: E402
from rvt_swarm.phase9b.budget import (  # noqa: E402
    build_generation_budget_manifest,
    build_generation_protocol_manifest,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    root = args.root.resolve()
    result_root = root / "results/rvt_fd24/datasets"
    budget = build_generation_budget_manifest(root)
    protocol = build_generation_protocol_manifest(root, budget)
    write_json(result_root / "generation_budget_v1.json", budget)
    write_json(result_root / "dataset_generation_protocol_v1.json", protocol)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
