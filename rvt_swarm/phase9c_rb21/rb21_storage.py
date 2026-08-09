"""Atomic-unit persistence, resume and failure safety for RB-21 staging."""

from __future__ import annotations

import json
import math
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional

from ..phase8.common import canonical_json_bytes, sha256_document


class StorageContractError(RuntimeError):
    pass


def _atomic_json(path: Path, document: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(canonical_json_bytes(dict(document)) + b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


class AtomicUnitStore:
    """Commit record and sidecar together; completion is content-validated."""

    def __init__(self, staging_root: Path) -> None:
        self.root = staging_root
        self.transactions = self.root / "transactions"
        self.units = self.root / "units"
        self.attempts = self.root / "attempts"
        for path in (self.transactions, self.units, self.attempts):
            path.mkdir(parents=True, exist_ok=True)

    def _attempt(self, unit_id: str, attempt_id: str, state: str,
                 detail: Optional[str] = None) -> None:
        _atomic_json(self.attempts / f"{attempt_id}.json", {
            "unit_id": unit_id, "attempt_id": attempt_id, "state": state,
            "detail": detail,
        })

    def _validated_commit(self, directory: Path) -> Optional[Dict[str, Any]]:
        try:
            commit = json.loads((directory / "commit.json").read_text(encoding="ascii"))
            record = json.loads((directory / "record.json").read_text(encoding="ascii"))
            sidecar = json.loads((directory / "sidecar.json").read_text(encoding="ascii"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return None
        if commit.get("record_sha256") != sha256_document(record):
            return None
        if commit.get("sidecar_sha256") != sha256_document(sidecar):
            return None
        if commit.get("unit_id") != directory.name:
            return None
        return commit

    def commit(self, unit_id: str, record: Mapping[str, Any], sidecar: Mapping[str, Any],
               *, attempt_id: str, failure_point: Optional[str] = None,
               required_free_bytes: int = 0) -> str:
        if shutil.disk_usage(self.root).free < required_free_bytes:
            self._attempt(unit_id, attempt_id, "INFRASTRUCTURE_FAILURE",
                          "INSUFFICIENT_TEMPORARY_SPACE")
            raise StorageContractError("insufficient temporary space")
        final = self.units / unit_id
        expected = {
            "unit_id": unit_id,
            "record_sha256": sha256_document(dict(record)),
            "sidecar_sha256": sha256_document(dict(sidecar)),
        }
        existing = self._validated_commit(final) if final.exists() else None
        if existing is not None:
            if existing != expected:
                raise StorageContractError("duplicate identity has different science")
            self._attempt(unit_id, attempt_id, "DUPLICATE_IDEMPOTENT")
            return "DUPLICATE_IDEMPOTENT"

        self._attempt(unit_id, attempt_id, "STARTED")
        transaction = self.transactions / attempt_id
        if transaction.exists():
            shutil.rmtree(transaction)
        transaction.mkdir()
        try:
            _atomic_json(transaction / "record.json", dict(record))
            if failure_point == "after_record":
                raise StorageContractError("injected failure after record")
            _atomic_json(transaction / "sidecar.json", dict(sidecar))
            if failure_point == "after_sidecar":
                raise StorageContractError("injected failure after sidecar")
            _atomic_json(transaction / "commit.json", expected)
            if failure_point == "before_promotion":
                raise StorageContractError("injected failure before promotion")
            os.replace(transaction, final)
            self._attempt(unit_id, attempt_id, "ACKNOWLEDGED")
            return "ACKNOWLEDGED"
        except Exception as error:
            self._attempt(unit_id, attempt_id, "INFRASTRUCTURE_FAILURE", str(error))
            raise

    def completed_unit_ids(self) -> set:
        return {path.name for path in self.units.iterdir()
                if path.is_dir() and self._validated_commit(path) is not None}

    def incomplete_attempts(self) -> Dict[str, Mapping[str, Any]]:
        output = {}
        for path in sorted(self.attempts.glob("*.json")):
            item = json.loads(path.read_text(encoding="ascii"))
            if item["state"] not in ("ACKNOWLEDGED", "DUPLICATE_IDEMPOTENT"):
                output[item["attempt_id"]] = item
        return output

    def validate_complete(self, expected_unit_ids: Iterable[str]) -> Mapping[str, Any]:
        expected = set(expected_unit_ids)
        completed = self.completed_unit_ids()
        return {
            "expected": len(expected), "completed": len(completed),
            "missing": sorted(expected - completed),
            "unexpected": sorted(completed - expected),
            "valid": completed == expected,
        }

    def promote(self, destination: Path, expected_unit_ids: Iterable[str]) -> None:
        validation = self.validate_complete(expected_unit_ids)
        if not validation["valid"]:
            raise StorageContractError("staging is incomplete and cannot be promoted")
        if destination.exists():
            raise StorageContractError("final destination already exists")
        _atomic_json(self.root / "completion_manifest.json", validation)
        os.replace(self.root, destination)


def representative_sizes(rb18: Mapping[str, Any]) -> Mapping[str, int]:
    recoverability = rb18["recoverability"][0]
    replica = recoverability["replica_records"][0]
    labeled = next(item for item in rb18["residual"]
                   if item["disposition"] == "LABELED")
    no_eligible = next(item for item in rb18["residual"]
                       if item["disposition"] == "NO_ELIGIBLE_ACTION")
    shard_metadata = {
        "schema_version": "rvt-rb21-diagnostic-shard-index/v1",
        "unit_ids": ["u" * 64], "record_hashes": ["r" * 64],
        "sidecar_hashes": ["s" * 64], "complete": True,
    }
    return {
        "recoverability_scientific_record_bytes": len(canonical_json_bytes(replica)),
        "recoverability_audit_replica_metadata_bytes": len(
            canonical_json_bytes(recoverability)),
        "residual_labeled_row_bytes": len(canonical_json_bytes(labeled)),
        "residual_nine_candidate_sidecar_bytes": len(
            canonical_json_bytes(labeled["candidate_sidecar"])),
        "no_eligible_action_audit_record_bytes": len(canonical_json_bytes(no_eligible)),
        "shard_index_manifest_metadata_bytes": len(canonical_json_bytes(shard_metadata)),
    }


def storage_projection(sizes: Mapping[str, int]) -> Mapping[str, Any]:
    recoverability_rows = 332_900
    residual_rows = 536_000
    scientific = (
        recoverability_rows * sizes["recoverability_scientific_record_bytes"]
        + residual_rows * sizes["residual_labeled_row_bytes"])
    audit = (
        recoverability_rows * sizes["recoverability_audit_replica_metadata_bytes"]
        + residual_rows * sizes["residual_nine_candidate_sidecar_bytes"]
        + residual_rows * sizes["no_eligible_action_audit_record_bytes"])
    indexes = math.ceil((scientific + audit) * 0.05)
    final_dataset = scientific + audit + indexes
    resume = math.ceil(final_dataset * 0.02)
    temporary = math.ceil(final_dataset * 0.25)
    upper = final_dataset * 2 + resume + temporary
    return {
        "recoverability_record_upper_count": recoverability_rows,
        "residual_stored_row_upper_cap": residual_rows,
        "residual_candidate_evaluation_upper_bound": 4_824_000,
        "candidate_evaluation_bound_is_scientific_row_count": False,
        "scientific_payload_bytes": scientific,
        "audit_sidecars_bytes": audit,
        "indexes_and_manifests_bytes": indexes,
        "resume_metadata_bytes": resume,
        "temporary_generation_bytes": temporary,
        "staging_bytes": final_dataset,
        "final_dataset_bytes": final_dataset,
        "staging_plus_final_plus_temporary_upper_bytes": upper,
    }
