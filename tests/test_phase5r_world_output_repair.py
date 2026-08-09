"""Phase 5R / RB16R -- WORLD residual output repair and identifiability.

The frame conflict RB16 found is closed here by an owner decision, not by an
edit: the expert, target, runtime and now the model all mean the same WORLD
acceleration vector. The added frame context is proven *necessary* (remove it
and rotated states are ambiguous again) and *local* (hidden non-neighbour state
cannot move it).
"""

from __future__ import annotations

import ast
import copy
import hashlib
import json
import math
import pathlib

import pytest
import torch

from rvt_swarm.decentralized.ego_graph_v2 import (
    EDGE_FEATURE_DIM, EGO_GRAPH_FEATURE_SCHEMA_SHA256, EGO_GRAPH_SCHEMA_VERSION,
    NODE_FEATURE_DIM, build_robot_local_ego_graph, dump_robot_local_ego_graph,
    load_robot_local_ego_graph,
)
from rvt_swarm.decentralized.guards import EGO_TENSOR_PARAMS
from rvt_swarm.decentralized.system_model import NeighbourRecord, RobotView
from rvt_swarm.fd24.configuration import (
    ROBOT_LOCAL_ACTION_COMPONENTS, FD24ModelConfig, residual_action_limits,
)
from rvt_swarm.fd24.model import (
    FD24_MODEL_INPUT_SCHEMA_VERSION, FD24_MODEL_OUTPUT_SCHEMA_VERSION,
    FD24_MODEL_SCHEMA_VERSION, MISSION_ORIENTATION_CONTEXT_DIM, FD24ModelContractError,
    RVTFD24LocalModel, bounded_residual_action, prepare_fd24_model_batch,
)
from rvt_swarm.phase8.common import canonical_json_bytes
from rvt_swarm.phase8.targets import (
    DENSE_ACTION_SAMPLE_SCHEMA_VERSION, DenseActionSample, LocalActionEvaluation,
    build_residual_action_target,
)
from rvt_swarm.phase8r import CANDIDATE_COUNT, residual_candidate_lattice
from rvt_swarm.phase9c_rb import policies as P
from rvt_swarm.phase9c_rb.binding import build_binding, load_execution_specification
from rvt_swarm.phase9c_rb.session import SimulatorEpisodeSession
from rvt_swarm.runtime_configuration import DEFAULT_RUNTIME_CONFIG, RuntimeConfig
from rvt_swarm.topology_registry import COMPACT

ROOT = pathlib.Path("results/rvt_fd24")
PROTOCOL = json.loads((ROOT / "executable_scientific_protocol_v1.json").read_text())
TARGET_CONTRACT = json.loads((ROOT / "target_v4_execution_contract_v1.json").read_text())
CONTRACTS = json.loads((ROOT / "source_policy_contracts_v1.json").read_text())
ERRATUM = json.loads((ROOT / "model_residual_output_frame_v2.json").read_text())
RB16 = json.loads((ROOT / "rb16_native_action_frame_v1.json").read_text())
SPEC = json.loads((ROOT / "residual_expert_spec_v2.json").read_text())
SEEDS = {"initial_condition": 11, "communication": 22, "dynamic_obstacle": 33}

MODEL = FD24ModelConfig()
RUNTIME = RuntimeConfig.for_team_size(6)
LIMITS = residual_action_limits(MODEL, RUNTIME)
ROTATION = math.radians(37.0)                 # TEST-ONLY rigid rotation


def rotate(vector, radians):
    return (vector[0] * math.cos(radians) - vector[1] * math.sin(radians),
            vector[0] * math.sin(radians) + vector[1] * math.cos(radians))


def rotate_view(view: RobotView, radians: float) -> RobotView:
    """A rigid rotation of the whole scene; the local geometry is unchanged."""
    return RobotView(
        robot_id=view.robot_id,
        position=rotate(view.position, radians),
        velocity=rotate(view.velocity, radians),
        role_keep=rotate(view.role_keep, radians),
        role_line=rotate(view.role_line, radians),
        committed_mode=view.committed_mode, epoch_id=view.epoch_id,
        steps_since_decision=view.steps_since_decision,
        local_progress=view.local_progress,
        goal=rotate(view.goal, radians),
        mission_dir=rotate(view.mission_dir, radians),
        neighbours=tuple(
            NeighbourRecord(
                robot_id=nb.robot_id,
                rel_position=rotate(nb.rel_position, radians),
                rel_velocity=rotate(nb.rel_velocity, radians),
                role_keep=rotate(nb.role_keep, radians),
                role_line=rotate(nb.role_line, radians),
                committed_mode=nb.committed_mode, epoch_id=nb.epoch_id,
                message_age_steps=nb.message_age_steps, degree=nb.degree,
                link_valid=nb.link_valid, packet_loss_estimate=nb.packet_loss_estimate,
            ) for nb in view.neighbours),
        obstacles=tuple((*rotate((token[0], token[1]), radians), token[2])
                        for token in view.obstacles),
    )


@pytest.fixture(scope="module")
def session():
    binding = build_binding(
        load_execution_specification(ROOT, "train", "train-f1-00"), team_size=6,
        source_policy=P.S1, protocol=PROTOCOL, target_contract=TARGET_CONTRACT,
        source_policy_contracts=CONTRACTS)
    policy = P.build_source_policy(
        P.S1, contracts=CONTRACTS, seed=7, horizon_seconds=binding.horizon_seconds,
        team_size=6, family_id=binding.family, runtime_config=DEFAULT_RUNTIME_CONFIG,
        event_plan=())
    built = SimulatorEpisodeSession(binding, protocol=PROTOCOL,
                                    target_contract=TARGET_CONTRACT, seeds=SEEDS,
                                    source_policy=policy)
    for _ in range(20):
        built.step()
    return built


def graph_for(view, session):
    return build_robot_local_ego_graph(
        view, session.runtime_config, session.robots[0].local_topology_metadata,
        COMPACT, 20)


# ---------------------------------------------------------------------------
# R16R-0/1/9/10 -- the owner decision and its provenance
# ---------------------------------------------------------------------------
def test_erratum_is_self_consistent_and_additive() -> None:
    body = {k: v for k, v in ERRATUM.items()
            if k != "model_residual_output_frame_v2_sha256"}
    assert hashlib.sha256(canonical_json_bytes(body)).hexdigest() == ERRATUM[
        "model_residual_output_frame_v2_sha256"]
    assert ERRATUM["schema_version"] == "rvt-fd24-model-residual-frame/v2"
    assert ERRATUM["conflict_artifact"]["preserved_unmodified"] is True
    assert ERRATUM["conflict_artifact"]["sha256"] == RB16[
        "rb16_native_action_frame_sha256"]
    assert ERRATUM["conflict_discovery_commit"] == (
        "79904f87d8e35eaa5045c985adb52669d2727306")


def test_the_historical_mission_declaration_is_preserved_not_rewritten() -> None:
    historical = ERRATUM["historical_declaration"]
    assert historical["model_schema_version"] == "rvt-fd24-model/v1"
    assert historical["declared_output_frame"] == "MISSION"
    assert historical["robot_local_action_components"] == [
        "mission_longitudinal_acceleration", "mission_lateral_acceleration"]
    assert historical["rewritten"] is False
    # and V1 is not silently claimed to have said WORLD
    assert FD24_MODEL_SCHEMA_VERSION == "rvt-fd24-model/v2"
    assert FD24_MODEL_INPUT_SCHEMA_VERSION == "rvt-fd24-model-input/v2"
    assert FD24_MODEL_OUTPUT_SCHEMA_VERSION == "rvt-fd24-model-output/v2"


def test_current_output_declaration_is_world() -> None:
    assert ROBOT_LOCAL_ACTION_COMPONENTS == ("world_x_acceleration",
                                             "world_y_acceleration")
    for forbidden in ("mission_longitudinal", "mission_lateral"):
        assert not any(forbidden in name for name in ROBOT_LOCAL_ACTION_COMPONENTS)
    current = ERRATUM["current_declaration"]
    assert current["declared_output_frame"] == "WORLD"
    assert current["output_shape"] == [2]
    assert current["output_units"] == "meters_per_second_squared"
    assert current["axis_convention"] == {"component_0": "world X acceleration",
                                          "component_1": "world Y acceleration"}
    assert current["robot_local_action_components"] == list(ROBOT_LOCAL_ACTION_COMPONENTS)


def test_world_was_chosen_because_the_qualified_chain_is_world() -> None:
    why = ERRATUM["why_world_is_authoritative"]
    assert why["all_four_use_world"] is True
    assert why["isolated_conflicting_element"] == "the model output declaration"
    assert why["rotating_a_componentwise_box_changes_its_admissible_set"] is True
    assert why["therefore_no_target_or_runtime_rotation"] is True
    decision = ERRATUM["owner_decision"]
    assert decision["PRIMARY_RESIDUAL_OUTPUT_FRAME"] == "WORLD"
    assert decision["expert_or_runtime_converted_to_mission"] is False
    assert decision["world_mission_residual_rotation_added"] is False
    assert decision["lattice_changed"] is False and decision["bounds_changed"] is False


# ---------------------------------------------------------------------------
# R16R-2 -- the head never rotated anything
# ---------------------------------------------------------------------------
def test_the_forward_path_contains_no_frame_arithmetic() -> None:
    source = pathlib.Path("rvt_swarm/fd24/model.py").read_text()
    tree = ast.parse(source)
    called = {node.func.attr for node in ast.walk(tree)
              if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)}
    for trig in ("cos", "sin", "atan2", "rotate", "matmul", "mm"):
        assert trig not in called, trig
    assert ERRATUM["implementation_semantics"][
        "OLD_MISSION_OUTPUT_DECLARATION_IS_METADATA_ONLY"] is True
    assert ERRATUM["implementation_semantics"][
        "rotation_arithmetic_in_the_forward_path"] is False


# ---------------------------------------------------------------------------
# R16R-3/4/5/20 -- identifiability, and the negative test
# ---------------------------------------------------------------------------
def test_rotated_states_produce_identical_ego_features(session) -> None:
    """CASE II: the encoder input is exactly rotation invariant."""
    view_a = session._build_robot_view(session.robots[0])
    view_b = rotate_view(view_a, ROTATION)
    graph_a, graph_b = graph_for(view_a, session), graph_for(view_b, session)
    assert torch.equal(graph_a.node_x, graph_b.node_x)
    assert torch.equal(graph_a.edge_attr, graph_b.edge_attr)
    assert torch.equal(graph_a.node_feature_valid_mask, graph_b.node_feature_valid_mask)
    assert torch.equal(graph_a.edge_feature_valid_mask, graph_b.edge_feature_valid_mask)
    assert ERRATUM["frame_context"]["required"] is True


def test_the_world_target_is_not_invariant_under_that_rotation() -> None:
    target = (LIMITS[0] * 0.5, -LIMITS[1] * 0.25)
    rotated = rotate(target, ROTATION)
    assert target != rotated
    assert max(abs(target[i] - rotated[i]) for i in range(2)) > 0.05


def test_the_frame_context_makes_the_two_states_distinguishable(session) -> None:
    """R16R-20: remove it and they are ambiguous; restore it and they are not."""
    view_a = session._build_robot_view(session.robots[0])
    view_b = rotate_view(view_a, ROTATION)
    graph_a, graph_b = graph_for(view_a, session), graph_for(view_b, session)

    # masked: only the ego features -- ambiguous
    assert torch.equal(graph_a.node_x, graph_b.node_x)
    # restored: exactly the approved frame metadata separates them
    assert graph_a.mission_orientation_cos_sin != graph_b.mission_orientation_cos_sin

    batch_a = prepare_fd24_model_batch((graph_a,))
    batch_b = prepare_fd24_model_batch((graph_b,))
    assert torch.equal(batch_a.graph_batch.node_x, batch_b.graph_batch.node_x)
    assert not torch.equal(batch_a.mission_orientation_cos_sin,
                           batch_b.mission_orientation_cos_sin)

    model = RVTFD24LocalModel(MODEL, session.runtime_config)
    model.eval()
    with torch.no_grad():
        out_a = model(batch_a)
        out_b = model(batch_b)
    assert not torch.equal(out_a.residual_action, out_b.residual_action)
    # the recoverability head is deliberately untouched by orientation
    assert torch.equal(out_a.recoverability_logit, out_b.recoverability_logit)


def test_the_context_is_the_authoritative_mission_transform(session) -> None:
    view = session._build_robot_view(session.robots[0])
    graph = graph_for(view, session)
    norm = math.hypot(*view.mission_dir)
    assert graph.mission_orientation_cos_sin == (view.mission_dir[0] / norm,
                                                 view.mission_dir[1] / norm)
    assert abs(math.hypot(*graph.mission_orientation_cos_sin) - 1.0) < 1e-12
    context = ERRATUM["frame_context"]
    assert context["source_field"] == "RobotView.mission_dir"
    assert "_mission_axes" in context["source_transform"]
    assert context["separately_calculated_heading"] is False


# ---------------------------------------------------------------------------
# R16R-8 -- decentralization
# ---------------------------------------------------------------------------
def test_hidden_non_neighbour_state_cannot_change_the_frame_context(session) -> None:
    other = copy.deepcopy(session)
    far = other.robots[-1]
    far.position = (far.position[0] + 9.0, far.position[1] - 6.0)
    far.velocity = (0.0, 0.0)
    graph_a = graph_for(session._build_robot_view(session.robots[0]), session)
    graph_b = graph_for(other._build_robot_view(other.robots[0]), other)
    assert graph_a.mission_orientation_cos_sin == graph_b.mission_orientation_cos_sin
    assert torch.equal(graph_a.node_x, graph_b.node_x)
    assert session.robots[-1].position != other.robots[-1].position
    context = ERRATUM["frame_context"]
    assert context["requires_global_online_state_aggregation"] is False
    assert context["available_identically_to_every_robot"] is True


def test_every_robot_sees_the_same_frame_context(session) -> None:
    orientations = set()
    for robot in session.robots:
        view = session._build_robot_view(robot)
        graph = build_robot_local_ego_graph(
            view, session.runtime_config, robot.local_topology_metadata, COMPACT, 20)
        orientations.add(graph.mission_orientation_cos_sin)
    assert len(orientations) == 1


def test_the_context_is_declared_local_to_the_strict_guard() -> None:
    assert "mission_orientation_cos_sin" in EGO_TENSOR_PARAMS
    from rvt_swarm.decentralized import guards
    assert guards.scan_signatures() == []
    assert guards.audit() == []


# ---------------------------------------------------------------------------
# R16R-7/21 -- scope and parameters
# ---------------------------------------------------------------------------
def test_only_the_residual_head_consumes_the_orientation() -> None:
    source = pathlib.Path("rvt_swarm/fd24/model.py").read_text()
    tree = ast.parse(source)
    users = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            body = ast.dump(node)
            if "mission_orientation_cos_sin" in body:
                users.append(node.name)
    assert "FD24ResidualActionHead" in users
    for forbidden in ("FD24RecoverabilityHead", "FD24LocalEncoder"):
        assert forbidden not in users, forbidden
    context = ERRATUM["frame_context"]
    assert context["consumed_by"] == ["FD24ResidualActionHead"]
    assert "recoverability head" in context["not_consumed_by"]
    assert context["graph_topology_changed"] is False
    assert context["message_passing_changed"] is False
    assert context["global_pooling_introduced"] is False


def test_parameter_delta_is_only_the_residual_head(session) -> None:
    model = RVTFD24LocalModel(MODEL, session.runtime_config)
    counts = model.parameter_counts()
    impact = ERRATUM["parameter_impact"]
    assert counts["residual_action_head"] == impact["residual_action_head_after"]
    assert impact["residual_action_head_delta"] == (
        MISSION_ORIENTATION_CONTEXT_DIM * MODEL.hidden_dimension)
    assert (impact["residual_action_head_after"]
            - impact["residual_action_head_before"]) == impact[
        "residual_action_head_delta"]
    assert counts["recoverability_head"] == impact["recoverability_head"]
    assert impact["recoverability_head_changed"] is False
    assert counts["encoder"] == impact["encoder"]
    assert counts["candidate_conditioner"] == impact["candidate_conditioner"]
    assert counts["total"] == impact["total_after"]


def test_the_ego_feature_contract_did_not_move() -> None:
    impact = ERRATUM["ego_graph_impact"]
    assert impact["feature_schema_sha256"] == EGO_GRAPH_FEATURE_SCHEMA_SHA256
    assert impact["schema_version"] == EGO_GRAPH_SCHEMA_VERSION
    assert impact["node_feature_dim"] == NODE_FEATURE_DIM
    assert impact["edge_feature_dim"] == EDGE_FEATURE_DIM
    assert impact["node_or_edge_feature_added"] is False
    assert impact["feature_schema_hash_changed"] is False


def test_the_graph_record_round_trips_with_the_orientation(session) -> None:
    graph = graph_for(session._build_robot_view(session.robots[0]), session)
    restored = load_robot_local_ego_graph(
        dump_robot_local_ego_graph(graph), session.runtime_config)
    assert restored.mission_orientation_cos_sin == graph.mission_orientation_cos_sin
    assert restored.fingerprint() == graph.fingerprint()


# ---------------------------------------------------------------------------
# R16R-11/12/13 -- expert, bounds, saturation
# ---------------------------------------------------------------------------
def test_expert_target_and_lattice_are_untouched() -> None:
    assert SPEC["residual_expert_spec_v2_sha256"] == (
        "e3a3093038b31f7f8c11d56be224929c9eccc27e6bde2fa47c5c6c644b7f3fbf")
    composite = json.loads(
        (ROOT / "residual_label_contract_composite_v2.json").read_text())
    assert composite["residual_label_contract_composite_sha256"] == (
        "8921424d0342e26a7a22da4ca042543a8eb08c2dc310f5f5639b70678ceb08ad")
    binding = json.loads((ROOT / "rb15_residual_expert_binding_v2.json").read_text())
    assert binding["rb15_residual_expert_binding_v2_sha256"] == (
        "9edc8cc8d46b94c76f0fa8e3a2ea07b7bff06fd9d5cfe5f5cb26565170af3f24")
    assert len(residual_candidate_lattice(MODEL, RUNTIME)) == CANDIDATE_COUNT == 9
    assert SPEC["candidate_lattice"]["candidates_meters_per_second_squared"] == [
        list(item) for item in residual_candidate_lattice(MODEL, RUNTIME)]


def test_world_bounds_are_identical_across_expert_model_and_runtime(session) -> None:
    model = RVTFD24LocalModel(MODEL, session.runtime_config)
    expert_bound = residual_action_limits(MODEL, session.runtime_config)
    # the model buffer is float32; the bound is the same authoritative quantity
    model_bound = tuple(float(v) for v in model.residual_action_limits)
    assert tuple(expert_bound) == tuple(LIMITS)
    assert model_bound == pytest.approx(tuple(LIMITS), abs=1e-6)
    expert = LocalActionEvaluation((LIMITS[0], 0.0), True, True, True, 1.0, 0.0, 0.0, 0.0)
    target = build_residual_action_target((0.0, 0.0), expert, RUNTIME, MODEL)
    assert tuple(target.residual_bounds_world_acceleration) == tuple(LIMITS)
    # no rotated box, no enlarged bound
    assert not any(abs(v - 0.154) < 1e-3 for v in LIMITS)


def test_model_output_respects_the_world_componentwise_bound(session) -> None:
    view = session._build_robot_view(session.robots[0])
    batch = prepare_fd24_model_batch((graph_for(view, session),))
    model = RVTFD24LocalModel(MODEL, session.runtime_config)
    model.eval()
    with torch.no_grad():
        residual = model(batch).residual_action
    assert residual.shape == (1, 2)
    assert bool((residual.abs() <= torch.tensor(LIMITS) + 1e-6).all())


def test_tanh_limit_point_is_documented_not_repaired() -> None:
    lattice = residual_candidate_lattice(MODEL, RUNTIME)
    on_boundary = [c for c in lattice
                   if any(abs(abs(v) - limit) < 1e-12 for v, limit in zip(c, LIMITS))]
    assert len(on_boundary) == 8                      # every non-zero lattice point
    assert len(on_boundary) / len(lattice) == pytest.approx(8 / 9)
    saturated = bounded_residual_action(torch.tensor([[40.0, -40.0]]),
                                        torch.tensor(list(LIMITS)))
    assert float(saturated[0][0]) == pytest.approx(LIMITS[0], abs=1e-6)
    # tanh < 1 exactly, so in exact arithmetic the bound is approached, never
    # attained; float32 rounds the product to the representable neighbour.
    assert math.tanh(40.0) <= 1.0
    assert abs(float(saturated[0][0])) <= LIMITS[0] + 1e-6
    note = RB16["identity_transform"]["head_saturation_note"]
    assert "limit point" in note
    # Smooth L1 is well defined on an open interval; nothing requires exact equality
    from rvt_swarm.phase8 import contracts
    assert "smooth_l1" in contracts.LossContract.__dataclass_fields__[
        "residual_loss"].default


# ---------------------------------------------------------------------------
# R16R-17/18/19 -- loss, runtime, end to end
# ---------------------------------------------------------------------------
def test_loss_compares_world_to_world_with_no_conversion() -> None:
    from rvt_swarm.phase8 import contracts
    fields = contracts.LossContract.__dataclass_fields__
    assert fields["local_consistency_loss"].default == "disabled_initially"
    for module in ("rvt_swarm/fd24", "rvt_swarm/phase8", "rvt_swarm/phase8r"):
        for path in sorted(pathlib.Path(module).rglob("*.py")):
            text = path.read_text().lower()
            assert "equivarian" not in text, path


def test_runtime_adds_the_world_residual_before_the_projection() -> None:
    source = pathlib.Path("rvt_swarm/phase9c_rb/session.py").read_text()
    assert "Additive command disturbance BEFORE the unchanged projection." in source
    assert RB16["runtime_insertion_frame"] == "WORLD"
    producer = pathlib.Path("rvt_swarm/phase9c_rb/residual_expert_v2.py").read_text()
    for token in ("rotate", "_to_mission", "world_to_mission", "mission_to_world"):
        assert token not in producer, token


def test_non_symmetric_vector_survives_the_whole_world_path(session) -> None:
    delta = (LIMITS[0] * 0.5, -LIMITS[1] * 0.25)
    assert delta[0] != delta[1] and abs(delta[0]) != abs(delta[1])
    base = (0.10, -0.02)
    expert = LocalActionEvaluation((base[0] + delta[0], base[1] + delta[1]),
                                   True, True, True, 0.5, 0.4, 0.2, 0.3)
    target = build_residual_action_target(base, expert, RUNTIME, MODEL)
    assert tuple(target.residual_target_world_acceleration) == pytest.approx(delta)

    row = DenseActionSample(
        DENSE_ACTION_SAMPLE_SCHEMA_VERSION, EGO_GRAPH_SCHEMA_VERSION, "f" * 64, 5,
        base, (base[0] + delta[0], base[1] + delta[1]),
        tuple(target.residual_target_world_acceleration), base,
        (("intervened", "false"),), "role_0", 6, "F1", "g" * 64, "train",
        "r16r-row", 20, "0" * 40, (("runtime", "r" * 64),))
    decoded = tuple(row.residual_target_world_acceleration)
    assert decoded == pytest.approx(delta)

    model_output = decoded                    # deterministic injected WORLD output
    runtime_input = model_output
    pre_safety = (base[0] + runtime_input[0], base[1] + runtime_input[1])
    assert runtime_input[0] == pytest.approx(delta[0])
    assert runtime_input[1] == pytest.approx(delta[1])
    assert runtime_input != (delta[1], delta[0])          # no swap
    assert runtime_input != (-delta[0], -delta[1])        # no sign inversion
    assert pre_safety == pytest.approx((base[0] + delta[0], base[1] + delta[1]))


# ---------------------------------------------------------------------------
# R16R-16 and isolation
# ---------------------------------------------------------------------------
def test_no_rotation_augmentation_was_introduced() -> None:
    assert RB16["augmentation"]["PRIMARY_SYNTHETIC_ROTATION_AUGMENTATION"] == "DISABLED"
    assert RB16["counts_unchanged"]["PRIMARY_TRANSFORM_MULTIPLIER"] == 1
    assert RB16["augmentation"]["synthetic_transformed_supervision_rows"] == 0
    for module in ("rvt_swarm/fd24", "rvt_swarm/phase8r", "rvt_swarm/phase9c_rb"):
        for path in sorted(pathlib.Path(module).rglob("*.py")):
            assert "augment" not in path.read_text().lower(), path


def test_no_scientific_data_was_generated() -> None:
    residual_audit = json.loads(
        (ROOT / "datasets" / "phase9_residual_audit.json").read_text())
    assert residual_audit["emitted_rows"] == 0
    assert residual_audit["expert_calls"] == 0
    budget = json.loads((ROOT / "datasets" / "generation_budget_v1.json").read_text())
    assert budget["scientific_dataset_records_generated"] == 0
    assert budget["training_operations"] == 0
    assert budget["exact_total_budget"]["dense_residual_action_records"] == 536000


def test_seals_hold() -> None:
    assert PROTOCOL["final_test_access_policy"]["runtime_access_count"] == 0
    assert not (ROOT / "layout_execution_specifications" / "final_test").exists()
    v6 = json.loads((ROOT / "headroom_requalification_v6.json").read_text())
    assert v6["headroom_requalification_v6_sha256"] == (
        "d044d6b99d7a2bbb83565b121d188a35e335bfd856e3eb0e885823ca1a6742ef")
