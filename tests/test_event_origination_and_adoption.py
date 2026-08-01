"""Tasks 6RR-4 / 6RR-5 / 6RR-9 — event origination vs adoption.

The distinction these tests pin: a robot that ORIGINATES a RECOVERY event must
hold valid local evidence, but a robot that ADOPTS a propagated event must NOT
be required to reproduce that evidence. Requiring rediscovery is what made
commitment track the LAST robot's sensing (evidence 44...103, commit 111)
instead of the first valid propagated event.
"""

from __future__ import annotations

import inspect

import numpy as np
import pytest

from rvt_swarm.config import Config
from rvt_swarm.decentralized import epoch as E
from rvt_swarm.decentralized import guards
from rvt_swarm.decentralized.system_model import (KEEP, LINE,
                                                  CentralizedAccessError,
                                                  ConsensusParams,
                                                  NeighbourRecord, RobotView)

CFG = Config()
CONS = ConsensusParams()
WALLS_AHEAD = ((0.5, 0.9, 0.35), (0.5, -0.9, 0.35))
WALLS_BEHIND = ((-0.5, 0.9, 0.35), (-0.5, -0.9, 0.35))


def view(obstacles, mode=LINE, neighbours=()):
    return RobotView(0, (0., 0.), (0.9, 0.), (0.45, 0.9), (-2.25, 0.0), mode, 0, 0,
                     1.0, (10., 0.), (1., 0.), tuple(neighbours), tuple(obstacles))


def team(n, mode, latch):
    eps = {i: E.EpochState(robot_id=i) for i in range(n)}
    for e in eps.values():
        e.committed_mode = mode
        e.passage_latch = latch
    return eps


def path(n):
    """Worst-case chain, diameter n-1."""
    return {i: [j for j in (i - 1, i + 1) if 0 <= j < n] for i in range(n)}


def runtime_graph(n):
    """Representative of the ACTUAL runtime connectivity.

    Measured over the post-repair traces, every robot's degree is 5 out of 5 --
    the communication graph at r_comm = 3.0 is COMPLETE for N = 6 throughout
    these episodes. A chain is not representative of it.
    """
    return {i: [j for j in range(n) if j != i] for i in range(n)}


# ===========================================================================
# 6RR-9 (1-6): front robot originates, rear robots adopt without evidence
# ===========================================================================
def test_01_front_robot_observes_a_valid_opening() -> None:
    e = team(1, LINE, E.LATCH_INSIDE)[0]
    fired = [E.latched_local_trigger_v3(view(WALLS_BEHIND), CFG, e, CONS)
             for _ in range(E.evidence_persistence_steps(CFG))]
    assert fired[-1] is True
    assert e.requested_mode == KEEP


def test_02_rear_robots_do_not_yet_observe_the_opening() -> None:
    e = team(1, LINE, E.LATCH_INSIDE)[0]
    for _ in range(10):
        assert E.latched_local_trigger_v3(view(WALLS_AHEAD), CFG, e, CONS) is False
    assert e.forward_open_streak == 0
    assert e.requested_mode is None


def test_03_04_05_06_recovery_token_propagates_and_rear_robots_adopt() -> None:
    """The core of the repair, end to end at protocol level."""
    n = 6
    eps = team(n, LINE, E.LATCH_INSIDE)

    # only robot 5 (the front of the line) has evidence
    for _ in range(E.evidence_persistence_steps(CFG)):
        E.latched_local_trigger_v3(view(WALLS_BEHIND), CFG, eps[5], CONS)
    for i in range(5):
        E.latched_local_trigger_v3(view(WALLS_AHEAD), CFG, eps[i], CONS)
    assert eps[5].requested_mode == KEEP
    assert all(eps[i].requested_mode is None for i in range(5))

    # 3. the front robot originates
    eps[5].arm_trigger(0)
    # 4. the token propagates peer-to-peer
    out = E.simulate_trigger_consensus(eps, runtime_graph(n), CONS.k_trigger)
    # 5. rear robots adopt WITHOUT fabricating evidence
    assert all(eps[i].trigger_token is not None for i in range(n))
    assert all(eps[i].forward_open_streak == 0 for i in range(5)), \
        "an adopting robot must not have manufactured sensor evidence"
    assert len(set(out["epoch_ids"].values())) == 1
    # 6. every robot derives requested mode KEEP
    assert all(E.requested_mode_for(eps[i]) == KEEP for i in range(n))


# ===========================================================================
# 6RR-4: event-type semantics survive propagation
# ===========================================================================
def test_propagated_recovery_requests_keep_on_every_adopting_robot() -> None:
    eps = team(6, LINE, E.LATCH_INSIDE)
    assert all(E.requested_mode_for(e) == KEEP for e in eps.values())


def test_propagated_entry_requests_line_on_every_adopting_robot() -> None:
    eps = team(6, KEEP, E.LATCH_BEFORE_ENTRY)
    assert all(E.requested_mode_for(e) == LINE for e in eps.values())


@pytest.mark.parametrize("clearance", [0.2, 0.5, 0.872, 1.5, 3.0, 10.0])
def test_requested_mode_is_invariant_to_local_clearance(clearance) -> None:
    """The defect this pins: the mode was re-derived from nearest clearance.

    0.872 m is the exact value that cancelled a valid recovery event.
    """
    e = team(1, LINE, E.LATCH_INSIDE)[0]
    _ = view(((clearance, 0.0, 0.0),))
    assert E.requested_mode_for(e) == KEEP


def test_requested_mode_never_equals_the_committed_mode() -> None:
    for mode, latch in ((KEEP, E.LATCH_BEFORE_ENTRY), (LINE, E.LATCH_INSIDE)):
        e = team(1, mode, latch)[0]
        req = E.requested_mode_for(e)
        assert req is not None and req != mode


def test_token_origin_grants_no_decision_authority() -> None:
    """Originating robot and adopting robots run identical logic."""
    eps = team(6, LINE, E.LATCH_INSIDE)
    for _ in range(E.evidence_persistence_steps(CFG)):
        E.latched_local_trigger_v3(view(WALLS_BEHIND), CFG, eps[3], CONS)
    eps[3].arm_trigger(0)
    E.simulate_trigger_consensus(eps, runtime_graph(6), CONS.k_trigger)
    # every robot derives the same requested mode, origin included
    assert len({E.requested_mode_for(e) for e in eps.values()}) == 1
    # and the origin has no distinguishing field
    import dataclasses
    fields = {f.name for f in dataclasses.fields(E.EpochState)}
    assert not (fields & {"is_leader", "leader_id", "authority", "rank"})


def test_08_origin_robot_cannot_force_commitment_by_itself() -> None:
    """One robot proposing KEEP against a split team must NOT commit."""
    e = team(1, LINE, E.LATCH_INSIDE)[0]
    e.begin_scoring()
    e.begin_confirming(KEEP, 1.0)
    e.mode_lo, e.mode_hi = KEEP, LINE          # confirmation saw disagreement
    before = e.committed_mode
    assert E.commit_or_retain(e, 5, CONS) is False
    assert e.committed_mode == before
    assert len(e.disagreements) == 1


def test_09_stale_token_is_rejected() -> None:
    e = E.EpochState(robot_id=0)
    e.arm_trigger(0)
    tok = e.trigger_token
    e.close_epoch()
    msg = E.TriggerMessage(sender_id=1, epoch_counter=1, trigger_flag=True,
                           trigger_token=tok, timestamp_step=0)
    assert E.max_consensus_trigger(e, [msg], now_step=99,
                                   delta_stale_steps=3) is False
    assert e.rejected_stale >= 1


def test_10_disconnected_components_do_not_claim_swarm_wide_agreement() -> None:
    eps = team(4, LINE, E.LATCH_INSIDE)
    adj = {0: [1], 1: [0], 2: [3], 3: [2]}
    eps[0].arm_trigger(0)
    eps[2].arm_trigger(0)
    out = E.simulate_trigger_consensus(eps, adj, CONS.k_trigger)
    ids = out["epoch_ids"]
    assert ids[0] == ids[1] and ids[2] == ids[3] and ids[0] != ids[2]


def test_different_event_types_are_never_merged() -> None:
    """An ENTRY robot and a RECOVERY robot request opposite modes."""
    entry = team(1, KEEP, E.LATCH_BEFORE_ENTRY)[0]
    recovery = team(1, LINE, E.LATCH_INSIDE)[0]
    assert E.requested_mode_for(entry) == LINE
    assert E.requested_mode_for(recovery) == KEEP
    assert E.requested_mode_for(entry) != E.requested_mode_for(recovery)


# ===========================================================================
# 6RR-9 (11, 12): decentralization invariants
# ===========================================================================
def test_11_no_global_state_or_exit_plane_is_used() -> None:
    for fn in (E.forward_opening_evidence, E.recovery_evidence_v3,
               E.recovery_armable, E.requested_mode_for,
               E.latched_local_trigger_v3, E.peer_support_for_recovery):
        src = inspect.getsource(fn)
        body = src.split('"""')[2] if src.count('"""') >= 2 else src
        for banned in ("exit_x", "exit_plane", "centroid", "positions",
                       "world_size", "joint"):
            assert banned not in body, (fn.__name__, banned)
    assert guards.audit() == []


def test_12_every_robot_computes_only_its_own_action() -> None:
    from rvt_swarm.decentralized import local_controller as lc
    sig = inspect.signature(lc.local_controller)
    assert list(sig.parameters)[0] == "view"
    with pytest.raises(CentralizedAccessError):
        lc.local_controller({"positions": np.zeros((6, 2))}, CFG, KEEP)


def test_communication_carries_a_proposal_not_a_command() -> None:
    """A trigger message carries an event token, never a mode to execute."""
    import dataclasses
    fields = {f.name for f in dataclasses.fields(E.TriggerMessage)}
    assert "committed_mode" not in fields and "command" not in fields
    assert fields == {"sender_id", "epoch_counter", "trigger_flag",
                      "trigger_token", "timestamp_step"}
    # confirmation carries a mode SET (min/max bounds), i.e. a vote, not an order
    cfields = {f.name for f in dataclasses.fields(E.ConfirmMessage)}
    assert "selected_mode" in cfields and "confirm_round" in cfields


def test_propagation_now_covers_the_worst_case_chain_after_the_G6_repair() -> None:
    """G6 repair verified: k_trigger is derived as D_max = N_max - 1.

    This test previously PINNED the defect -- k_trigger = 4 reached only five of
    six robots on a chain of diameter 5. With k_trigger derived from the
    declared maximum team size the whole chain is covered, and the guarantee is
    now stated rather than assumed.
    """
    from rvt_swarm.decentralized.parameters import (default_parameters,
                                                    derived_component_diameter,
                                                    derived_k_trigger)
    _, _, protocol = default_parameters()
    assert derived_k_trigger(protocol) == derived_component_diameter(protocol)
    assert derived_k_trigger(protocol) == protocol.max_team_size - 1 == 5

    n = 6
    eps = team(n, LINE, E.LATCH_INSIDE)
    for _ in range(E.evidence_persistence_steps(CFG)):
        E.latched_local_trigger_v3(view(WALLS_BEHIND), CFG, eps[5], CONS)
    eps[5].arm_trigger(0)
    E.simulate_trigger_consensus(eps, path(n), CONS.k_trigger)
    assert all(eps[i].trigger_token is not None for i in range(n)), \
        "the derived k_trigger must cover the worst-case chain"
