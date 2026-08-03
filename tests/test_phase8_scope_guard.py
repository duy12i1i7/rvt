import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE = "d24a0f674c1e75df293e4524f020acc49d4e2f35"


def test_phase8_changes_no_frozen_mechanical_implementation():
    frozen = (
        "rvt_swarm/topology_registry.py",
        "rvt_swarm/runtime_configuration.py",
        "rvt_swarm/decentralized/ego_graph_v2.py",
        "rvt_swarm/fd24/model.py",
        "rvt_swarm/fd24/configuration.py",
        "rvt_swarm/decentralized/robot_local_controller.py",
        "rvt_swarm/decentralized/local_safety_projection.py",
        "rvt_swarm/decentralized/transition_messages.py",
        "rvt_swarm/decentralized/transition_protocol.py",
        "rvt_swarm/decentralized/transition_readiness.py",
        "rvt_swarm/decentralized/transition_execution.py",
        "rvt_swarm/decentralized/formation_metric_v3.py",
    )
    changed = subprocess.run(
        ["git", "diff", "--name-only", BASE, "--", *frozen],
        cwd=ROOT, check=True, capture_output=True, text=True,
    ).stdout.splitlines()
    assert changed == []


def test_online_scope_manifest_is_bitwise_unchanged():
    current = subprocess.run(
        ["git", "hash-object", "results/rvt_fd24/online_topology_scope.json"],
        cwd=ROOT, check=True, capture_output=True, text=True,
    ).stdout.strip()
    baseline = subprocess.run(
        ["git", "rev-parse", f"{BASE}:results/rvt_fd24/online_topology_scope.json"],
        cwd=ROOT, check=True, capture_output=True, text=True,
    ).stdout.strip()
    assert current == baseline


def test_tiny_diagnostic_is_exactly_bounded_and_nonvacuous():
    diagnostic = json.loads(
        (ROOT / "results/rvt_fd24/phase8_tiny_target_diagnostic.json").read_text(
            encoding="ascii"
        )
    )
    assert diagnostic["declared_budget"] == {
        "candidate_rollouts": 16,
        "decision_events": 8,
        "residual_action_samples": 16,
    }
    assert diagnostic["recoverability"]["candidate_positive_counts"] == {
        "COMPACT": 4, "LINE": 4,
    }
    assert diagnostic["recoverability"]["candidate_negative_counts"] == {
        "COMPACT": 4, "LINE": 4,
    }
    assert diagnostic["residual_action"]["valid_sample_count"] == 16


def test_no_dataset_checkpoint_training_or_dagger_artifact_was_created():
    phase8_files = tuple(
        path.name for path in (ROOT / "results/rvt_fd24").iterdir() if path.is_file()
    )
    assert not any("dataset" in name or "checkpoint" in name for name in phase8_files)
    diagnostic = json.loads(
        (ROOT / "results/rvt_fd24/phase8_tiny_target_diagnostic.json").read_text(
            encoding="ascii"
        )
    )
    assert diagnostic["scientific_dataset_generated"] is False
    assert diagnostic["model_training_runs"] == 0
    assert diagnostic["dagger_rounds"] == 0
    assert diagnostic["final_test_runtime_access_count"] == 0


def test_all_required_phase8_documents_exist():
    required = (
        "RVT_FD24_RESEARCH_QUESTIONS_AND_HYPOTHESES.md",
        "RVT_FD24_UNIT_OF_ANALYSIS.md",
        "RVT_FD24_SCENARIO_FAMILY_CONTRACT.md",
        "RVT_FD24_SCENARIO_HEADROOM_PROTOCOL.md",
        "RVT_FD24_SPLIT_CONTRACT.md",
        "RVT_FD24_TEAM_SIZE_EXPERIMENT_CONTRACT.md",
        "RVT_TASK_RECOVERABILITY_TARGET_V4.md",
        "RVT_COUNTERFACTUAL_ROLLOUT_PROTOCOL.md",
        "RVT_LOCAL_VIEW_TASK_LABEL_CONTRACT.md",
        "RVT_DECISION_STATE_SAMPLING_PROTOCOL.md",
        "RVT_RECOVERABILITY_LABEL_AUDIT_GATES.md",
        "RVT_RESIDUAL_ACTION_TARGET_V1.md",
        "RVT_RESIDUAL_TARGET_DIAGNOSTIC_AUDIT.md",
        "RVT_DENSE_ACTION_DATA_CONTRACT.md",
        "RVT_FD24_LOSS_CONTRACT.md",
        "RVT_FD24_HYPERPARAMETER_BUDGET.md",
        "RVT_CHECKPOINT_SELECTION_CONTRACT.md",
        "RVT_RANDOM_SEED_AND_REPRODUCIBILITY_CONTRACT.md",
        "RVT_DATA_PROVENANCE_CONTRACT.md",
        "RVT_BASELINE_FAIRNESS_CONTRACT.md",
        "RVT_FD24_METRIC_CONTRACT.md",
        "RVT_PRACTICAL_SIGNIFICANCE_GATES.md",
        "RVT_STATISTICAL_ANALYSIS_CONTRACT.md",
        "PHASE8_TARGET_NON_VACUITY_DIAGNOSTIC.md",
        "PHASE8_EXPERIMENT_PROTOCOL_REPORT.md",
    )
    assert all((ROOT / "docs" / name).is_file() for name in required)
