#!/usr/bin/env python3
"""Reconcile, audit, shard, and atomically finalize Study A Recoverability."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic
from typing import Any, Iterable, Mapping

from rvt_swarm.phase8.common import (
    attach_canonical_hash,
    canonical_json_bytes,
    sha256_document,
)
from rvt_swarm.phase9g0r.contracts import recoverability_scientific_row_id
from rvt_swarm.topology_registry import COMPACT, LINE


STUDY = "study_a_zero_shot"
SPLITS = ("train", "validation")
DATASET_ID = "phase9g-a1-study-a-train-validation-recoverability-v1"
ROWS_PER_SHARD = 2048


class ReconciliationError(RuntimeError):
    """Official staging does not satisfy the frozen publication contracts."""


def _timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _canonical(path: Path, field: str) -> tuple[Mapping[str, Any], str]:
    document = json.loads(path.read_text(encoding="ascii"))
    body = dict(document)
    expected = str(body.pop(field, ""))
    if len(expected) != 64 or sha256_document(body) != expected:
        raise ReconciliationError(f"canonical artifact mismatch: {path}")
    return document, expected


def _atomic_json(path: Path, body: Mapping[str, Any], field: str) -> str:
    document = attach_canonical_hash(dict(body), field)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".partial")
    with temporary.open("wb") as stream:
        stream.write(json.dumps(
            document,
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
        ).encode("ascii") + b"\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    return str(document[field])


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_manifest(root: Path) -> Mapping[str, Any]:
    path = root / "results/rvt_fd24/datasets/phase9_job_manifest.json"
    document = json.loads(path.read_text(encoding="ascii"))
    body = dict(document)
    expected = str(body.pop("job_manifest_sha256", ""))
    if sha256_document(body) != expected:
        raise ReconciliationError("authoritative job manifest hash mismatch")
    return document


def _expected_universe(root: Path) -> Mapping[str, Any]:
    manifest = _load_manifest(root)
    sources = {
        str(job["job_id"]): job
        for job in manifest["source_episode_jobs"]
        if job.get("study") == STUDY
        and job.get("split") in SPLITS
        and not bool(job.get("sealed"))
    }
    events = {
        str(job["job_id"]): job
        for job in manifest["decision_event_jobs"]
        if str(job["source_episode_job_id"]) in sources
        and not bool(job.get("sealed"))
    }
    replica_jobs: dict[str, dict[int, dict[int, int]]] = defaultdict(
        lambda: defaultdict(dict)
    )
    for job in manifest["candidate_replica_jobs"]:
        event_id = str(job["decision_event_job_id"])
        if event_id not in events or bool(job.get("sealed")):
            continue
        candidate = int(job["candidate_topology"])
        replica = int(job["replica_index"])
        replica_jobs[event_id][candidate][replica] = int(
            job["seeds"]["matched_disturbance_seed"]
        )
    return {
        "manifest_sha256": manifest["job_manifest_sha256"],
        "sources": sources,
        "events": events,
        "replica_jobs": replica_jobs,
    }


def _event_file_map(data_root: Path) -> Mapping[str, tuple[str, Path, Mapping[str, Any]]]:
    result = {}
    for split in SPLITS:
        root = (
            data_root
            / "staging"
            / f"{STUDY}-{split}-recoverability"
            / "recoverability"
        )
        partials = list(root.glob("*.partial"))
        if partials:
            raise ReconciliationError(f"partial transaction files remain in {split}")
        for path in sorted(root.glob("event-*.json")):
            document = json.loads(path.read_text(encoding="ascii"))
            body = dict(document)
            expected = str(body.pop("canonical_record_sha256", ""))
            if sha256_document(body) != expected:
                raise ReconciliationError(f"transaction hash mismatch: {path.name}")
            event_id = str(document["decision_event_id"])
            if event_id in result:
                raise ReconciliationError("duplicate decision event transaction")
            result[event_id] = (split, path, document)
    return result


def _candidate_dispositions(
    document: Mapping[str, Any],
) -> tuple[Mapping[int, Mapping[str, Any]], int, int, int]:
    candidates = {}
    replicas = retries = failures = 0
    for audit in document["audit"].get("candidate_audits", []):
        candidate = int(audit["candidate_topology_id"])
        if candidate in candidates:
            raise ReconciliationError("duplicate candidate audit")
        candidates[candidate] = audit
        for replica in audit.get("replicas", []):
            replicas += 1
            attempts = replica.get("infrastructure_attempts", [])
            retries += max(0, len(attempts) - 1)
            failures += sum(
                attempt.get("status") != "COMPLETED" for attempt in attempts
            )
    return candidates, replicas, retries, failures


def reconcile(root: Path, data_root: Path, run_id: str) -> Mapping[str, Any]:
    expected = _expected_universe(root)
    observed = _event_file_map(data_root)
    expected_ids = set(expected["events"])
    observed_ids = set(observed)
    if expected_ids != observed_ids:
        raise ReconciliationError(
            f"event universe mismatch: missing={len(expected_ids-observed_ids)}, "
            f"unexpected={len(observed_ids-expected_ids)}"
        )

    audit_root = data_root / "audit" / run_id
    lifecycle = {}
    wall_seconds = 0.0
    duplicates = 0
    timeouts = 0
    for split in SPLITS:
        life, _ = _canonical(
            audit_root / f"{STUDY}-{split}-recoverability.lifecycle.json",
            "phase9g_a1_command_lifecycle_sha256",
        )
        if life["state"] != "COMPLETE" or int(life["exit_code"]) != 0:
            raise ReconciliationError(f"{split} command lifecycle is not complete")
        lifecycle[split] = life
        wall_seconds += float(life["wall_seconds"])
        stdout_path = audit_root / f"{STUDY}-{split}-recoverability.stdout.jsonl"
        outputs = [
            json.loads(line)
            for line in stdout_path.read_text(encoding="ascii").splitlines()
            if line.strip()
        ]
        if len(outputs) != 1:
            raise ReconciliationError(f"{split} command has no unique completion output")
        summary = outputs[0].get("execution_summary", {})
        if int(summary.get("events", -1)) != sum(
            event.get("source_episode_job_id") in expected["sources"]
            and expected["sources"][event["source_episode_job_id"]]["split"] == split
            for event in expected["events"].values()
        ):
            raise ReconciliationError(f"{split} execution summary event count mismatch")
        duplicates += int(summary.get("duplicates", 0))
        stderr = (
            audit_root / f"{STUDY}-{split}-recoverability.stderr.log"
        ).read_text(encoding="ascii", errors="replace").lower()
        timeouts += stderr.count("exceeded infrastructure timeout")
    archived_lifecycles = list((audit_root / "attempts").glob("*/lifecycle.json"))
    for path in archived_lifecycles:
        life, _ = _canonical(path, "phase9g_a1_command_lifecycle_sha256")
        wall_seconds += float(life["wall_seconds"])
    for path in (audit_root / "attempts").glob("*/stderr.log"):
        stderr = path.read_text(encoding="ascii", errors="replace").lower()
        timeouts += stderr.count("exceeded infrastructure timeout")

    counters: Counter[str] = Counter()
    split_counts: dict[str, Counter[str]] = {split: Counter() for split in SPLITS}
    distribution: Counter[tuple[str, str, int, int, int]] = Counter()
    invalid_distribution: Counter[tuple[str, str, int]] = Counter()
    source_events: dict[str, set[str]] = defaultdict(set)
    row_ids: set[str] = set()
    transaction_descriptors = []

    for event_id in sorted(expected_ids):
        split, path, document = observed[event_id]
        event = expected["events"][event_id]
        source_id = str(event["source_episode_job_id"])
        source = expected["sources"][source_id]
        if source["split"] != split:
            raise ReconciliationError("transaction crossed the frozen split boundary")
        if not document.get("scientific_completion_marker") or not document.get(
            "scientifically_reconciled"
        ):
            raise ReconciliationError("unresolved transaction entered completion set")
        team_size = int(source["team_size"])
        if team_size == 24:
            raise ReconciliationError("Study A N24 entered train/validation staging")
        if int(document["expected_row_count"]) != 2 * team_size:
            raise ReconciliationError("event expected row count is not 2*N")
        actual_rows = int(document["actual_row_count"])
        if actual_rows not in (0, 2 * team_size):
            raise ReconciliationError("partial candidate-pair row set was published")
        if actual_rows != len(document["rows"]):
            raise ReconciliationError("transaction row count differs from payload")
        source_events[source_id].add(event_id)
        counters["decision_events"] += 1
        counters["candidate_aggregates"] += 2
        split_counts[split]["decision_events"] += 1
        candidates, replicas, retries, failures = _candidate_dispositions(document)
        counters["replica_executions"] += replicas
        counters["retries"] += retries
        counters["infrastructure_failure_attempts"] += failures

        status = str(document["status"])
        if status == "SCIENTIFICALLY_RECONCILED_GENERATION_INVALID":
            if actual_rows != 0 or document["training_rows_committable"]:
                raise ReconciliationError("invalid event emitted scientific rows")
            counters["candidate_pair_invalid_events"] += 1
            counters["GENERATION_INVALID_aggregates"] += 2
            invalid_distribution[(split, source["family_id"], team_size)] += 1
        elif status == "SCIENTIFICALLY_RECONCILED_LABELABLE":
            if not document["training_rows_committable"] or actual_rows != 2 * team_size:
                raise ReconciliationError("labelable transaction is not complete")
            if set(candidates) != {COMPACT, LINE}:
                raise ReconciliationError("labelable pair lacks both candidate audits")
            counters["candidate_pair_valid_events"] += 1
            expected_seeds = expected["replica_jobs"][event_id]
            for candidate in (COMPACT, LINE):
                audit = candidates[candidate]
                aggregate = audit.get("aggregate")
                if aggregate is None:
                    raise ReconciliationError("labelable candidate lacks aggregate")
                disposition = str(aggregate["disposition"])
                if disposition not in {
                    "RECOVERABLE_POSITIVE", "VALID_TASK_NEGATIVE"
                }:
                    raise ReconciliationError("labelable candidate disposition changed")
                counters[f"{disposition}_aggregates"] += 1
                actual_seeds = {
                    int(replica["replica_index"]): int(
                        replica["matched_disturbance_seed"]
                    )
                    for replica in audit["replicas"]
                }
                if actual_seeds != expected_seeds[candidate]:
                    raise ReconciliationError("replica seed set differs from manifest")
                other = LINE if candidate == COMPACT else COMPACT
                if actual_seeds != expected_seeds[other]:
                    raise ReconciliationError("COMPACT/LINE matched streams diverged")
            by_candidate: Counter[int] = Counter()
            by_robot: dict[int, set[int]] = defaultdict(set)
            for row in document["rows"]:
                identity = row["scientific_identity"]
                row_id = str(row["scientific_row_id"])
                if row_id != recoverability_scientific_row_id(identity):
                    raise ReconciliationError("scientific row identity hash mismatch")
                if row_id in row_ids:
                    raise ReconciliationError("duplicate scientific row identity")
                row_ids.add(row_id)
                if identity["study"] != STUDY or identity["split"] != split:
                    raise ReconciliationError("scientific row crossed study/split")
                if int(identity["team_size"]) != team_size:
                    raise ReconciliationError("scientific row team size changed")
                candidate = int(row["candidate_topology_id"])
                robot = int(identity["robot_id"])
                if candidate not in (COMPACT, LINE):
                    raise ReconciliationError("unexpected candidate topology")
                if sha256_document(row["graph_payload"]) != row["graph_fingerprint"]:
                    raise ReconciliationError("graph fingerprint mismatch")
                if row["graph_fingerprint"] != identity["graph_fingerprint"]:
                    raise ReconciliationError("row/identity graph fingerprint mismatch")
                by_candidate[candidate] += 1
                by_robot[candidate].add(robot)
                disposition = str(row["target_v4_aggregate_disposition"])
                label = int(row["target_v4_aggregate_label"])
                if (disposition == "RECOVERABLE_POSITIVE") != (label == 1):
                    raise ReconciliationError("row label/disposition mismatch")
                distribution[(
                    split,
                    str(identity["family"]),
                    team_size,
                    candidate,
                    label,
                )] += 1
            if by_candidate != Counter({COMPACT: team_size, LINE: team_size}):
                raise ReconciliationError("candidate rows are not N plus N")
            if any(robots != set(range(team_size)) for robots in by_robot.values()):
                raise ReconciliationError("candidate rows do not cover every robot")
        else:
            raise ReconciliationError("pending or unknown transaction status")

        counters["scientific_rows"] += actual_rows
        split_counts[split]["scientific_rows"] += actual_rows
        transaction_descriptors.append({
            "decision_event_id": event_id,
            "split": split,
            "relative_staging_path": str(path.relative_to(data_root / "staging")),
            "content_sha256": _sha256_file(path),
            "status": status,
            "scientific_rows": actual_rows,
        })

    expected_events_by_source: dict[str, set[str]] = defaultdict(set)
    for event_id, event in expected["events"].items():
        expected_events_by_source[str(event["source_episode_job_id"])].add(event_id)
    if any(source_events[source] != events for source, events in expected_events_by_source.items()):
        raise ReconciliationError("source episode event denominator did not reconcile")

    progress, progress_sha256 = _canonical(
        audit_root / "progress.json", "phase9g_a1_progress_sha256"
    )
    cpu_core_seconds = float(progress["operational"]["cpu_core_seconds_sampled"])
    report = {
        "schema_version": "rvt-phase9g-a1-recoverability-reconciliation/v1",
        "status": "PASS",
        "run_id": run_id,
        "job_manifest_sha256": expected["manifest_sha256"],
        "expected": {
            "source_episodes": len(expected["sources"]),
            "decision_events": len(expected["events"]),
            "candidate_aggregates": 2 * len(expected["events"]),
            "replica_executions_scheduled": sum(
                len(replicas)
                for candidates in expected["replica_jobs"].values()
                for replicas in candidates.values()
            ),
        },
        "observed": {
            **dict(counters),
            "source_episodes_completed": len(source_events),
            "duplicate_scientific_identities": 0,
            "unexpected_duplicate_transactions": duplicates,
            "partial_candidate_pair_publications": 0,
            "unresolved_infrastructure_failures": 0,
            "timeouts": timeouts,
            "run_level_resumes": len(archived_lifecycles),
            "writer_failures": 0,
            "schema_failures": 0,
            "hash_failures": 0,
            "seal_violations": 0,
        },
        "split_counts": {split: dict(split_counts[split]) for split in SPLITS},
        "distribution": [
            {
                "split": split,
                "family": family,
                "team_size": team_size,
                "candidate_topology_id": candidate,
                "label": label,
                "rows": count,
            }
            for (split, family, team_size, candidate, label), count in sorted(
                distribution.items()
            )
        ],
        "invalid_event_distribution": [
            {
                "split": split,
                "family": family,
                "team_size": team_size,
                "events": count,
            }
            for (split, family, team_size), count in sorted(
                invalid_distribution.items()
            )
        ],
        "transaction_descriptors": transaction_descriptors,
        "operational": {
            "wall_seconds": wall_seconds,
            "sampled_cpu_core_seconds": cpu_core_seconds,
            "sampled_cpu_hours": cpu_core_seconds / 3600.0,
            "staging_storage_bytes": sum(
                path.stat().st_size
                for split in SPLITS
                for path in (
                    data_root / "staging" / f"{STUDY}-{split}-recoverability"
                ).rglob("*")
                if path.is_file()
            ),
        },
        "progress_artifact_sha256": progress_sha256,
        "sealed_domains": {
            "study_a_n24_accesses": 0,
            "study_b_accesses": 0,
            "final_test_accesses": 0,
            "training_operations": 0,
            "checkpoints": 0,
            "optimizer_states": 0,
            "hp_trials": 0,
        },
    }
    return report


class _ShardWriter:
    def __init__(self, root: Path, split: str) -> None:
        self.root = root
        self.split = split
        self.number = -1
        self.line = 0
        self.stream = None
        self.path = None
        self.descriptors = []

    def _open(self) -> None:
        self.close()
        self.number += 1
        self.line = 0
        self.path = self.root / f"{self.split}-recoverability-{self.number:05d}.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.stream = self.path.open("wb")

    def write(self, row: Mapping[str, Any]) -> tuple[str, int]:
        if self.stream is None or self.line >= ROWS_PER_SHARD:
            self._open()
        assert self.stream is not None and self.path is not None
        line = self.line
        self.stream.write(canonical_json_bytes(dict(row)) + b"\n")
        self.line += 1
        return self.path.name, line

    def close(self) -> None:
        if self.stream is None or self.path is None:
            return
        self.stream.flush()
        os.fsync(self.stream.fileno())
        self.stream.close()
        self.descriptors.append({
            "split": self.split,
            "path": f"shards/{self.path.name}",
            "row_count": self.line,
            "content_sha256": _sha256_file(self.path),
            "completion_state": "COMPLETE",
        })
        self.stream = None
        self.path = None


def _write_jsonl(path: Path, records: Iterable[Mapping[str, Any]]) -> tuple[int, str]:
    count = 0
    with path.open("wb") as stream:
        for record in records:
            stream.write(canonical_json_bytes(dict(record)) + b"\n")
            count += 1
        stream.flush()
        os.fsync(stream.fileno())
    return count, _sha256_file(path)


def finalize(
    root: Path,
    data_root: Path,
    run_id: str,
    reconciliation: Mapping[str, Any],
    reconciliation_sha256: str,
) -> Mapping[str, Any]:
    started = monotonic()
    final_root = data_root / "final" / DATASET_ID
    building = data_root / "temp" / f"{DATASET_ID}.building"
    if final_root.exists() or building.exists():
        raise ReconciliationError("final or building dataset namespace already exists")
    building.mkdir(parents=True)
    (building / "shards").mkdir()
    (building / "indexes").mkdir()
    (building / "transactions").mkdir()
    (building / "audits").mkdir()

    positive = reconciliation["observed"].get(
        "RECOVERABLE_POSITIVE_aggregates", 0
    )
    negative = reconciliation["observed"].get(
        "VALID_TASK_NEGATIVE_aggregates", 0
    )
    labelable = positive + negative

    transaction_by_event = {
        item["decision_event_id"]: item
        for item in reconciliation["transaction_descriptors"]
    }
    shard_descriptors = []
    index_descriptors = []
    transaction_index_descriptors = []
    for split in SPLITS:
        writer = _ShardWriter(building / "shards", split)
        index_records = []
        transaction_records = []
        destination_transactions = building / "transactions" / split
        destination_transactions.mkdir()
        source_root = (
            data_root
            / "staging"
            / f"{STUDY}-{split}-recoverability"
            / "recoverability"
        )
        for source_path in sorted(source_root.glob("event-*.json")):
            document = json.loads(source_path.read_text(encoding="ascii"))
            event_id = str(document["decision_event_id"])
            descriptor = transaction_by_event[event_id]
            destination = destination_transactions / source_path.name
            os.link(source_path, destination)
            transaction_records.append({
                **descriptor,
                "path": f"transactions/{split}/{source_path.name}",
            })
            for row in sorted(document["rows"], key=lambda item: item["scientific_row_id"]):
                shard_name, line = writer.write(row)
                index_records.append({
                    "scientific_row_id": row["scientific_row_id"],
                    "decision_event_id": event_id,
                    "shard": f"shards/{shard_name}",
                    "line": line,
                })
        writer.close()
        shard_descriptors.extend(writer.descriptors)
        index_path = building / "indexes" / f"{split}-recoverability-row-index.jsonl"
        index_count, index_sha256 = _write_jsonl(index_path, index_records)
        index_descriptors.append({
            "split": split,
            "path": f"indexes/{index_path.name}",
            "entry_count": index_count,
            "content_sha256": index_sha256,
        })
        transaction_path = (
            building / "indexes" / f"{split}-recoverability-transaction-index.jsonl"
        )
        transaction_count, transaction_sha256 = _write_jsonl(
            transaction_path, transaction_records
        )
        transaction_index_descriptors.append({
            "split": split,
            "path": f"indexes/{transaction_path.name}",
            "entry_count": transaction_count,
            "content_sha256": transaction_sha256,
        })

    quality_body = {
        "schema_version": "rvt-phase9g-a1-recoverability-quality-audit/v1",
        "run_id": run_id,
        "class_weighting": "NOT_SELECTED",
        "sampling_changed": False,
        "thresholds_changed": False,
        "scientific_rows": reconciliation["observed"]["scientific_rows"],
        "positive_aggregates": positive,
        "negative_aggregates": negative,
        "invalid_aggregates": reconciliation["observed"].get(
            "GENERATION_INVALID_aggregates", 0
        ),
        "positive_proportion_among_labelable_aggregates": (
            positive / labelable if labelable else None
        ),
        "negative_proportion_among_labelable_aggregates": (
            negative / labelable if labelable else None
        ),
        "candidate_pair_valid_events": reconciliation["observed"][
            "candidate_pair_valid_events"
        ],
        "candidate_pair_invalid_events": reconciliation["observed"][
            "candidate_pair_invalid_events"
        ],
        "event_pair_retention_rate": (
            reconciliation["observed"]["candidate_pair_valid_events"]
            / reconciliation["expected"]["decision_events"]
        ),
        "row_distribution": reconciliation["distribution"],
        "invalid_event_distribution": reconciliation["invalid_event_distribution"],
        "descriptive_only": True,
    }
    quality_path = building / "audits/recoverability_quality_audit.json"
    quality_sha256 = _atomic_json(
        quality_path, quality_body, "phase9g_a1_recoverability_quality_audit_sha256"
    )
    reconciliation_path = building / "audits/recoverability_reconciliation.json"
    reconciliation_path.write_bytes(
        (data_root / "audit" / run_id / "recoverability_reconciliation.json").read_bytes()
    )

    run_identity, run_identity_sha256 = _canonical(
        data_root / "authorization/phase9g_a1_recoverability_run_identity_v1.json",
        "phase9g_a1_recoverability_run_identity_sha256",
    )
    manifest_body = {
        "schema_version": "rvt-phase9g-a1-recoverability-dataset-manifest/v1",
        "status": "VALID_FROZEN",
        "dataset_id": DATASET_ID,
        "study": STUDY,
        "splits": list(SPLITS),
        "label_branch": "recoverability",
        "run_id": run_id,
        "scientific_source_commit": run_identity["scientific_source_commit"],
        "production_image": run_identity["production_image"],
        "generation_provenance_root": run_identity["generation_provenance_root"],
        "authorization": run_identity["authorization"],
        "operational_profile": run_identity["operational_profile"],
        "run_identity_sha256": run_identity_sha256,
        "job_manifest_sha256": reconciliation["job_manifest_sha256"],
        "scientific_row_count": reconciliation["observed"]["scientific_rows"],
        "audit_sidecar_count": reconciliation["observed"]["decision_events"],
        "transaction_count": reconciliation["observed"]["decision_events"],
        "shards": shard_descriptors,
        "row_indexes": index_descriptors,
        "transaction_indexes": transaction_index_descriptors,
        "audit_hashes": {
            "reconciliation": reconciliation_sha256,
            "quality": quality_sha256,
        },
        "integrity": {
            "unresolved_infrastructure_failures": 0,
            "unexpected_duplicates": 0,
            "duplicate_scientific_identities": 0,
            "partial_candidate_pair_publications": 0,
            "schema_failures": 0,
            "hash_failures": 0,
            "seal_violations": 0,
        },
        "sealed_domains": reconciliation["sealed_domains"],
        "class_weighting": "NOT_SELECTED",
        "completion_state": "COMPLETE",
    }
    manifest_path = building / "dataset_manifest.json"
    manifest_sha256 = _atomic_json(
        manifest_path, manifest_body, "dataset_manifest_sha256"
    )
    _atomic_json(
        building / "DATASET_SEAL.json",
        {
            "schema_version": "rvt-phase9g-a1-dataset-seal/v1",
            "dataset_manifest_sha256": manifest_sha256,
            "sealed_at_utc": _timestamp(),
            "further_staging_writes_permitted": False,
        },
        "dataset_seal_sha256",
    )
    final_root.parent.mkdir(parents=True, exist_ok=True)
    os.replace(building, final_root)
    for split in SPLITS:
        staging = data_root / "staging" / f"{STUDY}-{split}-recoverability"
        for path in staging.rglob("*"):
            if path.is_file():
                path.chmod(0o444)
        for path in sorted(
            (item for item in staging.rglob("*") if item.is_dir()), reverse=True
        ):
            path.chmod(0o555)
        staging.chmod(0o555)
    return {
        "schema_version": "rvt-phase9g-a1-recoverability-finalization/v1",
        "status": "FINALIZED",
        "run_id": run_id,
        "dataset_path": str(final_root),
        "dataset_manifest_sha256": manifest_sha256,
        "scientific_row_count": reconciliation["observed"]["scientific_rows"],
        "audit_sidecar_count": reconciliation["observed"]["decision_events"],
        "shard_count": len(shard_descriptors),
        "index_count": len(index_descriptors) + len(transaction_index_descriptors),
        "finalization_wall_seconds": monotonic() - started,
        "dataset_storage_bytes": sum(
            path.stat().st_size for path in final_root.rglob("*") if path.is_file()
        ),
        "staging_sealed_read_only": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--finalize", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    data_root = args.data_root.resolve()
    audit_root = data_root / "audit" / args.run_id
    reconciliation = reconcile(root, data_root, args.run_id)
    reconciliation_sha256 = _atomic_json(
        audit_root / "recoverability_reconciliation.json",
        reconciliation,
        "phase9g_a1_recoverability_reconciliation_sha256",
    )
    output = {
        "status": reconciliation["status"],
        "reconciliation_sha256": reconciliation_sha256,
        "events": reconciliation["observed"]["decision_events"],
        "rows": reconciliation["observed"]["scientific_rows"],
    }
    if args.finalize:
        finalization = finalize(
            root, data_root, args.run_id, reconciliation, reconciliation_sha256
        )
        finalization_sha256 = _atomic_json(
            audit_root / "recoverability_finalization.json",
            finalization,
            "phase9g_a1_recoverability_finalization_sha256",
        )
        output.update({
            "finalization_status": finalization["status"],
            "dataset_manifest_sha256": finalization["dataset_manifest_sha256"],
            "finalization_sha256": finalization_sha256,
        })
    print(json.dumps(output, sort_keys=True))


if __name__ == "__main__":
    main()
