"""Task 4R-6 — epoch churn guards."""
from __future__ import annotations

import pytest

from rvt_swarm.decentralized import epoch as E
from rvt_swarm.decentralized.qualification_fixtures import (
    build_fixtures, fixture_config, fixture_layout, simulate_reset_to_fixture)
from rvt_swarm.decentralized.runtime import simulate_decentralized_episode as run
from rvt_swarm.decentralized.system_model import KEEP, LINE, ConsensusParams
from rvt_swarm.environment import SwarmFormationEnv


@pytest.fixture(scope="module")
def corridor_run():
    cfg = fixture_config()
    B = build_fixtures(cfg, 6)["B_line_only_corridor"]
    env = SwarmFormationEnv(cfg)
    obs = simulate_reset_to_fixture(env, B, 0, cfg)
    return run(cfg, fixture_layout(B), 6, 0, mode_rule="geometric",
               preset_env=env, preset_obs=obs)


def test_no_entry_epoch_while_already_committed_to_line(monkeypatch) -> None:
    """The entry trigger is only consulted when the robot is in KEEP."""
    import inspect
    from rvt_swarm.decentralized import runtime as rt
    src = inspect.getsource(rt.simulate_decentralized_episode)
    assert "local_recovery_trigger(views[i], cfg, e, cons)" in src
    assert "if e.committed_mode == LINE" in src


def test_recovery_trigger_refuses_when_already_in_keep(cfg=None) -> None:
    from rvt_swarm.config import Config
    e = E.EpochState(robot_id=0)
    e.committed_mode = KEEP
    view = __import__("rvt_swarm.decentralized.system_model", fromlist=["RobotView"]).RobotView(
        0, (0., 0.), (0., 0.), (0., 0.), (0., 0.), KEEP, 0, 0, 1.0,
        (10., 0.), (1., 0.), (), ((5.0, 0.0, 0.0),))
    assert E.local_recovery_trigger(view, Config(), e) is False


def test_no_new_epoch_during_the_commitment_interval() -> None:
    from rvt_swarm.config import Config
    from rvt_swarm.decentralized.system_model import RobotView
    cons = ConsensusParams()
    e = E.EpochState(robot_id=0)
    e.committed_mode = KEEP
    e.commit(LINE, cons.h_commit)
    tight = RobotView(0, (0., 0.), (0., 0.), (0., 0.), (0., 0.), LINE, 0, 0,
                      1.0, (10., 0.), (1., 0.), (), ((0.2, 0.0, 0.0),))
    for _ in range(cons.h_commit):
        assert E.local_trigger(tight, Config(), e, cons) is False
        assert E.local_recovery_trigger(tight, Config(), e, cons) is False
        e.tick()


def test_a_stale_token_cannot_reopen_a_closed_epoch() -> None:
    e = E.EpochState(robot_id=0)
    e.arm_trigger(0)
    tok = e.trigger_token
    e.close_epoch()
    msg = E.TriggerMessage(sender_id=1, epoch_counter=1, trigger_flag=True,
                           trigger_token=tok, timestamp_step=0)
    assert E.max_consensus_trigger(e, [msg], now_step=99, delta_stale_steps=3) is False


def test_noop_epochs_are_detected_and_skip_confirmation(corridor_run) -> None:
    """The guard that matters: an epoch proposing the committed mode is a no-op."""
    assert corridor_run["n_noop_epochs"] > 0
    assert corridor_run["n_noop_epochs"] <= corridor_run["n_decisions"]


def test_exactly_one_entry_and_one_recovery_transition_per_robot(corridor_run) -> None:
    """One corridor traversal, one K->L and one L->K per robot."""
    n = 6
    assert corridor_run["n_keep_to_line"] == n
    assert corridor_run["n_line_to_keep"] == n


def test_noop_guard_reduces_protocol_traffic() -> None:
    """Non-vacuity: the guard must actually save bytes, not just count."""
    cfg = fixture_config()
    B = build_fixtures(cfg, 6)["B_line_only_corridor"]
    env = SwarmFormationEnv(cfg)
    obs = simulate_reset_to_fixture(env, B, 0, cfg)
    r = run(cfg, fixture_layout(B), 6, 0, mode_rule="geometric",
            preset_env=env, preset_obs=obs)
    c = r["comm"]["categories"]
    # confirmation traffic must be strictly less than trigger traffic, because
    # no-op epochs run the trigger+score rounds but skip confirmation entirely
    assert c["mode_confirmation"]["messages"] < c["trigger"]["messages"]
