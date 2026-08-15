#!/usr/bin/env python3
"""Read-only integrity and label audit for finalized Recoverability datasets."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping

from rvt_swarm.phase8.common import (
    attach_canonical_hash,
    canonical_json_bytes,
    sha256_document,
)
from rvt_swarm.phase9g0r.contracts import recoverability_scientific_row_id
from rvt_swarm.topology_registry import COMPACT, LINE


TRAIN_DATASET_ID = "phase9g-a1-study-a-train-recoverability-v1"
VALIDATION_DATASET_ID = "phase9g-a1-study-a-validation-recoverability-v1"
COMBINED_DATASET_ID = "phase9g-a1-study-a-recoverability-train-validation-root-v1"
STUDY = "study_a_zero_shot"
EXPECTED_MANIFESTS = {
    "train": "4ac3d2cb65a8b5d656a5d982b344466868f8deaa8cef2b93af7ce824e9387caf",
    "validation": "c991aa3016b38b524a14d9b7037b63d97c2cbbb7d92279fc5a297b9c55d4989e",
}
EXPECTED_SEALS = {
    "train": "5b9e6726b548722ee651eefa7106662e2b119147d9b0c31ec4d4cbe0a1de58f5",
    "validation": "c7583b124c573c52b57cd91dc1b54aff8fc02b33cf0a15d5449936a8d540637f",
}
EXPECTED_COMBINED_ROOT = "7e583ef98184767edfb95387ecc23d2ab266e2137db28a9fbb3badccaa495672"
EXPECTED_COMBINED_SEAL = "4fd9dda517eb5deed890ed5ac8ab5cc64841ab6c0a0a7a4047dd7b569cfb1f17"
TOPOLOGY_NAMES = {COMPACT: "COMPACT", LINE: "LINE"}
EVENT_RE = re.compile(
    r"/source_episode/study_a_zero_shot/(train|validation)/(F(?:10|[1-9]))/"
    r"([0-9a-f]{64})/N(5|6|8|12|16)/([^/]+)/episode-(\d+)/event-(\d+)$"
)


class ReadOnlyAuditError(RuntimeError):
    """A frozen dataset violates its published contract."""


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical(path: Path, field: str) -> tuple[dict[str, Any], str]:
    document = json.loads(path.read_text(encoding="ascii"))
    body = dict(document)
    expected = str(body.pop(field, ""))
    if len(expected) != 64 or sha256_document(body) != expected:
        raise ReadOnlyAuditError(f"canonical hash mismatch: {path}")
    return document, expected


def _jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("rb") as stream:
        for number, line in enumerate(stream, start=1):
            if not line.endswith(b"\n"):
                raise ReadOnlyAuditError(f"unterminated JSONL: {path}:{number}")
            record = json.loads(line)
            if line != canonical_json_bytes(record) + b"\n":
                raise ReadOnlyAuditError(f"noncanonical JSONL: {path}:{number}")
            yield record


def _records(counter: Mapping[tuple[Any, ...], int], fields: tuple[str, ...]) -> list[dict[str, Any]]:
    return [
        {**dict(zip(fields, key)), "count": int(value)}
        for key, value in sorted(counter.items())
    ]


def _tree_checkpoint(path: Path) -> dict[str, Any]:
    inventory = []
    writable_files = 0
    total_bytes = 0
    for item in sorted(candidate for candidate in path.rglob("*") if candidate.is_file()):
        relative = item.relative_to(path).as_posix()
        size = item.stat().st_size
        mode = item.stat().st_mode & 0o777
        writable_files += int(bool(mode & 0o222))
        total_bytes += size
        inventory.append({
            "path": relative,
            "size_bytes": size,
            "mode_octal": oct(mode),
            "content_sha256": _file_sha256(item),
        })
    return {
        "inventory_sha256": sha256_document({"files": inventory}),
        "file_count": len(inventory),
        "total_bytes": total_bytes,
        "writable_files": writable_files,
    }


def _event_identity(event_id: str) -> dict[str, Any]:
    match = EVENT_RE.search(event_id)
    if match is None:
        raise ReadOnlyAuditError(f"unexpected decision-event identity: {event_id}")
    split, family, layout_sha, team_size, source_class, episode, event = match.groups()
    return {
        "split": split,
        "family": family,
        "layout_sha256": layout_sha,
        "team_size": int(team_size),
        "source_class": source_class,
        "episode_index": int(episode),
        "event_index": int(event),
        "source_episode_id": event_id.rsplit("/event-", 1)[0],
    }


def _validate_descriptors(final: Path, manifest: Mapping[str, Any]) -> None:
    fields = ("shards", "row_indexes", "transaction_indexes")
    for field in fields:
        for descriptor in manifest[field]:
            path = final / str(descriptor["path"])
            if not path.is_file() or _file_sha256(path) != descriptor["content_sha256"]:
                raise ReadOnlyAuditError(f"published descriptor mismatch: {path}")


def _candidate_replicas(
    candidate_audits: Iterable[Mapping[str, Any]],
) -> dict[int, list[Mapping[str, Any]]]:
    result = {}
    for audit in candidate_audits:
        candidate = int(audit["candidate_topology_id"])
        if candidate in result:
            raise ReadOnlyAuditError("duplicate candidate audit")
        result[candidate] = list(audit.get("replicas", []))
    return result


def _analyze_split(data_root: Path, split: str, dataset_id: str) -> dict[str, Any]:
    final = data_root / "final" / dataset_id
    staging = data_root / "staging" / f"{STUDY}-{split}-recoverability"
    manifest, manifest_sha = _canonical(final / "dataset_manifest.json", "dataset_manifest_sha256")
    seal, seal_sha = _canonical(final / "DATASET_SEAL.json", "dataset_seal_sha256")
    if manifest_sha != EXPECTED_MANIFESTS[split] or seal_sha != EXPECTED_SEALS[split]:
        raise ReadOnlyAuditError(f"{split} manifest or seal changed")
    if manifest["scientific_dataset_lineage_id"] != "phase9g-a1-study-a-train-validation-recoverability-v1":
        raise ReadOnlyAuditError(f"{split} lineage changed")
    if seal["dataset_manifest_sha256"] != manifest_sha:
        raise ReadOnlyAuditError(f"{split} seal does not bind manifest")
    _validate_descriptors(final, manifest)

    shard_rows: dict[str, dict[str, Any]] = {}
    for descriptor in manifest["shards"]:
        rows = list(_jsonl(final / descriptor["path"]))
        if len(rows) != int(descriptor["row_count"]):
            raise ReadOnlyAuditError(f"{split} shard row count mismatch")
        for row in rows:
            identity = row["scientific_identity"]
            row_id = str(row["scientific_row_id"])
            if row_id in shard_rows or row_id != recoverability_scientific_row_id(identity):
                raise ReadOnlyAuditError(f"{split} duplicate or invalid row identity")
            if identity["study"] != STUDY or identity["split"] != split:
                raise ReadOnlyAuditError(f"{split} row crossed scientific scope")
            graph_sha = sha256_document(row["graph_payload"])
            if graph_sha != row["graph_fingerprint"] or graph_sha != identity["graph_fingerprint"]:
                raise ReadOnlyAuditError(f"{split} graph fingerprint mismatch")
            if int(row["candidate_topology_id"]) not in TOPOLOGY_NAMES:
                raise ReadOnlyAuditError(f"{split} row has unsupported candidate")
            shard_rows[row_id] = row

    transaction_index = list(_jsonl(final / manifest["transaction_indexes"][0]["path"]))
    transaction_ids: set[str] = set()
    source_ids: set[str] = set()
    layout_ids: set[tuple[str, str]] = set()
    transaction_row_ids: set[str] = set()
    aggregate: Counter[tuple[Any, ...]] = Counter()
    rows_by_cell: Counter[tuple[Any, ...]] = Counter()
    pairs: Counter[tuple[Any, ...]] = Counter()
    invalid: Counter[tuple[Any, ...]] = Counter()
    joint: Counter[tuple[Any, ...]] = Counter()
    replica_instability: Counter[tuple[Any, ...]] = Counter()
    replica_totals: Counter[tuple[Any, ...]] = Counter()
    stochastic_aggregate_totals: Counter[tuple[Any, ...]] = Counter()
    source_episode_counts: Counter[tuple[Any, ...]] = Counter()
    source_event_counts: Counter[tuple[Any, ...]] = Counter()
    matched_seed_mismatches = 0
    hardlink_matches = 0
    rollout_invalid_replicas = 0
    replica_executions = 0

    for descriptor in transaction_index:
        event_id = str(descriptor["decision_event_id"])
        if event_id in transaction_ids:
            raise ReadOnlyAuditError(f"{split} duplicate transaction identity")
        transaction_ids.add(event_id)
        event = _event_identity(event_id)
        if event["split"] != split:
            raise ReadOnlyAuditError(f"{split} transaction identity crossed split")
        family, n = event["family"], event["team_size"]
        if event["source_episode_id"] not in source_ids:
            source_episode_counts[(family, n)] += 1
        source_ids.add(event["source_episode_id"])
        layout_ids.add((split, event["layout_sha256"]))
        source_event_counts[(family, n)] += 1

        final_path = final / descriptor["path"]
        staging_path = data_root / "staging" / descriptor["relative_staging_path"]
        if not final_path.is_file() or not staging_path.is_file():
            raise ReadOnlyAuditError(f"{split} transaction provenance path missing")
        if not os.path.samefile(final_path, staging_path):
            raise ReadOnlyAuditError(f"{split} transaction is not linked to STAGING")
        hardlink_matches += 1
        if _file_sha256(final_path) != descriptor["content_sha256"]:
            raise ReadOnlyAuditError(f"{split} transaction content hash mismatch")
        document, _ = _canonical(final_path, "canonical_record_sha256")
        if document["decision_event_id"] != event_id:
            raise ReadOnlyAuditError(f"{split} transaction/event mismatch")
        if int(document["actual_row_count"]) != len(document["rows"]):
            raise ReadOnlyAuditError(f"{split} transaction row count mismatch")
        if len(document["rows"]) not in (0, int(document["expected_row_count"])):
            raise ReadOnlyAuditError(f"{split} partial candidate-pair publication")

        status = str(document["status"])
        if status == "SCIENTIFICALLY_RECONCILED_GENERATION_INVALID":
            if document["rows"] or document["training_rows_committable"]:
                raise ReadOnlyAuditError(f"{split} invalid event published rows")
            termination = document["audit"].get("termination")
            if not document["audit"].get("source_terminated_before_event") or not termination:
                raise ReadOnlyAuditError(f"{split} invalid event lacks source cause")
            reason = f"SOURCE_TERMINATED_BEFORE_EVENT:{termination['cause']}"
            pairs[(family, n, "DROPPED_NONPUBLISHED")] += 1
            invalid[(family, n, event["source_class"], reason)] += 1
            for candidate in (COMPACT, LINE):
                aggregate[(family, n, TOPOLOGY_NAMES[candidate], "GENERATION_INVALID")] += 1
            continue
        if status != "SCIENTIFICALLY_RECONCILED_LABELABLE":
            raise ReadOnlyAuditError(f"{split} unexpected transaction status")
        if len(document["rows"]) != 2 * n or not document["training_rows_committable"]:
            raise ReadOnlyAuditError(f"{split} retained transaction does not contain 2*N rows")

        candidate_audits = {
            int(item["candidate_topology_id"]): item
            for item in document["audit"]["candidate_audits"]
        }
        if set(candidate_audits) != {COMPACT, LINE}:
            raise ReadOnlyAuditError(f"{split} retained event lacks both candidates")
        replicas = _candidate_replicas(candidate_audits.values())
        for replica_index in range(max(len(replicas[COMPACT]), len(replicas[LINE]))):
            compact_replica = replicas[COMPACT][replica_index]
            line_replica = replicas[LINE][replica_index]
            if compact_replica["matched_disturbance_seed"] != line_replica["matched_disturbance_seed"]:
                matched_seed_mismatches += 1
        pairs[(family, n, "RETAINED")] += 1
        labels = {}
        for candidate, audit in candidate_audits.items():
            disposition = str(audit["aggregate"]["disposition"])
            label = audit["aggregate"]["aggregate_label"]
            if disposition not in {"RECOVERABLE_POSITIVE", "VALID_TASK_NEGATIVE"}:
                raise ReadOnlyAuditError(f"{split} retained aggregate is not labelable")
            expected_label = 1 if disposition == "RECOVERABLE_POSITIVE" else 0
            if int(label) != expected_label:
                raise ReadOnlyAuditError(f"{split} aggregate label/disposition mismatch")
            labels[candidate] = expected_label
            aggregate[(family, n, TOPOLOGY_NAMES[candidate], disposition)] += 1
            replica_labels = []
            if len(replicas[candidate]) > 1:
                stochastic_aggregate_totals[(family, TOPOLOGY_NAMES[candidate])] += 1
            for replica in replicas[candidate]:
                replica_executions += 1
                replica_totals[(family, TOPOLOGY_NAMES[candidate])] += 1
                if replica["disposition"] == "GENERATION_INVALID":
                    rollout_invalid_replicas += 1
                if replica.get("label") in (0, 1):
                    replica_labels.append(int(replica["label"]))
            if len(set(replica_labels)) > 1:
                replica_instability[(family, TOPOLOGY_NAMES[candidate])] += 1
        expected_joint = {
            (1, 1): "BOTH_SUCCESS",
            (1, 0): "COMPACT_ONLY_SUCCESS",
            (0, 1): "LINE_ONLY_SUCCESS",
            (0, 0): "BOTH_FAIL",
        }[(labels[COMPACT], labels[LINE])]
        observed_joint = {str(row["joint_outcome_category"]) for row in document["rows"]}
        if observed_joint != {expected_joint}:
            raise ReadOnlyAuditError(f"{split} joint outcome category mismatch")
        joint[(family, n, expected_joint)] += 1

        candidate_row_counts = Counter()
        for row in document["rows"]:
            row_id = str(row["scientific_row_id"])
            if row_id in transaction_row_ids or row_id not in shard_rows:
                raise ReadOnlyAuditError(f"{split} duplicate or unpublished transaction row")
            if shard_rows[row_id] != row:
                raise ReadOnlyAuditError(f"{split} transaction/shard row mismatch")
            transaction_row_ids.add(row_id)
            candidate = int(row["candidate_topology_id"])
            label = int(row["target_v4_aggregate_label"])
            if label != labels[candidate]:
                raise ReadOnlyAuditError(f"{split} row/aggregate label mismatch")
            candidate_row_counts[candidate] += 1
            rows_by_cell[(family, n, TOPOLOGY_NAMES[candidate], label)] += 1
        if candidate_row_counts != Counter({COMPACT: n, LINE: n}):
            raise ReadOnlyAuditError(f"{split} retained row topology coverage changed")

    row_index = list(_jsonl(final / manifest["row_indexes"][0]["path"]))
    row_index_ids = {str(item["scientific_row_id"]) for item in row_index}
    if len(row_index_ids) != len(row_index) or row_index_ids != set(shard_rows):
        raise ReadOnlyAuditError(f"{split} row index does not reconcile")
    if transaction_row_ids != set(shard_rows):
        raise ReadOnlyAuditError(f"{split} transaction and shard row universes differ")
    if len(shard_rows) != int(manifest["scientific_row_count"]):
        raise ReadOnlyAuditError(f"{split} manifest row count mismatch")
    if any(manifest["integrity"].values()) or any(manifest["sealed_domains"].values()):
        raise ReadOnlyAuditError(f"{split} manifest reports integrity or sealed-domain activity")

    return {
        "dataset_id": dataset_id,
        "manifest_sha256": manifest_sha,
        "seal_sha256": seal_sha,
        "source_commit": manifest["scientific_source_commit"],
        "generation_provenance_root": manifest["generation_provenance_root"],
        "counts": {
            "source_episodes": len(source_ids),
            "decision_events": len(transaction_ids),
            "candidate_aggregates": 2 * len(transaction_ids),
            "retained_candidate_pairs": sum(value for key, value in pairs.items() if key[2] == "RETAINED"),
            "dropped_candidate_pairs": sum(value for key, value in pairs.items() if key[2] == "DROPPED_NONPUBLISHED"),
            "scientific_rows": len(shard_rows),
            "replica_executions": replica_executions,
        },
        "source_episode_distribution": _records(
            source_episode_counts, ("family", "team_size")
        ),
        "source_event_distribution": _records(source_event_counts, ("family", "team_size")),
        "aggregate_distribution": _records(
            aggregate, ("family", "team_size", "candidate_topology", "disposition")
        ),
        "row_label_distribution": _records(
            rows_by_cell, ("family", "team_size", "candidate_topology", "label")
        ),
        "candidate_pair_distribution": _records(pairs, ("family", "team_size", "state")),
        "joint_outcome_distribution": _records(joint, ("family", "team_size", "joint_category")),
        "invalid_reason_distribution": _records(
            invalid, ("family", "team_size", "source_class", "reason")
        ),
        "replica_instability_distribution": _records(
            replica_instability, ("family", "candidate_topology")
        ),
        "replica_total_distribution": _records(
            replica_totals, ("family", "candidate_topology")
        ),
        "stochastic_aggregate_distribution": _records(
            stochastic_aggregate_totals, ("family", "candidate_topology")
        ),
        "integrity": {
            "published_file_hash_failures": 0,
            "transaction_hash_failures": 0,
            "row_identity_failures": 0,
            "graph_fingerprint_failures": 0,
            "candidate_pair_reconciliation_failures": 0,
            "matched_seed_mismatches": matched_seed_mismatches,
            "partial_pair_publications": 0,
            "duplicate_scientific_row_ids": 0,
            "rollout_invalid_replicas": rollout_invalid_replicas,
            "transaction_hardlink_matches": hardlink_matches,
            "staging_writable_files": sum(
                bool(path.stat().st_mode & 0o222)
                for path in staging.rglob("*")
                if path.is_file()
            ),
        },
        "identity_digest": {
            "source_episode_ids_sha256": sha256_document({"ids": sorted(source_ids)}),
            "decision_event_ids_sha256": sha256_document({"ids": sorted(transaction_ids)}),
            "scientific_row_ids_sha256": sha256_document({"ids": sorted(shard_rows)}),
            "layout_identities_sha256": sha256_document({"ids": sorted(layout_ids)}),
        },
        "identity_sets": {
            "source_episode_ids": sorted(source_ids),
            "decision_event_ids": sorted(transaction_ids),
            "scientific_row_ids": sorted(shard_rows),
            "layout_identities": sorted(layout_ids),
        },
        "immutable_namespace_checkpoint": {
            "final": _tree_checkpoint(final),
            "staging": _tree_checkpoint(staging),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, required=True)
    args = parser.parse_args()
    data_root = args.data_root.resolve()
    train = _analyze_split(data_root, "train", TRAIN_DATASET_ID)
    validation = _analyze_split(data_root, "validation", VALIDATION_DATASET_ID)

    for key in ("source_episode_ids", "decision_event_ids", "scientific_row_ids", "layout_identities"):
        def normalized(values: Iterable[Any]) -> set[Any]:
            return {tuple(value) if isinstance(value, list) else value for value in values}

        if normalized(train["identity_sets"][key]) & normalized(validation["identity_sets"][key]):
            raise ReadOnlyAuditError(f"TRAIN/VALIDATION overlap: {key}")
    train.pop("identity_sets")
    validation.pop("identity_sets")

    combined = data_root / "final" / COMBINED_DATASET_ID
    root_manifest, root_sha = _canonical(
        combined / "dataset_root_manifest.json",
        "combined_recoverability_dataset_root_sha256",
    )
    root_seal, root_seal_sha = _canonical(
        combined / "DATASET_ROOT_SEAL.json",
        "combined_recoverability_dataset_root_seal_sha256",
    )
    if root_sha != EXPECTED_COMBINED_ROOT or root_seal_sha != EXPECTED_COMBINED_SEAL:
        raise ReadOnlyAuditError("combined dataset root changed")
    if root_seal["combined_recoverability_dataset_root_sha256"] != root_sha:
        raise ReadOnlyAuditError("combined root seal binding changed")
    for split, result in (("train", train), ("validation", validation)):
        expected = root_manifest["splits"][split]
        if (
            expected["manifest_sha256"] != result["manifest_sha256"]
            or expected["seal_sha256"] != result["seal_sha256"]
            or expected["scientific_rows"] != result["counts"]["scientific_rows"]
        ):
            raise ReadOnlyAuditError(f"combined root {split} reference mismatch")

    report = {
        "schema_version": "rvt-phase9d-r-dataset-readonly-audit/v1",
        "phase": "PHASE_9D_R",
        "status": "PASS",
        "execution_mode": "READ_ONLY",
        "datasets": {"train": train, "validation": validation},
        "combined_root": {
            "manifest_sha256": root_sha,
            "seal_sha256": root_seal_sha,
            "immutable_namespace_checkpoint": _tree_checkpoint(combined),
            "scientific_contracts": root_manifest["scientific_contracts"],
        },
        "split_isolation": {
            "source_episode_id_overlap": 0,
            "decision_event_id_overlap": 0,
            "scientific_row_id_overlap": 0,
            "layout_identity_overlap": 0,
        },
        "infrastructure_misclassification_count": 0,
        "official_dataset_mutations": 0,
        "residual_generation_operations": 0,
        "training_operations": 0,
        "hyperparameter_trials": 0,
        "study_a_n24_dataset_accesses": 0,
        "study_b_dataset_accesses": 0,
        "final_test_dataset_accesses": 0,
    }
    report = attach_canonical_hash(report, "phase9d_r_dataset_readonly_audit_sha256")
    print(json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
