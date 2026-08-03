"""Immutable Phase 8 layout split manifests and leakage checks."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Dict, Iterable, Tuple

from .common import attach_canonical_hash, verify_canonical_hash, write_json
from .scenario import (
    FINAL_TEST_SPLIT,
    SPLIT_NAMES,
    STUDY_A_TRAINING_SIZES,
    SUPPORTED_TEAM_SIZES,
    TRAIN_SPLIT,
    VALIDATION_SPLIT,
    ScenarioLayout,
    generate_layouts,
)


SPLIT_MANIFEST_SCHEMA_VERSION = "rvt-layout-split/v1"


def _distribution(values: Iterable[object]) -> Dict[str, int]:
    return dict(sorted((str(key), value) for key, value in Counter(values).items()))


def layout_record(layout: ScenarioLayout) -> Dict[str, object]:
    return {
        "layout_id": layout.layout_id,
        "family_id": layout.family_id,
        "geometry_sha256": layout.geometry_sha256(),
        "canonical_parameter_tuple_sha256": layout.parameter_tuple_sha256(),
        "generation_seed_commitment": layout.generation_seed_commitment,
        "diagnostic_headroom_by_team_size": [
            [size, category]
            for size, category in layout.diagnostic_headroom_by_team_size
        ],
        "geometry": layout.canonical_geometry(),
    }


def build_split_manifest(split: str) -> Dict[str, object]:
    if split not in SPLIT_NAMES:
        raise ValueError(f"unknown split {split!r}")
    layouts = generate_layouts(
        split,
        sealed_generation_authorized=split == FINAL_TEST_SPLIT,
    )
    primary_sizes = (
        STUDY_A_TRAINING_SIZES
        if split in (TRAIN_SPLIT, VALIDATION_SPLIT)
        else SUPPORTED_TEAM_SIZES
    )
    family_distribution = _distribution(item.family_id for item in layouts)
    headroom_distribution = _distribution(
        item.headroom_for(primary_sizes[0]) for item in layouts
    )
    team_size_distribution = {
        str(size): len(layouts) for size in primary_sizes
    }
    document: Dict[str, object] = {
        "schema_version": SPLIT_MANIFEST_SCHEMA_VERSION,
        "split": split,
        "sealed": split == FINAL_TEST_SPLIT,
        "layout_count": len(layouts),
        "family_distribution": family_distribution,
        "headroom_category_distribution": headroom_distribution,
        "primary_team_size_distribution": team_size_distribution,
        "study_a_team_sizes": list(STUDY_A_TRAINING_SIZES),
        "study_b_team_sizes": list(SUPPORTED_TEAM_SIZES),
        "layout_records": [layout_record(item) for item in layouts],
    }
    return attach_canonical_hash(document)


def verify_split_disjointness(
    manifests: Iterable[object],
) -> Tuple[str, ...]:
    seen_geometry: Dict[str, str] = {}
    seen_parameters: Dict[str, str] = {}
    issues = []
    for raw in manifests:
        if not isinstance(raw, dict) or not verify_canonical_hash(raw):
            issues.append("invalid_manifest_hash")
            continue
        split = str(raw.get("split"))
        records = raw.get("layout_records")
        if not isinstance(records, list):
            issues.append(f"{split}:missing_layout_records")
            continue
        for record in records:
            if not isinstance(record, dict):
                issues.append(f"{split}:invalid_layout_record")
                continue
            geometry = str(record.get("geometry_sha256"))
            parameters = str(record.get("canonical_parameter_tuple_sha256"))
            if geometry in seen_geometry and seen_geometry[geometry] != split:
                issues.append(f"geometry_leak:{geometry}")
            if parameters in seen_parameters and seen_parameters[parameters] != split:
                issues.append(f"parameter_leak:{parameters}")
            seen_geometry[geometry] = split
            seen_parameters[parameters] = split
    return tuple(sorted(set(issues)))


def write_split_manifests(result_root: Path) -> Dict[str, Dict[str, object]]:
    split_root = result_root / "splits"
    documents = {split: build_split_manifest(split) for split in SPLIT_NAMES}
    issues = verify_split_disjointness(documents.values())
    if issues:
        raise RuntimeError(f"split leakage detected: {issues}")
    paths = {
        TRAIN_SPLIT: split_root / "train_layouts.json",
        VALIDATION_SPLIT: split_root / "validation_layouts.json",
        FINAL_TEST_SPLIT: split_root / "final_test_layouts.sealed.json",
    }
    for split, path in paths.items():
        write_json(path, documents[split])
    return documents


def load_nonfinal_split_manifest(path: Path) -> Dict[str, object]:
    if "final_test" in path.name or path.name.endswith(".sealed.json"):
        raise PermissionError("training and validation cannot load final-test manifests")
    raw = json.loads(path.read_text(encoding="ascii"))
    if not isinstance(raw, dict) or raw.get("split") == FINAL_TEST_SPLIT:
        raise PermissionError("final-test manifest is inaccessible from this loader")
    if not verify_canonical_hash(raw):
        raise ValueError("split manifest hash is invalid")
    return raw


def permitted_final_test_metadata(document: object) -> Dict[str, object]:
    if not isinstance(document, dict) or document.get("split") != FINAL_TEST_SPLIT:
        raise ValueError("expected a final-test split manifest")
    if not verify_canonical_hash(document):
        raise ValueError("final-test manifest hash is invalid")
    keys = (
        "layout_count",
        "family_distribution",
        "primary_team_size_distribution",
        "manifest_sha256",
    )
    return {key: document[key] for key in keys}
