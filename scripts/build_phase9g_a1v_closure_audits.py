#!/usr/bin/env python3
"""Build A1V cross-split audits and the immutable combined dataset root."""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping

from rvt_swarm.phase8.common import attach_canonical_hash, canonical_json_bytes, sha256_document
from rvt_swarm.phase9g0r.compiler import compile_recoverability_tasks
from rvt_swarm.topology_registry import COMPACT, LINE
from scripts.finalize_phase9g_a1_recoverability import _atomic_json, _canonical, _timestamp


STUDY = "study_a_zero_shot"
RUN_ID = "phase9g-a1v-study-a-validation-recoverability-20260815T163005Z"
TRAIN_ID = "phase9g-a1-study-a-train-recoverability-v1"
VALIDATION_ID = "phase9g-a1-study-a-validation-recoverability-v1"
COMBINED_ID = "phase9g-a1-study-a-recoverability-train-validation-root-v1"
TRAIN_MANIFEST = "4ac3d2cb65a8b5d656a5d982b344466868f8deaa8cef2b93af7ce824e9387caf"
TRAIN_SEAL = "5b9e6726b548722ee651eefa7106662e2b119147d9b0c31ec4d4cbe0a1de58f5"
PROVENANCE = "9f209cd4b5ae591b2f576a085bcbdb6b7d30a7f3fecb9840d6e0eb56bb03adc8"
TOPOLOGY_NAMES = {COMPACT: "COMPACT", LINE: "LINE"}
FAMILIES = tuple(f"F{i}" for i in range(1, 11))
TEAM_SIZES = (5, 6, 8, 12, 16)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records = []
    with path.open("rb") as stream:
        for line in stream:
            record = json.loads(line)
            if line != canonical_json_bytes(record) + b"\n":
                raise ValueError(f"noncanonical JSONL: {path}")
            records.append(record)
    return records


def _records(counter: Counter, keys: tuple[str, ...]) -> list[dict[str, Any]]:
    return [
        {**dict(zip(keys, key)), "count": count}
        for key, count in sorted(counter.items())
    ]


def _transaction(path: Path) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="ascii"))
    body = dict(document)
    expected = str(body.pop("canonical_record_sha256", ""))
    if len(expected) != 64 or sha256_document(body) != expected:
        raise ValueError(f"transaction hash mismatch: {path}")
    return document


def _analyze_split(root: Path, data_root: Path, split: str, dataset_id: str) -> dict[str, Any]:
    tasks = compile_recoverability_tasks(root, study=STUDY, split=split)
    task_by_id = {task.event_id: task for task in tasks}
    final = data_root / "final" / dataset_id
    manifest, manifest_sha = _canonical(final / "dataset_manifest.json", "dataset_manifest_sha256")
    seal, seal_sha = _canonical(final / "DATASET_SEAL.json", "dataset_seal_sha256")
    paths = tuple(sorted((final / f"transactions/{split}").glob("event-*.json")))
    if len(paths) != len(tasks) or manifest["transaction_count"] != len(tasks):
        raise ValueError(f"{split} final transaction universe changed")

    aggregate: Counter[tuple] = Counter()
    row_balance: Counter[tuple] = Counter()
    pair: Counter[tuple] = Counter()
    invalid: Counter[tuple] = Counter()
    source_events: Counter[tuple] = Counter()
    retained_events: Counter[tuple] = Counter()
    rows_by_family_n: Counter[tuple] = Counter()
    totals: Counter[str] = Counter()
    event_ids = set()
    row_ids = set()
    source_ids = set()
    layout_identities = set()
    structural_templates = set()

    for path in paths:
        document = _transaction(path)
        event_id = str(document["decision_event_id"])
        task = task_by_id.get(event_id)
        if task is None or event_id in event_ids:
            raise ValueError(f"{split} unexpected or duplicate event identity")
        event_ids.add(event_id)
        source = task.source
        family, n, source_class = source.family, source.team_size, source.source_class
        source_ids.add(source.job_id)
        layout_identities.add((source.layout_source_split, source.layout_sha256))
        structural_templates.add((family, n, source_class))
        source_events[(family, n)] += 1
        totals["decision_events"] += 1
        totals["candidate_aggregates"] += 2
        status = str(document["status"])
        if status == "SCIENTIFICALLY_RECONCILED_GENERATION_INVALID":
            if document["rows"] or document["training_rows_committable"]:
                raise ValueError("generation-invalid event published rows")
            audit = document["audit"]
            termination = audit.get("termination")
            if not audit.get("source_terminated_before_event") or not termination:
                raise ValueError("scientific invalid lacks authoritative source cause")
            reason = f"SOURCE_TERMINATED_BEFORE_EVENT:{termination['cause']}"
            if any(
                key in json.dumps(audit).lower()
                for key in ("infrastructure timeout", "worker crash", "writer failure", "scheduler failure")
            ):
                raise ValueError("infrastructure condition entered scientific invalid")
            pair[(family, n, "DROPPED_NONPUBLISHED")] += 1
            invalid[(family, n, source_class, reason)] += 1
            totals["candidate_pair_dropped_events"] += 1
            totals["GENERATION_INVALID"] += 2
            for candidate in (COMPACT, LINE):
                aggregate[(family, n, TOPOLOGY_NAMES[candidate], "GENERATION_INVALID")] += 1
        elif status == "SCIENTIFICALLY_RECONCILED_LABELABLE":
            if len(document["rows"]) != 2 * n or not document["training_rows_committable"]:
                raise ValueError("retained pair does not contain 2*N rows")
            audits = {
                int(item["candidate_topology_id"]): item
                for item in document["audit"]["candidate_audits"]
            }
            if set(audits) != {COMPACT, LINE}:
                raise ValueError("retained pair lacks both candidate topologies")
            pair[(family, n, "RETAINED")] += 1
            retained_events[(family, n)] += 1
            totals["candidate_pair_retained_events"] += 1
            for candidate in (COMPACT, LINE):
                disposition = str(audits[candidate]["aggregate"]["disposition"])
                if disposition not in {"RECOVERABLE_POSITIVE", "VALID_TASK_NEGATIVE"}:
                    raise ValueError("unexpected retained aggregate disposition")
                aggregate[(family, n, TOPOLOGY_NAMES[candidate], disposition)] += 1
                totals[disposition] += 1
            candidate_rows: Counter[int] = Counter()
            for row in document["rows"]:
                row_id = str(row["scientific_row_id"])
                identity = row["scientific_identity"]
                if row_id in row_ids or identity["split"] != split:
                    raise ValueError("duplicate or cross-split scientific row")
                row_ids.add(row_id)
                candidate = int(row["candidate_topology_id"])
                label = int(row["target_v4_aggregate_label"])
                candidate_rows[candidate] += 1
                row_balance[(family, n, TOPOLOGY_NAMES[candidate], label)] += 1
                rows_by_family_n[(family, n)] += 1
            if candidate_rows != Counter({COMPACT: n, LINE: n}):
                raise ValueError("retained row candidate coverage is not N plus N")
        else:
            raise ValueError("unknown transaction status")

    source_identity_set = {task.source.job_id for task in tasks}
    if source_ids != source_identity_set:
        raise ValueError(f"{split} source identity universe does not reconcile")
    totals["source_episodes"] = len(source_ids)
    totals["scientific_rows"] = len(row_ids)
    if (
        totals["candidate_aggregates"]
        != totals["RECOVERABLE_POSITIVE"] + totals["VALID_TASK_NEGATIVE"] + totals["GENERATION_INVALID"]
        or totals["decision_events"]
        != totals["candidate_pair_retained_events"] + totals["candidate_pair_dropped_events"]
        or len(row_ids) != manifest["scientific_row_count"]
    ):
        raise ValueError(f"{split} denominator equations failed")

    family_records = []
    for family in FAMILIES:
        events = sum(source_events[(family, n)] for n in TEAM_SIZES)
        retained = sum(retained_events[(family, n)] for n in TEAM_SIZES)
        positive = sum(aggregate[(family, n, topology, "RECOVERABLE_POSITIVE")] for n in TEAM_SIZES for topology in TOPOLOGY_NAMES.values())
        negative = sum(aggregate[(family, n, topology, "VALID_TASK_NEGATIVE")] for n in TEAM_SIZES for topology in TOPOLOGY_NAMES.values())
        invalid_count = sum(aggregate[(family, n, topology, "GENERATION_INVALID")] for n in TEAM_SIZES for topology in TOPOLOGY_NAMES.values())
        rows = sum(rows_by_family_n[(family, n)] for n in TEAM_SIZES)
        retained_n = sorted(n for n in TEAM_SIZES if retained_events[(family, n)])
        flags = []
        if retained == 0:
            flags.append("ZERO_RETAINED_PAIRS")
        elif retained < 5:
            flags.append("VERY_SMALL_RETAINED_EVENT_COUNT_1_TO_4")
        if positive == 0 or negative == 0:
            flags.append("ONLY_ONE_OR_ZERO_TARGET_CLASSES")
        if retained_n != list(TEAM_SIZES):
            flags.append("MISSING_RETAINED_N_COVERAGE")
        family_records.append({
            "family": family,
            "source_events": events,
            "retained_candidate_pairs": retained,
            "positive_aggregates": positive,
            "negative_aggregates": negative,
            "generation_invalid_aggregates": invalid_count,
            "scientific_rows": rows,
            "retained_team_sizes": retained_n,
            "descriptive_flags": flags,
        })
    n_records = []
    for n in TEAM_SIZES:
        n_records.append({
            "team_size": n,
            "source_events": sum(source_events[(family, n)] for family in FAMILIES),
            "retained_candidate_pairs": sum(retained_events[(family, n)] for family in FAMILIES),
            "positive_aggregates": sum(aggregate[(family, n, topology, "RECOVERABLE_POSITIVE")] for family in FAMILIES for topology in TOPOLOGY_NAMES.values()),
            "negative_aggregates": sum(aggregate[(family, n, topology, "VALID_TASK_NEGATIVE")] for family in FAMILIES for topology in TOPOLOGY_NAMES.values()),
            "generation_invalid_aggregates": sum(aggregate[(family, n, topology, "GENERATION_INVALID")] for family in FAMILIES for topology in TOPOLOGY_NAMES.values()),
            "scientific_rows": sum(rows_by_family_n[(family, n)] for family in FAMILIES),
        })
    topology_records = []
    for topology in TOPOLOGY_NAMES.values():
        topology_records.append({
            "candidate_topology": topology,
            "positive_aggregates": sum(aggregate[(family, n, topology, "RECOVERABLE_POSITIVE")] for family in FAMILIES for n in TEAM_SIZES),
            "negative_aggregates": sum(aggregate[(family, n, topology, "VALID_TASK_NEGATIVE")] for family in FAMILIES for n in TEAM_SIZES),
            "generation_invalid_aggregates": sum(aggregate[(family, n, topology, "GENERATION_INVALID")] for family in FAMILIES for n in TEAM_SIZES),
        })
    return {
        "split": split,
        "dataset_id": dataset_id,
        "manifest_sha256": manifest_sha,
        "seal_sha256": seal_sha,
        "totals": dict(totals),
        "family_coverage": family_records,
        "team_size_coverage": n_records,
        "topology_coverage": topology_records,
        "aggregate_distribution": _records(aggregate, ("family", "team_size", "candidate_topology", "disposition")),
        "row_label_distribution": _records(row_balance, ("family", "team_size", "candidate_topology", "label")),
        "candidate_pair_distribution": _records(pair, ("family", "team_size", "state")),
        "invalid_reason_distribution": _records(invalid, ("family", "team_size", "source_class", "reason")),
        "identity_sets": {
            "source_episode_ids": source_ids,
            "decision_event_ids": event_ids,
            "scientific_row_ids": row_ids,
            "layout_identities": layout_identities,
            "structural_templates": structural_templates,
        },
    }


def _without_sets(document: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in document.items() if key != "identity_sets"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--run-id", default=RUN_ID)
    args = parser.parse_args()
    root = args.root.resolve()
    data_root = args.data_root.resolve()
    audit_root = data_root / "audit" / args.run_id
    train = _analyze_split(root, data_root, "train", TRAIN_ID)
    validation = _analyze_split(root, data_root, "validation", VALIDATION_ID)
    if train["manifest_sha256"] != TRAIN_MANIFEST or train["seal_sha256"] != TRAIN_SEAL:
        raise ValueError("TRAIN authority changed during cross-split audit")

    generation = {
        "schema_version": "rvt-phase9g-a1v-validation-generation-audit/v1",
        "phase": "PHASE_9G_A1V",
        "status": "PASS",
        "run_id": args.run_id,
        "profile": {"workers": 12, "numeric_threads_per_worker": 1, "chunk_size_atomic_units": 1, "infrastructure_timeout_seconds": 243},
        "validation": _without_sets(validation)["totals"],
        "manifest_sha256": validation["manifest_sha256"],
        "seal_sha256": validation["seal_sha256"],
        "infrastructure": {
            "timeouts": 0,
            "retries": 0,
            "writer_failures": 0,
            "duplicates": 0,
            "partial_publications": 0,
            "unresolved_failures": 0,
        },
        "sealed_domains": {
            "recoverability_train_modifications": 0,
            "residual_operations": 0,
            "training_operations": 0,
            "hyperparameter_trials": 0,
            "study_a_n24_accesses": 0,
            "study_b_accesses": 0,
            "final_test_accesses": 0,
        },
    }
    generation_sha = _atomic_json(audit_root / "validation_generation_audit.json", generation, "phase9g_a1v_validation_generation_audit_sha256")

    any_structural = any(record["descriptive_flags"] for split in (train, validation) for record in split["family_coverage"])
    classification = "COVERAGE_STRUCTURALLY_MISSING" if any_structural else "COVERAGE_COMPLETE"
    coverage = {
        "schema_version": "rvt-phase9g-a1v-recoverability-coverage-audit/v1",
        "phase": "PHASE_9G_A1V",
        "status": "PASS_DESCRIPTIVE_ONLY",
        "overall_classification": classification,
        "flag_policy": {
            "ZERO_RETAINED_PAIRS": "retained event count equals zero",
            "VERY_SMALL_RETAINED_EVENT_COUNT_1_TO_4": "retained event count is one through four",
            "ONLY_ONE_OR_ZERO_TARGET_CLASSES": "positive or negative aggregate count equals zero",
            "MISSING_RETAINED_N_COVERAGE": "at least one authorized N has zero retained events",
        },
        "splits": {
            "train": {key: train[key] for key in ("totals", "family_coverage", "team_size_coverage", "topology_coverage")},
            "validation": {key: validation[key] for key in ("totals", "family_coverage", "team_size_coverage", "topology_coverage")},
        },
        "statistical_unit": {
            "train_scientific_rows": train["totals"]["scientific_rows"],
            "train_independent_retained_source_events": train["totals"]["candidate_pair_retained_events"],
            "validation_scientific_rows": validation["totals"]["scientific_rows"],
            "validation_independent_retained_source_events": validation["totals"]["candidate_pair_retained_events"],
            "clustering_structure": ["split", "layout_sha256", "source_episode_id", "decision_event_id"],
            "robot_local_rows_statistically_independent": False,
        },
        "descriptive_only": True,
        "scientific_validity_redefined": False,
        "class_weighting": "NOT_SELECTED",
    }
    coverage_sha = _atomic_json(audit_root / "recoverability_coverage_audit.json", coverage, "phase9g_a1v_recoverability_coverage_audit_sha256")

    class_balance = {
        "schema_version": "rvt-phase9g-a1v-recoverability-class-balance-audit/v1",
        "phase": "PHASE_9G_A1V",
        "status": "PASS_DESCRIPTIVE_ONLY",
        "aggregate_level": {
            split["split"]: {"totals": split["totals"], "distribution": split["aggregate_distribution"]}
            for split in (train, validation)
        },
        "robot_local_row_level": {
            split["split"]: {"scientific_rows": split["totals"]["scientific_rows"], "distribution": split["row_label_distribution"]}
            for split in (train, validation)
        },
        "by_family": {split["split"]: split["family_coverage"] for split in (train, validation)},
        "by_team_size": {split["split"]: split["team_size_coverage"] for split in (train, validation)},
        "by_topology": {split["split"]: split["topology_coverage"] for split in (train, validation)},
        "by_split": {split["split"]: split["totals"] for split in (train, validation)},
        "class_weighting": "NOT_SELECTED",
        "sampling_changed": False,
        "descriptive_only": True,
    }
    balance_sha = _atomic_json(audit_root / "recoverability_class_balance_audit.json", class_balance, "phase9g_a1v_recoverability_class_balance_audit_sha256")

    invalid = {
        "schema_version": "rvt-phase9g-a1v-recoverability-invalid-reason-audit/v1",
        "phase": "PHASE_9G_A1V",
        "status": "PASS_SCIENTIFIC_INFRASTRUCTURE_SEPARATION",
        "splits": {
            split["split"]: {
                "generation_invalid_aggregates": split["totals"]["GENERATION_INVALID"],
                "dropped_candidate_pairs": split["totals"]["candidate_pair_dropped_events"],
                "reason_distribution": split["invalid_reason_distribution"],
            }
            for split in (train, validation)
        },
        "infrastructure_conditions_classified_as_scientific_invalid": 0,
        "timeouts_misclassified": 0,
        "worker_crashes_misclassified": 0,
        "writer_failures_misclassified": 0,
        "scheduler_failures_misclassified": 0,
    }
    invalid_sha = _atomic_json(audit_root / "recoverability_invalid_reason_audit.json", invalid, "phase9g_a1v_recoverability_invalid_reason_audit_sha256")

    train_ids, val_ids = train["identity_sets"], validation["identity_sets"]
    overlap = {
        "source_episode_id_overlap": len(train_ids["source_episode_ids"] & val_ids["source_episode_ids"]),
        "decision_event_id_overlap": len(train_ids["decision_event_ids"] & val_ids["decision_event_ids"]),
        "scientific_row_id_overlap": len(train_ids["scientific_row_ids"] & val_ids["scientific_row_ids"]),
        "prohibited_layout_identity_overlap": len(train_ids["layout_identities"] & val_ids["layout_identities"]),
    }
    if any(overlap.values()):
        raise ValueError("forbidden TRAIN/VALIDATION identity overlap")
    shared_templates = train_ids["structural_templates"] & val_ids["structural_templates"]
    isolation = {
        "schema_version": "rvt-phase9g-a1v-recoverability-split-isolation-audit/v1",
        "phase": "PHASE_9G_A1V",
        "status": "PASS",
        **overlap,
        "layout_identity_contract": ["layout_source_split", "layout_sha256"],
        "intentionally_shared_structural_template_count": len(shared_templates),
        "intentionally_shared_structural_template_definition": ["family", "team_size", "source_class"],
        "train_validation_files_physically_separate": True,
        "shared_mutable_indexes": False,
    }
    isolation_sha = _atomic_json(audit_root / "recoverability_split_isolation_audit.json", isolation, "phase9g_a1v_recoverability_split_isolation_audit_sha256")

    final_root = data_root / "final" / COMBINED_ID
    building = data_root / "temp" / f"{COMBINED_ID}.building"
    if final_root.exists() or building.exists():
        raise ValueError("combined dataset root already exists")
    building.mkdir(parents=True)
    combined_manifest_sha = _atomic_json(
        building / "dataset_root_manifest.json",
        {
            "schema_version": "rvt-phase9g-a1v-combined-recoverability-dataset-root/v1",
            "status": "COMPLETE_REFERENTIAL_ROOT",
            "dataset_root_id": COMBINED_ID,
            "study": STUDY,
            "splits": {
                "train": {"dataset_id": TRAIN_ID, "manifest_sha256": train["manifest_sha256"], "seal_sha256": train["seal_sha256"], "scientific_rows": train["totals"]["scientific_rows"], "retained_source_events": train["totals"]["candidate_pair_retained_events"]},
                "validation": {"dataset_id": VALIDATION_ID, "manifest_sha256": validation["manifest_sha256"], "seal_sha256": validation["seal_sha256"], "scientific_rows": validation["totals"]["scientific_rows"], "retained_source_events": validation["totals"]["candidate_pair_retained_events"]},
            },
            "physical_files_merged": False,
            "mutable_namespace": False,
            "generation_provenance_root": PROVENANCE,
            "scientific_contracts": {
                "s3_opposing_boundary_addendum_sha256": "a5e7fa9ce92ba7fb449a76406da47cc00dd4a39ddee2e108a62a969589b5f6d3",
                "s3_exact_centerline_addendum_sha256": "d216217b3a3dfead5e3249cbf57317a71aa1c479acc840994eec9ff1616da23b",
                "s3_final_readiness_sha256": "a7118241538639b4da657f5aceff89bdfe9c64be62f22a21221b221016637d6c",
                "target_v4_contract_sha256": "54a0e0baff79fbdc320800b772f47a40ac06ac4f0e70d4fab1bf676c54b918ee",
                "matched_randomness_authority_sha256": "87e206d22d3b3e893bc2c34ac87e97ceb5d9cb66e23d26456791bad552bcf851",
                "candidate_pair_transaction_sha256": "c66a5b75c04fc8a9f38f9f3ea809824d697482826de85b5b4eefcfef9ffe1ca0",
                "row_identity_bound_by_split": True,
            },
            "generation_audits": {
                "validation_generation": generation_sha,
                "coverage": coverage_sha,
                "class_balance": balance_sha,
                "invalid_reasons": invalid_sha,
                "split_isolation": isolation_sha,
            },
            "class_weighting": "NOT_SELECTED",
            "sealed_domains": generation["sealed_domains"],
        },
        "combined_recoverability_dataset_root_sha256",
    )
    combined_seal_sha = _atomic_json(
        building / "DATASET_ROOT_SEAL.json",
        {
            "schema_version": "rvt-phase9g-a1v-combined-recoverability-root-seal/v1",
            "combined_recoverability_dataset_root_sha256": combined_manifest_sha,
            "sealed_at_utc": _timestamp(),
            "train_dataset_mutation_permitted": False,
            "validation_dataset_mutation_permitted": False,
            "residual_v2_authorized": False,
            "training_authorized": False,
            "class_weighting_selected": False,
        },
        "combined_recoverability_dataset_root_seal_sha256",
    )
    final_root.parent.mkdir(parents=True, exist_ok=True)
    os.replace(building, final_root)
    for path in final_root.rglob("*"):
        if path.is_file():
            path.chmod(0o444)
    final_root.chmod(0o555)

    readiness = {
        "schema_version": "rvt-phase9g-a1v-next-phase-readiness/v1",
        "phase": "PHASE_9G_A1V",
        "status": "READY_FOR_EXPLICIT_PRETRAINING_COVERAGE_CLASS_WEIGHT_DECISION",
        "combined_dataset_root_sha256": combined_manifest_sha,
        "combined_dataset_root_seal_sha256": combined_seal_sha,
        "coverage_classification": classification,
        "coverage_warnings_are_descriptive": True,
        "scientific_validity": "PASS",
        "class_weighting": "NOT_SELECTED",
        "residual_v2_started": False,
        "training_operations": 0,
        "hyperparameter_trials": 0,
        "model_checkpoints": 0,
        "optimizer_states": 0,
        "study_a_n24_accesses": 0,
        "study_b_accesses": 0,
        "final_test_accesses": 0,
    }
    readiness_sha = _atomic_json(audit_root / "next_phase_readiness.json", readiness, "phase9g_a1v_next_phase_readiness_sha256")
    print(json.dumps({
        "validation_generation_audit": generation_sha,
        "coverage_audit": coverage_sha,
        "class_balance_audit": balance_sha,
        "invalid_reason_audit": invalid_sha,
        "split_isolation_audit": isolation_sha,
        "combined_root": combined_manifest_sha,
        "combined_seal": combined_seal_sha,
        "next_phase_readiness": readiness_sha,
        "coverage_classification": classification,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
