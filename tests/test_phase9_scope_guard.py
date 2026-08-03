"""The blocked Phase 9 gate preserves the approved mechanical boundary."""

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PHASE8 = "c17081fe1cf58cc2d3f929e35ff4bca811c75c58"


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
    assert changed == []


def test_phase9_has_no_dataset_shards_or_training_state():
    dataset_root = ROOT / "results/rvt_fd24/datasets"
    files = tuple(path for path in dataset_root.rglob("*") if path.is_file())
    prohibited_suffixes = (".jsonl", ".jsonl.gz", ".pt", ".pth", ".ckpt")
    assert not any(path.name.endswith(prohibited_suffixes) for path in files)
    assert not any("optimizer" in path.name.lower() for path in files)
