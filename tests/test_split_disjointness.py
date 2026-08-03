import json
from pathlib import Path

import pytest

from rvt_swarm.phase8.common import verify_canonical_hash
from rvt_swarm.phase8.splits import (
    load_nonfinal_split_manifest,
    permitted_final_test_metadata,
    verify_split_disjointness,
)


ROOT = Path(__file__).resolve().parents[1]
SPLIT_ROOT = ROOT / "results/rvt_fd24/splits"


def _load(name):
    return json.loads((SPLIT_ROOT / name).read_text(encoding="ascii"))


def test_committed_split_manifests_have_frozen_counts_and_valid_hashes():
    train = _load("train_layouts.json")
    validation = _load("validation_layouts.json")
    final = _load("final_test_layouts.sealed.json")
    assert [train["layout_count"], validation["layout_count"], final["layout_count"]] == [20, 10, 10]
    assert all(verify_canonical_hash(item) for item in (train, validation, final))
    assert final["sealed"] is True


def test_geometry_and_parameter_tuple_leakage_is_zero():
    manifests = (
        _load("train_layouts.json"),
        _load("validation_layouts.json"),
        _load("final_test_layouts.sealed.json"),
    )
    assert verify_split_disjointness(manifests) == ()


def test_every_split_contains_all_families_and_reports_team_sizes():
    for name in (
        "train_layouts.json",
        "validation_layouts.json",
        "final_test_layouts.sealed.json",
    ):
        manifest = _load(name)
        assert set(manifest["family_distribution"]) == {f"F{index}" for index in range(1, 11)}
        assert manifest["primary_team_size_distribution"]


def test_normal_loader_rejects_sealed_final_manifest():
    with pytest.raises(PermissionError, match="final-test"):
        load_nonfinal_split_manifest(SPLIT_ROOT / "final_test_layouts.sealed.json")


def test_permitted_final_metadata_excludes_layout_records():
    metadata = permitted_final_test_metadata(_load("final_test_layouts.sealed.json"))
    assert set(metadata) == {
        "layout_count",
        "family_distribution",
        "primary_team_size_distribution",
        "manifest_sha256",
    }
