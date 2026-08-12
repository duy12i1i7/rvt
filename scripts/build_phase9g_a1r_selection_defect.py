#!/usr/bin/env python3
"""Record and exclude the first long-tail manifest's incomplete identity key."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from rvt_swarm.phase8.common import attach_canonical_hash


def _file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    result_root = root / "results/rvt_fd24"
    manifest_path = result_root / "phase9g_a1r_long_tail_manifest_selection_defect_v1.json"
    manifest = json.loads(manifest_path.read_text(encoding="ascii"))
    timeout = json.loads(
        (result_root / "phase9g_a1r_timeout_unit_v1.json").read_text(encoding="ascii")
    )
    claimed = next(
        item for item in manifest["events"]
        if "exact_timed_out_structural_unit" in item["coverage_intent"]
    )
    actual_event = str(claimed["event_id"])
    expected_event = str(timeout["timed_out_unit"]["decision_event_id"])
    if actual_event == expected_event:
        raise ValueError("selection defect is not reproduced")
    measurements = {}
    for profile in ("w1", "w12"):
        path = result_root / "phase9g_a1r_long_tail_selection_defect" / f"{profile}.json"
        measurements[profile] = {
            "file_sha256": _file_sha(path),
            "scientific_semantic_digest": json.loads(
                path.read_text(encoding="ascii")
            )["scientific_semantic_digest"],
        }
    document = {
        "schema_version": "rvt-phase9g-a1r-diagnostic-selection-defect/v1",
        "status": "INVALID_DIAGNOSTIC_SELECTION_EXCLUDED",
        "scope": "NON_OFFICIAL_DIAGNOSTIC_ONLY",
        "cause": (
            "the initial metadata selection key omitted layout_sha256 and a "
            "dictionary collision selected another F2/N12 layout"
        ),
        "claimed_exact_event_id": actual_event,
        "required_exact_event_id": expected_event,
        "claimed_layout_sha256": claimed["source"]["layout_sha256"],
        "required_layout_sha256": timeout["timed_out_unit"]["layout_sha256"],
        "manifest_file_sha256": _file_sha(manifest_path),
        "excluded_measurements": measurements,
        "may_participate_in_timeout_derivation": False,
        "official_staging_effect": 0,
        "corrective_action": (
            "predeclare v2 using family, layout_sha256, team size, source class, "
            "episode and event slot as the complete selection key"
        ),
    }
    document = attach_canonical_hash(
        document, "phase9g_a1r_diagnostic_selection_defect_sha256"
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(document, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )


if __name__ == "__main__":
    main()
