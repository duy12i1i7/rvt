"""The blocked Phase 9 gate preserves the approved mechanical boundary."""

import hashlib
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
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
A1S3Z_AUTHORIZED_FILES = {"rvt_swarm/decentralized/system_model.py"}


def test_phase9_changes_no_phase8_or_mechanical_files():
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
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    contract = json.loads((
        ROOT / "results/rvt_fd24/phase9_s3_centerline_execution_contract_v1.json"
    ).read_text(encoding="ascii"))
    for path in A1S3Z_AUTHORIZED_FILES:
        assert contract["runtime_files"][path]["after_sha256"] == hashlib.sha256(
            (ROOT / path).read_bytes()).hexdigest()
    assert set(changed) <= RB16R_AUTHORIZED_FILES | A1S3Z_AUTHORIZED_FILES


def test_phase9_has_no_dataset_shards_or_training_state():
    dataset_root = ROOT / "results/rvt_fd24/datasets"
    files = tuple(path for path in dataset_root.rglob("*") if path.is_file())
    prohibited_suffixes = (".jsonl", ".jsonl.gz", ".pt", ".pth", ".ckpt")
    assert not any(path.name.endswith(prohibited_suffixes) for path in files)
    assert not any("optimizer" in path.name.lower() for path in files)
