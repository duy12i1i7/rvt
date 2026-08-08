"""Phase 8R -- pre-data residual expert specification completion.

The lattice, bound derivation, pipeline erratum and execution rules are frozen
owner decisions and are pinned here. The four utility normalizers are *not*
specified, and that finding is pinned too: a later phase that supplies one must
do it by freezing a quantity, not by editing a test.
"""

from __future__ import annotations

import ast
import hashlib
import json
import math
import pathlib

import pytest

from rvt_swarm.fd24.configuration import FD24ModelConfig, residual_action_limits
from rvt_swarm.phase8r import (
    CANDIDATE_COUNT,
    CANONICAL_MULTIPLIERS,
    RESIDUAL_EXPERT_V1_ID,
    RESIDUAL_EXPERT_V2_ID,
    canonical_lattice_hash,
    residual_candidate_lattice,
    zero_residual_index,
)
from rvt_swarm.phase8 import targets as phase8_targets
from rvt_swarm.runtime_configuration import RuntimeConfig

ROOT = pathlib.Path("results/rvt_fd24")
AUDIT = json.loads((ROOT / "residual_expert_spec_v2_audit_v1.json").read_text())
ERRATUM = json.loads((ROOT / "residual_action_pipeline_erratum_v1.json").read_text())
BUDGET_V2 = json.loads((ROOT / "proposed_generation_budget_addendum_v2.json").read_text())
BUDGET_V1 = json.loads(
    (ROOT / "datasets" / "generation_budget_v1.json").read_text())

RUNTIME = RuntimeConfig.for_team_size(5)
MODEL = FD24ModelConfig()
LIMITS = residual_action_limits(MODEL, RUNTIME)
LATTICE = residual_candidate_lattice(MODEL, RUNTIME)

LATTICE_MODULE = pathlib.Path("rvt_swarm/phase8r/residual_lattice.py")


# ---------------------------------------------------------------------------
# SPEC-1 -- the candidate lattice
# ---------------------------------------------------------------------------
def test_candidate_set_is_the_nine_point_symmetric_lattice() -> None:
    bx, by = LIMITS
    assert CANDIDATE_COUNT == 9
    assert LATTICE == (
        (-bx, -by), (-bx, 0.0), (-bx, by),
        (0.0, -by), (0.0, 0.0), (0.0, by),
        (bx, -by), (bx, 0.0), (bx, by),
    )
    assert len(set(LATTICE)) == 9


def test_canonical_ordering_is_x_major_then_y_each_ascending() -> None:
    assert CANONICAL_MULTIPLIERS == (
        (-1, -1), (-1, 0), (-1, 1),
        (0, -1), (0, 0), (0, 1),
        (1, -1), (1, 0), (1, 1),
    )
    signs = [(int(math.copysign(1, x)) if x else 0, int(math.copysign(1, y)) if y else 0)
             for x, y in LATTICE]
    assert signs == list(CANONICAL_MULTIPLIERS)
    assert signs == sorted(signs)


def test_zero_residual_occurs_exactly_once() -> None:
    assert zero_residual_index() == 4
    assert LATTICE[4] == (0.0, 0.0)
    assert sum(1 for candidate in LATTICE if candidate == (0.0, 0.0)) == 1


def test_lattice_is_not_conditioned_on_team_size_or_topology() -> None:
    for team_size in (5, 6, 8, 12, 16):
        assert residual_candidate_lattice(
            MODEL, RuntimeConfig.for_team_size(team_size)) == LATTICE
    source = LATTICE_MODULE.read_text()
    for forbidden in ("team_size", "topology", "COMPACT", "LINE", "random", "gauss",
                      "normal(", "resolution"):
        assert forbidden not in source, forbidden


def test_candidate_set_hash_is_stable() -> None:
    assert canonical_lattice_hash(LATTICE) == AUDIT[
        "spec_1_candidate_lattice"]["candidate_set_sha256"]
    assert [list(c) for c in LATTICE] == AUDIT["spec_1_candidate_lattice"]["candidates"]


# ---------------------------------------------------------------------------
# SPEC-2 -- the bound is derived, never written
# ---------------------------------------------------------------------------
def test_lattice_module_contains_no_residual_magnitude_literal() -> None:
    """AST check: no numeric constant in the module is a residual magnitude."""
    tree = ast.parse(LATTICE_MODULE.read_text())
    constants = [node.value for node in ast.walk(tree)
                 if isinstance(node, ast.Constant) and isinstance(node.value, (int, float))
                 and not isinstance(node.value, bool)]
    # only the multiplier table (-1, 0, 1) and the component count 2 may appear
    assert set(constants) <= {-1, 0, 1, 2}, constants
    for value in (0.15, 0.25, 0.6):
        assert str(value) not in LATTICE_MODULE.read_text()


def test_changing_the_authoritative_bound_changes_the_lattice_deterministically() -> None:
    halved = FD24ModelConfig(
        residual_limit_fractions_of_maximum_acceleration=(0.125, 0.125))
    lattice = residual_candidate_lattice(halved, RUNTIME)
    assert lattice != LATTICE
    assert lattice[8] == pytest.approx((LIMITS[0] / 2.0, LIMITS[1] / 2.0))
    assert lattice[4] == (0.0, 0.0)
    assert residual_candidate_lattice(halved, RUNTIME) == lattice     # deterministic

    asymmetric = FD24ModelConfig(
        residual_limit_fractions_of_maximum_acceleration=(0.25, 0.125))
    skewed = residual_candidate_lattice(asymmetric, RUNTIME)
    assert skewed[8] == pytest.approx((LIMITS[0], LIMITS[1] / 2.0))


def test_bound_derivation_matches_the_authoritative_fields() -> None:
    spec = AUDIT["spec_2_residual_bound"]
    assert spec["bx_by"] == list(LIMITS)
    assert spec["fractions"] == list(
        MODEL.residual_limit_fractions_of_maximum_acceleration)
    assert spec["maximum_acceleration_meters_per_second_squared"] == (
        RUNTIME.physical.maximum_acceleration_meters_per_second_squared)
    assert spec["independent_literal_in_lattice_module"] is False


# ---------------------------------------------------------------------------
# SPEC-3/4/5 -- pipeline, intervention, evaluation horizon
# ---------------------------------------------------------------------------
def test_residual_is_inserted_before_the_local_safety_projection() -> None:
    pipeline = ERRATUM["authoritative_pipeline"]
    assert pipeline["insertion_point"] == "BEFORE_LOCAL_SAFETY_PROJECTION"
    assert pipeline["equation"] == (
        "u_safe = local_safety_projection(u_base_pre_safety + delta_u_world)")
    for name in ("u_base_pre_safety", "delta_u_world", "u_candidate_pre_safety",
                 "u_safe_candidate"):
        assert pipeline[name]["units"] == "meters_per_second_squared"
        assert pipeline[name]["frame"] == "world"


def test_historical_action_target_document_is_not_edited() -> None:
    manifest = json.loads((ROOT / "experiment_protocol_manifest.json").read_text())
    entry = manifest["hashed_protocol_documents"]["action_target"]
    digest = hashlib.sha256(pathlib.Path(entry["path"]).read_bytes()).hexdigest()
    assert digest == entry["sha256"]
    assert ERRATUM["supersedes_wording_in"]["document_edited_in_place"] is False
    assert ERRATUM["supersedes_wording_in"]["document_sha256"] == entry["sha256"]


def test_intervention_is_exactly_one_control_interval() -> None:
    intervention = ERRATUM["candidate_intervention"]
    assert intervention["duration_control_intervals"] == 1
    assert intervention["holding_duration_parameter_added"] is False
    assert intervention["reapplied_through_rollout"] is False
    assert ERRATUM["control_period_seconds"] == (
        RUNTIME.physical.control_period_seconds)


def test_evaluation_horizon_is_the_existing_episode_remainder() -> None:
    evaluation = ERRATUM["counterfactual_evaluation"]
    assert evaluation["new_lookahead_horizon"] is False
    assert evaluation["new_discount_factor"] is False
    assert evaluation["new_planning_horizon"] is False
    assert evaluation["distinct_from_intervention_duration"] is True
    assert evaluation["conflict_with_hashed_phase8_semantics"] is False


# ---------------------------------------------------------------------------
# SPEC-6/7/8/9 -- boundaries and field semantics
# ---------------------------------------------------------------------------
def test_action_information_is_local_and_the_label_oracle_is_separate() -> None:
    boundary = AUDIT["spec_6_information_boundary"]
    assert boundary["ACTION_INFORMATION_LOCAL"] is True
    assert boundary["LABEL_ORACLE_CENTRALIZED"] is True
    assert boundary["centralized_oracle_may_never_be_a_runtime_model_input"] is True
    provenance = AUDIT["spec_7_provenance_fields"]
    assert provenance["new_field_required"] == "label_oracle_centralized"
    assert provenance["v1_schema_extended_in_this_phase"] is False
    assert provenance["v1_explicit_contradictory_definition_found"] is False


def test_the_v1_evaluation_schema_was_not_extended() -> None:
    fields = list(phase8_targets.LocalActionEvaluation.__dataclass_fields__)
    assert fields == ["action_world_acceleration", "locally_feasible",
                      "safety_projection_compatible", "robot_local_information_only",
                      "normalized_progress", "normalized_clearance_margin",
                      "normalized_formation_error", "normalized_action_deviation"]
    assert "label_oracle_centralized" not in fields


def test_locally_feasible_is_narrow_and_distinct() -> None:
    spec = AUDIT["spec_8_locally_feasible"]
    assert set(spec["explicitly_excluded"]) == {
        "safety success", "collision-free rollout", "task success",
        "recoverability success"}
    assert spec["duplicates_selector_bound_checks"] is False
    assert set(spec["distinct_from"]) == {"safety_projection_compatible", "task_success"}
    assert len(spec["required_conditions"]) == 5


def test_safety_compatibility_uses_only_the_local_projection() -> None:
    spec = AUDIT["spec_9_safety_compatibility"]
    assert spec["global_safety_oracle"] is False
    assert spec["constraints_altered"] is False
    assert "pre-safety action" in spec["recorded_raw_fields"]
    assert "post-safety action" in spec["recorded_raw_fields"]


# ---------------------------------------------------------------------------
# SPEC-10/11/12 -- the utility audit and the hard stop
# ---------------------------------------------------------------------------
def test_utility_field_inventory_is_exact_and_complete() -> None:
    audited = [field["field"] for field in AUDIT["spec_10_utility_field_audit"]["fields"]]
    declared = [name for name in phase8_targets.LocalActionEvaluation.__dataclass_fields__
                if name.startswith("normalized_")]
    assert audited == declared
    assert len(audited) == 4
    weights = {field["field"]: field["utility_weight"]
               for field in AUDIT["spec_10_utility_field_audit"]["fields"]}
    assert weights == {"normalized_progress": 1.00,
                       "normalized_clearance_margin": 0.50,
                       "normalized_formation_error": -0.25,
                       "normalized_action_deviation": -0.05}


def test_audited_weights_match_the_frozen_utility() -> None:
    """The audit's weight column must be the selector's actual arithmetic."""
    def utility(progress, clearance, formation, deviation):
        return phase8_targets.LocalActionEvaluation(
            (0.0, 0.0), True, True, True, progress, clearance, formation, deviation
        ).utility()
    base = utility(0.0, 0.0, 0.0, 0.0)
    assert utility(1.0, 0.0, 0.0, 0.0) - base == pytest.approx(1.00)
    assert utility(0.0, 1.0, 0.0, 0.0) - base == pytest.approx(0.50)
    assert utility(0.0, 0.0, 1.0, 0.0) - base == pytest.approx(-0.25)
    assert utility(0.0, 0.0, 0.0, 1.0) - base == pytest.approx(-0.05)


def test_every_normalizer_candidate_is_a_frozen_repository_quantity() -> None:
    """SPEC-11: no tuned constant, no data-derived statistic."""
    frozen_values = {
        RUNTIME.formation.nominal_spacing_meters,
        RUNTIME.sensing.obstacle_sensing_range_meters,
        RUNTIME.communication.communication_range_meters,
        RUNTIME.derived.robot_obstacle_required_clearance_meters,
        RUNTIME.derived.robot_robot_required_clearance_meters,
        RUNTIME.derived.formation_tolerance_meters,
    }
    for field in AUDIT["spec_10_utility_field_audit"]["fields"]:
        for candidate in field["frozen_normalizer_candidates"]:
            assert candidate["dimensionless"] is True
            value = candidate["value"]
            if isinstance(value, list):
                assert value == list(LIMITS)
            else:
                assert any(abs(value - frozen) < 1e-12 for frozen in frozen_values), (
                    field["field"], candidate)


def test_no_data_dependent_normalization_was_used() -> None:
    forbidden = ("training-set", "validation statistic", "percentile", "min/max",
                 "per-decision range", "tuned")
    rendered = json.dumps(AUDIT["spec_10_utility_field_audit"]).lower()
    for phrase in forbidden:
        assert phrase.lower() not in rendered.replace("candidate-set min/max", ""), phrase
    assert AUDIT["spec_11_normalizer_owner_rule"]["tuned_constants_introduced"] == 0
    assert AUDIT["spec_11_normalizer_owner_rule"]["forbidden_sources_used"] == []


def test_spec12_hard_stop_fired_and_no_number_was_chosen() -> None:
    stop = AUDIT["spec_12_hard_stop"]
    assert stop["status"] == "TRIGGERED"
    assert stop["number_chosen"] is False
    assert stop["v2_expert_implemented"] is False
    assert [row["field"] for row in stop["unresolved_fields"]] == [
        "normalized_progress", "normalized_clearance_margin",
        "normalized_formation_error", "normalized_action_deviation"]
    assert AUDIT["verdict"] == "A"
    assert AUDIT["v2_specification_frozen"] is False


def test_the_deviation_norm_choice_is_materially_undetermined() -> None:
    """The three citable rules rank the frozen lattice differently."""
    edge, corner = (LIMITS[0], 0.0), (LIMITS[0], LIMITS[1])
    l_inf = lambda d: max(abs(d[0]) / LIMITS[0], abs(d[1]) / LIMITS[1])
    l2_bound = lambda d: math.hypot(*d) / math.hypot(*LIMITS)
    l2_component = lambda d: math.hypot(*d) / LIMITS[0]

    assert l_inf(edge) == l_inf(corner) == 1.0          # ties -> tie-break inert
    assert l2_bound(edge) < l2_bound(corner)            # edges preferred
    assert l2_component(corner) > 1.0                   # leaves the unit range

    norms = AUDIT["spec_10_utility_field_audit"]["fields"][3]["candidate_norms"]
    assert norms["L_inf_over_componentwise_bound"]["separates_edge_from_corner"] is False
    assert norms["L2_over_bound_norm"]["separates_edge_from_corner"] is True
    assert len(norms) == 3


def test_v2_specification_artifact_was_not_written() -> None:
    """SPEC-19 is conditional; the completed artifact must not exist yet."""
    assert not (ROOT / "residual_expert_spec_v2.json").exists()
    assert AUDIT["spec_19_versioned_artifact"]["status"] == "NOT_CREATED"
    assert AUDIT["schema_version"] == "rvt-residual-expert-spec-v2-audit/v1"


def test_spec13_classification_was_not_forced() -> None:
    assert AUDIT["spec_13_utility_oracle_classification"]["status"] == "NOT_REACHED"


# ---------------------------------------------------------------------------
# SPEC-16 -- the V1 selector is untouched
# ---------------------------------------------------------------------------
def test_v1_selector_and_identity_are_preserved() -> None:
    identity = AUDIT["expert_identity"]
    assert identity["v1"] == RESIDUAL_EXPERT_V1_ID == phase8_targets.RESIDUAL_EXPERT_ID
    assert identity["v2_proposed"] == RESIDUAL_EXPERT_V2_ID
    assert RESIDUAL_EXPERT_V2_ID.endswith("_V2") and RESIDUAL_EXPERT_V1_ID.endswith("_V1")
    assert identity["v1_semantics_mutated"] is False
    assert identity["v1_selector_modified"] is False
    assert AUDIT["spec_16_selector"]["selector_modified"] is False


def test_no_module_reimplements_the_frozen_selector() -> None:
    """The lattice enumerates. It must not import, call or shadow the selector.

    Checked on the AST rather than the text, so the module docstring may
    describe what it deliberately does not do.
    """
    tree = ast.parse(LATTICE_MODULE.read_text())
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    attributes = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    defined = {node.name for node in ast.walk(tree)
               if isinstance(node, (ast.FunctionDef, ast.ClassDef))}
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported.update(alias.name for alias in node.names)
            assert "phase8.targets" not in (node.module or ""), node.module
        elif isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
    forbidden = {"utility", "select_counterfactual_local_action",
                 "LocalActionEvaluation", "build_residual_action_target"}
    assert not (names | attributes | defined | imported) & forbidden


# ---------------------------------------------------------------------------
# SPEC-17 -- generation budget impact
# ---------------------------------------------------------------------------
def test_dense_record_caps_are_not_multiplied_by_the_candidate_count() -> None:
    impact = AUDIT["spec_17_generation_budget_impact"]
    assert impact["stored_record_caps_remain_valid_upper_bounds"] is True
    assert impact["old_formula"]["totals"]["total"] == 536000
    assert impact["old_formula"]["implicit_residual_candidate_count_assumption"] is None
    stored = BUDGET_V1["exact_total_budget"]["dense_residual_action_records"]
    assert stored == 536000
    assert impact["new_formula_with_nine_candidates"]["dense_rows_unchanged"] == stored


def test_candidate_evaluation_count_is_nine_times_the_dense_rows() -> None:
    new = AUDIT["spec_17_generation_budget_impact"]["new_formula_with_nine_candidates"]
    assert new["residual_candidate_evaluations"] == 536000 * CANDIDATE_COUNT == 4824000
    assert new["per_cell_train"]["candidate_evaluations_per_cell"] == 2000 * 9 == 18000


def test_the_two_invalidated_frozen_fields_are_named_and_unmodified() -> None:
    invalidated = AUDIT["spec_17_generation_budget_impact"]["invalidated_frozen_fields"]
    assert len(invalidated) == 2
    assert BUDGET_V1["timeout_contract"]["wall_clock_seconds"][
        "residual_action_cell_generation_job"] == 1800
    assert BUDGET_V1["job_identity_contract"]["residual_cell"] == [
        "study", "split", "family", "layout_sha256", "team_size"]
    assert "candidate" not in BUDGET_V1["job_identity_contract"]["residual_cell"]
    assert AUDIT["spec_17_generation_budget_impact"]["existing_budget_modified"] is False
    assert AUDIT["spec_17_generation_budget_impact"][
        "existing_job_manifest_modified"] is False


def test_additive_budget_proposal_exists_and_proposes_no_numbers() -> None:
    assert BUDGET_V2["status"] == "PROPOSED_NOT_AUTHORITATIVE"
    assert BUDGET_V2["extends"]["modified"] is False
    assert BUDGET_V2["authorization"]["generation_authorized"] is False
    assert BUDGET_V2["authorization"]["budget_v1_superseded"] is False
    assert BUDGET_V2["new_budget_dimension_required"]["total"] == 4824000
    timeout_proposal = BUDGET_V2["proposed_changes"][0]
    assert "owner must choose" in timeout_proposal["proposal"]
    assert "proposed_seconds" not in timeout_proposal


def test_generation_budget_hash_is_unchanged() -> None:
    protocol = json.loads((ROOT / "executable_scientific_protocol_v1.json").read_text())
    assert protocol["generation_budget_hash"] == (
        "3853b8ad4484d733de9be7d0e27bf273f33e14054f3089f6b5454cc17815846e")
    assert BUDGET_V1["generation_budget_sha256"] == protocol["generation_budget_hash"]


# ---------------------------------------------------------------------------
# SPEC-18/20 and isolation
# ---------------------------------------------------------------------------
def test_rb16_synthetic_rotation_augmentation_is_disabled() -> None:
    rb16 = AUDIT["spec_18_rb16"]
    assert rb16["synthetic_residual_rotation_augmentation"] == "DISABLED"
    assert rb16["predeclared_non_identity_transform_set_exists"] is False
    assert rb16["rb16_started"] is False
    loss_contract = pathlib.Path("docs/RVT_FD24_LOSS_CONTRACT.md").read_text()
    assert "predeclared local equivariant transforms" in loss_contract
    assert "disabled initially" in loss_contract


def test_protocol_versioning_is_additive_only() -> None:
    versioning = AUDIT["spec_20_protocol_versioning"]
    assert versioning["historical_hashes_rewritten"] is False
    assert versioning["job_manifest_mutated"] is False
    assert versioning["old_composite_is_not_the_complete_residual_label_contract"] is True
    referenced = {row["artifact"] for row
                  in versioning["artifacts_a_future_residual_provenance_record_must_reference"]}
    assert "docs/RVT_RESIDUAL_ACTION_TARGET_V1.md" in referenced


def test_no_scientific_data_was_generated() -> None:
    isolation = AUDIT["isolation"]
    assert isolation["recoverability_rows"] == 0
    assert isolation["residual_supervision_rows"] == 0
    assert isolation["scientific_shards"] == 0
    assert isolation["new_checkpoints"] == 0
    assert isolation["optimizer_states"] == 0
    assert isolation["canary_requiring_v2_labels"] is False
    assert isolation["rb15_retried"] is False
    assert isolation["final_test_access_count"] == 0
    assert isolation["study_a_n24_access_count"] == 0
    assert BUDGET_V1["scientific_dataset_records_generated"] == 0
    assert BUDGET_V1["training_operations"] == 0


def test_authoritative_headroom_artifacts_are_unchanged() -> None:
    v6 = json.loads((ROOT / "headroom_requalification_v6.json").read_text())
    reproduction = json.loads(
        (ROOT / "headroom_v6_detached_reproduction_v1.json").read_text())
    authority = json.loads((ROOT / "headroom_authority_record_v1.json").read_text())
    assert v6["headroom_requalification_v6_sha256"] == (
        "d044d6b99d7a2bbb83565b121d188a35e335bfd856e3eb0e885823ca1a6742ef")
    assert reproduction["headroom_v6_detached_reproduction_sha256"] == (
        "1f08ba77315e6fdbabfeac8f9350e6f5cd64468c431ecc9fba19747fcd26af32")
    assert authority["headroom_authority_record_sha256"] == (
        "fafe1460c69ef37ca9134c2fc17721adddda92607e3e4e3c084d6a29d9dab509")
