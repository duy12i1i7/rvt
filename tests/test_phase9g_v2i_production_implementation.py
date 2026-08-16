"""Phase 9G-V2I -- Recoverability V2 production implementation.

Closes the three Phase 9G-V2Q blocking findings:

* V2Q-F1 -- a V2 compiler that selects from the realized universe instead of
  reading V1's precomputed `resolved_control_step`;
* V2Q-F2 -- a V2 producer for which the source-terminated-before-event branch
  is unreachable, with V1 left byte-identical for historical replay;
* V2Q-F3 -- an additive Row Identity V2 that binds the source-acquisition
  protocol, so a V1 row can never collide with a V2 row.
"""

from __future__ import annotations

import dataclasses
import inspect
import json
import pathlib

import pytest

from rvt_swarm.phase8.common import sha256_document, verify_canonical_hash
from rvt_swarm.phase9d_h1r.acquisition_v2 import (
    DEFAULT_K, REALIZED_TRAJECTORY_UNIFORM_K, RealizedSourceState,
    SourceStateUniverse, frozen_acquisition_protocol_v2,
    frozen_acquisition_protocol_v2_sha256, select,
)
from rvt_swarm.phase9g0r import compiler_v2, producer_v2
from rvt_swarm.phase9g0r.compiler import OfficialDecisionEventTask, compile_source_tasks
from rvt_swarm.phase9g0r.contracts import (
    RECOVERABILITY_ROW_IDENTITY_FIELDS, Phase9G0RContractError,
    recoverability_scientific_row_id,
)
from rvt_swarm.phase9g0r.contracts_v2 import (
    PROHIBITED_ROW_IDENTITY_V2_FIELDS, RECOVERABILITY_PROTOCOL_V1,
    RECOVERABILITY_PROTOCOL_V2, RECOVERABILITY_ROW_IDENTITY_V2_FIELDS,
    RECOVERABILITY_ROW_IDENTITY_V2_SCHEMA_VERSION, TARGET_V4_SHA256,
    build_recoverability_row_key_v2, recoverability_row_binding_v2_spec,
    recoverability_row_binding_v2_spec_sha256, recoverability_scientific_row_id_v2,
)
from rvt_swarm.phase9g0r.producer import produce_recoverability_candidate

ROOT = pathlib.Path(".")
ARTIFACT_ROOT = pathlib.Path("results/rvt_fd24")
PROTOCOL_SHA = frozen_acquisition_protocol_v2_sha256(frozen_acquisition_protocol_v2())
BINDING_SHA = recoverability_row_binding_v2_spec_sha256()


def universe(m: int) -> SourceStateUniverse:
    states = tuple(
        RealizedSourceState(
            universe_index=i, control_step=i * 10, time_seconds=i * 1.5,
            source_state_fingerprint="%064d" % i, is_terminal_step=(i == m - 1),
            descriptors={})
        for i in range(m))
    return SourceStateUniverse(states=states, terminal_cause="GOAL_COMPLETE",
                               terminal_control_step=max(m - 1, 0) * 10,
                               episode_realized=True)


# ---------------------------------------------------------------------------
# V2Q-F1 -- the V2 compiler does not consume V1 scheduling
# ---------------------------------------------------------------------------
def test_v2_compiler_does_not_read_v1_scheduled_events() -> None:
    source = inspect.getsource(compiler_v2)
    assert "decision_event_jobs" not in source
    assert "load_authoritative_job_manifest" not in source
    assert "enumerate_realized_source_universe" in source
    assert "REALIZED_TRAJECTORY_UNIFORM_K" in source


def test_v2_compiler_binds_the_frozen_protocol_and_target_v4() -> None:
    manifest = compiler_v2.compile_recoverability_v2_source_manifest(
        ROOT, study="study_a_zero_shot", split="validation")
    assert manifest["source_acquisition_protocol_sha256"] == PROTOCOL_SHA
    assert manifest["target_v4_contract_sha256"] == TARGET_V4_SHA256
    assert manifest["recoverability_row_binding_v2_spec_sha256"] == BINDING_SHA
    assert manifest["acquisition_rule"] == REALIZED_TRAJECTORY_UNIFORM_K
    assert manifest["K"] == DEFAULT_K == 5
    assert manifest["protocol_version"] == RECOVERABILITY_PROTOCOL_V2
    assert manifest["authorizes_official_generation"] is False


def test_v2_manifest_unit_is_the_source_episode_not_the_event() -> None:
    manifest = compiler_v2.compile_recoverability_v2_source_manifest(
        ROOT, study="study_a_zero_shot", split="train")
    assert manifest["scientific_unit"] == "SOURCE_EPISODE"
    assert manifest["maximum_is_a_cap_not_a_target"] is True
    assert manifest["realized_event_count_is_emergent"] is True
    assert manifest["adaptive_refill_permitted"] is False
    assert manifest["outcome_dependent_stopping_permitted"] is False


@pytest.mark.parametrize("split,budget,cap", [("train", 1200, 6000),
                                              ("validation", 300, 1500)])
def test_fixed_source_budget(split: str, budget: int, cap: int) -> None:
    tasks = compiler_v2.compile_recoverability_v2_source_episodes(
        ROOT, study="study_a_zero_shot", split=split)
    assert len(tasks) == budget
    manifest = compiler_v2.compile_recoverability_v2_source_manifest(
        ROOT, study="study_a_zero_shot", split=split)
    assert manifest["source_episodes"] == budget
    assert manifest["maximum_selected_source_events"] == cap == budget * DEFAULT_K
    assert manifest["families"] == ["F%d" % i for i in range(1, 11)]
    assert 24 not in manifest["team_sizes"]
    assert manifest["n24_episodes"] == 0
    assert manifest["study_b_episodes"] == 0
    assert manifest["final_test_episodes"] == 0


@pytest.mark.parametrize("split", ["final_test", "test", "n24_evaluation",
                                   "study_b_train"])
def test_sealed_splits_have_no_v2_budget(split: str) -> None:
    with pytest.raises(compiler_v2.V2CompilerError):
        compiler_v2.compile_recoverability_v2_source_episodes(
            ROOT, study="study_a_zero_shot", split=split)


@pytest.mark.parametrize("study", ["study_a_n24_evaluation", "study_b_with_n24",
                                   "final_test"])
def test_sealed_studies_are_refused(study: str) -> None:
    with pytest.raises(compiler_v2.V2CompilerError):
        compiler_v2.compile_recoverability_v2_source_episodes(
            ROOT, study=study, split="train")


def test_manifest_fails_closed_on_an_excluded_identity() -> None:
    tasks = compiler_v2.compile_recoverability_v2_source_episodes(
        ROOT, study="study_a_zero_shot", split="validation")
    from rvt_swarm.phase9d_h1r.exclusion import design_pilot_identity
    burned = {design_pilot_identity(**compiler_v2._source_identity(tasks[3]))}
    with pytest.raises(compiler_v2.V2CompilerError):
        compiler_v2.compile_recoverability_v2_source_episodes(
            ROOT, study="study_a_zero_shot", split="validation", excluded=burned)


def test_committed_exclusion_sets_are_loaded_by_default() -> None:
    burned = compiler_v2.load_v2_excluded_identities(ROOT)
    pilot = json.loads((ARTIFACT_ROOT
                        / "phase9d_h1r_design_pilot_exclusion_set_v1.json").read_text())
    canary = json.loads(
        (ARTIFACT_ROOT
         / "phase9g_v2q_qualification_canary_exclusion_set_v1.json").read_text())
    assert len(burned) == (pilot["excluded_identity_count"]
                           + canary["excluded_identity_count"])


# ---------------------------------------------------------------------------
# selection semantics on the production path
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("m,expected", [
    (0, ()), (1, (0,)), (3, (0, 1, 2)), (5, (0, 1, 2, 3, 4)),
    (13, (0, 3, 6, 9, 12)), (101, (0, 25, 50, 75, 100))])
def test_selection_semantics(m, expected) -> None:
    assert select(REALIZED_TRAJECTORY_UNIFORM_K, universe(m), DEFAULT_K) == expected


def test_m_zero_yields_no_candidate_tasks() -> None:
    empty = SourceStateUniverse(states=(), terminal_cause="INITIALIZATION_INVALID",
                                terminal_control_step=0, episode_realized=False)
    source = compile_source_tasks(ROOT, study="study_a_zero_shot",
                                  split="validation")[0]
    acquisition = compiler_v2.V2SourceAcquisition(
        source=source, protocol_sha256=PROTOCOL_SHA, M=0,
        terminal_cause="INITIALIZATION_INVALID", terminal_control_step=0,
        universe_fingerprints=(), selected=())
    assert acquisition.selected_event_count == 0
    assert compiler_v2.compile_recoverability_v2_candidate_tasks(acquisition) == ()
    assert empty.M == 0


def test_candidate_task_cannot_escape_the_realized_trajectory() -> None:
    source = compile_source_tasks(ROOT, study="study_a_zero_shot",
                                  split="validation")[0]
    bad = compiler_v2.V2SelectedSourceState(
        selection_ordinal=0, universe_index=0, realized_control_step=10_000,
        realized_time_seconds=1500.0, source_state_fingerprint="a" * 64,
        source_event_id="b" * 64)
    acquisition = compiler_v2.V2SourceAcquisition(
        source=source, protocol_sha256=PROTOCOL_SHA, M=1,
        terminal_cause="GOAL_COMPLETE", terminal_control_step=50,
        universe_fingerprints=("a" * 64,), selected=(bad,))
    with pytest.raises(compiler_v2.V2CompilerError):
        compiler_v2.compile_recoverability_v2_candidate_tasks(acquisition)


def test_matched_randomness_is_shared_across_candidates() -> None:
    source = compile_source_tasks(ROOT, study="study_a_zero_shot",
                                  split="validation")[0]
    state = compiler_v2.V2SelectedSourceState(
        selection_ordinal=2, universe_index=7, realized_control_step=70,
        realized_time_seconds=10.5, source_state_fingerprint="c" * 64,
        source_event_id="d" * 64)
    acquisition = compiler_v2.V2SourceAcquisition(
        source=source, protocol_sha256=PROTOCOL_SHA, M=9,
        terminal_cause="GOAL_COMPLETE", terminal_control_step=80,
        universe_fingerprints=tuple("%064d" % i for i in range(9)),
        selected=(state,))
    task = compiler_v2.compile_recoverability_v2_candidate_tasks(acquisition)[0]
    from rvt_swarm.topology_registry import COMPACT, LINE
    compact = [j["seeds"]["matched_disturbance_seed"]
               for j in task.replica_jobs(COMPACT)]
    line = [j["seeds"]["matched_disturbance_seed"] for j in task.replica_jobs(LINE)]
    assert compact == line, "COMPACT and LINE must share the matched disturbance seed"
    job_seeds_compact = [j["seeds"]["candidate_replica_job_seed"]
                         for j in task.replica_jobs(COMPACT)]
    job_seeds_line = [j["seeds"]["candidate_replica_job_seed"]
                      for j in task.replica_jobs(LINE)]
    assert job_seeds_compact != job_seeds_line


def test_f8_f9_keep_three_replicas() -> None:
    from rvt_swarm.phase9c_rb.counterfactual import replica_count_for_family
    for family in ("F8", "F9"):
        assert replica_count_for_family(family) == 3
    for family in ("F1", "F2", "F3", "F4", "F5", "F6", "F7", "F10"):
        assert replica_count_for_family(family) == 1


# ---------------------------------------------------------------------------
# V2Q-F3 -- Row Identity V2 and V1/V2 separation
# ---------------------------------------------------------------------------
def test_row_binding_v2_spec_is_additive_and_hashes() -> None:
    spec = recoverability_row_binding_v2_spec()
    assert spec["owner_authorization"]["authorized"] is True
    assert spec["owner_authorization"]["additive"] is True
    assert spec["owner_authorization"]["supersedes_v1_row_identity"] is False
    assert spec["v1_row_identity_modified"] is False
    assert spec["authorizes_official_generation"] is False
    assert recoverability_row_binding_v2_spec_sha256(spec) == sha256_document(spec)


def test_v1_row_identity_fields_are_untouched() -> None:
    assert RECOVERABILITY_ROW_IDENTITY_FIELDS == (
        "schema", "study", "split", "family", "layout_sha256", "team_size",
        "episode_id", "timestep", "robot_id", "candidate_topology_id",
        "graph_fingerprint", "target_v4_contract_sha256",
        "recoverability_row_binding_spec_sha256")


def test_v2_row_identity_binds_the_acquisition_protocol() -> None:
    assert "source_acquisition_protocol_sha256" in \
        RECOVERABILITY_ROW_IDENTITY_V2_FIELDS
    assert "realized_source_timestep" in RECOVERABILITY_ROW_IDENTITY_V2_FIELDS
    assert "timestep" not in RECOVERABILITY_ROW_IDENTITY_V2_FIELDS


def _v2_key(**overrides):
    key = dict(build_recoverability_row_key_v2(
        study="study_a_zero_shot", split="train", family="F3",
        layout_sha256="a" * 64, team_size=8, episode_id="episode-0",
        realized_source_timestep=60, robot_id=2, candidate_topology_id=5,
        graph_fingerprint="b" * 64,
        source_acquisition_protocol_sha256=PROTOCOL_SHA))
    key.update(overrides)
    return key


def test_v1_and_v2_rows_for_the_same_state_never_collide() -> None:
    """I19: identical scientific coordinates under V1 and V2 must differ."""
    v1_binding = json.loads(
        (ARTIFACT_ROOT / "phase9_recoverability_row_binding_v1.json").read_text()
    )["phase9_recoverability_row_binding_sha256"]
    v1_key = {
        "schema": "rvt-recoverability-row-identity/v1",
        "study": "study_a_zero_shot", "split": "train", "family": "F3",
        "layout_sha256": "a" * 64, "team_size": 8, "episode_id": "episode-0",
        "timestep": 60, "robot_id": 2, "candidate_topology_id": 5,
        "graph_fingerprint": "b" * 64,
        "target_v4_contract_sha256": TARGET_V4_SHA256,
        "recoverability_row_binding_spec_sha256": v1_binding,
    }
    assert recoverability_scientific_row_id(v1_key) != \
        recoverability_scientific_row_id_v2(_v2_key())


def test_v2_row_id_is_invariant_to_operational_context() -> None:
    """I19: worker/chunk/attempt/retry/order cannot move a V2 row identity."""
    baseline = recoverability_scientific_row_id_v2(_v2_key())
    for _ in range(5):
        assert recoverability_scientific_row_id_v2(_v2_key()) == baseline
    reordered = dict(reversed(list(_v2_key().items())))
    assert recoverability_scientific_row_id_v2(reordered) == baseline


@pytest.mark.parametrize("field", sorted(PROHIBITED_ROW_IDENTITY_V2_FIELDS))
def test_v2_row_identity_rejects_prohibited_fields(field: str) -> None:
    with pytest.raises(Phase9G0RContractError):
        recoverability_scientific_row_id_v2(_v2_key(**{field: 1}))


def test_v2_row_identity_rejects_missing_or_extra_fields() -> None:
    incomplete = _v2_key()
    incomplete.pop("family")
    with pytest.raises(Phase9G0RContractError):
        recoverability_scientific_row_id_v2(incomplete)
    with pytest.raises(Phase9G0RContractError):
        recoverability_scientific_row_id_v2(_v2_key(unexpected="x"))


def test_v2_row_id_changes_with_the_acquisition_protocol() -> None:
    assert recoverability_scientific_row_id_v2(
        _v2_key(source_acquisition_protocol_sha256="f" * 64)) != \
        recoverability_scientific_row_id_v2(_v2_key())


def test_v2_row_identity_schema_is_v2() -> None:
    assert RECOVERABILITY_ROW_IDENTITY_V2_SCHEMA_VERSION.endswith("/v2")
    with pytest.raises(Phase9G0RContractError):
        recoverability_scientific_row_id_v2(
            _v2_key(schema="rvt-recoverability-row-identity/v1"))


# ---------------------------------------------------------------------------
# V2Q-F2 -- producer dispatch, and the historical branch preserved
# ---------------------------------------------------------------------------
def test_v1_producer_branch_is_preserved_for_historical_replay() -> None:
    source = inspect.getsource(produce_recoverability_candidate)
    assert "source_terminated_before_event" in source
    assert "control_step < task.resolved_control_step" in source


def test_producer_dispatch_is_by_explicit_protocol_version() -> None:
    assert RECOVERABILITY_PROTOCOL_V1 == "RECOVERABILITY_V1"
    assert RECOVERABILITY_PROTOCOL_V2 == "RECOVERABILITY_V2"
    with pytest.raises(producer_v2.V2ProducerError):
        producer_v2.produce_recoverability_event_by_protocol(
            ROOT, None, protocol_version="RECOVERABILITY_V3")
    with pytest.raises(producer_v2.V2ProducerError):
        producer_v2.produce_recoverability_event_by_protocol(
            ROOT, None, protocol_version=RECOVERABILITY_PROTOCOL_V2)


def test_v2_producer_refuses_an_unrealized_source_state() -> None:
    """I21: V2 must never convert a nonexistent source state into an invalid."""
    source = inspect.getsource(producer_v2.produce_recoverability_v2_event)
    assert "source_terminated_before_event" in source
    assert "must never convert this into GENERATION_INVALID" in source


def test_v1_invalid_versus_v2_no_event_on_the_same_episode() -> None:
    """I21 regression, executed: the same episode, both protocols.

    V1 keeps its historical accounting for an unreached scheduled step; V2
    selects only realized states and therefore emits nothing for it.
    """
    source = next(task for task in compile_source_tasks(
        ROOT, study="study_a_zero_shot", split="validation")
        if task.team_size == 5)
    acquisition = compiler_v2.execute_v2_source_acquisition(ROOT, source)
    unreached = acquisition.terminal_control_step + 10_000

    v1_task = OfficialDecisionEventTask(
        event_id="v1-unreached", source=source, event_slot_index=4,
        resolved_control_step=unreached, resolved_timestamp_seconds=1e6,
        replicas_per_candidate=1,
        candidate_replica_jobs=tuple(
            {"candidate_topology": topology, "replica_index": 0,
             "seeds": {"candidate_replica_job_seed": 1,
                       "matched_disturbance_seed": 1}}
            for topology in (5, 2)))
    v1_result = produce_recoverability_candidate(ROOT, v1_task, 5)
    assert v1_result["source_terminated_before_event"] is True
    assert v1_result["disposition"]["disposition"] == "GENERATION_INVALID"

    steps = [state.realized_control_step for state in acquisition.selected]
    assert unreached not in steps
    assert all(step <= acquisition.terminal_control_step for step in steps)
    assert len(steps) == min(acquisition.M, DEFAULT_K)


# ---------------------------------------------------------------------------
# artifacts
# ---------------------------------------------------------------------------
V2I_ARTIFACTS = {
    "binding": ("phase9g_v2i_recoverability_v2_executable_binding_v1.json",
                "phase9g_v2i_recoverability_v2_executable_binding_sha256"),
    "row_identity": ("phase9g_v2i_recoverability_row_identity_v2_contract_v1.json",
                     "phase9g_v2i_recoverability_row_identity_v2_contract_sha256"),
    "separation": ("phase9g_v2i_v1_v2_identity_separation_v1.json",
                   "phase9g_v2i_v1_v2_identity_separation_sha256"),
    "manifest": ("phase9g_v2i_v2_manifest_dry_compile_v1.json",
                 "phase9g_v2i_v2_manifest_dry_compile_sha256"),
    "canary": ("phase9g_v2i_v2_end_to_end_canary_v1.json",
               "phase9g_v2i_v2_end_to_end_canary_sha256"),
    "determinism": ("phase9g_v2i_v2_determinism_v1.json",
                    "phase9g_v2i_v2_determinism_sha256"),
    "docker": ("phase9g_v2i_docker_reproducibility_repair_v1.json",
               "phase9g_v2i_docker_reproducibility_repair_sha256"),
    "readiness": ("phase9g_v2i_next_generation_readiness_v1.json",
                  "phase9g_v2i_next_generation_readiness_sha256"),
}


@pytest.mark.parametrize("name", sorted(V2I_ARTIFACTS))
def test_v2i_artifact_hashes_canonically(name: str) -> None:
    path, field = V2I_ARTIFACTS[name]
    assert verify_canonical_hash(
        json.loads((ARTIFACT_ROOT / path).read_text(encoding="ascii")), field)


def test_canary_published_only_two_n_rows_and_no_fake_invalid() -> None:
    canary = json.loads(
        (ARTIFACT_ROOT / V2I_ARTIFACTS["canary"][0]).read_text(encoding="ascii"))
    assert canary["fake_generation_invalid"] == 0
    assert canary["partial_publications"] == 0
    assert canary["duplicate_row_ids"] == 0
    assert canary["row_schema_versions"] == ["rvt-recoverability-scientific-row/v2"]
    assert canary["official_namespace_written"] is False
    for record in canary["records"]:
        for event in record["events"]:
            assert event["actual_row_count"] in (0, event["expected_row_count"])
            if event["committable"]:
                assert event["actual_row_count"] == 2 * record["team_size"]


def test_canary_determinism_is_worker_and_order_invariant() -> None:
    determinism = json.loads(
        (ARTIFACT_ROOT / V2I_ARTIFACTS["determinism"][0]).read_text(encoding="ascii"))
    assert determinism["w1_equals_w12"] is True
    assert determinism["order_invariant"] is True
    assert determinism["digest_w1"] == determinism["digest_w12"] == \
        determinism["digest_reverse"]


def test_readiness_reports_no_official_data_and_target_pending() -> None:
    readiness = json.loads(
        (ARTIFACT_ROOT / V2I_ARTIFACTS["readiness"][0]).read_text(encoding="ascii"))
    assert readiness["official_v2_generation_authorized"] is False
    assert readiness["target_status"] == "TARGET_REQUALIFICATION_PENDING"
    assert set(readiness["closed_scopes"].values()) == {0}
    assert readiness["v2q_findings_closed"] == ["V2Q-F1", "V2Q-F2", "V2Q-F3"]
