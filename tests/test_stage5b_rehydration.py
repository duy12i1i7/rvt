"""Deterministic V3 row rehydration, and every way it must fail closed."""

import copy
import json

import pytest

from rvt_swarm.decentralized.ego_graph_v2 import _canonical_json
from rvt_swarm.openloop_v3 import synthetic
from rvt_swarm.openloop_v3.rehydrate import (
    V3FingerprintMismatch, V3RehydrationError, rehydrate_row,
    rehydrate_row_payload, runtime_config_for_row,
)
from rvt_swarm.phase9g0r.contracts import (
    recoverability_ego_payload, recoverability_graph_fingerprint,
)
from rvt_swarm.runtime_configuration import (
    DEFAULT_RUNTIME_CONFIG, RuntimeConfig, canonical_runtime_hash,
)
from rvt_swarm.topology_registry import COMPACT, LINE


@pytest.fixture(scope="module")
def transactions():
    return synthetic.synthetic_transactions()


def _row(transactions, *, team_size=5, candidate=COMPACT):
    for transaction in transactions:
        for row in transaction["rows"]:
            identity = row["scientific_identity"]
            if (int(identity["team_size"]) == team_size
                    and int(identity["candidate_topology_id"]) == candidate):
                return copy.deepcopy(row)
    raise AssertionError("fixture lacks the requested row")


def test_round_trip_reproduces_the_sealed_fingerprint(transactions):
    for transaction in transactions:
        for row in transaction["rows"]:
            graph = rehydrate_row(row)
            payload, candidate = recoverability_ego_payload(graph)
            assert candidate == int(row["scientific_identity"]["candidate_topology_id"])
            assert (recoverability_graph_fingerprint(payload)
                    == row["scientific_identity"]["graph_fingerprint"])
            assert int(graph.observer_robot_id) == int(
                row["scientific_identity"]["robot_id"])


def test_rehydration_is_deterministic(transactions):
    row = _row(transactions)
    assert rehydrate_row_payload(row) == rehydrate_row_payload(copy.deepcopy(row))


def test_runtime_config_comes_from_the_row_not_a_global_default(transactions):
    """N = 6 coincides with the default; the other qualified sizes do not."""
    five = runtime_config_for_row(_row(transactions, team_size=5))
    sixteen = runtime_config_for_row(_row(transactions, team_size=16))
    assert canonical_runtime_hash(five) == canonical_runtime_hash(
        RuntimeConfig.for_team_size(5))
    assert canonical_runtime_hash(sixteen) == canonical_runtime_hash(
        RuntimeConfig.for_team_size(16))
    assert canonical_runtime_hash(five) != canonical_runtime_hash(
        DEFAULT_RUNTIME_CONFIG)
    assert canonical_runtime_hash(sixteen) != canonical_runtime_hash(five)


def test_the_wrong_runtime_config_is_refused_rather_than_reinterpreted(transactions):
    row = _row(transactions, team_size=5)
    with pytest.raises(V3RehydrationError):
        rehydrate_row(row, RuntimeConfig.for_team_size(16))


def test_wrong_candidate_id_fails_closed(transactions):
    """The fingerprint cannot catch this; the candidate one-hot must.

    ``recoverability_graph_fingerprint`` refuses a payload that still carries
    candidate_topology_id, so the sealed fingerprint is candidate-blind by
    design. Swapping the candidate in the row identity therefore leaves the
    fingerprint matching, and only the published node features -- which were
    generated per candidate -- reveal the swap.
    """
    row = _row(transactions, candidate=COMPACT)
    row["scientific_identity"] = dict(row["scientific_identity"])
    row["scientific_identity"]["candidate_topology_id"] = LINE
    with pytest.raises(V3FingerprintMismatch) as caught:
        rehydrate_row(row)
    assert "candidate" in str(caught.value)


def test_a_tampered_row_id_fails_closed(transactions):
    row = _row(transactions)
    row["scientific_row_id"] = "b" * 64
    with pytest.raises(V3FingerprintMismatch):
        rehydrate_row(row)


def test_a_tampered_identity_field_fails_closed(transactions):
    """Any identity edit breaks the row id, even one the graph cannot see."""
    row = _row(transactions)
    row["scientific_identity"] = dict(row["scientific_identity"])
    row["scientific_identity"]["family"] = "F7"
    with pytest.raises(V3FingerprintMismatch):
        rehydrate_row(row)


def test_invalid_topology_fails_closed(transactions):
    row = _row(transactions)
    row["scientific_identity"] = dict(row["scientific_identity"])
    row["scientific_identity"]["candidate_topology_id"] = 99
    with pytest.raises(V3RehydrationError):
        rehydrate_row(row)


def test_a_payload_that_already_carries_the_content_hash_fails_closed(transactions):
    row = _row(transactions)
    row["graph_payload"] = dict(row["graph_payload"])
    row["graph_payload"]["content_sha256"] = "0" * 64
    with pytest.raises(V3RehydrationError):
        rehydrate_row(row)


def test_a_payload_that_already_carries_the_candidate_fails_closed(transactions):
    row = _row(transactions)
    payload = copy.deepcopy(row["graph_payload"])
    payload["metadata"]["candidate_topology_id"] = COMPACT
    row["graph_payload"] = payload
    with pytest.raises(V3RehydrationError):
        rehydrate_row(row)


@pytest.mark.parametrize("tensor,index", [
    ("node_x", 0), ("edge_attr", 0),
])
def test_changed_tensor_value_fails_closed(transactions, tensor, index):
    row = _row(transactions)
    payload = copy.deepcopy(row["graph_payload"])
    rows = payload["tensors"][tensor]
    assert rows, "fixture must exercise this tensor"
    rows[index] = [value + 1.0 for value in rows[index]]
    row["graph_payload"] = payload
    with pytest.raises(V3RehydrationError):
        rehydrate_row(row)


def test_changed_mask_fails_closed(transactions):
    row = _row(transactions)
    payload = copy.deepcopy(row["graph_payload"])
    mask = payload["tensors"]["node_feature_valid_mask"]
    mask[0] = [not bool(value) for value in mask[0]]
    row["graph_payload"] = payload
    with pytest.raises(V3RehydrationError):
        rehydrate_row(row)


def test_changed_fingerprint_fails_closed(transactions):
    row = _row(transactions)
    row["scientific_identity"] = dict(row["scientific_identity"])
    row["scientific_identity"]["graph_fingerprint"] = "a" * 64
    with pytest.raises(V3FingerprintMismatch):
        rehydrate_row(row)


def test_unknown_row_schema_fails_closed(transactions):
    row = _row(transactions)
    row["schema_version"] = "rvt-recoverability-v2-supervision-row/v1"
    with pytest.raises(V3RehydrationError):
        rehydrate_row(row)


def test_rehydration_does_not_mutate_the_published_row(transactions):
    row = _row(transactions)
    before = json.dumps(row, sort_keys=True)
    rehydrate_row(row)
    assert json.dumps(row, sort_keys=True) == before


def test_reconstructed_document_uses_the_frozen_canonical_serialization(transactions):
    row = _row(transactions)
    document = json.loads(rehydrate_row_payload(row))
    body = {key: value for key, value in document.items() if key != "content_sha256"}
    import hashlib
    assert document["content_sha256"] == hashlib.sha256(
        _canonical_json(body).encode("ascii")).hexdigest()
