"""Deterministic SYNTHETIC V3 fixtures for mechanical qualification.

These exist so the training driver can be exercised end to end -- publication
format, rehydration, loader grouping, batching, loss, optimizer, checkpoint --
without touching official data. Everything produced here is synthetic by
construction: the layouts, episodes, seeds and supervision are fabricated from a
fixed integer seed, and the emitted directory carries no ``ops/authority.json``
and no ``seal/``, so :func:`authorization.classify_dataset_root` classifies it
SYNTHETIC and mechanical mode accepts it.

The fixtures deliberately span the axes the frozen protocol cares about: team
sizes 5 and 16, replica counts 1 and 3, both candidates, several source episodes
across several synthetic layouts, soft supervision (k = 1 and k = 2 at R = 3) and
deterministic supervision (k = 0 and k = 1 at R = 1).

This module never fabricates official identity. It cannot: no synthetic layout
hash can collide with a frozen registry layout, and nothing here writes into an
official tree.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence, Tuple

from ..decentralized.ego_graph_v2 import (
    RobotLocalTopologyMetadata, build_robot_local_ego_graph,
    prepare_robot_local_topology_metadata,
)
from ..decentralized.system_model import NeighbourRecord, RobotView
from ..phase9g0r.contracts import (
    recoverability_ego_payload, recoverability_graph_fingerprint,
)
from ..phase9g0r.contracts_v3 import (
    CANDIDATE_PAIR_TRANSACTION_V3_SCHEMA_VERSION, INVALIDITY_CONTRACT_V3_SHA256,
    RECOVERABILITY_PROTOCOL_V3, build_recoverability_row_key_v3,
    recoverability_scientific_row_id_v3,
)
from ..runtime_configuration import RuntimeConfig
from ..topology_registry import (
    COMPACT, LINE, construct_primary_templates, generate_persistent_roles,
)

SYNTHETIC_SPLIT = "synthetic_mechanical"
SYNTHETIC_STUDY = "study_synthetic_mechanical"
V3_ROW_SCHEMA_VERSION = "rvt-recoverability-v3-supervision-row/v1"


def synthetic_digest(label: str) -> str:
    """A stable 64-hex label. Namespaced so it can never look official."""
    return hashlib.sha256(f"rvt-openloop-v3-synthetic::{label}".encode("ascii")).hexdigest()


def _rotate(vector: Tuple[float, float], direction: Tuple[float, float]):
    norm = math.hypot(*direction) or 1.0
    cos, sin = direction[0] / norm, direction[1] / norm
    return (vector[0] * cos - vector[1] * sin, vector[0] * sin + vector[1] * cos)


def synthetic_graph(*, team_size: int, robot: int, candidate: int, step: int,
                    jitter: float, peers: int = 3, obstacles: int = 2):
    """One robot-local ego graph, built through the frozen builder."""
    config = RuntimeConfig.for_team_size(team_size)
    keys = tuple(range(team_size))
    roles = generate_persistent_roles(keys)
    templates = {item.topology_id: item
                 for item in construct_primary_templates(config.formation, role_set=roles)}
    local: RobotLocalTopologyMetadata = prepare_robot_local_topology_metadata(
        roles, robot, config.formation)
    mission = (1.0, 0.0)
    compact_template = templates[COMPACT]
    line_template = templates[LINE]
    neighbours: List[NeighbourRecord] = []
    for index in range(min(peers, team_size - 1)):
        peer = (robot + index + 1) % team_size
        peer_role = roles.role_for_robot(peer)
        angle = 2.0 * math.pi * index / max(peers, 1) + jitter
        neighbours.append(NeighbourRecord(
            robot_id=peer,
            rel_position=_rotate((1.0 + 0.2 * math.cos(angle),
                                  0.7 * math.sin(angle)), mission),
            rel_velocity=_rotate((0.02 * (index + 1), -0.01 * index), mission),
            role_keep=compact_template.offset(peer_role.role_id),
            role_line=line_template.offset(peer_role.role_id),
            committed_mode=COMPACT, epoch_id=3,
            message_age_steps=index % 2, degree=2, link_valid=True))
    tokens = tuple(
        (_rotate((1.5 + 0.4 * index + jitter, -0.6 + 0.3 * index), mission) + (0.25,))
        for index in range(obstacles))
    view = RobotView(
        robot_id=robot,
        position=(0.4 * robot + jitter, -0.2 * robot),
        velocity=(0.15, -0.05),
        role_keep=compact_template.offset(roles.role_for_robot(robot).role_id),
        role_line=line_template.offset(roles.role_for_robot(robot).role_id),
        committed_mode=COMPACT, epoch_id=3, steps_since_decision=step % 11,
        local_progress=0.35 + 0.01 * robot, goal=(9.0, 0.4), mission_dir=mission,
        neighbours=tuple(neighbours), obstacles=tokens)
    return build_robot_local_ego_graph(view, config, local, candidate, step)


def _rows(*, family: str, layout_sha256: str, team_size: int, episode_id: str,
          step: int, candidate: int, jitter: float) -> List[Mapping[str, Any]]:
    rows = []
    for robot in range(team_size):
        graph = synthetic_graph(team_size=team_size, robot=robot,
                                candidate=candidate, step=step, jitter=jitter)
        payload, separated = recoverability_ego_payload(graph)
        assert separated == candidate
        key = build_recoverability_row_key_v3(
            study=SYNTHETIC_STUDY, split=SYNTHETIC_SPLIT, family=family,
            layout_sha256=layout_sha256, team_size=team_size,
            episode_id=episode_id, realized_source_timestep=step, robot_id=robot,
            candidate_topology_id=candidate,
            graph_fingerprint=recoverability_graph_fingerprint(payload))
        rows.append({
            "schema_version": V3_ROW_SCHEMA_VERSION,
            "protocol_version": RECOVERABILITY_PROTOCOL_V3,
            "scientific_row_id": recoverability_scientific_row_id_v3(key),
            "scientific_identity": key,
            "graph_payload_schema_version":
                "rvt-recoverability-ego-payload-binding/v1",
            "graph_payload": payload,
        })
    return rows


def synthetic_transaction(*, family: str, layout_label: str, team_size: int,
                          episode_index: int, step: int,
                          compact_k: int, compact_r: int,
                          line_k: int, line_r: int) -> Mapping[str, Any]:
    """One complete, labelable V3 pair transaction in publication format."""
    layout_sha256 = synthetic_digest(f"layout::{layout_label}")
    episode_id = f"synthetic-{layout_label}-n{team_size}-e{episode_index:03d}"
    event_id = f"{episode_id}-t{step:04d}"
    jitter = 0.05 * ((episode_index * 7 + step * 3) % 11)
    rows = (_rows(family=family, layout_sha256=layout_sha256, team_size=team_size,
                  episode_id=episode_id, step=step, candidate=COMPACT, jitter=jitter)
            + _rows(family=family, layout_sha256=layout_sha256, team_size=team_size,
                    episode_id=episode_id, step=step, candidate=LINE, jitter=jitter))
    supervision = {}
    labelability = {}
    for candidate, successes, replicas in ((COMPACT, compact_k, compact_r),
                                           (LINE, line_k, line_r)):
        supervision[str(candidate)] = {
            "decision_event_id": event_id,
            "candidate_topology_id": int(candidate),
            "k": int(successes), "R": int(replicas),
        }
        labelability[str(candidate)] = {
            "decision_event_id": event_id,
            "candidate_topology_id": int(candidate),
            "R_required": int(replicas),
            "executed_required_replicas": int(replicas),
            "candidate_scientifically_labelable": True,
            "k": int(successes), "R": int(replicas),
        }
    return {
        "schema_version": CANDIDATE_PAIR_TRANSACTION_V3_SCHEMA_VERSION,
        "protocol_version": RECOVERABILITY_PROTOCOL_V3,
        "decision_event_id": event_id,
        "status": "SCIENTIFICALLY_RECONCILED_LABELABLE",
        "scientifically_reconciled": True,
        "training_rows_committable": True,
        "expected_row_count": 2 * team_size,
        "actual_row_count": 2 * team_size,
        "labelability": labelability,
        "supervision": supervision,
        "rows": rows,
        "audit_dispositions": [],
        "recoverability_v3_required_replica_invalidity_contract_v1_sha256":
            INVALIDITY_CONTRACT_V3_SHA256,
        "episode_id": episode_id,
        "family": family,
    }


#: One layout per fold-half, spanning the axes the protocol distinguishes.
SYNTHETIC_PLAN: Tuple[Mapping[str, Any], ...] = (
    {"layout_label": "alpha", "family": "F1", "team_size": 5, "episodes": 2,
     "steps": (0, 4), "supervision": ((1, 1), (0, 1))},
    {"layout_label": "beta", "family": "F9", "team_size": 5, "episodes": 2,
     "steps": (1, 5), "supervision": ((1, 3), (2, 3))},
    {"layout_label": "gamma", "family": "F8", "team_size": 16, "episodes": 1,
     "steps": (2,), "supervision": ((2, 3), (1, 3))},
    {"layout_label": "delta", "family": "F2", "team_size": 16, "episodes": 1,
     "steps": (3,), "supervision": ((0, 1), (1, 1))},
)


def synthetic_transactions() -> Tuple[Mapping[str, Any], ...]:
    out = []
    for entry in SYNTHETIC_PLAN:
        (compact_k, compact_r), (line_k, line_r) = entry["supervision"]
        for episode_index in range(int(entry["episodes"])):
            for step in entry["steps"]:
                out.append(synthetic_transaction(
                    family=str(entry["family"]),
                    layout_label=str(entry["layout_label"]),
                    team_size=int(entry["team_size"]),
                    episode_index=episode_index, step=int(step),
                    compact_k=compact_k, compact_r=compact_r,
                    line_k=line_k, line_r=line_r))
    return tuple(out)


def write_synthetic_namespace(root: Path) -> Path:
    """Write the fixtures in publication layout. No ops/, no seal/, no authority."""
    namespace = Path(root) / "synthetic_v3" / "transactions"
    namespace.mkdir(parents=True, exist_ok=True)
    for transaction in synthetic_transactions():
        key = hashlib.sha256(
            json.dumps({"decision_event_id": transaction["decision_event_id"]},
                       sort_keys=True, separators=(",", ":"),
                       ensure_ascii=True).encode("ascii")).hexdigest()
        (namespace / f"event-{key}.json").write_text(
            json.dumps(transaction, indent=1, sort_keys=True) + "\n", encoding="ascii")
    return namespace


def synthetic_fold_manifest() -> Mapping[str, Any]:
    """A synthetic two-fold manifest with the same structure as the frozen one.

    The four layouts the fixtures actually use are placed deliberately: alpha and
    delta in fold A, beta and gamma in fold B, so a fold split of the synthetic
    events is non-trivial. The remaining families are filled with layouts no
    fixture uses, which keeps the one-layout-per-family shape without inventing
    events for them.
    """
    families = ("F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10")
    placed = {
        "A": {"F1": "alpha", "F2": "delta"},
        "B": {"F9": "beta", "F8": "gamma"},
    }
    folds = {}
    for name, offset in (("A", 0.22), ("B", 0.54)):
        entries = []
        for family in families:
            label = placed[name].get(family, f"filler-{name}-{family}")
            entries.append({
                "family": family,
                "layout_id": f"synthetic-{label}",
                "layout_sha256": synthetic_digest(f"layout::{label}"),
                "geometry_sha256": synthetic_digest(f"geometry::{label}"),
                "offset": offset,
            })
        folds[name] = {"registry_offset": offset, "layouts": len(entries),
                       "entries": entries}
    return {
        "schema_version": "rvt-open-loop-v3-train-internal-fold-manifest/v1",
        "folds": folds,
        "assertions": {"geometry_disjoint": True, "geometry_overlap": 0,
                       "row_event_candidate_or_episode_can_cross_a_fold": False},
        "open_loop_v3_train_internal_fold_manifest_v1_sha256":
            synthetic_digest("fold-manifest"),
    }
