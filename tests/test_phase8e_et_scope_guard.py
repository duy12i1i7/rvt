"""ET-15 / ET-G8 / ET-G9 -- the addendum changed nothing it was forbidden to change."""

from __future__ import annotations

import hashlib
import json
import pathlib

import pytest

from rvt_swarm.runtime_configuration import DEFAULT_RUNTIME_CONFIG as CONFIG

ROOT = pathlib.Path("results/rvt_fd24")
ADDENDUM = json.loads((ROOT / "source_event_timing_addendum_v1.json").read_text())

# File hashes recorded at the audited protocol commit 554d44b.
FROZEN_FILE_SHA256 = {
    "executable_scientific_protocol_v1.json":
        "342ae8b901315df2d178d7c8a0d2bdbfa8a659c99cfae1774d6d4211519ce770",
    "source_policy_contracts_v1.json":
        "c80f2a8d1fb608c27f5ec8d68d40eb88563a98e944cf84f8fc0d983086f8a8c5",
    "target_v4_execution_contract_v1.json":
        "a3abf73330314fdf332b0e9d69657dd1e9e1cae8a6ba53c83320186d8a2eb23c",
    "datasets/generation_budget_v1.json":
        "e12e42052fd48a6647b4b7fdac77db3a20340d550617ff196fb40b7541da5492",
    "datasets/dataset_generation_protocol_v1.json":
        "06284aae2a58fbc1b670bfa261ef40cdebb7c5cc46a1c24d13ef940272730a68",
    "datasets/phase9_job_manifest.json":
        "9d094d7dca34e2daf8edc05c018d0372d7c4d2219a710032a6b066be494ea49f",
}


@pytest.mark.parametrize("relative,expected", sorted(FROZEN_FILE_SHA256.items()))
def test_frozen_artifacts_are_byte_identical(relative: str, expected: str) -> None:
    digest = hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
    assert digest == expected, relative


def test_the_old_source_policy_contract_was_not_rewritten() -> None:
    assert ADDENDUM["supersedes"]["old_source_policy_contract_rewritten"] is False


def test_addendum_scope_is_limited_to_s0_and_s4_event_origination() -> None:
    scope = ADDENDUM["supersedes"]["scope"].lower()
    assert "s0" in scope and "s4" in scope
    not_superseded = ADDENDUM["supersedes"]["not_superseded"]
    for item in ("Target V4", "generation budget", "job manifest", "seed mapping",
                 "episode horizons", "mission geometry", "maximum speed", "controller",
                 "safety projection", "transition protocol", "readiness", "S1", "S2", "S3"):
        assert item in not_superseded, item


def test_physical_constants_are_unchanged() -> None:
    assert float(CONFIG.physical.maximum_speed_meters_per_second) == 0.9
    assert float(CONFIG.physical.maximum_acceleration_meters_per_second_squared) == 0.6
    assert float(CONFIG.physical.robot_radius_meters) == 0.18
    assert float(CONFIG.physical.control_period_seconds) == 0.15
    assert float(CONFIG.sensing.obstacle_sensing_range_meters) == 3.0
    assert float(CONFIG.formation.nominal_spacing_meters) == 0.9
    assert float(CONFIG.derived.formation_tolerance_meters) == 0.55


def test_mission_geometry_and_horizons_are_unchanged() -> None:
    """Start, goal and horizon are read back from the untouched compiled records."""
    expected_horizons = {"F1": 90.0, "F2": 120.0, "F3": 135.0, "F4": 150.0, "F5": 180.0,
                         "F6": 130.0, "F7": 110.0, "F8": 180.0, "F9": 150.0, "F10": 90.0}
    seen = set()
    for split in ("train", "validation"):
        for path in sorted((ROOT / "layout_execution_specifications" / split).glob("*.json")):
            record = json.loads(path.read_text())
            family = record["source_layout"]["family_id"]
            seen.add(family)
            assert record["episode_horizon_seconds"] == expected_horizons[family]
            origin = record["mission_frame"]["initial_topology_origin_meters"]
            goal = record["mission_frame"]["goal_center_meters"]
            assert origin[0] == pytest.approx(-6.0, abs=1e-6)
            assert goal[0] == pytest.approx(6.0, abs=1e-6)
    assert seen == set(expected_horizons)


#: Phase 9G-V3X-Q added thirty ADDITIVE V3 execution specifications into
#: the same directories. Narrowing to the V2-era layout set -- defined by
#: the frozen split manifests -- keeps this assertion at its original
#: force over the historical layouts instead of loosening it.
def _v2_era_layout_ids(split):
    manifest = json.loads(
        (ROOT / "splits" / f"{split}_layouts.json").read_text(encoding="ascii"))
    return {str(record["layout_id"]) for record in manifest["layout_records"]}


def test_train_validation_membership_is_unchanged() -> None:
    counts = {
        split: len([path for path in
                    (ROOT / "layout_execution_specifications" / split).glob("*.json")
                    if path.stem in _v2_era_layout_ids(split)])
        for split in ("train", "validation")}
    assert counts == {"train": 20, "validation": 10}


def test_final_test_geometry_is_not_present_and_not_accessed() -> None:
    assert not (ROOT / "layout_execution_specifications" / "final_test").exists()
    assert ADDENDUM["final_test_access_count"] == 0
    protocol = json.loads((ROOT / "executable_scientific_protocol_v1.json").read_text())
    assert protocol["final_test_access_policy"]["runtime_access_count"] == 0


def test_study_a_n24_seal_is_intact() -> None:
    assert ADDENDUM["study_a_n24_access_count"] == 0
    manifest = json.loads((ROOT / "datasets" / "phase9_job_manifest.json").read_text())
    assert manifest["study_a_n24_policy"]["sealed"] is True
    assert manifest["study_a_n24_policy"]["phase9_record_access_count"] == 0


def test_no_execution_occurred_during_this_addendum() -> None:
    assert ADDENDUM["simulator_steps_executed"] == 0
    assert ADDENDUM["specification_only"] is True
    assert ADDENDUM["post_hoc_data_used"] is False
    assert list(ROOT.glob("**/*.pt")) == []
    assert list((ROOT / "datasets").glob("*shard*")) == []


def test_s0_s3_s4_remain_scientifically_distinct() -> None:
    distinction = ADDENDUM["policy_role_distinction"]
    assert distinction["aliases"] is False
    assert distinction["S0"] != distinction["S4"] != distinction["S3"]
    assert "offline" in distinction["S0"]
    assert "local evidence" in distinction["S4"] or "evidence-originated" in distinction["S4"]


def test_addendum_hash_is_reproducible() -> None:
    from rvt_swarm.phase8e.event_timing_artifacts import canonical_sha256
    document = {k: v for k, v in ADDENDUM.items()
                if k != "source_event_timing_addendum_sha256"}
    assert canonical_sha256(document) == ADDENDUM["source_event_timing_addendum_sha256"]


def test_static_audit_hash_is_reproducible_and_referenced() -> None:
    from rvt_swarm.phase8e.event_timing_artifacts import canonical_sha256
    audit = json.loads((ROOT / "event_timing_static_audit_v1.json").read_text())
    document = {k: v for k, v in audit.items()
                if k != "event_timing_static_audit_sha256"}
    assert canonical_sha256(document) == audit["event_timing_static_audit_sha256"]
    assert ADDENDUM["static_reachability_audit_sha256"] == audit["event_timing_static_audit_sha256"]
