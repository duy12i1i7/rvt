"""Deterministic, read-only rehydration of a published V3 supervised row.

``recoverability_ego_payload`` strips two fields before publication: the scalar
``metadata.candidate_topology_id``, which moved into the scientific row identity,
and ``content_sha256``, which would otherwise have covered it. The strict graph
loader requires both, so a published row cannot be loaded without reconstructing
them. That reconstruction is what this module does, and nothing else.

The reconstruction is proved rather than assumed: after loading, the graph is
put back through the exact publication transform and its fingerprint must equal
the one stored in the frozen row identity. If it does not, the row is refused.
There is no repair path, no tolerance and no fallback -- a fingerprint mismatch
means the bytes on disk are not the bytes that were sealed, which is a provenance
failure, not a loading inconvenience.

Nothing here writes. The canonical transaction JSON is opened read-only and the
reconstructed payload lives only in memory.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Optional

from ..decentralized.ego_graph_v2 import (
    NODE_FEATURE_SLICES, RobotLocalEgoGraph, _canonical_json,
    load_robot_local_ego_graph,
)
from ..phase9g0r.contracts import (
    recoverability_ego_payload, recoverability_graph_fingerprint,
)
from ..phase9g0r.contracts_v3 import recoverability_scientific_row_id_v3
from ..topology_registry import PRIMARY_TOPOLOGY_IDS
from ..runtime_configuration import RuntimeConfig
from ..topology_registry import COMPACT, LINE

V3_ROW_SCHEMA_VERSION = "rvt-recoverability-v3-supervision-row/v1"
V3_GRAPH_PAYLOAD_SCHEMA_VERSION = "rvt-recoverability-ego-payload-binding/v1"


class V3RehydrationError(ValueError):
    """A published V3 row cannot be reconstructed into a graph. Fails closed."""


class V3FingerprintMismatch(V3RehydrationError):
    """The reconstructed graph is not the graph whose fingerprint was sealed."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise V3RehydrationError(message)


def rehydrate_row_payload(row: Mapping[str, Any]) -> str:
    """Rebuild the exact serialized graph document for one published row.

    ``_canonical_json`` is imported from the ego-graph module on purpose. The
    content hash must be computed over byte-for-byte the same serialization the
    dumper used; re-implementing that serialization here would create a second
    definition that could drift from the first.
    """
    _require(isinstance(row, Mapping), "a V3 row must be an object")
    _require(row.get("schema_version") == V3_ROW_SCHEMA_VERSION,
             f"unknown supervised row schema {row.get('schema_version')!r}")
    _require(row.get("graph_payload_schema_version") == V3_GRAPH_PAYLOAD_SCHEMA_VERSION,
             "unknown graph payload binding")
    identity = row.get("scientific_identity")
    _require(isinstance(identity, Mapping), "a V3 row must carry its scientific identity")
    payload = row.get("graph_payload")
    _require(isinstance(payload, Mapping), "a V3 row must carry a graph payload")

    candidate = identity.get("candidate_topology_id")
    _require(isinstance(candidate, int) and not isinstance(candidate, bool),
             "candidate_topology_id must be an integer")
    _require(int(candidate) in (COMPACT, LINE),
             "the candidate topology must be COMPACT or LINE")

    document = json.loads(json.dumps(payload, allow_nan=False, sort_keys=True))
    _require("content_sha256" not in document,
             "a published payload must not already carry content_sha256")
    metadata = document.get("metadata")
    _require(isinstance(metadata, dict), "the graph payload must carry metadata")
    _require("candidate_topology_id" not in metadata,
             "a published payload must not already carry the candidate topology")
    metadata["candidate_topology_id"] = int(candidate)
    document["metadata"] = metadata
    body = {key: value for key, value in document.items() if key != "content_sha256"}
    document["content_sha256"] = hashlib.sha256(
        _canonical_json(body).encode("ascii")).hexdigest()
    return _canonical_json(document) + "\n"


def runtime_config_for_row(row: Mapping[str, Any]) -> RuntimeConfig:
    """The runtime configuration a published row was generated under.

    This is NOT the default configuration. The generator builds every ego graph
    through ``RuntimeConfig.for_team_size(N)``, and each qualified team size
    hashes differently -- N = 6 happens to coincide with the default, and the
    other four do not. Deriving the configuration from the frozen row identity's
    ``team_size`` is therefore mandatory: a rehydrator that assumed the default
    would refuse four fifths of the official rows, and a rehydrator that skipped
    the loader's hash check would silently reconstruct graphs under the wrong
    physical configuration.
    """
    identity = row.get("scientific_identity")
    _require(isinstance(identity, Mapping), "a V3 row must carry its scientific identity")
    team_size = identity.get("team_size")
    _require(isinstance(team_size, int) and not isinstance(team_size, bool)
             and team_size > 0, "team_size must be a positive integer")
    return RuntimeConfig.for_team_size(int(team_size))


def rehydrate_row(row: Mapping[str, Any],
                  runtime_config: Optional[RuntimeConfig] = None,
                  ) -> RobotLocalEgoGraph:
    """Load one published row into a graph and prove it is the sealed graph.

    ``runtime_config`` defaults to the one the row's own team size implies. The
    strict loader then compares its hash against the payload's declared
    ``runtime_config_sha256``, so a wrong configuration is a loud refusal rather
    than a quiet reinterpretation.
    """
    if runtime_config is None:
        runtime_config = runtime_config_for_row(row)
    serialized = rehydrate_row_payload(row)
    try:
        graph = load_robot_local_ego_graph(serialized, runtime_config)
    except Exception as exc:                                # noqa: BLE001
        raise V3RehydrationError(f"strict graph loader refused the row: {exc}") from exc

    identity = row["scientific_identity"]
    stripped, separated_candidate = recoverability_ego_payload(graph)
    if int(separated_candidate) != int(identity["candidate_topology_id"]):
        raise V3FingerprintMismatch(
            "the reconstructed candidate topology disagrees with the row identity")
    fingerprint = recoverability_graph_fingerprint(stripped)
    if fingerprint != str(identity["graph_fingerprint"]):
        raise V3FingerprintMismatch(
            "reconstructed graph fingerprint "
            f"{fingerprint[:16]}... does not equal the sealed "
            f"{str(identity['graph_fingerprint'])[:16]}...")
    if int(graph.observer_robot_id) != int(identity["robot_id"]):
        raise V3FingerprintMismatch(
            "the reconstructed observer disagrees with the row identity")
    _require_candidate_binding(graph, int(identity["candidate_topology_id"]))
    _require_row_identity_binding(row)
    return graph


def _require_candidate_binding(graph: RobotLocalEgoGraph, candidate: int) -> None:
    """Prove the TENSORS were built for the declared candidate.

    The graph fingerprint deliberately excludes ``candidate_topology_id`` -- the
    row identity carries it instead -- so the fingerprint alone cannot detect a
    swapped candidate. The tensors can: the ego graph is rebuilt per candidate,
    so the root's ``candidate_topology_onehot`` records which candidate the
    features were generated for. Checking it closes the gap the fingerprint
    leaves open, and it is not circular, because that one-hot comes from the
    published node features rather than from the metadata we reinserted.
    """
    block = NODE_FEATURE_SLICES["candidate_topology_onehot"]
    row_index = int(graph.root_index)
    values = graph.node_x[row_index, block]
    expected = [1.0 if topology == candidate else 0.0
                for topology in PRIMARY_TOPOLOGY_IDS]
    observed = [float(value) for value in values]
    if observed != expected:
        raise V3FingerprintMismatch(
            "the published node features were generated for a different candidate "
            f"topology than the row identity declares ({candidate})")


def _require_row_identity_binding(row: Mapping[str, Any]) -> None:
    """The scientific row id must recompute from the sixteen identity fields."""
    identity = row["scientific_identity"]
    try:
        recomputed = recoverability_scientific_row_id_v3(identity)
    except Exception as exc:                                # noqa: BLE001
        raise V3RehydrationError(f"row identity is not admissible: {exc}") from exc
    if recomputed != str(row["scientific_row_id"]):
        raise V3FingerprintMismatch(
            "the scientific row id does not recompute from its identity fields")


def rehydrate_candidate_group(group: Any,
                              runtime_config: Optional[RuntimeConfig] = None):
    """Every robot row of one candidate, in the published row order."""
    return tuple(rehydrate_row(row, runtime_config) for row in group.rows)
