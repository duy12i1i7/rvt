import inspect
import json
import subprocess
from pathlib import Path

import pytest

import rvt_swarm.topology_registry as topology_registry
from rvt_swarm.decentralized.online_topology_scope import (
    ADMITTED,
    HISTORICAL_REPLAY_ONLY,
    NO_TRANSITION_REQUIRED,
    ONLINE_TOPOLOGY_SCOPE,
    ONLINE_TOPOLOGY_SCOPE_SCHEMA_VERSION,
    PHASE7R_SOURCE_COMMIT,
    UNKNOWN_TOPOLOGY,
    UNSUPPORTED_INITIAL_TOPOLOGY,
    UNSUPPORTED_TRANSITION,
    build_online_topology_scope_manifest,
    canonical_scope_sha256,
    evaluate_historical_transition,
    evaluate_primary_initial_topology,
    evaluate_publication_transition,
    request_publication_transition,
)
from rvt_swarm.decentralized.forced_topology_runtime import (
    ForcedTopologyRuntimeAdapter,
)
from rvt_swarm.decentralized.transition_messages import (
    TransitionIntent,
    deserialize_transition_message,
)
from rvt_swarm.decentralized.transition_protocol import (
    TransitionProtocolNode,
    TransitionProtocolRuntimeOptions,
)
from rvt_swarm.decentralized.transition_runtime import (
    run_phase7_transition_episode,
)
from rvt_swarm.runtime_configuration import RuntimeConfig
from rvt_swarm.topology_registry import COMPACT, KEEP, LINE


ROOT = Path(__file__).resolve().parents[1]
DECLARED_TEAM_SIZES = (5, 6, 8, 12, 16, 24)
KEEP_EDGES = (
    (KEEP, COMPACT),
    (COMPACT, KEEP),
    (KEEP, LINE),
    (LINE, KEEP),
)


def _node(topology=COMPACT):
    return TransitionProtocolNode(
        0,
        tuple(range(5)),
        RuntimeConfig.for_team_size(5),
        topology,
        TransitionProtocolRuntimeOptions(True),
    )


@pytest.mark.parametrize("team_size", DECLARED_TEAM_SIZES)
@pytest.mark.parametrize("source,target", ((COMPACT, LINE), (LINE, COMPACT)))
def test_compact_line_graph_is_admitted_for_every_declared_team_size(
    team_size, source, target,
):
    assert team_size in ONLINE_TOPOLOGY_SCOPE.qualified_team_sizes
    decision = evaluate_publication_transition(source, target)
    assert decision.status == ADMITTED
    assert decision.admitted
    assert decision.creates_lifecycle


@pytest.mark.parametrize("source,target", KEEP_EDGES)
def test_every_keep_edge_is_structurally_rejected_in_publication_mode(
    source, target,
):
    decision = evaluate_publication_transition(source, target)
    assert decision.status == UNSUPPORTED_TRANSITION
    assert not decision.admitted
    assert not decision.creates_lifecycle
    assert decision.historical_replay_allowed


def test_publication_filter_does_not_route_a_keep_edge_or_mutate_node_state():
    node = _node(COMPACT)
    result = request_publication_transition(
        node, 1, KEEP, "local_opening", 0.0
    )
    assert result.intent is None
    assert result.decision.status == UNSUPPORTED_TRANSITION
    assert node.committed_topology == COMPACT
    assert node.state == "STABLE_TOPOLOGY"
    assert node.mode_epoch_count == 0
    assert node.active_intent is None


def test_publication_filter_emits_an_intent_for_an_admitted_edge():
    node = _node(COMPACT)
    result = request_publication_transition(
        node, 1, LINE, "local_constriction", 0.0
    )
    assert result.decision.status == ADMITTED
    assert result.intent is not None
    assert result.intent.source_topology == COMPACT
    assert result.intent.candidate_topology == LINE


def test_historical_replay_deserializes_keep_records_without_authorizing_them():
    intent = TransitionIntent.create(
        7, 0, KEEP, LINE, "externally_forced_diagnostic", 1.0, 5.0
    )
    decoded = deserialize_transition_message(intent.payload_bytes())
    assert decoded == intent
    decision = evaluate_historical_transition(KEEP, LINE)
    assert decision.status == HISTORICAL_REPLAY_ONLY
    assert decision.historical_replay_allowed
    assert not decision.admitted
    assert not decision.creates_lifecycle


def test_source_equals_target_creates_no_intent_epoch_or_lifecycle():
    node = _node(COMPACT)
    result = request_publication_transition(
        node, 1, COMPACT, "deterministic_local_fixture", 0.0
    )
    assert result.intent is None
    assert result.decision.status == NO_TRANSITION_REQUIRED
    assert not result.decision.creates_lifecycle
    assert node.mode_epoch_count == 0
    assert node.state == "STABLE_TOPOLOGY"
    assert node.active_intent is None


@pytest.mark.parametrize("source,target", ((999, LINE), (COMPACT, 999)))
def test_unknown_transitions_fail_explicitly(source, target):
    decision = evaluate_publication_transition(source, target)
    assert decision.status == UNKNOWN_TOPOLOGY
    assert not decision.admitted
    assert not decision.historical_replay_allowed


def test_registry_ordering_cannot_change_the_explicit_publication_scope(monkeypatch):
    monkeypatch.setattr(
        topology_registry,
        "PRIMARY_TOPOLOGY_IDS",
        tuple(reversed(topology_registry.PRIMARY_TOPOLOGY_IDS)),
    )
    assert ONLINE_TOPOLOGY_SCOPE.active_topology_ids == (COMPACT, LINE)
    assert ONLINE_TOPOLOGY_SCOPE.active_transition_pairs == (
        (COMPACT, LINE),
        (LINE, COMPACT),
    )


def test_one_graph_has_no_team_size_scenario_or_seed_selector():
    signature = inspect.signature(evaluate_publication_transition)
    assert tuple(signature.parameters) == ("source_topology", "target_topology")
    assert ONLINE_TOPOLOGY_SCOPE.qualified_team_sizes == DECLARED_TEAM_SIZES


def test_primary_runtime_initialization_contract_is_explicit():
    default = evaluate_primary_initial_topology()
    assert default.admitted and default.selected_topology == COMPACT
    rejected_line = evaluate_primary_initial_topology(LINE)
    assert rejected_line.status == UNSUPPORTED_INITIAL_TOPOLOGY
    admitted_line = evaluate_primary_initial_topology(
        LINE, narrow_start_declared=True, physically_valid=True
    )
    assert admitted_line.admitted and admitted_line.selected_topology == LINE
    keep = evaluate_primary_initial_topology(KEEP)
    assert keep.status == UNSUPPORTED_INITIAL_TOPOLOGY
    assert keep.fixed_baseline_only


def test_scope_manifest_is_canonical_hashed_and_matches_runtime_contract():
    manifest = build_online_topology_scope_manifest()
    assert manifest["schema_version"] == ONLINE_TOPOLOGY_SCOPE_SCHEMA_VERSION
    assert manifest["source_commit"] == PHASE7R_SOURCE_COMMIT
    assert manifest["active_candidate_topology_ids"] == [COMPACT, LINE]
    assert manifest["active_directed_transition_pairs"] == [
        [COMPACT, LINE],
        [LINE, COMPACT],
    ]
    assert manifest["scope_sha256"] == canonical_scope_sha256(manifest)
    serialized = json.dumps(manifest, sort_keys=True)
    assert canonical_scope_sha256(json.loads(serialized)) == manifest["scope_sha256"]


def test_committed_scope_manifest_matches_the_authoritative_builder():
    path = ROOT / "results/rvt_fd24/online_topology_scope.json"
    assert json.loads(path.read_text(encoding="ascii")) == (
        build_online_topology_scope_manifest()
    )


def test_phase7_and_phase7r_result_trees_are_bitwise_preserved():
    expected = {
        "results/phase7_transition_protocol": (
            "93ac2641442b3113d75939b477f1d7a400afa8a8"
        ),
        "results/phase7_transition_execution_repair": (
            "511a0027e873555884519efd8be867b855490b2d"
        ),
    }
    for path, tree_id in expected.items():
        actual = subprocess.run(
            ["git", "rev-parse", f"HEAD:{path}"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        assert actual == tree_id


def test_no_frozen_mechanical_file_changed_after_phase7r():
    frozen = (
        "rvt_swarm/topology_registry.py",
        "rvt_swarm/runtime_configuration.py",
        "rvt_swarm/decentralized/ego_graph_v2.py",
        "rvt_swarm/decentralized/robot_local_controller.py",
        "rvt_swarm/decentralized/local_safety_projection.py",
        "rvt_swarm/decentralized/formation_metric_v3.py",
        "rvt_swarm/decentralized/local_control_types.py",
        "rvt_swarm/decentralized/forced_topology_runtime.py",
        "rvt_swarm/decentralized/transition_messages.py",
        "rvt_swarm/decentralized/transition_protocol.py",
        "rvt_swarm/decentralized/transition_readiness.py",
        "rvt_swarm/decentralized/transition_execution.py",
    )
    changed = subprocess.run(
        ["git", "diff", "--name-only", PHASE7R_SOURCE_COMMIT, "--", *frozen],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    # RB16R (owner-authorized): the residual output frame was repaired to WORLD,
    # which required the ego-graph record to carry the mission-to-world
    # orientation. See results/rvt_fd24/model_residual_output_frame_v2.json.
    # Every other frozen mechanical file must still be untouched.
    assert set(changed) <= {"rvt_swarm/decentralized/ego_graph_v2.py"}


def test_keep_forced_topology_execution_remains_available_and_unchanged(
    phase6_input_factory,
):
    runtime, adapter, view, controller_input = phase6_input_factory(topology=KEEP)
    expected = adapter.controller.evaluate(controller_input)
    fixed = ForcedTopologyRuntimeAdapter(
        runtime,
        adapter.local_topology_metadata,
        KEEP,
        controller=adapter.controller,
    )
    assert fixed.evaluate(view, 0.0) == expected


def test_supported_compact_line_runtime_output_matches_phase7r_snapshot():
    result = run_phase7_transition_episode(
        5,
        COMPACT,
        LINE,
        "exact_source",
        "path",
        execution_strategy="generic_role_space_profile",
    )
    assert {
        "transition_success": result.transition_success,
        "collision_free": result.collision_free,
        "projection_infeasible_count": result.projection_infeasible_count,
        "target_tube_entry_step": result.target_tube_entry_step,
        "mode_epoch_count": result.mode_epoch_count,
        "no_op_epoch_count": result.no_op_epoch_count,
        "retry_epoch_count": result.retry_epoch_count,
        "actual_communication_bytes": result.actual_communication_bytes,
    } == {
        "transition_success": True,
        "collision_free": True,
        "projection_infeasible_count": 0,
        "target_tube_entry_step": 19,
        "mode_epoch_count": 1,
        "no_op_epoch_count": 0,
        "retry_epoch_count": 0,
        "actual_communication_bytes": 77380,
    }
