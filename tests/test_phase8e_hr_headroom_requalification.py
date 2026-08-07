"""HR -- executable headroom requalification, frozen definitions applied literally."""
from __future__ import annotations
import hashlib, json, pathlib, pytest
from rvt_swarm.phase8.common import canonical_json_bytes

ROOT = pathlib.Path("results/rvt_fd24")
HR = json.loads((ROOT / "headroom_requalification_v2.json").read_text())
MC = json.loads((ROOT / "transition_mission_coupling_v1.json").read_text())
CATEGORIES = {"COMPACT_ONLY_SUCCESS", "LINE_ONLY_SUCCESS", "BOTH_SUCCESS",
              "BOTH_FAIL", "RECONFIGURATION_REQUIRED", "INVALID_OR_AMBIGUOUS"}


def test_category_vocabulary_is_unchanged() -> None:
    assert HR["category_definitions_changed"] is False
    assert {c["category"] for c in HR["cells"]} <= CATEGORIES


def test_every_nonfinal_layout_is_requalified() -> None:
    assert len(HR["cells"]) == 30
    assert {c["split"] for c in HR["cells"]} == {"train", "validation"}
    assert {c["family"] for c in HR["cells"]} == {f"F{i}" for i in range(1, 11)}


def test_the_runtime_was_executable_not_historical() -> None:
    assert HR["executable_runtime"] is True
    assert HR["learned_model_used"] is False
    assert HR["dataset_rows_generated"] == 0


def test_fixed_line_success_excludes_reconfiguration_required() -> None:
    """The frozen definition, applied literally."""
    for cell in HR["cells"]:
        if cell["line"]["success"] or cell["compact"]["success"]:
            assert cell["category"] != "RECONFIGURATION_REQUIRED", cell["layout_id"]


def test_reconfiguration_required_means_both_fixed_fail_and_oracle_succeeds() -> None:
    for cell in HR["cells"]:
        if cell["category"] != "RECONFIGURATION_REQUIRED":
            continue
        assert not cell["compact"]["success"]
        assert not cell["line"]["success"]
        assert cell["oracle"]["success"]


def test_category_follows_outcomes_not_family_name() -> None:
    for cell in HR["cells"]:
        if cell["family"] != "F5":
            continue
        assert cell["line"]["success"] is True
        assert cell["category"] == "LINE_ONLY_SUCCESS", cell["layout_id"]


def test_f5_no_longer_carries_the_universal_necessity_claim() -> None:
    analysis = HR["f5_analysis"]
    assert analysis["declared_family_category"] == "RECONFIGURATION_REQUIRED"
    assert set(analysis["executable_category_by_cell"].values()) == {"LINE_ONLY_SUCCESS"}
    assert "fixed LINE completes" in analysis["reason"]


def test_reconfiguration_required_remains_nonzero_in_both_splits() -> None:
    assert HR["reconfiguration_required_train"] > 0
    assert HR["reconfiguration_required_validation"] > 0
    assert HR["h2_viable"] is True


def test_the_h2_concentration_limitation_is_recorded() -> None:
    assert HR["reconfiguration_required_families"] == ["F9"]
    assert "concentrated in a single family" in HR["h2_limitation"]


def test_the_coverage_limitation_is_declared() -> None:
    assert HR["team_sizes_evaluated"] == [6]
    assert "not yet requalified" in HR["coverage_limitation"]


def test_historical_headroom_artifacts_were_not_overwritten() -> None:
    for name in ("SCENARIO_HEADROOM_REPORT.md", "SCENARIO_HEADROOM_V2_REPORT.md",
                 "RVT_FD24_SCENARIO_HEADROOM_PROTOCOL.md",
                 "RVT_FD24_SCENARIO_FAMILY_CONTRACT.md"):
        assert (pathlib.Path("docs") / name).exists()


def test_family_contract_still_records_the_historical_f5_wording() -> None:
    text = (pathlib.Path("docs") / "RVT_FD24_SCENARIO_FAMILY_CONTRACT.md").read_text()
    assert "RECONFIGURATION_REQUIRED" in text and "repeated C->L->C" in text


def test_artifact_hashes_are_reproducible() -> None:
    for document, key in ((HR, "headroom_requalification_sha256"),
                          (MC, "transition_mission_coupling_sha256")):
        body = {k: v for k, v in document.items() if k != key}
        assert hashlib.sha256(canonical_json_bytes(body)).hexdigest() == document[key]


def test_the_coupling_artifact_records_the_derived_settle_rule() -> None:
    assert MC["settle_formula"] == "a_max * dt"
    assert MC["derived_v_settle_meters_per_second"] == pytest.approx(
        MC["authoritative_a_max_meters_per_second_squared"]
        * MC["authoritative_dt_seconds"])
    assert MC["mc2_pure_frame_binding_bug"] is False
    assert MC["readiness_unchanged"] and MC["generic_profile_unchanged"]
    assert MC["controller_gains_unchanged"] and MC["safety_projection_unchanged"]


def test_qualification_results_clear_the_frozen_clearance() -> None:
    q = MC["qualification"]
    assert q["open_space_compact_to_line_min_separation_meters"] >= q["required_clearance_meters"]
    assert q["line_to_compact_min_separation_meters"] >= q["required_clearance_meters"]


def test_isolation_counters_are_zero() -> None:
    assert HR["final_test_access_count"] == 0
    assert HR["study_a_n24_access_count"] == 0
    assert not (ROOT / "layout_execution_specifications" / "final_test").exists()
    assert list(ROOT.glob("**/*.pt")) == []


def test_generation_budget_and_job_manifest_are_unchanged() -> None:
    assert hashlib.sha256((ROOT / "datasets" / "generation_budget_v1.json").read_bytes()
                          ).hexdigest() == (
        "e12e42052fd48a6647b4b7fdac77db3a20340d550617ff196fb40b7541da5492")
    manifest = json.loads((ROOT / "datasets" / "phase9_job_manifest.json").read_text())
    assert manifest["job_manifest_sha256"] == (
        "801fe4e2bd694da0dda7c310226906e59d9bc5435d657fab2e3f132432aa2dc3")
