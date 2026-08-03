from rvt_swarm.phase8.scenario import (
    BOTH_FAIL,
    BOTH_SUCCESS,
    COMPACT_ONLY_SUCCESS,
    LINE_ONLY_SUCCESS,
    RECONFIGURATION_REQUIRED,
    SCENARIO_FAMILIES,
    SCENARIO_FAMILY_SCHEMA_VERSION,
    SUPPORTED_TEAM_SIZES,
    scenario_family_manifest,
)
from rvt_swarm.topology_registry import COMPACT


def test_all_ten_required_scenario_families_are_versioned_and_complete():
    assert tuple(item.family_id for item in SCENARIO_FAMILIES) == tuple(
        f"F{index}" for index in range(1, 11)
    )
    assert all(item.schema_version == SCENARIO_FAMILY_SCHEMA_VERSION for item in SCENARIO_FAMILIES)
    assert all(item.initial_topology_id == COMPACT for item in SCENARIO_FAMILIES)
    assert all(item.team_sizes == SUPPORTED_TEAM_SIZES for item in SCENARIO_FAMILIES)
    assert all(item.validity_checks and item.exclusion_rules and item.diagnostic_policies for item in SCENARIO_FAMILIES)


def test_family_set_contains_decisive_neutral_reconfiguration_and_failure_headroom():
    categories = {
        category
        for family in SCENARIO_FAMILIES
        for category in family.expected_headroom_categories
    }
    assert {
        COMPACT_ONLY_SUCCESS,
        LINE_ONLY_SUCCESS,
        BOTH_SUCCESS,
        BOTH_FAIL,
        RECONFIGURATION_REQUIRED,
    } <= categories


def test_scenario_family_manifest_is_explicit_and_hashed():
    manifest = scenario_family_manifest()
    assert manifest["family_count"] == 10
    assert len(manifest["scenario_family_sha256"]) == 64
    assert len(manifest["families"]) == 10
