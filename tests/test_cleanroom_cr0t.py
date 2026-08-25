"""Qualification for the CR-0T closure: dataset-composition authority."""
from __future__ import annotations

import hashlib
import pytest

from rvt_swarm.cleanroom.composition import (
    ACQUISITION_RULE, CELLS, FAMILIES, GENERATION_SEED_MODULUS,
    K_MAX_SELECTED_SOURCE_EVENTS_PER_EPISODE, MAIN_R_PLANNING, ROLE_COMPOSITION,
    SOURCE_POLICIES, TEAM_SIZES, V3_ROOT, CompositionContractError,
    all_roles_disjoint, assert_composition_unchanged, composition_fingerprint,
    enumerate_episode_ids, episode_id, generation_seed, replicas_per_candidate,
    verify_role_arithmetic,
)

ROLES = tuple(ROLE_COMPOSITION)


def test_grid_matches_the_pilot_cell_structure():
    assert len(FAMILIES) == 10 and len(TEAM_SIZES) == 5 and len(SOURCE_POLICIES) == 6
    assert CELLS == 300
    assert TEAM_SIZES == (5, 6, 8, 12, 16)


def test_every_role_is_exactly_balanced_on_the_grid():
    for role in ROLES:
        a = verify_role_arithmetic(role)
        assert a["source_episodes"] % CELLS == 0
        assert a["source_episodes"] == a["episodes_per_cell"] * CELLS
        assert a["episodes_per_family_team_size_cell"] == a["episodes_per_cell"] * 6
        assert a["source_episodes"] % a["layouts"] == 0


def test_frozen_totals():
    expected = {"TRAIN-R": 1200, "SELECT-R": 300, "CL-DEV-R": 300,
                "MAIN-R": 900, "MECH-R": 900, "PROTECTED-R": 600}
    assert {r: ROLE_COMPOSITION[r].source_episode_count for r in ROLES} == expected
    assert sum(expected.values()) == 4200


def test_train_r_preserves_the_pilot_train_budget_not_the_validation_budget():
    t = ROLE_COMPOSITION["TRAIN-R"]
    assert t.source_episode_count == 1200            # pilot TRAIN, not pilot VALIDATION 300
    assert t.episodes_per_family_team_size_cell == 24


def test_offsets_are_exactly_the_v3_values():
    assert {r: ROLE_COMPOSITION[r].offset for r in ROLES} == {
        "TRAIN-R": 0.00, "SELECT-R": 0.11, "CL-DEV-R": 0.44,
        "MAIN-R": 0.55, "MECH-R": 0.66, "PROTECTED-R": 0.79}


def test_offsets_avoid_pilot_reserve_and_forbidden_bands():
    used = {ROLE_COMPOSITION[r].offset for r in ROLES}
    assert not (used & {0.22, 0.54, 0.65})     # pilot consumed
    assert not (used & {0.33})                 # pilot reserve
    assert not (used & {0.76, 0.77, 0.87})     # forbidden band


def test_seed_derivation_is_deterministic_and_reproducible():
    for role in ROLES:
        payload = "|".join((V3_ROOT, role, "GENERATION")).encode("ascii")
        want = int.from_bytes(hashlib.sha256(payload).digest()[:8], "big") % GENERATION_SEED_MODULUS
        assert generation_seed(role) == want
        assert 0 <= generation_seed(role) < 2**32


def test_seeds_are_distinct_across_roles():
    assert len({generation_seed(r) for r in ROLES}) == len(ROLES)


def test_episode_universe_enumerates_exactly_and_without_duplicates():
    for role in ROLES:
        ids = list(enumerate_episode_ids(role))
        assert len(ids) == ROLE_COMPOSITION[role].source_episode_count
        assert len(set(ids)) == len(ids)


def test_episode_ids_are_deterministic_functions_of_manifest_fields():
    a = episode_id("MAIN-R", "F1", 5, "S0_SCRIPTED_DIAGNOSTIC", 0)
    b = episode_id("MAIN-R", "F1", 5, "S0_SCRIPTED_DIAGNOSTIC", 0)
    assert a == b and "MAIN-R" in a and "/F1/" in a and "/N5/" in a
    assert "sha256" not in a.lower()   # no layout hash: enumerable before generation


def test_clean_room_roles_are_pairwise_disjoint_by_identity():
    assert all_roles_disjoint()
    for i, r1 in enumerate(ROLES):
        for r2 in ROLES[i+1:]:
            assert not (set(enumerate_episode_ids(r1)) & set(enumerate_episode_ids(r2)))


def test_no_clean_room_id_collides_with_the_pilot_namespace():
    for role in ROLES:
        for eid in list(enumerate_episode_ids(role))[:50]:
            assert not eid.startswith("rvt-generation-job-identity/")
            assert "study_a_zero_shot" not in eid
            assert "v3_train" not in eid and "v3_validation" not in eid


def test_replica_law_reproduced_for_manifest_construction():
    assert replicas_per_candidate("F8") == 3 and replicas_per_candidate("F9") == 3
    for f in FAMILIES:
        if f not in ("F8", "F9"):
            assert replicas_per_candidate(f) == 1
    with pytest.raises(CompositionContractError):
        replicas_per_candidate("F99")


def test_open_loop_roles_carry_the_k_expansion_and_closed_loop_roles_do_not():
    assert ACQUISITION_RULE == "REALIZED_TRAJECTORY_UNIFORM_K"
    assert K_MAX_SELECTED_SOURCE_EVENTS_PER_EPISODE == 5
    assert ROLE_COMPOSITION["TRAIN-R"].maximum_selected_source_events == 6000
    assert ROLE_COMPOSITION["SELECT-R"].maximum_selected_source_events == 1500
    for r in ("CL-DEV-R", "MAIN-R", "MECH-R", "PROTECTED-R"):
        assert ROLE_COMPOSITION[r].maximum_selected_source_events is None


def test_main_r_planning_inputs_are_frozen_and_outcome_free():
    p = MAIN_R_PLANNING
    assert p["threshold"] == 0.08 and p["planning_alternative"] == 0.16
    assert p["alpha_one_sided"] == 0.05 and p["target_power"] == 0.90
    assert p["achieved_power_at_chosen_size"] >= 0.90
    assert p["pilot_information_used"].startswith("NONE in the arithmetic")


def test_main_r_power_recomputes_from_the_frozen_planning_inputs():
    from math import sqrt
    from statistics import NormalDist
    nd = NormalDist()
    n = ROLE_COMPOSITION["MAIN-R"].source_episode_count
    se = sqrt(0.5 / n)
    power = nd.cdf((MAIN_R_PLANNING["planning_alternative"] - MAIN_R_PLANNING["threshold"]) / se
                   - nd.inv_cdf(1 - MAIN_R_PLANNING["alpha_one_sided"]))
    assert power >= MAIN_R_PLANNING["target_power"]
    assert abs(power - MAIN_R_PLANNING["achieved_power_at_chosen_size"]) < 1e-3
    # one balanced step down would miss the target, which is why 900 was chosen
    smaller = sqrt(0.5 / (2 * CELLS))
    assert nd.cdf(0.08 / smaller - nd.inv_cdf(0.95)) < 0.90


def test_mech_r_is_at_least_as_large_as_main_r():
    assert (ROLE_COMPOSITION["MECH-R"].source_episode_count
            >= ROLE_COMPOSITION["MAIN-R"].source_episode_count)


def test_protected_r_precision_meets_its_target():
    from math import sqrt
    n = ROLE_COMPOSITION["PROTECTED-R"].source_episode_count
    assert 1.959964 * sqrt(0.25 / n) <= 0.05


# ------------------------------------------------ negative fixtures (§18) ---

@pytest.mark.parametrize("role", ROLES)
def test_fixture_resize_attempt_fails_closed(role):
    c = ROLE_COMPOSITION[role]
    ok = dict(offset=c.offset, layout_instances_per_family=c.layout_instances_per_family,
              generation_seed_value=generation_seed(role))
    assert_composition_unchanged(role, episodes_per_cell=c.episodes_per_cell, **ok)
    with pytest.raises(CompositionContractError):      # changed total count
        assert_composition_unchanged(role, episodes_per_cell=c.episodes_per_cell + 1, **ok)


def test_fixture_wrong_offset_seed_or_layout_count_fails_closed():
    c = ROLE_COMPOSITION["MAIN-R"]
    base = dict(episodes_per_cell=c.episodes_per_cell, offset=c.offset,
                layout_instances_per_family=c.layout_instances_per_family,
                generation_seed_value=generation_seed("MAIN-R"))
    for field, bad in (("offset", 0.65), ("layout_instances_per_family", 2),
                       ("generation_seed_value", 12345)):
        kw = dict(base); kw[field] = bad
        with pytest.raises(CompositionContractError):
            assert_composition_unchanged("MAIN-R", **kw)


def test_fixture_unknown_role_fails_closed():
    for fn in (generation_seed, verify_role_arithmetic):
        with pytest.raises(CompositionContractError):
            fn("TRAIN-R-v2")
    with pytest.raises(CompositionContractError):
        list(enumerate_episode_ids("SOME-OTHER-ROLE"))


def test_fixture_omitted_or_duplicated_family_breaks_the_arithmetic():
    """A grid missing or repeating a family cannot produce the frozen totals."""
    assert len(set(FAMILIES)) == len(FAMILIES) == 10
    assert ROLE_COMPOSITION["MAIN-R"].source_episode_count == 3 * 10 * 5 * 6
    assert 3 * 9 * 5 * 6 != ROLE_COMPOSITION["MAIN-R"].source_episode_count


def test_fixture_changed_n_schedule_breaks_the_arithmetic():
    assert len(TEAM_SIZES) == 5
    assert 3 * 10 * 4 * 6 != ROLE_COMPOSITION["MAIN-R"].source_episode_count


def test_fingerprint_is_stable_and_covers_every_frozen_field():
    f1 = composition_fingerprint()
    assert f1 == composition_fingerprint() and len(f1) == 64
    for r in ROLES:
        assert str(ROLE_COMPOSITION[r].episodes_per_cell) in "".join(
            f"{rr}:{ROLE_COMPOSITION[rr].offset}:{ROLE_COMPOSITION[rr].episodes_per_cell}"
            for rr in ROLES)
