"""Immutable publication scope layered over the generic transition protocol.

The protocol wire format deliberately remains able to represent every registry
topology. This module owns the narrower scientific publication contract and is
the only admission point for primary online transition requests.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Dict, Optional, Tuple

from ..topology_registry import (
    COMPACT,
    KEEP,
    LINE,
    PRIMARY_TOPOLOGY_IDS,
    TOPOLOGY_REGISTRY_SCHEMA_VERSION,
)
from .transition_messages import (
    TRANSITION_PROTOCOL_SCHEMA_VERSION,
    TransitionIntent,
)
from .transition_protocol import TransitionProtocolNode


ONLINE_TOPOLOGY_SCOPE_SCHEMA_VERSION = "rvt-online-topology-scope/v1"
ONLINE_TOPOLOGY_SCOPE_VERSION = "compact-line-publication-v1"
PHASE7R_SOURCE_COMMIT = "f74ba7d63e684be4213a89ca31d0214a48543b64"

ADMITTED = "ADMITTED"
UNSUPPORTED_TRANSITION = "UNSUPPORTED_TRANSITION"
NO_TRANSITION_REQUIRED = "NO_TRANSITION_REQUIRED"
UNKNOWN_TOPOLOGY = "UNKNOWN_TOPOLOGY"
HISTORICAL_REPLAY_ONLY = "HISTORICAL_REPLAY_ONLY"
UNSUPPORTED_INITIAL_TOPOLOGY = "UNSUPPORTED_INITIAL_TOPOLOGY"


@dataclass(frozen=True)
class OnlineTopologyScope:
    schema_version: str
    scope_version: str
    active_topology_ids: Tuple[int, ...]
    active_transition_pairs: Tuple[Tuple[int, int], ...]
    fixed_only_topology_ids: Tuple[int, ...]
    unsupported_transition_pairs: Tuple[Tuple[int, int], ...]
    qualified_team_sizes: Tuple[int, ...]
    primary_initial_topology_id: int


# The publication candidate order and graph are explicit. Registry ordering is
# intentionally not consulted when constructing either tuple.
ONLINE_TOPOLOGY_SCOPE = OnlineTopologyScope(
    schema_version=ONLINE_TOPOLOGY_SCOPE_SCHEMA_VERSION,
    scope_version=ONLINE_TOPOLOGY_SCOPE_VERSION,
    active_topology_ids=(COMPACT, LINE),
    active_transition_pairs=((COMPACT, LINE), (LINE, COMPACT)),
    fixed_only_topology_ids=(KEEP,),
    unsupported_transition_pairs=(
        (KEEP, COMPACT),
        (COMPACT, KEEP),
        (KEEP, LINE),
        (LINE, KEEP),
    ),
    qualified_team_sizes=(5, 6, 8, 12, 16, 24),
    primary_initial_topology_id=COMPACT,
)


@dataclass(frozen=True)
class OnlineTransitionDecision:
    schema_version: str
    status: str
    source_topology: int
    target_topology: int
    admitted: bool
    creates_lifecycle: bool
    historical_replay_allowed: bool
    reason: str


@dataclass(frozen=True)
class PublicationTransitionRequestResult:
    decision: OnlineTransitionDecision
    intent: Optional[TransitionIntent]


@dataclass(frozen=True)
class InitialTopologyDecision:
    schema_version: str
    status: str
    requested_topology: int
    selected_topology: Optional[int]
    admitted: bool
    fixed_baseline_only: bool
    reason: str


def _transition_decision(
    status: str,
    source_topology: int,
    target_topology: int,
    admitted: bool,
    creates_lifecycle: bool,
    historical_replay_allowed: bool,
    reason: str,
) -> OnlineTransitionDecision:
    return OnlineTransitionDecision(
        ONLINE_TOPOLOGY_SCOPE_SCHEMA_VERSION,
        status,
        source_topology,
        target_topology,
        admitted,
        creates_lifecycle,
        historical_replay_allowed,
        reason,
    )


def evaluate_publication_transition(
    source_topology: int,
    target_topology: int,
) -> OnlineTransitionDecision:
    """Admit exactly the frozen COMPACT/LINE directed graph."""
    if (
        isinstance(source_topology, bool)
        or isinstance(target_topology, bool)
        or source_topology not in PRIMARY_TOPOLOGY_IDS
        or target_topology not in PRIMARY_TOPOLOGY_IDS
    ):
        return _transition_decision(
            UNKNOWN_TOPOLOGY,
            source_topology,
            target_topology,
            False,
            False,
            False,
            "source or target is absent from the immutable topology registry",
        )
    if source_topology == target_topology:
        return _transition_decision(
            NO_TRANSITION_REQUIRED,
            source_topology,
            target_topology,
            False,
            False,
            False,
            "source and target are equal; no lifecycle is created",
        )
    if (source_topology, target_topology) in ONLINE_TOPOLOGY_SCOPE.active_transition_pairs:
        return _transition_decision(
            ADMITTED,
            source_topology,
            target_topology,
            True,
            True,
            True,
            "transition is an edge in the frozen publication graph",
        )
    return _transition_decision(
        UNSUPPORTED_TRANSITION,
        source_topology,
        target_topology,
        False,
        False,
        True,
        "transition is excluded from publication runtime and retained for replay only",
    )


def evaluate_historical_transition(
    source_topology: int,
    target_topology: int,
) -> OnlineTransitionDecision:
    """Classify a generic protocol record without authorizing online use."""
    publication = evaluate_publication_transition(source_topology, target_topology)
    if publication.status == UNKNOWN_TOPOLOGY:
        return publication
    if publication.status == NO_TRANSITION_REQUIRED:
        return publication
    return _transition_decision(
        HISTORICAL_REPLAY_ONLY,
        source_topology,
        target_topology,
        False,
        False,
        True,
        "known generic-protocol record is readable but grants no publication authority",
    )


def request_publication_transition(
    node: TransitionProtocolNode,
    lifecycle_id: int,
    target_topology: int,
    event_type: str,
    timestamp_seconds: float,
) -> PublicationTransitionRequestResult:
    """Filter a local node request before the generic protocol sees it."""
    decision = evaluate_publication_transition(
        node.committed_topology,
        target_topology,
    )
    if not decision.admitted:
        return PublicationTransitionRequestResult(decision, None)
    intent = node.request_intent(
        lifecycle_id,
        target_topology,
        event_type,
        timestamp_seconds,
    )
    if intent is None:
        raise RuntimeError("admitted publication edge failed to create an intent")
    return PublicationTransitionRequestResult(decision, intent)


def evaluate_primary_initial_topology(
    requested_topology: Optional[int] = None,
    *,
    narrow_start_declared: bool = False,
    physically_valid: bool = False,
) -> InitialTopologyDecision:
    """Apply the frozen primary-runtime initialization contract."""
    requested = COMPACT if requested_topology is None else requested_topology
    if isinstance(requested, bool) or requested not in PRIMARY_TOPOLOGY_IDS:
        return InitialTopologyDecision(
            ONLINE_TOPOLOGY_SCOPE_SCHEMA_VERSION,
            UNKNOWN_TOPOLOGY,
            requested,
            None,
            False,
            False,
            "requested initial topology is absent from the immutable registry",
        )
    if requested == COMPACT:
        return InitialTopologyDecision(
            ONLINE_TOPOLOGY_SCOPE_SCHEMA_VERSION,
            ADMITTED,
            requested,
            COMPACT,
            True,
            False,
            "COMPACT is the default primary-runtime initial topology",
        )
    if requested == LINE and narrow_start_declared and physically_valid:
        return InitialTopologyDecision(
            ONLINE_TOPOLOGY_SCOPE_SCHEMA_VERSION,
            ADMITTED,
            requested,
            LINE,
            True,
            False,
            "LINE is admitted for an explicitly declared physically valid narrow start",
        )
    if requested == KEEP:
        return InitialTopologyDecision(
            ONLINE_TOPOLOGY_SCOPE_SCHEMA_VERSION,
            UNSUPPORTED_INITIAL_TOPOLOGY,
            requested,
            None,
            False,
            True,
            "KEEP is available only through the fixed-topology baseline runtime",
        )
    return InitialTopologyDecision(
        ONLINE_TOPOLOGY_SCOPE_SCHEMA_VERSION,
        UNSUPPORTED_INITIAL_TOPOLOGY,
        requested,
        None,
        False,
        False,
        "LINE requires a declared narrow start and physical-validity check",
    )


def _canonical_json_bytes(document: object) -> bytes:
    return json.dumps(
        document,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")


def canonical_scope_sha256(document: object) -> str:
    """Hash a scope document after excluding its self-referential digest."""
    if not isinstance(document, dict):
        raise TypeError("scope document must be a dictionary")
    payload = dict(document)
    payload.pop("scope_sha256", None)
    return hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()


def build_online_topology_scope_manifest() -> Dict[str, object]:
    scope = ONLINE_TOPOLOGY_SCOPE
    document: Dict[str, object] = {
        "schema_version": scope.schema_version,
        "scope_version": scope.scope_version,
        "source_commit": PHASE7R_SOURCE_COMMIT,
        "topology_registry_schema_version": TOPOLOGY_REGISTRY_SCHEMA_VERSION,
        "transition_protocol_schema_version": TRANSITION_PROTOCOL_SCHEMA_VERSION,
        "active_candidate_topology_ids": list(scope.active_topology_ids),
        "active_online_topology_ids": list(scope.active_topology_ids),
        "active_directed_transition_pairs": [
            list(pair) for pair in scope.active_transition_pairs
        ],
        "fixed_only_topology_ids": list(scope.fixed_only_topology_ids),
        "mechanically_supported_team_sizes": list(scope.qualified_team_sizes),
        "experimentally_qualified_team_sizes": list(scope.qualified_team_sizes),
        "unsupported_online_transitions": [
            list(pair) for pair in scope.unsupported_transition_pairs
        ],
        "primary_initial_topology_id": scope.primary_initial_topology_id,
        "reason_for_scope_reduction": (
            "Phase 7R qualified both COMPACT/LINE directions for every declared "
            "team size, while KEEP-edge transitions remained unreliable under the "
            "frozen controller and safety contract."
        ),
        "final_test_access_status": {
            "accessed": False,
            "access_count": 0,
        },
        "method_repair_cycle_count": 1,
        "single_graph_for_all_team_sizes": True,
        "historical_replay_compatibility": {
            "generic_protocol_vocabulary_preserved": list(PRIMARY_TOPOLOGY_IDS),
            "keep_transition_records_readable": True,
            "publication_authority_granted": False,
        },
        "preserved_result_roots": [
            {
                "path": "results/phase7_transition_protocol/",
                "source_git_tree": "93ac2641442b3113d75939b477f1d7a400afa8a8",
            },
            {
                "path": "results/phase7_transition_execution_repair/",
                "source_git_tree": "511a0027e873555884519efd8be867b855490b2d",
            },
        ],
    }
    document["scope_sha256"] = canonical_scope_sha256(document)
    return document


def serialize_online_topology_scope_manifest() -> str:
    return json.dumps(
        build_online_topology_scope_manifest(),
        allow_nan=False,
        ensure_ascii=True,
        indent=2,
        sort_keys=True,
    ) + "\n"


def scope_as_dict() -> Dict[str, object]:
    """Return a copy suitable for diagnostics without exposing mutable state."""
    return asdict(ONLINE_TOPOLOGY_SCOPE)
