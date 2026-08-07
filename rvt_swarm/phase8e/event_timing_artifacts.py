"""Generate the ET static reachability audit and the machine-readable addendum."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Dict, List, Mapping, Sequence, Tuple

from ..phase8.common import canonical_json_bytes
from ..runtime_configuration import DEFAULT_RUNTIME_CONFIG
from ..topology_registry import COMPACT, LINE
from .event_timing import (
    ADDENDUM_SCHEMA_VERSION, EVENT_CONSTRICTION, EVENT_DIAGNOSTIC, EVENT_OPENING,
    LOCAL_COMPACT_FEASIBLE, LOCAL_EVIDENCE_PREDICATE_VERSION, LOCAL_GEOMETRY_UNKNOWN,
    LOCAL_LINE_REQUIRED, LOCAL_OPENING_FOR_COMPACT, NO_EVENT,
    SAMPLING_SLOTS_FIVE, SAMPLING_SLOTS_FOUR,
    SUPERSEDED_S0_FIELDS, SUPERSEDED_S4_FIELDS,
    build_family_event_plan, extract_landmarks,
)

STATIC_AUDIT_SCHEMA_VERSION = "rvt-event-timing-static-audit/v1"
QUALIFIED_TEAM_SIZES: Tuple[int, ...] = (5, 6, 8, 12, 16, 24)
SUPPORT_DISC_RADIUS_METERS = 0.35


def canonical_sha256(document: object) -> str:
    return hashlib.sha256(canonical_json_bytes(document)).hexdigest()


def _scripted_topologies(policies: Mapping[str, object], family_id: str) -> Tuple[int, ...]:
    """The frozen ordered desired-topology sequence, trigger stripped.

    Only the `(normalized_time, topology)` pairs' *topology* column survives;
    the normalized time is exactly what this addendum supersedes.
    """
    table = dict(policies["policies"]["S0_SCRIPTED_DIAGNOSTIC"]      # type: ignore[index]
                 ["machine_readable_script"])
    return tuple(int(entry[1]) for entry in table.get(family_id, ()))


def build_static_audit(root: Path) -> Dict[str, object]:
    config = DEFAULT_RUNTIME_CONFIG
    sensing = float(config.sensing.obstacle_sensing_range_meters)
    spacing = float(config.formation.nominal_spacing_meters)
    max_speed = float(config.physical.maximum_speed_meters_per_second)
    policies = json.loads((root / "source_policy_contracts_v1.json").read_text())

    records: List[Dict[str, object]] = []
    for split in ("train", "validation"):
        directory = root / "layout_execution_specifications" / split
        for path in sorted(directory.glob("*.json")):
            specification = json.loads(path.read_text())
            source = specification["source_layout"]
            family = str(source["family_id"])
            mission_frame = specification["mission_frame"]
            from .event_timing import project_to_mission
            goal_longitudinal, _ = project_to_mission(
                mission_frame["goal_center_meters"], mission_frame)
            topologies = _scripted_topologies(policies, family)
            landmarks = extract_landmarks(specification, SUPPORT_DISC_RADIUS_METERS)

            per_team: Dict[str, object] = {}
            for team_size in QUALIFIED_TEAM_SIZES:
                events = build_family_event_plan(
                    specification, team_size, topologies,
                    sensing_range_meters=sensing, nominal_spacing_meters=spacing,
                    support_disc_radius_meters=SUPPORT_DISC_RADIUS_METERS,
                    maximum_speed_meters_per_second=max_speed)
                per_team[str(team_size)] = {
                    "declared_event_count": len(topologies),
                    "planned_event_count": len(events),
                    "no_event_family": len(topologies) == 0,
                    "events": [{
                        "ordinal": e.ordinal,
                        "event_type": e.event_type,
                        "candidate_topology": e.candidate_topology,
                        "landmark_id": e.landmark_id,
                        "landmark_longitudinal_meters": e.landmark_longitudinal_meters,
                        "trigger_longitudinal_meters": e.trigger_longitudinal_meters,
                        "trigger_lower_bound_seconds": e.trigger_lower_bound_seconds,
                        "reachable_before_goal": e.reachable_before_goal,
                        "observable_at_initialization": e.observable_at_initialization,
                        "scientific_purpose": e.scientific_purpose,
                    } for e in events],
                    "all_declared_events_reachable": (
                        len(events) == len(topologies)
                        and all(e.reachable_before_goal for e in events)),
                }

            records.append({
                "layout_id": str(source["layout_id"]),
                "family_id": family,
                "split": split,
                "layout_sha256": str(source["geometry_sha256"]),
                "episode_horizon_seconds": float(specification["episode_horizon_seconds"]),
                "mission_distance_meters": goal_longitudinal,
                "minimum_unconstrained_traverse_seconds": goal_longitudinal / max_speed,
                "landmarks": [{
                    "landmark_id": item.landmark_id, "kind": item.kind,
                    "longitudinal_meters": item.longitudinal_meters,
                    "lateral_meters": item.lateral_meters,
                    "support_lateral_meters": item.support_lateral_meters,
                } for item in landmarks],
                "by_team_size": per_team,
            })

    unreachable = [
        {"layout_id": record["layout_id"], "team_size": team_size}
        for record in records
        for team_size, entry in record["by_team_size"].items()          # type: ignore[union-attr]
        if not entry["all_declared_events_reachable"]                    # type: ignore[index]
    ]
    document: Dict[str, object] = {
        "schema_version": STATIC_AUDIT_SCHEMA_VERSION,
        "simulator_steps_executed": 0,
        "specification_only": True,
        "maximum_speed_meters_per_second": max_speed,
        "obstacle_sensing_range_meters": sensing,
        "nominal_spacing_meters": spacing,
        "support_disc_radius_meters": SUPPORT_DISC_RADIUS_METERS,
        "qualified_team_sizes": list(QUALIFIED_TEAM_SIZES),
        "records": records,
        "layouts_audited": len(records),
        "unreachable_declared_events": unreachable,
        "final_test_access_count": 0,
        "study_a_n24_access_count": 0,
    }
    document["event_timing_static_audit_sha256"] = canonical_sha256(document)
    return document


def build_addendum(root: Path, static_audit: Mapping[str, object],
                   source_commit: str) -> Dict[str, object]:
    protocol = json.loads((root / "executable_scientific_protocol_v1.json").read_text())
    policies = json.loads((root / "source_policy_contracts_v1.json").read_text())

    document: Dict[str, object] = {
        "schema_version": ADDENDUM_SCHEMA_VERSION,
        "executable_scientific_protocol_sha256": str(protocol["protocol_hash"]),
        "source_policy_contract_sha256": str(policies["source_policy_contract_sha256"]),
        "phase8_protocol_hash": str(protocol["phase8_protocol_hash"]),
        "frozen_job_manifest_hash": str(protocol["frozen_job_manifest_hash"]),
        "generation_budget_hash": str(protocol["generation_budget_hash"]),
        "source_commit": source_commit,
        "specification_only": True,
        "simulator_steps_executed": 0,
        "frozen_principle": (
            "source-policy transition events are anchored to physical mission state "
            "and local observability, never to a fraction of the episode wall-clock "
            "horizon"),
        "supersedes": {
            "scope": "event origination and timing fields of S0 and S4 only",
            "s0_superseded_fields": list(SUPERSEDED_S0_FIELDS),
            "s4_superseded_fields": list(SUPERSEDED_S4_FIELDS),
            "not_superseded": [
                "event vocabulary", "event order per family",
                "candidate topology per event", "S1", "S2", "S3",
                "hysteresis and rearm semantics", "Target V4",
                "generation budget", "job manifest", "seed mapping",
                "decision-state sampling slots", "episode horizons",
                "mission geometry", "maximum speed", "controller",
                "safety projection", "transition protocol", "readiness",
            ],
            "old_source_policy_contract_rewritten": False,
        },
        "s0_semantics": {
            "role": "offline scripted diagnostic collection policy",
            "old_trigger": "normalized fraction of episode horizon",
            "new_trigger": (
                "deterministic mission landmark: the earliest nominal local "
                "observability of the corresponding physical feature, computed "
                "over the nominal role template with the frozen obstacle sensing "
                "range"),
            "constriction_rule": (
                "landmark longitudinal coordinate minus the approved local "
                "observation extent along the mission direction, evaluated per "
                "template robot"),
            "opening_rule": (
                "forward sector clears past the corresponding feature, under the "
                "already frozen opening and hysteresis semantics"),
            "initialization_case": (
                "if the landmark is observable at episode initialization the event "
                "may occur at the first eligible control step"),
            "may_read_compiled_landmark": True,
            "may_read_headroom_or_outcome": False,
            "directly_sets_topology": False,
            "enters_phase7_protocol": True,
            "absolute_event_seconds_present": False,
        },
        "s4_semantics": {
            "role": "runtime-local evidence-originated event timing",
            "old_trigger": "0.25H and 0.65H episode-horizon fractions",
            "new_trigger": (
                "first eligible control step at which the frozen local geometric "
                "evidence predicate enters LOCAL_LINE_REQUIRED (COMPACT committed) "
                "or LOCAL_OPENING_FOR_COMPACT (LINE committed)"),
            "originator": "whichever robot detects first; it is not a leader",
            "propagation": "neighbour-only through the real leaderless Phase 7 protocol",
            "event_implies_authorization": False,
            "readiness_still_gates_commitment": True,
            "global_geometry_injected": False,
            "future_outcome_used": False,
            "family_id_input": False,
            "headroom_input": False,
            "no_evidence_means_no_transition": True,
            "horizon_fraction_trigger_present": False,
        },
        "local_evidence_predicate": {
            "version": LOCAL_EVIDENCE_PREDICATE_VERSION,
            "shared_by": ["S3_FROZEN_LOCAL_GEOMETRIC_SELECTOR",
                          "S4_FROZEN_TRANSITION_PROTOCOL"],
            "implementation": "rvt_swarm.phase8e.protocol.s3_local_geometric_decision",
            "second_threshold_system_introduced": False,
            "states": {
                "LOCAL_COMPACT_FEASIBLE": LOCAL_COMPACT_FEASIBLE,
                "LOCAL_LINE_REQUIRED": LOCAL_LINE_REQUIRED,
                "LOCAL_OPENING_FOR_COMPACT": LOCAL_OPENING_FOR_COMPACT,
                "LOCAL_GEOMETRY_UNKNOWN": LOCAL_GEOMETRY_UNKNOWN,
            },
            "permitted_inputs": [
                "own robot-local state", "locally observed obstacle primitives",
                "fresh permitted peer information", "committed topology",
                "local mission direction", "frozen topology geometry",
                "frozen physical clearances",
            ],
            "prohibited_inputs": [
                "family id as a runtime feature", "ScenarioLayout object",
                "global corridor width", "passage entry coordinate directly",
                "global obstacle geometry", "headroom category", "future outcome",
            ],
        },
        "event_vocabulary": [EVENT_CONSTRICTION, EVENT_OPENING, EVENT_DIAGNOSTIC],
        "no_event_marker": NO_EVENT,
        "hysteresis_and_rearm_reference": {
            "source": "frozen S3 contract and Phase 7 abort/rearm semantics",
            "commitment_seconds": float(DEFAULT_RUNTIME_CONFIG.protocol.commitment_seconds),
            "evidence_persistence_seconds": float(
                DEFAULT_RUNTIME_CONFIG.protocol.evidence_persistence_seconds),
            "rearm_inactive_seconds": float(
                DEFAULT_RUNTIME_CONFIG.protocol.rearm_inactive_seconds),
            "modified_by_this_addendum": False,
        },
        "event_slot_distinction": {
            "statement": (
                "Phase 9 decision-state slots are DATA SAMPLING TIMES; they are not "
                "source-policy transition event times and were not modified"),
            "five_slot_episodes": list(SAMPLING_SLOTS_FIVE),
            "four_slot_episodes": list(SAMPLING_SLOTS_FOUR),
            "planned_decision_event_slots": 15300,
            "modified_by_this_addendum": False,
        },
        "horizon_semantics": {
            "roles": ["maximum rollout and evaluation duration", "timeout boundary",
                      "scientific denominator context"],
            "prohibited_use": (
                "episode_horizon_fraction may not be the sole detector of a physical "
                "source-policy topology event unless a future contract defines a "
                "purely temporal experiment"),
        },
        "policy_role_distinction": {
            "S0": "offline geometry-scripted diagnostic event timing",
            "S3": "frozen deployable local geometric selector",
            "S4": "runtime-local evidence-originated event timing through the real "
                  "leaderless protocol",
            "aliases": False,
        },
        "static_reachability_audit_sha256": str(
            static_audit["event_timing_static_audit_sha256"]),
        "unreachable_declared_event_count": len(
            list(static_audit["unreachable_declared_events"])),          # type: ignore[arg-type]
        "post_hoc_data_used": False,
        "final_test_access_count": 0,
        "study_a_n24_access_count": 0,
    }
    document["source_event_timing_addendum_sha256"] = canonical_sha256(document)
    return document


def write_event_timing_artifacts(root: Path, source_commit: str) -> Dict[str, object]:
    audit = build_static_audit(root)
    (root / "event_timing_static_audit_v1.json").write_text(
        json.dumps(audit, indent=1, sort_keys=True) + "\n")
    addendum = build_addendum(root, audit, source_commit)
    (root / "source_event_timing_addendum_v1.json").write_text(
        json.dumps(addendum, indent=1, sort_keys=True) + "\n")
    return {"static_audit": audit, "addendum": addendum}
