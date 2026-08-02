"""Communication-cost accounting: wire schemas, ledger totals, and rates.

Task 10. Guards `rvt_swarm/decentralized/comm_cost.py`, which until this file
existed had **zero** of its 40 functions exercised (see
`docs/INTERRUPTED_WORKFLOW_RECOVERY_AUDIT.md` §4) and which shipped two wrong
wire schemas as a direct consequence.

What each group of tests is here to stop:

1. `test_no_byte_count_...`, `test_every_schema_...` -- a byte figure that comes
   from a Python object rather than from a declared wire format. Every number in
   the communication-cost table must trace to `struct.calcsize` of a format
   built out of `FieldSpec`s, and must equal `len(payload_bytes())` of a message
   that a radio would really send.
2. `test_verify_schema_sizes_...` -- the four declared sizes drifting from
   49 / 21 / 20 / 16 B without anyone noticing.
3. `test_*_schema_tracks_the_live_epoch_encoder` -- the exact defect the
   recovery audit found: `comm_cost` declared trigger 16 B and confirmation
   17 B while `epoch.py` encodes 21 B and 16 B, and two `except TypeError: pass`
   handlers hid it. These tests compare against the **live encoder**, never
   against a literal, so they track the code instead of restating it.
4. `test_totals_...`, `test_total_is_the_sum_...` -- a ledger whose parts stop
   adding up to its whole: a double-counted category, a category dropped from
   the total, a per-robot or per-decision split that loses messages.
5. `test_peak_...`, `test_average_...` -- a rate that is not `bytes / (steps *
   t_ctrl)` with `t_ctrl = 0.15 s`.
6. `test_..._epoch_module_...` -- the epoch-module probe caching a stale answer,
   or falling back to a provisional schema instead of failing loudly.
7. `test_simulated_episode_...` -- an accounted message that was never sent.

Nothing here asserts anything about trigger or confirmation *traffic*: no such
message is sent anywhere in the system, because `runtime.py` does not import
`epoch.py`. Their rows are schema-only and the tests assert they are flagged
`pending`, which is what stops a zero being read as "free".
"""

from __future__ import annotations

import ast
import struct
from pathlib import Path
from typing import Dict, List, Set, Tuple

import pytest

from rvt_swarm.config import Config
from rvt_swarm.decentralized import comm_cost as CC
from rvt_swarm.decentralized import epoch as EP
from rvt_swarm.decentralized.comms import Beacon
from rvt_swarm.decentralized.consensus import ScoreMessage
from rvt_swarm.decentralized.system_model import (
    KEEP, LINE, CommParams, ConsensusParams,
)
from rvt_swarm.layouts import build_layouts

REPO = Path(__file__).resolve().parents[1]
PKG = REPO / "rvt_swarm" / "decentralized"

# The four declared wire sizes. Written out here so a silent change to any of
# them fails a test; every *other* assertion in this file derives its expected
# size from the live schema or the live encoder instead.
DECLARED_SIZES: Dict[str, int] = {
    CC.BEACON: 49,
    CC.TRIGGER: 21,
    CC.SCORE: 20,
    CC.CONFIRM: 16,
}
T_CTRL = 0.15


# ---------------------------------------------------------------------------
# One real, fully populated message of each of the four categories
# ---------------------------------------------------------------------------
def a_beacon(sender_id: int = 3, step: int = 11, seq: int = 5) -> Beacon:
    return Beacon(sender_id=sender_id, timestamp_step=step, seq=seq,
                  position=(1.5, -2.25), velocity=(0.3, -0.1),
                  role_keep=(0.45, 0.45), role_line=(-1.8, 0.0),
                  committed_mode=LINE, epoch_id=2, degree=4, valid=True)


def a_score(sender_id: int = 3, round_index: int = 1,
            step: int = 11) -> ScoreMessage:
    return ScoreMessage(sender_id=sender_id, epoch_id=2,
                        round_index=round_index, z_keep=0.25, z_line=-0.75,
                        degree=4, timestamp_step=step)


def an_epoch_trigger(sender_id: int = 3, step: int = 11) -> EP.TriggerMessage:
    return EP.TriggerMessage(
        sender_id=sender_id, epoch_counter=2, trigger_flag=True,
        trigger_token=EP.TriggerToken(epoch_counter=2, trigger_timestamp=step,
                                      robot_id=sender_id),
        timestamp_step=step)


def an_epoch_confirm(sender_id: int = 3, step: int = 11) -> EP.ConfirmMessage:
    return EP.ConfirmMessage(sender_id=sender_id, epoch_id=2,
                             selected_mode=LINE, margin=0.5, confirm_round=1,
                             timestamp_step=step)


REAL_MESSAGE = {
    CC.BEACON: a_beacon,
    CC.SCORE: a_score,
    CC.TRIGGER: an_epoch_trigger,
    CC.CONFIRM: an_epoch_confirm,
}


# ---------------------------------------------------------------------------
# 1. Bytes come from an explicit wire schema, never from a Python object
# ---------------------------------------------------------------------------
FORBIDDEN_SIZING = ("getsizeof", "__sizeof__", "pickle", "marshal", "nbytes",
                    "itemsize", "sizeof", "dumps")
SIZING_SOURCES = ("comm_cost.py", "comms.py", "consensus.py", "epoch.py")


def _code_identifiers(path: Path) -> Set[str]:
    """Every name referenced in *code* (docstrings and comments excluded)."""
    tree = ast.parse(path.read_text())
    names: Set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.add((node.module or "").split(".")[0])
    return names


def test_no_byte_count_is_derived_from_a_python_object_size():
    """No figure may come from `sys.getsizeof`, `__sizeof__`, or a serializer.

    Parsed as an AST, so the prose in `comm_cost.py`'s own docstring -- which
    says exactly this -- cannot make the test pass by mentioning the words.
    """
    for name in SIZING_SOURCES:
        used = _code_identifiers(PKG / name)
        offending = sorted(used.intersection(FORBIDDEN_SIZING))
        assert not offending, (
            f"{name} references {offending} in code; every communication byte "
            f"count must come from an explicit struct-packed wire schema")


def test_every_declared_size_is_the_sum_of_its_field_specs_and_a_real_encoding():
    """schema.size_bytes == sum(FieldSpec.n_bytes) == len(payload_bytes())."""
    assert set(CC.WIRE_SCHEMAS) == set(CC.MESSAGE_TYPES)
    for name, schema in CC.WIRE_SCHEMAS.items():
        schema.check()                       # declared widths vs packed size
        by_field = sum(f.n_bytes for f in schema.fields)
        assert schema.declared_sum == by_field
        assert schema.size_bytes == by_field, (
            f"{name}: field widths sum to {by_field} B but the packed size is "
            f"{schema.size_bytes} B")
        # The format is exactly the concatenation of the per-field struct codes,
        # little-endian and unpadded -- so size_bytes is a function of the field
        # table and of nothing else.
        assert schema.struct_format == "<" + "".join(
            f.struct_code for f in schema.fields)
        assert struct.calcsize(schema.struct_format) == by_field
        # ... and the same number is the length of a message a radio would send.
        msg = REAL_MESSAGE[name]()
        assert CC.message_type_of(msg) == name
        assert len(CC.payload_of(msg)) == by_field
        assert CC.wire_size(msg) == by_field


def test_schema_check_rejects_a_field_width_that_disagrees_with_its_code():
    """A FieldSpec whose declared width is off by one must be caught."""
    good = CC.SCORE_SCHEMA
    bad = CC.WireSchema(
        message_type=good.message_type, source="test-only", provisional=True,
        fields=tuple(
            CC.FieldSpec(f.name, f.wire_type, f.struct_code,
                         f.n_bytes + (1 if f.name == "z_keep" else 0), f.note)
            for f in good.fields))
    assert bad.declared_sum == good.declared_sum + 1
    assert bad.size_bytes == good.size_bytes          # the packing is unchanged
    with pytest.raises(ValueError):
        bad.check()


def test_wire_size_does_not_depend_on_the_values_carried():
    """Fixed-size by construction: cost is a function of message count alone.

    `simulate_episode_message_cost` relies on this when it says the measured
    byte counts are unbiased by running the episode in a single committed mode.
    """
    variants = [
        a_beacon(sender_id=0, step=0, seq=0),
        a_beacon(sender_id=65535, step=10 ** 6, seq=10 ** 6),
        Beacon(sender_id=7, timestamp_step=3, seq=1, position=(-9.0, 9.0),
               velocity=(0.0, 0.0), role_keep=(0.0, 0.0), role_line=(0.0, 0.0),
               committed_mode=KEEP, epoch_id=0, degree=0, valid=False),
    ]
    assert {len(CC.payload_of(m)) for m in variants} == {DECLARED_SIZES[CC.BEACON]}
    scores = [a_score(round_index=0), a_score(sender_id=11, round_index=5),
              ScoreMessage(0, 0, 0, -1e30, 1e30, 255, 0)]
    assert {len(CC.payload_of(m)) for m in scores} == {DECLARED_SIZES[CC.SCORE]}
    triggers = [an_epoch_trigger(),
                EP.TriggerMessage(sender_id=0, epoch_counter=0,
                                  trigger_flag=False, trigger_token=None,
                                  timestamp_step=0)]
    assert {len(m.payload_bytes()) for m in triggers} == {DECLARED_SIZES[CC.TRIGGER]}


def test_markdown_table_lists_every_field_and_the_packed_total():
    for name, schema in CC.WIRE_SCHEMAS.items():
        table = schema.markdown_table()
        for f in schema.fields:
            assert f"`{f.name}`" in table
            assert f"`{f.struct_code}`" in table
        assert f"**{schema.size_bytes}**" in table
        assert f"`{schema.struct_format}`" in table
        # one row per field, plus header, separator and total
        assert len(table.strip().splitlines()) == len(schema.fields) + 3


# ---------------------------------------------------------------------------
# 2. The four declared sizes, verified
# ---------------------------------------------------------------------------
def test_verify_schema_sizes_reports_ok_and_not_provisional_for_all_four():
    table = CC.verify_schema_sizes()
    assert set(table) == set(CC.MESSAGE_TYPES)
    for name, want in DECLARED_SIZES.items():
        row = table[name]
        assert row["declared_bytes"] == want, f"{name} declared size"
        assert row["declared_field_sum"] == want, f"{name} field-width sum"
        assert row["measured_bytes"] == want, f"{name} measured encoding"
        assert row["provisional"] is False, f"{name} still provisional"
        assert row["ok"] is True, f"{name} not ok: {row}"


def test_assert_schema_sizes_passes_for_all_four_message_types():
    table = CC.assert_schema_sizes()
    assert sorted(table) == sorted(CC.MESSAGE_TYPES)
    assert all(row["ok"] for row in table.values())


def test_sample_messages_covers_every_declared_category():
    """`_sample_messages` must produce one real instance per category."""
    samples = CC._sample_messages()
    assert sorted(CC.message_type_of(m) for m in samples) == sorted(CC.MESSAGE_TYPES)
    for msg in samples:
        assert len(CC.payload_of(msg)) == \
            CC.WIRE_SCHEMAS[CC.message_type_of(msg)].size_bytes


# ---------------------------------------------------------------------------
# 3. Regression: the schemas track the live epoch.py encoders
# ---------------------------------------------------------------------------
def test_trigger_schema_tracks_the_live_epoch_encoder():
    """The defect: TRIGGER_SCHEMA declared 16 B; the encoder produces 21 B.

    Compared against `epoch.TriggerMessage.payload_bytes()` rather than against
    a literal, so if either side moves the test moves with it and only a
    *divergence* is red.
    """
    encoded = an_epoch_trigger().payload_bytes()
    assert CC.TRIGGER_SCHEMA.size_bytes == len(encoded)
    assert CC.TRIGGER_SCHEMA.declared_sum == len(encoded)
    assert CC.TRIGGER_SCHEMA.provisional is False
    assert CC.TRIGGER_SCHEMA.source.startswith(CC.EPOCH_MODULE)
    assert CC.verify_schema_sizes()[CC.TRIGGER]["measured_bytes"] == len(encoded)
    # epoch.py's own declared constant is the third independent statement of it
    assert EP.TRIGGER_PAYLOAD_BYTES == len(encoded)
    # the 10 bytes the old declaration was missing are the token
    assert len(EP.TriggerToken(1, 2, 3).pack()) == EP.TRIGGER_TOKEN_BYTES == 10


def test_confirm_schema_tracks_the_live_epoch_encoder():
    """The defect: CONFIRM_SCHEMA declared 17 B; the encoder produces 16 B."""
    encoded = an_epoch_confirm().payload_bytes()
    assert CC.CONFIRM_SCHEMA.size_bytes == len(encoded)
    assert CC.CONFIRM_SCHEMA.declared_sum == len(encoded)
    assert CC.CONFIRM_SCHEMA.provisional is False
    assert CC.CONFIRM_SCHEMA.source.startswith(CC.EPOCH_MODULE)
    assert CC.verify_schema_sizes()[CC.CONFIRM]["measured_bytes"] == len(encoded)
    assert EP.CONFIRM_PAYLOAD_BYTES == len(encoded)


def test_every_schema_tracks_whatever_encoder_its_source_names():
    """Generalisation of the two above: declared == measured, all four, live."""
    for name, schema in CC.WIRE_SCHEMAS.items():
        measured = len(CC.payload_of(REAL_MESSAGE[name]()))
        assert schema.size_bytes == measured, (
            f"{name}: schema declares {schema.size_bytes} B, its encoder "
            f"({schema.source}) produces {measured} B")


def test_comm_cost_mirror_encoders_are_byte_identical_to_epoch():
    """`comm_cost`'s field-by-field encoders must agree with `epoch.py` exactly.

    Two independent encoders of the same schema. Byte equality -- not just
    length equality -- is what makes the FieldSpec table in the documentation a
    statement about the packet the protocol really sends.
    """
    mirror_trigger = CC.TriggerMessage(
        sender_id=3, epoch_counter=2, trigger_flag=1, token_epoch_counter=2,
        token_timestamp=11, token_robot_id=3, timestamp_step=11)
    assert mirror_trigger.payload_bytes() == an_epoch_trigger().payload_bytes()

    mirror_confirm = CC.ConfirmMessage(
        sender_id=3, epoch_id=2, selected_mode=LINE, margin=0.5,
        confirm_round=1, timestamp_step=11)
    assert mirror_confirm.payload_bytes() == an_epoch_confirm().payload_bytes()

    # an absent token is all-zero on the wire, and still the full 21 bytes
    none_token = CC.TriggerMessage(
        sender_id=1, epoch_counter=0, trigger_flag=0, token_epoch_counter=0,
        token_timestamp=0, token_robot_id=0, timestamp_step=0)
    assert none_token.payload_bytes() == EP.TriggerMessage(
        sender_id=1, epoch_counter=0, trigger_flag=False, trigger_token=None,
        timestamp_step=0).payload_bytes()
    assert len(none_token.payload_bytes()) == DECLARED_SIZES[CC.TRIGGER]


def test_score_message_encoder_is_the_declared_schema():
    msg = a_score()
    packed = CC.encode_score_message(msg)
    assert packed == CC.payload_of(msg)          # no payload_bytes() on the class
    assert len(packed) == CC.SCORE_SCHEMA.size_bytes
    assert struct.unpack(CC.SCORE_SCHEMA.struct_format, packed) == (
        msg.sender_id, msg.epoch_id, msg.round_index,
        pytest.approx(msg.z_keep), pytest.approx(msg.z_line),
        msg.degree, msg.timestamp_step)


# ---------------------------------------------------------------------------
# 4 + 5. Ledger: totals equal the sum of the parts, per category / robot /
#        decision / episode
# ---------------------------------------------------------------------------
N_ROBOTS = 4
K_SCORE = 2

# A scripted episode whose every byte is known in advance:
#   steps 0..3, 4 robots, one beacon each per step        16 x 49 = 784 B
#   score consensus, decision 0, rounds 0..1, steps 0..1   8 x 20 = 160 B
#   trigger, decision 0, step 0, one per robot             4 x 21 =  84 B
#   confirmation, decision 1, step 2, one per robot        4 x 16 =  64 B
SCRIPT_BEACON_BYTES = 16 * 49
SCRIPT_SCORE_BYTES = 8 * 20
SCRIPT_TRIGGER_BYTES = 4 * 21
SCRIPT_CONFIRM_BYTES = 4 * 16
SCRIPT_TOTAL_BYTES = (SCRIPT_BEACON_BYTES + SCRIPT_SCORE_BYTES
                      + SCRIPT_TRIGGER_BYTES + SCRIPT_CONFIRM_BYTES)
SCRIPT_STEPS = 4


def scripted_accountant(keep_payloads: bool = True) -> CC.MessageAccountant:
    acct = CC.MessageAccountant(N_ROBOTS, params=CommParams(), label="scripted",
                                keep_payloads=keep_payloads)
    for step in range(SCRIPT_STEPS):
        acct.current_decision = 0 if step < 2 else 1
        for i in range(N_ROBOTS):
            acct.record_sent(a_beacon(sender_id=i, step=step, seq=step),
                             step=step, round_index=step)
    for r in range(K_SCORE):
        for i in range(N_ROBOTS):
            acct.record_sent(a_score(sender_id=i, round_index=r, step=r),
                             step=r, round_index=r, decision_index=0)
    for i in range(N_ROBOTS):
        acct.record_sent(an_epoch_trigger(sender_id=i, step=0), step=0,
                         round_index=0, decision_index=0)
    for i in range(N_ROBOTS):
        acct.record_sent(an_epoch_confirm(sender_id=i, step=2), step=2,
                         round_index=0, decision_index=1)
    acct.set_episode_steps(SCRIPT_STEPS)
    return acct


def test_totals_equal_the_sum_of_the_individual_message_sizes():
    """Episode total == sum of len(payload_bytes()) over every message sent."""
    acct = scripted_accountant()
    acct.assert_consistent()
    assert acct.total_messages == 16 + 8 + 4 + 4
    assert acct.total_bytes == SCRIPT_TOTAL_BYTES
    assert acct.payload_bytes_ledger_total() == acct.total_bytes
    # recomputed from the wire schema and the message counts, independently
    from_counts = sum(CC.WIRE_SCHEMAS[t].size_bytes * n for t, n in
                      ((CC.BEACON, 16), (CC.SCORE, 8), (CC.TRIGGER, 4),
                       (CC.CONFIRM, 4)))
    assert from_counts == acct.total_bytes


def test_totals_equal_the_sum_of_the_parts_per_robot():
    acct = scripted_accountant()
    per_robot = acct._tx_bytes_by_robot
    assert sorted(per_robot) == list(range(N_ROBOTS))
    # every robot sent the same script: 4 beacons, 2 scores, 1 trigger, 1 confirm
    expected = 4 * 49 + 2 * 20 + 21 + 16
    assert set(per_robot.values()) == {expected}
    assert sum(per_robot.values()) == acct.total_bytes
    assert sum(acct._tx_msgs_by_robot.values()) == acct.total_messages
    assert acct.report()["total"]["bytes_per_robot_per_episode"] == \
        pytest.approx(acct.total_bytes / N_ROBOTS)


def test_totals_equal_the_sum_of_the_parts_per_decision():
    acct = scripted_accountant()
    per_decision = acct._tx_bytes_by_decision
    assert sorted(per_decision) == [0, 1]
    # decision 0: beacons at steps 0,1 + all score + all trigger
    assert per_decision[0] == 8 * 49 + SCRIPT_SCORE_BYTES + SCRIPT_TRIGGER_BYTES
    # decision 1: beacons at steps 2,3 + all confirmation
    assert per_decision[1] == 8 * 49 + SCRIPT_CONFIRM_BYTES
    assert sum(per_decision.values()) == acct.total_bytes
    assert acct.n_decisions == 2


def test_the_four_categories_are_accounted_separately_and_sum_to_the_total():
    """Requirement: discovery / trigger / score / confirmation, kept apart."""
    rep = scripted_accountant().report()
    cats = rep["categories"]
    assert sorted(cats) == sorted(CC.MESSAGE_TYPES)
    assert cats[CC.BEACON]["bytes"] == SCRIPT_BEACON_BYTES
    assert cats[CC.SCORE]["bytes"] == SCRIPT_SCORE_BYTES
    assert cats[CC.TRIGGER]["bytes"] == SCRIPT_TRIGGER_BYTES
    assert cats[CC.CONFIRM]["bytes"] == SCRIPT_CONFIRM_BYTES
    assert sum(cats[t]["bytes"] for t in CC.MESSAGE_TYPES) == rep["total"]["bytes"]
    assert sum(cats[t]["messages"] for t in CC.MESSAGE_TYPES) == \
        rep["total"]["messages"]
    assert rep["total"]["bytes"] == SCRIPT_TOTAL_BYTES
    # no category may borrow another's per-message size
    for name in CC.MESSAGE_TYPES:
        assert cats[name]["wire_bytes_per_message"] == DECLARED_SIZES[name]
        assert cats[name]["bytes"] == \
            cats[name]["messages"] * DECLARED_SIZES[name]


def test_receptions_are_a_separate_ledger_from_transmissions():
    """A broadcast is one transmission and many receptions; never merged."""
    acct = CC.MessageAccountant(N_ROBOTS)
    beacon = a_beacon(sender_id=0, step=0, seq=0)
    acct.record_sent(beacon, step=0)
    for receiver in (1, 2, 3):
        acct.record_received(beacon, receiver_id=receiver, step=0)
    acct.assert_consistent()
    rep = acct.report()
    assert rep["total"]["messages"] == 1
    assert rep["total"]["bytes"] == 49
    assert rep["total"]["received_messages"] == 3
    assert rep["total"]["received_bytes"] == 3 * 49
    assert sum(rep["categories"][t]["received_bytes"] for t in CC.MESSAGE_TYPES) \
        == rep["total"]["received_bytes"]


def test_a_byte_count_cannot_be_recorded_directly():
    """The only way into the ledger is a real encoding."""
    acct = CC.MessageAccountant(2)
    with pytest.raises(TypeError):
        acct.record_sent_bytes(CC.BEACON, 0, 49, step=0)           # type: ignore[arg-type]
    with pytest.raises(TypeError):
        acct.record_received_bytes(CC.BEACON, 0, 49, step=0)       # type: ignore[arg-type]
    assert acct.total_bytes == 0


def test_a_payload_that_disagrees_with_its_schema_is_refused():
    acct = CC.MessageAccountant(2)
    for wrong in (b"\x00" * 48, b"\x00" * 50):
        with pytest.raises(ValueError):
            acct.record_sent_bytes(CC.BEACON, 0, wrong, step=0)
        with pytest.raises(ValueError):
            acct.record_received_bytes(CC.BEACON, 0, wrong, step=0)
    with pytest.raises(ValueError):
        acct.record_sent_bytes("gossip", 0, b"\x00" * 4, step=0)
    with pytest.raises(ValueError):
        acct.record_received_bytes("gossip", 0, b"\x00" * 4, step=0)
    assert acct.total_bytes == 0
    acct.assert_consistent()


def test_unencodable_objects_are_refused():
    class NotAMessage(object):
        pass

    class BadEncoder(object):
        def payload_bytes(self):
            return "20 bytes, honest"

    with pytest.raises(TypeError):
        CC.message_type_of(NotAMessage())
    with pytest.raises(TypeError):
        CC.payload_of(NotAMessage())
    with pytest.raises(TypeError):
        CC.payload_of(BadEncoder())


def test_accountant_rejects_impossible_framing():
    with pytest.raises(ValueError):
        CC.MessageAccountant(0)
    with pytest.raises(ValueError):
        CC.MessageAccountant(2).set_episode_steps(-1)


def test_payload_cross_check_is_unavailable_without_retained_payloads():
    acct = scripted_accountant(keep_payloads=False)
    acct.assert_consistent()                       # still valid, minus that check
    assert acct.total_bytes == SCRIPT_TOTAL_BYTES
    with pytest.raises(RuntimeError):
        acct.payload_bytes_ledger_total()


# ---------------------------------------------------------------------------
# 6. Rates: peak and average bytes per second from t_ctrl = 0.15 s
# ---------------------------------------------------------------------------
def test_time_base_is_t_ctrl_and_comes_from_comm_params():
    acct = scripted_accountant()
    assert CommParams().t_ctrl == T_CTRL
    assert CommParams().t_comm == T_CTRL          # one beacon per control step
    assert acct.t_ctrl == T_CTRL
    assert acct.episode_steps == SCRIPT_STEPS
    assert acct.episode_seconds == pytest.approx(SCRIPT_STEPS * T_CTRL)


def test_peak_and_average_bytes_per_second_follow_from_the_message_counts():
    rep = scripted_accountant().report()
    seconds = SCRIPT_STEPS * T_CTRL

    # Per-step totals of the scripted traffic, recomputed by hand:
    #   step 0: 4 beacons + 4 scores + 4 triggers = 4*(49+20+21) = 360 B
    #   step 1: 4 beacons + 4 scores             = 4*(49+20)     = 276 B
    #   step 2: 4 beacons + 4 confirmations      = 4*(49+16)     = 260 B
    #   step 3: 4 beacons                        = 4*49          = 196 B
    per_step = [4 * (49 + 20 + 21), 4 * (49 + 20), 4 * (49 + 16), 4 * 49]
    assert sum(per_step) == SCRIPT_TOTAL_BYTES

    total = rep["total"]
    assert total["peak_bytes_per_second"] == pytest.approx(max(per_step) / T_CTRL)
    assert total["average_bytes_per_second"] == pytest.approx(sum(per_step) / seconds)
    # average rate x duration must return the byte total exactly
    assert total["average_bytes_per_second"] * rep["episode_seconds"] == \
        pytest.approx(total["bytes"])

    cats = rep["categories"]
    # beacons are uniform: every step carries N of them
    assert cats[CC.BEACON]["peak_bytes_per_second"] == pytest.approx(4 * 49 / T_CTRL)
    assert cats[CC.BEACON]["average_bytes_per_second"] == \
        pytest.approx(SCRIPT_BEACON_BYTES / seconds)
    # score consensus occupies 2 of the 4 steps, so its peak is twice its average
    assert cats[CC.SCORE]["peak_bytes_per_second"] == pytest.approx(4 * 20 / T_CTRL)
    assert cats[CC.SCORE]["average_bytes_per_second"] == \
        pytest.approx(SCRIPT_SCORE_BYTES / seconds)
    assert cats[CC.SCORE]["peak_bytes_per_second"] == \
        pytest.approx(2.0 * cats[CC.SCORE]["average_bytes_per_second"])
    # per-robot peak is the busiest single robot in the busiest single step
    assert total["peak_bytes_per_second_per_robot"] == \
        pytest.approx((49 + 20 + 21) / T_CTRL)
    assert total["average_bytes_per_second_per_robot"] == \
        pytest.approx(sum(per_step) / seconds / N_ROBOTS)


def test_average_rate_uses_the_declared_episode_length_not_the_busy_span():
    """Silent steps at the end of an episode must still count as airtime."""
    acct = CC.MessageAccountant(1)
    acct.record_sent(a_beacon(sender_id=0, step=0, seq=0), step=0)
    assert acct.episode_steps == 1                       # inferred from the span
    assert acct.report()["total"]["average_bytes_per_second"] == \
        pytest.approx(49 / T_CTRL)
    acct.set_episode_steps(10)
    assert acct.episode_steps == 10
    assert acct.episode_seconds == pytest.approx(1.5)
    assert acct.report()["total"]["average_bytes_per_second"] == \
        pytest.approx(49 / 1.5)
    assert acct.report()["total"]["peak_bytes_per_second"] == \
        pytest.approx(49 / T_CTRL)   # peak is unaffected by the framing


def test_an_empty_ledger_reports_zero_rather_than_dividing_by_zero():
    rep = CC.MessageAccountant(3).report()
    assert rep["episode_steps"] == 0
    assert rep["episode_seconds"] == 0.0
    assert rep["total"]["bytes"] == 0
    assert rep["total"]["average_bytes_per_second"] == 0.0
    assert rep["total"]["peak_bytes_per_second"] == 0.0


# ---------------------------------------------------------------------------
# 7. The epoch-module dependency
# ---------------------------------------------------------------------------
def test_epoch_module_status_names_the_epoch_classes():
    CC.reset_epoch_lookup()
    status = CC.epoch_module_status()
    assert status["module"] == CC.EPOCH_MODULE == "rvt_swarm.decentralized.epoch"
    assert status["available"] is True
    assert status["trigger_class"] == "TriggerMessage"
    assert status["confirm_class"] == "ConfirmMessage"
    assert status["trigger_schema_source"] == "epoch"
    assert status["confirm_schema_source"] == "epoch"


def test_status_is_cached_and_reset_clears_the_cache():
    CC.reset_epoch_lookup()
    assert CC._EPOCH_LOOKUP == {}
    CC.epoch_module_status()
    assert CC._EPOCH_LOOKUP.get("checked") is True
    assert CC._EPOCH_LOOKUP.get("module") is not None
    CC.reset_epoch_lookup()
    assert CC._EPOCH_LOOKUP == {}


def test_absent_epoch_module_is_reported_and_fails_loudly():
    """With `epoch.py` gone, the trigger/confirm rows must not fall back.

    The old behaviour -- `except TypeError: pass` around the sample
    construction -- is exactly how a 16-byte declaration survived against a
    21-byte encoder.
    """
    CC.reset_epoch_lookup()
    CC._EPOCH_LOOKUP["checked"] = True
    CC._EPOCH_LOOKUP["module"] = None                # simulate an absent module
    try:
        status = CC.epoch_module_status()
        assert status["available"] is False
        assert status["trigger_class"] is None
        assert status["confirm_class"] is None
        assert status["trigger_schema_source"] == "provisional"
        assert status["confirm_schema_source"] == "provisional"
        with pytest.raises(ImportError):
            CC._sample_messages()
        with pytest.raises(ImportError):
            CC.verify_schema_sizes()
        with pytest.raises(ImportError):
            CC.assert_schema_sizes()
    finally:
        CC.reset_epoch_lookup()
    # ... and the reset restores the real answer
    assert CC.epoch_module_status()["available"] is True
    assert CC.assert_schema_sizes()[CC.TRIGGER]["ok"] is True


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------
def test_report_carries_the_schema_and_the_epoch_status():
    rep = scripted_accountant().report()
    assert rep["consistent"] is True
    assert rep["n_robots"] == N_ROBOTS
    assert rep["t_ctrl_seconds"] == T_CTRL
    assert rep["label"] == "scripted"
    assert rep["schema"] == CC.verify_schema_sizes()
    assert rep["epoch_module"] == CC.epoch_module_status()
    assert rep["episode_steps"] == SCRIPT_STEPS
    assert rep["decisions_per_episode"] == 2


def test_a_category_with_no_recorded_message_is_flagged_pending():
    """A zero in a cost table must say "never sent", not "free".

    `runtime.py` does not import `epoch.py`, so trigger and confirmation
    traffic does not exist yet. Their rows are schema-only. This is the guard
    that stops such a row being read as a measurement.
    """
    acct = CC.MessageAccountant(2)
    acct.record_sent(a_beacon(sender_id=0, step=0, seq=0), step=0)
    rep = acct.report()
    for name in CC.MESSAGE_TYPES:
        row = rep["categories"][name]
        assert row["pending"] is (row["messages"] == 0), (
            f"{name}: {row['messages']} messages recorded but "
            f"pending={row['pending']}")
    assert rep["categories"][CC.BEACON]["pending"] is False
    assert rep["categories"][CC.TRIGGER]["pending"] is True
    assert rep["categories"][CC.CONFIRM]["pending"] is True
    text = CC.format_report(rep)
    assert "trigger [PENDING]" in text
    assert "mode_confirmation [PENDING]" in text
    assert "beacon [PENDING]" not in text


def test_format_report_prints_every_category_and_the_total():
    text = CC.format_report(scripted_accountant().report())
    lines = text.splitlines()
    for name in CC.MESSAGE_TYPES:
        assert any(line.startswith(name) for line in lines), name
    assert any(line.startswith("TOTAL") for line in lines)
    assert "0.150 s" in text
    assert "[PENDING]" not in text          # the scripted ledger sent all four


def test_mean_of_reports_averages_matching_leaves():
    short = CC.MessageAccountant(N_ROBOTS, label="short")
    short.record_sent(a_beacon(sender_id=0, step=0, seq=0), step=0)
    short.set_episode_steps(2)
    full = scripted_accountant()
    mean = CC.mean_of_reports([short.report(), full.report()])
    assert mean["episodes"] == 2
    assert mean["episode_steps"] == pytest.approx((2 + SCRIPT_STEPS) / 2.0)
    assert mean["total"]["bytes"] == pytest.approx((49 + SCRIPT_TOTAL_BYTES) / 2.0)
    assert mean["categories"][CC.BEACON]["bytes"] == \
        pytest.approx((49 + SCRIPT_BEACON_BYTES) / 2.0)
    assert mean["categories"][CC.BEACON]["wire_bytes_per_message"] == 49
    # pending only if the category was unexercised in *every* episode
    assert mean["categories"][CC.TRIGGER]["pending"] is False   # full sent some
    assert mean["categories"][CC.BEACON]["pending"] is False
    with pytest.raises(ValueError):
        CC.mean_of_reports([])


# ---------------------------------------------------------------------------
# The instrumented episode: only messages that were really sent are accounted
# ---------------------------------------------------------------------------
def val_layout(family: str):
    return [lay for lay in build_layouts("val") if lay.family == family][0]


def test_simulated_episode_accounts_exactly_the_messages_that_were_sent():
    """Beacons and score messages counted against the protocol's own cadence.

    One beacon per robot per control step (`t_comm == t_ctrl`), and `k_score`
    score messages per robot per decision epoch. Both figures are checked
    against the episode's own step and epoch counts, not against constants.
    """
    cfg = Config()
    cfg.train.device = "cpu"
    protocol = ConsensusParams()
    n, k, interval = 4, protocol.k_score, protocol.decision_interval
    out = CC.simulate_episode_message_cost(
        cfg, n, val_layout("line_corridor"), seed=3, mode=LINE, max_steps=6)
    acct = out["accountant"]
    acct.assert_consistent()
    steps = int(out["steps"])
    epochs = int(out["decisions"])
    assert steps == 6
    assert epochs == 1 + (steps - 1) // interval

    rep = acct.report()
    cats = rep["categories"]
    assert cats[CC.BEACON]["messages"] == n * steps
    assert cats[CC.SCORE]["messages"] == n * k * epochs
    assert cats[CC.BEACON]["bytes"] == n * steps * 49
    assert cats[CC.SCORE]["bytes"] == n * k * epochs * 20
    assert rep["total"]["bytes"] == acct.payload_bytes_ledger_total()

    # receptions are what the radios really demodulated
    assert cats[CC.BEACON]["received_messages"] == out["channel_delivered_links"]
    assert cats[CC.BEACON]["received_messages"] <= n * (n - 1) * steps
    assert cats[CC.SCORE]["received_messages"] > 0

    # nothing may appear in a category the runtime cannot send
    assert cats[CC.TRIGGER]["messages"] == 0
    assert cats[CC.CONFIRM]["messages"] == 0
    assert cats[CC.TRIGGER]["pending"] is True
    assert cats[CC.CONFIRM]["pending"] is True

    # rates, from t_ctrl and the counts
    assert rep["episode_seconds"] == pytest.approx(steps * T_CTRL)
    assert cats[CC.BEACON]["average_bytes_per_second"] == \
        pytest.approx(n * 49 / T_CTRL)
    assert cats[CC.BEACON]["peak_bytes_per_second"] == \
        pytest.approx(n * 49 / T_CTRL)


def test_simulated_episode_refuses_an_undeclared_mode():
    cfg = Config()
    cfg.train.device = "cpu"
    with pytest.raises(ValueError):
        CC.simulate_episode_message_cost(cfg, 4, val_layout("keep_open"),
                                         seed=0, mode=1, max_steps=2)


def test_message_cost_is_the_same_in_both_modes_for_the_same_step_count():
    """Fixed-size wire format: the mode changes the trajectory, not the bytes."""
    cfg = Config()
    cfg.train.device = "cpu"
    lay = val_layout("keep_open")
    per_step = {}
    for mode in (KEEP, LINE):
        out = CC.simulate_episode_message_cost(cfg, 4, lay, seed=5, mode=mode,
                                               max_steps=4)
        rep = out["accountant"].report()
        per_step[mode] = (rep["categories"][CC.BEACON]["bytes"]
                          / max(1, int(out["steps"])))
    assert per_step[KEEP] == per_step[LINE] == 4 * 49
