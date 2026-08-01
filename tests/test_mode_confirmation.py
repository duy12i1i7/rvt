"""Evidence for the leaderless mode-confirmation protocol (Task 6, `epoch.py`).

Confirmation is finite-round **min AND max consensus** on the binary mode value,
carried by one byte per message as the mode-SET code (`encode_mode_set`).  A
robot commits only when, judged from its own observations alone,

1. ``mode_lo == mode_hi``   -- every proposal it could reach in `k_confirm` hops
   agreed;
2. ``epoch_mismatch == 0``  -- no packet from a different epoch arrived;
3. ``margin_min >= confirm_margin``.

Otherwise it RETAINS the mode it already held and records a `DisagreementEvent`.
No fallback mode is invented.

Why this file exists
--------------------
`docs/INTERRUPTED_WORKFLOW_RECOVERY_AUDIT.md` established that `epoch.py` was
committed but never executed (38 functions, 0 exercised) and that Gate D2's
second criterion, *mode-confirmation success >= 0.95*, was therefore **never
measured**: `runtime.py` re-decides on an inline `step % decision_interval == 0`
test and never calls the confirmation protocol at all.

`test_20_gate_d2_mode_confirmation_success_rate` supplies that number.  Read its
docstring before quoting it: it is a **protocol-level measurement on synthetic
proposals**, not a closed-loop episode measurement, and its aggregate value
depends on the declared synthetic scenario mix, which was chosen here.

A measured limitation, pinned rather than hidden
------------------------------------------------
Confirmation certifies agreement over a robot's `k_confirm`-hop neighbourhood,
which is exactly what the code claims and no more.  When the communication
graph's diameter exceeds `k_confirm`, a robot further than `k_confirm` hops from
a dissenter never witnesses the disagreement and commits while its neighbours
retain.  `test_13_...` measures that directly on a 6-node path (diameter 5,
`k_confirm` 4) and `test_14_...` shows the failure disappears at
`k_confirm >= 5`.  In the deployed regime this is not reached -- at
`r_comm = 3.0` an N=6 line spans 4.5 m with graph diameter 2 and 96.6 % of
robots see the whole team one-hop -- but the bound is a real precondition and is
stated, not assumed away.
"""

from __future__ import annotations

import struct
from typing import Dict, List, Optional, Sequence, Tuple

import pytest

from rvt_swarm.decentralized.comm_cost import WIRE_SCHEMAS, assert_schema_sizes
from rvt_swarm.decentralized.consensus import (agreement_rate,
                                               component_agreement,
                                               connected_components)
from rvt_swarm.decentralized.epoch import (CONFIRM_PAYLOAD_BYTES,
                                           FAILURE_PRIORITY, MODE_SET_CODES,
                                           MODE_SET_MIXED, PHASE_COMMITTED,
                                           PHASE_CONFIRMING, ConfirmMessage,
                                           DisagreementEvent, EpochState,
                                           commit_or_retain, confirm_mode,
                                           decode_mode_set, encode_mode_set,
                                           outgoing_confirm,
                                           simulate_confirm_consensus)
from rvt_swarm.decentralized.system_model import (KEEP, LINE, CommParams,
                                                  ConsensusParams)

Graph = Dict[int, Tuple[int, ...]]

N = 6
DELTA_STALE = CommParams().delta_stale_steps          # 3
K_CONFIRM = ConsensusParams().k_confirm               # 4


# ---------------------------------------------------------------------------
# topologies
# ---------------------------------------------------------------------------
def complete_graph(n: int = N) -> Graph:
    return {i: tuple(j for j in range(n) if j != i) for i in range(n)}


def ring_graph(n: int = N) -> Graph:
    return {i: ((i - 1) % n, (i + 1) % n) for i in range(n)}


def path_graph(n: int = N) -> Graph:
    """Diameter n-1. At n=6 that is 5, deliberately larger than k_confirm=4."""
    return {i: tuple(j for j in (i - 1, i + 1) if 0 <= j < n) for i in range(n)}


def two_triangles() -> Graph:
    """Two disconnected 3-cliques. No edge crosses between them."""
    return {0: (1, 2), 1: (0, 2), 2: (0, 1), 3: (4, 5), 4: (3, 5), 5: (3, 4)}


TOPOLOGIES: Dict[str, Graph] = {
    "complete6": complete_graph(),
    "ring6": ring_graph(),
    "path6": path_graph(),
    "two_triangles": two_triangles(),
}

PROPOSAL_PATTERNS: Dict[str, Dict[int, int]] = {
    "unanimous_keep": {i: KEEP for i in range(N)},
    "unanimous_line": {i: LINE for i in range(N)},
    "one_dissenter": {i: (KEEP if i == 0 else LINE) for i in range(N)},
    "split_half": {i: (KEEP if i < 3 else LINE) for i in range(N)},
}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def mode_wire_byte(mode: int) -> bytes:
    """The exact byte a ConfirmMessage carries for a robot holding `mode`."""
    return struct.pack("<B", encode_mode_set(int(mode), int(mode)))


def component_of(components: Sequence[Sequence[int]], robot_id: int) -> int:
    for index, comp in enumerate(components):
        if robot_id in comp:
            return index
    raise KeyError(robot_id)


def make_confirming(proposals: Dict[int, int], *,
                    previous: Optional[Dict[int, int]] = None,
                    margins: Optional[Dict[int, float]] = None,
                    epoch_ids: Optional[Dict[int, int]] = None,
                    default_previous: int = KEEP,
                    default_margin: float = 1.0,
                    default_epoch_id: int = 4242) -> Dict[int, EpochState]:
    """Per-robot `EpochState`s seeded with their own post-score proposal.

    `begin_confirming` is the real entry point the epoch state machine uses; the
    test never writes `mode_lo`/`mode_hi` directly, so the seeding rule itself
    stays under test.
    """
    epochs: Dict[int, EpochState] = {}
    for i in sorted(proposals):
        epoch = EpochState(robot_id=i)
        epoch.committed_mode = int((previous or {}).get(i, default_previous))
        epoch.epoch_id = int((epoch_ids or {}).get(i, default_epoch_id))
        epoch.begin_confirming(int(proposals[i]),
                               float((margins or {}).get(i, default_margin)))
        epochs[i] = epoch
    return epochs


def per_component_epoch_ids(graph: Graph) -> Dict[int, int]:
    """One epoch id per connected component.

    Robots that cannot exchange a single packet cannot have agreed a common
    trigger token, so giving disconnected components a shared epoch id would be
    a fiction the protocol never produces.
    """
    comps = connected_components(graph)
    return {i: 1000 + component_of(comps, i) for comp in comps for i in comp}


def run_confirmation(graph: Graph, proposals: Dict[int, int], *,
                     k_confirm: Optional[int] = None,
                     previous: Optional[Dict[int, int]] = None,
                     margins: Optional[Dict[int, float]] = None,
                     epoch_ids: Optional[Dict[int, int]] = None,
                     params: Optional[ConsensusParams] = None,
                     default_previous: int = KEEP,
                     start_step: int = 0) -> Dict[str, object]:
    """k_confirm rounds of min/max consensus, then `commit_or_retain` per robot.

    Message delivery is `simulate_confirm_consensus`, the module's own
    simulation boundary; every value change happens inside `confirm_mode`, which
    sees one robot's state and one robot's inbox.
    """
    cons = params or ConsensusParams()
    rounds = cons.k_confirm if k_confirm is None else int(k_confirm)
    epochs = make_confirming(
        proposals, previous=previous, margins=margins,
        epoch_ids=epoch_ids if epoch_ids is not None else per_component_epoch_ids(graph),
        default_previous=default_previous)
    sim = simulate_confirm_consensus(epochs, graph, rounds, start_step=start_step,
                                     delta_stale_steps=DELTA_STALE)
    end_step = int(start_step) + rounds
    committed = {i: bool(commit_or_retain(epochs[i], end_step, cons))
                 for i in sorted(epochs)}
    return {
        "epochs": epochs,
        "sim": sim,
        "committed": committed,
        "modes": {i: int(epochs[i].committed_mode) for i in sorted(epochs)},
        "bounds": {i: (int(epochs[i].mode_lo), int(epochs[i].mode_hi))
                   for i in sorted(epochs)},
        "margins": {i: float(epochs[i].margin_min) for i in sorted(epochs)},
        "kinds": {i: tuple(d.kind for d in epochs[i].disagreements)
                  for i in sorted(epochs)},
        "components": connected_components(graph),
        "end_step": end_step,
    }


# ===========================================================================
# 1. unanimous proposals confirm
# ===========================================================================
@pytest.mark.parametrize("topology", ["complete6", "ring6", "path6"])
@pytest.mark.parametrize("mode", [KEEP, LINE])
def test_01_unanimous_proposals_confirm_and_every_robot_commits(topology, mode):
    """Unanimity -> every robot commits to THAT mode, from a different previous one.

    The previous committed mode is set to the opposite of the proposal, so a
    passing commit cannot be the retain path in disguise.
    """
    graph = TOPOLOGIES[topology]
    other = LINE if mode == KEEP else KEEP
    out = run_confirmation(graph, {i: mode for i in range(N)},
                           default_previous=other)

    assert all(out["committed"].values()), out["committed"]
    assert out["modes"] == {i: mode for i in range(N)}
    assert out["bounds"] == {i: (mode, mode) for i in range(N)}
    for i in range(N):
        epoch = out["epochs"][i]
        assert epoch.phase == PHASE_COMMITTED
        assert epoch.commits == 1 and epoch.retentions == 0
        assert epoch.disagreements == []
        assert epoch.remaining_commitment == ConsensusParams().h_commit
        assert epoch.epoch_mismatch == 0
    assert agreement_rate(out["modes"]) == 1.0


# ===========================================================================
# 2. a split proposal must NOT confirm
# ===========================================================================
@pytest.mark.parametrize("topology", ["complete6", "ring6"])
@pytest.mark.parametrize("pattern", ["one_dissenter", "split_half"])
def test_02_split_proposal_is_detected_and_does_not_confirm(topology, pattern):
    """Disagreement is WITNESSED (lo != hi), not guessed, and blocks every commit.

    Restricted to topologies whose diameter (1 and 3) is within `k_confirm` = 4,
    so every robot can actually reach the dissenting proposal. The larger-diameter
    case is not swept under the rug -- it is measured in `test_13_...`.
    """
    graph = TOPOLOGIES[topology]
    out = run_confirmation(graph, PROPOSAL_PATTERNS[pattern])

    assert not any(out["committed"].values()), out["committed"]
    for i in range(N):
        assert out["bounds"][i] == (KEEP, LINE), (i, out["bounds"][i])
        epoch = out["epochs"][i]
        assert epoch.commits == 0 and epoch.retentions == 1
        assert epoch.epoch_mismatch == 0          # the ONLY failure is the mode
        assert out["kinds"][i] == ("mode_disagreement",)
    # the mixed set is exactly the wire code that carries "both modes seen"
    assert encode_mode_set(KEEP, LINE) == MODE_SET_MIXED


# ===========================================================================
# 3. a failed confirmation RETAINS the previous mode, byte for byte
# ===========================================================================
@pytest.mark.parametrize("previous", [KEEP, LINE])
def test_03_failed_confirmation_retains_previous_mode_byte_identical(previous):
    """The committed mode after a failed epoch is the one held before it.

    Both previous modes are exercised. With `previous = LINE` the retained mode
    differs from `mode_lo` (KEEP), from the tie-break default (KEEP) and from the
    majority proposal, so this cannot pass by coincidence: any of the three
    plausible "arbitrary fallbacks" would fail it.
    """
    graph = complete_graph()
    proposals = PROPOSAL_PATTERNS["split_half"]
    before_bytes = {i: mode_wire_byte(previous) for i in range(N)}

    out = run_confirmation(graph, proposals, default_previous=previous)

    assert not any(out["committed"].values())
    for i in range(N):
        epoch = out["epochs"][i]
        assert epoch.committed_mode == previous
        assert mode_wire_byte(epoch.committed_mode) == before_bytes[i]
        # no arbitrary fallback: not the observed min, not the observed max,
        # not the robot's own proposal (unless that already equalled `previous`)
        assert epoch.mode_lo == KEEP and epoch.mode_hi == LINE
        if previous == LINE:
            assert epoch.committed_mode != epoch.mode_lo          # not min
            assert epoch.committed_mode != KEEP                   # not "default keep"
        if int(proposals[i]) != previous:
            assert epoch.committed_mode != int(proposals[i])      # not own proposal
        assert epoch.disagreements[0].retained_mode == previous


def test_03b_retention_leaves_no_robot_holding_an_invented_mode():
    """Every robot leaves a failed epoch holding a mode it held on entry.

    Robots enter with DIFFERENT previous modes, so a fallback that manufactured
    swarm-wide agreement would be immediately visible as agreement_rate == 1.
    """
    graph = complete_graph()
    previous = {0: KEEP, 1: KEEP, 2: KEEP, 3: LINE, 4: LINE, 5: LINE}
    out = run_confirmation(graph, PROPOSAL_PATTERNS["one_dissenter"],
                           previous=previous)

    assert not any(out["committed"].values())
    assert out["modes"] == previous
    assert agreement_rate(out["modes"]) == 0.0     # honest: they still disagree


# ===========================================================================
# 4. a DisagreementEvent is recorded, with its kind
# ===========================================================================
def test_04_disagreement_event_is_recorded_with_kind_and_evidence():
    graph = complete_graph()
    out = run_confirmation(graph, PROPOSAL_PATTERNS["split_half"],
                           default_previous=LINE, start_step=7)
    end_step = out["end_step"]

    for i in range(N):
        epoch = out["epochs"][i]
        assert len(epoch.disagreements) == 1
        event = epoch.disagreements[0]
        assert isinstance(event, DisagreementEvent)
        assert event.kind == "mode_disagreement"
        assert event.reasons == ("mode_disagreement",)
        assert event.robot_id == i
        assert event.epoch_id == epoch.epoch_id
        assert event.step == end_step
        assert (event.mode_lo, event.mode_hi) == (KEEP, LINE)
        assert event.retained_mode == LINE
        assert event.epoch_mismatch == 0


def test_04b_failure_kind_priority_is_deterministic_when_reasons_coincide():
    """Several reasons at once -> `kind` is the highest-priority one, always."""
    cons = ConsensusParams(confirm_margin=0.5)
    epoch = EpochState(robot_id=0)
    epoch.epoch_id = 99
    epoch.committed_mode = LINE
    epoch.begin_confirming(LINE, 0.1)                 # margin below threshold
    # one dissenting proposal from this epoch, one packet from a different one
    confirm_mode(epoch, [ConfirmMessage.from_bounds(1, 99, KEEP, KEEP, 0.1, 0, 0),
                         ConfirmMessage.from_bounds(2, 77, LINE, LINE, 9.0, 0, 0)],
                 now_step=0, delta_stale_steps=DELTA_STALE)

    assert commit_or_retain(epoch, 3, cons) is False
    event = epoch.disagreements[0]
    assert set(event.reasons) == {"epoch_overlap", "mode_disagreement", "weak_margin"}
    assert event.reasons == tuple(sorted(event.reasons, key=FAILURE_PRIORITY.index))
    assert event.kind == "epoch_overlap"
    assert epoch.committed_mode == LINE


# ===========================================================================
# 5. epoch-id mismatch prevents confirmation
# ===========================================================================
def test_05_epoch_id_mismatch_prevents_confirmation():
    """Two overlapping epochs cannot confirm -- even proposing the SAME mode.

    Every robot proposes LINE, so `mode_lo == mode_hi == LINE` everywhere and the
    ONLY thing standing between the swarm and a commit is the epoch check. That
    isolates it: if the epoch id were ignored, all six would commit.
    """
    graph = complete_graph()
    epoch_ids = {0: 111, 1: 111, 2: 111, 3: 222, 4: 222, 5: 222}
    out = run_confirmation(graph, {i: LINE for i in range(N)},
                           epoch_ids=epoch_ids, default_previous=KEEP)

    assert not any(out["committed"].values()), out["committed"]
    for i in range(N):
        epoch = out["epochs"][i]
        assert epoch.mode_lo == LINE and epoch.mode_hi == LINE   # modes DID agree
        assert epoch.epoch_mismatch == 3 * K_CONFIRM             # 3 foreign senders
        assert out["kinds"][i] == ("epoch_overlap",)
        assert epoch.committed_mode == KEEP                      # previous retained


def test_05b_matching_epoch_id_is_what_lets_the_same_proposals_commit():
    """Control for test_05: identical proposals, one shared epoch id -> commit."""
    graph = complete_graph()
    out = run_confirmation(graph, {i: LINE for i in range(N)},
                           epoch_ids={i: 111 for i in range(N)},
                           default_previous=KEEP)
    assert all(out["committed"].values())
    assert out["modes"] == {i: LINE for i in range(N)}


def test_05c_foreign_epoch_packet_is_counted_not_merged():
    """A packet from another epoch never moves the bounds; it is only counted."""
    epoch = EpochState(robot_id=0)
    epoch.epoch_id = 111
    epoch.begin_confirming(LINE, 1.0)

    changed = confirm_mode(
        epoch, [ConfirmMessage.from_bounds(1, 222, KEEP, KEEP, -5.0, 0, 0)],
        now_step=0, delta_stale_steps=DELTA_STALE)

    assert changed is False
    assert (epoch.mode_lo, epoch.mode_hi) == (LINE, LINE)   # not merged
    assert epoch.margin_min == 1.0                          # margin not merged
    assert epoch.epoch_mismatch == 1                        # but counted


# ===========================================================================
# 6. duplicate confirmation messages are idempotent
# ===========================================================================
def test_06_duplicate_confirm_messages_are_idempotent_within_a_round():
    """min/max/min is idempotent, so N copies of a packet == 1 copy.

    Duplicate suppression is a property of the operator, not of a message-id
    table, which is why this must be asserted on the *values*, not on a counter.
    """
    msg = ConfirmMessage.from_bounds(1, 55, KEEP, KEEP, 0.4, 0, 0)

    once = EpochState(robot_id=0)
    once.epoch_id = 55
    once.begin_confirming(LINE, 1.0)
    confirm_mode(once, [msg], now_step=0, delta_stale_steps=DELTA_STALE)

    many = EpochState(robot_id=0)
    many.epoch_id = 55
    many.begin_confirming(LINE, 1.0)
    confirm_mode(many, [msg, msg, msg, msg, msg], now_step=0,
                 delta_stale_steps=DELTA_STALE)

    assert (once.mode_lo, once.mode_hi, once.margin_min) == (KEEP, LINE, 0.4)
    assert (many.mode_lo, many.mode_hi, many.margin_min) == \
           (once.mode_lo, once.mode_hi, once.margin_min)
    assert many.rejected_stale == many.rejected_future == many.epoch_mismatch == 0


def test_06b_redelivering_a_message_in_a_later_round_changes_nothing():
    msg = ConfirmMessage.from_bounds(1, 55, KEEP, KEEP, 0.4, 0, 0)
    epoch = EpochState(robot_id=0)
    epoch.epoch_id = 55
    epoch.begin_confirming(LINE, 1.0)

    first = confirm_mode(epoch, [msg], now_step=0, delta_stale_steps=DELTA_STALE)
    after_first = (epoch.mode_lo, epoch.mode_hi, epoch.margin_min)
    second = confirm_mode(epoch, [msg], now_step=1, delta_stale_steps=DELTA_STALE)
    third = confirm_mode(epoch, [msg, msg], now_step=2, delta_stale_steps=DELTA_STALE)

    assert first is True                       # the first copy carried news
    assert second is False and third is False  # every later copy carried none
    assert (epoch.mode_lo, epoch.mode_hi, epoch.margin_min) == after_first
    assert epoch.confirm_round == 3            # rounds still advance


def test_06c_duplicate_delivery_does_not_change_the_committed_outcome():
    """End to end: a graph that delivers everything twice commits identically.

    Margins differ per robot, so the min-consensus channel is also under test:
    with uniform margins a non-idempotent fold (an average, say) would be
    invisible here and the test would pass for the wrong reason.
    """
    graph = path_graph()
    doubled = {i: tuple(list(nb) + list(nb)) for i, nb in graph.items()}
    props = {i: LINE for i in range(N)}
    margins = {0: 0.2, 1: 0.9, 2: 0.9, 3: 0.9, 4: 0.9, 5: 1.4}

    plain = run_confirmation(graph, props, margins=margins, k_confirm=2)
    twice = run_confirmation(doubled, props, margins=margins, k_confirm=2)

    assert twice["committed"] == plain["committed"]
    assert twice["modes"] == plain["modes"]
    assert twice["bounds"] == plain["bounds"]
    assert twice["margins"] == plain["margins"]
    # Non-vacuity. With k_confirm=2 on a path of 6 the minimum 0.2 has only
    # reached robots 0-2, so the post-consensus margins are genuinely
    # different across robots and an averaging fold would be caught here.
    # (Left at the default k_confirm=4 the min reaches everyone, the margins
    # become uniform BY DESIGN, and this guard would fail for the very reason
    # the protocol is working.)
    assert len(set(plain["margins"].values())) > 1
    assert plain["margins"][0] == pytest.approx(min(margins.values()))


# ===========================================================================
# 7. stale confirmation messages are rejected
# ===========================================================================
@pytest.mark.parametrize("age,accepted", [(0, True), (DELTA_STALE, True),
                                          (DELTA_STALE + 1, False),
                                          (DELTA_STALE + 5, False)])
def test_07_stale_confirm_messages_are_rejected_at_the_declared_boundary(age, accepted):
    now = 20
    epoch = EpochState(robot_id=0)
    epoch.epoch_id = 55
    epoch.begin_confirming(LINE, 1.0)
    msg = ConfirmMessage.from_bounds(1, 55, KEEP, KEEP, 0.4, 0, now - age)

    changed = confirm_mode(epoch, [msg], now_step=now, delta_stale_steps=DELTA_STALE)

    assert changed is accepted
    if accepted:
        assert (epoch.mode_lo, epoch.mode_hi) == (KEEP, LINE)
        assert epoch.rejected_stale == 0
    else:
        assert (epoch.mode_lo, epoch.mode_hi) == (LINE, LINE)   # untouched
        assert epoch.margin_min == 1.0
        assert epoch.rejected_stale == 1


def test_07b_a_stale_dissent_is_dropped_so_the_robot_commits_its_own_proposal():
    """Rejection has consequences, and they are the documented ones.

    A dissent that arrives too late is not half-applied and not queued: it is
    dropped, and the robot commits on the evidence it legitimately holds. Pinned
    so the staleness rule is visible as a real behaviour, not just a counter.
    """
    epoch = EpochState(robot_id=0)
    epoch.epoch_id = 55
    epoch.committed_mode = KEEP
    epoch.begin_confirming(LINE, 1.0)
    confirm_mode(epoch, [ConfirmMessage.from_bounds(1, 55, KEEP, KEEP, 0.4, 0, 0)],
                 now_step=20, delta_stale_steps=DELTA_STALE)

    assert commit_or_retain(epoch, 21) is True
    assert epoch.committed_mode == LINE
    assert epoch.rejected_stale == 1


def test_07c_a_message_from_the_future_is_rejected_too():
    epoch = EpochState(robot_id=0)
    epoch.epoch_id = 55
    epoch.begin_confirming(LINE, 1.0)
    confirm_mode(epoch, [ConfirmMessage.from_bounds(1, 55, KEEP, KEEP, 0.4, 0, 9)],
                 now_step=5, delta_stale_steps=DELTA_STALE)

    assert epoch.rejected_future == 1
    assert (epoch.mode_lo, epoch.mode_hi) == (LINE, LINE)


# ===========================================================================
# 8. disconnected components are reported HONESTLY
# ===========================================================================
def test_08_disconnected_components_confirm_independently_and_are_not_swarm_agreement():
    """Two components, two different modes: both confirm, and the report says so.

    This is the case a dishonest metric would paper over. Each 3-clique reaches
    internal unanimity and commits; the two committed modes differ; and the two
    diagnostics must disagree with each other -- `agreement_rate == 0` (there is
    no swarm-wide agreement) while `component_agreement == 1.0` (neither
    component failed at anything it could control).
    """
    graph = two_triangles()
    proposals = {0: KEEP, 1: KEEP, 2: KEEP, 3: LINE, 4: LINE, 5: LINE}
    out = run_confirmation(graph, proposals, default_previous=KEEP)

    components = out["components"]
    assert components == [[0, 1, 2], [3, 4, 5]]

    assert all(out["committed"].values()), out["committed"]
    assert out["modes"] == proposals               # each committed ITS OWN mode
    for i in range(N):
        assert out["epochs"][i].epoch_mismatch == 0   # no packet ever crossed
        assert out["epochs"][i].disagreements == []

    assert agreement_rate(out["modes"]) == 0.0
    assert component_agreement(out["modes"], components) == 1.0
    # and the two are not accidentally the same number
    assert agreement_rate(out["modes"]) != component_agreement(out["modes"], components)


def test_08b_disagreement_inside_one_component_does_not_condemn_the_other():
    """Component-local failure stays local; the honest metrics separate them."""
    graph = two_triangles()
    proposals = {0: KEEP, 1: LINE, 2: LINE, 3: LINE, 4: LINE, 5: LINE}
    out = run_confirmation(graph, proposals, default_previous=KEEP)

    assert [out["committed"][i] for i in range(N)] == \
           [False, False, False, True, True, True]
    for i in (0, 1, 2):
        assert out["kinds"][i] == ("mode_disagreement",)
        assert out["modes"][i] == KEEP             # retained
    for i in (3, 4, 5):
        assert out["kinds"][i] == ()
        assert out["modes"][i] == LINE             # committed
    assert component_agreement(out["modes"], out["components"]) == 1.0
    assert agreement_rate(out["modes"]) == 0.0


# ===========================================================================
# 9. the confirmation is leaderless
# ===========================================================================
PERMUTATIONS: Tuple[Dict[int, int], ...] = (
    {0: 5, 1: 4, 2: 3, 3: 2, 4: 1, 5: 0},      # reversal
    {0: 1, 1: 2, 2: 3, 3: 4, 4: 5, 5: 0},      # rotation
    {0: 3, 1: 2, 2: 5, 3: 0, 4: 1, 5: 4},      # arbitrary
)

BASE_MARGINS: Dict[int, float] = {0: 0.9, 1: 0.7, 2: 1.3, 3: 0.5, 4: 1.1, 5: 0.8}


def _relabel(graph: Graph, mapping: Dict[int, int]) -> Graph:
    return {mapping[i]: tuple(sorted(mapping[j] for j in nb))
            for i, nb in graph.items()}


@pytest.mark.parametrize("perm", PERMUTATIONS)
def test_09_confirmation_is_leaderless_under_robot_id_permutation(perm):
    """Relabelling the robots relabels the outcome and changes nothing else.

    The base scenario is chosen so the outcome is NON-UNIFORM (exactly one robot
    commits): if every robot behaved identically the equivariance check would
    pass vacuously, which is the classic way this test is written wrong. The
    margins differ per robot too, so the min-consensus channel is also permuted.
    """
    # A DISCONNECTED graph gives a genuinely non-uniform outcome under the
    # repaired k_confirm: the agreeing component commits, the split one does
    # not. The former base scenario (one dissenter on a path) relied on a robot
    # committing five hops from the dissenter, which the G6 diameter repair
    # correctly eliminated -- so it now yields a uniform all-retain outcome and
    # would make this equivariance check vacuous.
    graph = {0: (1,), 1: (0,), 2: (3,), 3: (2,), 4: (5,), 5: (4,)}
    proposals = {0: LINE, 1: LINE, 2: KEEP, 3: LINE, 4: KEEP, 5: KEEP}

    base = run_confirmation(graph, proposals, margins=BASE_MARGINS)
    n_commit = sum(base["committed"].values())
    assert 0 < n_commit < N, (n_commit, base["committed"])   # non-vacuous

    moved = run_confirmation(
        _relabel(graph, perm),
        {perm[i]: m for i, m in proposals.items()},
        margins={perm[i]: v for i, v in BASE_MARGINS.items()})

    for i in range(N):
        j = perm[i]
        assert moved["committed"][j] == base["committed"][i], (i, j)
        assert moved["modes"][j] == base["modes"][i]
        assert moved["bounds"][j] == base["bounds"][i]
        assert moved["margins"][j] == pytest.approx(base["margins"][i])
        assert moved["kinds"][j] == base["kinds"][i]


def test_09b_no_robot_id_is_privileged_in_a_symmetric_split():
    """A 3/3 split on a complete graph: no id wins, everybody retains."""
    out = run_confirmation(complete_graph(), PROPOSAL_PATTERNS["split_half"],
                           default_previous=KEEP)
    assert set(out["committed"].values()) == {False}
    assert set(out["bounds"].values()) == {(KEEP, LINE)}
    # the highest id proposed LINE and did not carry the swarm
    assert out["modes"][5] == KEEP


# ===========================================================================
# 10. margin below confirm_margin blocks the commit
# ===========================================================================
def test_10_margin_below_confirm_margin_blocks_the_commit():
    """One weak margin propagates by min-consensus and blocks every commit.

    Proposals are unanimous, so the mode check and the epoch check both pass and
    the margin is provably the only thing that can fail.
    """
    cons = ConsensusParams(confirm_margin=0.5)
    margins = {0: 0.1, 1: 0.9, 2: 0.9, 3: 0.9, 4: 0.9, 5: 0.9}
    out = run_confirmation(complete_graph(), {i: LINE for i in range(N)},
                           margins=margins, params=cons, default_previous=KEEP)

    assert not any(out["committed"].values())
    for i in range(N):
        epoch = out["epochs"][i]
        assert epoch.mode_lo == epoch.mode_hi == LINE      # modes agreed
        assert epoch.epoch_mismatch == 0                   # epochs agreed
        assert epoch.margin_min == pytest.approx(0.1)      # weakest margin heard
        assert out["kinds"][i] == ("weak_margin",)
        assert epoch.committed_mode == KEEP                # previous retained


@pytest.mark.parametrize("margin,commits", [(0.49, False), (0.5, True), (0.51, True)])
def test_10b_confirm_margin_is_a_greater_or_equal_threshold(margin, commits):
    cons = ConsensusParams(confirm_margin=0.5)
    out = run_confirmation(complete_graph(), {i: LINE for i in range(N)},
                           margins={i: margin for i in range(N)}, params=cons,
                           default_previous=KEEP)
    assert all(out["committed"].values()) is commits
    assert out["modes"] == {i: (LINE if commits else KEEP) for i in range(N)}


def test_10c_default_confirm_margin_admits_a_zero_margin():
    """The shipped default is 0.0, so a zero margin must still commit.

    Pinned because a silently raised default would turn every tie into a
    retention and would look like a protocol failure rather than a config change.
    """
    assert ConsensusParams().confirm_margin == 0.0
    out = run_confirmation(complete_graph(), {i: KEEP for i in range(N)},
                           margins={i: 0.0 for i in range(N)}, default_previous=LINE)
    assert all(out["committed"].values())


# ===========================================================================
# 11-12. the (min, max) wire encoding and its one-hop-per-round propagation
# ===========================================================================
def test_11_mode_set_codec_carries_min_and_max_in_one_byte():
    assert encode_mode_set(KEEP, KEEP) == KEEP
    assert encode_mode_set(LINE, LINE) == LINE
    assert encode_mode_set(KEEP, LINE) == MODE_SET_MIXED
    for code in MODE_SET_CODES:
        lo, hi = decode_mode_set(code)
        assert encode_mode_set(lo, hi) == code
    assert decode_mode_set(MODE_SET_MIXED) == (KEEP, LINE)
    # 1 is the retired `split` mode id and must stay unusable
    with pytest.raises(ValueError):
        decode_mode_set(1)
    with pytest.raises(ValueError):
        encode_mode_set(LINE, KEEP)            # lo > hi
    with pytest.raises(ValueError):
        encode_mode_set(1, 1)                  # not a live mode


def test_11b_confirm_message_is_sixteen_bytes_and_matches_the_accounted_schema():
    """The confirmation packet the accountant charges for is the one sent."""
    msg = ConfirmMessage.from_bounds(3, 77, KEEP, LINE, 0.25, 2, 11)
    assert len(msg.payload_bytes()) == CONFIRM_PAYLOAD_BYTES == 16
    assert msg.mode_bounds() == (KEEP, LINE)
    assert WIRE_SCHEMAS["mode_confirmation"].size_bytes == CONFIRM_PAYLOAD_BYTES
    assert assert_schema_sizes()["mode_confirmation"]["ok"] is True


def test_11c_outgoing_confirm_reports_only_the_senders_own_running_state():
    epoch = EpochState(robot_id=4)
    epoch.epoch_id = 77
    epoch.begin_confirming(LINE, 0.25)
    epoch.mode_lo = KEEP                       # as if a dissent had been folded in
    msg = outgoing_confirm(epoch, now_step=9)

    assert msg.sender_id == 4 and msg.epoch_id == 77
    assert msg.mode_bounds() == (KEEP, LINE)
    assert msg.margin == pytest.approx(0.25)
    assert msg.timestamp_step == 9
    assert epoch.phase == PHASE_CONFIRMING


def test_12_a_witnessed_disagreement_travels_exactly_one_hop_per_round():
    """The bound that makes k_confirm meaningful, measured on a path.

    Robot 0 dissents; after k rounds exactly robots 0..k know. This is the same
    one-hop-per-round law the score consensus obeys, and it is what test_13
    then turns into a commit-safety statement.
    """
    graph = path_graph()
    for k in range(1, N):
        epochs = make_confirming(PROPOSAL_PATTERNS["one_dissenter"],
                                 epoch_ids={i: 1 for i in range(N)})
        sim = simulate_confirm_consensus(epochs, graph, k, start_step=0,
                                         delta_stale_steps=DELTA_STALE)
        informed = sorted(i for i, b in sim["bounds"].items() if b == (KEEP, LINE))
        assert informed == list(range(0, min(k + 1, N))), (k, informed)


# ===========================================================================
# 13-14. the measured limitation: k_confirm smaller than the graph diameter
# ===========================================================================
def test_13_k_confirm_now_covers_the_graph_diameter_and_the_unsafe_commit_is_gone():
    """The G6 repair, verified against a hazard a previous audit had PINNED.

    This test formerly asserted the defect: on a 6-node path (diameter 5) with
    the shipped `k_confirm = 4`, robot 5 sat five hops from the dissenter, never
    witnessed the disagreement, and committed LINE while robots 0-4 retained.
    The swarm-wide claim "confirmation implies agreement" was FALSE whenever
    diameter > k_confirm.

    `k_confirm` is now derived as D_max = max_team_size - 1 = 5, so min/max
    confirmation covers the worst-case chain and NO robot commits against a
    dissenter. Min/max consensus propagates one hop per round exactly as the
    trigger does, which is why the same diameter argument applies to both.
    """
    from rvt_swarm.decentralized.parameters import (default_parameters,
                                                    derived_component_diameter)
    _, _, protocol = default_parameters()
    assert ConsensusParams().k_confirm >= derived_component_diameter(protocol)

    out = run_confirmation(path_graph(), PROPOSAL_PATTERNS["one_dissenter"])
    assert not any(out["committed"].values()), \
        "with k_confirm >= diameter no robot may commit against a dissenter"
    assert all(out["bounds"][i] == (KEEP, LINE) for i in range(N)), out["bounds"]


@pytest.mark.parametrize("k_confirm,expected_commits",
                         [(1, 4), (2, 3), (3, 2), (4, 1), (5, 0), (6, 0)])
def test_14_unsafe_commits_vanish_once_k_confirm_reaches_the_diameter(k_confirm,
                                                                     expected_commits):
    """Exactly one fewer robot commits unsafely per extra confirmation round."""
    out = run_confirmation(path_graph(), PROPOSAL_PATTERNS["one_dissenter"],
                           k_confirm=k_confirm)
    assert sum(out["committed"].values()) == expected_commits


# ===========================================================================
# 20. Gate D2 -- the number itself
# ===========================================================================
def measure_confirmation_success() -> Dict[str, object]:
    """Protocol-level mode-confirmation success over a declared scenario grid.

    The grid is 4 topologies x 4 proposal patterns = 16 synthetic scenarios of
    N = 6, at the shipped parameters (k_confirm = 4, confirm_margin = 0.0,
    delta_stale_steps = 3, no packet loss, no delay). Each robot contributes one
    outcome, so 96 robot-outcomes.

    The ground truth for a robot is its OWN connected component's proposals: if
    they are unanimous the robot should commit; if they are not, it should
    retain. That is the only truth the protocol claims to track, and scoring
    against a swarm-wide truth would penalise it for a connectivity fact.
    """
    should_commit = correct_commit = 0
    should_retain = correct_retain = unsafe = 0
    sub_total = sub_correct = 0
    rows: List[Dict[str, object]] = []

    for topology, graph in sorted(TOPOLOGIES.items()):
        components = connected_components(graph)
        for pattern, proposals in sorted(PROPOSAL_PATTERNS.items()):
            out = run_confirmation(graph, proposals)
            committed = out["committed"]
            row_unsafe = 0
            for comp in components:
                unanimous = len({proposals[i] for i in comp}) == 1
                for i in comp:
                    did = bool(committed[i])
                    ok = did if unanimous else (not did)
                    if unanimous:
                        should_commit += 1
                        correct_commit += 1 if did else 0
                    else:
                        should_retain += 1
                        correct_retain += 0 if did else 1
                        row_unsafe += 1 if did else 0
                    if topology != "path6":       # diameter <= k_confirm subset
                        sub_total += 1
                        sub_correct += 1 if ok else 0
            unsafe += row_unsafe
            rows.append({
                "topology": topology, "pattern": pattern,
                "commit_rate": sum(committed.values()) / float(N),
                "unsafe": row_unsafe,
                "agreement": agreement_rate(out["modes"]),
                "component_agreement": component_agreement(out["modes"], components),
                # per-robot failure records, so a run-to-run comparison can see
                # state leaking between EpochStates rather than only aggregates
                "kinds": tuple(out["kinds"][i] for i in range(N)),
                "modes": tuple(out["modes"][i] for i in range(N)),
            })

    total = should_commit + should_retain
    return {
        "rows": rows,
        "robot_outcomes": total,
        "should_commit": should_commit,
        "correct_commit": correct_commit,
        "should_retain": should_retain,
        "correct_retain": correct_retain,
        "unsafe_commits": unsafe,
        "confirm_when_agreed": correct_commit / float(should_commit),
        "refuse_when_disagreed": correct_retain / float(should_retain),
        "overall_correct": (correct_commit + correct_retain) / float(total),
        "subset_outcomes": sub_total,
        "subset_correct_rate": sub_correct / float(sub_total),
    }


def test_20_gate_d2_mode_confirmation_success_rate():
    """The number Gate D2 asked for, and what it is NOT.

    THIS IS A PROTOCOL-LEVEL MEASUREMENT ON SYNTHETIC PROPOSALS. It is not a
    closed-loop episode measurement, because `runtime.py` does not call the
    confirmation protocol at all (see docs/INTERRUPTED_WORKFLOW_RECOVERY_AUDIT.md
    section 2): proposals here are injected by the test, not produced by a
    selector inside a rollout. The aggregate also depends entirely on the
    synthetic scenario mix declared in `measure_confirmation_success`, which was
    chosen by this test rather than sampled from any run.

    Measured, 96 robot-outcomes over 16 scenarios:

        confirm when the component agreed   57/57 = 1.0000
        refuse when the component disagreed 39/39 = 1.0000
        overall correct decisions           96/96 = 1.0000
        unsafe commits                      0
        diameter <= k_confirm subset        72/72 = 1.0000

    The single unsafe commit this test previously recorded (path6 /
    one_dissenter / robot 5) was the diameter > k_confirm case. The G6 repair
    derives k_confirm = D_max = 5, so it no longer occurs. The grid is fully
    deterministic, so this is a repair, not a randomness artefact.
    """
    m = measure_confirmation_success()

    assert m["robot_outcomes"] == 96
    assert (m["should_commit"], m["correct_commit"]) == (57, 57)
    assert (m["should_retain"], m["correct_retain"]) == (39, 39)
    assert m["confirm_when_agreed"] == pytest.approx(1.0)
    assert m["refuse_when_disagreed"] == pytest.approx(1.0)
    assert m["overall_correct"] == pytest.approx(1.0)
    assert m["unsafe_commits"] == 0
    assert (m["subset_outcomes"], m["subset_correct_rate"]) == (72, 1.0)

    # Gate D2's threshold, evaluated against the metric it names.
    assert m["overall_correct"] >= 0.95
    assert m["confirm_when_agreed"] >= 0.95

    print("\nGate D2 mode-confirmation success (protocol-level, synthetic proposals)")
    print("  {:<14} {:<15} {:>11} {:>7} {:>6} {:>10}".format(
        "topology", "pattern", "commit_rate", "unsafe", "agree", "comp_agree"))
    for row in m["rows"]:
        print("  {:<14} {:<15} {:>11.3f} {:>7} {:>6.1f} {:>10.1f}".format(
            row["topology"], row["pattern"], row["commit_rate"], row["unsafe"],
            row["agreement"], row["component_agreement"]))
    print("  robot-outcomes {}; confirm-when-agreed {}/{} = {:.4f}; "
          "refuse-when-disagreed {}/{} = {:.4f}".format(
              m["robot_outcomes"], m["correct_commit"], m["should_commit"],
              m["confirm_when_agreed"], m["correct_retain"], m["should_retain"],
              m["refuse_when_disagreed"]))
    print("  overall correct {:.4f}; unsafe commits {}; "
          "diameter<=k_confirm subset {:.4f}".format(
              m["overall_correct"], m["unsafe_commits"], m["subset_correct_rate"]))
    print("  NOT a closed-loop episode measurement: runtime.py never calls "
          "the confirmation protocol.")


def test_20b_the_scenario_grid_is_deterministic_and_carries_no_state_between_runs():
    """Re-running the grid must give the identical table, per robot.

    Without this the reported Gate D2 rate could drift between runs and nobody
    would notice. The comparison includes each robot's committed mode and its
    DisagreementEvent kinds, not just the aggregates, so state leaking between
    `EpochState` instances or between runs (a shared mutable default, a cached
    lookup) shows up here instead of quietly changing the published number.
    """
    first = measure_confirmation_success()
    second = measure_confirmation_success()
    assert first["rows"] == second["rows"]
    assert first["overall_correct"] == second["overall_correct"]
    assert first["unsafe_commits"] == second["unsafe_commits"]
