"""Composite protocol binds the original protocol and generation budget."""

import json
from pathlib import Path

from rvt_swarm.phase8.common import verify_canonical_hash
from rvt_swarm.phase9b.budget import (
    build_generation_budget_manifest,
    build_generation_protocol_manifest,
)


ROOT = Path(__file__).resolve().parents[1]


def test_both_new_manifests_are_canonical_and_deterministic():
    budget = build_generation_budget_manifest(ROOT)
    protocol = build_generation_protocol_manifest(ROOT, budget)
    assert verify_canonical_hash(budget, "generation_budget_sha256")
    assert verify_canonical_hash(protocol, "dataset_generation_protocol_sha256")
    assert json.loads(
        (ROOT / "results/rvt_fd24/datasets/generation_budget_v1.json").read_text(encoding="ascii")
    ) == budget
    assert json.loads(
        (ROOT / "results/rvt_fd24/datasets/dataset_generation_protocol_v1.json").read_text(encoding="ascii")
    ) == protocol


def test_composite_references_both_required_future_dataset_hashes():
    budget = build_generation_budget_manifest(ROOT)
    protocol = build_generation_protocol_manifest(ROOT, budget)
    assert protocol["future_dataset_required_hashes"] == [
        "0bb68dd56ef0837f83c44dcf5281498f8c0ea934b00bbb9b3d3f298264d32147",
        budget["generation_budget_sha256"],
    ]
    assert protocol["generation_budget_sha256"] == budget["generation_budget_sha256"]


def test_old_blocked_budget_remains_readable_but_cannot_authorize():
    old = json.loads(
        (ROOT / "results/rvt_fd24/datasets/phase9_generation_budget.json").read_text(
            encoding="ascii"
        )
    )
    protocol = build_generation_protocol_manifest(ROOT)
    assert old["status"] == "BLOCKED_PROTOCOL_INCOMPLETENESS"
    assert old["generation_authorized"] is False
    assert protocol["blocked_phase9_audit"]["can_authorize_generation"] is False
