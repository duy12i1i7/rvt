"""RB-16 -- native action-frame binding and identity-transform verification.

The world segment of the residual path is verified exactly. The model-output
frame is *not* verified as world: RB-16 found it declared as the mission frame,
and that conflict is pinned here so it cannot be silently closed by editing a
name or inserting a conversion.
"""

from __future__ import annotations

import ast
import hashlib
import json
import math
import pathlib

import pytest
import torch

from rvt_swarm.decentralized.ego_graph_v2 import EGO_GRAPH_SCHEMA_VERSION
from rvt_swarm.fd24.configuration import (
    ROBOT_LOCAL_ACTION_COMPONENTS, FD24ModelConfig, residual_action_limits,
)
from rvt_swarm.fd24.model import bounded_residual_action
from rvt_swarm.phase8 import targets as phase8_targets
from rvt_swarm.phase8.common import canonical_json_bytes
from rvt_swarm.phase8.targets import (
    DENSE_ACTION_SAMPLE_SCHEMA_VERSION, DenseActionSample, LocalActionEvaluation,
    build_residual_action_target,
)
from rvt_swarm.phase8r import CANDIDATE_COUNT, residual_candidate_lattice
from rvt_swarm.runtime_configuration import RuntimeConfig

ROOT = pathlib.Path("results/rvt_fd24")
RB16 = json.loads((ROOT / "rb16_native_action_frame_v1.json").read_text())
SPEC = json.loads((ROOT / "residual_expert_spec_v2.json").read_text())
BINDING_V2 = json.loads((ROOT / "rb15_residual_expert_binding_v2.json").read_text())
CANARY = json.loads((ROOT / "rb15_v2_canary_v1.json").read_text())
BUDGET = json.loads((ROOT / "datasets" / "generation_budget_v1.json").read_text())
S3Z = json.loads((ROOT / "phase9_s3_centerline_execution_contract_v1.json").read_text())

MODEL = FD24ModelConfig()
RUNTIME = RuntimeConfig.for_team_size(6)
LIMITS = residual_action_limits(MODEL, RUNTIME)


def _case(name):
    return next(row for row in RB16["identity_transform"]["cases"] if row["case"] == name)


# ---------------------------------------------------------------------------
# RB16-0/5/8 -- the world side of the path
# ---------------------------------------------------------------------------
def test_artifact_is_self_consistent() -> None:
    body = {k: v for k, v in RB16.items() if k != "rb16_native_action_frame_sha256"}
    assert hashlib.sha256(canonical_json_bytes(body)).hexdigest() == RB16[
        "rb16_native_action_frame_sha256"]
    assert RB16["schema_version"] == "rvt-rb16-native-action-frame/v1"
    assert RB16["provenance_class"] == "RUNTIME_CONFORMANCE_ONLY"


def test_target_builder_emits_native_world_acceleration() -> None:
    base = (0.10, -0.02)
    expert = LocalActionEvaluation((base[0] + 0.05, base[1] - 0.03), True, True, True,
                                   0.5, 0.4, 0.2, 0.3)
    target = build_residual_action_target(base, expert, RUNTIME, MODEL)
    assert target.residual_target_world_acceleration == pytest.approx((0.05, -0.03))
    assert len(target.residual_target_world_acceleration) == 2
    assert target.residual_bounds_world_acceleration == pytest.approx(LIMITS)
    fields = list(phase8_targets.ResidualActionTarget.__dataclass_fields__)
    assert "residual_target_world_acceleration" in fields
    assert RB16["expert_target_frame"] == "WORLD"
    assert RB16["target_shape"] == [2]
    assert RB16["target_units"] == "meters_per_second_squared"


def test_no_rotation_occurs_between_the_selected_candidate_and_the_target() -> None:
    base = (0.10, -0.02)
    for delta in residual_candidate_lattice(MODEL, RUNTIME):
        expert = LocalActionEvaluation((base[0] + delta[0], base[1] + delta[1]),
                                       True, True, True, 0.5, 0.4, 0.2, 0.3)
        target = build_residual_action_target(base, expert, RUNTIME, MODEL)
        assert target.residual_target_world_acceleration == pytest.approx(delta)


def test_training_row_field_is_world_named_and_two_components() -> None:
    fields = phase8_targets.DenseActionSample.__dataclass_fields__
    assert "residual_target_world_acceleration" in fields
    assert "base_action_world_acceleration" in fields
    assert "projected_base_action_world_acceleration" in fields
    contract = pathlib.Path("docs/RVT_DENSE_ACTION_DATA_CONTRACT.md").read_text()
    assert "World-frame" in contract and "dt=0.15 s" in contract
    assert RB16["training_target_frame"] == "WORLD"


def test_axis_convention_is_recorded_on_both_sides() -> None:
    convention = RB16["axis_convention"]
    assert convention["world_side"]["component_0"] == "world X acceleration"
    assert convention["world_side"]["component_1"] == "world Y acceleration"
    assert convention["model_side"]["component_0"] == "mission longitudinal acceleration"
    assert convention["model_side"]["component_1"] == "mission lateral acceleration"
    assert convention["agree"] is False
    # RB16 recorded the historical declaration; RB16R replaced it with WORLD.
    assert tuple(RB16["robot_local_action_components"]) != ROBOT_LOCAL_ACTION_COMPONENTS
    erratum = json.loads((ROOT / "model_residual_output_frame_v2.json").read_text())
    assert tuple(RB16["robot_local_action_components"]) == tuple(
        erratum["historical_declaration"]["robot_local_action_components"])


# ---------------------------------------------------------------------------
# RB16-1/6 -- the frame conflict itself
# ---------------------------------------------------------------------------
def test_the_model_output_frame_conflict_is_recorded_and_repaired() -> None:
    """RB16 found MISSION; RB16R repaired it to WORLD by owner decision.

    The failed audit is preserved verbatim -- it still records MISSION -- and the
    live declaration is now WORLD. The two are reconciled only by the erratum.
    """
    erratum = json.loads(
        (ROOT / "model_residual_output_frame_v2.json").read_text())
    assert RB16["model_output_frame"] == "MISSION"          # preserved evidence
    assert tuple(erratum["historical_declaration"][
        "robot_local_action_components"]) == ("mission_longitudinal_acceleration",
                                              "mission_lateral_acceleration")
    assert ROBOT_LOCAL_ACTION_COMPONENTS == ("world_x_acceleration",
                                             "world_y_acceleration")
    assert erratum["current_declaration"]["declared_output_frame"] == "WORLD"
    assert erratum["historical_declaration"]["rewritten"] is False
    assert RB16["expert_target_frame"] == "WORLD"
    assert RB16["frame_conflict"]["conflict"] is True
    assert RB16["verdict"] == "B"
    assert RB16["status"] == "BLOCKED_FRAME_CONFLICT"
    assert RB16["required_owner_decision"]["rb16_must_not_choose"] is True


def test_the_mission_frame_is_never_the_world_frame_in_any_layout() -> None:
    angles = []
    for split in ("train", "validation"):
        for path in sorted(
                (ROOT / "layout_execution_specifications" / split).glob("*.json")):
            axis = json.loads(path.read_text())["mission_frame"]["longitudinal_axis"]
            angles.append(math.degrees(math.atan2(float(axis[1]), float(axis[0]))))
    assert len(angles) == RB16["frame_conflict"]["layouts_examined"] == 30
    assert not any(abs(angle) < 1e-12 for angle in angles)
    assert RB16["frame_conflict"]["layouts_world_aligned"] == 0
    assert min(angles) == pytest.approx(
        RB16["frame_conflict"]["mission_vs_world_angle_degrees"]["minimum"], abs=1e-6)
    assert max(angles) == pytest.approx(
        RB16["frame_conflict"]["mission_vs_world_angle_degrees"]["maximum"], abs=1e-6)


def test_reading_a_bounded_residual_in_the_other_frame_leaves_the_bound() -> None:
    """Why the conflict is material rather than cosmetic."""
    theta = math.radians(
        RB16["frame_conflict"]["mission_vs_world_angle_degrees"]["mean"])
    corner = (LIMITS[0], LIMITS[1])
    rotated = (corner[0] * math.cos(theta) - corner[1] * math.sin(theta),
               corner[0] * math.sin(theta) + corner[1] * math.cos(theta))
    assert any(abs(value) > LIMITS[0] + 1e-12 for value in rotated)
    recorded = next(row for row in RB16["frame_conflict"]["material_consequences"]
                    if "corner" in row["case"])
    assert recorded["leaves_componentwise_bound"] is True


def test_no_conversion_was_inserted_to_make_the_audit_pass() -> None:
    assert RB16["frame_conflict"]["conversion_inserted"] is False
    assert RB16["frame_conflict"][
        "authoritative_action_frame_conversion_exists"] is False
    for module in ("rvt_swarm/phase9c_rb/residual_expert_v2.py",
                   "rvt_swarm/phase8r/utility_v2.py",
                   "rvt_swarm/phase8r/residual_lattice.py"):
        source = pathlib.Path(module).read_text()
        for token in ("world_to_mission", "mission_to_world", "_to_mission",
                      "rotate", "rotation"):
            assert token not in source, (module, token)


# ---------------------------------------------------------------------------
# RB16-7 -- bound equality
# ---------------------------------------------------------------------------
def test_the_residual_bound_is_one_authoritative_quantity_everywhere() -> None:
    expert_bound = residual_action_limits(MODEL, RUNTIME)
    base = (0.0, 0.0)
    expert = LocalActionEvaluation((LIMITS[0], 0.0), True, True, True, 1.0, 0.0, 0.0, 0.0)
    target_bound = build_residual_action_target(
        base, expert, RUNTIME, MODEL).residual_bounds_world_acceleration
    model_bound = tuple(float(v) for v in residual_action_limits(MODEL, RUNTIME))
    assert tuple(expert_bound) == tuple(target_bound) == model_bound
    assert RB16["residual_bound"]["all_equal"] is True
    assert RB16["residual_bound"]["independent_literal"] is False
    assert RB16["residual_bound"]["values"] == list(LIMITS)
    # the bound is a box, so a frame change alters admissibility
    assert RB16["residual_bound"]["frame_conversion_would_alter_admissibility"] is True


def test_the_model_head_clamps_with_the_same_limits() -> None:
    raw = torch.tensor([[10.0, -10.0]], dtype=torch.float32)
    bounded = bounded_residual_action(
        raw, torch.tensor(list(LIMITS), dtype=torch.float32))
    assert float(bounded[0][0]) == pytest.approx(LIMITS[0], abs=1e-6)
    assert float(bounded[0][1]) == pytest.approx(-LIMITS[1], abs=1e-6)
    assert all(abs(float(v)) <= limit + 1e-6 for v, limit in zip(bounded[0], LIMITS))


# ---------------------------------------------------------------------------
# RB16-3/12/13/14 -- identity, non-symmetric, sign and axis
# ---------------------------------------------------------------------------
def test_identity_transform_is_exact_on_every_case() -> None:
    assert RB16["identity_transform"]["definition"] == (
        "T_identity(delta_u_world) = delta_u_world")
    assert RB16["identity_transform"]["general_rotation_api_created"] is False
    assert RB16["identity_transform"]["all_exact"] is True
    assert RB16["identity_transform"]["model_trained"] is False
    for case in RB16["identity_transform"]["cases"]:
        assert case["exact_equality_through_identity_path"] is True
        assert case["component_0_preserved"] is True
        assert case["component_1_preserved"] is True
        assert case["input"] == case["runtime_residual_input"]


def test_the_non_symmetric_vector_would_expose_an_axis_swap() -> None:
    case = _case("test_only_non_symmetric")
    dx, dy = case["input"]
    assert dx != dy and abs(dx) != abs(dy) and dy < 0.0 < dx
    assert RB16["test_only_vector"]["inside_authoritative_bound"] is True
    assert RB16["test_only_vector"]["added_to_candidate_set"] is False
    assert tuple(RB16["test_only_vector"]["value"]) not in set(
        residual_candidate_lattice(MODEL, RUNTIME))


def test_signs_and_axis_order_survive_the_identity_path() -> None:
    for name in ("test_only_non_symmetric", "lattice_mixed_sign", "lattice_corner"):
        case = _case(name)
        dx, dy = case["input"]
        rx, ry = case["runtime_residual_input"]
        assert (rx, ry) == (dx, dy)
        assert case["axis_swapped"] is False
        assert case["sign_inverted"] is False
        if dx != dy:
            assert (rx, ry) != (dy, dx)                 # not transposed
            assert (rx, ry) != (-dx, -dy)               # not negated
            assert (rx, ry) != (-dy, dx) and (rx, ry) != (dy, -dx)   # not quarter-turned
    assert RB16["identity_transform"]["no_axis_swap"] is True
    assert RB16["identity_transform"]["no_sign_inversion"] is True


def test_a_row_round_trip_preserves_the_two_components() -> None:
    delta = (LIMITS[0] * 0.5, -LIMITS[1] * 0.25)
    row = DenseActionSample(
        DENSE_ACTION_SAMPLE_SCHEMA_VERSION, EGO_GRAPH_SCHEMA_VERSION, "f" * 64, 5,
        (0.1, 0.0), (0.1 + delta[0], 0.0 + delta[1]), delta, (0.1, 0.0),
        (("intervened", "false"),), "role_0", 6, "F1", "g" * 64, "train",
        "rb16-row", 20, "0" * 40, (("runtime", "r" * 64),))
    assert tuple(row.residual_target_world_acceleration) == delta
    assert row.residual_target_world_acceleration[0] != (
        row.residual_target_world_acceleration[1])


def test_the_head_saturation_property_is_recorded() -> None:
    """tanh cannot emit exactly +/- the bound. Recorded, not corrected."""
    note = RB16["identity_transform"]["head_saturation_note"]
    assert "limit point" in note and "never emits" in note
    interior = _case("test_only_non_symmetric")
    assert interior["strictly_inside_bound"] is True
    assert interior["head_representable"] is True
    assert interior["head_float32_round_trip_error"] < 1e-6
    corner = _case("lattice_corner")
    assert corner["strictly_inside_bound"] is False
    assert corner["head_representable"] is None


# ---------------------------------------------------------------------------
# RB16-2/4/15/16 -- no transforms, no multiplication
# ---------------------------------------------------------------------------
def test_no_non_identity_transform_is_active_in_the_primary_path() -> None:
    for row in RB16["transform_occurrences"]:
        assert row["in_primary_residual_path"] is False, row["symbol"]
        assert row["classification"] in (
            "ROLE_GEOMETRY_NOT_ACTION", "OBSERVATION_FRAME_NOT_ACTION",
            "QUALIFICATION_FIXTURE_OUTSIDE_PRIMARY_PATH",
            "OBSTACLE_GEOMETRY_FLAG_OUTSIDE_PRIMARY_PATH")


def test_synthetic_rotation_augmentation_stays_disabled() -> None:
    augmentation = RB16["augmentation"]
    assert augmentation["PRIMARY_SYNTHETIC_ROTATION_AUGMENTATION"] == "DISABLED"
    for flag in ("random_angle_sampling", "fixed_quarter_turn_transforms",
                 "reflected_actions", "residual_label_duplication_through_transforms",
                 "equivariance_consistency_loss"):
        assert augmentation[flag] is False, flag
    assert augmentation["synthetic_transformed_supervision_rows"] == 0
    assert augmentation["historical_code_deleted"] is False
    assert augmentation["consistency_loss_implementation_exists"] is False


def test_no_consistency_loss_is_implemented() -> None:
    from rvt_swarm.phase8 import contracts
    source = pathlib.Path(contracts.__file__).read_text()
    assert "disabled_initially" in source
    for module in ("rvt_swarm/fd24", "rvt_swarm/phase8r", "rvt_swarm/phase9c_rb"):
        for path in sorted(pathlib.Path(module).rglob("*.py")):
            text = path.read_text().lower()
            assert "equivarian" not in text, path
            assert "consistency_loss" not in text, path


def test_transform_multiplier_is_one_and_no_count_moved() -> None:
    counts = RB16["counts_unchanged"]
    assert counts["PRIMARY_TRANSFORM_MULTIPLIER"] == 1
    assert counts["candidate_count"] == CANDIDATE_COUNT == 9
    assert counts["candidate_evaluation_upper_bound"] == 536000 * 9 == 4824000
    assert counts["stored_dense_residual_row_cap"] == 536000
    assert counts["rb16_added_candidate_evaluations"] == 0
    assert counts["rb16_added_rows"] == 0
    assert BUDGET["exact_total_budget"]["dense_residual_action_records"] == 536000
    assert SPEC["candidate_lattice"]["count"] == 9


# ---------------------------------------------------------------------------
# RB16-17/18 -- no-eligible semantics and session provenance
# ---------------------------------------------------------------------------
def test_no_eligible_semantics_are_preserved_without_a_fallback() -> None:
    semantics = RB16["no_eligible_semantics"]
    assert semantics["preserved"] is True
    assert semantics["fallback_added"] is False
    assert semantics["zero_fallback"] is False
    assert semantics["rotated_fallback"] is False
    assert semantics["clipped_fallback"] is False
    assert semantics["observed_in_rb15_canary"] == CANARY["selector_failures"] >= 1
    producer = pathlib.Path("rvt_swarm/phase9c_rb/residual_expert_v2.py").read_text()
    assert "selector_error" in producer
    tree = ast.parse(producer)
    handlers = [node for node in ast.walk(tree) if isinstance(node, ast.ExceptHandler)]
    assert len(handlers) == 1                      # only the frozen no-eligible path
    body = ast.dump(handlers[0])
    assert "selector_error" in body
    assert "fallback" not in body.lower()


def test_session_refactor_provenance_is_accurate() -> None:
    provenance = RB16["session_refactor_provenance"]
    current = hashlib.sha256(
        pathlib.Path(provenance["file"]).read_bytes()).hexdigest()
    if provenance["post_refactor_sha256"] != current:
        additive = S3Z["runtime_files"][provenance["file"]]
        assert additive["before_sha256"] == provenance["post_refactor_sha256"]
        assert additive["after_sha256"] == current
        assert S3Z["unchanged_components"]["controller"] is True
    else:
        assert provenance["post_refactor_sha256"] == current
    assert provenance["pre_refactor_sha256"] != current
    cited = next(row for row in SPEC["clearance_sources"]
                 if row["constraint_type"] == "ROBOT_ROBOT")
    assert cited["source_file_sha256"] == provenance["pre_refactor_sha256"]
    assert provenance["v2_spec_rewritten"] is False
    assert provenance["claims_historical_hash_matches_current_file"] is False
    assert provenance["semantic_quantity_changed"] is False
    assert provenance["rb15_binding_sha256"] == BINDING_V2[
        "rb15_residual_expert_binding_v2_sha256"]
    # the cited quantity really is unchanged
    assert RUNTIME.derived.robot_robot_required_clearance_meters == pytest.approx(
        2.0 * RUNTIME.physical.robot_radius_meters
        + RUNTIME.safety.inter_robot_safety_margin_meters)


# ---------------------------------------------------------------------------
# isolation
# ---------------------------------------------------------------------------
def test_rb16_generated_no_scientific_data() -> None:
    isolation = RB16["isolation"]
    for key in ("recoverability_rows", "residual_rows", "scientific_shards",
                "new_fd24_checkpoints", "optimizer_states", "training_operations",
                "final_test_access_count", "study_a_n24_access_count"):
        assert isolation[key] == 0, key
    assert isolation["scientific_supervision_generated"] is False
    residual_audit = json.loads(
        (ROOT / "datasets" / "phase9_residual_audit.json").read_text())
    assert residual_audit["emitted_rows"] == 0
    assert BUDGET["scientific_dataset_records_generated"] == 0


def test_upstream_authority_is_unchanged() -> None:
    upstream = RB16["upstream"]
    assert upstream["modified"] is False
    assert upstream["residual_expert_spec_v2_sha256"] == SPEC[
        "residual_expert_spec_v2_sha256"] == (
        "e3a3093038b31f7f8c11d56be224929c9eccc27e6bde2fa47c5c6c644b7f3fbf")
    assert upstream["rb15_residual_expert_binding_v2_sha256"] == BINDING_V2[
        "rb15_residual_expert_binding_v2_sha256"]
    # The three model-side files were changed by the owner-authorized RB16R
    # repair. RB16 pinned their pre-repair digests; the erratum records the
    # post-repair ones. Everything else RB16 pinned must still match exactly.
    erratum = json.loads((ROOT / "model_residual_output_frame_v2.json").read_text())
    authorized = {row["file"]: row["sha256"]
                  for row in erratum["authorized_frozen_file_changes"]}
    for name, digest in (("rvt_swarm/fd24/model.py", upstream["model_module_sha256"]),
                         ("rvt_swarm/fd24/configuration.py",
                          upstream["model_configuration_sha256"]),
                         ("rvt_swarm/decentralized/ego_graph_v2.py",
                          upstream["ego_graph_v2_sha256"])):
        current = hashlib.sha256(pathlib.Path(name).read_bytes()).hexdigest()
        if current != digest:
            assert name in authorized, name
            assert authorized[name] == current, name


def test_final_test_and_n24_remain_sealed() -> None:
    protocol = json.loads((ROOT / "executable_scientific_protocol_v1.json").read_text())
    assert protocol["final_test_access_policy"]["runtime_access_count"] == 0
    assert not (ROOT / "layout_execution_specifications" / "final_test").exists()
    assert 24 not in CANARY["team_sizes_covered"]


def test_headroom_authority_chain_is_untouched() -> None:
    v6 = json.loads((ROOT / "headroom_requalification_v6.json").read_text())
    assert v6["headroom_requalification_v6_sha256"] == (
        "d044d6b99d7a2bbb83565b121d188a35e335bfd856e3eb0e885823ca1a6742ef")
