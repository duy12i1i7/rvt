#!/usr/bin/env python3
"""Fail closed on unresolved S3Z population semantics before a future resume."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from rvt_swarm.phase8.common import sha256_document


def validate(document: dict) -> None:
    """Validate scientific readiness without granting operational authority."""
    guard = document["population_guard"]
    if guard["missing_side_unresolved"] != 0:
        raise RuntimeError("S3_MISSING_OPPOSING_SIDE_UNDERSPECIFIED")
    if guard["tie_unresolved"] != 0:
        raise RuntimeError("S3_SUPPORT_TIE_UNDERSPECIFIED")
    if guard["escapes"] != 0:
        raise RuntimeError("S3_POPULATION_PREFLIGHT_ESCAPE")
    if document["official_data_action"] != "RETAIN_ALL_342":
        raise RuntimeError("official S3 data cannot be retained")
    if document["status"] != "QUALIFIED_AWAITING_SEPARATE_OWNER_AUTHORIZATION":
        raise RuntimeError("S3Z scientific qualification is incomplete")
    if document["official_resume_authorized_now"]:
        raise RuntimeError("unexpected embedded official authorization")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--readiness",
        type=Path,
        default=(
            Path(__file__).resolve().parents[1]
            / "results/rvt_fd24/phase9_s3_final_resume_readiness_v1.json"
        ),
    )
    args = parser.parse_args()
    document = json.loads(args.readiness.read_text(encoding="ascii"))
    body = dict(document)
    expected = str(body.pop("phase9_s3_final_resume_readiness_sha256", ""))
    if not expected or sha256_document(body) != expected:
        raise SystemExit("S3Z readiness artifact has a canonical-hash mismatch")
    try:
        validate(document)
    except RuntimeError as error:
        raise SystemExit(str(error)) from error
    print("S3Z_SCIENTIFIC_PREFLIGHT_PASS_AUTHORIZATION_STILL_REQUIRED")


if __name__ == "__main__":
    main()
