"""Qualification for the CR-0R closures: safety rule, A3 control, layout semantics."""
from __future__ import annotations

import pytest

from rvt_swarm.cleanroom.a3_control import (
    BLOCKS, CANDIDATE_EMBEDDING_DIMENSION, CAPACITY_MATCH_TOLERANCE_FRACTION,
    DROPOUT_PROBABILITY, HIDDEN_DIMENSION, M2_RECOVERABILITY_PATH_PARAMETERS,
    capacity_match_report,
)
from rvt_swarm.cleanroom.safety_contract import (
    COLLISION_ABSOLUTE_DEGRADATION_MAXIMUM, COLLISION_FREE_POINT_ESTIMATE_MINIMUM,
    PRIMARY_ENDPOINTS, SECONDARY_ENDPOINTS, SafetyContractError,
    TTC_VIOLATION_THRESHOLD_S, EndpointVerdict, central_closed_loop_claim,
    endpoint_passes, safety_hypothesis_passes,
)

BY_KEY = {e.key: e for e in PRIMARY_ENDPOINTS}


# ------------------------------------------------------------------ safety ---

def test_four_primary_endpoints_each_fully_specified():
    assert len(PRIMARY_ENDPOINTS) == 4
    for e in PRIMARY_ENDPOINTS:
        assert e.definition and e.unit and e.aggregation_unit
        assert e.direction_of_harm in ("increase", "decrease")
        assert e.margin > 0 and e.margin_justification
        assert e.role == "PRIMARY"


def test_margins_are_the_frozen_values():
    assert BY_KEY["collision_free_rate"].margin == COLLISION_ABSOLUTE_DEGRADATION_MAXIMUM == 0.01
    assert BY_KEY["collision_free_rate"].absolute_floor == COLLISION_FREE_POINT_ESTIMATE_MINIMUM == 0.95
    assert BY_KEY["minimum_clearance_m"].margin == 0.01
    assert BY_KEY["ttc_violation_rate"].margin == 0.01
    assert BY_KEY["severe_near_collision_rate"].margin == 0.005
    assert TTC_VIOLATION_THRESHOLD_S == 1.5


def test_severe_endpoint_margin_is_stricter_than_the_gate_margin():
    assert BY_KEY["severe_near_collision_rate"].margin < BY_KEY["collision_free_rate"].margin


def test_decrease_endpoint_passes_only_inside_the_margin():
    e = BY_KEY["collision_free_rate"]
    assert endpoint_passes(e, point_difference=-0.002, one_sided_bound=-0.009,
                           treatment_point_estimate=0.97).passed
    assert not endpoint_passes(e, point_difference=-0.02, one_sided_bound=-0.011,
                               treatment_point_estimate=0.97).passed
    # exactly at the margin is a failure: the rule is strict
    assert not endpoint_passes(e, point_difference=-0.01, one_sided_bound=-0.01,
                               treatment_point_estimate=0.97).passed


def test_absolute_floor_can_fail_a_non_inferior_result():
    e = BY_KEY["collision_free_rate"]
    v = endpoint_passes(e, point_difference=0.0, one_sided_bound=-0.001,
                        treatment_point_estimate=0.90)
    assert not v.passed and "absolute floor" in v.reason


def test_absolute_floor_requires_a_treatment_estimate():
    with pytest.raises(SafetyContractError):
        endpoint_passes(BY_KEY["collision_free_rate"], point_difference=0.0,
                        one_sided_bound=-0.001)


def test_increase_endpoint_direction():
    e = BY_KEY["ttc_violation_rate"]
    assert endpoint_passes(e, point_difference=0.001, one_sided_bound=0.009).passed
    assert not endpoint_passes(e, point_difference=0.02, one_sided_bound=0.011).passed


def test_secondary_endpoint_has_no_pass_rule():
    with pytest.raises(SafetyContractError):
        endpoint_passes(SECONDARY_ENDPOINTS[0], point_difference=0.0, one_sided_bound=0.0)


def test_intersection_union_requires_every_endpoint():
    ok = {e.key: EndpointVerdict(e.key, True, "") for e in PRIMARY_ENDPOINTS}
    assert safety_hypothesis_passes(ok)
    for k in list(ok):
        one_bad = dict(ok); one_bad[k] = EndpointVerdict(k, False, "")
        assert not safety_hypothesis_passes(one_bad)


def test_missing_endpoint_verdict_fails_closed():
    partial = {e.key: EndpointVerdict(e.key, True, "") for e in PRIMARY_ENDPOINTS[:3]}
    with pytest.raises(SafetyContractError):
        safety_hypothesis_passes(partial)


def test_progress_without_safety_fails_the_central_claim():
    assert central_closed_loop_claim(True, True) == "CENTRAL_CLOSED_LOOP_CLAIM_SUPPORTED"
    assert central_closed_loop_claim(True, False) == "CENTRAL_CLAIM_FAILS_SAFETY_NON_INFERIORITY_NOT_MET"
    assert central_closed_loop_claim(False, True) == "CENTRAL_CLAIM_FAILS_BENEFIT_NOT_DEMONSTRATED"
    assert central_closed_loop_claim(False, False).startswith("CENTRAL_CLAIM_FAILS")


# ---------------------------------------------------------------------- A3 ---

def test_a3_is_capacity_matched_to_m2_within_tolerance():
    r = capacity_match_report()
    assert r["within_tolerance"]
    assert abs(r["relative_difference"]) <= CAPACITY_MATCH_TOLERANCE_FRACTION
    assert r["a3_parameters"] == 261681
    assert r["m2_recoverability_path_parameters"] == M2_RECOVERABILITY_PATH_PARAMETERS == 262529


def test_a3_frozen_hyperparameters_match_m2_where_they_must():
    assert HIDDEN_DIMENSION == 184
    assert BLOCKS == 3                              # same depth as M2
    assert CANDIDATE_EMBEDDING_DIMENSION == 16      # same topology conditioning as M2
    assert DROPOUT_PROBABILITY == 0.0               # same as M2


def test_a3_width_is_the_closest_matching_width():
    here = abs(capacity_match_report(HIDDEN_DIMENSION)["absolute_difference"])
    for w in (HIDDEN_DIMENSION - 1, HIDDEN_DIMENSION + 1):
        assert here <= abs(capacity_match_report(w)["absolute_difference"])


def test_a3_sees_topology_identity_so_it_is_not_the_blinding_ablation():
    from rvt_swarm.cleanroom.a3_control import A3PooledLocalModel
    m = A3PooledLocalModel()
    assert m.candidate_embedding.embedding_dim == CANDIDATE_EMBEDDING_DIMENSION


def test_a3_has_no_message_passing_module():
    import inspect
    from rvt_swarm.cleanroom import a3_control
    src = inspect.getsource(a3_control)
    for banned in ("scatter_add", "propagate", "MessagePassing", "GATConv", "attention"):
        assert banned not in src
