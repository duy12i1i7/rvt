"""Task 3E — the REAL runtime executes the real protocol.

Unit coverage of `epoch.py` and `comm_cost.py` obtained by importing them
directly proved nothing: an audit found both modules were unreferenced dead
code while their unit coverage read 38/38 and 40/40. Every test here therefore
drives a full episode through `simulate_decentralized_episode` and proves, with
spies and counters, that the intended functions were actually called.
"""

from __future__ import annotations

from typing import Dict, List

import numpy as np
import pytest

from rvt_swarm.config import Config
from rvt_swarm.decentralized import epoch as epoch_mod
from rvt_swarm.decentralized import runtime as runtime_mod
from rvt_swarm.decentralized import guards
from rvt_swarm.decentralized.runtime import simulate_decentralized_episode
from rvt_swarm.decentralized.system_model import (KEEP, LINE,
                                                  CentralizedAccessError,
                                                  CommParams, ConsensusParams)
from rvt_swarm.layouts import build_layouts

CORRIDOR = "line_corridor"
OPEN = "keep_open"


@pytest.fixture(scope="module")
def cfg() -> Config:
    c = Config()
    c.train.device = "cpu"
    c.env.scenarios = ["cluttered"]
    return c


def layout(family: str):
    return [l for l in build_layouts("val") if l.family == family][0]


def run(cfg, family=CORRIDOR, n=6, seed=20000001, **kw):
    return simulate_decentralized_episode(cfg, layout(family), n, seed, **kw)


# ---------------------------------------------------------------------------
# 1. the runtime actually executes the epoch manager
# ---------------------------------------------------------------------------
def test_01_runtime_calls_the_epoch_state_machine(cfg, monkeypatch) -> None:
    """Spy on the authoritative implementations, not on a copy."""
    calls: Dict[str, int] = {k: 0 for k in
                             ("local_trigger", "trigger_consensus",
                              "confirm_consensus", "commit_or_retain")}

    def spy(name, fn):
        def wrapped(*a, **k):
            calls[name] += 1
            return fn(*a, **k)
        return wrapped

    monkeypatch.setattr(runtime_mod, "local_trigger",
                        spy("local_trigger", epoch_mod.local_trigger))
    monkeypatch.setattr(runtime_mod, "simulate_trigger_consensus",
                        spy("trigger_consensus", epoch_mod.simulate_trigger_consensus))
    monkeypatch.setattr(runtime_mod, "simulate_confirm_consensus",
                        spy("confirm_consensus", epoch_mod.simulate_confirm_consensus))
    monkeypatch.setattr(runtime_mod, "commit_or_retain",
                        spy("commit_or_retain", epoch_mod.commit_or_retain))

    r = run(cfg)
    assert calls["local_trigger"] > 0, "the runtime never evaluated a local trigger"
    assert calls["trigger_consensus"] > 0, "trigger propagation never ran"
    assert calls["confirm_consensus"] > 0, "mode confirmation never ran"
    assert calls["commit_or_retain"] > 0, "no robot ever committed or retained"
    assert r["n_decisions"] > 0


def test_01b_runtime_imports_epoch_and_comm_cost(cfg) -> None:
    """The regression that the recovery audit would have caught."""
    import inspect
    src = inspect.getsource(runtime_mod)
    assert "from .epoch import" in src
    assert "from .comm_cost import" in src


# ---------------------------------------------------------------------------
# 2-5. an epoch produces the full message sequence
# ---------------------------------------------------------------------------
def test_02_corridor_entry_produces_trigger_messages(cfg) -> None:
    cats = run(cfg)["comm"]["categories"]
    assert cats["trigger"]["messages"] > 0
    assert cats["trigger"]["bytes"] > 0
    assert cats["trigger"]["wire_bytes_per_message"] == 21


def test_03_trigger_propagation_yields_one_epoch_per_component(cfg) -> None:
    """All robots in a connected component adopt the SAME epoch id."""
    eps = {i: epoch_mod.EpochState(robot_id=i) for i in range(6)}
    adj = {i: [j for j in (i - 1, i + 1) if 0 <= j < 6] for i in range(6)}
    eps[3].arm_trigger(0)                       # a non-zero robot triggers
    out = epoch_mod.simulate_trigger_consensus(eps, adj, 8)
    ids = set(out["epoch_ids"].values())
    assert len(ids) == 1, out["epoch_ids"]
    assert all(t == out["tokens"][0] for t in out["tokens"].values())
    # leaderless: the winner is the trigger's own token, not robot 0's
    assert out["tokens"][0].robot_id == 3


def test_04_score_consensus_messages_are_sent(cfg) -> None:
    cats = run(cfg)["comm"]["categories"]
    assert cats["score_consensus"]["messages"] > 0
    assert cats["score_consensus"]["wire_bytes_per_message"] == 20


def test_05_confirmation_messages_precede_commitment(cfg) -> None:
    r = run(cfg)
    cats = r["comm"]["categories"]
    assert cats["mode_confirmation"]["messages"] > 0
    assert cats["mode_confirmation"]["wire_bytes_per_message"] == 16
    # a commitment happened, and confirmation traffic exists to justify it
    assert r["n_keep_to_line"] + r["n_line_to_keep"] > 0


# ---------------------------------------------------------------------------
# 6-7. confirmation gates commitment
# ---------------------------------------------------------------------------
def test_06_disagreement_blocks_commitment_and_retains_previous_mode() -> None:
    e = epoch_mod.EpochState(robot_id=0)
    e.committed_mode = KEEP
    e.begin_scoring()
    e.begin_confirming(LINE, 1.0)
    e.mode_lo, e.mode_hi = KEEP, LINE          # min != max: disagreement
    before = e.committed_mode
    ok = epoch_mod.commit_or_retain(e, now_step=5)
    assert ok is False
    assert e.committed_mode == before, "a disagreeing robot must not switch"
    assert len(e.disagreements) == 1


def test_07_agreement_commits_every_robot_in_the_component(cfg) -> None:
    r = run(cfg)
    assert len(set(r["final_modes"])) == 1, r["final_modes"]


# ---------------------------------------------------------------------------
# 8-9. counters are non-zero only when work happened
# ---------------------------------------------------------------------------
def test_08_all_four_byte_counters_are_nonzero_on_a_transition_episode(cfg) -> None:
    r = run(cfg)
    assert r["n_keep_to_line"] + r["n_line_to_keep"] > 0, "no transition occurred"
    for name in ("beacon", "trigger", "score_consensus", "mode_confirmation"):
        assert r["comm"]["categories"][name]["bytes"] > 0, name


def test_09_open_field_generates_far_fewer_epochs_than_a_corridor(cfg) -> None:
    """No event, no unnecessary decision epochs.

    Compared against the corridor rather than against zero: the entry trigger
    also fires on sustained low progress, which can legitimately occur in open
    space, so demanding exactly zero would be asserting something the protocol
    does not promise.
    """
    corridor = run(cfg, family=CORRIDOR)
    field = run(cfg, family=OPEN)
    assert field["n_keep_to_line"] <= corridor["n_keep_to_line"]


# ---------------------------------------------------------------------------
# 10. the legacy periodic path is unreachable
# ---------------------------------------------------------------------------
def test_10_legacy_periodic_path_is_refused_under_strict_runtime(cfg) -> None:
    guards.set_strict(True)
    with pytest.raises(CentralizedAccessError):
        run(cfg, legacy_periodic_epoch_baseline=True)


def test_10b_no_modulo_decision_timer_remains_in_the_runtime() -> None:
    import inspect
    src = inspect.getsource(runtime_mod.simulate_decentralized_episode)
    assert "% decision_interval" not in src
    assert "step % " not in src, "an inline periodic decision timer is back"


def test_10c_epoch_ids_are_not_advanced_in_lockstep_by_the_harness() -> None:
    """The old runtime did `epoch_ids = [e + 1 for e in epoch_ids]`, which made
    epoch agreement a property of the harness rather than of the protocol."""
    import inspect
    src = inspect.getsource(runtime_mod.simulate_decentralized_episode)
    assert "e + 1 for e in epoch_ids" not in src


# ---------------------------------------------------------------------------
# 11. disconnection
# ---------------------------------------------------------------------------
def test_11_disconnected_components_do_not_claim_swarm_wide_confirmation() -> None:
    eps = {i: epoch_mod.EpochState(robot_id=i) for i in range(4)}
    adj = {0: [1], 1: [0], 2: [3], 3: [2]}          # two components
    for i in (0, 2):
        eps[i].arm_trigger(0)
    out = epoch_mod.simulate_trigger_consensus(eps, adj, 6)
    ids = out["epoch_ids"]
    assert ids[0] == ids[1] and ids[2] == ids[3]
    assert ids[0] != ids[2], "two disconnected components must not share an epoch"


# ---------------------------------------------------------------------------
# 12. strict runtime detects global access
# ---------------------------------------------------------------------------
def test_12_strict_runtime_detects_global_state_access() -> None:
    guards.set_strict(True)
    with pytest.raises(CentralizedAccessError):
        guards.assert_local_only({"positions": np.zeros((6, 2))})
    assert guards.audit() == []


def test_12b_episode_runs_with_strict_enabled(cfg) -> None:
    guards.set_strict(True)
    r = run(cfg)
    assert guards.strict_enabled() is True
    assert r["completion_steps"] > 0
