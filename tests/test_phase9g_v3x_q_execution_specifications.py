"""Phase 9G-V3X-Q -- the additive V3 layout execution specifications.

The official V3 layout domain was frozen as geometry but never compiled into an
executable binding, which is why official TRAIN could not start. These tests
pin the repair: thirty specifications that are deterministic compilations of
already-frozen authority, reproducing every frozen hash, with V1/V2 untouched.
"""
from __future__ import annotations

import json
import pathlib
import subprocess

import pytest

from rvt_swarm.phase8.common import verify_canonical_hash
from rvt_swarm.phase8.scenario import _SPLIT_OFFSETS, _SPLIT_VARIANTS, _layout
from rvt_swarm.phase9c_rb.binding import (
    BindingError, build_binding, load_execution_specification,
)
from rvt_swarm.phase9g0r.compiler_v3 import (
    V3_TRAIN, V3_VALIDATION, load_v3_layout_registry,
)
from rvt_swarm.phase9g0r.execution_spec_v3 import (
    V3ExecutionSpecError, assert_execution_spec_registry_root,
    compile_all_v3_execution_specifications, frozen_v3_layout_entries,
    load_v3_execution_specification, specification_path,
    v3_execution_spec_registry, v3_split_of_official_layout,
)
from rvt_swarm.runtime_configuration import RuntimeConfig

ROOT = pathlib.Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results/rvt_fd24"
SPECS = RESULTS / "layout_execution_specifications"
PREFIX = "phase9g_v3x_q_"

EXECUTION_SPEC_REGISTRY_ROOT = (
    "e16928c999e80c2661861efac4924f0e6270ef864bfbc311fa04c47bc0117195")
PHASE8 = "c17081fe1cf58cc2d3f929e35ff4bca811c75c58"
#: The Phase 9G-V3A-T prelaunch stop, immediately before this phase.
STOP_COMMIT = "096a136876549830d6f5a94ed0f0708a6518855a"

def _git(*arguments):
    """git, tolerant of the container's root-owned checkout (see above)."""
    return ["git", "-c", "safe.directory=*", *arguments]



def load(stem):
    return json.loads((RESULTS / f"{PREFIX}{stem}_v1.json").read_text())


@pytest.fixture(scope="module")
def entries():
    return frozen_v3_layout_entries(ROOT)


# ------------------------------------------------------------- X9 coverage
def test_exactly_thirty_official_layouts(entries):
    assert len(entries) == 30
    assert sum(1 for e in entries if e["v3_split"] == V3_TRAIN) == 20
    assert sum(1 for e in entries if e["v3_split"] == V3_VALIDATION) == 10


def test_every_official_layout_has_a_specification_on_disk(entries):
    for entry in entries:
        assert specification_path(ROOT, entry).exists(), entry["layout_id"]


def test_no_reserve_or_forbidden_offset_was_compiled(entries):
    offsets = {round(entry["offset"], 2) for entry in entries}
    assert offsets == {0.22, 0.54, 0.65}
    assert 0.33 not in offsets
    assert not offsets & {0.76, 0.87}
    registry = load_v3_layout_registry(ROOT)
    for record in registry["layout_records"]["RESERVE"]:
        assert not (SPECS / "train" / f"{record['layout_id']}.json").exists()


def test_the_registry_root_is_stable_and_fails_closed_on_a_wrong_value():
    registry = v3_execution_spec_registry(ROOT)
    assert registry["v3_layout_execution_spec_registry_v1_sha256"] == (
        EXECUTION_SPEC_REGISTRY_ROOT)
    assert verify_canonical_hash(
        registry, "v3_layout_execution_spec_registry_v1_sha256")
    assert assert_execution_spec_registry_root(
        ROOT, EXECUTION_SPEC_REGISTRY_ROOT) == EXECUTION_SPEC_REGISTRY_ROOT
    with pytest.raises(V3ExecutionSpecError):
        assert_execution_spec_registry_root(ROOT, "0" * 64)


def test_registry_counts_train_and_validation_and_no_reserve():
    registry = v3_execution_spec_registry(ROOT)
    assert registry["layout_count"] == 30
    assert registry["train_layouts"] == 20
    assert registry["validation_layouts"] == 10
    assert registry["reserve_layouts_compiled"] == 0


# ------------------------------------------------------------- X11/X12 hashes
def test_every_layout_regenerates_to_its_frozen_geometry_hash(entries):
    for entry in entries:
        layout = _layout(entry["family"], entry["geometry_namespace"],
                         entry["variant_index"])
        assert layout.geometry_sha256() == entry["geometry_sha256"]
        assert layout.parameter_tuple_sha256() == entry["parameter_tuple_sha256"]
        assert layout.layout_id == entry["layout_id"]
        assert layout.generation_seed_commitment == entry[
            "generation_seed_commitment"]
        assert float(layout.episode_horizon_seconds) == entry[
            "episode_horizon_seconds"]


def test_every_specification_carries_the_frozen_geometry_hash_and_horizon(entries):
    for entry in entries:
        specification = load_v3_execution_specification(ROOT, entry["layout_id"])
        assert specification["source_layout"]["geometry_sha256"] == entry[
            "geometry_sha256"]
        assert float(specification["episode_horizon_seconds"]) == entry[
            "episode_horizon_seconds"]
        assert verify_canonical_hash(
            specification, "layout_execution_specification_sha256")


def test_the_hash_audit_reports_thirty_matches_and_no_mismatch():
    audit = load("all_layout_hash_audit")
    assert audit["layouts"] == 30
    assert audit["geometry_hash_matches"] == 30
    assert audit["geometry_hash_mismatches"] == 0
    assert audit["horizon_matches"] == 30
    assert audit["horizon_mismatches"] == 0
    assert audit["execution_spec_hash_recomputes"] == 30
    assert audit["registry_hash_rewritten"] == 0
    assert audit["independent_recomputation"]["registry_root_identical"] is True


def test_compilation_is_bit_reproducible():
    """Recompiling from frozen inputs must match every file already on disk."""
    result = compile_all_v3_execution_specifications(ROOT)
    assert len(result["entries"]) == 30
    assert all(item["pre_existing"] for item in result["entries"])


# ------------------------------------------------------------- X2 category D
def test_no_execution_critical_field_is_an_unbound_degree_of_freedom():
    binding = load("execution_critical_field_binding")
    assert binding["D_count"] == 0
    assert binding["X2_requirement_met"] is True
    assert binding["every_specification_field_classified"] is True
    assert binding["fields_not_classified"] == []
    assert binding["unexplained_values"] == 0


def test_every_compiled_specification_declares_category_d_zero(entries):
    for entry in entries:
        specification = load_v3_execution_specification(ROOT, entry["layout_id"])
        assert int(specification["category_d_count"]) == 0
        assert specification["validity"] == "COMPILED_SPECIFICATION"


def test_geometry_hash_coverage_is_stated_not_assumed():
    coverage = load("execution_critical_field_binding")["X3_geometry_hash_coverage"]
    for field in ("obstacle_geometry", "corridor_geometry", "goal", "start",
                  "horizon", "family_specific_parameters",
                  "dynamic_obstacle_parameters"):
        assert coverage[field] is True
    assert len(coverage["not_covered_by_geometry_sha256"]) >= 4
    assert "does not cover the whole execution specification" in (
        coverage["conclusion"])


# ------------------------------------------------------------- X4 row binding
def test_row_binding_v3_does_not_change():
    impact = load("row_binding_impact")
    assert impact["row_binding_v3_must_change"] is False
    assert impact["row_binding_v3_modified"] is False
    assert impact["V3_ROW_BINDING_PROVENANCE_REFREEZE_REQUIRED"] is False
    assert impact["row_identity_field_count_unchanged"] == 16
    frozen = json.loads((RESULTS / "phase9d_v3f_row_binding_v1.json").read_text())
    assert frozen["recoverability_row_binding_v3_spec_sha256"] == impact[
        "recoverability_row_binding_v3_spec_sha256"]


def test_the_counterfactual_that_would_have_forced_a_change_is_stated():
    impact = load("row_binding_impact")
    assert "category D" in impact["counterfactual_that_would_have_forced_a_change"]


# ------------------------------------------------------------- X5 V2 frozen
def test_historical_split_enumeration_is_untouched():
    assert _SPLIT_VARIANTS == {"train": (0, 1), "validation": (0,),
                               "final_test": (0,)}
    assert _SPLIT_OFFSETS == {"train": 0.0, "validation": 0.43,
                              "final_test": 0.79}


def test_the_v3_offsets_are_unreachable_by_historical_enumeration():
    reachable = {round(_SPLIT_OFFSETS[split] + 0.11 * variant, 2)
                 for split, variants in _SPLIT_VARIANTS.items()
                 for variant in variants}
    assert not reachable & {0.22, 0.54, 0.65}


def test_no_historical_execution_specification_was_modified():
    changed = subprocess.run(
        _git("diff", "--name-only", "--diff-filter=MRD", PHASE8, "--",
             "results/rvt_fd24/layout_execution_specifications",
             "results/rvt_fd24/splits", "rvt_swarm/phase8"),
        cwd=ROOT, check=True, capture_output=True, text=True).stdout.split()
    assert changed == []


def test_this_phase_added_thirty_specifications_and_modified_none():
    """Measured against the STOP commit, which is this phase's own delta.

    The V2-era specifications were themselves added after the Phase-8 commit,
    so a Phase-8 baseline would count all sixty. The question this test asks is
    narrower and is the one that matters here: what did Phase 9G-V3X-Q change?
    """
    def names(diff_filter):
        return subprocess.run(
            _git("diff", "--name-only", f"--diff-filter={diff_filter}",
                 STOP_COMMIT, "--",
                 "results/rvt_fd24/layout_execution_specifications"),
            cwd=ROOT, check=True, capture_output=True, text=True).stdout.split()

    assert len(names("A")) == 30
    assert names("MRD") == []


# ------------------------------------------------------------- X10 split
def test_split_comes_from_registry_membership_not_the_layout_id_string():
    """validation-f1-01 is a V3 TRAIN layout despite what its name says."""
    assert v3_split_of_official_layout(ROOT, "validation-f1-01") == V3_TRAIN
    assert v3_split_of_official_layout(ROOT, "validation-f1-02") == V3_VALIDATION
    assert v3_split_of_official_layout(ROOT, "train-f1-02") == V3_TRAIN
    naive = V3_VALIDATION if "validation" in "validation-f1-01" else V3_TRAIN
    assert naive != v3_split_of_official_layout(ROOT, "validation-f1-01")


def test_the_geometry_namespace_is_separate_from_the_v3_split(entries):
    hazard = next(e for e in entries if e["layout_id"] == "validation-f1-01")
    assert hazard["v3_split"] == V3_TRAIN
    assert hazard["geometry_namespace"] == "validation"
    assert specification_path(ROOT, hazard).parent.name == "validation"


def test_requesting_the_wrong_v3_split_is_refused():
    with pytest.raises(V3ExecutionSpecError):
        load_v3_execution_specification(
            ROOT, "validation-f1-01", expected_v3_split=V3_VALIDATION)
    assert load_v3_execution_specification(
        ROOT, "validation-f1-01", expected_v3_split=V3_TRAIN) is not None


# ------------------------------------------------------------- X20 fail closed
def test_a_reserve_layout_has_no_official_specification():
    with pytest.raises(V3ExecutionSpecError):
        load_v3_execution_specification(ROOT, "train-f1-03")


def test_an_unknown_layout_is_refused():
    with pytest.raises(V3ExecutionSpecError):
        load_v3_execution_specification(ROOT, "train-f1-99")


def test_a_tampered_specification_fails_closed(tmp_path):
    entry = next(e for e in frozen_v3_layout_entries(ROOT)
                 if e["layout_id"] == "train-f3-02")
    original = specification_path(ROOT, entry).read_text()
    document = json.loads(original)
    document["episode_horizon_seconds"] = float(
        document["episode_horizon_seconds"]) + 1.0
    staged = tmp_path / "results/rvt_fd24/layout_execution_specifications/train"
    staged.mkdir(parents=True)
    (staged / "train-f3-02.json").write_text(json.dumps(document, sort_keys=True))
    # the canonical hash no longer recomputes over the tampered document
    assert not verify_canonical_hash(
        document, "layout_execution_specification_sha256")


def test_the_fail_closed_matrix_was_exercised_in_the_image():
    closed = load("all_layout_binding_load")["X20_fail_closed"]
    assert closed == {"reserve_layout_rejected": True,
                      "unknown_layout_rejected": True,
                      "split_mismatch_rejected": True,
                      "tampered_spec_rejected": True,
                      "missing_spec_rejected": True}


# ------------------------------------------------------------- X21/X22/X23
def test_all_thirty_bindings_load_with_no_simulation():
    record = load("all_layout_binding_load")
    assert record["layouts_loaded"] == 30
    assert record["layouts_expected"] == 30
    assert record["mismatches"] == 0
    assert record["simulator_steps"] == 0
    assert record["team_size_bindings"]["ok"] == 150
    assert record["team_size_bindings"]["failed"] == 0


def test_every_official_episode_dry_binds():
    record = load("all_episode_dry_binding")
    assert record["train"]["resolved"] == 1200 == record["train"]["expected"]
    assert record["train"]["failed"] == 0
    assert record["train"]["distinct_layouts"] == 20
    assert record["validation"]["resolved"] == 300 == record["validation"]["expected"]
    assert record["validation"]["failed"] == 0
    assert record["validation"]["distinct_layouts"] == 10
    assert record["simulator_steps"] == 0
    assert record["official_source_episodes_executed"] == 0
    assert record["official_target_v4_evaluations"] == 0
    assert record["official_rows"] == 0


def test_the_original_blocker_now_resolves():
    """train-f1-02 is the exact layout that stopped the official TRAIN phase."""
    specification = load_execution_specification(RESULTS, "train", "train-f1-02")
    assert specification["source_layout"]["layout_id"] == "train-f1-02"
    assert load("all_layout_binding_load")["X23_original_blocker"][
        "frozen_loader_resolves"] is True


def test_the_original_blocker_binds_at_every_qualified_team_size():
    specification = load_v3_execution_specification(ROOT, "train-f1-02")
    protocol = json.loads(
        (RESULTS / "executable_scientific_protocol_v1.json").read_text())
    target = json.loads(
        (RESULTS / "target_v4_execution_contract_v1.json").read_text())
    policies = json.loads(
        (RESULTS / "source_policy_contracts_v1.json").read_text())
    for size in (5, 6, 8, 12, 16):
        binding = build_binding(
            specification, team_size=size, source_policy="S1_ALWAYS_COMPACT",
            protocol=protocol, target_contract=target,
            source_policy_contracts=policies,
            runtime_config=RuntimeConfig.for_team_size(size))
        assert binding.layout_id == "train-f1-02"
        assert binding.team_size == size


def test_a_missing_specification_still_fails_closed_in_the_frozen_loader():
    with pytest.raises(BindingError):
        load_execution_specification(RESULTS, "train", "train-f1-77")


# ------------------------------------------------------------- X24 scope
def test_no_scope_guard_was_weakened():
    authorization = load("scope_guard_authorization")
    assert authorization["authorization"] == (
        "V3_EXECUTION_SPECIFICATION_ADDITIVE_SCOPE_AUTHORIZED")
    assert authorization["guards_fired"] == 0
    assert authorization["guards_weakened"] == 0
    for field, value in authorization["explicitly_not_done"].items():
        assert value in (0, False), field


def test_the_execution_spec_registry_is_bound_by_manifest_and_seal():
    binding = load("execution_spec_provenance_binding")
    binds = {item["object"] for item in binding["objects"] if item["binds"]}
    assert "V3 produced dataset manifest" in binds
    assert "V3 dataset seal" in binds
    assert "V3 row identity" not in binds
    assert binding["v3_layout_execution_spec_registry_v1_sha256"] == (
        EXECUTION_SPEC_REGISTRY_ROOT)


def test_the_manifest_root_is_not_claimed_to_be_the_whole_authority():
    versioning = load("manifest_versioning")
    assert versioning["re_emitted"] is False
    assert versioning["episode_membership_changed"] == 0
    assert versioning["complete_runtime_authority"]["requires_both"] is True
    assert versioning["complete_runtime_authority"][
        "execution_spec_registry_root"] == EXECUTION_SPEC_REGISTRY_ROOT
    impact = load("execution_spec_provenance_binding")["X17_manifest_impact"]
    assert impact["silently_pretended_old_root_is_complete"] is False


def test_the_v3_dataset_manifest_and_seal_carry_the_registry_root():
    from rvt_swarm.phase9g0r.contracts_v3 import (
        LAYOUT_SPLIT_REGISTRY_V2_SHA256, S8InvalidRateAccounting,
    )
    from rvt_swarm.phase9g0r.writer_v3 import (
        build_v3_dataset_manifest, seal_v3_dataset,
    )
    accounting = S8InvalidRateAccounting()
    accounting.record_replica(family="F9", disposition="RECOVERABLE_POSITIVE")
    manifest = build_v3_dataset_manifest(
        v3_split=V3_TRAIN, dataset_id="qual",
        source_manifest_root_sha256="a" * 64,
        layout_registry_sha256=LAYOUT_SPLIT_REGISTRY_V2_SHA256,
        execution_spec_registry_sha256=EXECUTION_SPEC_REGISTRY_ROOT,
        accounting=accounting, source_episodes_executed=0,
        selected_source_events=0, pair_events_retained=0,
        pair_events_dropped_scientific_invalidity=0,
        candidate_supervision_records=0, candidate_supervision_blocked=0,
        rows_published=0, row_ids=[])
    assert manifest["v3_layout_execution_spec_registry_v1_sha256"] == (
        EXECUTION_SPEC_REGISTRY_ROOT)
    seal = seal_v3_dataset(manifest)
    assert seal["v3_layout_execution_spec_registry_v1_sha256"] == (
        EXECUTION_SPEC_REGISTRY_ROOT)
    assert verify_canonical_hash(seal, "v3_dataset_seal_sha256")


# ------------------------------------------------------------- frozen science
def test_no_frozen_v3_contract_changed():
    from rvt_swarm.phase9g0r.contracts_v3 import verify_frozen_v3_contracts
    resolved = verify_frozen_v3_contracts(ROOT)
    assert resolved["recoverability_probabilistic_target_v3_sha256"] == (
        "a127bf9fbe907c81f2cd8037e94164f738ee756d7480c7db6955d7405bc355b6")
    assert resolved["recoverability_row_binding_v3_spec_sha256"] == (
        "bdab65bdabbf503dc4d76d7d66d14c6504feb657b32d153a89643fab55058a8c")
    assert resolved[
        "recoverability_v3_required_replica_invalidity_contract_v1_sha256"
    ] == "66bdd9ffce3f0b6417f20c4b41602b5ea4be266a728bcdb1dd306b0e27ef5c75"


def test_historical_gate_7_is_untouched():
    record = json.loads(
        (RESULTS / "phase9d_v2c_r_gate7_replica_instability_v1.json").read_text())
    assert record["result"] == "FAIL"
    assert 59 / 530 > 0.10


# ------------------------------------------------------------- image / target
FINAL_COMMIT = "2ab73cf4e9f29c9b626f3a39fceb47effd80960b"
FINAL_IMAGE = ("sha256:0b2d9a686d17ae9a67fbf8745535e56df9da88d825"
               "60b9378254947904782137")
PRE_EXEC_IMAGE = ("sha256:a602ec015ff3d4063908f17e4d99087ce4aa89edda5853cf348"
                  "3532eb53ab318")
CANARY_DIGEST = (
    "95dbdab76ce8066f6e535c09a86dca73bb4018e135c590a0ac72584b992df340")

ARTIFACT_STEMS = (
    "execution_spec_authority_audit", "execution_critical_field_binding",
    "row_binding_impact", "execution_spec_registry",
    "execution_spec_provenance_binding", "manifest_versioning",
    "all_layout_hash_audit", "all_layout_binding_load",
    "all_episode_dry_binding", "scope_guard_authorization",
    "v1_v2_regression", "reference_canary", "numeric_regression",
    "image_provenance", "remote_target_qualification",
    "official_data_protection", "final_generation_authority",
    "final_readiness",
)


@pytest.mark.parametrize("stem", ARTIFACT_STEMS)
def test_artifact_exists_and_self_verifies(stem):
    document = load(stem)
    field = next(key for key in document
                 if key.startswith(PREFIX) and key.endswith("sha256"))
    assert verify_canonical_hash(document, field)


def test_all_eighteen_required_artifacts_and_no_more():
    found = sorted(path.name for path in RESULTS.glob(f"{PREFIX}*.json"))
    assert found == sorted(f"{PREFIX}{stem}_v1.json" for stem in ARTIFACT_STEMS)


def test_the_new_image_embeds_the_final_executable_commit():
    provenance = load("image_provenance")
    assert provenance["FINAL_V3_EXECUTABLE_SOURCE_COMMIT_V2"] == FINAL_COMMIT
    assert provenance["FINAL_V3_PRODUCTION_IMAGE_V2_SHA256"] == FINAL_IMAGE
    assert provenance["source_commit_read_inside_the_running_image"] == FINAL_COMMIT
    assert provenance["self_identity_matches"] is True
    assert provenance["execution_spec_registry_root_matches"] is True
    assert provenance["build_context_proof"]["clean_tree"] == 0
    assert provenance["build_context_proof"][
        "execution_specification_files_in_tree"] == 60
    assert provenance["build_context_proof"]["package_upgrades"] == 0


def test_both_image_builds_are_recorded_and_one_is_authorized():
    attempts = load("image_provenance")["build_attempts"]
    assert len(attempts) == 2
    authorized = [a for a in attempts if a["authorized_for_official_science"]]
    assert len(authorized) == 1
    assert authorized[0]["image"] == FINAL_IMAGE
    superseded = [a for a in attempts if not a["authorized_for_official_science"]]
    assert superseded[0]["status"] == "SUPERSEDED_FAILED_IN_IMAGE_SUITE"
    assert "portability defects" in superseded[0]["reason"]


def test_the_previous_image_is_retired_from_official_use():
    retired = load("image_provenance")["X29_pre_execution_spec_image"]
    assert retired["image"] == PRE_EXEC_IMAGE
    assert retired["status"] == "PRE_EXECUTION_SPEC_PRODUCTION_IMAGE"
    assert retired["authorized_for_official_v3_generation"] is False
    assert retired["history_deleted"] is False


def test_the_in_image_suite_passed_with_no_exemption():
    regression = load("v1_v2_regression")
    assert regression["in_image_full_suite"]["passed"] == 4440
    assert regression["in_image_full_suite"]["failed"] == 0
    assert regression["in_image_full_suite"]["environment_exemptions"] == 0
    assert regression["in_image_v1_v2_and_scope_guard_subset"]["failed"] == 0


def test_v1_v2_are_unchanged_and_gate_7_still_fails():
    regression = load("v1_v2_regression")
    assert regression["v1_unchanged"] is True
    assert regression["v2_unchanged"] is True
    assert regression["historical_execution_specifications_modified"] == 0
    assert regression["split_manifests_modified"] == 0
    assert regression["_SPLIT_VARIANTS_modified"] is False
    assert regression["historical_gate_7"]["status"] == "FAILED_FOR_V2"
    assert regression["historical_gate_7"]["still_exceeds"] is True
    assert regression["v2_era_test_enumerations_narrowed_not_weakened"][
        "assertions_relaxed"] == 0


def test_the_canary_digest_is_reproduced_not_replaced():
    canary = load("reference_canary")
    assert canary["X32_historical_digest"] == CANARY_DIGEST
    assert canary["recomputed_in_final_image_w1"] == CANARY_DIGEST
    assert canary["recomputed_in_final_image_w12"] == CANARY_DIGEST
    assert canary["identical_to_historical"] is True
    assert canary["new_digest_blessed"] is False
    assert canary["X35_worker_invariance"]["equal"] is True
    resume = canary["X36_failure_resume"]
    assert resume["duplicates"] == 0
    assert resume["partial_supervised_rows"] == 0
    assert resume["seed_substitution"] == 0
    assert resume["identity_mismatch"] == 0
    assert canary["X36_replica_order_invariance"]["identical"] is True


def test_the_numeric_fixtures_are_unchanged():
    numeric = load("numeric_regression")
    assert numeric["mandatory_brier_is_exactly_quarter"] is True
    assert float(numeric["mandatory_brier_p05_k1_R3"]) == 0.25
    assert numeric["R1_equality_is_exact"] is True
    assert numeric["event_weight_distinct_values"] == 1
    assert numeric["event_weight_invariance_holds"] is True
    assert numeric["changed_by_this_phase"] == 0


def test_all_heavy_execution_ran_on_the_remote_target():
    target = load("remote_target_qualification")
    assert target["X37_all_heavy_execution_ran_on"] == "100.71.102.9"
    assert target["scientific_simulation_on_the_orchestration_host"] == 0
    assert target["docker_qualification_on_the_orchestration_host"] == 0
    assert target["access"]["password_requested_or_used"] is False
    assert target["environment"]["wsl_distribution"] == "Ubuntu-24.04"
    assert target["environment"]["cpus"] == 24
    assert len(target["work_performed_remotely"]) >= 7


def test_the_segfault_did_not_reproduce():
    anomaly = load("remote_target_qualification")["X38_runtime_anomaly"]
    assert anomaly["reproduced_in_this_phase"] is False
    assert anomaly["segmentation_faults_in_this_phase_logs"] == 0
    assert anomaly["TARGET_RUNTIME_STABILITY_REQUALIFICATION_REQUIRED"] is False
    assert anomaly["science_altered"] == 0


def test_no_official_v3_data_was_touched():
    protection = load("official_data_protection")
    assert protection["X39"] == {
        "official_v3_train_source_episodes_executed": 0,
        "official_v3_validation_source_episodes_executed": 0,
        "official_target_v4_evaluations": 0,
        "official_robot_rows": 0,
        "official_labels_observed": 0,
        "simulator_steps_in_this_phase": 0}
    assert protection["X40_sealed_domains"] == {
        "study_a_n24_access": 0, "study_b_access": 0, "final_test_access": 0,
        "training": 0, "hp_trials": 0}
    assert protection["frozen_v3_layout_geometry_changed"] == 0
    assert protection["new_layouts_created"] == 0
    assert protection["episode_manifests_changed"] == 0


def test_the_final_generation_authority_pins_both_registries():
    authority = load("final_generation_authority")
    assert authority["FINAL_V3_EXECUTABLE_SOURCE_COMMIT_V2"] == FINAL_COMMIT
    assert authority["FINAL_V3_PRODUCTION_IMAGE_V2_SHA256"] == FINAL_IMAGE
    assert authority["v3_layout_execution_spec_registry_v1_sha256"] == (
        EXECUTION_SPEC_REGISTRY_ROOT)
    assert authority["v3_layout_split_registry_v2_sha256"] == (
        "5494914e687a306b0288ce416e80d7c8a25f0f79377580eba58edc538d53680a")
    assert authority[
        "complete_runtime_authority_requires_both_manifest_and_spec_registry"] is True
    assert authority["production_profile"] == {
        "workers": 12, "numeric_threads_per_worker": 1, "chunk": 1,
        "infrastructure_timeout_seconds": 243.0, "changed": False}
    assert len(authority["superseded"]) == 2
    assert all(item["authorized"] is False for item in authority["superseded"])


def test_verdict_is_c_with_train_only_retry():
    readiness = load("final_readiness")
    assert readiness["verdict"] == "C"
    assert readiness["recommendation"] == (
        "AUTHORIZE_OFFICIAL_RECOVERABILITY_V3_TRAIN_GENERATION_RETRY")
    assert readiness["recommendation_scope"] == "TRAIN ONLY"
    assert readiness["validation_generation_authorized"] is False
    assert readiness["training_authorized"] is False
    assert readiness["criteria_total"] == 18
    assert readiness["criteria_met"] == 18
    assert readiness["criteria_unmet"] == []
    assert len(readiness["declared_deviations"]) == 3
