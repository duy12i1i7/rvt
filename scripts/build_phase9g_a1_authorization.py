#!/usr/bin/env python3
"""Freeze the additive, owner-scoped Phase 9G-A1 authorization event."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

from rvt_swarm.phase8.common import attach_canonical_hash, sha256_document


CLOSURE_COMMIT = "6bcfc0e26c4b327ba63f2844eaa02d30d56903ba"
SCIENTIFIC_SOURCE_COMMIT = "8cf64481cd17b2c44f7007d3722a8110e53cae46"
PRODUCTION_IMAGE = (
    "sha256:88ecf1aac7cd95b5ba50811950090c13f78362274e5c5cdaeafaafde29a115f4"
)
STUDY = "study_a_zero_shot"
SPLITS = ("train", "validation")
BRANCHES = ("recoverability", "residual")

ROOT_BINDINGS = {
    "generation_readiness": (
        "phase9_production_performance_readiness_v1.json",
        "phase9_production_performance_readiness_sha256",
    ),
    "operational_production_contract": (
        "phase9g0p_operational_production_contract_v2.json",
        "phase9g0p_operational_contract_sha256",
    ),
    "official_command_plan": (
        "phase9_official_command_plan_v2_operational_addendum_v1.json",
        "phase9g0p_command_plan_operational_addendum_sha256",
    ),
    "generation_provenance": (
        "phase9_current_generation_provenance_v2.json",
        "phase9_current_generation_provenance_sha256",
    ),
    "predata_scientific_addendum": (
        "phase9_predata_generation_scientific_addendum_v1.json",
        "phase9_predata_generation_scientific_addendum_sha256",
    ),
    "recoverability_row_identity": (
        "phase9_recoverability_row_identity_v1.json",
        "phase9_recoverability_row_identity_sha256",
    ),
    "recoverability_row_binding": (
        "phase9_recoverability_row_binding_v1.json",
        "phase9_recoverability_row_binding_sha256",
    ),
    "matched_randomness": (
        "phase9_matched_randomness_binding_v1.json",
        "phase9_matched_randomness_binding_sha256",
    ),
    "candidate_pair_transaction": (
        "phase9_recoverability_candidate_pair_transaction_v1.json",
        "phase9_recoverability_candidate_pair_transaction_sha256",
    ),
    "residual_dense_state_retention": (
        "phase9_residual_dense_state_retention_v1.json",
        "phase9_residual_dense_state_retention_sha256",
    ),
    "phase9g_a1_prestart": (
        "phase9g_a1_prestart_v1.json",
        "phase9g_a1_prestart_sha256",
    ),
}


class AuthorizationBuildError(RuntimeError):
    """A frozen input cannot support the requested authorization event."""


def _canonical_hash(path: Path, field: str) -> str:
    document = json.loads(path.read_text(encoding="ascii"))
    body = dict(document)
    expected = str(body.pop(field, ""))
    if len(expected) != 64 or sha256_document(body) != expected:
        raise AuthorizationBuildError(f"canonical input mismatch: {path.name}")
    return expected


def _write(path: Path, document: Mapping[str, Any], hash_field: str) -> str:
    canonical = attach_canonical_hash(dict(document), hash_field)
    path.write_text(
        json.dumps(canonical, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )
    return str(canonical[hash_field])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--timestamp-utc", required=True)
    parser.add_argument("--authorization-source-sha256", required=True)
    args = parser.parse_args()

    root = args.root.resolve()
    result_root = root / "results/rvt_fd24"
    if len(args.authorization_source_sha256) != 64:
        raise AuthorizationBuildError("authorization source digest must be SHA-256")
    bindings = {
        key: {
            "artifact": artifact,
            "sha256": _canonical_hash(result_root / artifact, field),
        }
        for key, (artifact, field) in ROOT_BINDINGS.items()
    }
    if json.loads(
        (result_root / ROOT_BINDINGS["phase9g_a1_prestart"][0]).read_text(
            encoding="ascii"
        )
    ).get("status") != "PASS":
        raise AuthorizationBuildError("Phase 9G-A1 pre-start did not pass")

    scopes = []
    for split in SPLITS:
        for branch in BRANCHES:
            command_id = f"{STUDY}-{split}-{branch}"
            filename = f"phase9g_a1_authorization_scope_{command_id}_v1.json"
            scope = {
                "schema_version": "rvt-phase9g-a1-authorization-scope/v1",
                "phase": "PHASE_9G_A1",
                "owner_authorization_timestamp_utc": args.timestamp_utc,
                "authorization_class": "AUTHORIZED_STUDY_A_TRAIN_VALIDATION_ONLY",
                "broad_authorization": False,
                "official_generation_execution_authorized": True,
                "binding": {
                    "study": STUDY,
                    "split": split,
                    "branch": branch,
                    "source_commit": SCIENTIFIC_SOURCE_COMMIT,
                    "docker_image": PRODUCTION_IMAGE,
                    "scientific_addendum_sha256": bindings[
                        "predata_scientific_addendum"
                    ]["sha256"],
                    "generation_provenance_root": bindings[
                        "generation_provenance"
                    ]["sha256"],
                },
                "sealed_exclusions": [
                    "study_a_n24_zero_shot",
                    "study_b",
                    "final_test",
                    "training",
                ],
                "scientific_outcomes_present": False,
            }
            digest = _write(
                result_root / filename, scope, "phase9_authorization_scope_sha256"
            )
            scopes.append({
                "command_id": command_id,
                "study": STUDY,
                "split": split,
                "branch": branch,
                "artifact": filename,
                "sha256": digest,
            })

    event = {
        "schema_version": "rvt-phase9g-a1-owner-authorization/v1",
        "phase": "PHASE_9G_A1",
        "owner_authorization_timestamp_utc": args.timestamp_utc,
        "authorization_source": {
            "kind": "EXPLICIT_OWNER_INSTRUCTION",
            "sha256": args.authorization_source_sha256,
        },
        "source_evidence_commit": CLOSURE_COMMIT,
        "scientific_source_commit": SCIENTIFIC_SOURCE_COMMIT,
        "production_image": PRODUCTION_IMAGE,
        "frozen_bindings": bindings,
        "authorized_scope_artifacts": scopes,
        "enabled_scope_count": len(scopes),
        "broad_authorization": False,
        "scope_status": {
            "RECOVERABILITY_GENERATION": (
                "AUTHORIZED_STUDY_A_TRAIN_VALIDATION_ONLY"
            ),
            "RESIDUAL_V2_GENERATION": (
                "AUTHORIZED_STUDY_A_TRAIN_VALIDATION_ONLY"
            ),
            "STUDY_A_TRAIN_VALIDATION": "AUTHORIZED",
            "STUDY_A_N24_ZERO_SHOT": "SEALED_NOT_AUTHORIZED",
            "STUDY_B": "NOT_AUTHORIZED",
            "FINAL_TEST": "SEALED_NOT_AUTHORIZED",
            "TRAINING": "NOT_AUTHORIZED",
        },
        "required_branch_order": ["recoverability", "residual"],
        "residual_start_gate": (
            "recoverability completed, reconciled, finalized, with zero unresolved "
            "failures and zero seal violations"
        ),
        "scientific_outcomes_present": False,
    }
    event_path = result_root / "phase9g_a1_owner_authorization_v1.json"
    event_sha256 = _write(
        event_path, event, "phase9g_a1_owner_authorization_sha256"
    )
    print(json.dumps({
        "authorization_event": event_path.name,
        "authorization_sha256": event_sha256,
        "enabled_scope_count": len(scopes),
        "scope_sha256": {item["command_id"]: item["sha256"] for item in scopes},
    }, sort_keys=True))


if __name__ == "__main__":
    main()
