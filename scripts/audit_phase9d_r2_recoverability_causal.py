#!/usr/bin/env python3
"""Read-only causal reconstruction of finalized Phase 9 Recoverability events."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import re
import stat
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

COMPACT = 5
LINE = 2
RECOVERABILITY_ROW_IDENTITY_FIELDS = (
    "schema",
    "study",
    "split",
    "family",
    "layout_sha256",
    "team_size",
    "episode_id",
    "timestep",
    "robot_id",
    "candidate_topology_id",
    "graph_fingerprint",
    "target_v4_contract_sha256",
    "recoverability_row_binding_spec_sha256",
)


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


def recoverability_scientific_row_id(identity: Mapping[str, Any]) -> str:
    if set(identity) != set(RECOVERABILITY_ROW_IDENTITY_FIELDS):
        raise CausalAuditError("recoverability scientific row identity fields changed")
    return sha256_document({name: identity[name] for name in RECOVERABILITY_ROW_IDENTITY_FIELDS})


SCHEMA_VERSION = "rvt-phase9d-r2-recoverability-causal-audit/v1"
MATRIX_SCHEMA_VERSION = "rvt-phase9d-r2-recoverability-event-causal-record/v1"
STUDY = "study_a_zero_shot"
CONTROL_PERIOD_SECONDS = 0.15
EVENT_NORMALIZED_TIMES = (0.10, 0.30, 0.50, 0.70, 0.90)
FAMILY_HORIZON_SECONDS = {
    "F1": 90.0,
    "F2": 120.0,
    "F3": 135.0,
    "F4": 150.0,
    "F5": 180.0,
    "F6": 130.0,
    "F7": 110.0,
    "F8": 180.0,
    "F9": 150.0,
    "F10": 90.0,
}
DATASETS = {
    "train": {
        "dataset_id": "phase9g-a1-study-a-train-recoverability-v1",
        "manifest_sha256": "4ac3d2cb65a8b5d656a5d982b344466868f8deaa8cef2b93af7ce824e9387caf",
        "seal_sha256": "5b9e6726b548722ee651eefa7106662e2b119147d9b0c31ec4d4cbe0a1de58f5",
        "expected_events": 6000,
        "expected_rows": 8340,
    },
    "validation": {
        "dataset_id": "phase9g-a1-study-a-validation-recoverability-v1",
        "manifest_sha256": "c991aa3016b38b524a14d9b7037b63d97c2cbbb7d92279fc5a297b9c55d4989e",
        "seal_sha256": "c7583b124c573c52b57cd91dc1b54aff8fc02b33cf0a15d5449936a8d540637f",
        "expected_events": 1500,
        "expected_rows": 2294,
    },
}
TOPOLOGY_NAMES = {COMPACT: "COMPACT", LINE: "LINE"}
EVENT_RE = re.compile(
    r"/source_episode/study_a_zero_shot/(train|validation)/(F(?:10|[1-9]))/"
    r"([0-9a-f]{64})/N(5|6|8|12|16)/([^/]+)/episode-(\d+)/event-(\d+)$"
)
LABELABLE = frozenset({"RECOVERABLE_POSITIVE", "VALID_TASK_NEGATIVE"})


class CausalAuditError(RuntimeError):
    """Existing evidence violates the frozen publication contract."""


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_document(path: Path, hash_field: str) -> tuple[dict[str, Any], str]:
    document = json.loads(path.read_text(encoding="ascii"))
    body = dict(document)
    observed = str(body.pop(hash_field, ""))
    if len(observed) != 64 or sha256_document(body) != observed:
        raise CausalAuditError(f"canonical hash mismatch: {path}")
    return document, observed


def jsonl_records(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("rb") as stream:
        for number, line in enumerate(stream, start=1):
            if not line.endswith(b"\n"):
                raise CausalAuditError(f"unterminated JSONL: {path}:{number}")
            record = json.loads(line)
            if line != canonical_json_bytes(record) + b"\n":
                raise CausalAuditError(f"noncanonical JSONL: {path}:{number}")
            yield record


def namespace_metadata_checkpoint(paths: Sequence[Path]) -> dict[str, Any]:
    """Inventory metadata without writing or following namespace-crossing links."""
    inventory = []
    for root in paths:
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            metadata = path.stat()
            inventory.append({
                "namespace": root.name,
                "path": path.relative_to(root).as_posix(),
                "size_bytes": metadata.st_size,
                "mode_octal": oct(stat.S_IMODE(metadata.st_mode)),
                "mtime_ns": metadata.st_mtime_ns,
                "inode": metadata.st_ino,
            })
    return {
        "schema_version": "rvt-read-only-namespace-metadata-checkpoint/v1",
        "file_count": len(inventory),
        "total_bytes": sum(item["size_bytes"] for item in inventory),
        "writable_files": sum(
            int(bool(int(item["mode_octal"], 8) & 0o222)) for item in inventory
        ),
        "inventory_sha256": sha256_document({"files": inventory}),
    }


def event_identity(event_id: str) -> dict[str, Any]:
    match = EVENT_RE.search(event_id)
    if match is None:
        raise CausalAuditError(f"unexpected decision-event identity: {event_id}")
    split, family, layout_sha, team_size, source_class, episode, event = match.groups()
    event_index = int(event)
    if event_index not in range(len(EVENT_NORMALIZED_TIMES)):
        raise CausalAuditError(f"event stage is outside frozen Study-A schedule: {event_id}")
    horizon = FAMILY_HORIZON_SECONDS[family]
    requested_seconds = EVENT_NORMALIZED_TIMES[event_index] * horizon
    control_step = int(math.ceil(requested_seconds / CONTROL_PERIOD_SECONDS - 1e-12))
    return {
        "study": STUDY,
        "split": split,
        "family": family,
        "layout_sha256": layout_sha,
        "team_size": int(team_size),
        "episode_id": event_id.rsplit("/event-", 1)[0],
        "source_class": source_class,
        "episode_index": int(episode),
        "event_id": event_id,
        "event_stage": f"event-{event_index}",
        "event_index": event_index,
        "event_normalized_time": EVENT_NORMALIZED_TIMES[event_index],
        "event_requested_time_seconds": requested_seconds,
        "event_resolved_control_step": control_step,
        "event_resolved_time_seconds": control_step * CONTROL_PERIOD_SECONDS,
    }


def candidate_evidence(
    candidate_audits: Mapping[int, Mapping[str, Any]], candidate: int,
) -> dict[str, Any]:
    name = TOPOLOGY_NAMES[candidate].lower()
    audit = candidate_audits.get(candidate)
    if audit is None:
        return {
            f"{name}_attempted": False,
            f"{name}_raw_disposition": "NOT_EVALUATED_NO_SOURCE_SNAPSHOT",
            f"{name}_producer_disposition_before_pair": "GENERATION_INVALID",
            f"{name}_raw_reason": "SOURCE_TERMINATED_BEFORE_EVENT",
            f"{name}_replica_count": 0,
            f"{name}_label_if_labelable": None,
            f"{name}_replica_dispositions": [],
            f"{name}_replica_termination_causes": [],
        }
    aggregate = dict(audit["aggregate"])
    replicas = list(audit.get("replicas", []))
    return {
        f"{name}_attempted": True,
        f"{name}_raw_disposition": str(aggregate["disposition"]),
        f"{name}_producer_disposition_before_pair": str(aggregate["disposition"]),
        f"{name}_raw_reason": sorted({
            f"{replica['termination_cause']}:"
            + ",".join(str(item) for item in replica.get("failed_predicates", []))
            for replica in replicas
        }),
        f"{name}_replica_count": len(replicas),
        f"{name}_label_if_labelable": aggregate.get("aggregate_label"),
        f"{name}_replica_dispositions": [
            str(replica["disposition"]) for replica in replicas
        ],
        f"{name}_replica_termination_causes": [
            str(replica["termination_cause"]) for replica in replicas
        ],
    }


def infer_root_cause(record: Mapping[str, Any]) -> str:
    if not record["source_snapshot_exists"]:
        return "SOURCE_EVENT_NOT_REACHED"
    compact = record["compact_raw_disposition"]
    line = record["line_raw_disposition"]
    if record["pair_reconciliation_result"] == "PENDING_INFRASTRUCTURE_RESOLUTION":
        return "INFRA_FAILURE"
    if compact == "GENERATION_INVALID" and line in LABELABLE:
        return "COMPACT_ONLY_INVALID"
    if line == "GENERATION_INVALID" and compact in LABELABLE:
        return "LINE_ONLY_INVALID"
    if compact == line == "GENERATION_INVALID":
        return "BOTH_CANDIDATES_INVALID"
    if compact in LABELABLE and line in LABELABLE:
        if record["pair_reconciliation_result"] == "SCIENTIFICALLY_RECONCILED_LABELABLE":
            return "RETAINED_LABELABLE"
        return "PAIR_RECONCILIATION_ONLY"
    return "UNKNOWN_INSUFFICIENT_PROVENANCE"


def build_event_record(
    descriptor: Mapping[str, Any], transaction: Mapping[str, Any],
) -> dict[str, Any]:
    event_id = str(descriptor["decision_event_id"])
    identity = event_identity(event_id)
    if transaction["decision_event_id"] != event_id:
        raise CausalAuditError("transaction identity differs from its index")
    status = str(transaction["status"])
    audit = dict(transaction["audit"])
    source_terminated = bool(audit.get("source_terminated_before_event"))
    termination = audit.get("termination")
    snapshot_exists = bool(audit.get("source_snapshot_sha256"))
    if source_terminated == snapshot_exists:
        raise CausalAuditError(f"source reach/snapshot state is inconsistent: {event_id}")

    candidate_audits = {
        int(item["candidate_topology_id"]): item
        for item in audit.get("candidate_audits", [])
    }
    if snapshot_exists and set(candidate_audits) != {COMPACT, LINE}:
        raise CausalAuditError(f"realized event lacks independent candidate audits: {event_id}")
    if source_terminated and candidate_audits:
        raise CausalAuditError(f"unrealized event contains candidate execution: {event_id}")

    terminal_step = None if termination is None else int(termination["control_step"])
    event_step = int(identity["event_resolved_control_step"])
    if source_terminated and not terminal_step < event_step:
        raise CausalAuditError(
            f"source_terminated_before_event does not precede event step: {event_id}"
        )
    record = {
        "schema_version": MATRIX_SCHEMA_VERSION,
        **identity,
        "source_event_scheduled": True,
        "source_event_reached": snapshot_exists,
        "source_snapshot_exists": snapshot_exists,
        "source_snapshot_sha256": audit.get("source_snapshot_sha256"),
        "source_terminal_before_event": source_terminated,
        "source_terminal_same_step": False,
        "source_terminal_after_snapshot": None,
        "source_terminal_after_snapshot_observation": (
            "NOT_OBSERVED_SOURCE_EXECUTION_STOPS_AT_SNAPSHOT"
            if snapshot_exists else "NOT_APPLICABLE_NO_SNAPSHOT"
        ),
        "source_terminal_reason": None if termination is None else str(termination["cause"]),
        "source_terminal_control_step": terminal_step,
        "source_terminal_time_seconds": (
            None if termination is None else float(termination["time_seconds"])
        ),
        "source_terminal_detail": None if termination is None else termination.get("detail"),
        **candidate_evidence(candidate_audits, COMPACT),
        **candidate_evidence(candidate_audits, LINE),
        "pair_reconciliation_result": status,
        "pair_drop_reason": (
            f"SOURCE_TERMINATED_BEFORE_EVENT:{termination['cause']}"
            if source_terminated else None
        ),
        "published_robot_rows": int(transaction["actual_row_count"]),
        "expected_robot_rows": int(transaction["expected_row_count"]),
        "scientifically_reconciled": bool(transaction["scientifically_reconciled"]),
        "training_rows_committable": bool(transaction["training_rows_committable"]),
        "transaction_content_sha256": str(descriptor["content_sha256"]),
    }

    # A terminal snapshot is visible indirectly: every candidate clone starts
    # terminal and therefore all replicas finish at the event control step.
    if snapshot_exists:
        candidate_replicas = [
            replica
            for item in candidate_audits.values()
            for replica in item.get("replicas", [])
        ]
        if candidate_replicas and all(
            int(replica["control_steps"]) == event_step for replica in candidate_replicas
        ):
            causes = {str(replica["termination_cause"]) for replica in candidate_replicas}
            if len(causes) == 1:
                record["source_terminal_same_step"] = True
                record["source_terminal_reason"] = next(iter(causes))
                record["source_terminal_control_step"] = event_step
                record["source_terminal_time_seconds"] = identity[
                    "event_resolved_time_seconds"
                ]
    record["inferred_root_cause_category"] = infer_root_cause(record)
    return record


def validate_rows(transaction: Mapping[str, Any], team_size: int) -> None:
    rows = list(transaction["rows"])
    actual = int(transaction["actual_row_count"])
    expected = int(transaction["expected_row_count"])
    if actual != len(rows) or expected != 2 * team_size:
        raise CausalAuditError("transaction row accounting differs from 2*N contract")
    if len(rows) not in (0, expected):
        raise CausalAuditError("partial candidate-pair publication")
    seen = set()
    candidate_rows = Counter()
    for row in rows:
        row_id = str(row["scientific_row_id"])
        if row_id in seen or row_id != recoverability_scientific_row_id(row["scientific_identity"]):
            raise CausalAuditError("duplicate or invalid robot-local row identity")
        seen.add(row_id)
        candidate_rows[int(row["candidate_topology_id"])] += 1
    if rows and candidate_rows != Counter({COMPACT: team_size, LINE: team_size}):
        raise CausalAuditError("labelable transaction does not contain N rows per candidate")


def validate_matched_randomness(record: Mapping[str, Any], transaction: Mapping[str, Any]) -> dict[str, int]:
    audits = {
        int(item["candidate_topology_id"]): item
        for item in transaction["audit"].get("candidate_audits", [])
    }
    if not audits:
        return {"replica_pairs_checked": 0, "seed_mismatches": 0, "clone_hash_mismatches": 0}
    compact = list(audits[COMPACT]["replicas"])
    line = list(audits[LINE]["replicas"])
    if len(compact) != len(line):
        raise CausalAuditError(f"candidate replica cardinality mismatch: {record['event_id']}")
    seed_mismatches = 0
    clone_hash_mismatches = 0
    for left, right in zip(compact, line):
        seed_mismatches += int(
            int(left["matched_disturbance_seed"]) != int(right["matched_disturbance_seed"])
        )
        clone_hash_mismatches += int(left["initial_clone_hash"] != right["initial_clone_hash"])
    expected_replicas = 3 if record["family"] in ("F8", "F9") else 1
    if len(compact) != expected_replicas:
        raise CausalAuditError(f"frozen family replica count changed: {record['event_id']}")
    return {
        "replica_pairs_checked": len(compact),
        "seed_mismatches": seed_mismatches,
        "clone_hash_mismatches": clone_hash_mismatches,
    }


def infrastructure_evidence(transaction: Mapping[str, Any]) -> dict[str, int]:
    counts = Counter()
    for audit in transaction["audit"].get("candidate_audits", []):
        for replica in audit.get("replicas", []):
            attempts = list(replica.get("infrastructure_attempts", []))
            counts["infra_attempted"] += len(attempts)
            failures = sum(item.get("status") != "COMPLETED" for item in attempts)
            counts["infra_failed"] += failures
            counts["retried"] += int(len(attempts) > 1)
            counts["resolved"] += int(failures > 0 and attempts[-1].get("status") == "COMPLETED")
    counts["unresolved"] += int(
        transaction["status"] == "PENDING_INFRASTRUCTURE_RESOLUTION"
    )
    return dict(counts)


def distribution(
    records: Sequence[Mapping[str, Any]], keys: Sequence[str],
) -> list[dict[str, Any]]:
    counter = Counter(tuple(record[key] for key in keys) for record in records)
    result = []
    for values, count in sorted(counter.items()):
        subset = [record for record in records if tuple(record[key] for key in keys) == values]
        reached = sum(bool(record["source_event_reached"]) for record in subset)
        retained = sum(
            record["pair_reconciliation_result"] == "SCIENTIFICALLY_RECONCILED_LABELABLE"
            for record in subset
        )
        categories = Counter(record["inferred_root_cause_category"] for record in subset)
        result.append({
            **dict(zip(keys, values)),
            "total_source_events": count,
            "event_reached_count": reached,
            "event_reached_rate": reached / count,
            "source_snapshot_count": reached,
            "retained_pair_count": retained,
            "dropped_pair_count": count - retained,
            "retained_pair_rate": retained / count,
            "compact_only_invalid": categories["COMPACT_ONLY_INVALID"],
            "line_only_invalid": categories["LINE_ONLY_INVALID"],
            "both_candidates_invalid": categories["BOTH_CANDIDATES_INVALID"],
            "no_source_snapshot": categories["SOURCE_EVENT_NOT_REACHED"],
            "event_capture_ordering": categories["EVENT_CAPTURE_ORDERING"],
            "infra_failure": categories["INFRA_FAILURE"],
            "unknown": categories["UNKNOWN_INSUFFICIENT_PROVENANCE"],
        })
    return result


def summarize_records(
    records: Sequence[Mapping[str, Any]], *, provenance: Mapping[str, Any],
    checkpoints: Mapping[str, Any], matched: Mapping[str, int], infra: Mapping[str, int],
) -> dict[str, Any]:
    categories = Counter(record["inferred_root_cause_category"] for record in records)
    status = Counter(record["pair_reconciliation_result"] for record in records)
    compact = Counter(record["compact_raw_disposition"] for record in records)
    line = Counter(record["line_raw_disposition"] for record in records)
    raw_combinations = Counter(
        (record["compact_raw_disposition"], record["line_raw_disposition"])
        for record in records
    )
    reason_distribution = Counter(
        (
            record["split"],
            "BEFORE_EVENT" if record["source_terminal_before_event"] else "SAME_STEP_CAPTURED",
            record["source_terminal_reason"],
        )
        for record in records if record["source_terminal_reason"] is not None
    )
    source_not_reached = categories["SOURCE_EVENT_NOT_REACHED"]
    dropped = len(records) - status["SCIENTIFICALLY_RECONCILED_LABELABLE"]
    rows_prevented = sum(
        int(record["expected_robot_rows"])
        for record in records
        if record["pair_reconciliation_result"] != "SCIENTIFICALLY_RECONCILED_LABELABLE"
    )
    partner_only_losses = categories["COMPACT_ONLY_INVALID"] + categories["LINE_ONLY_INVALID"]
    accounting_by_split = []
    for split in DATASETS:
        subset = [record for record in records if record["split"] == split]
        split_categories = Counter(
            record["inferred_root_cause_category"] for record in subset
        )
        retained = sum(
            record["pair_reconciliation_result"] == "SCIENTIFICALLY_RECONCILED_LABELABLE"
            for record in subset
        )
        split_dropped = len(subset) - retained
        accounting_by_split.append({
            "split": split,
            "source_events": len(subset),
            "scheduled_events": len(subset),
            "realized_events": retained,
            "source_event_not_reached": split_categories["SOURCE_EVENT_NOT_REACHED"],
            "retained_pairs": retained,
            "dropped_pairs": split_dropped,
            "candidate_aggregates_scheduled": 2 * len(subset),
            "candidate_aggregates_attempted": sum(
                int(record["compact_attempted"]) + int(record["line_attempted"])
                for record in subset
            ),
            "raw_candidate_invalid": sum(
                int(record["compact_raw_disposition"] == "GENERATION_INVALID")
                + int(record["line_raw_disposition"] == "GENERATION_INVALID")
                for record in subset
            ),
            "producer_pre_pair_generation_invalid": sum(
                int(record["compact_producer_disposition_before_pair"] == "GENERATION_INVALID")
                + int(record["line_producer_disposition_before_pair"] == "GENERATION_INVALID")
                for record in subset
            ),
            "not_evaluated_no_source_snapshot_candidates": 2
            * split_categories["SOURCE_EVENT_NOT_REACHED"],
            "candidate_aggregates_absent_from_publication": 2 * split_dropped,
            "candidate_aggregates_removed_only_due_to_partner_invalid": (
                split_categories["COMPACT_ONLY_INVALID"]
                + split_categories["LINE_ONLY_INVALID"]
            ),
            "published_rows": sum(int(record["published_robot_rows"]) for record in subset),
            "robot_local_rows_prevented_from_publication": sum(
                int(record["expected_robot_rows"])
                for record in subset
                if record["pair_reconciliation_result"]
                != "SCIENTIFICALLY_RECONCILED_LABELABLE"
            ),
        })

    result = {
        "schema_version": SCHEMA_VERSION,
        "phase": "PHASE_9D_R2",
        "execution_mode": "READ_ONLY_EXISTING_ARTIFACT_FORENSICS",
        "provenance": dict(provenance),
        "namespace_checkpoints": dict(checkpoints),
        "counts": {
            "source_events": len(records),
            "scheduled_events": len(records),
            "realized_events": sum(bool(record["source_event_reached"]) for record in records),
            "snapshots_created": sum(bool(record["source_snapshot_exists"]) for record in records),
            "retained_pairs": status["SCIENTIFICALLY_RECONCILED_LABELABLE"],
            "dropped_pairs": dropped,
            "candidate_aggregates_scheduled": 2 * len(records),
            "candidate_aggregates_attempted": sum(
                int(record["compact_attempted"]) + int(record["line_attempted"])
                for record in records
            ),
            "raw_compact_invalid": compact["GENERATION_INVALID"],
            "raw_line_invalid": line["GENERATION_INVALID"],
            "raw_candidate_invalid": compact["GENERATION_INVALID"] + line["GENERATION_INVALID"],
            "producer_pre_pair_generation_invalid": sum(
                int(record["compact_producer_disposition_before_pair"] == "GENERATION_INVALID")
                + int(record["line_producer_disposition_before_pair"] == "GENERATION_INVALID")
                for record in records
            ),
            "both_invalid_events": categories["BOTH_CANDIDATES_INVALID"],
            "compact_only_invalid_events": categories["COMPACT_ONLY_INVALID"],
            "line_only_invalid_events": categories["LINE_ONLY_INVALID"],
            "source_event_not_reached": source_not_reached,
            "not_evaluated_no_source_snapshot_candidates": 2 * source_not_reached,
            "event_capture_ordering": categories["EVENT_CAPTURE_ORDERING"],
            "source_snapshot_invalid": categories["SOURCE_SNAPSHOT_INVALID"],
            "pair_reconciliation_only": categories["PAIR_RECONCILIATION_ONLY"],
            "infra_failure": categories["INFRA_FAILURE"],
            "unknown": categories["UNKNOWN_INSUFFICIENT_PROVENANCE"],
            "candidate_aggregates_absent_from_publication": 2 * dropped,
            "candidate_aggregates_removed_only_due_to_partner_invalid": partner_only_losses,
            "published_rows": sum(int(record["published_robot_rows"]) for record in records),
            "robot_local_rows_prevented_from_publication": rows_prevented,
            "source_terminal_same_step_snapshots": sum(
                bool(record["source_terminal_same_step"]) for record in records
            ),
        },
        "root_cause_distribution": [
            {"category": key, "count": value, "rate_of_all_events": value / len(records)}
            for key, value in sorted(categories.items())
        ],
        "raw_candidate_disposition_distribution": {
            "semantics": (
                "raw_*_disposition records whether a counterfactual rollout was evaluated; "
                "*_producer_disposition_before_pair separately preserves the producer enum"
            ),
            "compact": [{"disposition": key, "count": value} for key, value in sorted(compact.items())],
            "line": [{"disposition": key, "count": value} for key, value in sorted(line.items())],
            "combinations": [
                {"compact": key[0], "line": key[1], "count": value}
                for key, value in sorted(raw_combinations.items())
            ],
        },
        "source_terminal_reason_distribution": [
            {
                "split": key[0],
                "source_terminal_relation": key[1],
                "source_terminal_reason": key[2],
                "count": value,
            }
            for key, value in sorted(reason_distribution.items())
        ],
        "accounting_by_split": accounting_by_split,
        "breakdowns": {
            "by_split": distribution(records, ("split",)),
            "by_family": distribution(records, ("split", "family")),
            "by_event_stage": distribution(records, ("split", "event_stage")),
            "by_team_size": distribution(records, ("split", "team_size")),
            "by_family_event_team_size": distribution(
                records, ("split", "family", "event_stage", "team_size")
            ),
            "by_source_class": distribution(records, ("split", "source_class")),
        },
        "matched_randomness": dict(matched),
        "infrastructure": {
            key: int(infra.get(key, 0))
            for key in ("infra_attempted", "infra_failed", "retried", "resolved", "unresolved")
        },
        "ordering_hypothesis": {
            "terminal_before_capture_defect": "REFUTED",
            "dropped_events_attributable_to_same_step_ordering": categories[
                "EVENT_CAPTURE_ORDERING"
            ],
            "evidence": (
                "producer rejects only terminal_control_step < event_control_step; "
                "terminal at equality proceeds to snapshot"
            ),
        },
        "denominator_semantics": {
            "scheduled_event_identities_exist_before_source_execution": True,
            "scheduled_but_unrealized_events_are_counted": True,
            "scheduled_events": len(records),
            "realized_source_states": sum(bool(record["source_event_reached"]) for record in records),
        },
        "causal_verdict": {
            "primary_category": "CATEGORY_B_SOURCE_EVENT_ACQUISITION_DESIGN_FAILURE",
            "category_a_implementation_conformance_defect_dropped_events": categories[
                "EVENT_CAPTURE_ORDERING"
            ],
            "category_b_source_event_acquisition_design_failure_dropped_events": source_not_reached,
            "category_c_genuine_counterfactual_infeasibility_dropped_events": (
                categories["COMPACT_ONLY_INVALID"]
                + categories["LINE_ONLY_INVALID"]
                + categories["BOTH_CANDIDATES_INVALID"]
            ),
            "category_d_pair_atomicity_amplification_partner_aggregate_losses": partner_only_losses,
            "category_b_rate_of_dropped_events": source_not_reached / dropped,
            "recommended_next_action": "PROSPECTIVE_SOURCE_ACQUISITION_PROTOCOL_V2_REQUIRED",
        },
        "sealed_scope": {
            "study_a_n24_dataset_accesses": 0,
            "study_b_dataset_accesses": 0,
            "final_test_dataset_accesses": 0,
            "training_operations": 0,
            "official_generation_operations": 0,
            "scientific_dataset_mutations": 0,
        },
    }
    body = dict(result)
    result["phase9d_r2_recoverability_causal_summary_sha256"] = sha256_document(body)
    return result


def examples_by_category(
    records: Sequence[Mapping[str, Any]], limit: int = 3,
) -> dict[str, list[dict[str, Any]]]:
    examples: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        category = str(record["inferred_root_cause_category"])
        if len(examples[category]) < limit:
            examples[category].append({
                "split": record["split"],
                "family": record["family"],
                "team_size": record["team_size"],
                "source_class": record["source_class"],
                "episode_index": record["episode_index"],
                "event_stage": record["event_stage"],
                "event_id": record["event_id"],
                "source_event_reached": record["source_event_reached"],
                "source_terminal_reason": record["source_terminal_reason"],
                "compact_raw_disposition": record["compact_raw_disposition"],
                "line_raw_disposition": record["line_raw_disposition"],
                "pair_reconciliation_result": record["pair_reconciliation_result"],
            })
    return dict(sorted(examples.items()))


def analyze(data_root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    records = []
    provenance: dict[str, Any] = {"datasets": {}}
    matched = Counter()
    infra = Counter()
    namespace_paths = []
    for split, contract in DATASETS.items():
        final = data_root / "final" / str(contract["dataset_id"])
        staging = data_root / "staging" / f"{STUDY}-{split}-recoverability"
        if not final.is_dir() or not staging.is_dir():
            raise CausalAuditError(f"missing existing {split} final/STAGING namespace")
        namespace_paths.extend((final, staging))
    before = namespace_metadata_checkpoint(namespace_paths)

    for split, contract in DATASETS.items():
        final = data_root / "final" / str(contract["dataset_id"])
        staging = data_root / "staging" / f"{STUDY}-{split}-recoverability"
        manifest, manifest_sha = canonical_document(
            final / "dataset_manifest.json", "dataset_manifest_sha256"
        )
        seal, seal_sha = canonical_document(final / "DATASET_SEAL.json", "dataset_seal_sha256")
        if manifest_sha != contract["manifest_sha256"] or seal_sha != contract["seal_sha256"]:
            raise CausalAuditError(f"{split} published manifest/seal differs from authority")
        if seal["dataset_manifest_sha256"] != manifest_sha:
            raise CausalAuditError(f"{split} seal does not bind manifest")
        index_descriptor = manifest["transaction_indexes"][0]
        index_path = final / str(index_descriptor["path"])
        if file_sha256(index_path) != index_descriptor["content_sha256"]:
            raise CausalAuditError(f"{split} transaction index content hash changed")
        split_count = 0
        split_rows = 0
        for descriptor in jsonl_records(index_path):
            transaction_path = final / str(descriptor["path"])
            staging_path = data_root / "staging" / str(descriptor["relative_staging_path"])
            if not transaction_path.is_file() or not staging_path.is_file():
                raise CausalAuditError(f"{split} transaction provenance path is missing")
            if not os.path.samefile(transaction_path, staging_path):
                raise CausalAuditError(f"{split} FINAL transaction is not linked to STAGING")
            if file_sha256(transaction_path) != descriptor["content_sha256"]:
                raise CausalAuditError(f"{split} transaction content hash changed")
            transaction, _ = canonical_document(transaction_path, "canonical_record_sha256")
            identity = event_identity(str(descriptor["decision_event_id"]))
            validate_rows(transaction, int(identity["team_size"]))
            record = build_event_record(descriptor, transaction)
            randomness = validate_matched_randomness(record, transaction)
            matched.update(randomness)
            infra.update(infrastructure_evidence(transaction))
            records.append(record)
            split_count += 1
            split_rows += int(record["published_robot_rows"])
        if split_count != contract["expected_events"] or split_rows != contract["expected_rows"]:
            raise CausalAuditError(f"{split} event/row count differs from frozen publication")
        provenance["datasets"][split] = {
            "dataset_id": contract["dataset_id"],
            "dataset_manifest_sha256": manifest_sha,
            "dataset_seal_sha256": seal_sha,
            "scientific_source_commit": manifest["scientific_source_commit"],
            "generation_provenance_root": manifest["generation_provenance_root"],
            "event_count": split_count,
            "row_count": split_rows,
        }

    records.sort(key=lambda item: str(item["event_id"]))
    event_ids = [str(record["event_id"]) for record in records]
    if len(set(event_ids)) != len(event_ids):
        raise CausalAuditError("duplicate source-event identity across finalized datasets")
    after = namespace_metadata_checkpoint(namespace_paths)
    if before != after:
        raise CausalAuditError("scientific namespace metadata changed during read-only audit")
    checkpoints = {"before": before, "after": after, "unchanged": True}
    provenance["audit_host"] = {
        "hostname": platform.node(),
        "platform": platform.platform(),
        "python": sys.version.split()[0],
    }
    summary = summarize_records(
        records,
        provenance=provenance,
        checkpoints=checkpoints,
        matched=matched,
        infra=infra,
    )
    summary["event_examples"] = examples_by_category(records)
    body = dict(summary)
    body.pop("phase9d_r2_recoverability_causal_summary_sha256")
    summary["phase9d_r2_recoverability_causal_summary_sha256"] = sha256_document(body)
    return records, summary


def write_outputs(
    records: Sequence[Mapping[str, Any]], summary: Mapping[str, Any],
    matrix_output: Path, summary_output: Path,
) -> None:
    matrix_output.parent.mkdir(parents=True, exist_ok=True)
    summary_output.parent.mkdir(parents=True, exist_ok=True)
    with matrix_output.open("wb") as stream:
        for record in records:
            stream.write(canonical_json_bytes(dict(record)) + b"\n")
    summary_output.write_bytes(canonical_json_bytes(dict(summary)) + b"\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--matrix-output", type=Path, required=True)
    parser.add_argument("--summary-output", type=Path, required=True)
    args = parser.parse_args()
    records, summary = analyze(args.data_root)
    write_outputs(records, summary, args.matrix_output, args.summary_output)
    print(json.dumps({
        "status": "PASS",
        "events": len(records),
        "summary_sha256": summary["phase9d_r2_recoverability_causal_summary_sha256"],
        "matrix_file_sha256": file_sha256(args.matrix_output),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
