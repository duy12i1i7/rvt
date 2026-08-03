from dataclasses import replace

import pytest

from rvt_swarm.decentralized.ego_graph_v2 import EGO_GRAPH_SCHEMA_VERSION
from rvt_swarm.phase8.targets import (
    LOCAL_VIEW_LABEL_SCHEMA_VERSION,
    LocalViewRecoverabilitySample,
    validate_local_view_grouping,
)
from rvt_swarm.topology_registry import COMPACT, KEEP, LINE


def _sample(robot=0, candidate=COMPACT, split="train", label=1):
    return LocalViewRecoverabilitySample(
        LOCAL_VIEW_LABEL_SCHEMA_VERSION,
        "episode-1", "event-1", robot, candidate,
        EGO_GRAPH_SCHEMA_VERSION, "f" * 64, COMPACT, 5, "F2", "g" * 64,
        split, "r" * 64, label, "LINE_ONLY_SUCCESS", 1.5,
        "nominal", "d" * 40,
    )


def test_many_robot_views_share_one_event_label_without_becoming_independent():
    samples = tuple(_sample(robot=index) for index in range(5))
    assert validate_local_view_grouping(samples) == ()
    assert {item.decision_event_id for item in samples} == {"event-1"}


def test_event_rows_cannot_cross_splits_or_disagree_on_candidate_label():
    split_leak = (_sample(), _sample(robot=1, split="validation"))
    assert validate_local_view_grouping(split_leak) == ("event_split_leak:event-1",)
    conflict = (_sample(), _sample(robot=1, label=0))
    assert validate_local_view_grouping(conflict) == ("shared_label_conflict:event-1",)


def test_keep_is_rejected_from_primary_local_view_labels():
    with pytest.raises(ValueError, match="KEEP"):
        _sample(candidate=KEEP)


def test_two_candidates_remain_correlated_in_the_same_event():
    samples = (_sample(candidate=COMPACT, label=0), _sample(candidate=LINE, label=1))
    assert validate_local_view_grouping(samples) == ()
