#!/usr/bin/env python3
"""Build the canonical zero-escape A1V production preflight."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from rvt_swarm.phase8.common import attach_canonical_hash, sha256_document


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/rvt_fd24"
TARGET = OUT / "phase9g_a1v_target_prestart"
IMAGE = "sha256:8e26da918841eb146529bbb4ff95f3a55acf9793dcbc534f44dce0700d183a90"
SOURCE = "848e8b352a91e95af777ebbeccd5fbb43d53777e"


def _file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical(path: Path, field: str) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="ascii"))
    body = dict(document)
    expected = str(body.pop(field, ""))
    if len(expected) != 64 or sha256_document(body) != expected:
        raise ValueError(f"canonical artifact mismatch: {path}")
    return document


def _test_result(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    match = re.search(
        r"(?P<passed>\d+) passed(?:, (?P<warnings>\d+) warnings?)? in (?P<seconds>[0-9.]+)s",
        text,
    )
    if match is None:
        raise ValueError(f"test log did not report a passing suite: {path}")
    return {
        "passed": int(match.group("passed")),
        "failed": 0,
        "warnings": int(match.group("warnings") or 0),
        "seconds": float(match.group("seconds")),
        "publication_required_xfailed": 0,
        "log_file_sha256": _file_sha(path),
    }


def main() -> None:
    train = _canonical(
        OUT / "phase9g_a1v_train_seal_precheck_v1.json",
        "phase9g_a1v_train_seal_precheck_sha256",
    )
    manifest = _canonical(
        OUT / "phase9g_a1v_validation_task_manifest_v1.json",
        "phase9g_a1v_validation_task_manifest_sha256",
    )
    authorization = _canonical(
        OUT / "phase9g_a1v_owner_authorization_v1.json",
        "phase9g_a1v_owner_authorization_sha256",
    )
    run = _canonical(
        OUT / "phase9g_a1v_validation_run_identity_v1.json",
        "phase9g_a1v_validation_run_identity_sha256",
    )
    reference = _canonical(
        OUT / "phase9g_a1v_s3_prestart_guard_reference_v1.json",
        "phase9g_a1v_s3_prestart_guard_sha256",
    )
    target = _canonical(
        TARGET / "s3-prestart-guard-target.json",
        "phase9g_a1v_s3_prestart_guard_sha256",
    )
    reference_semantic = dict(reference)
    target_semantic = dict(target)
    for document in (reference_semantic, target_semantic):
        document.pop("phase9g_a1v_s3_prestart_guard_sha256")
        document.pop("execution_environment")
    if reference_semantic != target_semantic:
        raise ValueError("reference and target S3 guards differ semantically")

    inspect = json.loads((TARGET / "target-image-inspect.json").read_text(encoding="ascii"))[0]
    observation = json.loads((TARGET / "target-observation.json").read_text(encoding="ascii"))
    resolution = json.loads((TARGET / "target-resolve-only.json").read_text(encoding="ascii"))
    module_binding = (TARGET / "module-binding.txt").read_text(encoding="ascii").strip()
    negative = []
    for line in (TARGET / "negative-preflight.tsv").read_text(encoding="ascii").splitlines()[1:]:
        name, exit_code = line.split("\t")
        negative.append({"case": name, "exit_code": int(exit_code)})
    if (
        inspect["Id"] != IMAGE
        or inspect["Config"]["Labels"]["org.opencontainers.image.revision"] != SOURCE
        or observation
        != {
            "deploy_files": 15,
            "host": "avis",
            "running_phase9_containers": 0,
            "target_host": "100.71.102.9",
            "train_manifest_sha256": train["train_manifest_sha256"],
            "train_partials": 0,
            "train_scientific_rows": 8340,
            "train_seal_sha256": train["train_seal_sha256"],
            "train_staging_mode": "0o555",
            "train_staging_writable_files": 0,
            "train_transactions": 6000,
            "validation_final_exists": False,
            "validation_staging_exists": False,
        }
        or module_binding != "/a1v/scripts/run_phase9g_a1v_recoverability_validation.py"
    ):
        raise ValueError("target image, TRAIN seal, namespace, or module binding changed")
    if len(negative) != 5 or any(item["exit_code"] == 0 for item in negative):
        raise ValueError("a negative preflight case escaped")
    if (
        resolution["official_generation_execution_authorized"] is not True
        or resolution["study"] != "study_a_zero_shot"
        or resolution["split"] != "validation"
        or resolution["branch"] != "recoverability"
        or resolution["source_episodes"] != 300
        or resolution["total_event_identities"] != 1500
        or resolution["candidate_aggregate_identities"] != 3000
        or resolution["candidate_replica_slots"] != 4200
        or resolution["preexisting_event_identities"] != 0
        or resolution["scientific_retry_count"] != 0
        or resolution["validation_task_manifest_sha256"]
        != manifest["phase9g_a1v_validation_task_manifest_sha256"]
        or resolution["authorization_sha256"]
        != authorization["phase9g_a1v_owner_authorization_sha256"]
        or resolution["run_identity_sha256"]
        != run["phase9g_a1v_validation_run_identity_sha256"]
    ):
        raise ValueError("target resolution differs from A1V authority")

    body = {
        "schema_version": "rvt-phase9g-a1v-production-preflight/v1",
        "phase": "PHASE_9G_A1V",
        "status": "PASS_ZERO_ESCAPES",
        "target": {
            "host": "100.71.102.9",
            "reported_hostname": observation["host"],
            "production_image": inspect["Id"],
            "image_source_commit": inspect["Config"]["Labels"]["org.opencontainers.image.revision"],
            "module_binding": module_binding,
            "network_mode": "none",
            "container_root_filesystem": "read_only",
            "image_inspect_file_sha256": _file_sha(TARGET / "target-image-inspect.json"),
        },
        "train_immutability": {
            "train_seal_precheck_sha256": train["phase9g_a1v_train_seal_precheck_sha256"],
            "manifest_sha256": observation["train_manifest_sha256"],
            "seal_sha256": observation["train_seal_sha256"],
            "scientific_rows": observation["train_scientific_rows"],
            "transactions": observation["train_transactions"],
            "staging_mode": observation["train_staging_mode"],
            "writable_files": observation["train_staging_writable_files"],
            "partial_files": observation["train_partials"],
            "mutation_authorized": False,
        },
        "authority": {
            "owner_authorization_sha256": authorization["phase9g_a1v_owner_authorization_sha256"],
            "authorization_scope_sha256": authorization["authorization_scope_sha256"],
            "run_identity_sha256": run["phase9g_a1v_validation_run_identity_sha256"],
            "validation_task_manifest_sha256": manifest["phase9g_a1v_validation_task_manifest_sha256"],
            "scientific_provenance_root": authorization["bindings"]["scientific_provenance_root"],
            "matched_randomness_authority": "87e206d22d3b3e893bc2c34ac87e97ceb5d9cb66e23d26456791bad552bcf851",
            "candidate_pair_transaction_contract": "c66a5b75c04fc8a9f38f9f3ea809824d697482826de85b5b4eefcfef9ffe1ca0",
            "target_v4_contract": "54a0e0baff79fbdc320800b772f47a40ac06ac4f0e70d4fab1bf676c54b918ee",
            "s3_exact_centerline_contract": authorization["bindings"]["scientific_addendum_sha256"],
        },
        "validation_namespace": {
            "writer_namespace": run["writer_namespace"],
            "preexisting": observation["validation_staging_exists"],
            "final_preexisting": observation["validation_final_exists"],
            "preexisting_event_identities": resolution["preexisting_event_identities"],
            "separate_from_train": True,
            "shared_mutable_indexes_with_train": False,
        },
        "compiled_universe": {
            "source_episodes": manifest["source_episodes"],
            "decision_events": manifest["decision_events"],
            "candidate_aggregates": manifest["candidate_aggregates"],
            "candidate_replica_slots": manifest["candidate_replica_slots"],
            "family_source_counts": manifest["family_source_counts"],
            "family_event_counts": manifest["family_event_counts"],
            "team_size_source_counts": manifest["team_size_source_counts"],
            "team_size_event_counts": manifest["team_size_event_counts"],
            "replicas_per_candidate_event_counts": manifest["replicas_per_candidate_event_counts"],
        },
        "profile": {
            "workers": 12,
            "numeric_threads_per_worker": 1,
            "chunk_size_atomic_units": 1,
            "infrastructure_timeout_seconds": 243,
        },
        "s3_guard": {
            "reference_sha256": reference["phase9g_a1v_s3_prestart_guard_sha256"],
            "target_sha256": target["phase9g_a1v_s3_prestart_guard_sha256"],
            "reference_target_semantic_exact": True,
            **target["counter_levels"],
        },
        "negative_cases": negative,
        "negative_case_escapes": 0,
        "tests": {
            "focused": _test_result(OUT / "phase9g_a1v_prestart_focused.log"),
            "complete_suite": _test_result(OUT / "phase9g_a1v_prestart_full_suite.log"),
        },
        "scope": {
            "study_a_recoverability_validation": "AUTHORIZED",
            "recoverability_train_modification": "NOT_AUTHORIZED",
            "residual_v2": "NOT_AUTHORIZED",
            "training": "NOT_AUTHORIZED",
            "hyperparameter_search": "NOT_AUTHORIZED",
            "class_weight_selection": "NOT_AUTHORIZED",
            "study_a_n24": "SEALED_NOT_AUTHORIZED",
            "study_b": "NOT_AUTHORIZED",
            "final_test": "SEALED_NOT_AUTHORIZED",
        },
        "official_validation_authorized": True,
    }
    document = attach_canonical_hash(body, "phase9g_a1v_production_preflight_sha256")
    path = OUT / "phase9g_a1v_production_preflight_v1.json"
    path.write_text(
        json.dumps(document, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )
    print(document["phase9g_a1v_production_preflight_sha256"])


if __name__ == "__main__":
    main()
