"""Phase 8R-V2B -- the frozen V2 utility objective.

Every reducer is pinned against its owner decision, and every rejected
alternative is pinned as rejected. The V1 selector, its weights and its
tie-break are untouched and re-verified here.
"""

from __future__ import annotations

import ast
import hashlib
import json
import math
import pathlib

import pytest

from rvt_swarm.fd24.configuration import FD24ModelConfig, residual_action_limits
from rvt_swarm.phase8 import targets as phase8_targets
from rvt_swarm.phase8.targets import (
    LocalActionEvaluation, select_counterfactual_local_action,
)
from rvt_swarm.phase8r import (
    CANDIDATE_COUNT, RESIDUAL_EXPERT_V2_ID, UTILITY_INFORMATION_CLASS,
    ResidualUtilityError, canonical_lattice_hash, clearance_slack,
    normalized_action_deviation, normalized_clearance_margin,
    normalized_formation_error, normalized_progress, residual_candidate_lattice,
)
from rvt_swarm.phase8r import utility_v2
from rvt_swarm.phase9c_rb.binding import QUALIFIED_TEAM_SIZES
from rvt_swarm.runtime_configuration import RuntimeConfig

ROOT = pathlib.Path("results/rvt_fd24")
SPEC = json.loads((ROOT / "residual_expert_spec_v2.json").read_text())
COMPOSITE = json.loads((ROOT / "residual_label_contract_composite_v2.json").read_text())

RUNTIME = RuntimeConfig.for_team_size(5)
MODEL = FD24ModelConfig()
LIMITS = residual_action_limits(MODEL, RUNTIME)
LATTICE = residual_candidate_lattice(MODEL, RUNTIME)
SPACING = RUNTIME.formation.nominal_spacing_meters
UTILITY_MODULE = pathlib.Path("rvt_swarm/phase8r/utility_v2.py")


def _field(name):
    return next(row for row in SPEC["utility"]["fields"] if row["field"] == name)


# ---------------------------------------------------------------------------
# UTILITY-0/16 -- the V1 selector is untouched
# ---------------------------------------------------------------------------
def test_v1_selector_weights_and_dataclass_are_unchanged() -> None:
    item = LocalActionEvaluation((0.0, 0.0), True, True, True, 1.0, 1.0, 1.0, 1.0)
    assert item.utility() == pytest.approx(1.0 + 0.50 - 0.25 - 0.05)
    assert list(LocalActionEvaluation.__dataclass_fields__) == [
        "action_world_acceleration", "locally_feasible", "safety_projection_compatible",
        "robot_local_information_only", "normalized_progress",
        "normalized_clearance_margin", "normalized_formation_error",
        "normalized_action_deviation"]
    module = hashlib.sha256(
        pathlib.Path("rvt_swarm/phase8/targets.py").read_bytes()).hexdigest()
    assert module == SPEC["extends"]["phase8_targets_module_sha256"]
    assert SPEC["extends"]["selector_modified"] is False
    assert SPEC["extends"]["weights_modified"] is False
    assert SPEC["extends"]["tie_break_modified"] is False


def test_utility_information_classes_are_frozen() -> None:
    assert UTILITY_INFORMATION_CLASS == {
        "normalized_progress": "OFFLINE_LABEL_ORACLE",
        "normalized_clearance_margin": "OFFLINE_LABEL_ORACLE",
        "normalized_formation_error": "OFFLINE_LABEL_ORACLE",
        "normalized_action_deviation": "LOCAL_ACTION_INFORMATION",
    }
    for name, expected in UTILITY_INFORMATION_CLASS.items():
        assert _field(name)["information_class"] == expected
    assert SPEC["information_boundary"]["ACTION_INFORMATION_LOCAL"] is True
    assert SPEC["information_boundary"]["LABEL_ORACLE_CENTRALIZED"] is True
    assert SPEC["information_boundary"][
        "offline_oracle_may_become_a_runtime_model_input"] is False


# ---------------------------------------------------------------------------
# UTILITY-1/2/3 -- progress
# ---------------------------------------------------------------------------
def test_progress_is_the_signed_mean_increment_over_spacing() -> None:
    trace = [0.0, 0.3, 0.9, 1.2]                     # K = 3, total 1.2 m
    assert normalized_progress(trace, RUNTIME) == pytest.approx(
        (1.2 / 3.0) / SPACING)
    # equivalently: total displacement / K / spacing
    assert normalized_progress(trace, RUNTIME) == pytest.approx(
        (trace[-1] - trace[0]) / (len(trace) - 1) / SPACING)


def test_progress_is_signed_and_never_clipped_or_absolute() -> None:
    backwards = normalized_progress([0.0, -0.45], RUNTIME)
    assert backwards == pytest.approx(-0.45 / SPACING)
    assert backwards < 0.0
    mixed = normalized_progress([0.0, 1.0, 0.0], RUNTIME)
    assert mixed == pytest.approx(0.0)               # not a max, not an absolute value
    assert normalized_progress([0.0, 2.0, 0.0], RUNTIME) == pytest.approx(0.0)
    field = _field("normalized_progress")
    assert field["clipped"] is False and field["absolute_value"] is False


def test_progress_is_not_terminal_total_without_the_reduction() -> None:
    short, long = [0.0, 0.9], [0.0] * 9 + [0.9]
    assert normalized_progress(short, RUNTIME) > normalized_progress(long, RUNTIME)


def test_progress_normalizer_provenance_is_nominal_spacing() -> None:
    assert normalized_progress([0.0, SPACING], RUNTIME) == pytest.approx(1.0)
    other = RuntimeConfig.for_team_size(16)
    assert other.formation.nominal_spacing_meters == SPACING
    field = _field("normalized_progress")
    assert field["normalizer"] == "RuntimeConfig.formation.nominal_spacing_meters"
    assert "local_progress_spacing" in field["normalizer_authority"]


def test_k_zero_raises_and_has_no_fallback_denominator() -> None:
    with pytest.raises(ResidualUtilityError, match="no fallback denominator"):
        normalized_progress([0.4], RUNTIME)
    assert SPEC["evaluation"]["K_zero_possible"] is False
    audit = SPEC["evaluation"]["K_zero_audit"]["executable_audit"]
    assert audit["K_zero_cases"] == 0
    assert audit["controller_run_instants_snapshotted_and_restored"] == 503


# ---------------------------------------------------------------------------
# UTILITY-4/5/6/7 -- clearance
# ---------------------------------------------------------------------------
def test_clearance_slack_is_signed_and_normalized_by_its_own_threshold() -> None:
    assert clearance_slack(0.40, 0.40) == pytest.approx(0.0)          # exactly at
    assert clearance_slack(0.60, 0.40) == pytest.approx(0.5)          # above
    assert clearance_slack(0.20, 0.40) == pytest.approx(-0.5)         # violation
    assert clearance_slack(1.10, 0.55) == pytest.approx(1.0)


def test_clearance_margin_is_the_worst_slack_over_time_and_constraints() -> None:
    trace = [
        [(0.80, 0.40), (1.10, 0.55)],
        [(0.44, 0.40), (0.55, 0.55)],
        [(0.60, 0.40), (0.66, 0.55)],
    ]
    assert normalized_clearance_margin(trace) == pytest.approx(0.0)
    worse = trace + [[(0.30, 0.40)]]
    assert normalized_clearance_margin(worse) == pytest.approx(-0.25)


def test_clearance_is_not_clipped_at_zero() -> None:
    assert normalized_clearance_margin([[(0.10, 0.40)]]) < 0.0
    assert _field("normalized_clearance_margin")["clipped"] is False


def test_empty_clearance_set_raises_rather_than_inventing_a_sentinel() -> None:
    with pytest.raises(ResidualUtilityError, match="empty applicable clearance set"):
        normalized_clearance_margin([[(0.8, 0.4)], []])
    source = UTILITY_MODULE.read_text()
    for sentinel in ("inf)", "1e9", "float('inf')", 'float("inf")'):
        assert sentinel not in source, sentinel


def test_the_applicable_clearance_set_can_never_be_empty() -> None:
    """UTILITY-6: the smallest qualified team always has robot-robot pairs."""
    assert min(QUALIFIED_TEAM_SIZES) >= 2
    smallest = min(QUALIFIED_TEAM_SIZES)
    assert smallest * (smallest - 1) // 2 >= 10
    field = _field("normalized_clearance_margin")
    assert field["empty_set_possible"] is False
    assert field["qualified_team_sizes"] == list(QUALIFIED_TEAM_SIZES)


def test_every_clearance_threshold_comes_from_the_frozen_collision_truth() -> None:
    sources = {row["constraint_type"]: row for row in SPEC["clearance_sources"]}
    assert set(sources) == {"ROBOT_ROBOT", "ROBOT_STATIC_CIRCLE", "ROBOT_CORRIDOR_WALL",
                            "ROBOT_DYNAMIC_CIRCLE"}
    assert sources["ROBOT_ROBOT"]["threshold_value_meters"] == pytest.approx(
        RUNTIME.derived.robot_robot_required_clearance_meters)
    assert sources["ROBOT_ROBOT"]["always_applicable"] is True
    protocol = json.loads((ROOT / "executable_scientific_protocol_v1.json").read_text())
    inflation = protocol["static_obstacle_contract"]["collision_inflation"]
    assert sources["ROBOT_CORRIDOR_WALL"]["threshold_value_meters"] == pytest.approx(
        RUNTIME.physical.robot_radius_meters
        + inflation["obstacle_surface_margin_meters"])
    assert inflation["circle_center_threshold_formula"] == (
        "robot_radius + max(safety.obstacle_clearance_margin, circle_radius)")
    for row in SPEC["clearance_sources"]:
        digest = hashlib.sha256(pathlib.Path(row["source_file"]).read_bytes()).hexdigest()
        assert digest == row["source_file_sha256"], row["source_file"]


def test_no_communication_sensing_or_formation_scale_is_used_as_a_clearance_threshold() -> None:
    forbidden = {
        RUNTIME.communication.communication_range_meters,
        RUNTIME.sensing.obstacle_sensing_range_meters,
        RUNTIME.formation.nominal_spacing_meters,
        RUNTIME.derived.formation_tolerance_meters,
    }
    for row in SPEC["clearance_sources"]:
        value = row["threshold_value_meters"]
        if isinstance(value, (int, float)):
            assert not any(abs(value - bad) < 1e-12 for bad in forbidden), row


def test_boundary_exit_is_documented_as_deliberately_excluded() -> None:
    excluded = {row["constraint_type"] for row in SPEC["clearance_sources_excluded"]}
    assert excluded == {"WORLD_BOUNDARY"}


# ---------------------------------------------------------------------------
# UTILITY-8..12 -- formation error
# ---------------------------------------------------------------------------
def test_formation_uses_the_euclidean_norm_not_l1_or_linf() -> None:
    single = normalized_formation_error([(0.3, 0.4)], RUNTIME)
    assert single == pytest.approx(0.5 / SPACING)
    assert single != pytest.approx(0.7 / SPACING)        # L1
    assert single != pytest.approx(0.4 / SPACING)        # L-infinity


def test_formation_temporal_reduction_is_rms_not_mean_or_max() -> None:
    errors = [(0.0, 0.0), (0.6, 0.0)]
    rms = normalized_formation_error(errors, RUNTIME)
    assert rms == pytest.approx(math.sqrt((0.0 + 0.36) / 2.0) / SPACING)
    assert rms > (0.0 + 0.6) / 2.0 / SPACING            # strictly above the plain mean
    assert rms < 0.6 / SPACING                          # strictly below the maximum


def test_formation_normalizer_is_spacing_and_not_metric_v3_tolerance() -> None:
    field = _field("normalized_formation_error")
    assert field["normalizer"] == "RuntimeConfig.formation.nominal_spacing_meters"
    rejected = field["normalizer_rejected"]
    assert rejected["field"] == "RuntimeConfig.derived.formation_tolerance_meters"
    assert rejected["value"] == pytest.approx(RUNTIME.derived.formation_tolerance_meters)
    assert "tolerance" in rejected["reason"]
    assert normalized_formation_error([(SPACING, 0.0)], RUNTIME) == pytest.approx(1.0)
    assert normalized_formation_error(
        [(RUNTIME.derived.formation_tolerance_meters, 0.0)], RUNTIME) != pytest.approx(1.0)


def test_formation_sample_convention_excludes_the_initial_state() -> None:
    convention = SPEC["evaluation"]["trace_sample_convention"]
    assert convention["initial_state_included_in_M"] is False
    assert convention["M_equals_K"] is True
    assert _field("normalized_formation_error")["initial_state_included"] is False


def test_formation_rms_requires_at_least_one_sample() -> None:
    with pytest.raises(ResidualUtilityError, match="at least one trace sample"):
        normalized_formation_error([], RUNTIME)


# ---------------------------------------------------------------------------
# UTILITY-13/14/15 -- action deviation and the tie-break
# ---------------------------------------------------------------------------
def test_action_deviation_is_l2_over_the_euclidean_bound_norm() -> None:
    assert normalized_action_deviation((0.0, 0.0), MODEL, RUNTIME) == 0.0
    edge = normalized_action_deviation((LIMITS[0], 0.0), MODEL, RUNTIME)
    corner = normalized_action_deviation(LIMITS, MODEL, RUNTIME)
    assert edge == pytest.approx(1.0 / math.sqrt(2.0))
    assert corner == pytest.approx(1.0)
    assert edge < corner                                  # not L-infinity
    assert edge != pytest.approx(1.0)                     # not normalized by b_x alone


def test_action_deviation_handles_a_skewed_bound_vector() -> None:
    skewed = FD24ModelConfig(
        residual_limit_fractions_of_maximum_acceleration=(0.25, 0.125))
    limits = residual_action_limits(skewed, RUNTIME)
    assert limits[0] != limits[1]
    norm = math.hypot(*limits)
    assert normalized_action_deviation((limits[0], 0.0), skewed, RUNTIME) == pytest.approx(
        limits[0] / norm)
    assert normalized_action_deviation(limits, skewed, RUNTIME) == pytest.approx(1.0)
    # the y-edge is now the shorter one, which L-infinity would not distinguish
    assert (normalized_action_deviation((0.0, limits[1]), skewed, RUNTIME)
            < normalized_action_deviation((limits[0], 0.0), skewed, RUNTIME))


def test_sqrt_two_is_not_written_anywhere() -> None:
    source = UTILITY_MODULE.read_text()
    for literal in ("1.4142", "0.7071", "sqrt(2)", "2 ** 0.5", "2**0.5"):
        assert literal not in source, literal
    tree = ast.parse(source)
    constants = {node.value for node in ast.walk(tree)
                 if isinstance(node, ast.Constant)
                 and isinstance(node.value, (int, float)) and not isinstance(node.value, bool)}
    assert constants <= {0, 1, 2}, constants


def test_lattice_deviation_values_are_exactly_the_specified_three() -> None:
    values = sorted({round(normalized_action_deviation(c, MODEL, RUNTIME), 12)
                     for c in LATTICE})
    assert values == [0.0, round(1.0 / math.sqrt(2.0), 12), 1.0]
    assert sum(1 for c in LATTICE
               if normalized_action_deviation(c, MODEL, RUNTIME) == 0.0) == 1
    stored = _field("normalized_action_deviation")["lattice_values"]
    assert stored["zero"] == 0.0
    assert stored["axis_edge"] == pytest.approx(1.0 / math.sqrt(2.0))
    assert stored["corner"] == pytest.approx(1.0)


def _evaluation(action, deviation, progress=0.0):
    return LocalActionEvaluation(action, True, True, True, progress, 0.0, 0.0, deviation)


def test_exact_primary_tie_selects_the_lower_deviation_before_the_action_key() -> None:
    """UTILITY-15: the secondary key must outrank the action tuple."""
    base = (0.0, 0.0)
    edge_value = normalized_action_deviation((LIMITS[0], 0.0), MODEL, RUNTIME)
    corner_value = normalized_action_deviation(LIMITS, MODEL, RUNTIME)
    # equal primary utility by construction: progress offsets the deviation term
    edge = _evaluation((LIMITS[0], 0.0), edge_value, progress=0.05 * edge_value)
    corner = _evaluation(LIMITS, corner_value, progress=0.05 * corner_value)
    assert edge.utility() == corner.utility() == 0.0
    assert corner.action_world_acceleration > edge.action_world_acceleration
    for ordering in ((edge, corner), (corner, edge)):
        assert select_counterfactual_local_action(
            base, ordering, RUNTIME, MODEL) is edge


def test_enumeration_order_does_not_determine_the_winner() -> None:
    base = (0.0, 0.0)
    evaluations = [
        _evaluation(candidate, normalized_action_deviation(candidate, MODEL, RUNTIME),
                    progress=0.1 if candidate == (0.0, LIMITS[1]) else 0.0)
        for candidate in LATTICE
    ]
    forward = select_counterfactual_local_action(base, evaluations, RUNTIME, MODEL)
    backward = select_counterfactual_local_action(
        base, list(reversed(evaluations)), RUNTIME, MODEL)
    assert forward == backward
    assert forward.action_world_acceleration == (0.0, LIMITS[1])
    assert SPEC["tie_break"]["enumeration_order_determines_winner"] is False


def test_action_deviation_needs_no_rollout_information() -> None:
    """UTILITY-14: computable entirely at candidate construction time."""
    signature = utility_v2.normalized_action_deviation.__code__.co_varnames[
        :utility_v2.normalized_action_deviation.__code__.co_argcount]
    assert signature == ("delta_u_world", "model_config", "runtime_config")
    assert _field("normalized_action_deviation")["temporal_reducer"].startswith("none")


# ---------------------------------------------------------------------------
# UTILITY-17/18/19 -- trace boundary, terminal traces, no data dependence
# ---------------------------------------------------------------------------
def test_all_rollout_derived_utility_comes_from_one_trace() -> None:
    execution = SPEC["counterfactual_execution"]
    assert execution["identical_canonical_snapshot_per_candidate"] is True
    assert execution["matched_exogenous_streams"] is True
    assert execution["separate_utility_specific_simulation_permitted"] is False
    assert execution["single_trace_for_all_rollout_derived_utility"] is True


def test_terminal_and_failed_trajectories_are_scored_not_discarded() -> None:
    assert SPEC["evaluation"]["terminal_trajectories_discarded"] is False
    policy = SPEC["evaluation"]["terminal_policy"]
    for cause in ("collision", "task failure", "readiness failure", "horizon"):
        assert cause in policy


def test_the_reducers_contain_no_data_dependent_normalization() -> None:
    """UTILITY-19, checked structurally rather than by substring.

    Every identifier the module uses is on an allowlist, so a normalization
    that depends on a dataset, a candidate set, a batch or a fitted statistic
    cannot be spelled without failing here.
    """
    source = UTILITY_MODULE.read_text()
    tree = ast.parse(source)
    called = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                called.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                called.add(node.func.attr)
    allowed_calls = {"isfinite", "hypot", "sqrt", "float", "int", "sum", "len", "min",
                     "all", "range", "enumerate", "ResidualUtilityError",
                     "residual_action_limits", "_finite", "clearance_slack"}
    assert called <= allowed_calls, called - allowed_calls

    # No module-level mutable state that could accumulate a running statistic.
    module_assignments = [node for node in tree.body if isinstance(node, ast.Assign)]
    for node in module_assignments:
        assert isinstance(node.value, (ast.Constant, ast.Dict, ast.Name, ast.Subscript,
                                       ast.Call, ast.Tuple)), ast.dump(node)
    assert not any(isinstance(node, ast.Global) for node in ast.walk(tree))

    # No parameter names a dataset, a candidate set, a batch or a statistic.
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            for argument in node.args.args:
                for token in ("dataset", "batch", "candidates", "statistic", "corpus",
                              "samples_all", "population"):
                    assert token not in argument.arg, (node.name, argument.arg)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
        elif isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
    assert imported <= {"math", "typing", "__future__",
                        "fd24.configuration", "runtime_configuration"}, imported
    assert SPEC["utility"]["data_dependent_normalization"] is False
    assert SPEC["utility"]["forbidden_normalization_sources_used"] == []


def test_no_normalizer_constant_is_written_in_the_reducer_module() -> None:
    source = UTILITY_MODULE.read_text()
    for value in ("0.9", "0.15", "0.4", "0.55", "0.6", "3.0"):
        assert value not in source, value


def test_reducers_read_their_normalizers_from_configuration_not_arguments() -> None:
    """A caller cannot substitute a scale."""
    for function in (utility_v2.normalized_progress, utility_v2.normalized_formation_error):
        names = function.__code__.co_varnames[:function.__code__.co_argcount]
        assert "runtime_config" in names
        assert not any("spacing" in name or "scale" in name for name in names)
    other = RuntimeConfig.for_team_size(12)
    assert normalized_progress([0.0, 0.9], other) == normalized_progress(
        [0.0, 0.9], RUNTIME)


# ---------------------------------------------------------------------------
# UTILITY-20/21 -- artifacts
# ---------------------------------------------------------------------------
def test_v2_specification_exists_and_is_self_consistent() -> None:
    assert SPEC["schema_version"] == "rvt-residual-expert-spec/v2"
    assert SPEC["status"] == "FROZEN_PRE_DATA"
    assert SPEC["expert_id"] == RESIDUAL_EXPERT_V2_ID
    assert SPEC["candidate_lattice"]["count"] == CANDIDATE_COUNT == 9
    assert SPEC["candidate_lattice"]["candidate_set_sha256"] == canonical_lattice_hash(
        LATTICE)
    assert SPEC["candidate_lattice"]["zero_residual_occurrences"] == 1
    assert [row["field"] for row in SPEC["utility"]["fields"]] == list(
        UTILITY_INFORMATION_CLASS)
    for row in SPEC["utility"]["fields"]:
        assert row["dimensionless"] is True
        assert row["formula"]
        assert row["normalizer"]


def test_composite_references_every_required_component() -> None:
    roles = {row["role"] for row in COMPOSITE["components"]}
    for required in ("historical V1 target contract", "action pipeline erratum",
                     "residual expert V2 specification"):
        assert required in roles
    assert any("local-information" in role for role in roles)
    assert any("snapshot" in role for role in roles)
    assert any("generation-budget" in role for role in roles)
    assert COMPOSITE["historical_phase8_hashes_altered"] is False
    assert COMPOSITE["generation_authorized"] is False
    assert "RB-17" in COMPOSITE["rb17_requirement"]
    for row in COMPOSITE["components"]:
        if row["path"].startswith(("docs/", "rvt_swarm/")):
            digest = hashlib.sha256(pathlib.Path(row["path"]).read_bytes()).hexdigest()
            assert digest == row["sha256"], row["path"]


# ---------------------------------------------------------------------------
# BUDGET-1..4, RB-16 and isolation
# ---------------------------------------------------------------------------
def test_generation_timeout_remains_pending_and_generation_is_unauthorized() -> None:
    budget = SPEC["generation_budget_impact"]
    assert budget["RESIDUAL_V2_GENERATION_TIMEOUT"] == "PENDING_PERFORMANCE_BENCHMARK"
    assert budget["official_generation_authorized"] is False
    assert budget["official_job_manifest_mutated"] is False
    stored = json.loads(
        (ROOT / "datasets" / "generation_budget_v1.json").read_text())
    assert stored["timeout_contract"]["wall_clock_seconds"][
        "residual_action_cell_generation_job"] == 1800      # unchanged


def test_compute_bound_is_evaluations_not_stored_rows() -> None:
    budget = SPEC["generation_budget_impact"]
    assert budget["stored_dense_residual_row_upper_cap"] == 536000
    assert budget["candidate_evaluations_per_row"] == 9
    assert budget["candidate_evaluation_upper_bound"] == 536000 * 9 == 4824000
    assert budget["this_is_a_compute_upper_bound_not_a_stored_row_count"] is True
    stored = json.loads(
        (ROOT / "datasets" / "generation_budget_v1.json").read_text())
    assert stored["exact_total_budget"]["dense_residual_action_records"] == 536000


def test_job_identity_v2_dimensions_are_recorded_without_mutation() -> None:
    dimensions = SPEC["generation_budget_impact"][
        "residual_job_identity_v2_required_dimensions"]
    assert len(dimensions) == 5
    assert any("candidate residual" in dimension for dimension in dimensions)
    stored = json.loads(
        (ROOT / "datasets" / "generation_budget_v1.json").read_text())
    assert stored["job_identity_contract"]["residual_cell"] == [
        "study", "split", "family", "layout_sha256", "team_size"]


def test_h4_optionality_is_recorded_without_a_post_hoc_objective_change() -> None:
    h4 = SPEC["h4_optionality"]
    assert h4["residual_learning_is_optional_h4"] is True
    assert h4[
        "post_hoc_horizon_or_objective_change_to_speed_generation_permitted"] is False


def test_rb16_augmentation_stays_disabled() -> None:
    assert SPEC["rb16"]["PRIMARY_SYNTHETIC_ROTATION_AUGMENTATION"] == "DISABLED"
    assert SPEC["rb16"]["rb16_started"] is False


def test_no_scientific_data_exists() -> None:
    scope = SPEC["scope"]
    assert scope["rb15_producer_implemented"] is False
    assert scope["supervision_generated"] is False
    for key in ("recoverability_rows", "residual_rows", "scientific_shards",
                "new_fd24_checkpoints", "optimizer_states", "training_operations",
                "final_test_access_count", "study_a_n24_access_count"):
        assert scope[key] == 0, key
    residual_audit = json.loads(
        (ROOT / "datasets" / "phase9_residual_audit.json").read_text())
    assert residual_audit["emitted_rows"] == 0
    assert residual_audit["expert_calls"] == 0


def test_the_v2_reducers_are_not_a_producer() -> None:
    """No snapshot, no rollout, no enumeration, no selector call."""
    tree = ast.parse(UTILITY_MODULE.read_text())
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    attributes = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    forbidden = {"snapshot", "EpisodeSnapshot", "SimulatorEpisodeSession", "step",
                 "select_counterfactual_local_action", "residual_candidate_lattice",
                 "build_residual_action_target"}
    assert not (names | attributes) & forbidden


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


def test_historical_phase8_protocol_documents_are_unchanged() -> None:
    manifest = json.loads((ROOT / "experiment_protocol_manifest.json").read_text())
    for entry in manifest["hashed_protocol_documents"].values():
        digest = hashlib.sha256(pathlib.Path(entry["path"]).read_bytes()).hexdigest()
        assert digest == entry["sha256"], entry["path"]
