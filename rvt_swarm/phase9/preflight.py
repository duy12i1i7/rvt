"""Read-only verification of the approved Phase 8 protocol boundary."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Dict, Iterable

from ..decentralized.ego_graph_v2 import (
    EGO_GRAPH_FEATURE_SCHEMA_SHA256,
    EGO_GRAPH_SCHEMA_VERSION,
)
from ..fd24.configuration import FD24ModelConfig, canonical_model_config_hash
from ..fd24.model import FD24_MODEL_SCHEMA_VERSION
from ..runtime_configuration import RuntimeConfig, canonical_runtime_hash
from ..topology_registry import COMPACT, LINE
from ..phase8.common import file_sha256, sha256_document, verify_canonical_hash
from ..phase8.manifest import REQUIRED_HASHED_DOCUMENTS
from ..phase8.seeds import (
    SEED_DERIVATION_VERSION,
    SEED_NAMESPACE_SCHEMA_VERSION,
    SEED_NAMESPACES,
)
from ..phase8.splits import load_nonfinal_split_manifest
from .common import (
    EXPERIMENT_PROTOCOL_SHA256,
    FINAL_TEST_SPLIT_COMMITMENT_SHA256,
    ONLINE_SCOPE_SHA256,
    PHASE8_SOURCE_COMMIT,
    PHASE9_PREFLIGHT_SCHEMA_VERSION,
    TRAIN_SPLIT_SHA256,
    VALIDATION_SPLIT_SHA256,
)


def _model_frame_erratum(root: Path) -> Dict[str, str] | None:
    """The RB16R model-frame erratum, if one has been recorded.

    The frozen Phase-9 protocol records the historical `rvt-fd24-model/v1`
    declaration. RB16R repaired the residual output frame to WORLD, which
    necessarily moves the model schema version. The supersession is data, not a
    hardcoded string: preflight admits the new version only because an erratum
    artifact says so, and the frozen protocol is never rewritten.
    """
    path = root / "results/rvt_fd24/model_residual_output_frame_v2.json"
    if not path.exists():
        return None
    erratum = json.loads(path.read_text(encoding="ascii"))
    return {
        "artifact": "results/rvt_fd24/model_residual_output_frame_v2.json",
        "historical_schema_version":
            erratum["historical_declaration"]["model_schema_version"],
        "current_schema_version": erratum["current_declaration"]["model_schema_version"],
        "sha256": erratum["model_residual_output_frame_v2_sha256"],
    }


def _model_schema_admitted(root: Path, recorded: str) -> bool:
    if recorded == FD24_MODEL_SCHEMA_VERSION:
        return True
    erratum = _model_frame_erratum(root)
    return bool(
        erratum
        and recorded == erratum["historical_schema_version"]
        and FD24_MODEL_SCHEMA_VERSION == erratum["current_schema_version"]
    )


def _check(name: str, passed: bool, expected: object, observed: object) -> Dict[str, object]:
    return {
        "name": name,
        "passed": bool(passed),
        "expected": expected,
        "observed": observed,
    }


def _audit_runtime_access(path: Path) -> Dict[str, object]:
    entries = []
    if path.exists():
        for line in path.read_text(encoding="ascii").splitlines():
            if line.strip():
                entries.append(json.loads(line))
    admitted = sum(bool(item.get("admitted")) for item in entries)
    reported = max(
        (int(item.get("successful_runtime_access_count", 0)) for item in entries),
        default=0,
    )
    return {
        "audit_entry_count": len(entries),
        "admitted_entry_count": admitted,
        "successful_runtime_access_count": reported,
    }


def _all_pass(checks: Iterable[Dict[str, object]]) -> bool:
    return all(bool(item["passed"]) for item in checks)


def build_preflight_audit(root: Path) -> Dict[str, object]:
    """Verify Phase 8 without opening the sealed final-test split manifest."""
    protocol_path = root / "results/rvt_fd24/experiment_protocol_manifest.json"
    protocol = json.loads(protocol_path.read_text(encoding="ascii"))
    train = load_nonfinal_split_manifest(
        root / "results/rvt_fd24/splits/train_layouts.json"
    )
    validation = load_nonfinal_split_manifest(
        root / "results/rvt_fd24/splits/validation_layouts.json"
    )
    online_scope = json.loads(
        (root / "results/rvt_fd24/online_topology_scope.json").read_text(
            encoding="ascii"
        )
    )

    checks = [
        _check(
            "protocol_canonical_hash",
            verify_canonical_hash(protocol, "experiment_protocol_sha256"),
            True,
            verify_canonical_hash(protocol, "experiment_protocol_sha256"),
        ),
        _check(
            "protocol_identity",
            protocol.get("experiment_protocol_sha256") == EXPERIMENT_PROTOCOL_SHA256,
            EXPERIMENT_PROTOCOL_SHA256,
            protocol.get("experiment_protocol_sha256"),
        ),
        _check(
            "protocol_schema",
            protocol.get("schema_version") == "rvt-experiment-protocol/v1",
            "rvt-experiment-protocol/v1",
            protocol.get("schema_version"),
        ),
        _check(
            "online_scope",
            online_scope.get("scope_sha256") == ONLINE_SCOPE_SHA256
            and protocol["online_topology_scope"]["sha256"] == ONLINE_SCOPE_SHA256
            and online_scope.get("active_candidate_topology_ids") == [COMPACT, LINE],
            {"sha256": ONLINE_SCOPE_SHA256, "candidates": [COMPACT, LINE]},
            {
                "sha256": online_scope.get("scope_sha256"),
                "candidates": online_scope.get("active_candidate_topology_ids"),
            },
        ),
        _check(
            "train_split",
            train.get("manifest_sha256") == TRAIN_SPLIT_SHA256,
            TRAIN_SPLIT_SHA256,
            train.get("manifest_sha256"),
        ),
        _check(
            "validation_split",
            validation.get("manifest_sha256") == VALIDATION_SPLIT_SHA256,
            VALIDATION_SPLIT_SHA256,
            validation.get("manifest_sha256"),
        ),
        _check(
            "sealed_final_test_commitment",
            protocol["split_manifest_sha256"]["final_test"]
            == FINAL_TEST_SPLIT_COMMITMENT_SHA256,
            FINAL_TEST_SPLIT_COMMITMENT_SHA256,
            protocol["split_manifest_sha256"]["final_test"],
        ),
        _check(
            "ego_graph_schema",
            protocol["ego_graph"]
            == {
                "schema_version": EGO_GRAPH_SCHEMA_VERSION,
                "feature_schema_sha256": EGO_GRAPH_FEATURE_SCHEMA_SHA256,
            },
            {
                "schema_version": EGO_GRAPH_SCHEMA_VERSION,
                "feature_schema_sha256": EGO_GRAPH_FEATURE_SCHEMA_SHA256,
            },
            protocol["ego_graph"],
        ),
        _check(
            "model_schema",
            _model_schema_admitted(root, protocol["model"]["schema_version"])
            and protocol["model"]["config_sha256"]
            == canonical_model_config_hash(FD24ModelConfig()),
            protocol["model"],
            {
                "schema_version": FD24_MODEL_SCHEMA_VERSION,
                "config_sha256": canonical_model_config_hash(FD24ModelConfig()),
                "superseded_by": _model_frame_erratum(root),
            },
        ),
    ]

    runtime_hashes = {
        str(size): canonical_runtime_hash(RuntimeConfig.for_team_size(size))
        for size in (5, 6, 8, 12, 16, 24)
    }
    checks.append(_check(
        "runtime_controller_safety_protocol_configuration",
        runtime_hashes == protocol["runtime_configuration_sha256_by_team_size"],
        protocol["runtime_configuration_sha256_by_team_size"],
        runtime_hashes,
    ))

    seed_document = {
        "schema_version": SEED_NAMESPACE_SCHEMA_VERSION,
        "derivation_version": SEED_DERIVATION_VERSION,
        "namespaces": [asdict(item) for item in SEED_NAMESPACES],
    }
    checks.append(_check(
        "seed_namespaces",
        sha256_document(seed_document)
        == protocol["structured_contract_sha256"]["seeds"],
        protocol["structured_contract_sha256"]["seeds"],
        sha256_document(seed_document),
    ))

    for name, relative_path in REQUIRED_HASHED_DOCUMENTS.items():
        expected = protocol["hashed_protocol_documents"][name]["sha256"]
        observed = file_sha256(root / relative_path)
        checks.append(_check(f"frozen_document:{name}", observed == expected, expected, observed))

    final_access = _audit_runtime_access(
        root / "results/rvt_fd24/final_test_access_audit.jsonl"
    )
    checks.append(_check(
        "final_test_runtime_access",
        final_access["admitted_entry_count"] == 0
        and final_access["successful_runtime_access_count"] == 0,
        {"admitted_entry_count": 0, "successful_runtime_access_count": 0},
        final_access,
    ))

    return {
        "schema_version": PHASE9_PREFLIGHT_SCHEMA_VERSION,
        "status": "PASS" if _all_pass(checks) else "FAIL",
        "approved_phase8_source_commit": PHASE8_SOURCE_COMMIT,
        "experiment_protocol_sha256": EXPERIMENT_PROTOCOL_SHA256,
        "checks": checks,
        "final_test_geometry_loaded": False,
        "final_test_access": final_access,
        "note": (
            "The final-test split hash is checked only as an approved commitment "
            "stored in the Phase 8 protocol manifest; sealed geometry is not opened."
        ),
    }
