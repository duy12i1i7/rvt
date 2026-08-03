"""Deterministic immutable experiment-protocol manifest construction."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Dict

from ..decentralized.ego_graph_v2 import (
    EGO_GRAPH_FEATURE_SCHEMA_SHA256,
    EGO_GRAPH_SCHEMA_VERSION,
)
from ..fd24.configuration import FD24ModelConfig, canonical_model_config_hash
from ..fd24.model import FD24_MODEL_SCHEMA_VERSION
from ..runtime_configuration import RuntimeConfig, canonical_runtime_hash
from ..topology_registry import TOPOLOGY_REGISTRY_SCHEMA_VERSION
from .common import (
    EXPERIMENT_PROTOCOL_SCHEMA_VERSION,
    ONLINE_TOPOLOGY_SCOPE_SCHEMA_VERSION,
    ONLINE_TOPOLOGY_SCOPE_SHA256,
    PHASE8_APPROVED_BASE_COMMIT,
    attach_canonical_hash,
    file_sha256,
    sha256_document,
    verify_canonical_hash,
    write_json,
)
from .contracts import (
    CheckpointSelectionContract,
    HyperparameterBudget,
    LossContract,
    PracticalSignificanceGates,
    StatisticalAnalysisContract,
    baseline_definitions,
    metric_contract_document,
)
from .provenance import provenance_schema_document
from .scenario import scenario_family_manifest
from .seeds import SEED_DERIVATION_VERSION, SEED_NAMESPACE_SCHEMA_VERSION, SEED_NAMESPACES


REQUIRED_HASHED_DOCUMENTS = {
    "mechanical_architecture_scope": "docs/MECHANICAL_ARCHITECTURE_SCOPE_FREEZE.md",
    "scenario_family_specification": "docs/RVT_FD24_SCENARIO_FAMILY_CONTRACT.md",
    "recoverability_target": "docs/RVT_TASK_RECOVERABILITY_TARGET_V4.md",
    "rollout_protocol": "docs/RVT_COUNTERFACTUAL_ROLLOUT_PROTOCOL.md",
    "action_target": "docs/RVT_RESIDUAL_ACTION_TARGET_V1.md",
    "loss_contract": "docs/RVT_FD24_LOSS_CONTRACT.md",
    "baseline_contract": "docs/RVT_BASELINE_FAIRNESS_CONTRACT.md",
    "metric_contract": "docs/RVT_FD24_METRIC_CONTRACT.md",
    "statistical_contract": "docs/RVT_STATISTICAL_ANALYSIS_CONTRACT.md",
    "seed_contract": "docs/RVT_RANDOM_SEED_AND_REPRODUCIBILITY_CONTRACT.md",
    "practical_significance_gates": "docs/RVT_PRACTICAL_SIGNIFICANCE_GATES.md",
    "final_test_guard": "rvt_swarm/phase8/final_test_guard.py",
}


def _load_split_hash(root: Path, relative_path: str) -> str:
    document = json.loads((root / relative_path).read_text(encoding="ascii"))
    if not verify_canonical_hash(document):
        raise ValueError(f"split manifest hash is invalid: {relative_path}")
    return str(document["manifest_sha256"])


def build_experiment_protocol_manifest(root: Path) -> Dict[str, object]:
    runtime_hashes = {
        str(size): canonical_runtime_hash(RuntimeConfig.for_team_size(size))
        for size in (5, 6, 8, 12, 16, 24)
    }
    document_hashes = {
        name: {
            "path": path,
            "sha256": file_sha256(root / path),
        }
        for name, path in REQUIRED_HASHED_DOCUMENTS.items()
    }
    split_hashes = {
        "train": _load_split_hash(root, "results/rvt_fd24/splits/train_layouts.json"),
        "validation": _load_split_hash(root, "results/rvt_fd24/splits/validation_layouts.json"),
        "final_test": _load_split_hash(root, "results/rvt_fd24/splits/final_test_layouts.sealed.json"),
    }
    scenario_contract = scenario_family_manifest()
    model_config = FD24ModelConfig()
    contract_documents = {
        "loss": asdict(LossContract()),
        "hyperparameter_budget": asdict(HyperparameterBudget()),
        "checkpoint_selection": asdict(CheckpointSelectionContract()),
        "baselines": [asdict(item) for item in baseline_definitions()],
        "metrics": metric_contract_document(),
        "statistics": asdict(StatisticalAnalysisContract()),
        "practical_significance": asdict(PracticalSignificanceGates()),
        "seeds": {
            "schema_version": SEED_NAMESPACE_SCHEMA_VERSION,
            "derivation_version": SEED_DERIVATION_VERSION,
            "namespaces": [asdict(item) for item in SEED_NAMESPACES],
        },
        "provenance": provenance_schema_document(),
    }
    document: Dict[str, object] = {
        "schema_version": EXPERIMENT_PROTOCOL_SCHEMA_VERSION,
        "protocol_version": "rvt-fd24-phase8/v1",
        "approved_mechanical_source_commit": PHASE8_APPROVED_BASE_COMMIT,
        "online_topology_scope": {
            "schema_version": ONLINE_TOPOLOGY_SCOPE_SCHEMA_VERSION,
            "sha256": ONLINE_TOPOLOGY_SCOPE_SHA256,
            "active_candidate_ids": [5, 2],
            "active_transition_pairs": [[5, 2], [2, 5]],
        },
        "topology_registry": {
            "schema_version": TOPOLOGY_REGISTRY_SCHEMA_VERSION,
            "source_sha256": file_sha256(root / "rvt_swarm/topology_registry.py"),
        },
        "ego_graph": {
            "schema_version": EGO_GRAPH_SCHEMA_VERSION,
            "feature_schema_sha256": EGO_GRAPH_FEATURE_SCHEMA_SHA256,
        },
        "model": {
            "schema_version": FD24_MODEL_SCHEMA_VERSION,
            "config_sha256": canonical_model_config_hash(model_config),
        },
        "runtime_configuration_sha256_by_team_size": runtime_hashes,
        "scenario_family": {
            "schema_version": scenario_contract["schema_version"],
            "sha256": scenario_contract["scenario_family_sha256"],
            "family_count": scenario_contract["family_count"],
        },
        "split_manifest_sha256": split_hashes,
        "hashed_protocol_documents": document_hashes,
        "structured_contract_sha256": {
            name: sha256_document(value)
            for name, value in contract_documents.items()
        },
        "phase8_execution_scope": {
            "full_dataset_generated": False,
            "model_training_runs": 0,
            "dagger_rounds": 0,
            "final_test_runtime_access_count": 0,
            "tiny_diagnostic_only": True,
        },
    }
    return attach_canonical_hash(document, "experiment_protocol_sha256")


def write_experiment_protocol_manifest(root: Path) -> Dict[str, object]:
    document = build_experiment_protocol_manifest(root)
    write_json(root / "results/rvt_fd24/experiment_protocol_manifest.json", document)
    return document
