import json
from pathlib import Path

from rvt_swarm.phase8.common import verify_canonical_hash
from rvt_swarm.phase8.manifest import (
    REQUIRED_HASHED_DOCUMENTS,
    build_experiment_protocol_manifest,
)


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "results/rvt_fd24/experiment_protocol_manifest.json"


def test_committed_experiment_protocol_manifest_is_deterministic_and_authoritative():
    committed = json.loads(PATH.read_text(encoding="ascii"))
    rebuilt = build_experiment_protocol_manifest(ROOT)
    if committed != rebuilt:
        # The committed manifest is frozen and is never rewritten. RB16R moved
        # the model schema version when it repaired the residual output frame to
        # WORLD, so exactly that field -- and the manifest hash that covers it --
        # may diverge, and only with the erratum as authority. Any other drift
        # still fails.
        erratum = json.loads(
            (ROOT / "results/rvt_fd24/model_residual_output_frame_v2.json")
            .read_text(encoding="ascii"))
        assert committed["model"]["schema_version"] == (
            erratum["historical_declaration"]["model_schema_version"])
        assert rebuilt["model"]["schema_version"] == (
            erratum["current_declaration"]["model_schema_version"])
        allowed = {"model", "experiment_protocol_sha256"}
        differing = {key for key in set(committed) | set(rebuilt)
                     if committed.get(key) != rebuilt.get(key)}
        assert differing <= allowed, differing
        assert {k: v for k, v in committed["model"].items() if k != "schema_version"} == {
            k: v for k, v in rebuilt["model"].items() if k != "schema_version"}
    assert verify_canonical_hash(committed, "experiment_protocol_sha256")
    assert committed["schema_version"] == "rvt-experiment-protocol/v1"


def test_manifest_hashes_every_required_protocol_contract():
    manifest = json.loads(PATH.read_text(encoding="ascii"))
    assert set(manifest["hashed_protocol_documents"]) == set(REQUIRED_HASHED_DOCUMENTS)
    assert set(manifest["split_manifest_sha256"]) == {"train", "validation", "final_test"}
    assert manifest["scenario_family"]["family_count"] == 10


def test_manifest_freezes_scope_and_reports_zero_out_of_scope_execution():
    manifest = json.loads(PATH.read_text(encoding="ascii"))
    assert manifest["online_topology_scope"]["active_candidate_ids"] == [5, 2]
    assert manifest["online_topology_scope"]["active_transition_pairs"] == [[5, 2], [2, 5]]
    assert manifest["phase8_execution_scope"] == {
        "dagger_rounds": 0,
        "final_test_runtime_access_count": 0,
        "full_dataset_generated": False,
        "model_training_runs": 0,
        "tiny_diagnostic_only": True,
    }
