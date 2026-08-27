"""Qualification for RVT_CLEANROOM_GENERATOR_V1.

Covers the CR-0V and CR-0W negative fixtures. Every one must fail closed.
"""
from __future__ import annotations

import ast
import pathlib
import pytest

from rvt_swarm.cleanroom.composition import FAMILIES, SOURCE_POLICIES, TEAM_SIZES
from rvt_swarm.cleanroom.generation.budget import (
    BudgetAuthorityError, assert_matches_budget, budget, total_source_episodes,
)
from rvt_swarm.cleanroom.generation.callplan import (
    REQUIRED_FIELDS, CallPlanError, call_arguments, validate_all,
)
from rvt_swarm.cleanroom.generation.identity import IdentityError, make_identity
from rvt_swarm.cleanroom.generation.layouts import (
    LayoutAuthorityError, resolve_layout, role_layouts, assert_layouts_disjoint_across_roles,
)
from rvt_swarm.cleanroom.generation.ledger import enumerate_role, role_roots
from rvt_swarm.cleanroom.generation.roles import (
    CLEAN_ROOM_STUDY, ROLES, RoleAuthorityError, assert_disjoint_from_history, authorize, role,
)
from rvt_swarm.cleanroom.generation.seeds import (
    DECORATIVE_V4_ROLE_SEEDS, SeedAuthorityError, refuse_master_seed, source_episode_seeds,
)
from rvt_swarm.phase9b.identity import SourceEpisodeIdentity
from rvt_swarm.phase9c.manifest import _source_seeds


# ------------------------------------------------------- role authority ---

def test_six_roles_with_disjoint_clean_room_vocabulary():
    assert len(ROLES) == 6
    assert_disjoint_from_history()
    assert CLEAN_ROOM_STUDY == "rvt_cleanroom_final_v1"


@pytest.mark.parametrize("study,split,dataset", [
    ("study_a_zero_shot", "train", "study_a_train"),
    ("study_b_with_n24", "validation", "study_b_validation"),
    ("study_a_zero_shot", "train_r", "cleanroom_train_r"),
    ("rvt_cleanroom_final_v1", "train", "cleanroom_train_r"),
])
def test_fixture_pilot_identity_refused(study, split, dataset):
    with pytest.raises(RoleAuthorityError):
        authorize(study, split, dataset)


def test_fixture_unknown_role_and_role_split_mismatch_fail_closed():
    with pytest.raises(RoleAuthorityError):
        role("TRAIN")
    with pytest.raises(RoleAuthorityError):
        authorize(CLEAN_ROOM_STUDY, "train_r", "cleanroom_main_r")
    with pytest.raises(RoleAuthorityError):
        authorize(CLEAN_ROOM_STUDY, "not_a_split", "cleanroom_train_r")


# ------------------------------------------------------------- budget ---

def test_budget_consumes_v4_exactly():
    expected = {"TRAIN-R": (4, 1200, 0.00), "SELECT-R": (1, 300, 0.11),
                "CL-DEV-R": (1, 300, 0.44), "MAIN-R": (3, 900, 0.55),
                "MECH-R": (3, 900, 0.66), "PROTECTED-R": (2, 600, 0.79)}
    for name, (per, total, off) in expected.items():
        b = budget(name)
        assert (b.episodes_per_cell, b.expected_source_episode_count, b.offset) == (per, total, off)
        assert b.families == tuple(FAMILIES) and b.team_sizes == tuple(TEAM_SIZES)
        assert b.source_policies == tuple(SOURCE_POLICIES)
        assert b.k_max_selected_source_events_per_episode == 5
    assert total_source_episodes() == 4200


@pytest.mark.parametrize("field,bad", [
    ("episodes_per_cell", 5), ("expected_source_episode_count", 1201),
    ("offset", 0.22), ("k", 4),
])
def test_fixture_runtime_value_differing_from_budget_fails_closed(field, bad):
    b = budget("TRAIN-R")
    kw = dict(episodes_per_cell=b.episodes_per_cell,
              expected_source_episode_count=b.expected_source_episode_count,
              families=b.families, team_sizes=b.team_sizes,
              source_policies=b.source_policies, offset=b.offset,
              k=b.k_max_selected_source_events_per_episode)
    kw[field] = bad
    with pytest.raises(BudgetAuthorityError):
        assert_matches_budget("TRAIN-R", **kw)


def test_fixture_changed_family_set_or_n_schedule_fails_closed():
    b = budget("TRAIN-R")
    base = dict(episodes_per_cell=b.episodes_per_cell,
                expected_source_episode_count=b.expected_source_episode_count,
                families=b.families, team_sizes=b.team_sizes,
                source_policies=b.source_policies, offset=b.offset,
                k=b.k_max_selected_source_events_per_episode)
    for field, bad in (("families", tuple(FAMILIES[:9])),
                       ("team_sizes", (5, 6, 8, 12)),
                       ("source_policies", tuple(SOURCE_POLICIES[:5]))):
        kw = dict(base); kw[field] = bad
        with pytest.raises(BudgetAuthorityError):
            assert_matches_budget("TRAIN-R", **kw)


# ------------------------------------------------------------ identity ---

def test_fixture_bad_identity_fields_fail_closed():
    lay = resolve_layout("TRAIN-R", "F1")
    ok = dict(role_name="TRAIN-R", family="F1", team_size=5,
              source_policy="S0_SCRIPTED_DIAGNOSTIC", episode_index=0,
              layout_id=lay.layout_id, layout_sha256=lay.layout_sha256)
    make_identity(**ok)
    for field, bad in (("family", "F99"), ("team_size", 24),
                       ("source_policy", "S9_UNKNOWN"), ("episode_index", 4),
                       ("layout_sha256", "nothex")):
        kw = dict(ok); kw[field] = bad
        with pytest.raises(IdentityError):
            make_identity(**kw)


# ------------------------------------------------------------- layouts ---

def test_each_role_resolves_ten_distinct_layouts():
    for name in ROLES:
        items = role_layouts(name)
        assert len(items) == 10
        assert len({i.layout_sha256 for i in items}) == 10
        assert {i.family_id for i in items} == set(FAMILIES)
    assert_layouts_disjoint_across_roles()


def test_fixture_pilot_reserve_and_forbidden_offsets_refused():
    """No clean-room role may resolve onto a historical or forbidden offset."""
    used = {resolve_layout(n, "F1").offset for n in ROLES}
    assert not (used & {0.22, 0.54, 0.65})   # historical V3
    assert not (used & {0.33})               # untouched reserve
    assert not (used & {0.76, 0.77, 0.87})   # forbidden band


def test_fixture_unknown_family_layout_fails_closed():
    with pytest.raises(LayoutAuthorityError):
        resolve_layout("TRAIN-R", "F42")


# --------------------------------------------------------------- seeds ---

def test_fixture_decorative_v4_master_seed_refused():
    assert 3650100380 in DECORATIVE_V4_ROLE_SEEDS
    for value in DECORATIVE_V4_ROLE_SEEDS:
        with pytest.raises(SeedAuthorityError):
            refuse_master_seed(value)
    refuse_master_seed(12345)          # an unrelated int is not a master seed


def test_seed_adapter_equals_the_frozen_builder_on_a_broad_grid():
    """The clean-room adapter must equal frozen _source_seeds bit-for-bit."""
    checked = 0
    for name in ROLES:
        lay = {i.family_id: i for i in role_layouts(name)}
        per = budget(name).episodes_per_cell
        for family in ("F1", "F8", "F9", "F10"):
            for team_size in TEAM_SIZES:
                for policy in (SOURCE_POLICIES[0], SOURCE_POLICIES[-1]):
                    ident = make_identity(name, family, team_size, policy, per - 1,
                                          lay[family].layout_id, lay[family].layout_sha256)
                    frozen = _source_seeds(SourceEpisodeIdentity(
                        cell=ident.cell, source_class=ident.source_class,
                        episode_index=ident.episode_index))
                    assert dict(source_episode_seeds(ident)) == frozen
                    checked += 1
    assert checked == 6 * 4 * 5 * 2


def test_seeds_change_with_every_identity_field():
    lay = resolve_layout("TRAIN-R", "F1")
    base = make_identity("TRAIN-R", "F1", 5, "S0_SCRIPTED_DIAGNOSTIC", 0,
                         lay.layout_id, lay.layout_sha256)
    b = dict(source_episode_seeds(base))
    other_role = resolve_layout("MAIN-R", "F1")
    variants = [
        make_identity("MAIN-R", "F1", 5, "S0_SCRIPTED_DIAGNOSTIC", 0,
                      other_role.layout_id, other_role.layout_sha256),
        make_identity("TRAIN-R", "F2", 5, "S0_SCRIPTED_DIAGNOSTIC", 0,
                      *[getattr(resolve_layout("TRAIN-R", "F2"), a)
                        for a in ("layout_id", "layout_sha256")]),
        make_identity("TRAIN-R", "F1", 16, "S0_SCRIPTED_DIAGNOSTIC", 0,
                      lay.layout_id, lay.layout_sha256),
        make_identity("TRAIN-R", "F1", 5, "S5_BOUNDED_PERTURBATION", 0,
                      lay.layout_id, lay.layout_sha256),
        make_identity("TRAIN-R", "F1", 5, "S0_SCRIPTED_DIAGNOSTIC", 3,
                      lay.layout_id, lay.layout_sha256),
    ]
    for v in variants:
        assert dict(source_episode_seeds(v)) != b


# ----------------------------------------------------------- call plan ---

def test_call_plan_targets_the_frozen_consumer_with_no_free_arguments():
    lay = resolve_layout("TRAIN-R", "F1")
    ident = make_identity("TRAIN-R", "F1", 5, "S0_SCRIPTED_DIAGNOSTIC", 0,
                          lay.layout_id, lay.layout_sha256)
    args = call_arguments(ident)
    assert set(args) == set(REQUIRED_FIELDS)


def test_full_call_plan_validates():
    r = validate_all()
    assert r["calls"] == 4200
    assert r["unknown_arguments"] == 0 and r["missing_required_arguments"] == 0


# ------------------------------------------- non-duplication of science ---

def test_fixture_generation_layer_implements_no_scientific_formula():
    """No local hashing or RNG: the scientific core must be called, not copied."""
    for p in sorted(pathlib.Path("rvt_swarm/cleanroom/generation").glob("*.py")):
        tree = ast.parse(p.read_text())
        imported = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                imported |= {a.name for a in n.names}
            elif isinstance(n, ast.ImportFrom):
                imported.add(n.module or "")
        assert not any(m == "hashlib" or m.startswith("random") for m in imported), p.name
        for n in ast.walk(tree):
            if isinstance(n, ast.Attribute):
                assert n.attr not in ("sha256", "md5", "default_rng"), p.name


# ------------------------------------------------ enumeration integrity ---

def test_role_enumeration_matches_the_frozen_budget():
    for name in ROLES:
        r = role_roots(name)
        assert r["expected_source_episode_count"] == budget(name).expected_source_episode_count
        assert r["distinct_seed_values"] == r["total_seed_values"]


def test_no_duplicate_identity_within_or_across_roles():
    seen = set()
    for name in ROLES:
        ids = [i.source_episode_id() for i in enumerate_role(name)]
        assert len(set(ids)) == len(ids)
        assert not (seen & set(ids))
        seen |= set(ids)
    assert len(seen) == 4200
