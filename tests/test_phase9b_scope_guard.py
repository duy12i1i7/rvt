"""Phase 9B changes protocol metadata only and executes no scientific work."""

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BLOCKED_PHASE9 = "b7edc024eeb3d76f0827f23f3fc9a0aa34a461ae"
PHASE8 = "c17081fe1cf58cc2d3f929e35ff4bca811c75c58"


# RB16R (owner-authorized, phase PHASE 5R / RB16R): the residual model output
# frame was repaired from the historical mission-named declaration to WORLD.
# The declaration, its supersession and the evidence live in
# results/rvt_fd24/model_residual_output_frame_v2.json. The guard keeps its
# force: every OTHER frozen mechanical file must still be untouched.
RB16R_AUTHORIZED_FILES = {
    "rvt_swarm/decentralized/ego_graph_v2.py",
    "rvt_swarm/fd24/model.py",
    "rvt_swarm/fd24/configuration.py",
    "rvt_swarm/decentralized/guards.py",
}


def test_phase8_and_mechanical_files_are_unchanged():
    protected = (
        "rvt_swarm/phase8",
        "rvt_swarm/topology_registry.py",
        "rvt_swarm/runtime_configuration.py",
        "rvt_swarm/decentralized",
        "rvt_swarm/fd24",
        "results/rvt_fd24/experiment_protocol_manifest.json",
        "results/rvt_fd24/online_topology_scope.json",
        "results/rvt_fd24/splits",
    )
    changed = subprocess.run(
        ["git", "diff", "--name-only", PHASE8, "--", *protected],
        cwd=ROOT, check=True, capture_output=True, text=True,
    ).stdout.splitlines()
    assert set(changed) <= RB16R_AUTHORIZED_FILES


def test_blocked_phase9_artifacts_are_bitwise_preserved():
    paths = (
        "results/rvt_fd24/datasets/phase9_generation_budget.json",
        "results/rvt_fd24/datasets/phase9_preflight_audit.json",
        "docs/PHASE9_DATASET_REPORT.md",
    )
    for path in paths:
        current = subprocess.run(
            ["git", "hash-object", path], cwd=ROOT, check=True,
            capture_output=True, text=True,
        ).stdout.strip()
        baseline = subprocess.run(
            ["git", "rev-parse", f"{BLOCKED_PHASE9}:{path}"], cwd=ROOT,
            check=True, capture_output=True, text=True,
        ).stdout.strip()
        assert current == baseline


def test_addendum_execution_scope_is_zero_and_no_dataset_rows_exist():
    protocol = json.loads(
        (ROOT / "results/rvt_fd24/datasets/dataset_generation_protocol_v1.json").read_text(
            encoding="ascii"
        )
    )
    assert protocol["execution_scope"] == {
        "scientific_dataset_records_generated": 0,
        "rollout_jobs_executed": 0,
        "residual_expert_jobs_executed": 0,
        "training_operations": 0,
        "final_test_geometry_loaded": False,
        "final_test_runtime_access_count": 0,
    }
    root = ROOT / "results/rvt_fd24/datasets"
    assert not any(path.suffix in (".gz", ".pt", ".pth", ".ckpt") for path in root.rglob("*"))
