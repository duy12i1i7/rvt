"""Independent two-dimensional feasibility oracle for offline Phase 7R audit."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Optional, Sequence, Tuple

import numpy as np

from .local_control_types import LocalConstraintDiagnostic, Vec2


LOCAL_PROJECTION_FORENSICS_SCHEMA_VERSION = "rvt-local-projection-forensics/v1"


@dataclass(frozen=True)
class IndependentFeasibilityResult:
    classification: str
    feasible: Optional[bool]
    witness_action: Optional[Vec2]
    witness_primal_residual: Optional[float]
    proof_kind: str
    proof_constraint_keys: Tuple[str, ...]
    numerical_tolerance: float

    def source(self) -> dict:
        return asdict(self)


def action_primal_residual(
    action: Vec2,
    constraints: Sequence[LocalConstraintDiagnostic],
    acceleration_limit: float,
) -> float:
    value = np.asarray(action, dtype=np.float64)
    residuals = [float(np.linalg.norm(value)) - float(acceleration_limit)]
    residuals.extend(
        item.lower_bound_meters_per_second_squared
        - float(np.dot(np.asarray(item.outward_normal, dtype=np.float64), value))
        for item in constraints
    )
    return max(0.0, *residuals)


def independent_local_feasibility(
    constraints: Sequence[LocalConstraintDiagnostic],
    acceleration_limit: float,
) -> IndependentFeasibilityResult:
    """Check disk/half-space feasibility by minimum-norm vertex enumeration.

    This implementation does not call or share candidates with the production
    projection. It asks a different question: whether the minimum-norm point of
    the half-space intersection lies inside the acceleration disk.
    """
    radius = float(acceleration_limit)
    if not math.isfinite(radius) or radius <= 0.0:
        return IndependentFeasibilityResult(
            "D_malformed_constraint_system", None, None, None,
            "invalid_acceleration_limit", (), 0.0,
        )
    parsed = []
    scale = max(1.0, radius)
    for item in constraints:
        normal = np.asarray(item.outward_normal, dtype=np.float64)
        lower = float(item.lower_bound_meters_per_second_squared)
        if (
            normal.shape != (2,)
            or not bool(np.isfinite(normal).all())
            or not math.isfinite(lower)
            or float(np.linalg.norm(normal)) <= np.finfo(np.float64).tiny
        ):
            return IndependentFeasibilityResult(
                "D_malformed_constraint_system", None, None, None,
                "nonfinite_or_zero_normal", (item.source_key,), 0.0,
            )
        parsed.append((item, normal, lower))
        scale = max(scale, abs(lower), float(np.linalg.norm(normal)) * radius)
    tolerance = 1e-10 * scale

    impossible = tuple(
        item.source_key
        for item, normal, lower in parsed
        if lower > radius * float(np.linalg.norm(normal)) + tolerance
    )
    if impossible:
        return IndependentFeasibilityResult(
            "B_independently_infeasible", False, None, None,
            "single_half_space_exceeds_disk_support", impossible, tolerance,
        )

    def feasible(candidate: np.ndarray) -> bool:
        if float(np.linalg.norm(candidate)) > radius + tolerance:
            return False
        return all(
            float(np.dot(normal, candidate)) >= lower - tolerance
            for _, normal, lower in parsed
        )

    candidates = [np.zeros(2, dtype=np.float64)]
    for _, normal, lower in parsed:
        candidates.append(normal * (lower / float(np.dot(normal, normal))))
    for index, (_, first_normal, first_lower) in enumerate(parsed):
        for _, second_normal, second_lower in parsed[index + 1:]:
            matrix = np.stack((first_normal, second_normal))
            determinant = float(np.linalg.det(matrix))
            determinant_scale = max(
                1.0,
                float(np.linalg.norm(first_normal) * np.linalg.norm(second_normal)),
            )
            if abs(determinant) <= 1e-12 * determinant_scale:
                continue
            candidates.append(np.linalg.solve(
                matrix, np.asarray((first_lower, second_lower), dtype=np.float64)
            ))
    witnesses = [candidate for candidate in candidates if feasible(candidate)]
    if witnesses:
        witness = min(witnesses, key=lambda value: float(np.dot(value, value)))
        action = (float(witness[0]), float(witness[1]))
        return IndependentFeasibilityResult(
            "A_independently_feasible", True, action,
            action_primal_residual(action, constraints, radius),
            "minimum_norm_half_space_vertex", (), tolerance,
        )

    minimum_gap = min(
        (
            abs(lower - radius * float(np.linalg.norm(normal)))
            for _, normal, lower in parsed
        ),
        default=float("inf"),
    )
    if minimum_gap <= 10.0 * tolerance:
        return IndependentFeasibilityResult(
            "C_numerically_ambiguous", None, None, None,
            "boundary_within_numerical_tolerance", (), tolerance,
        )
    return IndependentFeasibilityResult(
        "B_independently_infeasible", False, None, None,
        "empty_half_space_intersection_inside_disk", (), tolerance,
    )
