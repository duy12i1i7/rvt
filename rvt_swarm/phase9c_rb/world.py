"""Executable static world: collision truth and sensor conversion (RB-2, RB-4).

Two distinct geometries live here and must never be confused, which is why the
protocol says `sensor_tokens_are_not_collision_truth`:

* **Collision truth** is analytic. Circles are closed disks; a corridor's
  occupied space is the in-bounds complement of the closed centreline tube
  inside its active longitudinal slab.
* **Sensor tokens** are support discs: a deterministic discretisation of the
  visible inner boundary that a robot can actually perceive. They approximate
  the boundary; they never decide a collision.

Every constant here is read from the frozen protocol document, not chosen:
support radius `0.35 m`, maximum arc spacing `0.175 m`, obstacle surface margin
`0.02 m`, and the circle threshold
`robot_radius + max(safety.obstacle_clearance_margin, circle_radius)`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

Vec2 = Tuple[float, float]

SENSOR_CONVERSION_ID = "phase8e_analytic_boundary_support_discs/v1"


def _sub(a: Vec2, b: Vec2) -> Vec2:
    return (a[0] - b[0], a[1] - b[1])


def _norm(a: Vec2) -> float:
    return math.hypot(a[0], a[1])


def _point_segment_distance(p: Vec2, a: Vec2, b: Vec2) -> float:
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    denominator = dx * dx + dy * dy
    if denominator <= 0.0:
        return math.hypot(p[0] - ax, p[1] - ay)
    t = ((p[0] - ax) * dx + (p[1] - ay) * dy) / denominator
    t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
    return math.hypot(p[0] - (ax + t * dx), p[1] - (ay + t * dy))


def _polyline_distance(p: Vec2, points: Sequence[Vec2]) -> float:
    if len(points) == 1:
        return math.hypot(p[0] - points[0][0], p[1] - points[0][1])
    return min(_point_segment_distance(p, points[i], points[i + 1])
               for i in range(len(points) - 1))


def _moving_point_min_distance(pa: Vec2, pb: Vec2, ca: Vec2, cb: Vec2) -> float:
    """Exact minimum distance between two linearly interpolated points.

    Closed form, not sampled: the squared separation is a quadratic in the
    interval parameter, so its minimum over `[0,1]` is exact. Used for
    robot-robot, robot-circle and robot-dynamic-circle checks.
    """
    r0 = (pa[0] - ca[0], pa[1] - ca[1])
    dr = ((pb[0] - cb[0]) - r0[0], (pb[1] - cb[1]) - r0[1])
    a = dr[0] * dr[0] + dr[1] * dr[1]
    if a <= 0.0:
        return _norm(r0)
    t = -(r0[0] * dr[0] + r0[1] * dr[1]) / a
    t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
    return math.hypot(r0[0] + t * dr[0], r0[1] + t * dr[1])


def _max_polyline_distance_over_path(pa: Vec2, pb: Vec2, points: Sequence[Vec2],
                                     threshold: float, tolerance: float) -> float:
    """Maximum distance-to-polyline along the straight path `pa -> pb`.

    Needed because a corridor collision means *leaving* the tube, i.e. the
    distance to the centreline becoming large. Distance to a polyline is a
    minimum of convex functions and is therefore not itself convex, so the
    maximum can occur strictly inside the interval and endpoint checks alone
    would miss a corner cut.

    The function is 1-Lipschitz in path length, which gives an exact
    branch-and-bound: over a subinterval of length `L`, the maximum cannot
    exceed `d(midpoint) + L/2`. Recursion stops as soon as a subinterval is
    provably below `threshold` (it cannot collide) or the bound is within
    `tolerance`. In open space it prunes at depth zero.
    """
    total_length = math.hypot(pb[0] - pa[0], pb[1] - pa[1])
    if total_length <= 0.0:
        return _polyline_distance(pa, points)

    def evaluate(t: float) -> float:
        return _polyline_distance((pa[0] + t * (pb[0] - pa[0]),
                                   pa[1] + t * (pb[1] - pa[1])), points)

    best = max(evaluate(0.0), evaluate(1.0))
    stack: List[Tuple[float, float]] = [(0.0, 1.0)]
    while stack:
        lo, hi = stack.pop()
        span = (hi - lo) * total_length
        mid = 0.5 * (lo + hi)
        value = evaluate(mid)
        if value > best:
            best = value
        upper_bound = value + 0.5 * span
        if upper_bound <= best + tolerance:
            continue                      # cannot improve the incumbent
        if best >= threshold:
            return best                   # already a collision; refining is pointless
        if span <= tolerance:
            continue
        stack.append((lo, mid))
        stack.append((mid, hi))
    return best


@dataclass(frozen=True)
class SupportDisc:
    """One sensor token. `side` and `arc_index` fix the canonical ordering."""

    center_meters: Vec2
    radius_meters: float
    primitive_index: int
    side: str
    arc_index: int
    source_key: str


@dataclass(frozen=True)
class CirclePrimitive:
    center_meters: Vec2
    radius_meters: float
    primitive_index: int
    source_primitive_type: str

    def collision_threshold(self, robot_radius: float, clearance_margin: float) -> float:
        return robot_radius + max(clearance_margin, self.radius_meters)


@dataclass(frozen=True)
class CorridorPrimitive:
    """Analytic corridor walls: the complement of a tube inside a slab."""

    primitive_index: int
    centerline_meters: Tuple[Vec2, ...]
    half_width_meters: float
    slab_world_x_meters: Tuple[float, float]
    entry_position_meters: Vec2
    exit_position_meters: Vec2
    primitive_type: str

    def surface_distance(self, position: Vec2) -> float:
        """Euclidean distance from `position` to this primitive's wall material.

        Zero when the robot is already inside wall material. Outside the active
        slab the primitive contributes no occupied space, so the nearest wall
        lies on the slab face; that distance is computed exactly rather than
        reported as infinite, which would let a robot graze the slab edge.
        """
        x0, x1 = self.slab_world_x_meters
        if x0 <= position[0] <= x1:
            distance_to_centerline = _polyline_distance(position, self.centerline_meters)
            if distance_to_centerline > self.half_width_meters:
                return 0.0
            return self.half_width_meters - distance_to_centerline
        face_x = x0 if position[0] < x0 else x1
        lateral = _polyline_distance((face_x, position[1]), self.centerline_meters)
        outward = max(0.0, self.half_width_meters - lateral)
        return math.hypot(face_x - position[0], outward)

    def swept_max_centerline_distance(self, pa: Vec2, pb: Vec2,
                                      threshold: float, tolerance: float) -> float:
        return _max_polyline_distance_over_path(
            pa, pb, self.centerline_meters, threshold, tolerance)

    def boundary_support_discs(self, support_radius: float,
                               maximum_arc_spacing: float) -> Tuple[SupportDisc, ...]:
        """Deterministic support discs for both inner boundary components.

        The boundary polylines are the centreline offset by `+/- half_width`
        along vertex normals; each is sampled by arc length with endpoints
        included and spacing at most `maximum_arc_spacing`; each sample is then
        inset one support radius into occupied space. Ordering is by side then
        arc index, which with the caller's distance sort reproduces the frozen
        `distance, primitive index, boundary side, arc index`.
        """
        discs: List[SupportDisc] = []
        for side, sign in (("left", 1.0), ("right", -1.0)):
            boundary = _offset_polyline(self.centerline_meters, sign * self.half_width_meters)
            outward = _offset_polyline(
                self.centerline_meters, sign * (self.half_width_meters + support_radius))
            for arc_index, (_, center) in enumerate(
                    _sample_by_arc_length(boundary, outward, maximum_arc_spacing)):
                discs.append(SupportDisc(
                    center_meters=center,
                    radius_meters=support_radius,
                    primitive_index=self.primitive_index,
                    side=side,
                    arc_index=arc_index,
                    source_key=f"corridor-{self.primitive_index}-{side}-{arc_index}",
                ))
        return tuple(discs)


def _vertex_normals(points: Sequence[Vec2]) -> Tuple[Vec2, ...]:
    """Unit normals at each control point; interior vertices average neighbours."""
    segment_normals: List[Vec2] = []
    for i in range(len(points) - 1):
        dx, dy = _sub(points[i + 1], points[i])
        length = math.hypot(dx, dy)
        if length <= 0.0:
            segment_normals.append((0.0, 1.0))
        else:
            segment_normals.append((-dy / length, dx / length))
    normals: List[Vec2] = []
    for i in range(len(points)):
        if i == 0:
            candidate = segment_normals[0]
        elif i == len(points) - 1:
            candidate = segment_normals[-1]
        else:
            a, b = segment_normals[i - 1], segment_normals[i]
            candidate = (a[0] + b[0], a[1] + b[1])
        length = _norm(candidate)
        normals.append((0.0, 1.0) if length <= 0.0 else (candidate[0] / length, candidate[1] / length))
    return tuple(normals)


def _offset_polyline(points: Sequence[Vec2], offset: float) -> Tuple[Vec2, ...]:
    normals = _vertex_normals(points)
    return tuple((p[0] + offset * n[0], p[1] + offset * n[1])
                 for p, n in zip(points, normals))


def _sample_by_arc_length(boundary: Sequence[Vec2], outward: Sequence[Vec2],
                          maximum_spacing: float) -> Tuple[Tuple[Vec2, Vec2], ...]:
    """Sample a boundary polyline by arc length, endpoints included.

    Returns `(boundary_point, inset_support_center)` pairs. `outward` is the
    same polyline offset by one further support radius, so the inset direction
    is taken from the same normal construction rather than recomputed.
    """
    samples: List[Tuple[Vec2, Vec2]] = []
    for i in range(len(boundary) - 1):
        a, b = boundary[i], boundary[i + 1]
        oa, ob = outward[i], outward[i + 1]
        length = math.hypot(b[0] - a[0], b[1] - a[1])
        steps = max(1, int(math.ceil(length / maximum_spacing))) if length > 0.0 else 1
        for k in range(steps):
            t = k / steps
            samples.append((
                (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])),
                (oa[0] + t * (ob[0] - oa[0]), oa[1] + t * (ob[1] - oa[1])),
            ))
    samples.append((boundary[-1], outward[-1]))
    return tuple(samples)


@dataclass(frozen=True)
class StaticWorld:
    """Complete static geometry. Simulator-scope; never handed to a robot."""

    circles: Tuple[CirclePrimitive, ...]
    corridors: Tuple[CorridorPrimitive, ...]
    world_bounds_meters: Tuple[Tuple[float, float], Tuple[float, float]]
    robot_radius_meters: float
    obstacle_clearance_margin_meters: float
    obstacle_surface_margin_meters: float
    support_disc_radius_meters: float
    maximum_arc_spacing_meters: float
    collision_tolerance_meters: float

    # -- collision truth ---------------------------------------------------
    def static_collision(self, position: Vec2) -> Optional[str]:
        for circle in self.circles:
            threshold = circle.collision_threshold(
                self.robot_radius_meters, self.obstacle_clearance_margin_meters)
            if _norm(_sub(position, circle.center_meters)) <= threshold + self.collision_tolerance_meters:
                return f"circle-{circle.primitive_index}"
        wall_threshold = self.robot_radius_meters + self.obstacle_surface_margin_meters
        for corridor in self.corridors:
            if corridor.surface_distance(position) <= wall_threshold + self.collision_tolerance_meters:
                return f"corridor-{corridor.primitive_index}"
        return None

    def swept_static_collision(self, pa: Vec2, pb: Vec2) -> Optional[str]:
        """Continuous check over one closed control interval."""
        for circle in self.circles:
            threshold = circle.collision_threshold(
                self.robot_radius_meters, self.obstacle_clearance_margin_meters)
            if _moving_point_min_distance(pa, pb, circle.center_meters,
                                          circle.center_meters) <= threshold + self.collision_tolerance_meters:
                return f"circle-{circle.primitive_index}"
        wall_threshold = self.robot_radius_meters + self.obstacle_surface_margin_meters
        for corridor in self.corridors:
            x0, x1 = corridor.slab_world_x_meters
            if max(pa[0], pb[0]) < x0 or min(pa[0], pb[0]) > x1:
                if (corridor.surface_distance(pa) <= wall_threshold + self.collision_tolerance_meters
                        or corridor.surface_distance(pb) <= wall_threshold + self.collision_tolerance_meters):
                    return f"corridor-{corridor.primitive_index}"
                continue
            limit = corridor.half_width_meters - wall_threshold
            reached = corridor.swept_max_centerline_distance(
                pa, pb, limit, self.collision_tolerance_meters)
            if reached >= limit - self.collision_tolerance_meters:
                return f"corridor-{corridor.primitive_index}"
        return None

    def boundary_exit(self, position: Vec2) -> bool:
        (xmin, xmax), (ymin, ymax) = self.world_bounds_meters
        radius = self.robot_radius_meters
        return not (xmin + radius <= position[0] <= xmax - radius
                    and ymin + radius <= position[1] <= ymax - radius)

    # -- sensor conversion -------------------------------------------------
    def observable_tokens(self, position: Vec2, sensing_range: float
                          ) -> Tuple[Tuple[Vec2, float, str], ...]:
        """Ego-relative `(relative_center, radius, source_key)` within `R_obs`.

        This is the *only* geometry a robot ever sees. Analytic occupied sets,
        world bounds, slab extents and the complete layout stay behind it.
        """
        tokens: List[Tuple[float, Vec2, float, int, str, int, str]] = []
        for circle in self.circles:
            offset = _sub(circle.center_meters, position)
            distance = _norm(offset)
            if distance <= sensing_range:
                tokens.append((distance, offset, circle.radius_meters,
                               circle.primitive_index, "circle", 0,
                               f"circle-{circle.primitive_index}"))
        for corridor in self.corridors:
            for disc in corridor.boundary_support_discs(
                    self.support_disc_radius_meters, self.maximum_arc_spacing_meters):
                offset = _sub(disc.center_meters, position)
                distance = _norm(offset)
                if distance <= sensing_range:
                    tokens.append((distance, offset, disc.radius_meters,
                                   disc.primitive_index, disc.side, disc.arc_index,
                                   disc.source_key))
        tokens.sort(key=lambda item: (item[0], item[3], item[4], item[5]))
        return tuple((offset, radius, key) for _, offset, radius, _, _, _, key in tokens)


def build_static_world(specification: Mapping[str, object],
                       runtime_config: object,
                       protocol: Mapping[str, object],
                       target_contract: Mapping[str, object]) -> StaticWorld:
    """Compile one layout execution specification into executable geometry.

    Reads the already-compiled record. It does not re-derive scientific geometry
    from raw Phase 8 fields -- RB-2 forbids that, and the compiler has already
    resolved slab extents, clipped centrelines and half widths.
    """
    static_contract = protocol["static_obstacle_contract"]
    inflation = static_contract["collision_inflation"]           # type: ignore[index]
    conversion = static_contract["sensor_conversion"]            # type: ignore[index]

    passages = list(specification.get("passages") or [])
    circles: List[CirclePrimitive] = []
    corridors: List[CorridorPrimitive] = []
    for entry in specification.get("static_obstacles") or []:
        primitive_type = str(entry["primitive_type"])
        index = int(entry["primitive_index"])
        if primitive_type == "circle":
            circles.append(CirclePrimitive(
                center_meters=(float(entry["center_meters"][0]), float(entry["center_meters"][1])),
                radius_meters=float(entry["radius_meters"]),
                primitive_index=index,
                source_primitive_type=str(entry.get("source_primitive_type", "circle")),
            ))
        elif primitive_type == "analytic_corridor_walls":
            passage = passages[int(entry["passage_reference"])]
            corridors.append(CorridorPrimitive(
                primitive_index=index,
                centerline_meters=tuple((float(p[0]), float(p[1]))
                                        for p in passage["centerline_control_points_meters"]),
                half_width_meters=float(passage["half_width_meters"]),
                slab_world_x_meters=(float(passage["active_longitudinal_world_x_meters"][0]),
                                     float(passage["active_longitudinal_world_x_meters"][1])),
                entry_position_meters=(float(passage["entry_position_meters"][0]),
                                       float(passage["entry_position_meters"][1])),
                exit_position_meters=(float(passage["exit_position_meters"][0]),
                                      float(passage["exit_position_meters"][1])),
                primitive_type=str(passage["primitive_type"]),
            ))
        else:
            raise ValueError(f"unsupported compiled static primitive {primitive_type!r}")

    bounds = specification["world_bounds_meters"]
    # The protocol document carries only a schema/hash reference to the Target
    # V4 contract, so the collision tolerance is read from the standalone
    # contract the caller supplies. It is never defaulted.
    tolerance = float(
        target_contract["conditions"]["collision_free_complete_horizon"]      # type: ignore[index]
        ["tolerance_meters"])

    return StaticWorld(
        circles=tuple(circles),
        corridors=tuple(corridors),
        world_bounds_meters=((float(bounds[0][0]), float(bounds[0][1])),
                             (float(bounds[1][0]), float(bounds[1][1]))),
        robot_radius_meters=float(runtime_config.physical.robot_radius_meters),
        obstacle_clearance_margin_meters=float(runtime_config.safety.obstacle_clearance_margin_meters),
        obstacle_surface_margin_meters=float(inflation["obstacle_surface_margin_meters"]),
        support_disc_radius_meters=float(conversion["support_disc_radius_meters"]),
        maximum_arc_spacing_meters=float(conversion["maximum_arc_spacing_meters"]),
        collision_tolerance_meters=tolerance,
    )


def first_passage_entry(specification: Mapping[str, object]) -> Optional[Vec2]:
    """Entry point of the first compiled passage; F8's cut start needs it."""
    passages = list(specification.get("passages") or [])
    if not passages:
        return None
    entry = passages[0]["entry_position_meters"]                  # type: ignore[index]
    return (float(entry[0]), float(entry[1]))
