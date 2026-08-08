"""RB-15 -- frozen residual-expert audit, locked in as regressions.

RB-15 stopped at Verdict A: the frozen expert
`B_FROZEN_COUNTERFACTUAL_LOCAL_ACTION_SEARCH_V1` has a frozen selector, bound and
target builder, but no frozen candidate enumeration, no frozen utility
normalizers and no frozen candidate horizon. These tests pin both halves -- what
*is* frozen must not drift, and what is *missing* must not be quietly invented by
a later phase.
"""

from __future__ import annotations

import ast
import hashlib
import inspect
import json
import pathlib

import pytest

from rvt_swarm.fd24.configuration import FD24ModelConfig, residual_action_limits
from rvt_swarm.phase8 import diagnostic as phase8_diagnostic
from rvt_swarm.phase8 import targets as phase8_targets
from rvt_swarm.phase8.targets import (
    RESIDUAL_EXPERT_ID,
    LocalActionEvaluation,
    build_residual_action_target,
    select_counterfactual_local_action,
)
from rvt_swarm.runtime_configuration import RuntimeConfig

ROOT = pathlib.Path("results/rvt_fd24")
BINDING = json.loads((ROOT / "rb15_residual_expert_binding_v1.json").read_text())
MAPPING = json.loads((ROOT / "rb15_local_information_mapping_v1.json").read_text())

RUNTIME = RuntimeConfig.for_team_size(5)
MODEL = FD24ModelConfig()


def _evaluation(action, progress=0.5, *, clearance=0.4, formation=0.2, deviation=0.2,
                local=True, feasible=True, safe=True):
    return LocalActionEvaluation(action, feasible, safe, local,
                                 progress, clearance, formation, deviation)


# ---------------------------------------------------------------------------
# what is frozen must not drift
# ---------------------------------------------------------------------------
def test_expert_identity_and_module_hash_are_unchanged() -> None:
    assert RESIDUAL_EXPERT_ID == "B_FROZEN_COUNTERFACTUAL_LOCAL_ACTION_SEARCH_V1"
    assert BINDING["expert"]["expert_id"] == RESIDUAL_EXPERT_ID
    module = hashlib.sha256(
        pathlib.Path("rvt_swarm/phase8/targets.py").read_bytes()).hexdigest()
    assert module == BINDING["expert"]["module_sha256"], "the frozen expert changed"
    assert BINDING["expert"]["expert_modified"] is False


def test_hashed_action_target_contract_is_unchanged() -> None:
    manifest = json.loads((ROOT / "experiment_protocol_manifest.json").read_text())
    entry = manifest["hashed_protocol_documents"]["action_target"]
    digest = hashlib.sha256(pathlib.Path(entry["path"]).read_bytes()).hexdigest()
    assert digest == entry["sha256"]


def test_residual_bound_is_derived_not_written() -> None:
    limits = residual_action_limits(MODEL, RUNTIME)
    assert limits == (0.15, 0.15)
    assert tuple(MODEL.residual_limit_fractions_of_maximum_acceleration) == (0.25, 0.25)
    assert RUNTIME.physical.maximum_acceleration_meters_per_second_squared == 0.6
    assert BINDING["residual_bound"]["duplicated_literal_introduced"] is False
    # No publication-side enumerator exists, so no module may carry its own bound.
    assert BINDING["candidate_enumeration"]["authoritative_source_exists"] is False


def test_eligibility_is_the_frozen_five_way_conjunction() -> None:
    base = (0.1, 0.0)
    good = _evaluation((0.2, 0.0), 0.9)
    for broken in (
        _evaluation((0.2, 0.0), 0.9, feasible=False),
        _evaluation((0.2, 0.0), 0.9, safe=False),
        _evaluation((0.2, 0.0), 0.9, local=False),
        _evaluation((0.30, 0.0), 0.9),            # outside the 0.15 residual bound
        _evaluation((0.70, 0.0), 0.9),            # outside the physical disk
    ):
        with pytest.raises(ValueError, match="no eligible"):
            select_counterfactual_local_action(base, (broken,), RUNTIME, MODEL)
    assert select_counterfactual_local_action(
        base, (good,), RUNTIME, MODEL).action_world_acceleration == (0.2, 0.0)


def test_no_eligible_candidate_raises_and_has_no_fallback() -> None:
    """RB15-17: the frozen behaviour is a raise, not a safe zero-residual default."""
    with pytest.raises(ValueError, match="no eligible robot-local candidate"):
        select_counterfactual_local_action(
            (0.0, 0.0), (_evaluation((0.1, 0.0), 1.0, local=False),), RUNTIME, MODEL)
    source = inspect.getsource(select_counterfactual_local_action)
    assert "return" not in source.split("if not eligible:")[1].split("raise")[0]


def test_frozen_utility_weights() -> None:
    item = _evaluation((0.0, 0.0), progress=1.0, clearance=1.0, formation=1.0,
                       deviation=1.0)
    assert item.utility() == pytest.approx(1.0 + 0.50 - 0.25 - 0.05)


def test_tie_break_is_deterministic_and_order_independent() -> None:
    """RB15-15: identical primary score, frozen winner, no randomness."""
    base = (0.0, 0.0)
    left = _evaluation((0.10, 0.0), progress=0.5, deviation=0.2)
    right = _evaluation((0.05, 0.0), progress=0.5, deviation=0.2)
    assert left.utility() == right.utility()
    forward = select_counterfactual_local_action(base, (left, right), RUNTIME, MODEL)
    backward = select_counterfactual_local_action(base, (right, left), RUNTIME, MODEL)
    assert forward == backward == left          # larger action vector wins the third key

    # The secondary key outranks the third: lower deviation wins even with a
    # lexicographically smaller action. The utilities must tie *exactly* -- the
    # frozen selector compares raw floats, with no tolerance.
    low = _evaluation((0.05, 0.0), progress=0.0, clearance=0.0, formation=0.0,
                      deviation=0.0)
    high = _evaluation((0.10, 0.0), progress=0.05, clearance=0.0, formation=0.0,
                       deviation=1.0)
    assert low.utility() == high.utility() == 0.0
    assert select_counterfactual_local_action(base, (high, low), RUNTIME, MODEL) == low
    assert select_counterfactual_local_action(base, (low, high), RUNTIME, MODEL) == low


def test_residual_target_is_the_frozen_clipped_difference() -> None:
    expert = _evaluation((0.25, -0.30))
    target = build_residual_action_target((0.0, 0.0), expert, RUNTIME, MODEL)
    assert target.expert_source == RESIDUAL_EXPERT_ID
    assert target.residual_target_world_acceleration == pytest.approx((0.15, -0.15))
    assert target.residual_bounds_world_acceleration == pytest.approx((0.15, 0.15))
    assert target.finite and target.nonzero and target.saturated


def test_target_frame_is_native_world_acceleration_with_no_rb16_rotation() -> None:
    """RB15-12/RB15-16: RB-16 frame work must not leak into RB-15."""
    assert BINDING["target_construction"]["native_frame_reported"] == (
        "world_acceleration_meters_per_second_squared")
    assert BINDING["target_construction"][
        "rb16_rotation_or_frame_correction_applied"] is False
    assert BINDING["action_frame"] == {
        "frame": "world", "units": "meters_per_second_squared",
        "control_period_seconds": 0.15}


# ---------------------------------------------------------------------------
# what is missing must not be quietly invented
# ---------------------------------------------------------------------------
def _evaluation_constructors() -> list[str]:
    """Every module that constructs a LocalActionEvaluation."""
    found = []
    for path in sorted(pathlib.Path("rvt_swarm").rglob("*.py")):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == "LocalActionEvaluation"):
                found.append(str(path))
                break
    return found


def test_no_publication_runtime_candidate_producer_exists() -> None:
    """The RB15-1 finding. A later phase that adds one must update this test.

    The point is that adding a producer is a *specification* act: it must arrive
    with a frozen enumeration, not as an implementation detail.
    """
    constructors = _evaluation_constructors()
    assert constructors == ["rvt_swarm/phase8/diagnostic.py"], constructors
    assert not any(path.startswith("rvt_swarm/phase9c") for path in constructors)
    assert BINDING["producer_implemented"] is False


def test_the_two_known_producers_are_fixtures_and_disagree() -> None:
    """RB15-1: neither is frozen, and they are not the same enumeration."""
    assert "never a scientific dataset" in phase8_diagnostic.__doc__
    manifest = json.loads((ROOT / "experiment_protocol_manifest.json").read_text())
    hashed = {entry["path"] for entry in manifest["hashed_protocol_documents"].values()}
    assert "rvt_swarm/phase8/diagnostic.py" not in hashed

    diagnostic_base, diagnostic_evaluations = phase8_diagnostic._action_evaluations(
        0, RUNTIME, MODEL)
    assert len(diagnostic_evaluations) == 3
    assert diagnostic_base != (0.1, 0.0)        # the unit-test fixture's base
    # the diagnostic fixture even emits duplicate candidates on one sample in four
    assert (diagnostic_evaluations[0].action_world_acceleration
            == diagnostic_evaluations[1].action_world_acceleration)

    enumeration = BINDING["candidate_enumeration"]
    assert enumeration["producers_agree"] is False
    assert enumeration["candidate_count"] is None
    assert enumeration["candidate_values"] is None
    assert enumeration["ordering"] is None
    assert enumeration["zero_residual_member"] is None
    assert enumeration["new_hyperparameter_introduced"] is False


def test_utility_normalizers_have_no_producer_anywhere() -> None:
    """RB15-14: nothing in the package computes the four scored terms.

    The terms are not merely uncomputed -- outside the dataclass that declares
    them they are never referenced by name at all. The one constructor supplies
    them positionally, as fixture literals.
    """
    scored = ("normalized_progress", "normalized_clearance_margin",
              "normalized_formation_error", "normalized_action_deviation")
    referencing = []
    for path in sorted(pathlib.Path("rvt_swarm").rglob("*.py")):
        if path.as_posix() == "rvt_swarm/phase8/targets.py":
            continue                            # the dataclass declaration itself
        text = path.read_text()
        if any(name in text for name in scored):
            referencing.append(path.as_posix())
    assert referencing == [], referencing
    assert _evaluation_constructors() == ["rvt_swarm/phase8/diagnostic.py"]
    assert BINDING["score_and_selection"]["normalizers_frozen"] is False
    assert BINDING["score_and_selection"]["normalizer_definitions_found"] == 0


def test_no_frozen_candidate_rollout_horizon_exists() -> None:
    horizon = BINDING["rollout_horizon"]
    assert horizon["frozen_source_exists"] is False
    assert horizon["existing_producers_perform_rollouts"] is False
    # the only horizon in the frozen target module belongs to topology rollouts
    trace_fields = phase8_targets.CounterfactualRolloutTrace.__dataclass_fields__
    assert "horizon_seconds" in trace_fields
    assert "candidate_topology" in trace_fields


def test_field_mapping_is_complete_and_has_no_vague_entries() -> None:
    """RB15-4: every expert input is enumerated; gaps are named, not hand-waved."""
    assert MAPPING["schema_version"] == "rvt-rb15-local-information-mapping/v1"
    assert MAPPING["vague_entries"] == 0
    allowed = {"SELF_LOCAL", "ONE_HOP_LOCAL", "LOCAL_OBSTACLE", "LOCAL_PROTOCOL_STATE",
               "LOCAL_CONTROLLER_DERIVED", "LOCAL_SAFETY_DERIVED",
               "IMMUTABLE_FROZEN_CONFIG", "OFFLINE_LABEL_ORACLE",
               "UNSPECIFIED_NO_FROZEN_SOURCE"}
    expert_fields = {field.name for field in
                     LocalActionEvaluation.__dataclass_fields__.values()}
    mapped = {row["expert_field"].split(".")[-1] for row in MAPPING["fields"]}
    assert expert_fields <= mapped, expert_fields - mapped
    for row in MAPPING["fields"]:
        assert row["local_provenance_class"] in allowed, row
        assert row["specification_status"] in (
            "SPECIFIED", "BLOCKING_GAP", "BLOCKED_BY_UPSTREAM_GAP")
        if row["specification_status"] == "SPECIFIED":
            assert row["source_path"], row
        assert "available locally" not in json.dumps(row).lower()


def test_robot_local_information_only_is_never_asserted_in_production_code() -> None:
    """RB15-5: the flag must be earned. No publication module may set it True."""
    for path in sorted(pathlib.Path("rvt_swarm/phase9c_rb").rglob("*.py")):
        assert "robot_local_information_only" not in path.read_text(), path
    assert BINDING["information_boundary"][
        "robot_local_information_only_asserted_in_production_code"] is False
    assert BINDING["information_boundary"]["separate_expert_view_created"] is False


def test_a_forbidden_global_source_cannot_survive_the_frozen_filter() -> None:
    """RB15-5's intervention, at the level the frozen contract actually enforces.

    A candidate whose action information is non-local is dropped by the frozen
    selector even when it dominates every score.
    """
    base = (0.0, 0.0)
    dominant_but_global = _evaluation((0.10, 0.0), progress=10.0, clearance=10.0,
                                      formation=0.0, deviation=0.0, local=False)
    modest_but_local = _evaluation((0.01, 0.0), progress=0.1, clearance=0.0,
                                   formation=0.0, deviation=0.0)
    assert dominant_but_global.utility() > modest_but_local.utility()
    chosen = select_counterfactual_local_action(
        base, (dominant_but_global, modest_but_local), RUNTIME, MODEL)
    assert chosen is modest_but_local
    with pytest.raises(ValueError, match="no eligible"):
        select_counterfactual_local_action(base, (dominant_but_global,), RUNTIME, MODEL)


def test_action_pipeline_boundary_contradiction_is_recorded_not_resolved() -> None:
    """RB15-10: the phase must not pick a side silently."""
    boundary = BINDING["action_pipeline_boundary"]
    assert boundary["contradiction"] is True
    assert boundary["resolved_by_this_phase"] is False
    assert boundary["system_model_boundary"] == "A_BEFORE_LOCAL_SAFETY_PROJECTION"
    assert boundary["publication_runtime_boundary"] == "A_BEFORE_LOCAL_SAFETY_PROJECTION"
    assert "projected" in boundary["hashed_action_target_document_wording"]


# ---------------------------------------------------------------------------
# isolation
# ---------------------------------------------------------------------------
def test_rb15_generated_no_scientific_supervision() -> None:
    isolation = BINDING["scientific_isolation"]
    assert isolation["official_residual_supervision_rows"] == 0
    assert isolation["official_recoverability_rows"] == 0
    assert isolation["scientific_shards"] == 0
    assert isolation["model_checkpoints"] == 0
    assert isolation["optimizer_states"] == 0
    assert isolation["expert_calls_in_scientific_context"] == 0
    assert isolation["generation_budget_run"] is False
    assert isolation["final_test_access_count"] == 0
    assert isolation["study_a_n24_access_count"] == 0
    assert BINDING["diagnostic_canary"]["persisted_as_scientific_schema"] is False


def test_authoritative_headroom_artifacts_are_untouched() -> None:
    provenance = BINDING["headroom_provenance"]
    v6 = json.loads((ROOT / "headroom_requalification_v6.json").read_text())
    reproduction = json.loads(
        (ROOT / "headroom_v6_detached_reproduction_v1.json").read_text())
    authority = json.loads((ROOT / "headroom_authority_record_v1.json").read_text())
    assert v6["headroom_requalification_v6_sha256"] == provenance[
        "headroom_requalification_v6_sha256"]
    assert reproduction["headroom_v6_detached_reproduction_sha256"] == provenance[
        "headroom_v6_detached_reproduction_sha256"]
    assert authority["headroom_authority_record_sha256"] == provenance[
        "headroom_authority_record_sha256"]
    assert provenance["H2_PRE_DATA_VIABILITY"] is True
    assert provenance["H2_EMPIRICALLY_CONFIRMED"] is False


def test_f5_partial_attempt_interpretation_is_preserved() -> None:
    f5 = BINDING["headroom_provenance"]["f5_interpretation"]
    assert f5["cell_id"] == "train/train-f5-00/N8"
    assert f5["completed_switching_epochs"] == 0
    assert f5["mechanism"] == "PARTIAL_ATTEMPT_EFFECT"
    assert f5["may_be_cited_as_completed_topology_switch"] is False
