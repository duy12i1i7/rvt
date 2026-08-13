#!/usr/bin/env python3
"""Bind the minimal executable A1S3Z repair without rewriting prior contracts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from rvt_swarm.phase8.common import attach_canonical_hash


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    results = root / "results/rvt_fd24"
    addendum = json.loads((
        results / "phase9_s3_exact_centerline_scientific_addendum_v1.json"
    ).read_text(encoding="ascii"))
    runtime_files = {
        "rvt_swarm/decentralized/system_model.py": {
            "before_sha256": "d62c0983234f26d6e73db1377e069a751310cc7950e1b5102b683a9c20d41607",
            "after_sha256": _sha(root / "rvt_swarm/decentralized/system_model.py"),
            "change": "two optional S3 local-frame fields on RobotView",
        },
        "rvt_swarm/phase9c_rb/session.py": {
            "before_sha256": "9a88932f69f6cba6eddd698af6a60840e12ed416e25c9eaad1b4286e31d2c342",
            "after_sha256": _sha(root / "rvt_swarm/phase9c_rb/session.py"),
            "change": "populate the frame only for S3 and S4 S3-evidence consumers",
        },
        "rvt_swarm/phase9c_rb/policies.py": {
            "before_sha256": "d0c8392b4a1f9ba842465b55a157d265ca1f4f034b652608b19a829e01a96451",
            "after_sha256": _sha(root / "rvt_swarm/phase9c_rb/policies.py"),
            "change": "replace same-side estimator with owner-qualified pairing",
        },
        "rvt_swarm/phase9c_rb/world.py": {
            "before_sha256": "7dfd0127cc25a253caf7dc6b333bea26b1312c5a66343231dbace72133e54645",
            "after_sha256": _sha(root / "rvt_swarm/phase9c_rb/world.py"),
            "change": "expose only the qualified local reference frame",
        },
        "rvt_swarm/phase9c_rb/s3_geometry.py": {
            "before_sha256": None,
            "after_sha256": _sha(root / "rvt_swarm/phase9c_rb/s3_geometry.py"),
            "change": "new pure opposing-boundary and exact-zero implementation",
        },
    }
    document = {
        "schema_version": "rvt-phase9-s3-centerline-execution-contract/v1",
        "phase": "PHASE_9G_A1S3Z",
        "binding": "ADDITIVE",
        "scientific_addendum_sha256": addendum[
            "phase9_s3_exact_centerline_scientific_addendum_sha256"],
        "prior_opposing_boundary_addendum_sha256": (
            "a5e7fa9ce92ba7fb449a76406da47cc00dd4a39ddee2e108a62a969589b5f6d3"
        ),
        "addendum_commit": "295722307412a85cba5506fb2abc62dcf23a99f3",
        "initial_repair_commit": "74de65a81f3aa897be326e57de29297f5cc237e4",
        "qualified_repair_commit": "20bfa1bfdc311f67075327418595441b101bc8de",
        "runtime_files": runtime_files,
        "pipeline": [
            "range-gated ego-relative support tokens",
            "qualified compiled local reference frame c,t,n",
            "exact binary64 signed free-surface coordinate",
            "CENTERLINE_NEUTRAL exclusion from boundary extrema",
            "nearest strict NEG/POS opposing-boundary pair",
            "existing HOLD_UNKNOWN disposition when a side is missing",
        ],
        "exact_arithmetic_order": (
            "dot((robot_position + support_offset) - c_world, n)"
        ),
        "numerical_epsilon": None,
        "consumer_boundary": {
            "frame_populated_for": [
                "S3_FROZEN_LOCAL_GEOMETRIC_SELECTOR",
                "S4_FROZEN_TRANSITION_PROTOCOL",
            ],
            "frame_absent_for_other_source_policies": True,
            "residual_expert_canonical_view_hash_includes_new_fields": False,
            "ego_graph_schema_changed": False,
            "controller_input_schema_changed": False,
        },
        "unchanged_components": {
            "collision_geometry": True,
            "controller": True,
            "local_safety_projection": True,
            "transition_protocol": True,
            "target_v4": True,
            "matched_randomness": True,
            "row_identity_contract": True,
            "residual_expert": True,
            "model": True,
        },
        "image_lineage": {
            "qualified_parent_image": (
                "sha256:88ecf1aac7cd95b5ba50811950090c13f78362274e5c5cdaeafaafde29a115f4"
            ),
            "rejected_candidate_image": (
                "sha256:88f4d7d833ec7166d3b946b31cae5fa8b6499e06e38370b9cb9f83bfacd29810"
            ),
            "rejected_reason": "S4 delegated S3 evidence without receiving its frame",
            "qualified_candidate_image": (
                "sha256:c2f8734403f6422c10e04531529458e7826c175cbec0933c5b7d936cebedf39f"
            ),
        },
        "official_operations": {
            "generation_resumed": False,
            "staging_writes": 0,
            "validation_started": False,
            "residual_started": False,
            "training_operations": 0,
        },
    }
    document = attach_canonical_hash(
        document, "phase9_s3_centerline_execution_contract_sha256")
    output = results / "phase9_s3_centerline_execution_contract_v1.json"
    output.write_text(
        json.dumps(document, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )
    print(document["phase9_s3_centerline_execution_contract_sha256"])


if __name__ == "__main__":
    main()
