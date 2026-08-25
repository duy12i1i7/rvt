"""Qualification for the CR-0S closures: H-CL1 benefit, oracle headroom, CL-DEV selection.

Every fixture in the frozen negative list must fail closed.
"""
from __future__ import annotations

import pytest

from rvt_swarm.cleanroom.benefit_contract import (
    COMPARATOR_ARM, MAXIMUM_INVALID_EPISODE_FRACTION, PRACTICAL_BENEFIT_THRESHOLD,
    PRIMARY, SEQUENCE, TREATMENT_ARM, BenefitContractError, EndpointResult,
    fixed_sequence_verdicts, impute_invalid, permitted_benefit_language, primary_passes,
)
from rvt_swarm.cleanroom.closed_loop_engine import (
    CLAIM_NOT_SUPPORTED, CLAIM_SUPPORTED, evaluate_closed_loop,
)
from rvt_swarm.cleanroom.development_selection import (
    CONSECUTIVE_NON_IMPROVEMENTS_TO_STOP, MAXIMUM_EVALUATED_CONFIGURATIONS,
    NO_ADMISSIBLE_CONFIGURATION, ConfigurationRecord, DevelopmentSelectionError,
    is_admissible, select_final_configuration, should_stop,
)
from rvt_swarm.cleanroom.oracle_contract import (
    ORACLE_HEADROOM_FAIL, ORACLE_HEADROOM_PASS, ORACLE_PRACTICAL_THRESHOLD,
    PREMISE_AT_RISK, learned_system_interpretation, oracle_headroom,
)
from rvt_swarm.cleanroom.safety_contract import (
    PRIMARY_ENDPOINTS as SAFETY_ENDPOINTS, EndpointVerdict as SafetyVerdict,
)
from rvt_swarm.cleanroom.universe import UniverseContractError

IDS = [f"e{i}" for i in range(10)]
LAY = {e: ("L0" if i < 5 else "L1") for i, e in enumerate(IDS)}
EV = [e for e in IDS for _ in range(2)]


def R(k, p, lo, hi): return EndpointResult(k, p, lo, hi)
def good_benefit():
    return {"episode_task_success_rate": R("episode_task_success_rate", 0.12, 0.09, 0.15),
            "deadlock_rate": R("deadlock_rate", -0.05, -0.08, -0.02),
            "irreversible_collapse_rate": R("irreversible_collapse_rate", -0.04, -0.07, -0.01),
            "goal_reached_rate": R("goal_reached_rate", 0.10, 0.06, 0.14)}
def safety(ok=True):
    v = {e.key: SafetyVerdict(e.key, True, "") for e in SAFETY_ENDPOINTS}
    if not ok:
        v["collision_free_rate"] = SafetyVerdict("collision_free_rate", False, "")
    return v
def kw(**over):
    base = dict(manifest_episode_ids=IDS, manifest_episode_layout=LAY,
                observed_event_episode_ids=EV, expected_episode_count=10,
                treatment_arm=TREATMENT_ARM, comparator_arm=COMPARATOR_ARM,
                invalid_episode_count=0, bootstrap_replicates=10000,
                bootstrap_seed=20260901, confidence_level=0.95)
    base.update(over); return base


# --------------------------------------------------------- benefit contract ---

def test_primary_endpoint_is_the_pilot_h1_endpoint_and_threshold():
    assert PRIMARY.key == "episode_task_success_rate" and PRIMARY.metric_key == "success"
    assert PRACTICAL_BENEFIT_THRESHOLD == 0.08
    assert PRIMARY.rank == 1 and SEQUENCE[0] is PRIMARY


def test_all_three_scientific_concepts_are_covered():
    concepts = " ".join(e.concept for e in SEQUENCE)
    assert "task progress" in concepts and "liveness" in concepts and "recovery" in concepts


def test_primary_rule_is_strict_at_the_threshold():
    assert primary_passes(R(PRIMARY.key, 0.12, 0.0801, 0.2))
    assert not primary_passes(R(PRIMARY.key, 0.12, 0.08, 0.2))     # equality fails
    assert not primary_passes(R(PRIMARY.key, 0.12, 0.079, 0.2))


def test_fixture_wrong_primary_benefit_endpoint_fails_closed():
    with pytest.raises(BenefitContractError):
        primary_passes(R("goal_reached_rate", 0.5, 0.4, 0.6))
    bad = good_benefit(); bad.pop("episode_task_success_rate")
    bad["some_other_metric"] = R("some_other_metric", 0.9, 0.8, 1.0)
    with pytest.raises(BenefitContractError):
        fixed_sequence_verdicts(bad)


def test_fixture_subjective_alternate_metric_path_fails_closed():
    extra = good_benefit(); extra["form_rms_mean"] = R("form_rms_mean", -1.0, -2.0, -0.5)
    with pytest.raises(BenefitContractError):
        evaluate_closed_loop(benefit_results=extra, safety_verdicts=safety(), **kw())


def test_fixture_swapped_treatment_and_comparator_fails_closed():
    with pytest.raises(BenefitContractError):
        evaluate_closed_loop(benefit_results=good_benefit(), safety_verdicts=safety(),
                             **kw(treatment_arm=COMPARATOR_ARM, comparator_arm=TREATMENT_ARM))


def test_fixture_omitted_and_extra_episode_fail_closed():
    with pytest.raises(UniverseContractError):
        evaluate_closed_loop(benefit_results=good_benefit(), safety_verdicts=safety(),
                             **kw(manifest_episode_ids=IDS[:-1], expected_episode_count=9))
    with pytest.raises(UniverseContractError):
        evaluate_closed_loop(benefit_results=good_benefit(), safety_verdicts=safety(),
                             **kw(observed_event_episode_ids=EV + ["ghost"]))


def test_fixture_changed_benefit_threshold_or_bootstrap_fails_closed():
    for over in ({"bootstrap_seed": 20260821}, {"bootstrap_replicates": 1000},
                 {"confidence_level": 0.90}):
        with pytest.raises(BenefitContractError):
            evaluate_closed_loop(benefit_results=good_benefit(),
                                 safety_verdicts=safety(), **kw(**over))


def test_fixture_wrong_ci_direction_fails_the_endpoint():
    """A decrease-is-better endpoint must not pass on a positive lower bound."""
    bad = good_benefit()
    bad["deadlock_rate"] = R("deadlock_rate", 0.05, 0.02, 0.08)   # deadlock went UP
    verdicts, h1 = fixed_sequence_verdicts(bad)
    assert h1 and not verdicts["deadlock_rate"].passed


def test_fixture_wrong_multiplicity_rule_sequence_stops_at_first_failure():
    bad = good_benefit()
    bad["deadlock_rate"] = R("deadlock_rate", 0.05, 0.02, 0.08)
    verdicts, _ = fixed_sequence_verdicts(bad)
    assert verdicts["deadlock_rate"].tested
    assert not verdicts["irreversible_collapse_rate"].tested
    assert not verdicts["goal_reached_rate"].tested


def test_fixture_safety_result_ignored_fails_closed():
    partial = safety(); partial.pop("ttc_violation_rate")
    with pytest.raises(Exception):
        evaluate_closed_loop(benefit_results=good_benefit(), safety_verdicts=partial, **kw())


def test_fixture_progress_pass_safety_fail_is_never_success():
    v = evaluate_closed_loop(benefit_results=good_benefit(),
                             safety_verdicts=safety(False), **kw())
    assert v.h_cl1_pass and not v.h_cl2_pass
    assert v.central_claim == CLAIM_NOT_SUPPORTED
    assert v.central_claim_detail == "CENTRAL_CLAIM_FAILS_SAFETY_NON_INFERIORITY_NOT_MET"


def test_both_pass_is_the_only_supported_combination():
    assert evaluate_closed_loop(benefit_results=good_benefit(),
                                safety_verdicts=safety(), **kw()).central_claim == CLAIM_SUPPORTED
    sub = good_benefit(); sub[PRIMARY.key] = R(PRIMARY.key, 0.05, 0.02, 0.09)
    assert evaluate_closed_loop(benefit_results=sub, safety_verdicts=safety(),
                                **kw()).central_claim == CLAIM_NOT_SUPPORTED


def test_invalid_episodes_are_imputed_worst_case_and_capped():
    assert impute_invalid(PRIMARY, [1.0, None, 0.0]) == [1.0, 0.0, 0.0]
    dl = SEQUENCE[1]
    assert impute_invalid(dl, [0.0, None]) == [0.0, 1.0]
    with pytest.raises(BenefitContractError):
        evaluate_closed_loop(benefit_results=good_benefit(), safety_verdicts=safety(),
                             **kw(invalid_episode_count=5))
    assert MAXIMUM_INVALID_EPISODE_FRACTION == 0.02


def test_claim_language_is_gated_by_the_primary_rule():
    assert permitted_benefit_language(R(PRIMARY.key, 0.12, 0.09, 0.15)) == (
        "improves", "substantially improves")
    assert permitted_benefit_language(R(PRIMARY.key, 0.05, 0.02, 0.09)) == ()
    assert permitted_benefit_language(R(PRIMARY.key, 0.0, -0.05, 0.05)) == ()


# ------------------------------------------------------------------ oracle ---

def test_oracle_requires_magnitude_direction_and_safety_together():
    ok = R(PRIMARY.key, 0.12, 0.05, 0.19)
    assert oracle_headroom(ok, oracle_safety_passes=True).outcome == ORACLE_HEADROOM_PASS
    assert oracle_headroom(ok, oracle_safety_passes=False).outcome == ORACLE_HEADROOM_FAIL
    assert oracle_headroom(R(PRIMARY.key, 0.03, 0.01, 0.05),
                           oracle_safety_passes=True).outcome == ORACLE_HEADROOM_FAIL
    assert oracle_headroom(R(PRIMARY.key, 0.12, -0.01, 0.25),
                           oracle_safety_passes=True).outcome == ORACLE_HEADROOM_FAIL


def test_fixture_oracle_threshold_changed_is_detectable():
    assert ORACLE_PRACTICAL_THRESHOLD == PRACTICAL_BENEFIT_THRESHOLD == 0.08


def test_oracle_failure_blocks_automatic_progression_to_main_r():
    v = oracle_headroom(R(PRIMARY.key, 0.01, 0.0, 0.02), oracle_safety_passes=True)
    assert v.premise_status == PREMISE_AT_RISK
    assert v.may_proceed_automatically_to_main_r is False


def test_oracle_passes_but_learned_fails_is_a_development_hypothesis():
    v = oracle_headroom(R(PRIMARY.key, 0.12, 0.05, 0.19), oracle_safety_passes=True)
    assert "DEVELOPMENT_HYPOTHESIS" in learned_system_interpretation(v, False)
    assert learned_system_interpretation(v, True) == "ORACLE_AND_LEARNED_BOTH_SHOW_HEADROOM"


def test_oracle_rule_rejects_a_different_endpoint():
    with pytest.raises(BenefitContractError):
        oracle_headroom(R("goal_reached_rate", 0.5, 0.4, 0.6), oracle_safety_passes=True)


# ----------------------------------------------------------------- CL-DEV ---

def cfg(i, delta, **over):
    base = dict(ledger_index=i, registered_before_execution=True, run_completed=True,
                invalid_episode_fraction_acceptable=True, safety_gate_passes=True,
                delta_success_point=delta, delta_success_ci_lower=delta - 0.03,
                deadlock_rate=0.10, irreversible_collapse_rate=0.10,
                minimum_clearance_m=0.50, topology_switches_per_episode=1.0)
    base.update(over); return ConfigurationRecord(**base)


def test_safety_gate_makes_a_better_scoring_configuration_inadmissible():
    ledger = [cfg(0, 0.05), cfg(1, 0.30, safety_gate_passes=False), cfg(2, 0.09)]
    assert select_final_configuration(ledger).ledger_index == 2


def test_fixture_unlogged_configuration_used_as_final_fails_closed():
    with pytest.raises(DevelopmentSelectionError):
        select_final_configuration([cfg(0, 0.1), cfg(1, 0.2, registered_before_execution=False)])


def test_fixture_more_than_forty_configurations_fails_closed():
    assert MAXIMUM_EVALUATED_CONFIGURATIONS == 40
    with pytest.raises(DevelopmentSelectionError):
        select_final_configuration([cfg(i, 0.1) for i in range(41)])


def test_duplicate_ledger_indices_fail_closed():
    with pytest.raises(DevelopmentSelectionError):
        select_final_configuration([cfg(0, 0.1), cfg(0, 0.2)])


def test_incomplete_or_invalid_runs_are_inadmissible():
    assert not is_admissible(cfg(0, 0.5, run_completed=False))
    assert not is_admissible(cfg(0, 0.5, invalid_episode_fraction_acceptable=False))
    assert select_final_configuration([cfg(0, 0.5, run_completed=False)]) == NO_ADMISSIBLE_CONFIGURATION


def test_fixture_wrong_tie_breaker_ordering_is_pinned():
    """Equal primary objective: the more certain, then fewer deadlocks, then earliest."""
    a, b = cfg(0, 0.10, delta_success_ci_lower=0.05), cfg(1, 0.10, delta_success_ci_lower=0.07)
    assert select_final_configuration([a, b]).ledger_index == 1
    c, d = cfg(0, 0.10, deadlock_rate=0.20), cfg(1, 0.10, deadlock_rate=0.05)
    assert select_final_configuration([c, d]).ledger_index == 1
    e, f = cfg(0, 0.10), cfg(1, 0.10)
    assert select_final_configuration([e, f]).ledger_index == 0     # earliest wins


def test_no_admissible_configuration_outcome():
    assert select_final_configuration([cfg(0, 0.5, safety_gate_passes=False)]) == \
        NO_ADMISSIBLE_CONFIGURATION


def test_stopping_rule():
    assert CONSECUTIVE_NON_IMPROVEMENTS_TO_STOP == 3
    assert not should_stop([0.1, 0.2, 0.3])
    assert should_stop([0.5, 0.1, 0.2, 0.3])            # three below the running best
    assert not should_stop([0.1, 0.2, 0.3, 0.4])        # still improving
    assert should_stop([0.1] * MAXIMUM_EVALUATED_CONFIGURATIONS)
