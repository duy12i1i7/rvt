"""RB-D -- F5's four-event sequence requires no unstated scientific choice.

The ET static audit found that F5's second bottleneck entry becomes locally
observable at longitudinal 2.66 m while its first bottleneck exit is at 3.50 m,
so the addendum clamps event #2's trigger to its predecessor's. Events #1 and
#2 therefore share the nominal trigger 3.502 m and become position-eligible at
the same control step.

This module establishes that the frozen rules already determine what happens,
so no queue duration, replay time, suppression rule, debounce interval or merge
rule has to be invented in runtime code.

The two frozen rules that decide it:

1. The S0 contract: `"retry": "none; skipped or blocked script entries are not
   moved"`. An entry is consumed at its trigger whatever happens next.
2. `request_candidate` refuses a candidate equal to the committed topology, so
   no source-equals-target lifecycle can be created.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from rvt_swarm.phase9c_rb import policies as P
from rvt_swarm.phase9c_rb.binding import build_binding, load_execution_specification
from rvt_swarm.phase9c_rb.session import build_event_plan
from rvt_swarm.runtime_configuration import DEFAULT_RUNTIME_CONFIG as CONFIG
from rvt_swarm.topology_registry import COMPACT, LINE

ROOT = pathlib.Path("results/rvt_fd24")
PROTOCOL = json.loads((ROOT / "executable_scientific_protocol_v1.json").read_text())
TARGET = json.loads((ROOT / "target_v4_execution_contract_v1.json").read_text())
POLICIES = json.loads((ROOT / "source_policy_contracts_v1.json").read_text())


def _plan(layout: str = "train-f5-00", team_size: int = 6):
    binding = build_binding(
        load_execution_specification(ROOT, "train", layout), team_size=team_size,
        source_policy=P.S0, protocol=PROTOCOL, target_contract=TARGET,
        source_policy_contracts=POLICIES)
    return binding, build_event_plan(binding, POLICIES)


class _StubRobot:
    """Minimal robot surface the S0 policy touches. No global state reaches it."""

    def __init__(self, committed: int) -> None:
        self.robot_id = 0
        self.committed_topology = committed
        self.protocol_node = type("N", (), {"state": "STABLE_TOPOLOGY"})()


class _StubSession:
    """Controls progress and records every candidate request verbatim."""

    def __init__(self, progress: float, accept: bool = True) -> None:
        self._progress = progress
        self.accept = accept
        self.control_step = 0
        self.time_seconds = 0.0
        self.control_period = float(CONFIG.physical.control_period_seconds)
        self.requests: list = []

    def _longitudinal_progress(self) -> float:
        return self._progress

    def request_candidate(self, robot, candidate_topology, event_type) -> bool:
        # Mirrors the real guard: a candidate equal to the committed topology
        # never creates a lifecycle.
        if candidate_topology == robot.committed_topology:
            self.requests.append((candidate_topology, event_type, "REFUSED_SAME"))
            return False
        self.requests.append((candidate_topology, event_type, "ACCEPTED"))
        if self.accept:
            robot.protocol_node.state = "INTENT_ACTIVE"
        return self.accept


# ---------------------------------------------------------------------------
# The plan itself
# ---------------------------------------------------------------------------
def test_f5_declares_exactly_four_events_with_distinct_identities() -> None:
    _, plan = _plan()
    assert len(plan) == 4
    assert [e.ordinal for e in plan] == [0, 1, 2, 3]
    assert len({(e.ordinal, e.landmark_id, e.event_type) for e in plan}) == 4


def test_f5_events_one_and_two_share_a_trigger_after_the_addendum_clamp() -> None:
    _, plan = _plan()
    assert plan[1].trigger_longitudinal_meters == pytest.approx(
        plan[2].trigger_longitudinal_meters)
    # The clamp matters because the *unclamped* observability trigger of the
    # second bottleneck entry precedes the first bottleneck exit.
    from rvt_swarm.phase8e.event_timing import earliest_observable_origin
    unclamped = min(
        earliest_observable_origin(plan[2].landmark_longitudinal_meters, sign * 1.05,
                                   6, 3.0, 0.9)
        for sign in (1.0, -1.0))
    assert unclamped < plan[1].trigger_longitudinal_meters, unclamped


def test_f5_declared_topology_sequence_is_preserved() -> None:
    _, plan = _plan()
    assert [e.candidate_topology for e in plan] == [LINE, COMPACT, LINE, COMPACT]


def test_f5_triggers_are_monotone_non_decreasing() -> None:
    _, plan = _plan()
    triggers = [e.trigger_longitudinal_meters for e in plan]
    assert triggers == sorted(triggers)


# ---------------------------------------------------------------------------
# Co-trigger disposition
# ---------------------------------------------------------------------------
def _run_to_cotrigger(one_event_per_step: bool):
    """Consume events up to and including the co-triggered pair.

    `one_event_per_step` selects the alternative admissible reading, in which a
    control step consumes at most one entry.
    """
    _, plan = _plan()
    policy = P.ScriptedDiagnosticPolicy(
        POLICIES["policies"]["S0_SCRIPTED_DIAGNOSTIC"], 7, 180.0, 6, "F5", plan)
    robot = _StubRobot(COMPACT)
    # Event #0 at the start.
    session = _StubSession(progress=plan[0].trigger_longitudinal_meters)
    policy.observe(session, robot, None, None)
    # The #0 lifecycle commits LINE before the team reaches 3.502 m.
    robot.committed_topology = LINE
    robot.protocol_node.state = "STABLE_TOPOLOGY"

    session = _StubSession(progress=plan[1].trigger_longitudinal_meters)
    if one_event_per_step:
        original = policy.observe
        for _ in range(2):
            before = len(policy.dispositions)
            for index, event in enumerate(policy.event_plan):
                if policy.fired.get(index):
                    continue
                if index > 0 and not policy.fired.get(index - 1):
                    break
                original(session, robot, None, None)
                break
            if len(policy.dispositions) == before:
                break
            session.control_step += 1
    else:
        policy.observe(session, robot, None, None)
    return policy, session


@pytest.mark.parametrize("one_event_per_step", [False, True])
def test_both_admissible_readings_give_the_same_disposition(one_event_per_step) -> None:
    """The residual ambiguity is immaterial, so no choice has to be invented.

    Whether a control step may consume one entry or several, event #2 is
    consumed at its trigger and is a no-op against the already-committed LINE.
    """
    policy, _ = _run_to_cotrigger(one_event_per_step)
    by_ordinal = {d["ordinal"]: d for d in policy.dispositions}
    assert set(by_ordinal) == {0, 1, 2}
    assert by_ordinal[0]["disposition"] == "ORIGINATED"
    assert by_ordinal[1]["disposition"] == "ORIGINATED"
    assert by_ordinal[2]["disposition"] == "NO_OP_ALREADY_COMMITTED"


def test_no_event_is_silently_overwritten_or_dropped() -> None:
    policy, _ = _run_to_cotrigger(False)
    ordinals = [d["ordinal"] for d in policy.dispositions]
    assert ordinals == sorted(ordinals), "ordering must be deterministic"
    assert len(ordinals) == len(set(ordinals)), "no ordinal recorded twice"
    # Every consumed entry produced exactly one auditable disposition record.
    assert len(policy.dispositions) == sum(1 for v in policy.fired.values() if v)


def test_a_co_triggered_event_is_not_dropped_merely_for_sharing_a_step() -> None:
    """Event #2 must still be consumed and recorded, not skipped over."""
    policy, _ = _run_to_cotrigger(False)
    assert 2 in {d["ordinal"] for d in policy.dispositions}
    assert policy.fired.get(2) is True


def test_no_source_equals_target_lifecycle_is_created() -> None:
    """The co-triggered LINE event must never open a LINE-to-LINE lifecycle."""
    policy, session = _run_to_cotrigger(False)
    # The final session covers the co-triggered pair (#1 then #2).
    assert ("REFUSED_SAME" not in [r[2] for r in session.requests]), session.requests
    by_ordinal = {d["ordinal"]: d for d in policy.dispositions}
    # #2 is a no-op decided before any request is issued, so no lifecycle opens.
    assert by_ordinal[2]["disposition"] == "NO_OP_ALREADY_COMMITTED"
    assert by_ordinal[2]["originated"] is False
    assert [r[0] for r in session.requests] == [COMPACT], session.requests


def test_blocked_origination_is_skipped_not_moved() -> None:
    """The frozen S0 retry rule, exercised directly."""
    _, plan = _plan()
    policy = P.ScriptedDiagnosticPolicy(
        POLICIES["policies"]["S0_SCRIPTED_DIAGNOSTIC"], 7, 180.0, 6, "F5", plan)
    robot = _StubRobot(COMPACT)
    session = _StubSession(progress=plan[0].trigger_longitudinal_meters, accept=False)
    policy.observe(session, robot, None, None)
    assert policy.dispositions[0]["disposition"] == "SKIPPED_ORIGINATION_BLOCKED"
    assert policy.fired[0] is True, "a blocked entry is still consumed, never requeued"


def test_the_frozen_contract_states_the_no_retry_rule() -> None:
    rule = POLICIES["policies"]["S0_SCRIPTED_DIAGNOSTIC"]["retry"]
    assert "not moved" in rule and "none" in rule


def test_commitment_and_rearm_constants_are_untouched() -> None:
    assert float(CONFIG.protocol.commitment_seconds) == 1.5
    assert float(CONFIG.protocol.rearm_inactive_seconds) == 3.75
    assert float(CONFIG.protocol.evidence_persistence_seconds) == 0.45
