#!/usr/bin/env python3
"""Run the frozen Phase 7 mechanical qualification and write JSON artifacts."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rvt_swarm.decentralized.phase7_qualification import (  # noqa: E402
    run_and_write_phase7_qualification,
)


def main() -> None:
    output = ROOT / "results" / "phase7_transition_protocol"
    summary = run_and_write_phase7_qualification(output)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
