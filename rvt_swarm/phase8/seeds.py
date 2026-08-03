"""Versioned, non-overlapping seed namespaces for Phase 8 and later phases."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Tuple


SEED_NAMESPACE_SCHEMA_VERSION = "rvt-seed-namespaces/v1"
SEED_DERIVATION_VERSION = "sha256-uint32/v1"
FINAL_TEST_SPLIT = "final_test"


@dataclass(frozen=True)
class SeedNamespace:
    name: str
    root_seed: int
    semantic_role: str


SEED_NAMESPACES: Tuple[SeedNamespace, ...] = (
    SeedNamespace("layout_generation", 8101, "deterministic geometry parameters"),
    SeedNamespace("split", 8102, "immutable split membership"),
    SeedNamespace("initial_condition", 8103, "formation pose and velocity"),
    SeedNamespace("communication", 8104, "delay loss and disconnection schedule"),
    SeedNamespace("dynamic_obstacle", 8105, "moving obstacle realization"),
    SeedNamespace("counterfactual_rollout", 8106, "matched candidate disturbance"),
    SeedNamespace("data_sampling", 8107, "decision and dense-action subsampling"),
    SeedNamespace("model_initialization", 8108, "model parameter initialization"),
    SeedNamespace("training_dataloader", 8109, "training batch ordering"),
    SeedNamespace("evaluation", 8110, "paired closed-loop evaluation"),
)

_NAMESPACE_BY_NAME = {item.name: item for item in SEED_NAMESPACES}


def derive_seed(
    namespace: str,
    *semantic_parts: object,
    split: str | None = None,
    sealed_final_authorized: bool = False,
) -> int:
    if namespace not in _NAMESPACE_BY_NAME:
        raise ValueError(f"unknown seed namespace {namespace!r}")
    if split == FINAL_TEST_SPLIT and not sealed_final_authorized:
        raise PermissionError("final-test seed derivation requires sealed authorization")
    item = _NAMESPACE_BY_NAME[namespace]
    payload = "|".join(
        (
            SEED_NAMESPACE_SCHEMA_VERSION,
            SEED_DERIVATION_VERSION,
            item.name,
            str(item.root_seed),
            str(split or "none"),
            *(str(part) for part in semantic_parts),
        )
    ).encode("ascii")
    return int.from_bytes(hashlib.sha256(payload).digest()[:4], "big")


def seed_commitment(seed: int) -> str:
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise ValueError("seed must be a nonnegative integer")
    return hashlib.sha256(f"sealed-seed/v1|{seed}".encode("ascii")).hexdigest()
