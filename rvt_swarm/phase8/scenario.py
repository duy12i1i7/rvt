"""Versioned Phase 8 scenario families and deterministic geometry descriptors."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict, Tuple

from ..topology_registry import COMPACT
from .common import sha256_document
from .seeds import derive_seed, seed_commitment


SCENARIO_FAMILY_SCHEMA_VERSION = "rvt-scenario-family/v1"
SCENARIO_LAYOUT_SCHEMA_VERSION = "rvt-scenario-layout/v1"
GEOMETRY_GENERATOR_VERSION = "rvt-compact-line-geometry/v1"

TRAIN_SPLIT = "train"
VALIDATION_SPLIT = "validation"
FINAL_TEST_SPLIT = "final_test"
SPLIT_NAMES: Tuple[str, ...] = (
    TRAIN_SPLIT,
    VALIDATION_SPLIT,
    FINAL_TEST_SPLIT,
)
SUPPORTED_TEAM_SIZES: Tuple[int, ...] = (5, 6, 8, 12, 16, 24)
STUDY_A_TRAINING_SIZES: Tuple[int, ...] = (5, 6, 8, 12, 16)

COMPACT_ONLY_SUCCESS = "COMPACT_ONLY_SUCCESS"
LINE_ONLY_SUCCESS = "LINE_ONLY_SUCCESS"
BOTH_SUCCESS = "BOTH_SUCCESS"
BOTH_FAIL = "BOTH_FAIL"
RECONFIGURATION_REQUIRED = "RECONFIGURATION_REQUIRED"
INVALID_OR_AMBIGUOUS = "INVALID_OR_AMBIGUOUS"
HEADROOM_CATEGORIES: Tuple[str, ...] = (
    COMPACT_ONLY_SUCCESS,
    LINE_ONLY_SUCCESS,
    BOTH_SUCCESS,
    BOTH_FAIL,
    RECONFIGURATION_REQUIRED,
    INVALID_OR_AMBIGUOUS,
)


@dataclass(frozen=True)
class ScenarioFamily:
    schema_version: str
    family_id: str
    canonical_name: str
    scientific_purpose: str
    expected_headroom_categories: Tuple[str, ...]
    geometry_parameter_ranges: Tuple[Tuple[str, str], ...]
    obstacle_representation: str
    initial_topology_id: int
    allowed_transition_opportunities: Tuple[str, ...]
    goal_semantics: str
    team_sizes: Tuple[int, ...]
    communication_conditions: Tuple[str, ...]
    episode_horizon_seconds: float
    validity_checks: Tuple[str, ...]
    exclusion_rules: Tuple[str, ...]
    diagnostic_policies: Tuple[str, ...]


@dataclass(frozen=True)
class ObstaclePrimitive:
    primitive_type: str
    values: Tuple[float, ...]


@dataclass(frozen=True)
class DynamicObstaclePath:
    radius_meters: float
    waypoints: Tuple[Tuple[float, float, float], ...]


@dataclass(frozen=True)
class ScenarioLayout:
    schema_version: str
    generator_version: str
    layout_id: str
    family_id: str
    split: str
    variant_index: int
    generation_seed_commitment: str
    start_center_meters: Tuple[float, float]
    goal_center_meters: Tuple[float, float]
    corridor_centerline_meters: Tuple[Tuple[float, float], ...]
    nominal_passage_width_meters: float
    static_obstacles: Tuple[ObstaclePrimitive, ...]
    dynamic_obstacle_paths: Tuple[DynamicObstaclePath, ...]
    bypass_available: bool
    communication_profile: str
    initial_topology_id: int
    episode_horizon_seconds: float
    canonical_parameters: Tuple[Tuple[str, str], ...]
    diagnostic_headroom_by_team_size: Tuple[Tuple[int, str], ...]

    def canonical_geometry(self) -> Dict[str, object]:
        return {
            "generator_version": self.generator_version,
            "family_id": self.family_id,
            "start_center_meters": list(self.start_center_meters),
            "goal_center_meters": list(self.goal_center_meters),
            "corridor_centerline_meters": [
                list(point) for point in self.corridor_centerline_meters
            ],
            "nominal_passage_width_meters": self.nominal_passage_width_meters,
            "static_obstacles": [asdict(item) for item in self.static_obstacles],
            "dynamic_obstacle_paths": [
                asdict(item) for item in self.dynamic_obstacle_paths
            ],
            "bypass_available": self.bypass_available,
            "communication_profile": self.communication_profile,
            "initial_topology_id": self.initial_topology_id,
            "episode_horizon_seconds": self.episode_horizon_seconds,
            "canonical_parameters": [list(item) for item in self.canonical_parameters],
        }

    def geometry_sha256(self) -> str:
        return sha256_document(self.canonical_geometry())

    def parameter_tuple_sha256(self) -> str:
        return sha256_document([list(item) for item in self.canonical_parameters])

    def headroom_for(self, team_size: int) -> str:
        for size, category in self.diagnostic_headroom_by_team_size:
            if size == team_size:
                return category
        raise ValueError(f"team size {team_size} is outside the layout contract")


_COMMON_VALIDITY = (
    "initial roles satisfy frozen physical-validity checks",
    "goal and obstacles lie inside declared world bounds",
    "geometry primitives are finite and non-self-intersecting",
    "communication schedule satisfies or explicitly violates its named contract",
)
_COMMON_EXCLUSIONS = (
    "duplicate geometry or canonical parameter tuple",
    "invalid initial collision or unreachable goal outside the intended task",
    "metric or simulator numerical invalidity",
)
_COMMON_DIAGNOSTICS = (
    "always COMPACT rollout",
    "always LINE rollout",
    "frozen scripted COMPACT/LINE transition oracle",
)


def _family(
    family_id: str,
    name: str,
    purpose: str,
    categories: Tuple[str, ...],
    ranges: Tuple[Tuple[str, str], ...],
    obstacle_representation: str,
    opportunities: Tuple[str, ...],
    communication: Tuple[str, ...],
    horizon: float,
) -> ScenarioFamily:
    return ScenarioFamily(
        SCENARIO_FAMILY_SCHEMA_VERSION,
        family_id,
        name,
        purpose,
        categories,
        ranges,
        obstacle_representation,
        COMPACT,
        opportunities,
        "reach the declared goal region and satisfy required final Metric V3 dwell",
        SUPPORTED_TEAM_SIZES,
        communication,
        horizon,
        _COMMON_VALIDITY,
        _COMMON_EXCLUSIONS,
        _COMMON_DIAGNOSTICS,
    )


SCENARIO_FAMILIES: Tuple[ScenarioFamily, ...] = (
    _family(
        "F1", "OPEN_NOMINAL_TRANSIT",
        "measure unnecessary LINE elongation in nominal open transit",
        (BOTH_SUCCESS,),
        (("sparse_obstacle_offset_m", "3.0..3.9"),),
        "static circles outside the nominal transit band",
        (), ("nominal",), 90.0,
    ),
    _family(
        "F2", "STRAIGHT_NARROW_PASSAGE",
        "provide clear LINE headroom over COMPACT",
        (LINE_ONLY_SUCCESS,),
        (("passage_width_m", "1.30..1.55"), ("length_m", "4.0..5.2")),
        "paired finite wall segments",
        ("COMPACT_TO_LINE", "LINE_TO_COMPACT"), ("nominal",), 120.0,
    ),
    _family(
        "F3", "OFFSET_ENTRY_PASSAGE",
        "test local reasoning at an entrance offset from the initial centreline",
        (LINE_ONLY_SUCCESS,),
        (("entry_offset_m", "0.7..1.4"), ("passage_width_m", "1.35..1.60")),
        "offset polyline corridor boundaries",
        ("COMPACT_TO_LINE", "LINE_TO_COMPACT"), ("nominal",), 135.0,
    ),
    _family(
        "F4", "CURVED_OR_S_SHAPED_PASSAGE",
        "require sustained narrow operation through curvature",
        (LINE_ONLY_SUCCESS,),
        (("curvature_amplitude_m", "0.7..1.4"), ("passage_width_m", "1.40..1.65")),
        "sampled S-centreline with finite-width boundaries",
        ("COMPACT_TO_LINE", "LINE_TO_COMPACT"), ("nominal",), 150.0,
    ),
    _family(
        "F5", "SEQUENTIAL_BOTTLENECKS",
        "test repeatable transition lifecycles across separated bottlenecks",
        (RECONFIGURATION_REQUIRED,),
        (("bottleneck_separation_m", "3.0..4.8"), ("passage_width_m", "1.40..1.65")),
        "two finite corridor bands separated by open recovery space",
        ("COMPACT_TO_LINE", "LINE_TO_COMPACT", "REPEAT"), ("nominal",), 180.0,
    ),
    _family(
        "F6", "FALSE_BOTTLENECK_OR_FEASIBLE_BYPASS",
        "penalize unnecessary LINE commitments when COMPACT has a valid bypass",
        (COMPACT_ONLY_SUCCESS, BOTH_SUCCESS),
        (("bypass_turn_radius_m", "1.0..1.8"), ("bypass_clearance_m", "1.2..2.0")),
        "central blocker with an explicit curved bypass branch",
        ("OPTIONAL_COMPACT_TO_LINE",), ("nominal",), 130.0,
    ),
    _family(
        "F7", "TOPOLOGY_NEUTRAL_CLUTTER",
        "preserve both-success outcomes without arbitrary winner labels",
        (BOTH_SUCCESS,),
        (("clutter_clearance_m", "2.8..3.8"),),
        "sparse deterministic circles with two feasible corridors",
        ("OPTIONAL_COMPACT_TO_LINE", "OPTIONAL_LINE_TO_COMPACT"), ("nominal",), 110.0,
    ),
    _family(
        "F8", "COMMUNICATION_DEGRADED_RECONFIGURATION",
        "measure bounded communication effects on score readiness and confirmation",
        (RECONFIGURATION_REQUIRED,),
        (("delay_s", "0.0..0.30"), ("packet_loss", "0.0..0.15")),
        "straight or sequential passage plus a versioned link schedule",
        ("COMPACT_TO_LINE", "LINE_TO_COMPACT"),
        ("bounded_delay_loss", "temporary_disconnection_then_restore"), 180.0,
    ),
    _family(
        "F9", "DYNAMIC_LOCAL_OBSTACLE",
        "test candidate recoverability under a locally observable moving obstacle",
        (BOTH_SUCCESS, LINE_ONLY_SUCCESS),
        (("obstacle_speed_mps", "0.15..0.35"), ("crossing_time_s", "12..24")),
        "static passage plus one circular obstacle waypoint path",
        ("OPTIONAL_COMPACT_TO_LINE", "OPTIONAL_LINE_TO_COMPACT"), ("nominal",), 150.0,
    ),
    _family(
        "F10", "PROVABLY_OR_DIAGNOSTICALLY_INFEASIBLE",
        "retain explicit both-fail outcomes and generator failure detection",
        (BOTH_FAIL,),
        (("passage_width_m", "0.65..0.95"),),
        "paired walls below the frozen disk-clearance requirement",
        ("COMPACT_TO_LINE",), ("nominal",), 90.0,
    ),
)

_FAMILY_BY_ID = {item.family_id: item for item in SCENARIO_FAMILIES}
_SPLIT_OFFSETS = {TRAIN_SPLIT: 0.0, VALIDATION_SPLIT: 0.43, FINAL_TEST_SPLIT: 0.79}
_SPLIT_VARIANTS = {TRAIN_SPLIT: (0, 1), VALIDATION_SPLIT: (0,), FINAL_TEST_SPLIT: (0,)}


def scenario_family(family_id: str) -> ScenarioFamily:
    try:
        return _FAMILY_BY_ID[family_id]
    except KeyError as exc:
        raise ValueError(f"unknown scenario family {family_id!r}") from exc


def _headroom(family_id: str, split: str, variant_index: int) -> str:
    if family_id == "F1":
        return BOTH_SUCCESS
    if family_id in ("F2", "F3", "F4"):
        return LINE_ONLY_SUCCESS
    if family_id in ("F5", "F8"):
        return RECONFIGURATION_REQUIRED
    if family_id == "F6":
        return BOTH_SUCCESS if split == TRAIN_SPLIT and variant_index == 1 else COMPACT_ONLY_SUCCESS
    if family_id in ("F7", "F9"):
        return BOTH_SUCCESS
    return BOTH_FAIL


def _layout(family_id: str, split: str, variant_index: int) -> ScenarioLayout:
    family = scenario_family(family_id)
    offset = _SPLIT_OFFSETS[split] + 0.11 * variant_index
    seed = derive_seed(
        "layout_generation",
        GEOMETRY_GENERATOR_VERSION,
        family_id,
        variant_index,
        split=split,
        sealed_final_authorized=split == FINAL_TEST_SPLIT,
    )
    jitter = (seed % 997) / 100000.0
    start = (-6.0, round(-0.2 + jitter, 6))
    goal = (6.0, round(0.2 - jitter, 6))
    centerline: Tuple[Tuple[float, float], ...] = (start, goal)
    width = 4.0
    obstacles: Tuple[ObstaclePrimitive, ...] = ()
    dynamic: Tuple[DynamicObstaclePath, ...] = ()
    bypass = False
    communication = family.communication_conditions[0]
    params: Tuple[Tuple[str, str], ...]

    if family_id == "F1":
        lateral = 3.0 + offset
        obstacles = (
            ObstaclePrimitive("circle", (-1.8, lateral, 0.35)),
            ObstaclePrimitive("circle", (1.8, -lateral, 0.35)),
        )
        params = (("sparse_obstacle_offset_m", f"{lateral:.6f}"),)
    elif family_id == "F2":
        width = 1.30 + 0.12 * offset
        length = 4.0 + 0.6 * offset
        obstacles = (ObstaclePrimitive("straight_corridor", (-length / 2, length / 2, width)),)
        params = (("passage_width_m", f"{width:.6f}"), ("length_m", f"{length:.6f}"))
    elif family_id == "F3":
        width = 1.35 + 0.10 * offset
        entry = 0.7 + 0.5 * offset
        centerline = (start, (-2.5, -entry), (0.0, entry), goal)
        obstacles = (ObstaclePrimitive("polyline_corridor", (width, entry)),)
        params = (("entry_offset_m", f"{entry:.6f}"), ("passage_width_m", f"{width:.6f}"))
    elif family_id == "F4":
        width = 1.40 + 0.10 * offset
        amplitude = 0.7 + 0.5 * offset
        centerline = (start, (-3.0, amplitude), (0.0, -amplitude), (3.0, amplitude), goal)
        obstacles = (ObstaclePrimitive("s_corridor", (width, amplitude)),)
        params = (("curvature_amplitude_m", f"{amplitude:.6f}"), ("passage_width_m", f"{width:.6f}"))
    elif family_id == "F5":
        width = 1.40 + 0.10 * offset
        separation = 3.0 + 1.2 * offset
        obstacles = (
            ObstaclePrimitive("straight_corridor", (-4.0, -2.5, width)),
            ObstaclePrimitive("straight_corridor", (-2.5 + separation, -1.0 + separation, width)),
        )
        params = (("bottleneck_separation_m", f"{separation:.6f}"), ("passage_width_m", f"{width:.6f}"))
    elif family_id == "F6":
        radius = 1.0 + 0.6 * offset
        clearance = 1.2 + 0.5 * offset
        centerline = (start, (-1.5, 0.0), (0.0, clearance), (1.5, 0.0), goal)
        obstacles = (ObstaclePrimitive("central_blocker", (0.0, 0.0, 0.8)),)
        bypass = True
        params = (("bypass_turn_radius_m", f"{radius:.6f}"), ("bypass_clearance_m", f"{clearance:.6f}"))
    elif family_id == "F7":
        clearance = 2.8 + 0.6 * offset
        obstacles = (
            ObstaclePrimitive("circle", (-2.0, clearance, 0.35)),
            ObstaclePrimitive("circle", (0.0, -clearance, 0.35)),
            ObstaclePrimitive("circle", (2.0, clearance, 0.35)),
        )
        params = (("clutter_clearance_m", f"{clearance:.6f}"),)
    elif family_id == "F8":
        width = 1.45 + 0.08 * offset
        delay = 0.05 + 0.10 * offset
        loss = 0.02 + 0.05 * offset
        obstacles = (ObstaclePrimitive("straight_corridor", (-2.5, 2.5, width)),)
        communication = (
            "temporary_disconnection_then_restore"
            if variant_index == 1 else "bounded_delay_loss"
        )
        params = (("delay_s", f"{delay:.6f}"), ("packet_loss", f"{loss:.6f}"), ("passage_width_m", f"{width:.6f}"))
    elif family_id == "F9":
        speed = 0.15 + 0.12 * offset
        crossing = 12.0 + 8.0 * offset
        dynamic = (
            DynamicObstaclePath(
                0.35,
                ((-0.5, -2.5, 0.0), (-0.5, 2.5, crossing)),
            ),
        )
        params = (("obstacle_speed_mps", f"{speed:.6f}"), ("crossing_time_s", f"{crossing:.6f}"))
    else:
        width = 0.65 + 0.12 * offset
        obstacles = (ObstaclePrimitive("straight_corridor", (-2.0, 2.0, width)),)
        params = (("passage_width_m", f"{width:.6f}"),)

    category = _headroom(family_id, split, variant_index)
    return ScenarioLayout(
        SCENARIO_LAYOUT_SCHEMA_VERSION,
        GEOMETRY_GENERATOR_VERSION,
        f"{split}-{family_id.lower()}-{variant_index:02d}",
        family_id,
        split,
        variant_index,
        seed_commitment(seed),
        start,
        goal,
        centerline,
        round(width, 6),
        obstacles,
        dynamic,
        bypass,
        communication,
        family.initial_topology_id,
        family.episode_horizon_seconds,
        params,
        tuple((size, category) for size in SUPPORTED_TEAM_SIZES),
    )


def generate_layouts(
    split: str,
    *,
    sealed_generation_authorized: bool = False,
) -> Tuple[ScenarioLayout, ...]:
    if split not in SPLIT_NAMES:
        raise ValueError(f"unknown split {split!r}")
    if split == FINAL_TEST_SPLIT and not sealed_generation_authorized:
        raise PermissionError("final-test geometry enumeration is sealed")
    return tuple(
        _layout(family.family_id, split, variant)
        for family in SCENARIO_FAMILIES
        for variant in _SPLIT_VARIANTS[split]
    )


def scenario_family_manifest() -> Dict[str, object]:
    payload: Dict[str, object] = {
        "schema_version": SCENARIO_FAMILY_SCHEMA_VERSION,
        "generator_version": GEOMETRY_GENERATOR_VERSION,
        "family_count": len(SCENARIO_FAMILIES),
        "families": [asdict(item) for item in SCENARIO_FAMILIES],
    }
    payload["scenario_family_sha256"] = sha256_document(payload)
    return payload
