"""Phase 9G-V3A-T -- the prelaunch NO-GO.

Official V3 TRAIN could not start: the twenty frozen official V3 TRAIN layouts
have no compiled layout execution specification, in the repository or inside
the qualified production image. These tests pin that finding against the live
filesystem so it cannot quietly become stale, and pin the zeros that prove no
official data were produced.
"""
from __future__ import annotations

import json
import pathlib

import pytest

from rvt_swarm.phase8.common import verify_canonical_hash
from rvt_swarm.phase9g0r.compiler_v3 import load_v3_layout_registry

ROOT = pathlib.Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results/rvt_fd24"
SPECS = RESULTS / "layout_execution_specifications"
PREFIX = "phase9g_v3a_t_"

ARTIFACTS = ("prelaunch_exclusion_union", "prelaunch_go",
             "execution_specification_blocker", "official_data_protection",
             "final_readiness")


def load(stem):
    return json.loads((RESULTS / f"{PREFIX}{stem}_v1.json").read_text())


@pytest.mark.parametrize("stem", ARTIFACTS)
def test_artifact_exists_and_self_verifies(stem):
    document = load(stem)
    field = next(key for key in document
                 if key.startswith(PREFIX) and key.endswith("sha256"))
    assert verify_canonical_hash(document, field)


def test_only_the_measurable_artifacts_were_emitted():
    found = sorted(path.name for path in RESULTS.glob(f"{PREFIX}*.json"))
    assert found == sorted(f"{PREFIX}{stem}_v1.json" for stem in ARTIFACTS)
    declared = load("final_readiness")["artifacts_that_cannot_exist"]
    assert declared["empty_placeholders_emitted"] == 0
    for name in declared["names"]:
        assert not (RESULTS / name).exists()


# ------------------------------------------------------------- the blocker
def specification_ids():
    ids = set()
    for split in ("train", "validation"):
        ids |= {path.stem for path in (SPECS / split).glob("*.json")}
    return ids


def test_the_official_v3_train_layouts_really_have_no_specification():
    """Re-measured against the filesystem, not read out of the artifact."""
    registry = load_v3_layout_registry(ROOT)
    train = sorted(registry["assignment"]["TRAIN"]["layout_ids"])
    assert len(train) == 20
    present = specification_ids()
    missing = [layout for layout in train if layout not in present]
    assert missing == train, "every official V3 TRAIN layout must be missing"
    assert load("execution_specification_blocker")["evidence"][
        "official_v3_train_layouts_without_specification"] == missing


def test_the_v3_validation_layouts_are_missing_too():
    registry = load_v3_layout_registry(ROOT)
    validation = sorted(registry["assignment"]["VALIDATION"]["layout_ids"])
    present = specification_ids()
    assert [layout for layout in validation if layout not in present] == validation


def test_only_the_v2_era_specifications_exist():
    present = specification_ids()
    assert len(present) == 30
    # train variants 00/01 and validation variant 00 -- nothing at a V3 offset
    assert not any(layout.endswith("-02") for layout in present)
    assert not any(layout.startswith("validation-") and layout.endswith("-01")
                   for layout in present)


def test_the_generator_cannot_even_enumerate_the_v3_offsets():
    from rvt_swarm.phase8.scenario import _SPLIT_OFFSETS, _SPLIT_VARIANTS
    train = [_SPLIT_OFFSETS["train"] + 0.11 * v for v in _SPLIT_VARIANTS["train"]]
    validation = [_SPLIT_OFFSETS["validation"] + 0.11 * v
                  for v in _SPLIT_VARIANTS["validation"]]
    producible = {round(value, 2) for value in train + validation}
    assert 0.22 not in producible
    assert 0.54 not in producible
    assert 0.65 not in producible


def test_the_split_manifests_do_not_carry_the_v3_layouts():
    registry = load_v3_layout_registry(ROOT)
    official = set(registry["assignment"]["TRAIN"]["layout_ids"]) | set(
        registry["assignment"]["VALIDATION"]["layout_ids"])
    declared = set()
    for split in ("train", "validation"):
        manifest = json.loads(
            (RESULTS / "splits" / f"{split}_layouts.json").read_text())
        declared |= {str(record["layout_id"])
                     for record in manifest["layout_records"]}
    assert official & declared == set()


def test_the_geometry_itself_is_not_missing():
    """The freeze is intact; only the compiled binding is absent."""
    registry = load_v3_layout_registry(ROOT)
    for group in ("TRAIN", "VALIDATION"):
        for record in registry["layout_records"][group]:
            assert len(record["geometry_sha256"]) == 64
            assert record["episode_horizon_seconds"] > 0
    assert load("execution_specification_blocker")["geometry_is_not_missing"][
        "registry_carries_geometry_sha256_for_every_v3_layout"] is True


def test_the_blocker_explains_why_earlier_qualification_missed_it():
    blocker = load("execution_specification_blocker")
    why = blocker["why_no_earlier_phase_caught_it"]
    assert why["canary_disjointness_was_correct"] is True
    assert "train-f1-00" in why["explanation"]
    assert blocker["scientific_contracts_changed"] == 0
    assert blocker["official_data_generated"] == 0


# ------------------------------------------------------------- prelaunch
def test_the_prelaunch_decision_is_no_go():
    go = load("prelaunch_go")
    assert go["DECISION"] == "NO_GO"
    assert go["official_train_launch_authorized_by_this_artifact"] is False
    assert go["decision_reason"] == (
        "OFFICIAL_V3_LAYOUT_EXECUTION_SPECIFICATIONS_DO_NOT_EXIST")


def test_the_image_and_source_identity_were_verified_before_the_stop():
    authority = load("prelaunch_go")["T1_production_authority"]
    assert authority["final_v3_production_image_sha256"].endswith(
        "a602ec015ff3d4063908f17e4d99087ce4aa89edda5853cf3483532eb53ab318")
    assert authority["embedded_source_commit"] == (
        "d635f17c8ef7e336fd54ff95a60dd608b61f3d7b")
    assert authority["image_verified_on_target"] is True
    assert authority["image_rebuilt"] is False
    assert authority["previous_image_used"] is False


def test_every_frozen_contract_was_verified_in_the_image():
    contracts = load("prelaunch_go")["T2_frozen_contracts_verified_in_image"]
    assert contracts["all_exact"] is True
    assert contracts["any_contract_changed"] == 0
    assert contracts["recoverability_v3_required_replica_invalidity_contract_v1_sha256"] == (
        "66bdd9ffce3f0b6417f20c4b41602b5ea4be266a728bcdb1dd306b0e27ef5c75")


def test_no_official_execution_ran_on_the_orchestration_host():
    proof = load("prelaunch_go")["T1_execution_location_proof"]
    assert proof["OFFICIAL_V3_EXECUTION_ON_UNAUTHORIZED_HOST"] is False
    assert proof["official_scientific_execution_on_the_orchestration_host"] == 0
    assert proof["remote_hostname"] == "avis"
    assert proof["wsl_distro"] == "Ubuntu-24.04"


def test_the_manifests_resolved_and_stayed_dry():
    roots = load("prelaunch_go")["T6_manifest_roots"]
    assert roots["official_v3_train_manifest_inner_root"] == (
        "6390cd31570d3dc12040d3522ca77db915171b82a2724db02825a32e90bd6edd")
    assert roots["official_v3_train_manifest_inner_root"] != (
        roots["official_v3_train_manifest_outer_artifact_sha256"])
    assert roots["train"]["source_episodes"] == 1200
    assert roots["train"]["layouts"] == 20
    assert roots["train"]["offsets"] == [0.22, 0.54]
    assert roots["train"]["dry"] == {"executed": 0, "generated": 0, "rows": 0}
    assert roots["validation"]["executed_in_this_phase"] == 0


def test_the_production_profile_was_not_changed():
    profile = load("prelaunch_go")["T20_production_profile"]
    assert profile == {"workers": 12, "numeric_threads_per_worker": 1,
                       "chunk": 1, "infrastructure_timeout_seconds": 243.0,
                       "changed": False}


# ------------------------------------------------------------- exclusion
def test_the_union_reconstructed_its_predecessor_exactly():
    union = load("prelaunch_exclusion_union")
    assert union["predecessor_reconstructed_exactly"] is True
    assert union["supersedes"]["identities"] == 1880
    assert union["supersedes"]["membership_removed"] == 0
    assert union["excluded_identity_count"] == 1884


def test_every_required_intersection_is_zero():
    intersections = load("prelaunch_exclusion_union")["T4_intersections"]
    assert intersections["official_v3_train_x_union"] == 0
    assert intersections["official_v3_validation_x_union"] == 0
    assert intersections["official_v3_train_x_official_v3_validation"] == 0
    assert intersections["qualification_canary_x_official_manifests"] == 0
    assert intersections["requirement_met"] is True


def test_axis_disjointness_holds_and_split_is_not_parsed_from_a_string():
    axes = load("prelaunch_exclusion_union")["T5_axis_disjointness"]
    assert all(value == 0 for value in axes["train_versus_validation"].values())
    assert all(value == 0 for value in axes["canary_versus_official"].values())
    assert axes["split_inferred_from_layout_id_string"] is False
    assert axes["requirement_met"] is True


def test_the_frozen_train_identities_were_not_altered():
    assert load("prelaunch_exclusion_union")["frozen_train_identities_altered"] == 0


# ------------------------------------------------------------- protection
def test_no_official_v3_data_of_any_kind_exists():
    protection = load("official_data_protection")
    for field in ("official_v3_train_source_episodes_executed",
                  "official_v3_train_stage_a_records",
                  "official_v3_train_candidate_rollouts",
                  "official_v3_train_target_v4_evaluations",
                  "official_v3_train_scientific_rows",
                  "T35_official_v3_validation_source_episodes_executed",
                  "T35_official_v3_validation_target_v4_evaluations",
                  "T35_official_v3_validation_rows",
                  "T36_models_trained", "T36_hp_trials", "T36_checkpoints",
                  "T37_v2_modified", "T38_study_a_n24_access",
                  "T38_study_b_access", "T38_final_test_access",
                  "residual_started", "executable_science_modified",
                  "frozen_manifests_modified"):
        assert protection[field] == 0, field
    assert protection["official_v3_train_namespace_created"] is False


def test_the_smoke_run_produced_nothing_durable():
    smoke = load("official_data_protection")["smoke_run"]
    assert smoke["durable_records_written"] == 0
    assert smoke["failed_before_any_durable_write"] is True
    assert smoke["official_data_produced"] == 0
    assert smoke["removed_from_target"] is True


def test_historical_gate_7_is_untouched():
    gate = load("official_data_protection")["T37_historical_gate_7"]
    assert gate["status"] == "FAILED_FOR_V2"
    assert gate["modified"] is False
    assert gate["recomputed_as_a_v3_gate"] is False
    assert gate["still_exceeds"] is True
    record = json.loads(
        (RESULTS / "phase9d_v2c_r_gate7_replica_instability_v1.json").read_text())
    assert record["result"] == "FAIL"


def test_verdict_is_a_with_do_not_proceed():
    readiness = load("final_readiness")
    assert readiness["verdict"] == "A"
    assert readiness["recommendation"] == "DO_NOT_PROCEED"
    assert readiness["official_v3_train_rows"] == 0
    assert readiness["validation_generation_authorized"] is False
    assert readiness["training_authorized"] is False
    assert readiness["blocker"] == (
        "OFFICIAL_V3_LAYOUT_EXECUTION_SPECIFICATIONS_DO_NOT_EXIST")


def test_the_work_completed_before_the_stop_is_recorded():
    readiness = load("final_readiness")
    assert len(readiness["completed_before_the_blocker"]) == 8
    assert len(readiness["blocked"]) >= 9
    assert readiness["next_phase_requires"]
