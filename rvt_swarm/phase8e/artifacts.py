"""Artifact writer for the specification-only Phase 8E addendum."""

from __future__ import annotations

from pathlib import Path
from typing import Dict

from ..phase8.common import write_json
from .compiler import compile_nonfinal_split
from .protocol import (
    build_executable_protocol,
    build_source_policy_contracts,
    build_target_v4_execution_contract,
    validate_executable_protocol,
    validate_source_policy_contracts,
    validate_target_v4_execution_contract,
)


def write_phase8e_artifacts(root: Path) -> Dict[str, object]:
    root = root.resolve()
    source = build_source_policy_contracts()
    target = build_target_v4_execution_contract()
    protocol = build_executable_protocol(root)
    validate_source_policy_contracts(source)
    validate_target_v4_execution_contract(target)
    validate_executable_protocol(protocol)

    result_root = root / "results/rvt_fd24"
    write_json(result_root / "source_policy_contracts_v1.json", source)
    write_json(result_root / "target_v4_execution_contract_v1.json", target)
    write_json(result_root / "executable_scientific_protocol_v1.json", protocol)

    counts = {}
    hashes = {}
    for split in ("train", "validation"):
        records = compile_nonfinal_split(root, split, protocol)
        destination = result_root / "layout_execution_specifications" / split
        counts[split] = len(records)
        hashes[split] = []
        for record in records:
            layout_id = record["source_layout"]["layout_id"]
            write_json(destination / f"{layout_id}.json", record)
            hashes[split].append(record["layout_execution_specification_sha256"])
    return {
        "protocol_hash": protocol["protocol_hash"],
        "source_policy_contract_sha256": source["source_policy_contract_sha256"],
        "target_v4_execution_contract_sha256": target[
            "target_v4_execution_contract_sha256"
        ],
        "layout_counts": counts,
        "layout_hashes": hashes,
    }
