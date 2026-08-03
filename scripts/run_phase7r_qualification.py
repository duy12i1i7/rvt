#!/usr/bin/env python3
"""Run the frozen Phase 7R forensic and repaired qualification matrices."""

from __future__ import annotations

import json
from pathlib import Path

from rvt_swarm.decentralized.phase7r_qualification import run_phase7r_qualification


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    print(json.dumps(run_phase7r_qualification(root), indent=2, sort_keys=True))
