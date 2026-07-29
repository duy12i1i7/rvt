"""Provenance stamp attached to every pilot result file (Task 0.4)."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from typing import Dict

REPO = Path(__file__).resolve().parent.parent

BENCHMARK_PROTOCOL_TAG = "benchmark-protocol-v2-smoke"
RECOVERY_EVENT_VERSION = 2
EVALUATION_SCHEMA_VERSION = 2
LAYOUT_SPLIT_VERSION = "layouts-v1"
DATASET_VERSION = "taskrecovery-v2-labels"
PILOT_TAG = "recovery-event-v2-complete"


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO,
                                       stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return "unknown"


def layout_split_hash() -> str:
    """Hash of every layout geometry, so a split change is detectable."""
    from .layouts import all_layouts

    h = hashlib.sha256()
    for split in ("train", "val", "test"):
        for lay in all_layouts()[split]:
            h.update(lay.layout_id.encode())
            h.update(lay.geometry_hash().encode())
    return h.hexdigest()[:16]


def stamp(**extra) -> Dict[str, object]:
    """The provenance block required in every pilot result row/file."""
    out = {
        "source_commit": git_commit(),
        "benchmark_protocol_tag": BENCHMARK_PROTOCOL_TAG,
        "recovery_event_version": RECOVERY_EVENT_VERSION,
        "evaluation_schema_version": EVALUATION_SCHEMA_VERSION,
        "dataset_version": DATASET_VERSION,
        "layout_split_version": LAYOUT_SPLIT_VERSION,
        "layout_split_hash": layout_split_hash(),
    }
    out.update(extra)
    return out


def checkpoint_provenance(path) -> Dict[str, object]:
    import torch

    p = Path(path)
    if not p.exists():
        return {"checkpoint": str(p), "exists": False}
    state = torch.load(p, map_location="cpu", weights_only=False)
    return {
        "checkpoint": str(p.relative_to(REPO)) if p.is_absolute() else str(p),
        "exists": True,
        "sha256": hashlib.sha256(p.read_bytes()).hexdigest()[:16],
        "epoch": int(state.get("epoch", -1)),
        "git_commit": str(state.get("git_commit", "unknown")),
        "evaluation_schema_version": int(state.get("evaluation_schema_version", -1)),
        "writer_token": str(state.get("writer_token", "unknown")),
    }
