"""Canonical serialization and approved Phase 8 source identities."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Dict


PHASE8_APPROVED_BASE_COMMIT = "d24a0f674c1e75df293e4524f020acc49d4e2f35"
ONLINE_TOPOLOGY_SCOPE_SCHEMA_VERSION = "rvt-online-topology-scope/v1"
ONLINE_TOPOLOGY_SCOPE_SHA256 = (
    "bc65ec533c895a9ad82ef277e89998c772db3403d4177ec04d9dce375f0c7684"
)
EXPERIMENT_PROTOCOL_SCHEMA_VERSION = "rvt-experiment-protocol/v1"


def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")


def sha256_document(value: object) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def attach_canonical_hash(
    document: Dict[str, object],
    field: str = "manifest_sha256",
) -> Dict[str, object]:
    result = dict(document)
    result.pop(field, None)
    result[field] = sha256_document(result)
    return result


def verify_canonical_hash(
    document: object,
    field: str = "manifest_sha256",
) -> bool:
    if not isinstance(document, dict) or not isinstance(document.get(field), str):
        return False
    payload = dict(document)
    expected = payload.pop(field)
    return expected == sha256_document(payload)


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, document: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            document,
            allow_nan=False,
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
        ) + "\n",
        encoding="ascii",
    )
