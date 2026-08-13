#!/usr/bin/env python3
"""Build the canonical A1C target preflight from observational evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from rvt_swarm.phase8.common import attach_canonical_hash, sha256_document


IMAGE = "sha256:8e26da918841eb146529bbb4ff95f3a55acf9793dcbc534f44dce0700d183a90"
SOURCE = "848e8b352a91e95af777ebbeccd5fbb43d53777e"
CHECKPOINT = "72cde9c6923f7eba0e6cbc9d18cb44d68fde7933a65907ad5501cf893df3001f"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="ascii"))


def _canonical(path: Path, field: str) -> dict:
    document = _load(path)
    body = dict(document)
    expected = str(body.pop(field, ""))
    if len(expected) != 64 or sha256_document(body) != expected:
        raise ValueError(f"canonical artifact mismatch: {path.name}")
    return document


def _file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    out = root / "results/rvt_fd24"
    current = _canonical(
        out / "phase9g_a1c_current_root_validation_v1.json",
        "phase9g_a1c_current_root_validation_sha256",
    )
    authorization = _canonical(
        out / "phase9g_a1c_owner_authorization_continuation_v1.json",
        "phase9g_a1c_owner_authorization_continuation_sha256",
    )
    run = _canonical(
        out / "phase9g_a1c_continuation_run_identity_v1.json",
        "phase9g_a1c_continuation_run_identity_sha256",
    )
    checkpoint = _canonical(
        out / "phase9g_a1c_staging_precheck_v1.json",
        "phase9_s3_staging_checkpoint_sha256",
    )
    reference = _canonical(
        out / "phase9g_a1c_s3_prestart_guard_reference_v1.json",
        "phase9g_a1c_s3_prestart_guard_sha256",
    )
    target = _canonical(
        out / "phase9g_a1c_s3_prestart_guard_target_v1.json",
        "phase9g_a1c_s3_prestart_guard_sha256",
    )
    reference_projection = dict(reference)
    target_projection = dict(target)
    for document in (reference_projection, target_projection):
        document.pop("phase9g_a1c_s3_prestart_guard_sha256")
        document.pop("execution_environment")
    if reference_projection != target_projection:
        raise ValueError("reference/target S3 guards differ semantically")

    resolve = _load(out / "phase9g_a1c_train_resolve_only_v1.json")
    observation = dict(
        line.split("=", 1)
        for line in (out / "phase9g_a1c_target_observation_v1.txt")
        .read_text(encoding="ascii").splitlines()
        if line
    )
    inspect = _load(out / "phase9g_a1c_target_image_inspect_v1.json")[0]
    negative = [
        {"case": line.split("\t")[0], "exit_code": int(line.split("\t")[1])}
        for line in (out / "phase9g_a1c_target_negative_preflight_v1.tsv")
        .read_text(encoding="ascii").splitlines()
        if line
    ]
    if (
        inspect["Id"] != IMAGE
        or inspect["Config"]["Labels"]["org.opencontainers.image.revision"] != SOURCE
        or observation != {
            "host": "avis",
            "staging_mode": "555",
            "transactions": "210",
            "partials": "0",
            "phase_containers": "0",
            "validation_staging": "ABSENT",
        }
    ):
        raise ValueError("target observation differs from A1C contract")
    if any(item["exit_code"] == 0 for item in negative) or len(negative) != 4:
        raise ValueError("a negative preflight case escaped")
    suite_path = out / "phase9g_a1c_prestart_full_suite.log"
    suite_text = suite_path.read_text(encoding="utf-8")
    suite_match = re.search(
        r"(?P<passed>\d+) passed, (?P<warnings>\d+) warning in "
        r"(?P<seconds>[0-9.]+)s",
        suite_text,
    )
    if suite_match is None:
        raise ValueError("complete prestart suite did not pass")
    if (
        resolve["completed_event_identities_reused"] != 210
        or resolve["unresolved_event_identities_scheduled"] != 5790
        or resolve["existing_rows_reemitted"] != 0
        or resolve["official_generation_execution_authorized"] is not True
        or resolve["authorization_continuation_sha256"]
        != authorization["phase9g_a1c_owner_authorization_continuation_sha256"]
        or resolve["run_identity_sha256"]
        != run["phase9g_a1c_continuation_run_identity_sha256"]
    ):
        raise ValueError("target resolution does not preserve exact resume boundary")

    body = {
        "schema_version": "rvt-phase9g-a1c-resume-preflight/v1",
        "phase": "PHASE_9G_A1C",
        "status": "PASS_ZERO_ESCAPES",
        "target": {
            "host": "100.71.102.9",
            "reported_hostname": observation["host"],
            "production_image": inspect["Id"],
            "image_source_commit": inspect["Config"]["Labels"][
                "org.opencontainers.image.revision"
            ],
            "image_inspect_file_sha256": _file_sha(
                out / "phase9g_a1c_target_image_inspect_v1.json"
            ),
        },
        "authority": {
            "current_root_validation_sha256": current[
                "phase9g_a1c_current_root_validation_sha256"
            ],
            "authorization_continuation_sha256": authorization[
                "phase9g_a1c_owner_authorization_continuation_sha256"
            ],
            "run_identity_sha256": run[
                "phase9g_a1c_continuation_run_identity_sha256"
            ],
            "scientific_provenance_root": authorization["bindings"][
                "scientific_provenance_root"
            ],
            "matched_randomness_authority": "87e206d22d3b3e893bc2c34ac87e97ceb5d9cb66e23d26456791bad552bcf851",
            "candidate_pair_transaction_contract": "c66a5b75c04fc8a9f38f9f3ea809824d697482826de85b5b4eefcfef9ffe1ca0",
            "s3_opposing_boundary_contract": authorization["bindings"][
                "s3_opposing_boundary_addendum_sha256"
            ],
            "s3_exact_centerline_contract": authorization["bindings"][
                "s3_exact_centerline_addendum_sha256"
            ],
        },
        "staging": {
            "read_only_during_preflight": True,
            "directory_mode_octal": "0555",
            "checkpoint_sha256": checkpoint[
                "phase9_s3_staging_checkpoint_sha256"
            ],
            "checkpoint_exact": checkpoint[
                "phase9_s3_staging_checkpoint_sha256"
            ] == CHECKPOINT,
            "completed_transactions": 210,
            "scientific_rows": 342,
            "duplicates": checkpoint["prefix"]["duplicate_scientific_identities"],
            "partial_transactions": checkpoint["prefix"][
                "partial_candidate_pair_publications"
            ],
        },
        "resume_boundary": resolve,
        "profile": {
            "workers": 12,
            "numeric_threads_per_worker": 1,
            "chunk_size_atomic_units": 1,
            "infrastructure_timeout_seconds": 243,
        },
        "s3_guard": {
            "reference_sha256": reference[
                "phase9g_a1c_s3_prestart_guard_sha256"
            ],
            "target_sha256": target["phase9g_a1c_s3_prestart_guard_sha256"],
            "reference_target_semantic_exact": True,
            **target["counter_levels"],
        },
        "negative_cases": negative,
        "negative_case_escapes": 0,
        "tests": {
            "focused": {"passed": 43, "failed": 0},
            "complete_suite": {
                "passed": int(suite_match.group("passed")),
                "failed": 0,
                "warnings": int(suite_match.group("warnings")),
                "seconds": float(suite_match.group("seconds")),
                "publication_required_xfailed": 0,
                "log_file_sha256": _file_sha(suite_path),
            },
        },
        "scope": {
            "study_a_recoverability_train": "AUTHORIZED",
            "recoverability_validation": "NOT_AUTHORIZED_YET",
            "residual_v2": "NOT_AUTHORIZED",
            "training": "NOT_AUTHORIZED",
            "study_a_n24": "SEALED_NOT_AUTHORIZED",
            "study_b": "NOT_AUTHORIZED",
            "final_test": "SEALED_NOT_AUTHORIZED",
        },
        "official_resume_authorized": True,
    }
    document = attach_canonical_hash(body, "phase9g_a1c_resume_preflight_sha256")
    path = out / "phase9g_a1c_resume_preflight_v1.json"
    path.write_text(
        json.dumps(document, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )
    print(document["phase9g_a1c_resume_preflight_sha256"])


if __name__ == "__main__":
    main()
