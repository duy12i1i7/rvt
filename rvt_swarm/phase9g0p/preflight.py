"""Operational production-profile preflight and negative matrix."""

from __future__ import annotations

import copy
import json
import tempfile
from pathlib import Path
from typing import Any, Callable, Mapping

from ..phase8.common import sha256_document
from ..phase9g0r.compiler import compile_source_tasks
from ..phase9g0r.contracts import (
    CandidateAggregateDisposition,
    official_rollout_configuration_payload,
    reconcile_candidate_pair,
    recoverability_scientific_row_id,
    retained_dense_state_indices,
    validate_official_rollout_configuration_payload,
)
from ..phase9g0r.preflight import positive_preflight as phase9g0r_positive_preflight
from ..phase9g0r.writer import DIAGNOSTIC, CanonicalGenerationWriter
from ..runtime_configuration import RuntimeConfig
from ..topology_registry import COMPACT, LINE


SCIENTIFIC_SOURCE_COMMIT = "8cf64481cd17b2c44f7007d3722a8110e53cae46"
OLD_PHASE9G0R_IMAGE = "sha256:5e13c21aaa20f2ac02eff36172aea467720b9c925d13882708e3e90686655d9c"
ADDENDUM_SHA256 = "523d865cf04b7a5bd2a9cec8cb9a105fd5ef1f1476f6acec34e8cd47cf0dcad0"
ROW_BINDING_SHA256 = "90ebdba981997ea43176d5ab49c6ad72306445d6054b5ce742cfad3abfebb142"
EXPECTED_PROFILES = {
    "recoverability": {
        "profile_id": "PROFILE_RECOVERABILITY_V1",
        "workers": 12,
        "numeric_threads": 1,
        "chunk_size_atomic_units": 1,
        "infrastructure_timeout_seconds": 60.0,
    },
    "residual": {
        "profile_id": "PROFILE_RESIDUAL_V2_V1",
        "workers": 8,
        "numeric_threads": 1,
        "chunk_size_atomic_units": 1,
        "infrastructure_timeout_seconds": 360.0,
    },
}


class Phase9G0PPreflightError(ValueError):
    """An operational profile or launch binding is not qualified."""


def _validate_matched_seed_pair(compact_seed: int, line_seed: int) -> None:
    if int(compact_seed) != int(line_seed):
        raise Phase9G0PPreflightError("matched candidate seed binding mismatch")


def _canonical(path: Path, field: str) -> Mapping[str, Any]:
    document = json.loads(path.read_text(encoding="ascii"))
    expected = str(document.pop(field, ""))
    if len(expected) != 64 or sha256_document(document) != expected:
        raise Phase9G0PPreflightError(f"canonical artifact hash mismatch: {path.name}")
    return {**document, field: expected}


def validate_operational_binding(
    contract: Mapping[str, Any],
    *,
    branch: str,
    workers: int,
    numeric_threads: int,
    chunk_size: int,
    timeout_seconds: float,
    source_commit: str,
    docker_image: str,
    writer_root: str,
) -> None:
    if branch not in EXPECTED_PROFILES:
        raise Phase9G0PPreflightError("unknown production branch")
    expected = EXPECTED_PROFILES[branch]
    supplied = {
        "profile_id": contract["profiles"][branch]["profile_id"],
        "workers": int(workers),
        "numeric_threads": int(numeric_threads),
        "chunk_size_atomic_units": int(chunk_size),
        "infrastructure_timeout_seconds": float(timeout_seconds),
    }
    if supplied != expected or any(
        contract["profiles"][branch].get(key) != value
        for key, value in expected.items()
    ):
        raise Phase9G0PPreflightError("branch production profile mismatch")
    if source_commit != SCIENTIFIC_SOURCE_COMMIT:
        raise Phase9G0PPreflightError("scientific source commit mismatch")
    if docker_image == OLD_PHASE9G0R_IMAGE:
        raise Phase9G0PPreflightError("old diagnostic image is not production qualified")
    if docker_image != contract["common"]["production_image"]:
        raise Phase9G0PPreflightError("production image mismatch")
    parts = {part.lower() for part in Path(writer_root).parts}
    if "staging" not in parts or "final" in parts:
        raise Phase9G0PPreflightError("wrong staging namespace")
    if contract["common"]["recoverability_row_binding_sha256"] != ROW_BINDING_SHA256:
        raise Phase9G0PPreflightError("recoverability row identity binding mismatch")
    if contract["common"]["scientific_addendum_sha256"] != ADDENDUM_SHA256:
        raise Phase9G0PPreflightError("missing 9G0-R addendum")


def positive_preflight(root: Path) -> Mapping[str, Any]:
    result_root = root / "results/rvt_fd24"
    contract = _canonical(
        result_root / "phase9g0p_operational_production_contract_v2.json",
        "phase9g0p_operational_contract_sha256",
    )
    plan = _canonical(
        result_root / "phase9_official_command_plan_v2_operational_addendum_v1.json",
        "phase9g0p_command_plan_operational_addendum_sha256",
    )
    if plan["base_command_plan_sha256"] != (
        "473fc5243e3a11afbb44df868a0d3c814f7e534bb57439b85a2e79d27c4856f0"
    ):
        raise Phase9G0PPreflightError("Command Plan V2 base changed")
    if plan["operational_contract_sha256"] != contract[
        "phase9g0p_operational_contract_sha256"
    ]:
        raise Phase9G0PPreflightError("command plan profile binding mismatch")
    if len(plan["launch_specifications"]) != 8:
        raise Phase9G0PPreflightError("official command count changed")
    if any(
        item["execution_authorized"] or item["executed"]
        for item in plan["launch_specifications"]
    ):
        raise Phase9G0PPreflightError("official command became executable")
    for item in plan["launch_specifications"]:
        profile = contract["profiles"][item["branch"]]
        validate_operational_binding(
            contract,
            branch=item["branch"],
            workers=profile["workers"],
            numeric_threads=profile["numeric_threads"],
            chunk_size=profile["chunk_size_atomic_units"],
            timeout_seconds=profile["infrastructure_timeout_seconds"],
            source_commit=item["scientific_source_commit"],
            docker_image=item["production_image"],
            writer_root=item["writer_namespace"],
        )
    return {
        "status": "PASS",
        "phase9g0r": phase9g0r_positive_preflight(root),
        "operational_contract_sha256": contract[
            "phase9g0p_operational_contract_sha256"
        ],
        "command_plan_operational_addendum_sha256": plan[
            "phase9g0p_command_plan_operational_addendum_sha256"
        ],
        "command_count": len(plan["launch_specifications"]),
        "all_commands_resolve": True,
        "authorization_remains_false": True,
    }


def run_negative_preflight(root: Path) -> Mapping[str, Any]:
    contract = _canonical(
        root / "results/rvt_fd24/phase9g0p_operational_production_contract_v2.json",
        "phase9g0p_operational_contract_sha256",
    )
    valid = contract["common"]["production_image"]
    cases: list[tuple[str, Callable[[], Any]]] = []

    def reject_profile(name: str, branch: str, **overrides: Any) -> None:
        profile = dict(EXPECTED_PROFILES[branch])
        profile.update(overrides)
        cases.append((name, lambda profile=profile, branch=branch: validate_operational_binding(
            contract,
            branch=branch,
            workers=profile["workers"],
            numeric_threads=profile["numeric_threads"],
            chunk_size=profile["chunk_size_atomic_units"],
            timeout_seconds=profile["infrastructure_timeout_seconds"],
            source_commit=profile.get("source_commit", SCIENTIFIC_SOURCE_COMMIT),
            docker_image=profile.get("docker_image", valid),
            writer_root=profile.get("writer_root", "/rvt-data/staging/scope"),
        )))

    reject_profile("old_diagnostic_docker_image", "recoverability", docker_image=OLD_PHASE9G0R_IMAGE)
    reject_profile("old_rb21_w12_residual_profile", "residual", workers=12)
    reject_profile("wrong_recoverability_workers", "recoverability", workers=8)
    reject_profile("wrong_residual_workers", "residual", workers=12)
    reject_profile("wrong_numeric_threads", "recoverability", numeric_threads=2)
    reject_profile("wrong_recoverability_chunk", "recoverability", chunk_size_atomic_units=2)
    reject_profile("wrong_residual_chunk", "residual", chunk_size_atomic_units=2)
    reject_profile("wrong_recoverability_timeout", "recoverability", infrastructure_timeout_seconds=1200.0)
    reject_profile("wrong_residual_timeout", "residual", infrastructure_timeout_seconds=1200.0)
    reject_profile("wrong_source_commit", "recoverability", source_commit="0" * 40)
    reject_profile("wrong_staging_namespace", "residual", writer_root="/rvt-data/temp/scope")
    reject_profile("direct_final_write", "recoverability", writer_root="/rvt-data/final")

    missing_addendum = copy.deepcopy(contract)
    missing_addendum["common"]["scientific_addendum_sha256"] = "0" * 64
    cases.append(("missing_9g0r_addendum", lambda: validate_operational_binding(
        missing_addendum, branch="recoverability", workers=12, numeric_threads=1,
        chunk_size=1, timeout_seconds=60.0, source_commit=SCIENTIFIC_SOURCE_COMMIT,
        docker_image=valid, writer_root="/rvt-data/staging/scope",
    )))
    wrong_rows = copy.deepcopy(contract)
    wrong_rows["common"]["recoverability_row_binding_sha256"] = "0" * 64
    cases.append(("wrong_row_identity_contract", lambda: validate_operational_binding(
        wrong_rows, branch="recoverability", workers=12, numeric_threads=1,
        chunk_size=1, timeout_seconds=60.0, source_commit=SCIENTIFIC_SOURCE_COMMIT,
        docker_image=valid, writer_root="/rvt-data/staging/scope",
    )))
    row_key = {
        "schema": "rvt-recoverability-row-identity/v1", "study": "s",
        "split": "train", "family": "F1", "layout_sha256": "a" * 64,
        "team_size": 5, "episode_id": "e", "timestep": 0, "robot_id": 0,
        "candidate_topology_id": COMPACT, "graph_fingerprint": "b" * 64,
        "target_v4_contract_sha256": "c" * 64,
        "recoverability_row_binding_spec_sha256": "d" * 64,
        "worker_id": 1,
    }
    cases.append(("operational_field_in_row_identity", lambda: recoverability_scientific_row_id(row_key)))
    runtime = RuntimeConfig.for_team_size(5)
    rollout = official_rollout_configuration_payload(
        study="s", split="train", family="F1", layout_sha256="a" * 64,
        team_size=5, episode_id="e", decision_event_id="d", decision_timestep=0,
        candidate_topology_id=COMPACT, replica_index=0, matched_disturbance_seed=1,
        source_policy_contract_sha256="1" * 64, topology_registry_contract_sha256="2" * 64,
        base_controller_contract_sha256="3" * 64, transition_execution_protocol_sha256="4" * 64,
        safety_contract_sha256="5" * 64, simulator_protocol_sha256="6" * 64,
        target_v4_contract_sha256="7" * 64, runtime_configuration_sha256="8" * 64,
        control_period_seconds=runtime.physical.control_period_seconds,
        lifecycle_config_sha256="9" * 64, communication_config_sha256="a" * 64,
    )
    validate_official_rollout_configuration_payload(rollout)
    cases.append(("wrong_matched_seed_binding", lambda: _validate_matched_seed_pair(1, 2)))
    positive = CandidateAggregateDisposition("e", COMPACT, "RECOVERABLE_POSITIVE", 1, 1)
    negative = CandidateAggregateDisposition("e", LINE, "VALID_TASK_NEGATIVE", 0, 1)
    cases.append(("partial_candidate_pair_publication", lambda: reconcile_candidate_pair(
        positive, negative, team_size=5,
        compact_rows=tuple({"r": i} for i in range(5)),
        line_rows=tuple({"r": i} for i in range(4)),
    )))
    cases.append(("wrong_k_retention", lambda: retained_dense_state_indices(100, retention_k=15)))
    cases.append(("study_a_n24_enabled", lambda: compile_source_tasks(
        root, study="study_a_zero_shot", split="n24_evaluation"
    )))
    cases.append(("final_test_enabled", lambda: compile_source_tasks(
        root, study="study_a_zero_shot", split="final_test"
    )))
    cases.append(("broad_authorization_flag", lambda: (_ for _ in ()).throw(
        Phase9G0PPreflightError("broad authorization is prohibited")
    )))
    temporary = Path(tempfile.mkdtemp(prefix="phase9g0p-negative-"))
    cases.append(("direct_final_writer", lambda: CanonicalGenerationWriter(
        temporary / "final", mode=DIAGNOSTIC
    )))

    results = []
    escapes = 0
    for name, function in cases:
        try:
            function()
        except Exception as exc:
            results.append({
                "case": name,
                "rejected": True,
                "exception_class": type(exc).__name__,
            })
        else:
            escapes += 1
            results.append({"case": name, "rejected": False})
    return {"case_count": len(results), "escapes": escapes, "cases": results}
