#!/usr/bin/env python3
"""Build the held Phase 9G0-R generator, provenance, and command artifacts."""

from __future__ import annotations

import json
import shlex
from pathlib import Path
from typing import Any, Mapping

from rvt_swarm.phase8.common import attach_canonical_hash, sha256_document
from rvt_swarm.phase9g0r.compiler import (
    JOB_MANIFEST_SHA256,
    compile_recoverability_tasks,
    compile_residual_tasks,
)


EXECUTABLE_SOURCE_COMMIT = "8cf64481cd17b2c44f7007d3722a8110e53cae46"
EVIDENCE_SOURCE_COMMIT = "44b9c73efc719f07c243d07f090dd096014d68ed"
BASE_IMAGE = "sha256:30e6dea61d67eb255e814996cf737140a3b47eac62fb74ecf303df58e280138b"
EXECUTION_IMAGE = "sha256:5e13c21aaa20f2ac02eff36172aea467720b9c925d13882708e3e90686655d9c"
ADDENDUM_SHA256 = "523d865cf04b7a5bd2a9cec8cb9a105fd5ef1f1476f6acec34e8cd47cf0dcad0"

STUDY_SPLITS = (
    ("study_a_zero_shot", "train"),
    ("study_a_zero_shot", "validation"),
    ("study_b_with_n24", "train"),
    ("study_b_with_n24", "validation"),
)
BRANCHES = ("recoverability", "residual")


def _load_hash(results: Path, name: str, hash_field: str) -> str:
    document = json.loads((results / name).read_text(encoding="ascii"))
    expected = str(document.pop(hash_field))
    if sha256_document(document) != expected:
        raise ValueError(f"canonical artifact hash mismatch: {name}")
    return expected


def _write(
    results: Path, name: str, body: Mapping[str, Any], hash_field: str,
) -> str:
    document = attach_canonical_hash(dict(body), hash_field)
    (results / name).write_text(
        json.dumps(document, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )
    return str(document[hash_field])


def _authorities(results: Path) -> Mapping[str, str]:
    specifications = {
        "scientific_addendum": (
            "phase9_predata_generation_scientific_addendum_v1.json",
            "phase9_predata_generation_scientific_addendum_sha256",
        ),
        "recoverability_row_identity": (
            "phase9_recoverability_row_identity_v1.json",
            "phase9_recoverability_row_identity_sha256",
        ),
        "recoverability_ego_payload": (
            "phase9_recoverability_ego_payload_binding_v1.json",
            "phase9_recoverability_ego_payload_binding_sha256",
        ),
        "recoverability_row_binding": (
            "phase9_recoverability_row_binding_v1.json",
            "phase9_recoverability_row_binding_sha256",
        ),
        "official_rollout_configuration": (
            "phase9_official_rollout_configuration_v1.json",
            "phase9_official_rollout_configuration_sha256",
        ),
        "lifecycle_configuration": (
            "phase9_lifecycle_config_hash_v1.json",
            "phase9_lifecycle_config_hash_sha256",
        ),
        "communication_configuration": (
            "phase9_communication_config_hash_v1.json",
            "phase9_communication_config_hash_sha256",
        ),
        "candidate_pair_transaction": (
            "phase9_recoverability_candidate_pair_transaction_v1.json",
            "phase9_recoverability_candidate_pair_transaction_sha256",
        ),
        "residual_dense_retention": (
            "phase9_residual_dense_state_retention_v1.json",
            "phase9_residual_dense_state_retention_sha256",
        ),
        "count_reconciliation": (
            "phase9g0r_count_reconciliation_v1.json",
            "phase9g0r_count_reconciliation_sha256",
        ),
        "matched_randomness_regression": (
            "phase9g0r_matched_randomness_regression_v1.json",
            "phase9g0r_matched_randomness_regression_sha256",
        ),
        "structural_canary": (
            "phase9g0r_structural_canary_v1.json",
            "phase9g0r_structural_canary_sha256",
        ),
        "rb20_official_path_replay": (
            "phase9g0r_rb20_official_path_replay_v1.json",
            "phase9g0r_rb20_official_path_replay_sha256",
        ),
        "negative_preflight": (
            "phase9g0r_preflight_v1.json",
            "phase9g0r_preflight_sha256",
        ),
        "performance_classification": (
            "phase9g0r_performance_classification_v1.json",
            "phase9g0r_performance_classification_sha256",
        ),
    }
    return {
        key: _load_hash(results, *value)
        for key, value in specifications.items()
    }


def build(root: Path) -> None:
    results = root / "results/rvt_fd24"
    authorities = _authorities(results)
    if authorities["scientific_addendum"] != ADDENDUM_SHA256:
        raise ValueError("scientific addendum authority changed")

    generator = {
        "schema_version": "rvt-phase9-official-generator-contract/v2",
        "status": "EXECUTABLE_PREPARED_OFFICIAL_EXECUTION_HELD",
        "provenance_class": "OFFICIAL_SCIENTIFIC_PRODUCER",
        "executable_source_commit": EXECUTABLE_SOURCE_COMMIT,
        "container": {
            "qualified_base_image": BASE_IMAGE,
            "superseding_execution_image": EXECUTION_IMAGE,
            "construction": "FROM qualified base plus committed executable source",
            "scientific_execution_device": "CPU",
        },
        "authorities": dict(authorities),
        "task_compiler": {
            "module": "rvt_swarm.phase9g0r.compiler",
            "job_manifest_sha256": JOB_MANIFEST_SHA256,
            "families": [f"F{index}" for index in range(1, 11)],
            "authorized_study_splits": [list(item) for item in STUDY_SPLITS],
            "study_a_n24": "REJECT_ONLY_SEALED",
            "final_test": "REJECT_ONLY_SEALED",
            "scheduling_fields_in_scientific_task_identity": [],
        },
        "recoverability": {
            "entry_point": "rvt_swarm.phase9g0r.producer.produce_recoverability_event",
            "candidates": ["COMPACT", "LINE"],
            "replica_rule": "F8/F9=3; all other families=1",
            "aggregation": "all_success",
            "publication_unit": "one reconciled 2*N event transaction",
            "generation_invalid_rows": 0,
        },
        "residual": {
            "entry_point": "rvt_swarm.phase9g0r.producer.produce_residual_state",
            "dense_universe": "all valid active robot-local decision instants",
            "retention": "K=16 deterministic rational temporal positions per episode and robot",
            "candidate_count": 9,
            "dispositions": ["LABELED", "NO_ELIGIBLE_ACTION"],
        },
        "writer": {
            "entry_point": "rvt_swarm.phase9g0r.writer.CanonicalGenerationWriter",
            "modes": ["DIAGNOSTIC", "OFFICIAL_STAGING"],
            "direct_final_writer": False,
            "atomic_scientific_units": True,
        },
        "retry": {
            "infrastructure_retries": 1,
            "semantic_retries": 0,
            "scientific_identity_changes_on_retry": False,
        },
        "cli": "scripts/run_phase9_official_generation.py",
        "official_generation_executed": False,
    }
    generator_hash = _write(
        results,
        "phase9_official_generator_contract_v2.json",
        generator,
        "phase9_official_generator_contract_sha256",
    )

    provenance = {
        "schema_version": "rvt-phase9-current-generation-provenance/v2",
        "additive": True,
        "parents": {
            "rb19": "e8317ad3e9facc76511098503cdad55dfc065dedd8fc2b530a2b25845c3f5571",
            "rb20": "8c55f4ef40be509dc6e0bc678467873e5ebd0ce60d0195a2227555676114b95a",
            "rb21p": "fcc218e4bc88546240789043aa9e160d1fa39b82701637ebd6af19f2f8dcc176",
            "phase9g0": "bab7d1f1238aa61648d57b3c9930ac8974f1aba2c30977d33c19785a16b2fd74",
        },
        "scientific_addendum_sha256": ADDENDUM_SHA256,
        "official_generator_contract_sha256": generator_hash,
        "scientific_authorities": dict(authorities),
        "job_manifest_sha256": JOB_MANIFEST_SHA256,
        "target_v4_sha256": "54a0e0baff79fbdc320800b772f47a40ac06ac4f0e70d4fab1bf676c54b918ee",
        "executable_source_commit": EXECUTABLE_SOURCE_COMMIT,
        "diagnostic_evidence_commit": EVIDENCE_SOURCE_COMMIT,
        "qualified_base_image": BASE_IMAGE,
        "superseding_execution_image": EXECUTION_IMAGE,
        "predata_isolation": {
            "official_scientific_rows": 0,
            "official_staging_writes": 0,
            "study_a_n24_accesses": 0,
            "final_test_accesses": 0,
        },
    }
    provenance_hash = _write(
        results,
        "phase9_current_generation_provenance_v2.json",
        provenance,
        "phase9_current_generation_provenance_sha256",
    )

    launch_specifications = []
    for study, split in STUDY_SPLITS:
        for branch in BRANCHES:
            command_id = f"{study}-{split}-{branch}"
            scope_name = f"phase9_authorization_scope_{command_id}_v2.json"
            scope_body = {
                "schema_version": "rvt-phase9-authorization-scope/v2",
                "broad_authorization": False,
                "official_generation_execution_authorized": False,
                "binding": {
                    "study": study,
                    "split": split,
                    "branch": branch,
                    "source_commit": EXECUTABLE_SOURCE_COMMIT,
                    "docker_image": EXECUTION_IMAGE,
                    "scientific_addendum_sha256": ADDENDUM_SHA256,
                    "generation_provenance_root": provenance_hash,
                },
                "state": "PREPARED_NOT_AUTHORIZED_DO_NOT_EXECUTE",
            }
            scope_hash = _write(
                results,
                scope_name,
                scope_body,
                "phase9_authorization_scope_sha256",
            )
            task_count = len(
                compile_recoverability_tasks(root, study=study, split=split)
                if branch == "recoverability"
                else compile_residual_tasks(root, study=study, split=split)
            )
            arguments = [
                "python", "/opt/rvt/scripts/run_phase9_official_generation.py",
                "--root", "/opt/rvt",
                "--study", study,
                "--split", split,
                "--branch", branch,
                "--mode", "OFFICIAL_STAGING",
                "--writer-root", f"/rvt-data/staging/{command_id}",
                "--source-commit", EXECUTABLE_SOURCE_COMMIT,
                "--docker-image", EXECUTION_IMAGE,
                "--job-manifest-sha256", JOB_MANIFEST_SHA256,
                "--scientific-addendum-sha256", ADDENDUM_SHA256,
                "--generation-provenance-root", provenance_hash,
                "--authorization-scope-sha256", scope_hash,
                "--authorization-scope", f"/rvt-data/authorization/{scope_name}",
                "--run-id", f"OWNER_MUST_ASSIGN_{command_id}",
            ]
            command = shlex.join(arguments)
            launch_specifications.append({
                "command_id": command_id,
                "study": study,
                "split": split,
                "branch": branch,
                "task_count": task_count,
                "manifest_sha256": JOB_MANIFEST_SHA256,
                "writer_namespace": f"/rvt-data/staging/{command_id}",
                "authorization_scope_artifact": scope_name,
                "authorization_scope_sha256": scope_hash,
                "official_command": command,
                "resolution_command": command + " --resolve-only",
                "execution_authorized": False,
                "executed": False,
            })

    command_plan = {
        "schema_version": "rvt-phase9-official-command-plan/v2",
        "status": "PREPARED_HELD_AUTHORIZATION_FALSE",
        "prepared": True,
        "executed": False,
        "executable_source_commit": EXECUTABLE_SOURCE_COMMIT,
        "docker_image": EXECUTION_IMAGE,
        "qualified_base_image": BASE_IMAGE,
        "scientific_addendum_sha256": ADDENDUM_SHA256,
        "current_generation_provenance_root": provenance_hash,
        "official_generator_contract_sha256": generator_hash,
        "source_job_manifest_sha256": JOB_MANIFEST_SHA256,
        "launch_specifications": launch_specifications,
        "study_a_n24_command": "NOT_CREATED_SEALED",
        "final_test_command": "NOT_CREATED_SEALED",
        "operational_profile": "NOT_SELECTED_PENDING_SCOPED_RB21_REQUALIFICATION",
    }
    command_plan_hash = _write(
        results,
        "phase9_official_command_plan_v2.json",
        command_plan,
        "phase9_official_command_plan_sha256",
    )
    print(json.dumps({
        "generator_contract": generator_hash,
        "provenance_root": provenance_hash,
        "command_plan": command_plan_hash,
        "authorization_scopes": len(launch_specifications),
    }, sort_keys=True))


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    build(args.root.resolve())


if __name__ == "__main__":
    main()
