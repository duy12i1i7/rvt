"""Generation seeds and semantic IDs are order-independent and guarded."""

from pathlib import Path

import pytest

from rvt_swarm.phase9b.identity import (
    CandidateReplicaIdentity,
    DecisionEventIdentity,
    SourceEpisodeIdentity,
    build_dataset_cells,
    derive_generation_seed,
    reject_duplicate_semantic_identities,
)


ROOT = Path(__file__).resolve().parents[1]


def _seed(cell, candidate, replica):
    return derive_generation_seed(
        "counterfactual_rollout",
        study=cell.study,
        split=cell.split,
        scenario_family=cell.family_id,
        layout_sha256=cell.layout_sha256,
        team_size=cell.team_size,
        source_class="S0_SCRIPTED_DIAGNOSTIC",
        episode_index=0,
        event_slot_index=2,
        candidate_topology=candidate,
        replica_index=replica,
    )


def test_seed_mapping_is_order_independent_and_32_bit():
    cells = build_dataset_cells(ROOT, "study_a_train")[:12]
    forward = {cell.canonical_hash(): _seed(cell, 5, 0) for cell in cells}
    reverse = {cell.canonical_hash(): _seed(cell, 5, 0) for cell in reversed(cells)}
    assert forward == reverse
    assert all(0 <= seed < 2**32 for seed in forward.values())


def test_candidate_and_replica_are_seed_identity_inputs():
    cell = build_dataset_cells(ROOT, "study_a_train")[0]
    assert len({_seed(cell, 5, 0), _seed(cell, 2, 0), _seed(cell, 5, 1)}) == 3


def test_canonical_job_ids_are_unique_and_duplicates_rejected():
    cell = build_dataset_cells(ROOT, "study_a_train")[0]
    source = SourceEpisodeIdentity(cell, "S0_SCRIPTED_DIAGNOSTIC", 0)
    event = DecisionEventIdentity(source, 0)
    identities = [
        CandidateReplicaIdentity(event, candidate, 0).job_id()
        for candidate in (5, 2)
    ]
    reject_duplicate_semantic_identities(identities)
    with pytest.raises(ValueError, match="duplicate semantic"):
        reject_duplicate_semantic_identities((identities[0], identities[0]))


def test_final_test_seed_derivation_is_rejected():
    with pytest.raises(PermissionError, match="final-test"):
        derive_generation_seed(
            "initial_condition",
            study="study_a_zero_shot",
            split="final_test",
            scenario_family="F1",
            layout_sha256="a" * 64,
            team_size=5,
            source_class="S0_SCRIPTED_DIAGNOSTIC",
            episode_index=0,
        )
