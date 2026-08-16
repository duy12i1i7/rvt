"""Phase 9G-V2Q -- Recoverability V2 executable/production qualification.

These tests pin what the qualification canary established and, just as
importantly, pin the three blocking findings so they cannot be quietly lost:
the frozen V2 protocol has no executable binding in the production path, the
production producer still assigns GENERATION_INVALID to unreached source
states, and the frozen row identity has no field for the V2 acquisition
protocol hash.
"""

from __future__ import annotations

import inspect
import json
import pathlib

import pytest

from rvt_swarm.phase8.common import verify_canonical_hash
from rvt_swarm.phase9d_h1r.acquisition_v2 import (
    DEFAULT_K, REALIZED_TRAJECTORY_UNIFORM_K, acquisition_protocol_v2_sha256,
    frozen_acquisition_protocol_v2, frozen_acquisition_protocol_v2_sha256,
)
from rvt_swarm.phase9d_h1r.manifest_v2 import (
    FROZEN_DECISION_EVENT_CAP, FROZEN_SOURCE_EPISODE_BUDGET,
)

ROOT = pathlib.Path("results/rvt_fd24")

FROZEN_SHA = frozen_acquisition_protocol_v2_sha256(
    frozen_acquisition_protocol_v2(
        design_protocol_sha256=acquisition_protocol_v2_sha256()))

ARTIFACTS = {
    "image": ("phase9g_v2q_image_qualification_v1.json",
              "phase9g_v2q_image_qualification_sha256"),
    "gap": ("phase9g_v2q_executable_binding_gap_v1.json",
            "phase9g_v2q_executable_binding_gap_sha256"),
    "replay": ("phase9g_v2q_source_selection_replay_v1.json",
               "phase9g_v2q_source_selection_replay_sha256"),
    "candidate": ("phase9g_v2q_candidate_canary_audit_v1.json",
                  "phase9g_v2q_candidate_canary_audit_sha256"),
    "dry_compile": ("phase9g_v2q_official_manifest_dry_compile_v1.json",
                    "phase9g_v2q_official_manifest_dry_compile_sha256"),
    "performance": ("phase9g_v2q_performance_and_cost_projection_v1.json",
                    "phase9g_v2q_performance_and_cost_projection_sha256"),
    "canary_exclusion": ("phase9g_v2q_qualification_canary_exclusion_set_v1.json",
                         "phase9g_v2q_qualification_canary_exclusion_set_sha256"),
    "readiness": ("phase9g_v2q_train_generation_readiness_v1.json",
                  "phase9g_v2q_train_generation_readiness_sha256"),
}


def load(name):
    path, _field = ARTIFACTS[name]
    return json.loads((ROOT / path).read_text(encoding="ascii"))


@pytest.mark.parametrize("name", sorted(ARTIFACTS))
def test_artifact_hashes_canonically(name: str) -> None:
    path, field = ARTIFACTS[name]
    assert verify_canonical_hash(
        json.loads((ROOT / path).read_text(encoding="ascii")), field)


# ---------------------------------------------------------------------------
# the three blocking findings, pinned against the live source
# ---------------------------------------------------------------------------
def test_no_production_module_binds_the_v2_acquisition_package() -> None:
    """V2Q-F1/F2/F3 rest on this. If it ever becomes false, the gap artifact and
    the readiness verdict must be revisited."""
    offenders = []
    for package in ("phase9g0r", "phase9"):
        for path in (pathlib.Path("rvt_swarm") / package).rglob("*.py"):
            if "phase9d_h1r" in path.read_text(encoding="utf-8"):
                offenders.append(str(path))
    assert offenders == [], (
        "a production module now references the V2 acquisition package; "
        "phase9g_v2q_executable_binding_gap_v1.json is stale")


def test_production_compiler_still_reads_v1_scheduled_events() -> None:
    from rvt_swarm.phase9g0r import compiler
    source = inspect.getsource(compiler.compile_recoverability_tasks)
    assert "decision_event_jobs" in source
    assert "resolved_control_step" in source
    assert "enumerate_realized_source_universe" not in source


def test_production_producer_still_has_the_unreached_state_invalid_branch() -> None:
    from rvt_swarm.phase9g0r import producer
    source = inspect.getsource(producer.produce_recoverability_candidate)
    assert "source_terminated_before_event" in source
    assert "control_step < task.resolved_control_step" in source


def test_row_identity_has_no_v2_acquisition_protocol_field() -> None:
    from rvt_swarm.phase9g0r.contracts import RECOVERABILITY_ROW_IDENTITY_FIELDS
    assert not any("acquisition" in name
                   for name in RECOVERABILITY_ROW_IDENTITY_FIELDS)
    assert not any("source_state_fingerprint" in name
                   for name in RECOVERABILITY_ROW_IDENTITY_FIELDS)


def test_gap_artifact_records_all_three_blocking_findings() -> None:
    gap = load("gap")
    assert gap["status"] == "V2_NOT_BOUND_TO_THE_PRODUCTION_EXECUTABLE_PATH"
    assert gap["production_modules_referencing_phase9d_h1r"] == 0
    assert [f["id"] for f in gap["findings"]] == ["V2Q-F1", "V2Q-F2", "V2Q-F3"]
    assert all(f["severity"] == "BLOCKING" for f in gap["findings"])
    assert gap["science_undefined"] is False
    assert gap["science_change_required"] is False
    assert gap["v2_acquisition_module_conforms_to_frozen_protocol"] is True


# ---------------------------------------------------------------------------
# source acquisition canary
# ---------------------------------------------------------------------------
def test_source_replay_covers_the_whole_nonsealed_domain() -> None:
    replay = load("replay")
    assert replay["families"] == ["F%d" % i for i in range(1, 11)]
    assert replay["team_sizes"] == [5, 6, 8, 12, 16]
    assert 24 not in replay["team_sizes"]
    assert replay["acquisition_protocol_sha256"] == FROZEN_SHA
    assert replay["rule"] == REALIZED_TRAJECTORY_UNIFORM_K
    assert replay["K"] == DEFAULT_K == 5


def test_no_fabricated_source_state_and_all_invariants_pass() -> None:
    replay = load("replay")
    assert replay["fabricated_states"] == 0
    assert replay["all_q8_invariants_pass"] is True
    for episode in replay["per_episode"]:
        checks = episode["checks"]
        assert all(checks.values()), (episode["episode_id"], checks)
        assert len(episode["selected_indices"]) <= 5
        assert len(set(episode["selected_indices"])) == \
            len(episode["selected_indices"])
        if episode["M"] == 0:
            assert episode["selected_count"] == 0
        elif episode["M"] <= 5:
            assert episode["selected_count"] == episode["M"]
        else:
            assert episode["selected_indices"] == sorted(
                {(j * (episode["M"] - 1)) // 4 for j in range(5)})
            assert episode["selected_indices"][0] == 0
            assert episode["selected_indices"][-1] == episode["M"] - 1


def test_worker_count_and_order_do_not_change_source_selection() -> None:
    invariance = load("replay")["worker_invariance"]
    assert invariance["w1_equals_w12"] is True
    assert invariance["order_invariant"] is True
    assert invariance["digest_w1"] == invariance["digest_w12"] == \
        invariance["digest_reverse_order"]


# ---------------------------------------------------------------------------
# candidate canary
# ---------------------------------------------------------------------------
def test_candidate_canary_publishes_exactly_two_n_rows_or_none() -> None:
    audit = load("candidate")
    assert audit["partial_publications"] == 0
    assert audit["duplicate_row_ids"] == 0
    assert audit["two_n_publication_verified"] is True
    for family in audit["per_family"]:
        assert family["rows"] == family["expected_rows"]
        assert family["rows"] == 2 * family["team_size"] * family["events"]


def test_f8_f9_use_three_replicas_and_others_use_one() -> None:
    audit = load("candidate")
    assert audit["f8_f9_three_replicas"] is True
    assert audit["other_families_one_replica"] is True
    for family in audit["per_family"]:
        expected = 3 if family["family"] in ("F8", "F9") else 1
        assert family["replicas_required"] == expected


def test_no_unreached_state_produced_generation_invalid() -> None:
    semantics = load("candidate")["generation_invalid_semantics"]
    assert semantics["unreached_state_produced_generation_invalid"] == 0
    assert semantics["every_generation_invalid_followed_an_attempted_rollout"] is True
    assert load("candidate")["generation_invalid_aggregates"] == 0


def test_candidate_blindness_holds_at_runtime() -> None:
    blindness = load("candidate")["candidate_blindness"]
    assert blindness["selection_finalized_before_any_candidate_executed"] is True
    assert blindness["selection_unchanged_after_candidates"] is True
    assert blindness["candidate_execution_order_invariant"] is True


def test_timeout_stayed_operational_only() -> None:
    timeout = load("candidate")["timeout"]
    assert timeout["reference_infrastructure_timeout_seconds"] == 243.0
    assert timeout["timeout_changed"] is False
    assert timeout["timeout_misclassified_as_scientific_outcome"] == 0
    assert timeout["exceeded"] is False


def test_candidate_canary_wrote_no_official_namespace() -> None:
    audit = load("candidate")
    assert audit["official_namespace_written"] is False
    assert audit["provenance_class"] == "QUALIFICATION_CANARY_NON_OFFICIAL"


# ---------------------------------------------------------------------------
# canary exclusion
# ---------------------------------------------------------------------------
def test_qualification_canary_identities_are_permanently_excluded() -> None:
    exclusion = load("canary_exclusion")
    assert exclusion["permanent"] is True
    assert exclusion["excluded_identity_count"] == \
        len(exclusion["excluded_identities"])
    identities = [e["design_pilot_identity_sha256"]
                  for e in exclusion["excluded_identities"]]
    assert len(set(identities)) == len(identities)
    for entry in exclusion["excluded_identities"]:
        assert entry["study"] == "study_a_qualification_canary"
        assert entry["split"] == "qualification_canary"
        assert entry["team_size"] in (5, 6, 8, 12, 16)
    assert exclusion["study_a_n24_identities"] == 0
    assert exclusion["study_b_identities"] == 0
    assert exclusion["final_test_identities"] == 0


def test_canary_exclusion_is_additive_to_the_design_pilot_set() -> None:
    exclusion = load("canary_exclusion")
    reference = exclusion["additive_to"]
    assert reference["path"] == \
        "results/rvt_fd24/phase9d_h1r_design_pilot_exclusion_set_v1.json"
    assert (ROOT / "phase9d_h1r_design_pilot_exclusion_set_v1.json").exists()
    pilot = json.loads(
        (ROOT / "phase9d_h1r_design_pilot_exclusion_set_v1.json").read_text())
    pilot_ids = {e["design_pilot_identity_sha256"]
                 for e in pilot["excluded_identities"]}
    canary_ids = {e["design_pilot_identity_sha256"]
                  for e in exclusion["excluded_identities"]}
    assert not (pilot_ids & canary_ids), "canary reused a design-pilot identity"


# ---------------------------------------------------------------------------
# dry manifest compile
# ---------------------------------------------------------------------------
def test_dry_compile_matches_the_frozen_source_budget_exactly() -> None:
    dry = load("dry_compile")
    assert dry["executed"] is False
    assert dry["materialized_candidate_results"] == 0
    for split, budget in FROZEN_SOURCE_EPISODE_BUDGET.items():
        block = dry["splits"][split]
        assert block["source_episodes"] == budget
        assert block["budget_exact"] is True
        assert block["maximum_selected_source_events"] == budget * DEFAULT_K
        assert block["maximum_selected_source_events"] == \
            FROZEN_DECISION_EVENT_CAP[split]
        assert block["saturates_cap"] is True
        assert block["protocol_sha256"] == FROZEN_SHA
        assert block["authorizes_official_generation"] is False


def test_dry_compile_touched_no_sealed_domain_and_no_excluded_identity() -> None:
    dry = load("dry_compile")
    for block in dry["splits"].values():
        assert block["n24_episodes"] == 0
        assert block["study_b_episodes"] == 0
        assert block["final_test_episodes"] == 0
        assert block["duplicate_identities"] == 0
        assert block["design_pilot_or_canary_overlap"] == 0
        assert block["v1_rows_reused"] == 0
        assert 24 not in block["team_sizes"]
        assert block["families"] == ["F%d" % i for i in range(1, 11)]


def test_validation_generation_is_not_permitted_yet() -> None:
    boundary = load("dry_compile")["train_first_authorization_boundary"]
    assert boundary["validation_generation_permitted_now"] is False


# ---------------------------------------------------------------------------
# image qualification is reported honestly
# ---------------------------------------------------------------------------
def test_image_qualification_records_its_failure_without_reusing_an_old_image() -> None:
    image = load("image")
    assert image["status"] == "FAILED_IMAGE_NOT_REBUILDABLE"
    assert image["image_id"] is None and image["image_digest"] is None
    assert image["older_image_reused"] is False
    assert image["failure"]["classification"] == "OPERATIONAL_REPRODUCIBILITY_DEFECT"
    assert image["failure"]["scientific_impact"] == \
        "none: no scientific code or contract is involved"
    assert image["failure"][
        "packages_still_available"]["ca-certificates=20230311+deb12u1~deb11u1"] is False


def test_dockerfile_was_not_modified_to_force_a_build() -> None:
    from rvt_swarm.phase8.common import file_sha256
    image = load("image")
    assert image["dockerfile"]["sha256"] == \
        file_sha256(pathlib.Path("docker/generation/Dockerfile"))
    text = pathlib.Path("docker/generation/Dockerfile").read_text()
    assert "ca-certificates=20230311+deb12u1~deb11u1" in text
    assert "PYTHONPATH=/opt/rvt" in text


# ---------------------------------------------------------------------------
# readiness and closed scopes
# ---------------------------------------------------------------------------
def test_readiness_is_verdict_d_and_authorizes_nothing() -> None:
    readiness = load("readiness")
    assert readiness["verdict"] == "D"
    assert readiness["recommendation"] == "DO_NOT_AUTHORIZE_OFFICIAL_GENERATION"
    assert readiness["official_train_generation_authorized"] is False
    assert readiness["blocking_findings"] == ["V2Q-F1", "V2Q-F2", "V2Q-F3"]
    assert readiness["frozen_protocol_sha256"] == FROZEN_SHA
    assert readiness["protocol_verified_against_artifact"] is True


def test_readiness_separates_what_was_and_was_not_qualified() -> None:
    readiness = load("readiness")
    assert set(readiness["qualified"].values()) == {True}
    not_qualified = readiness["not_qualified"]
    assert not_qualified["executable_v2_binding"] == "ABSENT"
    assert not_qualified["target_host_execution"] == "NOT_RUN_UNREACHABLE"
    assert not_qualified["row_identity_binds_v2_protocol_hash"] is False


def test_every_closed_scope_counter_is_zero() -> None:
    assert set(load("readiness")["closed_scopes"].values()) == {0}


def test_v1_dataset_roots_are_unchanged() -> None:
    train = json.loads((ROOT / "phase9g_a1c_official_train"
                        / "dataset_manifest.json").read_text())
    validation = json.loads((ROOT / "phase9g_a1v_official_validation"
                             / "validation_dataset_manifest.json").read_text())
    assert train["dataset_manifest_sha256"] == \
        "4ac3d2cb65a8b5d656a5d982b344466868f8deaa8cef2b93af7ce824e9387caf"
    assert validation["dataset_manifest_sha256"] == \
        "c991aa3016b38b524a14d9b7037b63d97c2cbbb7d92279fc5a297b9c55d4989e"
