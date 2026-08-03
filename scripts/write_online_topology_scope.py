#!/usr/bin/env python3
"""Write the immutable Phase 7S online-topology scope manifest."""

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rvt_swarm.decentralized.online_topology_scope import (  # noqa: E402
    serialize_online_topology_scope_manifest,
)


OUTPUT = ROOT / "results/rvt_fd24/online_topology_scope.json"


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        serialize_online_topology_scope_manifest(),
        encoding="ascii",
    )


if __name__ == "__main__":
    main()
