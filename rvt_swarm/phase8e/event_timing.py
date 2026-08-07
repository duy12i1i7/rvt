"""Phase 8E-PC-ET -- source event-timing addendum (specification only).

Frozen principle
----------------
    SOURCE-POLICY TRANSITION EVENTS MUST BE ANCHORED TO PHYSICAL MISSION STATE
    AND LOCAL OBSERVABILITY, NOT TO A FRACTION OF THE EPISODE WALL-CLOCK
    HORIZON.

The episode horizon remains a timeout and an evaluation bound. It no longer
determines when a locally meaningful topology event occurs.

Why this addendum exists
------------------------
Every one of the 30 layouts is a 12.01 m mission at a frozen 0.9 m/s, so an
ideal traversal takes at least 13.34 s. The superseded S0 table scheduled its
earliest event at 0.20-0.50 of a 90-180 s horizon (24.0 s in F2, 65.0 s in F6,
49.5 s in F9) and S4 fired at 0.25H (22.5-45 s). Every one of those instants
lies after the mission can physically end, so S0 and S4 degenerate to a
COMPACT hold and cannot perform their frozen role as transition-state source
policies. This module replaces the *trigger* of those events. It does not
change their scientific meaning, their order, their event vocabulary, or any
physical constant.

Nothing here reads a label, a headroom category, a candidate outcome, a
trajectory result or a dataset distribution. Reachability is decided from
frozen geometry alone.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

from ..topology_registry import COMPACT, LINE, construct_topology_from_spacing

ADDENDUM_SCHEMA_VERSION = "rvt-source-event-timing-addendum/v1"
LOCAL_EVIDENCE_PREDICATE_VERSION = "rvt-local-geometric-event-evidence/v1"

# Frozen Phase 7 event vocabulary. No new scientific event category is invented.
EVENT_CONSTRICTION = "local_constriction"
EVENT_OPENING = "local_opening"
EVENT_DIAGNOSTIC = "externally_forced_diagnostic"

# Frozen local evidence states, shared by S3 and S4 (ET-4). These are names for
# the return values of the already-approved `s3_local_geometric_decision`; no
# second threshold system is introduced.
LOCAL_COMPACT_FEASIBLE = "HOLD_COMPACT"
LOCAL_LINE_REQUIRED = "REQUEST_LINE"
LOCAL_OPENING_FOR_COMPACT = "REQUEST_COMPACT"
LOCAL_GEOMETRY_UNKNOWN = "HOLD_UNKNOWN"

NO_EVENT = "NO_EVENT"

# Superseded fields, named exactly so the addendum's scope is auditable.
SUPERSEDED_S0_FIELDS: Tuple[str, ...] = (
    "policies.S0_SCRIPTED_DIAGNOSTIC.machine_readable_script",
    "policies.S0_SCRIPTED_DIAGNOSTIC.event_rule",
)
SUPERSEDED_S4_FIELDS: Tuple[str, ...] = (
    "policies.S4_FROZEN_TRANSITION_PROTOCOL.event_schedule_normalized_horizon",
    "policies.S4_FROZEN_TRANSITION_PROTOCOL.event_rule",
)

# Phase 9 decision-state SAMPLING slots. These are data-sampling times and are
# NOT source-policy event times (ET-8). They are reproduced here only so a
# reader cannot confuse the two; they are not modified by this addendum.
SAMPLING_SLOTS_FIVE: Tuple[float, ...] = (0.10, 0.30, 0.50, 0.70, 0.90)
SAMPLING_SLOTS_FOUR: Tuple[float, ...] = (0.15, 0.40, 0.65, 0.90)


@dataclass(frozen=True)
class MissionLandmark:
    """One deterministic landmark taken from already-compiled geometry."""

    landmark_id: str
    kind: str                       # passage_entry | passage_exit | circle | dynamic_circle
    longitudinal_meters: float      # along the mission axis, from the topology origin
    lateral_meters: float
    support_lateral_meters: float   # lateral offset of the nearest observable token
    primitive_index: int


@dataclass(frozen=True)
class SourceEvent:
    """One scheduled scientific event, anchored to a landmark rather than a clock."""

    ordinal: int
    event_type: str                 # frozen vocabulary
    candidate_topology: int
    landmark_id: str
    landmark_longitudinal_meters: float
    trigger_longitudinal_meters: Optional[float]
    trigger_lower_bound_seconds: Optional[float]
    reachable_before_goal: bool
    observable_at_initialization: bool
    scientific_purpose: str


def mission_axes(mission_frame: Mapping[str, object]) -> Tuple[Tuple[float, float],
                                                               Tuple[float, float],
                                                               Tuple[float, float]]:
    origin = mission_frame["initial_topology_origin_meters"]        # type: ignore[index]
    longitudinal = mission_frame["longitudinal_axis"]               # type: ignore[index]
    lateral = mission_frame["lateral_axis"]                         # type: ignore[index]
    return ((float(origin[0]), float(origin[1])),
            (float(longitudinal[0]), float(longitudinal[1])),
            (float(lateral[0]), float(lateral[1])))


def project_to_mission(point: Sequence[float], mission_frame: Mapping[str, object]
                       ) -> Tuple[float, float]:
    origin, longitudinal, lateral = mission_axes(mission_frame)
    delta = (float(point[0]) - origin[0], float(point[1]) - origin[1])
    return (delta[0] * longitudinal[0] + delta[1] * longitudinal[1],
            delta[0] * lateral[0] + delta[1] * lateral[1])


def extract_landmarks(specification: Mapping[str, object],
                      support_disc_radius_meters: float) -> Tuple[MissionLandmark, ...]:
    """Landmarks present in the approved execution specification. Nothing added.

    No obstacle is created, no passage is moved, and no landmark is derived
    from a label, a headroom category or an execution result.
    """
    mission_frame = specification["mission_frame"]                  # type: ignore[index]
    landmarks: List[MissionLandmark] = []

    for index, passage in enumerate(specification.get("passages") or []):
        half_width = float(passage["half_width_meters"])
        for kind, key in (("passage_entry", "entry_position_meters"),
                          ("passage_exit", "exit_position_meters")):
            longitudinal, lateral = project_to_mission(passage[key], mission_frame)
            landmarks.append(MissionLandmark(
                landmark_id=f"{kind}-{index}", kind=kind,
                longitudinal_meters=longitudinal, lateral_meters=lateral,
                support_lateral_meters=half_width + support_disc_radius_meters,
                primitive_index=index))

    for entry in specification.get("static_obstacles") or []:
        if str(entry["primitive_type"]) != "circle":
            continue
        longitudinal, lateral = project_to_mission(entry["center_meters"], mission_frame)
        landmarks.append(MissionLandmark(
            landmark_id=f"circle-{entry['primitive_index']}", kind="circle",
            longitudinal_meters=longitudinal, lateral_meters=lateral,
            support_lateral_meters=0.0, primitive_index=int(entry["primitive_index"])))

    for entry in specification.get("dynamic_obstacles") or []:
        waypoints = entry["waypoints"]                              # type: ignore[index]
        first = project_to_mission(waypoints[0][:2], mission_frame)
        last = project_to_mission(waypoints[-1][:2], mission_frame)
        landmarks.append(MissionLandmark(
            landmark_id=f"dynamic-{entry['dynamic_obstacle_index']}", kind="dynamic_circle",
            longitudinal_meters=0.5 * (first[0] + last[0]),
            lateral_meters=0.0,          # the path sweeps across the axis
            support_lateral_meters=0.0,
            primitive_index=int(entry["dynamic_obstacle_index"])))

    landmarks.sort(key=lambda item: (item.longitudinal_meters, item.landmark_id))
    return tuple(landmarks)


def earliest_observable_origin(landmark_longitudinal: float, landmark_lateral: float,
                               team_size: int, sensing_range_meters: float,
                               nominal_spacing_meters: float,
                               topology_id: int = COMPACT) -> Optional[float]:
    """Longitudinal origin coordinate at which the landmark first enters `R_obs`.

    Computed over the *nominal role template*, not a point mass: a laterally
    offset robot sees a laterally offset landmark sooner than the origin does.
    That distinction decides real cases -- F7's clutter circles sit at
    |lateral| = 2.73-3.12 m against `R_obs = 3.0 m`, so a point-mass test would
    wrongly call several of them unobservable.

    Returns `None` when no template robot can ever bring the landmark inside
    `R_obs`, which is a legitimate NO_EVENT geometry rather than a defect.
    """
    template = construct_topology_from_spacing(
        topology_id, team_size, nominal_spacing_meters)
    best: Optional[float] = None
    for role in template.roles:
        offset_longitudinal, offset_lateral = float(role.offset[0]), float(role.offset[1])
        lateral_gap = abs(landmark_lateral - offset_lateral)
        if lateral_gap >= sensing_range_meters:
            continue
        reach = math.sqrt(sensing_range_meters * sensing_range_meters - lateral_gap * lateral_gap)
        candidate = landmark_longitudinal - offset_longitudinal - reach
        best = candidate if best is None else min(best, candidate)
    return best


def build_family_event_plan(specification: Mapping[str, object], team_size: int,
                            scripted_topologies: Sequence[int], *,
                            sensing_range_meters: float, nominal_spacing_meters: float,
                            support_disc_radius_meters: float,
                            maximum_speed_meters_per_second: float,
                            ) -> Tuple[SourceEvent, ...]:
    """Anchor the family's already-declared event *sequence* to its landmarks.

    `scripted_topologies` is the frozen ordered sequence of desired topologies
    for the family, taken unchanged from the superseded table. Only the trigger
    is re-derived; the number of events, their order and their target topologies
    are preserved exactly (ET-2).
    """
    landmarks = extract_landmarks(specification, support_disc_radius_meters)
    mission_frame = specification["mission_frame"]                  # type: ignore[index]
    goal_longitudinal, _ = project_to_mission(
        mission_frame["goal_center_meters"], mission_frame)         # type: ignore[index]

    constrictions = [item for item in landmarks
                     if item.kind in ("passage_entry", "circle", "dynamic_circle")]
    openings = [item for item in landmarks if item.kind == "passage_exit"]

    events: List[SourceEvent] = []
    constriction_cursor = 0
    opening_cursor = 0
    previous_trigger: Optional[float] = None

    for ordinal, topology in enumerate(scripted_topologies):
        if topology == LINE:
            if constriction_cursor >= len(constrictions):
                continue
            landmark = constrictions[constriction_cursor]
            constriction_cursor += 1
            # Earliest nominal local observability of the forward feature.
            lateral = landmark.lateral_meters
            candidates: List[float] = []
            for sign in (1.0, -1.0):
                value = earliest_observable_origin(
                    landmark.longitudinal_meters,
                    lateral + sign * landmark.support_lateral_meters,
                    team_size, sensing_range_meters, nominal_spacing_meters)
                if value is not None:
                    candidates.append(value)
            trigger = min(candidates) if candidates else None
            event_type = EVENT_CONSTRICTION
            purpose = ("originate the COMPACT->LINE event at the earliest nominal "
                       "local observability of the forward constriction")
        else:
            # Opening: the forward sector clears once the origin passes the last
            # support of the corresponding feature. Frozen S3 hysteresis then
            # governs whether the request is actually issued.
            if opening_cursor < len(openings):
                landmark = openings[opening_cursor]
                opening_cursor += 1
                trigger = landmark.longitudinal_meters
            elif constriction_cursor - 1 < len(constrictions) and constrictions:
                landmark = constrictions[min(constriction_cursor - 1, len(constrictions) - 1)]
                trigger = landmark.longitudinal_meters
            else:
                continue
            event_type = EVENT_OPENING
            purpose = ("originate the LINE->COMPACT event once the forward sector "
                       "clears past the feature, under frozen opening hysteresis")

        # ET-2: the declared sequence is preserved, so an event may not become
        # eligible before its predecessor. In F5 the second bottleneck entry
        # becomes observable at 2.66 m while the first exit is at 3.50 m; without
        # this clamp event #2 would fire before event #1, its LINE request would
        # be a no-op against an already-LINE commitment, and the family would
        # collapse from two bottleneck cycles to one.
        if trigger is not None and previous_trigger is not None:
            trigger = max(trigger, previous_trigger)
        previous_trigger = trigger if trigger is not None else previous_trigger

        reachable = trigger is not None and trigger < goal_longitudinal
        events.append(SourceEvent(
            ordinal=ordinal, event_type=event_type, candidate_topology=int(topology),
            landmark_id=landmark.landmark_id,
            landmark_longitudinal_meters=landmark.longitudinal_meters,
            trigger_longitudinal_meters=trigger,
            trigger_lower_bound_seconds=(max(0.0, trigger) / maximum_speed_meters_per_second
                                         if trigger is not None else None),
            reachable_before_goal=bool(reachable),
            observable_at_initialization=bool(trigger is not None and trigger <= 0.0),
            scientific_purpose=purpose))
    return tuple(events)
