"""Executable S3 opposing-boundary geometry.

This module implements the additive owner contracts
``rvt-s3-opposing-boundary-pairing/v1`` and
``rvt-s3-exact-centerline-support/v1``.  It consumes only an ego-relative
support set and the local reference frame supplied in ``RobotView``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Sequence, Tuple

Vec2 = Tuple[float, float]
ObstacleToken = Tuple[float, float, float]

NEGATIVE = "NEGATIVE"
POSITIVE = "POSITIVE"
CENTERLINE_NEUTRAL = "CENTERLINE_NEUTRAL"


def classify_s3_signed_coordinate(value: float) -> str:
    """Classify one finite signed coordinate without a numerical tolerance."""
    coordinate = float(value)
    if not math.isfinite(coordinate):
        raise ValueError("S3 signed support coordinate must be finite")
    if coordinate == 0.0:
        return CENTERLINE_NEUTRAL
    if coordinate < 0.0:
        return NEGATIVE
    return POSITIVE


@dataclass(frozen=True)
class S3SupportProjection:
    token_index: int
    signed_center_coordinate_meters: float
    signed_inner_surface_coordinate_meters: Optional[float]
    classification: str


@dataclass(frozen=True)
class S3OpposingBoundaryMeasurement:
    complete_open_observation: bool
    complete_observation: bool
    measured_width_meters: Optional[float]
    d_neg_meters: Optional[float]
    d_pos_meters: Optional[float]
    selected_negative_indices: Tuple[int, ...]
    selected_positive_indices: Tuple[int, ...]
    projections: Tuple[S3SupportProjection, ...]


def measure_s3_opposing_boundaries(
    obstacles: Sequence[ObstacleToken],
    *,
    mission_direction: Vec2,
    support_origin_world_meters: Vec2,
    local_frame_center_world_meters: Vec2,
    local_frame_normal: Vec2,
    lookahead_distance_meters: float,
) -> S3OpposingBoundaryMeasurement:
    """Measure the nearest strict NEG/POS free surfaces in the S3 lookahead.

    Exact signed zero, including either IEEE-754 signed-zero representation,
    is centerline-neutral.  The physical token remains in ``obstacles`` and
    still makes the observation non-open; only boundary-pair eligibility is
    removed.
    """
    direction = tuple(map(float, mission_direction))
    origin = tuple(map(float, support_origin_world_meters))
    center = tuple(map(float, local_frame_center_world_meters))
    normal = tuple(map(float, local_frame_normal))
    lookahead = float(lookahead_distance_meters)
    values = (*direction, *origin, *center, *normal, lookahead)
    if not all(math.isfinite(value) for value in values):
        raise ValueError("S3 frame and lookahead must be finite")
    if lookahead < 0.0:
        raise ValueError("S3 lookahead must be nonnegative")
    if math.hypot(*direction) <= 0.0 or math.hypot(*normal) <= 0.0:
        raise ValueError("S3 frame axes must be nonzero")

    negative: list[tuple[float, int]] = []
    positive: list[tuple[float, int]] = []
    projections: list[S3SupportProjection] = []
    participating_count = 0
    for token_index, token in enumerate(obstacles):
        ox, oy, radius = map(float, token)
        if not all(math.isfinite(value) for value in (ox, oy, radius)) or radius < 0.0:
            raise ValueError("S3 support tokens must be finite with nonnegative radius")
        longitudinal = ox * direction[0] + oy * direction[1]
        if not (0.0 <= longitudinal <= lookahead):
            continue
        participating_count += 1
        world_center = (origin[0] + ox, origin[1] + oy)
        signed_center = (
            (world_center[0] - center[0]) * normal[0]
            + (world_center[1] - center[1]) * normal[1]
        )
        center_classification = classify_s3_signed_coordinate(signed_center)
        if center_classification == CENTERLINE_NEUTRAL:
            signed_inner = None
            classification = CENTERLINE_NEUTRAL
        elif center_classification == NEGATIVE:
            signed_inner = signed_center + radius
            classification = classify_s3_signed_coordinate(signed_inner)
        else:
            signed_inner = signed_center - radius
            classification = classify_s3_signed_coordinate(signed_inner)

        projections.append(S3SupportProjection(
            token_index=token_index,
            signed_center_coordinate_meters=signed_center,
            signed_inner_surface_coordinate_meters=signed_inner,
            classification=classification,
        ))
        if classification == NEGATIVE:
            negative.append((float(signed_inner), token_index))
        elif classification == POSITIVE:
            positive.append((float(signed_inner), token_index))

    d_neg = max((value for value, _ in negative), default=None)
    d_pos = min((value for value, _ in positive), default=None)
    selected_negative = tuple(
        index for value, index in negative if value == d_neg
    )
    selected_positive = tuple(
        index for value, index in positive if value == d_pos
    )
    width = d_pos - d_neg if d_neg is not None and d_pos is not None else None
    complete_open = participating_count == 0
    complete_observation = complete_open or width is not None
    return S3OpposingBoundaryMeasurement(
        complete_open_observation=complete_open,
        complete_observation=complete_observation,
        measured_width_meters=width,
        d_neg_meters=d_neg,
        d_pos_meters=d_pos,
        selected_negative_indices=selected_negative,
        selected_positive_indices=selected_positive,
        projections=tuple(projections),
    )
