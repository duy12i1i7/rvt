"""Executable tests for the exact-centerline S3 scientific addendum."""

from __future__ import annotations

import math

import pytest

from rvt_swarm.phase9c_rb.s3_geometry import (
    CENTERLINE_NEUTRAL,
    NEGATIVE,
    POSITIVE,
    classify_s3_signed_coordinate,
    measure_s3_opposing_boundaries,
)


@pytest.mark.parametrize("zero", [0.0, -0.0])
def test_both_signed_zeros_are_centerline_neutral(zero: float) -> None:
    assert classify_s3_signed_coordinate(zero) == CENTERLINE_NEUTRAL


def test_classification_has_no_epsilon() -> None:
    negative = math.nextafter(0.0, -math.inf)
    positive = math.nextafter(0.0, math.inf)
    assert classify_s3_signed_coordinate(negative) == NEGATIVE
    assert classify_s3_signed_coordinate(0.0) == CENTERLINE_NEUTRAL
    assert classify_s3_signed_coordinate(positive) == POSITIVE


def test_centerline_support_is_present_but_not_a_boundary() -> None:
    measurement = measure_s3_opposing_boundaries(
        ((1.0, -1.35, 0.35), (1.0, 0.0, 0.8), (1.0, 1.35, 0.35)),
        mission_direction=(1.0, 0.0),
        support_origin_world_meters=(0.0, 0.0),
        local_frame_center_world_meters=(0.0, 0.0),
        local_frame_normal=(0.0, 1.0),
        lookahead_distance_meters=2.0,
    )
    assert measurement.complete_open_observation is False
    assert measurement.complete_observation is True
    assert measurement.measured_width_meters == pytest.approx(2.0)
    assert [row.classification for row in measurement.projections] == [
        NEGATIVE, CENTERLINE_NEUTRAL, POSITIVE,
    ]
    assert measurement.selected_negative_indices == (0,)
    assert measurement.selected_positive_indices == (2,)


def test_centerline_only_observation_uses_existing_missing_side_semantics() -> None:
    measurement = measure_s3_opposing_boundaries(
        ((1.0, -0.0, 0.8),),
        mission_direction=(1.0, 0.0),
        support_origin_world_meters=(0.0, 0.0),
        local_frame_center_world_meters=(0.0, 0.0),
        local_frame_normal=(0.0, 1.0),
        lookahead_distance_meters=2.0,
    )
    assert measurement.complete_open_observation is False
    assert measurement.complete_observation is False
    assert measurement.measured_width_meters is None
    assert measurement.projections[0].classification == CENTERLINE_NEUTRAL


def test_nonfinite_coordinate_uses_existing_fail_closed_guard() -> None:
    with pytest.raises(ValueError, match="must be finite"):
        classify_s3_signed_coordinate(math.nan)
    with pytest.raises(ValueError, match="must be finite"):
        classify_s3_signed_coordinate(math.inf)


def test_pairing_is_token_order_invariant() -> None:
    tokens = ((1.0, -1.35, 0.35), (1.0, 0.0, 0.8), (1.0, 1.35, 0.35))

    def projection(container):
        result = measure_s3_opposing_boundaries(
            container,
            mission_direction=(1.0, 0.0),
            support_origin_world_meters=(0.0, 0.0),
            local_frame_center_world_meters=(0.0, 0.0),
            local_frame_normal=(0.0, 1.0),
            lookahead_distance_meters=2.0,
        )
        return result.d_neg_meters, result.d_pos_meters, result.measured_width_meters

    assert projection(tokens) == projection(tuple(reversed(tokens)))


def test_pairing_is_translation_and_rotation_invariant() -> None:
    baseline = measure_s3_opposing_boundaries(
        ((1.0, -1.35, 0.35), (1.0, 0.0, 0.8), (1.0, 1.35, 0.35)),
        mission_direction=(1.0, 0.0),
        support_origin_world_meters=(0.0, 0.0),
        local_frame_center_world_meters=(0.0, 0.0),
        local_frame_normal=(0.0, 1.0),
        lookahead_distance_meters=2.0,
    )
    translated = measure_s3_opposing_boundaries(
        ((1.0, -1.35, 0.35), (1.0, 0.0, 0.8), (1.0, 1.35, 0.35)),
        mission_direction=(1.0, 0.0),
        support_origin_world_meters=(2.0, 1.0),
        local_frame_center_world_meters=(2.0, 1.0),
        local_frame_normal=(0.0, 1.0),
        lookahead_distance_meters=2.0,
    )
    rotated = measure_s3_opposing_boundaries(
        ((1.35, 1.0, 0.35), (0.0, 1.0, 0.8), (-1.35, 1.0, 0.35)),
        mission_direction=(0.0, 1.0),
        support_origin_world_meters=(0.0, 0.0),
        local_frame_center_world_meters=(0.0, 0.0),
        local_frame_normal=(-1.0, 0.0),
        lookahead_distance_meters=2.0,
    )
    assert translated.measured_width_meters == baseline.measured_width_meters
    assert rotated.measured_width_meters == baseline.measured_width_meters
    assert tuple(row.classification for row in translated.projections) == tuple(
        row.classification for row in baseline.projections)
    assert tuple(row.classification for row in rotated.projections) == tuple(
        row.classification for row in baseline.projections)
