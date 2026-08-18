"""Recoverability V3 task compilation -- probabilistic supervision, fixed R.

Additive. Stage A is not reimplemented: V3 reuses the frozen V2 acquisition
(``REALIZED_TRAJECTORY_UNIFORM_K``, K = 5) verbatim, because acquisition is
candidate-blind and target-independent and the owner froze it unchanged. What
V3 adds is a different *manifest* authority, a registry that must fail closed
on the superseded 10-layout TRAIN version, and V3-tagged candidate tasks.

Split authority is the sharp edge here. V3 TRAIN legitimately contains the
layout ``validation-f1-01`` (offset 0.54) next to ``train-f1-02`` (offset
0.22). Any code that reads a split out of a layout id would classify the first
as VALIDATION and be wrong. Split comes from the manifest's ``v3_split`` and
from registry membership, never from a string.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

from ..phase8.common import verify_canonical_hash
from ..phase9b.identity import derive_generation_seed
from ..phase9c_rb.counterfactual import replica_count_for_family
from ..phase9d_h1r.acquisition_v2 import (
    DEFAULT_K, REALIZED_TRAJECTORY_UNIFORM_K,
)
from ..topology_registry import COMPACT, LINE
from .compiler import OfficialDecisionEventTask, OfficialSourceTask
from .compiler_v2 import (
    V2SourceAcquisition, execute_v2_source_acquisition,
)
from .contracts_v3 import (
    INVALIDITY_CONTRACT_V3_SHA256, LAYOUT_SPLIT_REGISTRY_V2_SHA256,
    PROBABILISTIC_TARGET_V3_SHA256, RECOVERABILITY_PROTOCOL_V3,
    REPLICA_PROTOCOL_V3_SHA256, ROW_BINDING_V3_SPEC_SHA256,
    SOURCE_ACQUISITION_PROTOCOL_SHA256,
    SUPERSEDED_LAYOUT_SPLIT_REGISTRY_V1_SHA256, TARGET_V4_CONTRACT_SHA256,
    V3ContractError, verify_frozen_v3_contracts,
)

V3_TRAIN = "v3_train"
V3_VALIDATION = "v3_validation"
V3_SPLITS: Tuple[str, ...] = (V3_TRAIN, V3_VALIDATION)

_REGISTRY_ARTIFACT = "results/rvt_fd24/phase9d_v3f_l_layout_split_registry_v2.json"
_MANIFEST_ARTIFACTS: Mapping[str, Tuple[str, str, str]] = {
    V3_TRAIN: (
        "results/rvt_fd24/phase9d_v3f_l_train_manifest_dry_final_v1.json",
        "official_v3_train_manifest_dry_final_sha256",
        "phase9d_v3f_l_train_manifest_dry_final_sha256"),
    V3_VALIDATION: (
        "results/rvt_fd24/phase9d_v3f_l_validation_manifest_dry_final_v1.json",
        "official_v3_validation_manifest_dry_final_sha256",
        "phase9d_v3f_l_validation_manifest_dry_final_sha256"),
}

#: Inner manifest roots, distinct from the outer artifact hashes above. The
#: Phase 9G-V3I-Q stop found these two conflated; both are pinned separately.
FROZEN_V3_MANIFEST_ROOTS: Mapping[str, str] = {
    V3_TRAIN: "6390cd31570d3dc12040d3522ca77db915171b82a2724db02825a32e90bd6edd",
    V3_VALIDATION: "431e42ee832c808a6bb9747ee23940d4bb7d18d9b7a5f55bc43fcaa7f4a648f2",
}
FROZEN_V3_MANIFEST_ARTIFACT_HASHES: Mapping[str, str] = {
    V3_TRAIN: "ffb1fe3363908369096f4fd8463fe3a8cd5434cb0a4d48d5a39382df7ced4898",
    V3_VALIDATION: "72f88a6269358063047bf43edfb304f23e3a26d62bacdb2be07a01cc9c836076",
}

#: The frozen prospective shape. These are assertions about authority, not
#: parameters: a manifest that disagrees is refused rather than adapted to.
FROZEN_V3_SHAPE: Mapping[str, Mapping[str, Any]] = {
    V3_TRAIN: {
        "source_episodes": 1200, "layout_count": 20,
        "episodes_per_layout": 60, "layout_offsets": (0.22, 0.54),
        "registry_group": "TRAIN",
    },
    V3_VALIDATION: {
        "source_episodes": 300, "layout_count": 10,
        "episodes_per_layout": 30, "layout_offsets": (0.65,),
        "registry_group": "VALIDATION",
    },
}

#: Offset 0.33 is UNUSED_RESERVE and 0.76/0.87 are forbidden; neither may reach
#: an official V3 split.
RESERVE_OFFSET = 0.33
FORBIDDEN_OFFSETS: Tuple[float, ...] = (0.76, 0.87)

SEALED_STUDIES = ("study_a_n24_evaluation", "study_b_with_n24", "final_test")
SEALED_SPLITS = ("n24_evaluation", "final_test", "test")


class V3CompilerError(V3ContractError):
    """A V3 compilation that must fail closed."""


# ---------------------------------------------------------------------------
# layout registry
# ---------------------------------------------------------------------------
def assert_layout_registry_authoritative(registry_sha256: str) -> str:
    """Refuse the superseded 10-layout TRAIN registry, loudly."""
    value = str(registry_sha256)
    if value == SUPERSEDED_LAYOUT_SPLIT_REGISTRY_V1_SHA256:
        raise V3CompilerError(
            "V3_LAYOUT_SPLIT_REGISTRY_V1 is "
            "SUPERSEDED_PRE_GENERATION_CAPACITY_VERSION (10 TRAIN layouts); "
            "official V3 generation requires V3_LAYOUT_SPLIT_REGISTRY_V2 "
            f"{LAYOUT_SPLIT_REGISTRY_V2_SHA256}")
    if value != LAYOUT_SPLIT_REGISTRY_V2_SHA256:
        raise V3CompilerError(
            f"unknown V3 layout split registry {value[:16]}...; expected "
            f"{LAYOUT_SPLIT_REGISTRY_V2_SHA256[:16]}...")
    return value


def load_v3_layout_registry(root: Path) -> Mapping[str, Any]:
    """The final layout registry, hash-verified at both nesting levels."""
    path = Path(root) / _REGISTRY_ARTIFACT
    if not path.exists():
        raise V3CompilerError("V3 layout split registry V2 is missing")
    document = json.loads(path.read_text(encoding="ascii"))
    assert_layout_registry_authoritative(
        document.get("v3_layout_split_registry_v2_sha256", ""))
    body = {key: value for key, value in document.items()
            if key != "phase9d_v3f_l_layout_split_registry_sha256"}
    if not verify_canonical_hash(body, "v3_layout_split_registry_v2_sha256"):
        raise V3CompilerError("V3 layout registry root does not recompute")
    if not verify_canonical_hash(
            document, "phase9d_v3f_l_layout_split_registry_sha256"):
        raise V3CompilerError("V3 layout registry artifact hash does not recompute")
    return document


def v3_split_of_layout(registry: Mapping[str, Any], layout_id: str) -> Optional[str]:
    """Split by registry MEMBERSHIP. The layout id is never parsed."""
    groups = {
        "TRAIN": V3_TRAIN,
        "VALIDATION": V3_VALIDATION,
    }
    for group, split in groups.items():
        if layout_id in registry["assignment"][group]["layout_ids"]:
            return split
    if layout_id in registry["assignment"]["RESERVE"]["layout_ids"]:
        return None
    raise V3CompilerError(
        f"layout {layout_id!r} is not a member of the final V3 registry")


def layout_records(registry: Mapping[str, Any], group: str,
                   ) -> Mapping[str, Mapping[str, Any]]:
    return {str(record["layout_id"]): record
            for record in registry["layout_records"][group]}


# ---------------------------------------------------------------------------
# frozen dry source manifests
# ---------------------------------------------------------------------------
def load_v3_source_manifest(root: Path, *, v3_split: str) -> Mapping[str, Any]:
    """Load and fully verify one frozen dry V3 source manifest.

    Verification covers the inner manifest root, the outer artifact hash, every
    bound frozen contract hash, the registry hash, the prospective shape, and
    the dryness counters. Nothing here executes.
    """
    if v3_split not in _MANIFEST_ARTIFACTS:
        raise V3CompilerError(f"unknown V3 split {v3_split!r}")
    relative, inner_field, outer_field = _MANIFEST_ARTIFACTS[v3_split]
    path = Path(root) / relative
    if not path.exists():
        raise V3CompilerError(f"frozen V3 manifest is missing: {relative}")
    document = json.loads(path.read_text(encoding="ascii"))

    if document[inner_field] != FROZEN_V3_MANIFEST_ROOTS[v3_split]:
        raise V3CompilerError(f"{relative} manifest root drifted")
    if document[outer_field] != FROZEN_V3_MANIFEST_ARTIFACT_HASHES[v3_split]:
        raise V3CompilerError(f"{relative} artifact hash drifted")
    body = {key: value for key, value in document.items() if key != outer_field}
    if not verify_canonical_hash(body, inner_field):
        raise V3CompilerError(f"{relative} manifest root does not recompute")
    if not verify_canonical_hash(document, outer_field):
        raise V3CompilerError(f"{relative} artifact hash does not recompute")

    if document["v3_split"] != v3_split:
        raise V3CompilerError("manifest v3_split disagrees with the request")
    if document["protocol_version"] != RECOVERABILITY_PROTOCOL_V3:
        raise V3CompilerError("V3 manifest must declare RECOVERABILITY_V3")
    bound = {
        "recoverability_probabilistic_target_v3_sha256": PROBABILISTIC_TARGET_V3_SHA256,
        "recoverability_replica_protocol_v3_sha256": REPLICA_PROTOCOL_V3_SHA256,
        "recoverability_row_binding_v3_spec_sha256": ROW_BINDING_V3_SPEC_SHA256,
        "source_acquisition_protocol_sha256": SOURCE_ACQUISITION_PROTOCOL_SHA256,
        "target_v4_contract_sha256": TARGET_V4_CONTRACT_SHA256,
    }
    for field_name, expected in bound.items():
        if document.get(field_name) != expected:
            raise V3CompilerError(f"{relative} binds a wrong {field_name}")
    assert_layout_registry_authoritative(
        document.get("v3_layout_split_registry_v2_sha256", ""))

    shape = FROZEN_V3_SHAPE[v3_split]
    if int(document["source_episodes"]) != shape["source_episodes"]:
        raise V3CompilerError("V3 source-episode budget drifted")
    if int(document["layout_count"]) != shape["layout_count"]:
        raise V3CompilerError("V3 layout capacity drifted")
    if tuple(document["layout_offsets"]) != shape["layout_offsets"]:
        raise V3CompilerError("V3 layout offsets drifted")
    if (int(document["episodes_per_layout_min"]) != shape["episodes_per_layout"]
            or int(document["episodes_per_layout_max"]) != shape["episodes_per_layout"]):
        raise V3CompilerError("V3 episodes-per-layout uniformity drifted")
    if RESERVE_OFFSET in tuple(document["layout_offsets"]):
        raise V3CompilerError("the 0.33 reserve offset may not enter a V3 split")
    for offset in FORBIDDEN_OFFSETS:
        if offset in tuple(document["layout_offsets"]):
            raise V3CompilerError(f"offset {offset} is forbidden")
    if document["acquisition_rule"] != REALIZED_TRAJECTORY_UNIFORM_K:
        raise V3CompilerError("V3 acquisition rule drifted")
    if int(document["K"]) != DEFAULT_K:
        raise V3CompilerError("V3 acquisition K drifted")
    if len(document["episodes"]) != shape["source_episodes"]:
        raise V3CompilerError("V3 manifest episode count disagrees with its budget")
    return document


def assert_manifest_remains_dry(manifest: Mapping[str, Any]) -> Mapping[str, int]:
    """No generation has happened, and this phase does not change that."""
    counters = {name: int(manifest[name])
                for name in ("executed", "generated", "rows")}
    if any(value != 0 for value in counters.values()):
        raise V3CompilerError(
            "the frozen V3 manifest is no longer dry; official generation is "
            "not authorized in this phase")
    if manifest["status"] != "DRY_FROZEN_METADATA_ONLY_NO_GENERATION":
        raise V3CompilerError("V3 manifest status is not the frozen dry status")
    return counters


# ---------------------------------------------------------------------------
# source tasks
# ---------------------------------------------------------------------------
def compile_v3_source_tasks(
    root: Path, *, v3_split: str,
    manifest: Optional[Mapping[str, Any]] = None,
    registry: Optional[Mapping[str, Any]] = None,
) -> Tuple[OfficialSourceTask, ...]:
    """Turn the frozen dry manifest into source tasks. Executes nothing."""
    manifest = manifest or load_v3_source_manifest(root, v3_split=v3_split)
    registry = registry or load_v3_layout_registry(root)
    group = FROZEN_V3_SHAPE[v3_split]["registry_group"]
    records = layout_records(registry, group)
    horizons = {layout_id: float(record["episode_horizon_seconds"])
                for layout_id, record in records.items()}

    tasks = []
    seen = set()
    for entry in manifest["episodes"]:
        study = str(entry["study"])
        layout_id = str(entry["layout_id"])
        if study in SEALED_STUDIES:
            raise V3CompilerError("sealed study entered V3 compilation")
        if int(entry["team_size"]) == 24:
            raise V3CompilerError("N=24 is sealed and may not enter a V3 manifest")
        # Split authority: membership, never the layout-id string.
        membership = v3_split_of_layout(registry, layout_id)
        if membership != v3_split:
            raise V3CompilerError(
                f"layout {layout_id!r} is not a member of {v3_split}")
        if str(entry["v3_split"]) != v3_split:
            raise V3CompilerError("episode v3_split disagrees with the manifest")
        if str(records[layout_id]["layout_sha256"]) != str(entry["layout_sha256"]):
            raise V3CompilerError(f"layout {layout_id!r} geometry disagrees "
                                  "with the registry")
        job_id = str(entry["episode_id"])
        if job_id in seen:
            raise V3CompilerError("duplicate V3 source-episode identity")
        seen.add(job_id)
        tasks.append(OfficialSourceTask(
            job_id=job_id,
            dataset_id=str(manifest["dataset_id"]),
            study=study,
            split=v3_split,
            layout_source_split=str(entry["generator_split_namespace"]),
            family=str(entry["family"]),
            layout_id=layout_id,
            layout_sha256=str(entry["layout_sha256"]),
            team_size=int(entry["team_size"]),
            source_class=str(entry["source_policy"]),
            episode_index=int(entry["episode_index"]),
            horizon_seconds=horizons[layout_id],
            seeds=dict(entry["seeds"])))
    return tuple(tasks)


# ---------------------------------------------------------------------------
# Stage A -- unchanged
# ---------------------------------------------------------------------------
def execute_v3_source_acquisition(
    root: Path, source: OfficialSourceTask, *,
    session_factory=None, protocol_sha256: Optional[str] = None,
) -> V2SourceAcquisition:
    """Stage A is the frozen V2 acquisition, called by its V3 name.

    Deliberately a thin alias rather than a copy: the owner froze acquisition
    unchanged for V3, and a second implementation could drift from the first.
    """
    return execute_v2_source_acquisition(
        root, source, session_factory=session_factory,
        protocol_sha256=protocol_sha256 or SOURCE_ACQUISITION_PROTOCOL_SHA256)


# ---------------------------------------------------------------------------
# Stage B -- V3 candidate tasks
# ---------------------------------------------------------------------------
def v3_replica_jobs(acquisition: V2SourceAcquisition, state, replicas: int,
                    ) -> Tuple[Mapping[str, Any], ...]:
    """Matched randomness, identical to V2 by construction.

    The seed inputs deliberately exclude the protocol version, so a V3 replica
    job derives the *same* matched disturbance seed as the V2 job for the same
    scientific event. That is checked by a qualification test rather than
    asserted here.
    """
    source = acquisition.source
    jobs = []
    for replica_index in range(replicas):
        common = {
            "study": source.study, "split": source.split,
            "scenario_family": source.family,
            "layout_sha256": source.layout_sha256,
            "team_size": source.team_size,
            "source_class": source.source_class,
            "episode_index": source.episode_index,
            "event_slot_index": state.selection_ordinal,
            "replica_index": replica_index,
        }
        matched = derive_generation_seed(
            "counterfactual_rollout", candidate_topology=None, **common)
        for candidate in (COMPACT, LINE):
            jobs.append({
                "candidate_topology": int(candidate),
                "replica_index": replica_index,
                "seeds": {
                    "candidate_replica_job_seed": derive_generation_seed(
                        "counterfactual_rollout",
                        candidate_topology=int(candidate), **common),
                    "matched_disturbance_seed": matched,
                },
                "protocol_version": RECOVERABILITY_PROTOCOL_V3,
                "source_state_fingerprint": state.source_state_fingerprint,
            })
    return tuple(jobs)


def compile_recoverability_v3_candidate_tasks(
    acquisition: V2SourceAcquisition,
) -> Tuple[OfficialDecisionEventTask, ...]:
    """One V3 decision-event task per already-selected realized source state."""
    replicas = replica_count_for_family(acquisition.source.family)
    tasks = []
    for state in acquisition.selected:
        if state.realized_control_step > acquisition.terminal_control_step:
            raise V3CompilerError(
                "a V3 candidate task escaped the realized source trajectory")
        tasks.append(OfficialDecisionEventTask(
            event_id=state.source_event_id,
            source=acquisition.source,
            event_slot_index=state.selection_ordinal,
            resolved_control_step=state.realized_control_step,
            resolved_timestamp_seconds=state.realized_time_seconds,
            replicas_per_candidate=replicas,
            candidate_replica_jobs=v3_replica_jobs(acquisition, state, replicas)))
    if len({task.event_id for task in tasks}) != len(tasks):
        raise V3CompilerError("duplicate V3 decision-event identity")
    return tuple(tasks)


# ---------------------------------------------------------------------------
# dry preflight
# ---------------------------------------------------------------------------
def v3_manifest_dry_report(root: Path, *, v3_split: str) -> Mapping[str, Any]:
    """Everything R29 asks for, with zero scientific execution."""
    contracts = verify_frozen_v3_contracts(Path(root))
    registry = load_v3_layout_registry(root)
    manifest = load_v3_source_manifest(root, v3_split=v3_split)
    counters = assert_manifest_remains_dry(manifest)
    tasks = compile_v3_source_tasks(
        root, v3_split=v3_split, manifest=manifest, registry=registry)
    shape = FROZEN_V3_SHAPE[v3_split]
    group = FROZEN_V3_SHAPE[v3_split]["registry_group"]
    per_layout: Dict[str, int] = {}
    for task in tasks:
        per_layout[task.layout_id] = per_layout.get(task.layout_id, 0) + 1
    replica_counts = {task.family: replica_count_for_family(task.family)
                      for task in tasks}
    return {
        "v3_split": v3_split,
        "manifest_root_sha256": manifest[_MANIFEST_ARTIFACTS[v3_split][1]],
        "manifest_artifact_sha256": manifest[_MANIFEST_ARTIFACTS[v3_split][2]],
        "v3_layout_split_registry_v2_sha256":
            registry["v3_layout_split_registry_v2_sha256"],
        "source_episodes": len(tasks),
        "layout_count": len(per_layout),
        "episodes_per_layout": sorted(set(per_layout.values())),
        "layout_offsets": list(manifest["layout_offsets"]),
        "registry_group": group,
        "expected": dict(shape, layout_offsets=list(shape["layout_offsets"])),
        "replica_counts": dict(sorted(replica_counts.items())),
        "reserve_offset_present": RESERVE_OFFSET in tuple(manifest["layout_offsets"]),
        "forbidden_offsets_present": [
            offset for offset in FORBIDDEN_OFFSETS
            if offset in tuple(manifest["layout_offsets"])],
        "dry_counters": counters,
        "frozen_contracts": dict(contracts),
        "recoverability_v3_required_replica_invalidity_contract_v1_sha256":
            INVALIDITY_CONTRACT_V3_SHA256,
        "scientific_execution": 0,
    }
