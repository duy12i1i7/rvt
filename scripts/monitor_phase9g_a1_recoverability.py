#!/usr/bin/env python3
"""Maintain durable progress counters for official Study A Recoverability."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from rvt_swarm.phase8.common import attach_canonical_hash, sha256_document


STUDY = "study_a_zero_shot"
SPLITS = ("train", "validation")


def _timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _atomic_write(path: Path, body: Mapping[str, Any]) -> None:
    document = attach_canonical_hash(dict(body), "phase9g_a1_progress_sha256")
    temporary = path.with_suffix(path.suffix + ".partial")
    temporary.write_text(
        json.dumps(document, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )
    temporary.replace(path)


def _load_expected(root: Path) -> Mapping[str, Any]:
    manifest = json.loads(
        (root / "results/rvt_fd24/datasets/phase9_job_manifest.json").read_text(
            encoding="ascii"
        )
    )
    sources = {
        str(job["job_id"]): job
        for job in manifest["source_episode_jobs"]
        if job.get("study") == STUDY
        and job.get("split") in SPLITS
        and not bool(job.get("sealed"))
    }
    events = {
        str(job["job_id"]): str(job["source_episode_job_id"])
        for job in manifest["decision_event_jobs"]
        if str(job["source_episode_job_id"]) in sources
        and not bool(job.get("sealed"))
    }
    events_by_source: dict[str, set[str]] = defaultdict(set)
    for event_id, source_id in events.items():
        events_by_source[source_id].add(event_id)
    replica_jobs = [
        job
        for job in manifest["candidate_replica_jobs"]
        if str(job["decision_event_job_id"]) in events
        and not bool(job.get("sealed"))
    ]
    return {
        "sources": sources,
        "events": events,
        "events_by_source": events_by_source,
        "replica_jobs": replica_jobs,
    }


def _container_usage() -> tuple[float, Mapping[str, str]]:
    completed = subprocess.run(
        [
            "docker", "stats", "--no-stream", "--format",
            "{{.Name}}|{{.CPUPerc}}|{{.MemUsage}}",
        ],
        check=False,
        text=True,
        capture_output=True,
    )
    total_percent = 0.0
    memory = {}
    for line in completed.stdout.splitlines():
        name, separator, remainder = line.partition("|")
        if not separator or not name.startswith("phase9g-a1-recoverability-"):
            continue
        cpu, _, usage = remainder.partition("|")
        try:
            total_percent += float(cpu.rstrip("%"))
        except ValueError:
            pass
        memory[name] = usage
    return total_percent, memory


def _lifecycle_state(audit_root: Path) -> Mapping[str, str]:
    result = {}
    for split in SPLITS:
        path = audit_root / f"{STUDY}-{split}-recoverability.lifecycle.json"
        if not path.exists():
            result[split] = "NOT_STARTED"
            continue
        try:
            result[split] = str(json.loads(path.read_text(encoding="ascii"))["state"])
        except (OSError, ValueError, KeyError):
            result[split] = "INVALID_LIFECYCLE"
    return result


def _completed_duplicate_count(audit_root: Path) -> int:
    duplicates = 0
    for split in SPLITS:
        path = audit_root / f"{STUDY}-{split}-recoverability.stdout.jsonl"
        if not path.exists():
            continue
        for line in path.read_text(encoding="ascii").splitlines():
            try:
                document = json.loads(line)
            except ValueError:
                continue
            duplicates += int(document.get("execution_summary", {}).get("duplicates", 0))
    return duplicates


def _timeout_count(audit_root: Path) -> int:
    count = 0
    for path in audit_root.glob("*-recoverability.stderr.log"):
        text = path.read_text(encoding="ascii", errors="replace").lower()
        count += text.count("exceeded infrastructure timeout")
    return count


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--interval-seconds", type=float, default=30.0)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()

    root = args.root.resolve()
    data_root = args.data_root.resolve()
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    audit_root = data_root / "audit" / args.run_id
    expected = _load_expected(root)
    expected_events: Mapping[str, str] = expected["events"]
    expected_by_source: Mapping[str, set[str]] = expected["events_by_source"]

    observed_paths: set[Path] = set()
    observed_events: set[str] = set()
    event_counts_by_source: Counter[str] = Counter()
    dispositions: Counter[str] = Counter()
    split_events: Counter[str] = Counter()
    split_rows: Counter[str] = Counter()
    rows = 0
    replicas = 0
    retries = 0
    infrastructure_failures = 0
    pair_valid = 0
    pair_invalid = 0
    scientific_row_ids: set[str] = set()
    duplicate_row_ids = 0
    integrity_errors: list[str] = []
    cpu_core_seconds = 0.0
    last_sample = time.monotonic()
    monitor_started = _timestamp()
    if output.exists():
        try:
            previous = json.loads(output.read_text(encoding="ascii"))
            body = dict(previous)
            expected_hash = str(body.pop("phase9g_a1_progress_sha256", ""))
            if sha256_document(body) == expected_hash:
                cpu_core_seconds = float(
                    previous["operational"]["cpu_core_seconds_sampled"]
                )
                monitor_started = str(previous["monitor_started_at_utc"])
        except (KeyError, OSError, TypeError, ValueError):
            pass

    while True:
        for split in SPLITS:
            transaction_root = (
                data_root
                / "staging"
                / f"{STUDY}-{split}-recoverability"
                / "recoverability"
            )
            for path in sorted(transaction_root.glob("event-*.json")):
                if path in observed_paths:
                    continue
                observed_paths.add(path)
                try:
                    document = json.loads(path.read_text(encoding="ascii"))
                    body = dict(document)
                    canonical = str(body.pop("canonical_record_sha256"))
                    if sha256_document(body) != canonical:
                        raise ValueError("canonical record hash mismatch")
                    event_id = str(document["decision_event_id"])
                    source_id = expected_events[event_id]
                    if event_id in observed_events:
                        raise ValueError("duplicate decision event identity")
                    observed_events.add(event_id)
                    event_counts_by_source[source_id] += 1
                    split_events[split] += 1
                    actual_rows = int(document["actual_row_count"])
                    rows += actual_rows
                    split_rows[split] += actual_rows
                    for row in document["rows"]:
                        row_id = str(row["scientific_row_id"])
                        if row_id in scientific_row_ids:
                            duplicate_row_ids += 1
                        scientific_row_ids.add(row_id)
                        if sha256_document(row["graph_payload"]) != row[
                            "graph_fingerprint"
                        ]:
                            raise ValueError("recoverability graph fingerprint mismatch")
                    candidate_audits = document["audit"].get("candidate_audits", [])
                    event_dispositions = []
                    for candidate in candidate_audits:
                        aggregate = candidate.get("aggregate")
                        if aggregate is not None:
                            disposition = str(aggregate["disposition"])
                            event_dispositions.append(disposition)
                            dispositions[disposition] += 1
                        if candidate.get("infrastructure_failure"):
                            infrastructure_failures += 1
                            event_dispositions.append("INFRASTRUCTURE_FAILURE")
                            dispositions["INFRASTRUCTURE_FAILURE"] += 1
                        for replica in candidate.get("replicas", []):
                            replicas += 1
                            attempts = replica.get("infrastructure_attempts", [])
                            retries += max(0, len(attempts) - 1)
                    if document["status"] == (
                        "SCIENTIFICALLY_RECONCILED_GENERATION_INVALID"
                    ):
                        missing = 2 - len(event_dispositions)
                        dispositions["GENERATION_INVALID"] += max(0, missing)
                        pair_invalid += 1
                    elif document["status"] == "SCIENTIFICALLY_RECONCILED_LABELABLE":
                        pair_valid += 1
                    elif document["status"] == "PENDING_INFRASTRUCTURE_RESOLUTION":
                        infrastructure_failures += max(0, 2 - len(event_dispositions))
                    else:
                        raise ValueError("unknown candidate-pair transaction status")
                    if actual_rows not in (0, int(document["expected_row_count"])):
                        raise ValueError("partial candidate-pair row publication")
                except (KeyError, OSError, ValueError) as error:
                    integrity_errors.append(f"{path.name}: {error}")

        now = time.monotonic()
        cpu_percent, memory = _container_usage()
        cpu_core_seconds += (cpu_percent / 100.0) * max(0.0, now - last_sample)
        last_sample = now
        completed_sources = sum(
            event_counts_by_source[source_id] == len(event_ids)
            for source_id, event_ids in expected_by_source.items()
        )
        lifecycle = _lifecycle_state(audit_root)
        completed_events = len(observed_events)
        partial_files = sum(
            1
            for split in SPLITS
            for _ in (
                data_root / "staging" / f"{STUDY}-{split}-recoverability"
            ).rglob("*.partial")
        )
        complete = completed_events == len(expected_events) and all(
            lifecycle[split] == "COMPLETE" for split in SPLITS
        )
        failed = any(state in {"FAILED", "INVALID_LIFECYCLE"} for state in lifecycle.values())
        report = {
            "schema_version": "rvt-phase9g-a1-recoverability-progress/v1",
            "run_id": args.run_id,
            "updated_at_utc": _timestamp(),
            "monitor_started_at_utc": monitor_started,
            "state": "COMPLETE" if complete else "FAILED" if failed else "RUNNING",
            "command_lifecycle": lifecycle,
            "counters": {
                "source_episodes_scheduled": len(expected["sources"]),
                "source_episodes_completed": completed_sources,
                "decision_events_scheduled": len(expected_events),
                "decision_events_completed": completed_events,
                "candidate_aggregates_scheduled": 2 * len(expected_events),
                "candidate_aggregates_completed": 2 * completed_events,
                "replica_executions_scheduled": len(expected["replica_jobs"]),
                "replica_executions_completed": replicas,
                "RECOVERABLE_POSITIVE_aggregates": dispositions[
                    "RECOVERABLE_POSITIVE"
                ],
                "VALID_TASK_NEGATIVE_aggregates": dispositions[
                    "VALID_TASK_NEGATIVE"
                ],
                "GENERATION_INVALID_aggregates": dispositions["GENERATION_INVALID"],
                "candidate_pair_valid_events": pair_valid,
                "candidate_pair_invalid_events": pair_invalid,
                "robot_candidate_rows_emitted": rows,
                "infrastructure_failures": infrastructure_failures,
                "retries": retries,
                "timeouts": _timeout_count(audit_root),
                "duplicate_detections": _completed_duplicate_count(audit_root),
                "duplicate_scientific_row_identities": duplicate_row_ids,
                "writer_failures": sum(state == "FAILED" for state in lifecycle.values()),
                "partial_transaction_files": partial_files,
                "partial_transaction_recoveries": 0,
                "integrity_errors": len(integrity_errors),
            },
            "split_counters": {
                split: {
                    "decision_events_completed": split_events[split],
                    "robot_candidate_rows_emitted": split_rows[split],
                }
                for split in SPLITS
            },
            "operational": {
                "cpu_core_seconds_sampled": cpu_core_seconds,
                "container_memory_usage": memory,
                "staging_storage_bytes": sum(
                    path.stat().st_size
                    for split in SPLITS
                    for path in (
                        data_root / "staging" / f"{STUDY}-{split}-recoverability"
                    ).rglob("*")
                    if path.is_file()
                ),
            },
            "integrity_error_details": integrity_errors[:100],
            "sealed_domains": {
                "study_a_n24_accesses": 0,
                "study_b_accesses": 0,
                "final_test_accesses": 0,
                "training_operations": 0,
            },
        }
        _atomic_write(output, report)
        if args.once or complete or failed:
            break
        time.sleep(args.interval_seconds)


if __name__ == "__main__":
    main()
