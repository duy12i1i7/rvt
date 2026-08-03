"""One-time authorization and static guards for sealed final-test access."""

from __future__ import annotations

import ast
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple

from .common import file_sha256

FINAL_TEST_GUARD_SCHEMA_VERSION = "rvt-final-test-access-guard/v1"
PERMITTED_PILOT_VERDICT = "PERMIT_FINAL_EVALUATION"
PERMITTED_PURPOSE = "one_time_final_evaluation"


@dataclass(frozen=True)
class FinalTestAuthorization:
    method_freeze_manifest_path: str
    method_freeze_manifest_sha256: str
    three_seed_pilot_manifest_path: str
    three_seed_pilot_manifest_sha256: str
    three_seed_pilot_verdict: str
    authorization_id: str
    one_time: bool
    purpose: str


@dataclass(frozen=True)
class FinalTestAccessDecision:
    schema_version: str
    admitted: bool
    reason: str
    authorization_id: Optional[str]


def is_final_test_path(path: Path) -> bool:
    normalized = str(path).lower()
    return "final_test" in normalized or normalized.endswith(".sealed.json")


def evaluate_final_test_authorization(
    authorization: Optional[FinalTestAuthorization],
    audit_log_path: Path,
) -> FinalTestAccessDecision:
    if authorization is None:
        return FinalTestAccessDecision(
            FINAL_TEST_GUARD_SCHEMA_VERSION, False,
            "explicit final-test authorization is absent", None,
        )
    if not authorization.method_freeze_manifest_path:
        return FinalTestAccessDecision(
            FINAL_TEST_GUARD_SCHEMA_VERSION, False,
            "method-freeze manifest is absent", authorization.authorization_id,
        )
    if len(authorization.method_freeze_manifest_sha256) != 64:
        return FinalTestAccessDecision(
            FINAL_TEST_GUARD_SCHEMA_VERSION, False,
            "method-freeze manifest hash is invalid", authorization.authorization_id,
        )
    method_freeze_path = Path(authorization.method_freeze_manifest_path)
    if not method_freeze_path.is_file():
        return FinalTestAccessDecision(
            FINAL_TEST_GUARD_SCHEMA_VERSION, False,
            "method-freeze manifest file does not exist", authorization.authorization_id,
        )
    if file_sha256(method_freeze_path) != authorization.method_freeze_manifest_sha256:
        return FinalTestAccessDecision(
            FINAL_TEST_GUARD_SCHEMA_VERSION, False,
            "method-freeze manifest hash does not match the file",
            authorization.authorization_id,
        )
    pilot_path = Path(authorization.three_seed_pilot_manifest_path)
    if not pilot_path.is_file():
        return FinalTestAccessDecision(
            FINAL_TEST_GUARD_SCHEMA_VERSION, False,
            "three-seed pilot manifest file does not exist",
            authorization.authorization_id,
        )
    if len(authorization.three_seed_pilot_manifest_sha256) != 64:
        return FinalTestAccessDecision(
            FINAL_TEST_GUARD_SCHEMA_VERSION, False,
            "three-seed pilot manifest hash is invalid",
            authorization.authorization_id,
        )
    if file_sha256(pilot_path) != authorization.three_seed_pilot_manifest_sha256:
        return FinalTestAccessDecision(
            FINAL_TEST_GUARD_SCHEMA_VERSION, False,
            "three-seed pilot manifest hash does not match the file",
            authorization.authorization_id,
        )
    if authorization.three_seed_pilot_verdict != PERMITTED_PILOT_VERDICT:
        return FinalTestAccessDecision(
            FINAL_TEST_GUARD_SCHEMA_VERSION, False,
            "three-seed pilot does not permit final evaluation", authorization.authorization_id,
        )
    if not authorization.authorization_id or not authorization.one_time:
        return FinalTestAccessDecision(
            FINAL_TEST_GUARD_SCHEMA_VERSION, False,
            "one-time authorization identity is invalid", authorization.authorization_id,
        )
    if authorization.purpose != PERMITTED_PURPOSE:
        return FinalTestAccessDecision(
            FINAL_TEST_GUARD_SCHEMA_VERSION, False,
            "final-test purpose cannot be training labeling or checkpoint selection",
            authorization.authorization_id,
        )
    if not audit_log_path.exists():
        return FinalTestAccessDecision(
            FINAL_TEST_GUARD_SCHEMA_VERSION, False,
            "audit log must exist before access", authorization.authorization_id,
        )
    entries = tuple(
        json.loads(line)
        for line in audit_log_path.read_text(encoding="ascii").splitlines()
        if line.strip()
    )
    if any(
        item.get("authorization_id") == authorization.authorization_id
        and item.get("admitted") is True
        for item in entries
    ):
        return FinalTestAccessDecision(
            FINAL_TEST_GUARD_SCHEMA_VERSION, False,
            "one-time authorization has already been consumed",
            authorization.authorization_id,
        )
    return FinalTestAccessDecision(
        FINAL_TEST_GUARD_SCHEMA_VERSION, True,
        "all one-time final-test gates are satisfied", authorization.authorization_id,
    )


def guarded_read_json(
    path: Path,
    authorization: Optional[FinalTestAuthorization],
    audit_log_path: Path,
) -> object:
    if not is_final_test_path(path):
        return json.loads(path.read_text(encoding="ascii"))
    decision = evaluate_final_test_authorization(authorization, audit_log_path)
    entry = {
        "schema_version": FINAL_TEST_GUARD_SCHEMA_VERSION,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "path": str(path),
        **asdict(decision),
    }
    with audit_log_path.open("a", encoding="ascii") as handle:
        handle.write(json.dumps(entry, ensure_ascii=True, sort_keys=True) + "\n")
    if not decision.admitted:
        raise PermissionError(decision.reason)
    return json.loads(path.read_text(encoding="ascii"))


def scan_source_for_final_test_access(source: str) -> Tuple[str, ...]:
    """Detect sealed-layout imports, literals and access calls in training code."""
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return (f"syntax_error:{exc.lineno}",)
    issues = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = []
            if isinstance(node, ast.Import):
                names = [item.name for item in node.names]
            elif node.module:
                names = [node.module]
            if any("final_test" in name or "sealed" in name for name in names):
                issues.append(f"sealed_import:{node.lineno}")
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            lowered = node.value.lower()
            if "final_test" in lowered or ".sealed.json" in lowered:
                issues.append(f"sealed_literal:{node.lineno}")
        if isinstance(node, ast.Call):
            name = getattr(node.func, "attr", getattr(node.func, "id", ""))
            if name in (
                "guarded_read_json",
                "generate_layouts",
                "enumerate_final_test_layouts",
                "load_final_test_labels",
                "select_checkpoint_from_final_test",
            ):
                issues.append(f"sealed_access_call:{node.lineno}:{name}")
    return tuple(sorted(set(issues)))


def write_empty_official_audit(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    header = {
        "schema_version": FINAL_TEST_GUARD_SCHEMA_VERSION,
        "event": "PHASE8_GUARD_INITIALIZED",
        "admitted": False,
        "successful_runtime_access_count": 0,
    }
    path.write_text(
        json.dumps(header, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="ascii",
    )
