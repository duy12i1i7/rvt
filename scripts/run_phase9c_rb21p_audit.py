#!/usr/bin/env python3
"""Run one read-only RB21P diagnostic and write canonical JSON."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rvt_swarm.phase8.common import attach_canonical_hash
from rvt_swarm.phase9c_rb21p import (
    audit_authoritative_layouts,
    audit_fd24_batch_numerics,
    audit_fd24_cuda_forward,
    audit_rb20_semantic_replay,
)

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "mode",
        choices=("fd24-numerics", "fd24-cuda", "layouts", "rb20-replay"),
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    builders = {
        "fd24-numerics": audit_fd24_batch_numerics,
        "fd24-cuda": audit_fd24_cuda_forward,
        "layouts": audit_authoritative_layouts,
        "rb20-replay": audit_rb20_semantic_replay,
    }
    document = builders[args.mode](ROOT)
    document = attach_canonical_hash(document, "canonical_sha256")
    payload = json.dumps(document, allow_nan=False, indent=2, sort_keys=True) + "\n"
    if args.output is None:
        print(payload, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="ascii")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
