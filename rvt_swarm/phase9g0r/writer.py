"""Canonical diagnostic and staging-only writer for official producers."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping, Optional

from ..phase8.common import attach_canonical_hash, sha256_document
from .contracts import CandidatePairReconciliation, Phase9G0RContractError


DIAGNOSTIC = "DIAGNOSTIC"
OFFICIAL_STAGING = "OFFICIAL_STAGING"


class CanonicalGenerationWriter:
    """Write complete scientific units; never finalize a dataset."""

    def __init__(
        self,
        root: Path,
        *,
        mode: str,
        official_execution_authorized: bool = False,
    ) -> None:
        if mode not in (DIAGNOSTIC, OFFICIAL_STAGING):
            raise ValueError("writer mode must be explicit DIAGNOSTIC or OFFICIAL_STAGING")
        self.root = root.resolve()
        self.mode = mode
        self.official_execution_authorized = bool(official_execution_authorized)
        lower_parts = {part.lower() for part in self.root.parts}
        if "final" in lower_parts:
            raise PermissionError("direct FINAL writer is prohibited")
        if mode == OFFICIAL_STAGING:
            if "staging" not in lower_parts:
                raise PermissionError("official writer target must be a staging namespace")
            if not self.official_execution_authorized:
                raise PermissionError("official staging execution is not authorized")
        elif "staging" in lower_parts:
            raise PermissionError("diagnostic writer must not target official staging")

    @property
    def increments_official_counters(self) -> bool:
        return self.mode == OFFICIAL_STAGING

    @staticmethod
    def _durable_audit(audit: Mapping[str, Any]) -> Mapping[str, Any]:
        """Exclude nondeterministic operational telemetry from scientific records."""
        return {
            str(key): value
            for key, value in audit.items()
            if str(key) != "operational_timing"
        }

    def _write(self, relative: Path, document: Mapping[str, Any]) -> tuple[Path, bool]:
        destination = self.root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        body = json.loads(json.dumps(document, allow_nan=False, sort_keys=True))
        payload = attach_canonical_hash(body, "canonical_record_sha256")
        if destination.exists():
            existing = json.loads(destination.read_text(encoding="ascii"))
            if existing != payload:
                raise Phase9G0RContractError(
                    "duplicate scientific identity has different canonical content"
                )
            return destination, True
        temporary = destination.with_suffix(destination.suffix + ".partial")
        serialized = (
            json.dumps(
                payload,
                allow_nan=False,
                ensure_ascii=True,
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n"
        )
        with temporary.open("w", encoding="ascii") as stream:
            stream.write(serialized)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
        directory_fd = os.open(destination.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        return destination, False

    def write_recoverability_transaction(
        self,
        reconciliation: CandidatePairReconciliation,
        audit: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        event_key = sha256_document({"decision_event_id": reconciliation.decision_event_id})
        transaction = {
            "schema_version": reconciliation.schema_version,
            "writer_mode": self.mode,
            "decision_event_id": reconciliation.decision_event_id,
            "status": reconciliation.status,
            "scientifically_reconciled": reconciliation.scientifically_reconciled,
            "training_rows_committable": reconciliation.training_rows_committable,
            "expected_row_count": reconciliation.expected_row_count,
            "actual_row_count": reconciliation.actual_row_count,
            "rows": list(reconciliation.rows),
            "audit": self._durable_audit(audit),
            "scientific_completion_marker": bool(
                reconciliation.scientifically_reconciled
                and (
                    reconciliation.training_rows_committable
                    or reconciliation.actual_row_count == 0
                )
            ),
        }
        path, duplicate_replay = self._write(
            Path("recoverability") / f"event-{event_key}.json", transaction
        )
        return {
            "path": str(path),
            "canonical_sha256": sha256_document(transaction),
            "official_counter_delta": (
                1 if self.increments_official_counters and not duplicate_replay else 0
            ),
            "duplicate_replay": duplicate_replay,
        }

    def write_residual_attempt(
        self,
        *,
        scientific_row_id: str,
        disposition: str,
        row: Optional[Mapping[str, Any]],
        audit: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        if disposition == "LABELED" and row is None:
            raise Phase9G0RContractError("LABELED residual attempt requires one row")
        if disposition != "LABELED" and row is not None:
            raise Phase9G0RContractError("non-LABELED residual attempt emits no row")
        document = {
            "schema_version": "rvt-official-residual-attempt/v1",
            "writer_mode": self.mode,
            "residual_scientific_row_id": scientific_row_id,
            "disposition": disposition,
            "row": row,
            "audit": self._durable_audit(audit),
            "scientific_completion_marker": disposition in {
                "LABELED", "NO_ELIGIBLE_ACTION", "EXECUTION_INVALID"
            },
        }
        path, duplicate_replay = self._write(
            Path("residual") / f"state-{scientific_row_id}.json", document
        )
        return {
            "path": str(path),
            "canonical_sha256": sha256_document(document),
            "official_counter_delta": (
                1 if self.increments_official_counters and not duplicate_replay else 0
            ),
            "duplicate_replay": duplicate_replay,
        }
