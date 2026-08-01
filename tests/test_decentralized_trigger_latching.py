"""Task 5-7 — passage-lifecycle latching."""
from __future__ import annotations

import pytest

from rvt_swarm.config import Config
from rvt_swarm.decentralized import epoch as E
from rvt_swarm.decentralized.qualification_fixtures import (
    build_fixtures, fixture_config, fixture_layout, simulate_reset_to_fixture)
from rvt_swarm.decentralized.runtime import simulate_decentralized_episode as run
from rvt_swarm.decentralized.system_model import KEEP, LINE, ConsensusParams, RobotView
from rvt_swarm.environment import SwarmFormationEnv

CFG = Config()


def view(clear: float, mode: int) -> RobotView:
    return RobotView(0, (0., 0.), (0.9, 0.), (0., 0.), (0., 0.), mode, 0, 0,
                     1.0, (10., 0.), (1., 0.), (), ((clear, 0., 0.),))


def fresh(mode=KEEP) -> E.EpochState:
    e = E.EpochState(robot_id=0)
    e.committed_mode = mode
    return e


def test_01_entry_disabled_while_committed_to_line() -> None:
    e = fresh(LINE)
    assert E.entry_trigger_allowed(e) is False


def test_02_second_entry_epoch_is_suppressed_after_a_confirmed_transition() -> None:
    e = fresh(KEEP)
    assert E.entry_trigger_allowed(e)
    E.note_transition(e, LINE)
    e.committed_mode = LINE
    assert e.passage_latch == E.LATCH_INSIDE
    assert E.entry_trigger_allowed(e) is False


def test_03_recovery_disabled_before_the_passage_is_entered() -> None:
    e = fresh(KEEP)
    assert E.recovery_trigger_allowed(e) is False


def test_04_repeated_recovery_is_suppressed_after_a_confirmed_transition() -> None:
    e = fresh(KEEP)
    E.note_transition(e, LINE); e.committed_mode = LINE
    E.note_transition(e, KEEP); e.committed_mode = KEEP
    assert e.passage_latch == E.LATCH_COMPLETE
    assert E.recovery_trigger_allowed(e) is False
    assert E.entry_trigger_allowed(e) is False


def test_06_no_epoch_during_the_commitment_interval() -> None:
    cons = ConsensusParams()
    e = fresh(KEEP)
    e.commit(LINE, cons.h_commit)
    for _ in range(cons.h_commit):
        assert E.latched_local_trigger(view(0.2, LINE), CFG, e, cons) is False
        e.tick()


def test_07_hysteresis_uses_only_local_state() -> None:
    import inspect
    src = inspect.getsource(E.update_passage_latch)
    # Check the CODE, not the prose: the docstring legitimately explains what
    # the function does not do, so scanning raw text flags its own disclaimer.
    body = src.split('"""')[2] if src.count('"""') >= 2 else src
    for banned in ("neighbours", "peer", "global", "all_", "positions"):
        assert banned not in body, banned


def test_08_no_central_bottleneck_tracker_exists() -> None:
    import inspect
    src = inspect.getsource(E)
    for banned in ("BottleneckTracker", "bottleneck_registry", "global_passage"):
        assert banned not in src


def test_10_a_later_distinct_bottleneck_rearms_the_latch() -> None:
    e = fresh(KEEP)
    E.note_transition(e, LINE); e.committed_mode = LINE
    E.note_transition(e, KEEP); e.committed_mode = KEEP
    assert e.passage_latch == E.LATCH_COMPLETE
    for _ in range(E.rearm_open_steps(CFG)):
        E.update_passage_latch(e, view(5.0, KEEP), CFG)
    assert e.passage_latch == E.LATCH_BEFORE_ENTRY
    assert E.entry_trigger_allowed(e)


def test_rearm_requires_sustained_open_clearance() -> None:
    """Non-vacuity: a brief opening must NOT re-arm."""
    e = fresh(KEEP)
    E.note_transition(e, LINE); e.committed_mode = LINE
    E.note_transition(e, KEEP); e.committed_mode = KEEP
    for _ in range(E.rearm_open_steps(CFG) - 1):
        E.update_passage_latch(e, view(5.0, KEEP), CFG)
    E.update_passage_latch(e, view(0.3, KEEP), CFG)      # closes again
    assert e.passage_latch == E.LATCH_COMPLETE


def test_entry_reasons_exclude_formation_error_and_periodic_expiry() -> None:
    assert set(E.ENTRY_TRIGGER_REASONS) == {"low_clearance", "low_progress"}
    assert "interval_expiry" not in E.ENTRY_TRIGGER_REASONS
    assert "local_formation_error" not in E.ENTRY_TRIGGER_REASONS


def test_open_field_opens_no_epochs() -> None:
    cfg = fixture_config()
    A = build_fixtures(cfg, 6)["A_open_keep"]
    env = SwarmFormationEnv(cfg)
    obs = simulate_reset_to_fixture(env, A, 0, cfg)
    r = run(cfg, fixture_layout(A), 6, 0, mode_rule="geometric",
            preset_env=env, preset_obs=obs)
    assert r["n_decisions"] == 0
    assert r["n_keep_to_line"] == 0


def test_corridor_produces_exactly_one_transition_of_each_kind() -> None:
    cfg = fixture_config()
    B = build_fixtures(cfg, 6)["B_line_only_corridor"]
    env = SwarmFormationEnv(cfg)
    obs = simulate_reset_to_fixture(env, B, 0, cfg)
    r = run(cfg, fixture_layout(B), 6, 0, mode_rule="geometric",
            preset_env=env, preset_obs=obs)
    assert r["n_keep_to_line"] == 6      # one epoch, all six robots
    assert r["n_line_to_keep"] == 6
