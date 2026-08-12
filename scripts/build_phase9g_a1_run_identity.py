#!/usr/bin/env python3
"""Build an operational run identity and mechanically activate frozen commands."""

from __future__ import annotations

import argparse
import json
import shlex
from pathlib import Path
from typing import Any, Mapping, Sequence

from rvt_swarm.phase8.common import attach_canonical_hash, sha256_document


PRODUCTION_IMAGE = (
    "sha256:88ecf1aac7cd95b5ba50811950090c13f78362274e5c5cdaeafaafde29a115f4"
)
SCIENTIFIC_SOURCE_COMMIT = "8cf64481cd17b2c44f7007d3722a8110e53cae46"
STUDY = "study_a_zero_shot"
SPLITS = ("train", "validation")
BRANCH_PROFILES = {
    "recoverability": "PROFILE_RECOVERABILITY_V1",
    "residual": "PROFILE_RESIDUAL_V2_V1",
}
ALLOWED_ACTIVATION_OPTIONS = (
    "--authorization-scope-sha256",
    "--authorization-scope",
    "--run-id",
)


class RunIdentityError(RuntimeError):
    """The run cannot be bound without changing the frozen command semantics."""


def _canonical(path: Path, field: str) -> tuple[Mapping[str, Any], str]:
    document = json.loads(path.read_text(encoding="ascii"))
    body = dict(document)
    expected = str(body.pop(field, ""))
    if len(expected) != 64 or sha256_document(body) != expected:
        raise RunIdentityError(f"canonical artifact mismatch: {path.name}")
    return document, expected


def _write(path: Path, body: Mapping[str, Any], hash_field: str) -> str:
    document = attach_canonical_hash(dict(body), hash_field)
    path.write_text(
        json.dumps(document, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )
    return str(document[hash_field])


def _option_index(argv: Sequence[str], option: str) -> int:
    if argv.count(option) != 1:
        raise RunIdentityError(f"frozen command must contain {option} exactly once")
    index = argv.index(option)
    if index + 1 >= len(argv):
        raise RunIdentityError(f"frozen command has no value for {option}")
    return index + 1


def activate_command(
    command: str,
    *,
    scope_path: str,
    scope_sha256: str,
    run_id: str,
) -> tuple[list[str], list[Mapping[str, str]]]:
    original = shlex.split(command)
    activated = list(original)
    replacements = {
        "--authorization-scope-sha256": scope_sha256,
        "--authorization-scope": scope_path,
        "--run-id": run_id,
    }
    changes = []
    changed_indices = set()
    for option in ALLOWED_ACTIVATION_OPTIONS:
        index = _option_index(original, option)
        old = original[index]
        new = replacements[option]
        activated[index] = new
        changed_indices.add(index)
        changes.append({"option": option, "old": old, "new": new})
    for index, (old, new) in enumerate(zip(original, activated)):
        if index not in changed_indices and old != new:
            raise RunIdentityError("non-authorized command token changed")
    return activated, changes


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--branch", choices=tuple(BRANCH_PROFILES), required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--timestamp-utc", required=True)
    parser.add_argument("--authorization-commit", required=True)
    args = parser.parse_args()

    if any(character.isspace() for character in args.run_id):
        raise RunIdentityError("run ID must not contain whitespace")
    if len(args.authorization_commit) != 40:
        raise RunIdentityError("authorization commit must be a full Git object ID")
    root = args.root.resolve()
    result_root = root / "results/rvt_fd24"
    authorization, authorization_sha256 = _canonical(
        result_root / "phase9g_a1_owner_authorization_v1.json",
        "phase9g_a1_owner_authorization_sha256",
    )
    plan, plan_sha256 = _canonical(
        result_root / "phase9_official_command_plan_v2_operational_addendum_v1.json",
        "phase9g0p_command_plan_operational_addendum_sha256",
    )
    operational, operational_sha256 = _canonical(
        result_root / "phase9g0p_operational_production_contract_v2.json",
        "phase9g0p_operational_contract_sha256",
    )
    scopes = {
        item["command_id"]: item
        for item in authorization["authorized_scope_artifacts"]
    }
    launches = [
        launch
        for launch in plan["launch_specifications"]
        if launch.get("study") == STUDY
        and launch.get("split") in SPLITS
        and launch.get("branch") == args.branch
    ]
    if len(launches) != 2:
        raise RunIdentityError("run must bind exactly train and validation commands")

    run_identity_body = {
        "schema_version": "rvt-phase9g-a1-operational-run-identity/v1",
        "phase": "PHASE_9G_A1",
        "run_id": args.run_id,
        "identity_class": "OPERATIONAL_NOT_SCIENTIFIC",
        "created_at_utc": args.timestamp_utc,
        "state_at_creation": "CREATED_NOT_STARTED",
        "study": STUDY,
        "splits": list(SPLITS),
        "label_branch": args.branch,
        "command_ids": [launch["command_id"] for launch in launches],
        "scientific_row_identity_includes_run_id": False,
        "scientific_source_commit": SCIENTIFIC_SOURCE_COMMIT,
        "production_image": PRODUCTION_IMAGE,
        "generation_provenance_root": authorization["frozen_bindings"][
            "generation_provenance"
        ]["sha256"],
        "authorization": {
            "artifact": "phase9g_a1_owner_authorization_v1.json",
            "sha256": authorization_sha256,
            "commit": args.authorization_commit,
        },
        "operational_profile": {
            "artifact": "phase9g0p_operational_production_contract_v2.json",
            "sha256": operational_sha256,
            **dict(operational["profiles"][args.branch]),
        },
        "writer_namespaces": {
            str(launch["split"]): str(launch["writer_namespace"])
            for launch in launches
        },
        "sealed_scopes": {
            "study_a_n24_zero_shot": "SEALED_NOT_AUTHORIZED",
            "study_b": "NOT_AUTHORIZED",
            "final_test": "SEALED_NOT_AUTHORIZED",
            "training": "NOT_AUTHORIZED",
        },
        "initial_counters": {
            "official_staging_writes": 0,
            "scientific_rows": 0,
            "shards": 0,
            "training_operations": 0,
            "study_a_n24_accesses": 0,
            "study_b_accesses": 0,
            "final_test_accesses": 0,
        },
    }
    stem = f"phase9g_a1_{args.branch}_run_identity_v1"
    run_path = result_root / f"{stem}.json"
    run_sha256 = _write(
        run_path, run_identity_body, f"phase9g_a1_{args.branch}_run_identity_sha256"
    )

    activated_commands = []
    for launch in launches:
        command_id = str(launch["command_id"])
        scope = scopes.get(command_id)
        if scope is None:
            raise RunIdentityError(f"no enabled authorization scope for {command_id}")
        scope_path = f"/rvt-data/authorization/{scope['artifact']}"
        official, changes = activate_command(
            str(launch["official_command"]),
            scope_path=scope_path,
            scope_sha256=str(scope["sha256"]),
            run_id=args.run_id,
        )
        base_resolution = shlex.split(str(launch["resolution_command"]))
        if base_resolution != shlex.split(str(launch["official_command"])) + [
            "--resolve-only"
        ]:
            raise RunIdentityError("frozen resolution command is not official plus resolve")
        activated_commands.append({
            "command_id": command_id,
            "study": STUDY,
            "split": launch["split"],
            "branch": args.branch,
            "base_official_command": launch["official_command"],
            "official_command_argv": official,
            "resolve_command_argv": official + ["--resolve-only"],
            "activation_changes": changes,
            "unchanged_scientific_and_operational_tokens": True,
            "authorization_scope_artifact": scope["artifact"],
            "authorization_scope_sha256": scope["sha256"],
            "writer_namespace": launch["writer_namespace"],
            "task_count": launch["task_count"],
        })

    activation_body = {
        "schema_version": "rvt-phase9g-a1-authorized-command-activation/v1",
        "phase": "PHASE_9G_A1",
        "branch": args.branch,
        "run_id": args.run_id,
        "run_identity": {"artifact": run_path.name, "sha256": run_sha256},
        "base_command_plan": {
            "artifact": "phase9_official_command_plan_v2_operational_addendum_v1.json",
            "sha256": plan_sha256,
        },
        "authorization": {
            "artifact": "phase9g_a1_owner_authorization_v1.json",
            "sha256": authorization_sha256,
        },
        "production_image": PRODUCTION_IMAGE,
        "allowed_activation_options": list(ALLOWED_ACTIVATION_OPTIONS),
        "command_count": len(activated_commands),
        "commands": activated_commands,
        "sealed_scope_commands_activated": 0,
        "scientific_outcomes_present": False,
    }
    activation_path = result_root / f"phase9g_a1_{args.branch}_command_activation_v1.json"
    activation_sha256 = _write(
        activation_path,
        activation_body,
        f"phase9g_a1_{args.branch}_command_activation_sha256",
    )
    print(json.dumps({
        "run_id": args.run_id,
        "run_identity_sha256": run_sha256,
        "command_activation_sha256": activation_sha256,
        "command_count": len(activated_commands),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
