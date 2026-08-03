import pytest

from rvt_swarm.phase8.seeds import (
    FINAL_TEST_SPLIT,
    SEED_DERIVATION_VERSION,
    SEED_NAMESPACES,
    SEED_NAMESPACE_SCHEMA_VERSION,
    derive_seed,
    seed_commitment,
)


def test_seed_namespaces_are_unique_and_cover_every_required_semantic_role():
    assert SEED_NAMESPACE_SCHEMA_VERSION == "rvt-seed-namespaces/v1"
    assert SEED_DERIVATION_VERSION == "sha256-uint32/v1"
    assert len(SEED_NAMESPACES) == 10
    assert len({item.name for item in SEED_NAMESPACES}) == 10
    assert len({item.root_seed for item in SEED_NAMESPACES}) == 10


def test_seed_derivation_is_deterministic_and_semantically_separated():
    first = derive_seed("initial_condition", "layout-a", 5, 0, split="train")
    assert first == derive_seed("initial_condition", "layout-a", 5, 0, split="train")
    assert first != derive_seed("communication", "layout-a", 5, 0, split="train")
    assert first != derive_seed("initial_condition", "layout-a", 6, 0, split="train")


def test_final_test_seed_derivation_is_sealed_and_only_commitment_is_public():
    with pytest.raises(PermissionError, match="authorization"):
        derive_seed("evaluation", "episode", split=FINAL_TEST_SPLIT)
    seed = derive_seed(
        "evaluation", "episode", split=FINAL_TEST_SPLIT,
        sealed_final_authorized=True,
    )
    commitment = seed_commitment(seed)
    assert len(commitment) == 64
    assert str(seed) not in commitment
