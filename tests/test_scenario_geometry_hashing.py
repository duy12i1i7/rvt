from dataclasses import replace

import pytest

from rvt_swarm.phase8.scenario import (
    FINAL_TEST_SPLIT,
    SPLIT_NAMES,
    TRAIN_SPLIT,
    ObstaclePrimitive,
    generate_layouts,
)


def test_geometry_generation_is_deterministic_and_canonical():
    first = generate_layouts(TRAIN_SPLIT)
    second = generate_layouts(TRAIN_SPLIT)
    assert first == second
    assert tuple(item.geometry_sha256() for item in first) == tuple(
        item.geometry_sha256() for item in second
    )


def test_geometry_hash_changes_when_physical_geometry_changes():
    layout = generate_layouts(TRAIN_SPLIT)[0]
    changed = replace(
        layout,
        static_obstacles=layout.static_obstacles
        + (ObstaclePrimitive("circle", (0.0, 0.0, 0.35)),),
    )
    assert changed.geometry_sha256() != layout.geometry_sha256()


def test_final_geometry_enumeration_is_sealed_by_default():
    with pytest.raises(PermissionError, match="sealed"):
        generate_layouts(FINAL_TEST_SPLIT)


def test_all_split_geometry_and_parameter_hashes_are_disjoint_under_qualification():
    geometry = set()
    parameters = set()
    for split in SPLIT_NAMES:
        layouts = generate_layouts(
            split, sealed_generation_authorized=split == FINAL_TEST_SPLIT
        )
        for layout in layouts:
            assert layout.geometry_sha256() not in geometry
            assert layout.parameter_tuple_sha256() not in parameters
            geometry.add(layout.geometry_sha256())
            parameters.add(layout.parameter_tuple_sha256())
