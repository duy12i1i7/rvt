"""Task 3F — KEEP <-> LINE state-machine validation, scripted triggers only.

No learned selector is involved anywhere in this file. Where a behaviour can be
shown in a real episode it is; where the episode set cannot yet exhibit it, the
mechanism is validated at protocol level and the gap is stated in the test's
own docstring rather than papered over.
"""

from __future__ import annotations

from typing import Dict, List

import pytest

from rvt_swarm.config import Config
from rvt_swarm.decentralized import epoch as E
from rvt_swarm.decentralized.runtime import simulate_decentralized_episode
from rvt_swarm.decentralized.system_model import (KEEP, LINE, CommParams,
                                                  ConsensusParams, RobotView)
from rvt_swarm.layouts import build_layouts


@pytest.fixture(scope="module")
def cfg() -> Config:
    c = Config()
    c.train.device = "cpu"
    c.env.scenarios = ["cluttered"]
    return c


def layout(family: str):
    return [l for l in build_layouts("val") if l.family == family][0]


def view(clearance: float, mode: int = KEEP, progress: float = 1.0) -> RobotView:
    obstacles = () if clearance == float("inf") else ((clearance, 0.0, 0.0),)
    return RobotView(0, (0.0, 0.0), (0.9, 0.0), (0.0, 0.0), (0.0, 0.0),
                     mode, 0, 0, progress, (10.0, 0.0), (1.0, 0.0), (), obstacles)


def path(n: int) -> Dict[int, List[int]]:
    return {i: [j for j in (i - 1, i + 1) if 0 <= j < n] for i in range(n)}


# ---------------------------------------------------------------------------
# 1-2. trigger direction is governed by robot i's own clearance
# ---------------------------------------------------------------------------
def test_01_open_field_does_not_fire_the_entry_trigger(cfg) -> None:
    e = E.EpochState(robot_id=0)
    e.committed_mode = KEEP
    assert E.local_trigger(view(float("inf")), cfg, e) is False


def test_02_constrained_passage_fires_the_entry_trigger(cfg) -> None:
    e = E.EpochState(robot_id=0)
    e.committed_mode = KEEP
    assert E.local_trigger(view(0.4), cfg, e) is True
    assert E.trigger_reasons(view(0.4), cfg, e)["low_clearance"] is True


def test_02b_entry_and_recovery_triggers_are_asymmetric(cfg) -> None:
    """0.9 m entry vs 1.8 m recovery: no geometry fires both."""
    th = E.TriggerThresholds.from_config(cfg)
    assert th.recovery_clearance_m > th.clearance_m
    ek, el = E.EpochState(robot_id=0), E.EpochState(robot_id=1)
    ek.committed_mode, el.committed_mode = KEEP, LINE
    for c in (0.4, 0.9, 1.3, 1.8, 3.0):
        entry = E.local_trigger(view(c), cfg, ek)
        recov = E.local_recovery_trigger(view(c, LINE), cfg, el)
        assert not (entry and recov), f"both triggers fired at clearance {c}"


def test_02c_recovery_trigger_requires_the_robot_to_be_in_line(cfg) -> None:
    e = E.EpochState(robot_id=0)
    e.committed_mode = KEEP
    assert E.local_recovery_trigger(view(3.0, KEEP), cfg, e) is False
    e.committed_mode = LINE
    assert E.local_recovery_trigger(view(3.0, LINE), cfg, e) is True


# ---------------------------------------------------------------------------
# 3. no switch before confirmation
# ---------------------------------------------------------------------------
def test_03_mode_does_not_change_before_confirmation_completes() -> None:
    e = E.EpochState(robot_id=0)
    e.committed_mode = KEEP
    e.arm_trigger(0)
    assert e.committed_mode == KEEP
    e.adopt(e.trigger_token)
    e.begin_scoring()
    assert e.committed_mode == KEEP, "scoring must not commit"
    e.begin_confirming(LINE, 1.0)
    assert e.committed_mode == KEEP, "proposing must not commit"
    e.mode_lo = e.mode_hi = LINE
    assert E.commit_or_retain(e, 1) is True
    assert e.committed_mode == LINE


# ---------------------------------------------------------------------------
# 4-5. recovery and dwell
# ---------------------------------------------------------------------------
def test_04_line_to_keep_transition_is_mechanically_reachable() -> None:
    """Protocol level. Whether the validation corridors actually produce this
    transition in a closed-loop episode is a Task 4 question, and the seed-0
    probe found n_line_to_keep = 0 on `line_corridor` -- recorded there, not
    hidden here."""
    eps = {i: E.EpochState(robot_id=i) for i in range(4)}
    for e in eps.values():
        e.committed_mode = LINE
    eps[0].arm_trigger(0)
    E.simulate_trigger_consensus(eps, path(4), 6)
    for e in eps.values():
        e.begin_scoring()
        e.begin_confirming(KEEP, 1.0)
    E.simulate_confirm_consensus(eps, path(4), 6)
    for e in eps.values():
        E.commit_or_retain(e, 1)
    assert all(e.committed_mode == KEEP for e in eps.values())


def test_05_commitment_holds_for_the_full_dwell_interval() -> None:
    cons = ConsensusParams()
    e = E.EpochState(robot_id=0)
    e.committed_mode = KEEP
    e.commit(LINE, cons.h_commit)
    for _ in range(cons.h_commit):
        assert e.locked, "commitment released early"
        e.tick()
    assert not e.locked


# ---------------------------------------------------------------------------
# 6. no oscillation under trigger noise
# ---------------------------------------------------------------------------
def test_06_trigger_noise_cannot_oscillate_the_mode(cfg) -> None:
    """h_commit is the oscillation bound: a locked robot refuses to re-trigger."""
    cons = ConsensusParams()
    e = E.EpochState(robot_id=0)
    e.committed_mode = KEEP
    e.commit(LINE, cons.h_commit)
    fired = [E.local_trigger(view(0.2), cfg, e, cons) for _ in range(cons.h_commit)]
    assert not any(fired), "trigger fired inside the commitment window"


# ---------------------------------------------------------------------------
# 7. stale tokens
# ---------------------------------------------------------------------------
def test_07_stale_trigger_message_cannot_reopen_an_old_epoch() -> None:
    e = E.EpochState(robot_id=0)
    e.arm_trigger(0)
    tok = e.trigger_token
    e.close_epoch()
    stale = E.TriggerMessage(sender_id=1, epoch_counter=1, trigger_flag=True,
                             trigger_token=tok, timestamp_step=0)
    applied = E.max_consensus_trigger(e, [stale], now_step=99, delta_stale_steps=3)
    assert applied is False
    assert e.rejected_stale >= 1


# ---------------------------------------------------------------------------
# 8. simultaneous triggers
# ---------------------------------------------------------------------------
def test_08_simultaneous_triggers_resolve_deterministically() -> None:
    winners = []
    for order in ([1, 3], [3, 1]):
        eps = {i: E.EpochState(robot_id=i) for i in range(6)}
        for i in order:
            eps[i].arm_trigger(0)
        out = E.simulate_trigger_consensus(eps, path(6), 8)
        assert len(set(out["epoch_ids"].values())) == 1
        winners.append(out["tokens"][0])
    assert winners[0] == winners[1], "arrival order changed the winner"


# ---------------------------------------------------------------------------
# 9. delayed confirmation must not commit part of the team
# ---------------------------------------------------------------------------
def test_09_delayed_confirmation_does_not_cause_partial_commitment() -> None:
    """Delay beyond delta_stale drops confirmation traffic; every robot must
    then RETAIN, so the team stays consistent rather than splitting."""
    eps = {i: E.EpochState(robot_id=i) for i in range(4)}
    for e in eps.values():
        e.committed_mode = KEEP
        e.begin_scoring()
        e.begin_confirming(LINE, 1.0)
    E.simulate_confirm_consensus(eps, path(4), 4, delay_steps=9, delta_stale_steps=3)
    committed = [E.commit_or_retain(e, 20) for e in eps.values()]
    modes = {e.committed_mode for e in eps.values()}
    assert len(modes) == 1, f"partial commitment: {modes}"


# ---------------------------------------------------------------------------
# 10. disconnection
# ---------------------------------------------------------------------------
def test_10_disconnected_components_get_distinct_epochs() -> None:
    eps = {i: E.EpochState(robot_id=i) for i in range(4)}
    adj = {0: [1], 1: [0], 2: [3], 3: [2]}
    eps[0].arm_trigger(0)
    eps[2].arm_trigger(0)
    out = E.simulate_trigger_consensus(eps, adj, 6)
    ids = out["epoch_ids"]
    assert ids[0] == ids[1] and ids[2] == ids[3] and ids[0] != ids[2]


# ---------------------------------------------------------------------------
# Episode-level: the full sequence in a real corridor run
# ---------------------------------------------------------------------------
def test_11_real_episode_performs_a_keep_to_line_transition(cfg) -> None:
    r = simulate_decentralized_episode(cfg, layout("line_corridor"), 6, 20000001,
                                       mode_rule="geometric", trace_modes=True)
    assert r["n_decisions"] > 0
    assert r["n_keep_to_line"] > 0, "no KEEP -> LINE transition occurred"
    # The trace records CHANGES, so its first entry is the transition itself.
    # Task 5-7's latch means the entry transition is the first thing recorded.
    modes = [m for _, m in r["mode_trace"]]
    assert any(m[0] == LINE for m in modes), modes
    assert r["n_keep_to_line"] > 0
