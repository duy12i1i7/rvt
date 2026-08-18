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

# PHASE 9G-V3I-Q-R (owner-authorized): the phase authorizes "implement the V3
# loader" and "implement the frozen loss and Brier metric", which necessarily
# land in rvt_swarm/fd24. These three are ADDITIONS -- no pre-existing frozen
# mechanical file is touched -- and the assertion below is split so that the
# modification set stays bound by the older authorizations only. That makes the
# guard strictly stronger here than the single subset check it replaces.
V3I_Q_R_ADDED_FILES = {
    "rvt_swarm/fd24/loss_v3.py",
    "rvt_swarm/fd24/metrics_v3.py",
    "rvt_swarm/fd24/loader_v3.py",
}


def _protected_changes(root, phase8, protected):
    """Split the protected diff into additions and modifications."""
    def names(diff_filter):
        return set(subprocess.run(
            ["git", "diff", "--name-only", f"--diff-filter={diff_filter}",
             phase8, "--", *protected],
            cwd=root, check=True, capture_output=True, text=True,
        ).stdout.splitlines())
    return names("A"), names("MRD")


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
    added, modified = _protected_changes(ROOT, PHASE8, protected)
    contract = json.loads((
        ROOT / "results/rvt_fd24/phase9_s3_centerline_execution_contract_v1.json"
    ).read_text(encoding="ascii"))
    for path in A1S3Z_AUTHORIZED_FILES:
        assert contract["runtime_files"][path]["after_sha256"] == hashlib.sha256(
            (ROOT / path).read_bytes()).hexdigest()
    assert modified <= RB16R_AUTHORIZED_FILES | A1S3Z_AUTHORIZED_FILES
    assert added <= V3I_Q_R_ADDED_FILES


def test_phase9_has_no_dataset_shards_or_training_state():
    dataset_root = ROOT / "results/rvt_fd24/datasets"
    files = tuple(path for path in dataset_root.rglob("*") if path.is_file())
    prohibited_suffixes = (".jsonl", ".jsonl.gz", ".pt", ".pth", ".ckpt")
    assert not any(path.name.endswith(prohibited_suffixes) for path in files)
    assert not any("optimizer" in path.name.lower() for path in files)
