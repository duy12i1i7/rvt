"""Task 6-2 — the V3 forward-opening recovery event."""
from __future__ import annotations

import pytest

from rvt_swarm.config import Config
from rvt_swarm.decentralized import epoch as E
from rvt_swarm.decentralized.system_model import KEEP, LINE, RobotView

CFG = Config()


def v(obstacles, mode=LINE, neighbours=()):
    return RobotView(0, (0., 0.), (0.9, 0.), (0., 0.), (0., 0.), mode, 0, 0,
                     1.0, (10., 0.), (1., 0.), tuple(neighbours), tuple(obstacles))


def inside_epoch() -> E.EpochState:
    e = E.EpochState(robot_id=0)
    e.committed_mode = LINE
    e.passage_latch = E.LATCH_INSIDE
    return e


WALLS_AHEAD = ((0.5, 0.9, 0.35), (0.5, -0.9, 0.35))
WALLS_BEHIND = ((-0.5, 0.9, 0.35), (-0.5, -0.9, 0.35))


def test_forward_opening_is_false_with_walls_ahead() -> None:
    assert E.forward_opening_evidence(v(WALLS_AHEAD), CFG) is False


def test_forward_opening_is_true_once_the_walls_are_behind() -> None:
    assert E.forward_opening_evidence(v(WALLS_BEHIND), CFG) is True


def test_forward_opening_ignores_obstacles_outside_the_sector() -> None:
    """A wall far off to the side must not block the event."""
    assert E.forward_opening_evidence(v(((0.5, 3.0, 0.35),)), CFG) is True


def test_evidence_requires_persistence() -> None:
    e = inside_epoch()
    fired = [E.recovery_evidence_v3(v(WALLS_BEHIND), CFG, e) for _ in range(4)]
    assert fired == [False, False, True, True], fired
    assert E.L_TRIGGER == 3


def test_persistence_streak_resets_when_evidence_lapses() -> None:
    e = inside_epoch()
    E.recovery_evidence_v3(v(WALLS_BEHIND), CFG, e)
    E.recovery_evidence_v3(v(WALLS_AHEAD), CFG, e)      # lapse
    assert e.forward_open_streak == 0
    assert E.recovery_evidence_v3(v(WALLS_BEHIND), CFG, e) is False


def test_evidence_requires_line_mode() -> None:
    e = inside_epoch()
    e.committed_mode = KEEP
    for _ in range(5):
        assert E.recovery_evidence_v3(v(WALLS_BEHIND, mode=KEEP), CFG, e) is False


def test_isolated_robot_is_trusted_with_its_own_evidence() -> None:
    """Requiring support it cannot obtain would freeze an isolated robot."""
    e = inside_epoch()
    assert E.peer_support_for_recovery(v(WALLS_BEHIND), e) == 1.0


def test_peer_support_counts_only_one_hop_neighbours_in_line() -> None:
    from rvt_swarm.decentralized.system_model import NeighbourRecord

    def nb(i, mode):
        return NeighbourRecord(i, (0.9, 0.), (0., 0.), (0., 0.), (0., 0.),
                               mode, 0, 0, 2, True)
    e = inside_epoch()
    all_line = v(WALLS_BEHIND, neighbours=[nb(1, LINE), nb(2, LINE)])
    half = v(WALLS_BEHIND, neighbours=[nb(1, LINE), nb(2, KEEP)])
    none = v(WALLS_BEHIND, neighbours=[nb(1, KEEP), nb(2, KEEP)])
    assert E.peer_support_for_recovery(all_line, e) == 1.0
    assert E.peer_support_for_recovery(half, e) == 0.5
    assert E.peer_support_for_recovery(none, e) == 0.0


def test_arming_requires_the_passage_latch() -> None:
    e = E.EpochState(robot_id=0)
    e.committed_mode = LINE
    e.passage_latch = E.LATCH_BEFORE_ENTRY          # not yet inside
    for _ in range(5):
        assert E.recovery_armable(v(WALLS_BEHIND), CFG, e) is False


def test_the_event_never_reads_a_global_exit_plane() -> None:
    import inspect
    for fn in (E.forward_opening_evidence, E.recovery_evidence_v3,
               E.recovery_armable, E.peer_support_for_recovery):
        src = inspect.getsource(fn)
        # Scan the CODE, not the docstring: the docstrings legitimately say
        # "no exit plane, no centroid", and scanning raw text flags the very
        # disclaimer that documents the property.
        body = src.split('"""')[2] if src.count('"""') >= 2 else src
        for banned in ("exit_x", "exit_plane", "centroid", "positions"):
            assert banned not in body, (fn.__name__, banned)
