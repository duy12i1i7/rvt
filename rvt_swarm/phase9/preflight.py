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


RESIDUAL_V2_REQUIRED_CONTRACTS = {
    "residual_runtime_composite": (
        "results/rvt_fd24/residual_runtime_composite_v1.json",
        "residual_runtime_composite_sha256"),
    "rb17_generation_contract_composite": (
        "results/rvt_fd24/rb17_generation_contract_composite_v1.json",
        "rb17_generation_contract_composite_sha256"),
    "scientific_row_identity": (
        "results/rvt_fd24/residual_scientific_row_identity_v2.json",
        "residual_scientific_row_identity_v2_sha256"),
    "candidate_evaluation_identity": (
        "results/rvt_fd24/residual_candidate_evaluation_identity_v2.json",
        "residual_candidate_evaluation_identity_v2_sha256"),
    "execution_attempt_identity": (
        "results/rvt_fd24/residual_execution_attempt_identity_v1.json",
        "residual_execution_attempt_identity_v1_sha256"),
    "disposition_contract": (
        "results/rvt_fd24/residual_generation_disposition_contract_v1.json",
        "residual_generation_disposition_contract_v1_sha256"),
    "supervision_row_schema": (
        "results/rvt_fd24/residual_supervision_row_schema_v2.json",
        "residual_supervision_row_schema_v2_sha256"),
    "generation_budget_v2": (
        "results/rvt_fd24/generation_budget_v2.json", "generation_budget_v2_sha256"),
    "residual_job_manifest_v2": (
        "results/rvt_fd24/residual_job_manifest_v2.json",
        "residual_job_manifest_v2_sha256"),
}


def residual_v2_contract_checks(root: Path) -> list:
    """RB17-26 -- validate the versioned Residual V2 contracts.

    Parsing them is not authorization. These checks exist to *reject* stale or
    incompatible contracts: a historical mission-frame model declaration
    presented as current, a supervision schema that drops the orientation
    context, a WORLD/model frame mismatch, the superseded residual job identity,
    the historical 1800-second timeout presented as authoritative for V2, a
    candidate count other than nine, synthetic augmentation, or a disposition
    vocabulary the generator does not implement.
    """
    from ..fd24.configuration import ROBOT_LOCAL_ACTION_COMPONENTS
    from ..fd24.model import FD24_MODEL_INPUT_SCHEMA_VERSION, FD24_MODEL_SCHEMA_VERSION
    from ..phase9c_rb.generation_contract import (
        DISPOSITIONS, EMITS_TARGET_ROW, NO_ELIGIBLE_ACTION, SCIENTIFIC_ROW_KEY,
    )

    checks: list = []
    documents: Dict[str, Dict[str, object]] = {}
    for name, (relative, hash_field) in RESIDUAL_V2_REQUIRED_CONTRACTS.items():
        path = root / relative
        if not path.exists():
            checks.append(_check(f"residual_v2_contract_present:{name}", False,
                                 relative, "missing"))
            continue
        document = json.loads(path.read_text(encoding="ascii"))
        documents[name] = document
        checks.append(_check(f"residual_v2_contract_hash:{name}",
                             verify_canonical_hash(document, hash_field),
                             True, verify_canonical_hash(document, hash_field)))
    if len(documents) != len(RESIDUAL_V2_REQUIRED_CONTRACTS):
        return checks

    row_schema = documents["supervision_row_schema"]
    budget = documents["generation_budget_v2"]
    manifest = documents["residual_job_manifest_v2"]
    disposition = documents["disposition_contract"]
    row_identity = documents["scientific_row_identity"]

    # the model must not be presented under its historical mission declaration
    pins = row_schema["model_schema_pins"]
    checks.append(_check(
        "residual_v2_model_frame_is_world",
        pins["model_schema_version"] == FD24_MODEL_SCHEMA_VERSION
        and pins["model_input_schema_version"] == FD24_MODEL_INPUT_SCHEMA_VERSION
        and tuple(pins["output_components"]) == ROBOT_LOCAL_ACTION_COMPONENTS
        and not any("mission" in name for name in pins["output_components"]),
        {"model_schema_version": FD24_MODEL_SCHEMA_VERSION,
         "output_components": list(ROBOT_LOCAL_ACTION_COMPONENTS)},
        pins))

    # the orientation context must survive serialization
    added = row_schema["added_fields"]
    checks.append(_check(
        "residual_v2_orientation_context_present",
        "mission_orientation_cos_sin" in added
        and added["mission_orientation_cos_sin"]["shape"] == [2]
        and added["mission_orientation_cos_sin"][
            "recomputed_from_layout_ids_at_training_time"] is False
        and row_schema["model_input_reconstruction"]["all_preserved"] is True,
        "mission_orientation_cos_sin[2] preserved", sorted(added)))

    # the target must stay WORLD on both sides
    target = row_schema["target_field"]
    checks.append(_check(
        "residual_v2_target_frame_world",
        target["frame"] == "WORLD" and target["shape"] == [2]
        and target["units"] == "meters_per_second_squared"
        and not any(target["round_trip"].values()),
        {"frame": "WORLD", "shape": [2]}, target))

    # the superseded residual job identity must not be current
    checks.append(_check(
        "residual_v2_row_identity_excludes_candidate_index",
        row_identity["candidate_index_in_identity"] is False
        and "candidate_index" not in SCIENTIFIC_ROW_KEY
        and tuple(row_identity["key_fields"]) == SCIENTIFIC_ROW_KEY,
        list(SCIENTIFIC_ROW_KEY), row_identity["key_fields"]))

    # the historical timeout must not be presented as authoritative for V2
    timeout = budget["timeout"]
    checks.append(_check(
        "residual_v2_timeout_not_stale",
        timeout["historical_value_authoritative_for_v2"] is False
        and timeout["RESIDUAL_V2_GENERATION_TIMEOUT"]
        == "PENDING_RB21_PERFORMANCE_QUALIFICATION"
        and timeout["replacement_chosen_in_rb17"] is False,
        "PENDING_RB21_PERFORMANCE_QUALIFICATION", timeout))

    additions = budget["residual_v2_additions"]
    checks.append(_check(
        "residual_v2_candidate_count",
        additions["residual_candidate_count"] == 9
        and additions["stored_residual_supervision_upper_cap"] == 536000
        and additions["candidate_evaluation_compute_upper_bound"] == 536000 * 9,
        {"candidates": 9, "rows": 536000, "evaluations": 4824000}, additions))

    checks.append(_check(
        "residual_v2_no_synthetic_augmentation",
        json.loads((root / "results/rvt_fd24/rb16_world_output_requalification_v1.json")
                   .read_text(encoding="ascii"))["augmentation"][
            "PRIMARY_SYNTHETIC_ROTATION_AUGMENTATION"] == "DISABLED",
        "DISABLED", "checked"))

    checks.append(_check(
        "residual_v2_disposition_vocabulary",
        tuple(disposition["dispositions"]) == DISPOSITIONS
        and disposition["emits_target_row"] == dict(EMITS_TARGET_ROW)
        and disposition["no_eligible_action"]["target_rows"] == 0
        and disposition["no_eligible_action"]["counts_in_denominator"] is True
        and EMITS_TARGET_ROW[NO_ELIGIBLE_ACTION] is False,
        list(DISPOSITIONS), disposition["dispositions"]))

    checks.append(_check(
        "residual_v2_generation_not_authorized",
        budget["generation_authorized"] is False
        and manifest["official_scientific_execution_status"]
        == "NOT_AUTHORIZED_PENDING_RB18_RB21"
        and manifest["official_job_records_emitted"] == 0,
        "NOT_AUTHORIZED_PENDING_RB18_RB21",
        manifest["official_scientific_execution_status"]))

    return checks


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

    checks.extend(residual_v2_contract_checks(root))

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
