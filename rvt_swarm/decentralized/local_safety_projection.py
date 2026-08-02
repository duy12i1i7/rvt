"""Exact per-robot local acceleration projection for Phase 6."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Tuple

import numpy as np

from ..runtime_configuration import RuntimeConfig
from .local_control_types import (
    LocalConstraintDiagnostic,
    LocalSafetyProjectionResult,
    RobotLocalControllerInput,
    Vec2,
)


@dataclass(frozen=True)
class _LocalHalfSpace:
    source_key: str
    threat_kind: str
    normal: Vec2
    lower_bound: float
    current_distance: float
    required_clearance: float
    stale_or_uncertain: bool


def _vector(value: Vec2) -> np.ndarray:
    return np.asarray(value, dtype=np.float64)


def _tuple(value: Vec2) -> Vec2:
    array = np.asarray(value, dtype=np.float64)
    return (float(array[0]), float(array[1]))


def _norm_clip(value: Vec2, limit: float) -> np.ndarray:
    array = _vector(value)
    length = float(np.linalg.norm(array))
    if length <= limit:
        return array
    return array * (limit / max(length, np.finfo(np.float64).tiny))


def _normal_from_relative(relative_center: Vec2, source_key: str) -> Tuple[np.ndarray, float]:
    outward = -_vector(relative_center)
    distance = float(np.linalg.norm(outward))
    if distance > np.finfo(np.float64).tiny:
        return outward / distance, distance
    # Exact overlap has no geometric normal. A stable local source key gives a
    # deterministic escape direction without reading any other robot.
    parity = sum(source_key.encode("utf-8")) % 2
    return np.array((1.0 if parity == 0 else -1.0, 0.0)), 0.0


def _constraint_diagnostic(
    item: _LocalHalfSpace,
    proposed_action: Vec2,
) -> LocalConstraintDiagnostic:
    proposed = _vector(proposed_action)
    normal = _vector(item.normal)
    tolerance = np.finfo(np.float64).eps * max(
        1.0,
        abs(item.lower_bound),
        float(np.linalg.norm(proposed)),
    )
    active = float(np.dot(normal, proposed)) < item.lower_bound - tolerance
    return LocalConstraintDiagnostic(
        source_key=item.source_key,
        threat_kind=item.threat_kind,
        outward_normal=item.normal,
        lower_bound_meters_per_second_squared=item.lower_bound,
        current_distance_meters=item.current_distance,
        required_clearance_meters=item.required_clearance,
        stale_or_uncertain=item.stale_or_uncertain,
        active_for_proposed_action=active,
    )


def _solve_projection(
    proposed_action: Vec2,
    constraints: Tuple[_LocalHalfSpace, ...],
    acceleration_limit: float,
) -> Tuple[np.ndarray, bool]:
    target = _vector(proposed_action)
    radius = float(acceleration_limit)
    machine = np.finfo(np.float64).eps
    scale = max(
        1.0,
        radius,
        float(np.linalg.norm(target)),
        *(abs(item.lower_bound) for item in constraints),
    )
    tolerance = machine * scale

    def feasible(candidate: Vec2) -> bool:
        value = _vector(candidate)
        if float(np.dot(value, value)) > radius * radius + tolerance:
            return False
        return all(
            float(np.dot(_vector(item.normal), value))
            >= item.lower_bound - tolerance
            for item in constraints
        )

    candidates: List[np.ndarray] = []

    def add(candidate: Vec2) -> None:
        value = _vector(candidate)
        if bool(np.isfinite(value).all()) and feasible(_tuple(value)):
            candidates.append(value)

    add(_tuple(_norm_clip(_tuple(target), radius)))

    for item in constraints:
        normal = _vector(item.normal)
        normal_sq = float(np.dot(normal, normal))
        projected = target + (
            (item.lower_bound - float(np.dot(normal, target))) / normal_sq
        ) * normal
        add(_tuple(projected))

        closest = normal * (item.lower_bound / normal_sq)
        closest_sq = float(np.dot(closest, closest))
        if closest_sq <= radius * radius + tolerance:
            tangent = np.array((-normal[1], normal[0]), dtype=np.float64)
            tangent_length = math.sqrt(max(radius * radius - closest_sq, 0.0))
            add(_tuple(closest + tangent * tangent_length))
            add(_tuple(closest - tangent * tangent_length))

    for index, first in enumerate(constraints):
        n_first = _vector(first.normal)
        for second in constraints[index + 1:]:
            n_second = _vector(second.normal)
            determinant = float(
                n_first[0] * n_second[1] - n_first[1] * n_second[0]
            )
            determinant_scale = max(
                1.0,
                float(np.linalg.norm(n_first)) * float(np.linalg.norm(n_second)),
            )
            if abs(determinant) <= machine * determinant_scale:
                continue
            intersection = np.array((
                (
                    first.lower_bound * n_second[1]
                    - n_first[1] * second.lower_bound
                ) / determinant,
                (
                    n_first[0] * second.lower_bound
                    - first.lower_bound * n_second[0]
                ) / determinant,
            ))
            add(_tuple(intersection))

    if not candidates:
        return np.zeros(2, dtype=np.float64), False
    best = min(candidates, key=lambda candidate: float(np.sum((candidate - target) ** 2)))
    return best, True


def _conservative_fallback(
    proposed_action: Vec2,
    constraints: Tuple[_LocalHalfSpace, ...],
    acceleration_limit: float,
) -> np.ndarray:
    proposed = _vector(proposed_action)
    weighted = np.zeros(2, dtype=np.float64)
    urgency = []
    for item in constraints:
        normal = _vector(item.normal)
        violation = max(item.lower_bound - float(np.dot(normal, proposed)), 0.0)
        urgency.append((violation, item))
        weighted += violation * normal
    length = float(np.linalg.norm(weighted))
    if length <= np.finfo(np.float64).tiny:
        selected = max(
            urgency,
            key=lambda pair: (pair[0], pair[1].lower_bound, pair[1].source_key),
        )[1]
        weighted = _vector(selected.normal)
        length = float(np.linalg.norm(weighted))
    return weighted * (acceleration_limit / max(length, np.finfo(np.float64).tiny))


class RobotLocalSafetyProjection:
    """Project one proposed acceleration using only one robot's local input."""

    def __init__(self, runtime_config: RuntimeConfig) -> None:
        if not isinstance(runtime_config, RuntimeConfig):
            raise TypeError("local safety projection requires RuntimeConfig")
        self.runtime_config = runtime_config

    def _peer_constraints(
        self,
        controller_input: RobotLocalControllerInput,
    ) -> Tuple[_LocalHalfSpace, ...]:
        config = self.runtime_config
        physical = config.physical
        maximum_age = config.communication.maximum_message_age_seconds
        communication_range = config.communication.communication_range_meters
        required = config.derived.robot_robot_required_clearance_meters
        result = []
        for peer in controller_input.peer_states:
            normal, distance = _normal_from_relative(
                peer.relative_position_meters,
                f"peer:{peer.peer_robot_id}",
            )
            if not peer.valid or distance > communication_range:
                continue
            stale = peer.message_age_seconds > maximum_age
            inflated = required + (
                physical.maximum_speed_meters_per_second * peer.message_age_seconds
            )
            relative_velocity = -_vector(peer.relative_velocity_meters_per_second)
            lower_bound = (
                inflated
                - distance
                - float(np.dot(normal, relative_velocity))
                * physical.control_period_seconds
            ) / (physical.control_period_seconds ** 2)
            lower_bound += physical.maximum_acceleration_meters_per_second_squared
            result.append(_LocalHalfSpace(
                source_key=f"peer:{peer.peer_robot_id}",
                threat_kind="peer",
                normal=_tuple(normal),
                lower_bound=float(lower_bound),
                current_distance=distance,
                required_clearance=inflated,
                stale_or_uncertain=stale or peer.message_age_seconds > 0.0,
            ))
        return tuple(result)

    def _obstacle_constraints(
        self,
        controller_input: RobotLocalControllerInput,
    ) -> Tuple[_LocalHalfSpace, ...]:
        config = self.runtime_config
        physical = config.physical
        sensing_range = config.sensing.obstacle_sensing_range_meters
        result = []
        for obstacle in controller_input.obstacle_states:
            normal, distance = _normal_from_relative(
                obstacle.relative_center_meters,
                obstacle.source_key,
            )
            if not obstacle.valid or distance > sensing_range:
                continue
            clearance = physical.robot_radius_meters + max(
                config.safety.obstacle_clearance_margin_meters,
                obstacle.radius_meters,
            )
            uncertainty = (
                physical.maximum_speed_meters_per_second
                * obstacle.observation_age_seconds
                + (1.0 - obstacle.confidence) * physical.robot_radius_meters
            )
            inflated = clearance + uncertainty
            relative_velocity = -_vector(
                obstacle.relative_velocity_meters_per_second
            )
            lower_bound = (
                inflated
                - distance
                - float(np.dot(normal, relative_velocity))
                * physical.control_period_seconds
            ) / (physical.control_period_seconds ** 2)
            result.append(_LocalHalfSpace(
                source_key=obstacle.source_key,
                threat_kind="obstacle",
                normal=_tuple(normal),
                lower_bound=float(lower_bound),
                current_distance=distance,
                required_clearance=inflated,
                stale_or_uncertain=(
                    obstacle.observation_age_seconds > 0.0
                    or obstacle.confidence < 1.0
                ),
            ))
        return tuple(result)

    def project(
        self,
        proposed_action: Vec2,
        controller_input: RobotLocalControllerInput,
    ) -> LocalSafetyProjectionResult:
        if not isinstance(controller_input, RobotLocalControllerInput):
            raise TypeError("projection requires RobotLocalControllerInput")
        proposed = _vector(proposed_action)
        if not bool(np.isfinite(proposed).all()):
            return LocalSafetyProjectionResult(
                projected_action=(0.0, 0.0),
                intervened=True,
                infeasible=False,
                solver_failed=True,
                status="invalid_proposed_action_fail_closed",
                constraints=(),
                active_constraint_count=0,
            )
        local_constraints = tuple(sorted(
            self._peer_constraints(controller_input)
            + self._obstacle_constraints(controller_input),
            key=lambda item: (item.threat_kind, item.source_key),
        ))
        diagnostics = tuple(
            _constraint_diagnostic(item, _tuple(proposed))
            for item in local_constraints
        )
        limit = (
            self.runtime_config.physical
            .maximum_acceleration_meters_per_second_squared
        )
        projected, feasible = _solve_projection(
            _tuple(proposed), local_constraints, limit
        )
        if not feasible:
            if local_constraints:
                projected = _conservative_fallback(
                    _tuple(proposed), local_constraints, limit
                )
                status = "infeasible_conservative_fallback"
            else:
                projected = np.zeros(2, dtype=np.float64)
                status = "solver_failure_fail_closed"
            return LocalSafetyProjectionResult(
                projected_action=_tuple(projected),
                intervened=True,
                infeasible=bool(local_constraints),
                solver_failed=not bool(local_constraints),
                status=status,
                constraints=diagnostics,
                active_constraint_count=sum(
                    item.active_for_proposed_action for item in diagnostics
                ),
            )
        tolerance = np.finfo(np.float64).eps * max(
            1.0, limit, float(np.linalg.norm(proposed))
        )
        intervened = float(np.linalg.norm(projected - proposed)) > tolerance
        if not intervened:
            status = "unchanged"
        elif float(np.linalg.norm(proposed)) > limit + tolerance:
            status = "physical_bound_projection"
        else:
            status = "local_constraint_projection"
        return LocalSafetyProjectionResult(
            projected_action=_tuple(projected),
            intervened=intervened,
            infeasible=False,
            solver_failed=False,
            status=status,
            constraints=diagnostics,
            active_constraint_count=sum(
                item.active_for_proposed_action for item in diagnostics
            ),
        )
