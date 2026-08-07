"""HRF -- full executable headroom requalification, all 150 Study A cells."""
from __future__ import annotations
import hashlib, json, pathlib, pytest
from rvt_swarm.phase8.common import canonical_json_bytes

ROOT = pathlib.Path("results/rvt_fd24")
V3 = json.loads((ROOT / "headroom_requalification_v3.json").read_text())
CATEGORIES = {"COMPACT_ONLY_SUCCESS", "LINE_ONLY_SUCCESS", "BOTH_SUCCESS",
              "BOTH_FAIL", "RECONFIGURATION_REQUIRED", "INVALID_OR_AMBIGUOUS"}
TRAIN_N = [5, 6, 8, 12, 16]


def test_unit_is_the_frozen_layout_team_size_cell() -> None:
    unit = V3["unit_of_analysis"]
    assert unit["frozen_unit"] == "layout x team-size cell"
    assert unit["aggregation_rule_needed"] is False


def test_the_historical_counts_are_explained_by_per_n_invariance() -> None:
    """0/30 historical layouts varied across N, so the 20/10 projection was trivial."""
    for split in ("train", "validation"):
        manifest = json.loads((ROOT / "splits" / f"{split}_layouts.json").read_text())
        for record in manifest["layout_records"]:
            categories = {c for _, c in record["diagnostic_headroom_by_team_size"]}
            assert len(categories) == 1, record["layout_id"]


def test_all_one_hundred_and_fifty_study_a_cells_are_evaluated() -> None:
    assert V3["cells_evaluated"] == 150
    cells = V3["cells"]
    assert len([c for c in cells if c["split"] == "train"]) == 100
    assert len([c for c in cells if c["split"] == "validation"]) == 50
    assert sorted({c["team_size"] for c in cells}) == TRAIN_N
    assert {c["family"] for c in cells} == {f"F{i}" for i in range(1, 11)}


def test_n24_and_final_test_were_not_touched() -> None:
    assert 24 not in {c["team_size"] for c in V3["cells"]}
    assert V3["evaluation_domain"]["n24_sealed_excluded"] is True
    assert V3["final_test_access_count"] == 0
    assert V3["study_a_n24_access_count"] == 0
    assert not (ROOT / "layout_execution_specifications" / "final_test").exists()


def test_categories_use_the_frozen_vocabulary() -> None:
    assert {c["category"] for c in V3["cells"]} <= CATEGORIES


def test_reconfiguration_required_is_never_assigned_by_family_name() -> None:
    for cell in V3["cells"]:
        if cell["category"] != "RECONFIGURATION_REQUIRED":
            continue
        assert not cell["compact"]["success"]
        assert not cell["line"]["success"]
        assert cell["switching"]["success"]


def test_a_fixed_success_excludes_reconfiguration_required() -> None:
    for cell in V3["cells"]:
        if cell["compact"] and cell["line"] and (
                cell["compact"]["success"] or cell["line"]["success"]):
            assert cell["category"] != "RECONFIGURATION_REQUIRED", cell["layout_id"]


def test_h2_headroom_is_nonzero_in_both_splits() -> None:
    rr = V3["reconfiguration_required"]
    assert rr["train"] > 0 and rr["validation"] > 0
    assert V3["h2"]["falsifiable"] is True


def test_h2_concentration_is_quantified_honestly() -> None:
    rr = V3["reconfiguration_required"]
    assert rr["families"] == ["F9"]
    assert len(rr["team_sizes"]) > 1
    assert rr["concentration_class"] == "B"
    assert "F5 provides none" in V3["h2"]["limitation"]


def test_f5_carries_no_reconfiguration_required_at_any_n() -> None:
    f5 = [c for c in V3["cells"] if c["family"] == "F5"]
    assert len(f5) == 15
    assert all(c["category"] != "RECONFIGURATION_REQUIRED" for c in f5)
    assert all(c["old_category"] == "RECONFIGURATION_REQUIRED" for c in f5)


def test_invalid_cells_are_explained_and_not_forced_into_a_category() -> None:
    inv = V3["invalid_or_ambiguous"]
    assert inv["count"] == 15
    assert "S2 ALWAYS LINE" in inv["root_cause"]
    assert inv["classification"].startswith("newly exposed runtime binding gap")


def test_the_n6_artifact_is_preserved_not_overwritten() -> None:
    v2 = json.loads((ROOT / "headroom_requalification_v2.json").read_text())
    assert v2["team_sizes_evaluated"] == [6]
    assert v2["schema_version"] == "rvt-headroom-requalification/v2"
    assert V3["schema_version"] == "rvt-headroom-requalification/v3"


def test_replica_rule_is_read_not_invented() -> None:
    rule = V3["replica_rule"]
    assert rule["target_v4_three_replica_rule_reused"] is False
    assert rule["replicas_used"] == 1


def test_layout_projection_is_declared_no_longer_well_defined() -> None:
    unit = V3["unit_of_analysis"]
    assert unit["layout_projection_still_well_defined"] is False


def test_v3_hash_is_reproducible() -> None:
    body = {k: v for k, v in V3.items() if k != "headroom_requalification_v3_sha256"}
    assert hashlib.sha256(canonical_json_bytes(body)).hexdigest() == (
        V3["headroom_requalification_v3_sha256"])


def test_no_dataset_artifacts_were_created() -> None:
    assert V3["dataset_rows_generated"] == 0
    assert list(ROOT.glob("**/*.pt")) == []
    assert list((ROOT / "datasets").glob("*shard*")) == []
