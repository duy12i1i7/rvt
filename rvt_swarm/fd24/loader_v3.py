"""V3 supervised loader -- the decision event is the scientific unit.

Robot rows are not independent training examples. One decision event carries
two candidates, each with N robot-local graphs and one shared ``(k, R)``
observation, and the frozen loss gives that whole event weight 1. The loader
therefore refuses to hand out anything smaller: no lone candidate, no partial
robot set, no row without its group.

Non-labelable pairs are simply absent. There is nothing to mask, because no
supervised row was ever written for them; their evidence lives in the audit
ledger where the S8 accounting reads it.

This module loads and groups. It does not train.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

from ..phase8.common import sha256_document
from ..phase9g0r.contracts_v3 import (
    CANDIDATE_PAIR_TRANSACTION_V3_SCHEMA_VERSION, INVALIDITY_CONTRACT_V3_SHA256,
    RECOVERABILITY_PROTOCOL_V3,
)
from ..topology_registry import COMPACT, LINE

V3_ROW_SCHEMA_VERSION = "rvt-recoverability-v3-supervision-row/v1"
V2_ROW_SCHEMA_VERSIONS = frozenset({
    "rvt-recoverability-v2-supervision-row/v1",
    "rvt-recoverability-supervision-row/v1",
})

TRAINING_IS_NOT_AUTHORIZED_HERE = True


class V3LoaderError(ValueError):
    """A loader contract violation that must fail closed."""


@dataclass(frozen=True)
class V3CandidateGroup:
    """One candidate of one decision event: N robot rows and one (k, R)."""

    decision_event_id: str
    candidate_topology_id: int
    k: int
    R: int                                                     # noqa: N815
    rows: Tuple[Mapping[str, Any], ...]

    @property
    def team_size(self) -> int:
        return len(self.rows)

    @property
    def observed_fraction(self) -> float:
        """Descriptive only. The loss consumes (k, R), not this."""
        return float(self.k) / float(self.R)


@dataclass(frozen=True)
class V3EventGroup:
    """One complete decision event. Both candidates, or it does not exist."""

    decision_event_id: str
    split: str
    team_size: int
    compact: V3CandidateGroup
    line: V3CandidateGroup

    def candidates(self) -> Mapping[int, V3CandidateGroup]:
        return {COMPACT: self.compact, LINE: self.line}

    @property
    def row_count(self) -> int:
        return len(self.compact.rows) + len(self.line.rows)


def _candidate_group(transaction: Mapping[str, Any], candidate: int,
                     ) -> V3CandidateGroup:
    key = str(int(candidate))
    supervision = transaction["supervision"].get(key)
    if supervision is None:
        raise V3LoaderError(
            "a published V3 event must carry supervision for both candidates")
    rows = tuple(
        row for row in transaction["rows"]
        if int(row["scientific_identity"]["candidate_topology_id"]) == int(candidate))
    if not rows:
        raise V3LoaderError("a published V3 candidate must carry robot rows")
    for row in rows:
        schema = str(row["schema_version"])
        if schema in V2_ROW_SCHEMA_VERSIONS:
            raise V3LoaderError("a V2-schema row may not enter the V3 loader")
        if schema != V3_ROW_SCHEMA_VERSION:
            raise V3LoaderError(f"unknown supervised row schema {schema!r}")
    return V3CandidateGroup(
        decision_event_id=str(transaction["decision_event_id"]),
        candidate_topology_id=int(candidate),
        k=int(supervision["k"]), R=int(supervision["R"]), rows=rows)


def event_group_from_transaction(transaction: Mapping[str, Any],
                                 *, split: str) -> V3EventGroup:
    """Build one event group, refusing anything partial."""
    if transaction["schema_version"] != CANDIDATE_PAIR_TRANSACTION_V3_SCHEMA_VERSION:
        raise V3LoaderError("the V3 loader requires a V3 pair transaction")
    if transaction["protocol_version"] != RECOVERABILITY_PROTOCOL_V3:
        raise V3LoaderError("the V3 loader requires RECOVERABILITY_V3")
    if transaction[
            "recoverability_v3_required_replica_invalidity_contract_v1_sha256"
    ] != INVALIDITY_CONTRACT_V3_SHA256:
        raise V3LoaderError(
            "a V3 transaction must bind the frozen invalidity contract")
    if not transaction["training_rows_committable"]:
        raise V3LoaderError(
            "a non-labelable V3 pair is absent from loader membership; it is "
            "never a masked training row")
    compact = _candidate_group(transaction, COMPACT)
    line = _candidate_group(transaction, LINE)
    if compact.team_size != line.team_size:
        raise V3LoaderError("a V3 event must carry N rows per candidate")
    expected = int(transaction["expected_row_count"])
    if compact.team_size + line.team_size != expected:
        raise V3LoaderError("a V3 event must publish exactly 2 * N rows")
    for row in tuple(compact.rows) + tuple(line.rows):
        if str(row["scientific_identity"]["split"]) != split:
            raise V3LoaderError(
                f"row from split {row['scientific_identity']['split']!r} entered "
                f"the {split!r} loader")
    return V3EventGroup(
        decision_event_id=compact.decision_event_id, split=split,
        team_size=compact.team_size, compact=compact, line=line)


def load_v3_event_groups(
    transactions: Iterable[Mapping[str, Any]], *, split: str,
) -> Tuple[V3EventGroup, ...]:
    """Group a split into complete decision events, in canonical order."""
    groups: Dict[str, V3EventGroup] = {}
    for transaction in transactions:
        group = event_group_from_transaction(transaction, split=split)
        if group.decision_event_id in groups:
            raise V3LoaderError("duplicate V3 decision event in one split")
        groups[group.decision_event_id] = group
    return tuple(groups[key] for key in sorted(groups))


def load_v3_event_groups_from_namespace(
    namespace: Path, *, split: str,
) -> Tuple[V3EventGroup, ...]:
    """Read every written transaction under one V3 writer namespace."""
    directory = Path(namespace) / "transactions"
    if not directory.exists():
        return ()
    documents = [json.loads(path.read_text(encoding="ascii"))
                 for path in sorted(directory.glob("event-*.json"))]
    return load_v3_event_groups(documents, split=split)


def scientific_membership(groups: Sequence[V3EventGroup]) -> Mapping[str, Any]:
    """The order-independent membership fingerprint.

    Two loader configurations may hand events out in different orders; they may
    not disagree about which events exist, which candidates each has, or which
    rows belong to each candidate.
    """
    payload = sorted(
        (
            {
                "decision_event_id": group.decision_event_id,
                "team_size": group.team_size,
                "candidates": {
                    str(COMPACT): {
                        "k": group.compact.k, "R": group.compact.R,
                        "row_ids": sorted(str(row["scientific_row_id"])
                                          for row in group.compact.rows)},
                    str(LINE): {
                        "k": group.line.k, "R": group.line.R,
                        "row_ids": sorted(str(row["scientific_row_id"])
                                          for row in group.line.rows)},
                },
            }
            for group in groups
        ),
        key=lambda item: item["decision_event_id"])
    return {
        "events": len(payload),
        "rows": sum(group.row_count for group in groups),
        "membership_sha256": sha256_document(payload),
    }


def deterministic_event_order(
    groups: Sequence[V3EventGroup], *, seed: int,
) -> Tuple[V3EventGroup, ...]:
    """A frozen shuffle: reproducible from the seed, independent of workers.

    Ordering is derived by sorting on a counter-free canonical digest of
    ``(seed, decision_event_id)``, so it cannot depend on hash randomization,
    worker count or filesystem order.
    """
    keyed = sorted(
        ((sha256_document({"seed": int(seed),
                           "decision_event_id": group.decision_event_id}),
          group.decision_event_id, index)
         for index, group in enumerate(groups)),
        key=lambda item: (item[0], item[1]))
    return tuple(groups[index] for _, _, index in keyed)


def batch_event_groups(
    groups: Sequence[V3EventGroup], *, events_per_batch: int,
) -> Tuple[Tuple[V3EventGroup, ...], ...]:
    """Batch by decision event, never by row."""
    if events_per_batch < 1:
        raise V3LoaderError("a V3 batch must contain at least one decision event")
    batches: List[Tuple[V3EventGroup, ...]] = []
    for start in range(0, len(groups), events_per_batch):
        batches.append(tuple(groups[start:start + events_per_batch]))
    return tuple(batches)
