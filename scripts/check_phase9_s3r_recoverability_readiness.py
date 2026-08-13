#!/usr/bin/env python3
"""Fail closed unless the canonical A1S3R readiness artifact says READY."""

from __future__ import annotations

import json
from pathlib import Path

from rvt_swarm.phase8.common import sha256_document


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    path = root / "results/rvt_fd24/phase9_s3_recoverability_resume_readiness_v1.json"
    document = json.loads(path.read_text(encoding="ascii"))
    body = dict(document)
    expected = body.pop("phase9_s3_recoverability_resume_readiness_sha256")
    if sha256_document(body) != expected:
        raise SystemExit("S3R readiness artifact has a canonical-hash mismatch")
    if document["readiness"] != "READY":
        raise SystemExit(
            "official Recoverability resume blocked: "
            + str(document["blocking_code"])
        )


if __name__ == "__main__":
    main()
