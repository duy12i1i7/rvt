"""Additive V3 supervised-dataset namespace, manifest and seal.

Separate from :class:`CanonicalGenerationWriter` on purpose. V2 shards and V3
shards must never share a file, a directory or a schema, and the surest way to
guarantee that is for the V3 writer to be unable to name a V2 path at all.

The manifest and the seal both bind the required-replica invalidity contract,
because a dataset produced under a different censoring rule is a different
dataset even when every published row is identical. Row identity does not bind
it: the rule decides whether a row exists, not what it is.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

from ..phase8.common import attach_canonical_hash, sha256_document
from ..topology_registry import COMPACT, LINE
from .contracts_v3 import (
    CANDIDATE_PAIR_TRANSACTION_V3_SCHEMA_VERSION, INVALIDITY_CONTRACT_V3_SHA256,
    PROBABILISTIC_TARGET_V3_SHA256, RECOVERABILITY_PROTOCOL_V3,
    REPLICA_PROTOCOL_V3_SHA256, ROW_BINDING_V3_SPEC_SHA256,
    SOURCE_ACQUISITION_PROTOCOL_SHA256, TARGET_V4_CONTRACT_SHA256,
    S8InvalidRateAccounting, V3ContractError, V3PairTransaction,
    require_invalidity_contract,
)
from .writer import DIAGNOSTIC, OFFICIAL_STAGING

V3_NAMESPACE = "v3_recoverability"
V3_DATASET_MANIFEST_SCHEMA_VERSION = "rvt-recoverability-v3-dataset-manifest/v1"
V3_DATASET_SEAL_SCHEMA_VERSION = "rvt-recoverability-v3-dataset-seal/v1"
V3_ROW_SCHEMA_VERSION = "rvt-recoverability-v3-supervision-row/v1"


class V3WriterError(V3ContractError):
    """A V3 writer invariant that must fail closed."""


class V3SupervisedDatasetWriter:
    """Write complete V3 pair transactions; never finalize a dataset."""

    def __init__(self, root: Path, *, mode: str,
                 official_execution_authorized: bool = False) -> None:
        if mode not in (DIAGNOSTIC, OFFICIAL_STAGING):
            raise ValueError(
                "writer mode must be explicit DIAGNOSTIC or OFFICIAL_STAGING")
        self.root = Path(root).resolve()
        self.mode = mode
        self.official_execution_authorized = bool(official_execution_authorized)
        lower_parts = {part.lower() for part in self.root.parts}
        if "final" in lower_parts:
            raise PermissionError("direct FINAL writer is prohibited")
        if mode == OFFICIAL_STAGING:
            if "staging" not in lower_parts:
                raise PermissionError(
                    "official writer target must be a staging namespace")
            if not self.official_execution_authorized:
                raise PermissionError(
                    "official staging execution is not authorized")
        elif "staging" in lower_parts:
            raise PermissionError(
                "diagnostic writer must not target official staging")
        self.namespace = self.root / V3_NAMESPACE
        self.transactions_written = 0
        self.rows_written = 0

    # -- namespace separation -------------------------------------------
    def _write(self, relative: Path, document: Mapping[str, Any]) -> Tuple[Path, bool]:
        destination = self.namespace / relative
        for part in destination.parts:
            if part.lower() in ("v1", "v2", "recoverability_v2"):
                raise V3WriterError("the V3 writer may not target a V1/V2 path")
        destination.parent.mkdir(parents=True, exist_ok=True)
        body = json.loads(json.dumps(document, allow_nan=False, sort_keys=True))
        serialized = json.dumps(body, sort_keys=True, indent=1) + "\n"
        duplicate_replay = False
        if destination.exists():
            existing = destination.read_text(encoding="ascii")
            if existing != serialized:
                raise V3WriterError(
                    f"same V3 identity, different payload: {relative}")
            duplicate_replay = True
        else:
            destination.write_text(serialized, encoding="ascii")
        return destination, duplicate_replay

    # -- pair transactions ----------------------------------------------
    def write_v3_transaction(self, transaction: V3PairTransaction, *,
                             audit: Mapping[str, Any]) -> Mapping[str, Any]:
        """Only a scientifically labelable pair reaches a supervised shard."""
        require_invalidity_contract(transaction.invalidity_contract_sha256)
        if transaction.schema_version != CANDIDATE_PAIR_TRANSACTION_V3_SCHEMA_VERSION:
            raise V3WriterError("V3 writer received a non-V3 transaction")
        if not transaction.training_rows_committable:
            raise V3WriterError(
                "a non-committable V3 pair emits no supervised rows; its "
                "evidence belongs in the audit ledger")
        if transaction.actual_row_count != transaction.expected_row_count:
            raise V3WriterError("V3 pair atomicity requires exactly 2 * N rows")
        for row in transaction.rows:
            if row["schema_version"] != V3_ROW_SCHEMA_VERSION:
                raise V3WriterError("a non-V3 row entered the V3 namespace")
            for prohibited in ("k", "R", "label", "disposition", "k_over_R"):
                if prohibited in row["scientific_identity"]:
                    raise V3WriterError(
                        f"row identity carries the prohibited field {prohibited!r}")

        event_key = sha256_document(
            {"decision_event_id": transaction.decision_event_id})
        document = {
            **transaction.as_dict(),
            "writer_mode": self.mode,
            "audit": {str(key): value for key, value in audit.items()
                      if str(key) != "operational_timing"},
            "scientific_completion_marker": True,
        }
        path, duplicate_replay = self._write(
            Path("transactions") / f"event-{event_key}.json", document)
        if not duplicate_replay:
            self.transactions_written += 1
            self.rows_written += transaction.actual_row_count
        return {
            "path": str(path),
            "canonical_sha256": sha256_document(document),
            "rows": transaction.actual_row_count,
            "duplicate_replay": duplicate_replay,
            "official_counter_delta": (
                1 if self.mode == OFFICIAL_STAGING and not duplicate_replay else 0),
        }

    def write_v3_audit_record(self, *, decision_event_id: str,
                              record: Mapping[str, Any]) -> Mapping[str, Any]:
        """Evidence for a pair that publishes no rows. Never a supervised shard."""
        event_key = sha256_document({"decision_event_id": decision_event_id})
        document = {
            "schema_version": "rvt-recoverability-v3-audit-record/v1",
            "protocol_version": RECOVERABILITY_PROTOCOL_V3,
            "writer_mode": self.mode,
            "decision_event_id": decision_event_id,
            "supervised_rows": 0,
            "recoverability_v3_required_replica_invalidity_contract_v1_sha256":
                INVALIDITY_CONTRACT_V3_SHA256,
            **{str(key): value for key, value in record.items()},
        }
        if int(document["supervised_rows"]) != 0:
            raise V3WriterError("an audit record may never carry supervised rows")
        path, duplicate_replay = self._write(
            Path("audit") / f"event-{event_key}.json", document)
        return {"path": str(path), "canonical_sha256": sha256_document(document),
                "duplicate_replay": duplicate_replay}


# ---------------------------------------------------------------------------
# dataset manifest and seal
# ---------------------------------------------------------------------------
def build_v3_dataset_manifest(
    *, v3_split: str, dataset_id: str, source_manifest_root_sha256: str,
    layout_registry_sha256: str,
    execution_spec_registry_sha256: str,
    accounting: S8InvalidRateAccounting,
    source_episodes_executed: int, selected_source_events: int,
    pair_events_retained: int, pair_events_dropped_scientific_invalidity: int,
    candidate_supervision_records: int, candidate_supervision_blocked: int,
    rows_published: int, row_ids: Sequence[str],
    invalidity_contract_sha256: str = INVALIDITY_CONTRACT_V3_SHA256,
) -> Mapping[str, Any]:
    """The produced-dataset manifest. Binds the invalidity contract (A4)."""
    require_invalidity_contract(invalidity_contract_sha256)
    ordered = sorted(str(value) for value in row_ids)
    if len(set(ordered)) != len(ordered):
        raise V3WriterError("duplicate V3 scientific row identity")
    if len(ordered) != int(rows_published):
        raise V3WriterError("row-id count disagrees with rows_published")
    manifest = {
        "schema_version": V3_DATASET_MANIFEST_SCHEMA_VERSION,
        "protocol_version": RECOVERABILITY_PROTOCOL_V3,
        "v3_split": v3_split,
        "dataset_id": dataset_id,
        "source_manifest_root_sha256": source_manifest_root_sha256,
        "v3_layout_split_registry_v2_sha256": layout_registry_sha256,
        # The layout registry pins geometry; the execution-spec registry pins
        # the compiled runtime binding built from it. Neither alone identifies
        # the complete runtime authority, so the manifest carries both.
        "v3_layout_execution_spec_registry_v1_sha256":
            execution_spec_registry_sha256,
        "recoverability_probabilistic_target_v3_sha256":
            PROBABILISTIC_TARGET_V3_SHA256,
        "recoverability_replica_protocol_v3_sha256": REPLICA_PROTOCOL_V3_SHA256,
        "recoverability_row_binding_v3_spec_sha256": ROW_BINDING_V3_SPEC_SHA256,
        "source_acquisition_protocol_sha256": SOURCE_ACQUISITION_PROTOCOL_SHA256,
        "target_v4_contract_sha256": TARGET_V4_CONTRACT_SHA256,
        "recoverability_v3_required_replica_invalidity_contract_v1_sha256":
            invalidity_contract_sha256,
        # C13 invalidity accounting -- no hidden denominator changes.
        "invalidity_accounting": {
            "required_replica_evaluations": accounting.executed_required_rollouts,
            "scientifically_valid_replicas": (
                accounting.executed_required_rollouts
                - accounting.generation_invalid_rollouts),
            "generation_invalid_replicas": accounting.generation_invalid_rollouts,
            "infrastructure_unresolved_rollouts":
                accounting.infrastructure_unresolved_rollouts,
            "candidate_supervision_records_created": int(candidate_supervision_records),
            "candidate_supervision_blocked": int(candidate_supervision_blocked),
            "pair_events_retained": int(pair_events_retained),
            "pair_events_dropped_scientific_invalidity":
                int(pair_events_dropped_scientific_invalidity),
            "robot_rows_published": int(rows_published),
        },
        "s8": dict(accounting.gate()),
        "source_episodes_executed": int(source_episodes_executed),
        "selected_source_events": int(selected_source_events),
        "row_ids": ordered,
        "row_dataset_root_sha256": sha256_document(ordered),
        "placeholder_rows": 0,
        "partial_pairs_published": 0,
        "authorizes_official_generation": False,
    }
    return attach_canonical_hash(manifest, "v3_dataset_manifest_sha256")


def seal_v3_dataset(manifest: Mapping[str, Any]) -> Mapping[str, Any]:
    """The seal covers the manifest, so the censoring rule is sealed with it."""
    if manifest["schema_version"] != V3_DATASET_MANIFEST_SCHEMA_VERSION:
        raise V3WriterError("a V3 seal requires a V3 dataset manifest")
    require_invalidity_contract(manifest[
        "recoverability_v3_required_replica_invalidity_contract_v1_sha256"])
    seal = {
        "schema_version": V3_DATASET_SEAL_SCHEMA_VERSION,
        "protocol_version": RECOVERABILITY_PROTOCOL_V3,
        "v3_split": manifest["v3_split"],
        "v3_dataset_manifest_sha256": manifest["v3_dataset_manifest_sha256"],
        "row_dataset_root_sha256": manifest["row_dataset_root_sha256"],
        "v3_layout_execution_spec_registry_v1_sha256":
            manifest["v3_layout_execution_spec_registry_v1_sha256"],
        "v3_layout_split_registry_v2_sha256":
            manifest["v3_layout_split_registry_v2_sha256"],
        "recoverability_v3_required_replica_invalidity_contract_v1_sha256":
            manifest[
                "recoverability_v3_required_replica_invalidity_contract_v1_sha256"],
        "recoverability_probabilistic_target_v3_sha256":
            manifest["recoverability_probabilistic_target_v3_sha256"],
        "recoverability_replica_protocol_v3_sha256":
            manifest["recoverability_replica_protocol_v3_sha256"],
        "recoverability_row_binding_v3_spec_sha256":
            manifest["recoverability_row_binding_v3_spec_sha256"],
        "target_v4_contract_sha256": manifest["target_v4_contract_sha256"],
        "source_acquisition_protocol_sha256":
            manifest["source_acquisition_protocol_sha256"],
    }
    return attach_canonical_hash(seal, "v3_dataset_seal_sha256")
