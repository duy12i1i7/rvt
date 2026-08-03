#!/usr/bin/env python3
"""Write deterministic Phase 8 split, diagnostic and protocol artifacts."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rvt_swarm.phase8.common import write_json  # noqa: E402
from rvt_swarm.phase8.diagnostic import run_tiny_target_diagnostic  # noqa: E402
from rvt_swarm.phase8.final_test_guard import write_empty_official_audit  # noqa: E402
from rvt_swarm.phase8.manifest import write_experiment_protocol_manifest  # noqa: E402
from rvt_swarm.phase8.scenario import scenario_family_manifest  # noqa: E402
from rvt_swarm.phase8.splits import write_split_manifests  # noqa: E402


RESULT_ROOT = ROOT / "results/rvt_fd24"


def main() -> None:
    write_split_manifests(RESULT_ROOT)
    write_json(RESULT_ROOT / "scenario_family_manifest.json", scenario_family_manifest())
    write_json(
        RESULT_ROOT / "phase8_tiny_target_diagnostic.json",
        run_tiny_target_diagnostic(),
    )
    write_empty_official_audit(RESULT_ROOT / "final_test_access_audit.jsonl")
    write_experiment_protocol_manifest(ROOT)


if __name__ == "__main__":
    main()
