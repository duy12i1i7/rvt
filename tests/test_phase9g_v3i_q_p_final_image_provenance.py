"""Phase 9G-V3I-Q-P -- final image / source provenance closure.

The point of this phase was a provenance gap, not a science gap: the qualified
image's source commit predated the final closure commit. These tests pin the
diff that proved nothing executable moved, the one image that now carries the
closure commit, and the two builds that were performed rather than one being
quietly dropped.
"""
from __future__ import annotations

import json
import pathlib
import subprocess

import pytest

from rvt_swarm.phase8.common import verify_canonical_hash

ROOT = pathlib.Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results/rvt_fd24"
PREFIX = "phase9g_v3i_q_p_"

ARTIFACTS = (
    "commit_diff", "final_source_identity", "final_image_provenance",
    "final_image_suite", "numeric_fixture", "invalidity_regression",
    "reference_canary", "target_qualification", "runtime_anomaly_status",
    "official_data_protection", "final_readiness",
)

OLD_COMMIT = "beb65ba6eedcf0eebba07cde57a361b9956d15be"
FINAL_COMMIT = "d635f17c8ef7e336fd54ff95a60dd608b61f3d7b"
FINAL_IMAGE = ("sha256:a602ec015ff3d4063908f17e4d99087ce4aa89edda5853cf3483532"
               "eb53ab318")
PREFINAL_IMAGE = ("sha256:eaf52f7495f7eea1c1ae0392a4b688ce9918ecaee53d9be56ce1b"
                  "b5b9518f169")
CANARY_DIGEST = (
    "95dbdab76ce8066f6e535c09a86dca73bb4018e135c590a0ac72584b992df340")


def load(stem):
    return json.loads((RESULTS / f"{PREFIX}{stem}_v1.json").read_text())


@pytest.mark.parametrize("stem", ARTIFACTS)
def test_artifact_exists_and_self_verifies(stem):
    document = load(stem)
    field = next(key for key in document
                 if key.startswith(PREFIX) and key.endswith("sha256"))
    assert verify_canonical_hash(document, field)


def test_all_eleven_required_artifacts_and_no_more():
    found = sorted(path.name for path in RESULTS.glob(f"{PREFIX}*.json"))
    assert found == sorted(f"{PREFIX}{stem}_v1.json" for stem in ARTIFACTS)


# ---------------------------------------------------------------- P0 / P1
def test_the_full_shas_resolve_to_the_recorded_commits():
    for abbreviation, full in (("beb65ba", OLD_COMMIT), ("d635f17", FINAL_COMMIT)):
        resolved = subprocess.run(["git", "rev-parse", abbreviation], cwd=ROOT,
                                  check=True, capture_output=True,
                                  text=True).stdout.strip()
        assert resolved == full
        assert full.startswith(abbreviation)


def test_the_diff_is_purely_additive_and_touches_no_executable_surface():
    diff = load("commit_diff")
    counts = diff["classification_counts"]
    assert counts["RUNTIME_SCIENCE_CODE"] == 0
    assert counts["RUNTIME_NONSCIENCE_CODE"] == 0
    assert counts["BUILD_INPUT"] == 0
    assert counts["DEPENDENCY_INPUT"] == 0
    assert diff["PREFERRED_RESULT_MET"] is True
    assert diff["non_additive_changes"] == 0
    assert {entry["change"] for entry in diff["files"]} == {"A"}


def test_the_recorded_diff_still_matches_git():
    diff = load("commit_diff")
    actual = subprocess.run(
        ["git", "diff", "--name-status", f"{OLD_COMMIT}..{FINAL_COMMIT}"],
        cwd=ROOT, check=True, capture_output=True, text=True).stdout.splitlines()
    recorded = [f"{entry['change']}\t{entry['path']}" for entry in diff["files"]]
    assert sorted(actual) == sorted(recorded)
    assert diff["files_changed"] == len(actual) == 25


@pytest.mark.parametrize("surface", [
    "rvt_swarm", "scripts", "docker", "requirements.txt", "third_party",
])
def test_no_executable_or_build_surface_moved(surface):
    changed = subprocess.run(
        ["git", "diff", "--name-only", f"{OLD_COMMIT}..{FINAL_COMMIT}", "--",
         surface],
        cwd=ROOT, check=True, capture_output=True, text=True).stdout.split()
    assert changed == []


def test_the_previous_image_is_called_provenance_incomplete_not_science_incomplete():
    diff = load("commit_diff")
    assert diff["previous_image_qualification_incomplete"] is False
    assert diff["executable_or_build_inputs_changed_after_the_old_image"] is False
    assert "PROVENANCE" in diff["previous_image_qualification_status"]
    assert diff["hidden"] is False


# ---------------------------------------------------------------- P2 / P3
FROZEN = {
    "recoverability_probabilistic_target_v3_sha256":
        "a127bf9fbe907c81f2cd8037e94164f738ee756d7480c7db6955d7405bc355b6",
    "recoverability_replica_protocol_v3_sha256":
        "6c2143c4782f0d851205cb118a2ff1c3e33c8a6a3e3cdc2ce5a820106551fa9a",
    "recoverability_row_binding_v3_spec_sha256":
        "bdab65bdabbf503dc4d76d7d66d14c6504feb657b32d153a89643fab55058a8c",
    "recoverability_training_loss_v3_sha256":
        "fc9c093327eaaa5ae95c038cf36a2a16ff2fee6d5fdc125dd1106bc3a99dfc11",
    "recoverability_brier_metric_v3_sha256":
        "0bf6dee325825953d856fb4f6b5df190879424b0d5e8d29cbe55ac930f682f04",
    "recoverability_v3_required_replica_invalidity_contract_v1_sha256":
        "66bdd9ffce3f0b6417f20c4b41602b5ea4be266a728bcdb1dd306b0e27ef5c75",
    "source_acquisition_protocol_sha256":
        "19fa68a37d80f16ee1463b872f26402963daeb5a56f375423634a90dc1f3546d",
    "target_v4_contract_sha256":
        "54a0e0baff79fbdc320800b772f47a40ac06ac4f0e70d4fab1bf676c54b918ee",
    "v3_layout_split_registry_v2_sha256":
        "5494914e687a306b0288ce416e80d7c8a25f0f79377580eba58edc538d53680a",
}


@pytest.mark.parametrize("field,expected", sorted(FROZEN.items()))
def test_no_scientific_hash_changed(field, expected):
    assert load("final_source_identity")["frozen_contracts"][field] == expected


def test_the_final_source_commit_is_the_closure_commit():
    identity = load("final_source_identity")
    assert identity["FINAL_V3_EXECUTABLE_SOURCE_COMMIT"] == FINAL_COMMIT
    assert identity[
        "no_earlier_source_commit_is_acceptable_for_official_v3_generation"] is True
    assert identity["scientific_hash_changed"] == 0


def test_the_frozen_contracts_still_recompute_from_their_artifacts():
    from rvt_swarm.phase9g0r.contracts_v3 import verify_frozen_v3_contracts
    resolved = verify_frozen_v3_contracts(ROOT)
    for field, expected in FROZEN.items():
        if field in resolved:
            assert resolved[field] == expected


# ---------------------------------------------------------------- P4-P6, P19
def test_the_image_embeds_the_closure_commit():
    provenance = load("final_image_provenance")
    assert provenance["FINAL_V3_PRODUCTION_IMAGE_SHA256"] == FINAL_IMAGE
    assert provenance["source_commit"] == FINAL_COMMIT
    assert provenance["declared_revision_label"] == FINAL_COMMIT
    assert provenance["source_commit_read_from_inside_the_running_image"] == (
        FINAL_COMMIT)
    assert provenance["self_identity_matches"] is True
    assert provenance["architecture"] == "amd64/linux"


def test_the_build_context_was_clean():
    proof = load("final_image_provenance")["build_context_proof"]
    assert proof["clean_tree"] == 0
    assert proof["untracked_or_ignored_files_in_context"] == 0
    assert proof["checkout_commit"] == FINAL_COMMIT
    assert proof["bundle_integrity_verified"] is True
    assert len(proof["bundles_applied_in_order"]) == 3
    assert proof["package_upgrades"] == 0
    assert proof["debian_snapshot"] == "20260220T214329Z"


def test_both_builds_are_recorded_and_only_one_is_authorized():
    attempts = load("final_image_provenance")["build_attempts"]
    assert len(attempts) == 2
    authorized = [a for a in attempts if a["authorized_for_official_science"]]
    assert len(authorized) == 1
    assert authorized[0]["image"] == FINAL_IMAGE
    assert authorized[0]["status"] == "FINAL_V3_PRODUCTION_IMAGE"
    superseded = [a for a in attempts if not a["authorized_for_official_science"]]
    assert superseded[0]["status"] == "SUPERSEDED_BUILD_CONTEXT_HYGIENE"
    # both came from the same commit -- the difference was never executable
    assert {a["source_commit"] for a in attempts} == {FINAL_COMMIT}


def test_the_superseded_build_is_explained_not_merely_labelled():
    attempts = load("final_image_provenance")["build_attempts"]
    superseded = next(a for a in attempts
                      if a["status"] == "SUPERSEDED_BUILD_CONTEXT_HYGIENE")
    assert "unreachable from this commit" in superseded["reason"]
    assert superseded["size_bytes"] > authorized_size() * 1.5


def authorized_size():
    return next(a["size_bytes"] for a in load("final_image_provenance")[
        "build_attempts"] if a["authorized_for_official_science"])


def test_the_two_image_generations_are_unambiguous():
    status = load("final_image_provenance")["P19_historical_image_status"]
    assert status["pre_final"]["source_commit"] == OLD_COMMIT
    assert status["pre_final"]["image"] == PREFINAL_IMAGE
    assert status["pre_final"]["status"] == "PRE_FINAL_QUALIFICATION_IMAGE"
    assert status["pre_final"]["authorized_for_official_v3_generation"] is False
    assert status["pre_final"]["history_deleted"] is False
    assert status["final"]["source_commit"] == FINAL_COMMIT
    assert status["final"]["status"] == "FINAL_V3_PRODUCTION_IMAGE"
    assert status["final"]["authorized_for_official_v3_generation"] is True
    assert status["ambiguity_between_the_two"] == 0


def test_the_production_profile_is_unchanged():
    profile = load("final_image_provenance")["P20_production_profile"]
    assert profile["workers"] == 12
    assert profile["numeric_threads_per_worker"] == 1
    assert profile["chunk_size_atomic_units"] == 1
    assert profile["infrastructure_timeout_seconds"] == 243.0
    assert profile["changed_by_this_phase"] is False


# ---------------------------------------------------------------- P7-P9
def test_the_full_suite_in_the_final_image_is_clean_at_the_expected_count():
    suite = load("final_image_suite")["P7_full_suite_in_final_image"]
    assert suite["passed"] == 4317
    assert suite["failed"] == 0
    assert suite["expected_closure_count"] == 4317
    assert suite["count_matches_expectation"] is True
    assert suite["environment_exemptions"] == 0


def test_the_closure_count_plus_this_phase_accounts_for_the_repository():
    """4317 is what the image carries; the rest is this phase's own record tests.

    The image was built at the closure commit, so it cannot contain the tests
    written afterwards to describe it. The delta is asserted to be exactly this
    file rather than merely "larger than 4317".
    """
    def collected(target):
        output = subprocess.run(
            [".venv/bin/python", "-m", "pytest", target, "-q", "--co"],
            cwd=ROOT, capture_output=True, text=True).stdout
        return int(output.strip().rsplit("\n", 1)[-1].split()[0])

    total = collected("tests/")
    mine = collected(f"tests/{pathlib.Path(__file__).name}")
    assert total - mine == 4317


def test_the_invalidity_matrix_ran_inside_the_final_image():
    record = load("invalidity_regression")
    assert record["owner_frozen_matrix_executed_in_image"] is True
    assert record["tests_failed"] == 0
    for requirement, met in record["P9_requirements"].items():
        assert met is True, requirement
    assert record["semantics_changed_by_this_phase"] == 0


# ---------------------------------------------------------------- P8
def test_the_mandatory_brier_fixture_holds_in_the_final_image():
    fixture = load("numeric_fixture")["P8_mandatory_brier"]
    assert float(fixture["in_image"]) == 0.25
    assert float(fixture["reference_host"]) == 0.25
    assert fixture["match"] is True


def test_r1_bce_equivalence_is_exact_in_the_final_image():
    record = load("numeric_fixture")
    assert record["R1_equality_is_exact"] is True
    for pair in record["R1_exact_bce_equivalence"].values():
        assert pair["candidate_loss"] == pair["bce_with_logits"]


def test_event_weights_are_invariant_to_N_and_R_in_the_final_image():
    invariance = load("numeric_fixture")["event_weight_invariance"]
    assert invariance["distinct_values"] == 1
    assert invariance["holds"] is True
    weights = load("numeric_fixture")["event_weights"]
    assert set(weights) == {"W(N=5,R=1)", "W(N=16,R=1)", "W(N=5,R=3)",
                            "W(N=16,R=3)"}


def test_fixtures_are_bit_identical_to_the_reference_host():
    record = load("numeric_fixture")
    assert record["brier_bit_identical_mismatches_against_reference"] == 0
    assert record["loss_bit_identical_mismatches_against_reference"] == 0
    assert record["float64_repr_compared_not_approximated"] is True


# ---------------------------------------------------------------- P10-P12
def test_the_historical_digest_was_reproduced_not_replaced():
    canary = load("reference_canary")
    assert canary["P10_historical_qualified_digest"] == CANARY_DIGEST
    assert canary["recomputed_on_reference_host_at_closure_commit"] == CANARY_DIGEST
    assert canary["recomputed_in_final_image_on_target"] == CANARY_DIGEST
    assert canary["all_three_identical"] is True
    assert canary["new_digest_blessed"] is False
    assert canary["new_official_identities_chosen"] == 0


def test_worker_invariance_holds_inside_the_final_image():
    invariance = load("reference_canary")["P11_worker_invariance"]
    assert invariance["all_equal"] is True
    assert invariance["threads_per_worker"] == 1
    assert invariance["chunk"] == 1


def test_failure_resume_is_clean():
    resume = load("reference_canary")["P12_failure_resume"]
    assert resume["duplicates"] == 0
    assert resume["partial_supervised_rows"] == 0
    assert resume["seed_substitution"] == 0
    assert resume["identity_mismatch"] == 0
    assert resume["early_abort_scientific_path"] == 0
    assert resume["semantic_digest_matches_uninterrupted_run"] is True


# ---------------------------------------------------------------- P14-P17
def test_target_environment_is_recorded_as_observed():
    environment = load("target_qualification")["P14_environment"]
    assert environment["wsl_distribution"] == "Ubuntu-24.04"
    assert environment["architecture"] == "x86_64 / linux/amd64"
    assert environment["cpus"] == 24
    assert environment["docker_server"] == "29.6.1"
    assert environment["memory_bytes"] == 33323393024


def test_no_password_was_requested_or_recorded():
    access = load("target_qualification")["P14_access"]
    assert access["passwordless"] is True
    assert access["password_requested_or_used"] is False
    assert access["credential_material_recorded"] == "none"


def test_the_image_was_not_rebuilt_after_qualification():
    assert load("target_qualification")["image_rebuilt_after_qualification"] is False
    assert load("final_image_provenance")["rebuilt_after_qualification"] is False
    assert load("final_image_provenance")[
        "rebuilt_on_multiple_machines_to_compare_digests"] is False


def test_the_segfault_is_retained_as_a_transient_anomaly():
    anomaly = load("runtime_anomaly_status")
    assert anomaly["classification"] == "TRANSIENT_NONREPRODUCED_RUNTIME_ANOMALY"
    assert anomaly["this_closure"]["reproduced"] is False
    assert anomaly["TARGET_RUNTIME_STABILITY_REQUALIFICATION_REQUIRED"] is False
    assert anomaly["erased"] is False
    assert anomaly["science_blocker"] is False
    assert anomaly["scientific_protocol_changed"] == 0
    assert anomaly["cumulative_non_reproducing_runs"] == 13


# ---------------------------------------------------------------- P18 / P21
def test_official_v3_data_remains_untouched():
    protection = load("official_data_protection")
    assert protection["P18"] == {
        "official_v3_train_source_episodes_executed": 0,
        "official_v3_validation_source_episodes_executed": 0,
        "official_v3_target_v4_evaluations": 0,
        "official_v3_scientific_rows": 0,
        "qualification_canary_identities_overlapping_official_manifests": 0,
    }
    assert protection["sealed_domains"] == {
        "study_a_n24_access": 0, "study_b_access": 0, "final_test_access": 0,
        "training": 0, "hp_trials": 0}
    assert protection["executable_code_modified_by_this_phase"] == 0


def test_the_manifests_are_still_dry():
    manifests = load("official_data_protection")["manifests_remain_dry"]
    assert manifests["v3_train"]["executed"] == 0
    assert manifests["v3_validation"]["executed"] == 0
    assert manifests["v3_train"]["layouts"] == 20
    assert manifests["v3_validation"]["layouts"] == 10


def test_v2_and_gate_7_were_not_touched():
    protection = load("official_data_protection")
    assert protection["v2_modified"] == 0
    assert protection["historical_gate_7_modified"] == 0
    record = json.loads(
        (RESULTS / "phase9d_v2c_r_gate7_replica_instability_v1.json").read_text())
    assert record["result"] == "FAIL"
    assert 59 / 530 > 0.10


def test_every_p21_criterion_is_met():
    readiness = load("final_readiness")
    assert readiness["criteria_total"] == 13
    assert readiness["criteria_met"] == 13
    assert readiness["criteria_unmet"] == []
    assert all(item["met"] for item in readiness["P21_criteria"])


def test_verdict_is_c_with_train_only_authorization():
    readiness = load("final_readiness")
    assert readiness["verdict"] == "C"
    assert readiness["recommendation"] == (
        "AUTHORIZE_OFFICIAL_RECOVERABILITY_V3_TRAIN_GENERATION")
    assert readiness["recommendation_scope"] == "TRAIN ONLY"
    assert readiness["validation_generation_authorized"] is False
    assert readiness["training_authorized"] is False
    assert readiness["hp_search_authorized"] is False


def test_the_readiness_record_names_the_one_authorized_image_and_its_predecessor():
    readiness = load("final_readiness")
    assert readiness["FINAL_V3_PRODUCTION_IMAGE_SHA256"] == FINAL_IMAGE
    assert readiness["FINAL_V3_EXECUTABLE_SOURCE_COMMIT"] == FINAL_COMMIT
    assert readiness["pre_final_image"]["image"] == PREFINAL_IMAGE
    assert readiness["pre_final_image"][
        "authorized_for_official_v3_generation"] is False
    assert len(readiness["declared_notes"]) == 3
