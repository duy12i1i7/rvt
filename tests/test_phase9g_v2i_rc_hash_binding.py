"""Phase 9G-V2I-RC -- exact scientific-hash binding guards.

The frozen Recoverability Source-Acquisition Protocol V2 scientific hash is
pinned here as a literal. Every V2 scientific identity -- source event, row,
candidate task and future official manifest -- must bind *this exact value*, not
a derived or additive provenance hash that merely happens to reference it.

These tests read only live code and contracts. They deliberately do not read the
consistency-closure artifact, so that artifact stays pure provenance and is never
"required inside the image".
"""

from __future__ import annotations

import json
import pathlib

import pytest

from rvt_swarm.phase8.common import canonical_json_bytes, sha256_document
from rvt_swarm.phase9d_h1r.acquisition_v2 import (
    SOURCE_EVENT_IDENTITY_SCHEMA_VERSION, SOURCE_EVENT_KEY, RealizedSourceState,
    acquisition_protocol_v2_sha256, build_source_event_key,
    frozen_acquisition_protocol_v2, frozen_acquisition_protocol_v2_sha256,
    recoverability_source_event_id_v2,
)
from rvt_swarm.phase9g0r import compiler_v2
from rvt_swarm.phase9g0r.contracts_v2 import (
    RECOVERABILITY_ROW_IDENTITY_V2_FIELDS, TARGET_V4_SHA256,
    build_recoverability_row_key_v2, recoverability_row_binding_v2_spec,
    recoverability_row_binding_v2_spec_sha256, recoverability_scientific_row_id_v2,
)

ROOT = pathlib.Path(".")

#: The frozen scientific protocol, pinned as a literal so drift is a test failure
#: rather than a silent re-derivation.
FROZEN_PROTOCOL_SHA256 = (
    "19fa68a37d80f16ee1463b872f26402963daeb5a56f375423634a90dc1f3546d")
#: The additive V2 row-binding contract hash. A *different* object that embeds
#: the frozen protocol; it never substitutes for it.
ROW_BINDING_V2_SHA256 = (
    "98f18a94c6a69d27a4cbf38169ca15e998ce4b4adfbba9a48cb1b3233391adf8")


def _state(step: int = 60) -> RealizedSourceState:
    return RealizedSourceState(0, step, step * 0.15, "b" * 64, False, {})


def _row_key(**overrides):
    key = dict(build_recoverability_row_key_v2(
        study="study_a_zero_shot", split="train", family="F3",
        layout_sha256="a" * 64, team_size=8, episode_id="episode-0",
        realized_source_timestep=60, robot_id=2, candidate_topology_id=5,
        graph_fingerprint="c" * 64,
        source_acquisition_protocol_sha256=FROZEN_PROTOCOL_SHA256))
    key.update(overrides)
    return key


# ---------------------------------------------------------------------------
# the two hashes are distinct objects with distinct roles
# ---------------------------------------------------------------------------
def test_frozen_protocol_object_hashes_to_the_pinned_value() -> None:
    protocol = frozen_acquisition_protocol_v2(
        design_protocol_sha256=acquisition_protocol_v2_sha256())
    assert frozen_acquisition_protocol_v2_sha256(protocol) == FROZEN_PROTOCOL_SHA256


def test_row_binding_contract_hashes_to_its_own_distinct_value() -> None:
    assert recoverability_row_binding_v2_spec_sha256() == ROW_BINDING_V2_SHA256
    assert ROW_BINDING_V2_SHA256 != FROZEN_PROTOCOL_SHA256


def test_row_binding_contract_embeds_the_frozen_protocol() -> None:
    """98f18a94 is additive provenance: it *references* 19fa68, never replaces it."""
    spec = recoverability_row_binding_v2_spec()
    assert spec["acquisition"]["source_acquisition_protocol_sha256"] == \
        FROZEN_PROTOCOL_SHA256
    assert spec["owner_authorization"]["additive"] is True
    assert spec["owner_authorization"]["supersedes_v1_row_identity"] is False


# ---------------------------------------------------------------------------
# A -- source-event identity
# ---------------------------------------------------------------------------
def test_source_event_identity_binds_the_exact_frozen_protocol() -> None:
    assert "source_acquisition_protocol_sha256" in SOURCE_EVENT_KEY
    key = build_source_event_key(
        study="study_a_zero_shot", split="train", family="F3",
        layout_sha256="a" * 64, team_size=8, episode_id="episode-0",
        state=_state(), protocol_sha256=FROZEN_PROTOCOL_SHA256)
    assert key["source_acquisition_protocol_sha256"] == FROZEN_PROTOCOL_SHA256
    assert key["schema_version"] == SOURCE_EVENT_IDENTITY_SCHEMA_VERSION
    preimage = canonical_json_bytes(dict(key)).decode("ascii")
    assert FROZEN_PROTOCOL_SHA256 in preimage
    assert recoverability_source_event_id_v2(key) == sha256_document(key)


def test_source_event_identity_changes_if_the_protocol_changes() -> None:
    base = build_source_event_key(
        study="s", split="train", family="F3", layout_sha256="a" * 64,
        team_size=8, episode_id="e", state=_state(),
        protocol_sha256=FROZEN_PROTOCOL_SHA256)
    other = dict(base, source_acquisition_protocol_sha256=ROW_BINDING_V2_SHA256)
    assert recoverability_source_event_id_v2(other) != \
        recoverability_source_event_id_v2(base)


# ---------------------------------------------------------------------------
# B -- row identity V2
# ---------------------------------------------------------------------------
def test_row_identity_v2_binds_the_exact_frozen_protocol() -> None:
    key = _row_key()
    assert key["source_acquisition_protocol_sha256"] == FROZEN_PROTOCOL_SHA256
    preimage = canonical_json_bytes(dict(key)).decode("ascii")
    assert FROZEN_PROTOCOL_SHA256 in preimage


def test_row_identity_v2_binds_both_hashes_in_distinct_fields() -> None:
    key = _row_key()
    assert key["source_acquisition_protocol_sha256"] == FROZEN_PROTOCOL_SHA256
    assert key["recoverability_row_binding_v2_spec_sha256"] == ROW_BINDING_V2_SHA256
    assert key["target_v4_contract_sha256"] == TARGET_V4_SHA256
    for field in ("source_acquisition_protocol_sha256",
                  "recoverability_row_binding_v2_spec_sha256",
                  "target_v4_contract_sha256"):
        assert field in RECOVERABILITY_ROW_IDENTITY_V2_FIELDS


def test_row_binding_hash_never_substitutes_for_the_protocol_hash() -> None:
    """The exact defect this phase audits for: 98f18a94 landing in the field
    that must carry 19fa68."""
    substituted = _row_key(source_acquisition_protocol_sha256=ROW_BINDING_V2_SHA256)
    assert recoverability_scientific_row_id_v2(substituted) != \
        recoverability_scientific_row_id_v2(_row_key())


def test_row_identity_v2_preimage_carries_no_outcome_data() -> None:
    preimage = canonical_json_bytes(dict(_row_key())).decode("ascii").lower()
    for token in ("label", "disposition", "recoverable_positive",
                  "valid_task_negative", "generation_invalid", "aggregate",
                  "worker", "chunk", "attempt", "retry", "wall_clock",
                  "model_", "outcome"):
        assert token not in preimage, token


# ---------------------------------------------------------------------------
# C -- future official manifests
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("split,episodes", [("train", 1200), ("validation", 300)])
def test_official_manifest_binds_the_exact_frozen_protocol(split, episodes) -> None:
    manifest = compiler_v2.compile_recoverability_v2_source_manifest(
        ROOT, study="study_a_zero_shot", split=split)
    assert manifest["source_acquisition_protocol_sha256"] == FROZEN_PROTOCOL_SHA256
    assert manifest["recoverability_row_binding_v2_spec_sha256"] == \
        ROW_BINDING_V2_SHA256
    assert manifest["target_v4_contract_sha256"] == TARGET_V4_SHA256
    assert manifest["source_episodes"] == episodes
    assert manifest["authorizes_official_generation"] is False
    preimage = canonical_json_bytes(dict(manifest)).decode("ascii")
    assert FROZEN_PROTOCOL_SHA256 in preimage


# ---------------------------------------------------------------------------
# D -- candidate tasks
# ---------------------------------------------------------------------------
def test_candidate_task_event_id_derives_from_the_frozen_protocol() -> None:
    from rvt_swarm.phase9g0r.compiler import compile_source_tasks
    source = next(task for task in compile_source_tasks(
        ROOT, study="study_a_zero_shot", split="validation")
        if task.team_size == 5)
    acquisition = compiler_v2.execute_v2_source_acquisition(ROOT, source)
    assert acquisition.protocol_sha256 == FROZEN_PROTOCOL_SHA256
    tasks = compiler_v2.compile_recoverability_v2_candidate_tasks(acquisition)
    assert tasks, "the canary episode must yield at least one candidate task"

    selected = acquisition.selected[0]
    key = build_source_event_key(
        study=source.study, split=source.split, family=source.family,
        layout_sha256=source.layout_sha256, team_size=source.team_size,
        episode_id=source.job_id,
        state=RealizedSourceState(
            selected.universe_index, selected.realized_control_step,
            selected.realized_time_seconds, selected.source_state_fingerprint,
            False, {}),
        protocol_sha256=FROZEN_PROTOCOL_SHA256)
    assert recoverability_source_event_id_v2(key) == tasks[0].event_id


def test_producer_v2_requires_the_acquisition_protocol_hash() -> None:
    from rvt_swarm.phase9g0r.producer_v2 import (
        V2ProducerError, produce_recoverability_event_by_protocol,
    )
    from rvt_swarm.phase9g0r.contracts_v2 import RECOVERABILITY_PROTOCOL_V2
    with pytest.raises(V2ProducerError):
        produce_recoverability_event_by_protocol(
            ROOT, None, protocol_version=RECOVERABILITY_PROTOCOL_V2)
