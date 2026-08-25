"""Clean-room dataset composition, frozen before any clean-room data exists.

CR-1 stopped because V3 bound the generator, the offsets and every scientific
rule, but never bound how much data to make or of what shape. This module is
that missing authority. Nothing here was chosen from a clean-room outcome,
because none exists.

The pilot's own balanced design, reconstructed from
results/rvt_fd24/phase9d_v3f_l_{train,validation}_manifest_dry_final_v1.json,
is the template. Its atomic cell is

    (scenario family) x (team size) x (source policy)  =  10 x 5 x 6 = 300 cells

and every pilot split filled that grid uniformly. Every clean-room role does
the same, so each role total is an exact multiple of 300 and every
(family, team_size) cell holds an exact integer count.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Iterator, Mapping

# ---------------------------------------------------------------- the grid ---
FAMILIES: tuple[str, ...] = ("F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10")
TEAM_SIZES: tuple[int, ...] = (5, 6, 8, 12, 16)
SOURCE_POLICIES: tuple[str, ...] = (
    "S0_SCRIPTED_DIAGNOSTIC", "S1_ALWAYS_COMPACT", "S2_ALWAYS_LINE",
    "S3_FROZEN_LOCAL_GEOMETRIC_SELECTOR", "S4_FROZEN_TRANSITION_PROTOCOL",
    "S5_BOUNDED_PERTURBATION")
CELLS = len(FAMILIES) * len(TEAM_SIZES) * len(SOURCE_POLICIES)      # 300

# Replicas per candidate follow the frozen replica law: F8 and F9 take R = 3,
# every other family takes R = 1. Reproduced here for manifest construction, not
# redefined -- the law itself lives in the frozen replica-protocol artifact.
REPLICA_FAMILIES_R3: frozenset[str] = frozenset({"F8", "F9"})

# The frozen acquisition rule caps selected source events per episode at K = 5.
ACQUISITION_RULE = "REALIZED_TRAJECTORY_UNIFORM_K"
K_MAX_SELECTED_SOURCE_EVENTS_PER_EPISODE = 5

V3_ROOT = "90d374d52f47319949cfafd724e83996d9d9dd95a71eb26ab6fed0116252e905"


class CompositionContractError(ValueError):
    """A dataset-composition violation that must fail closed."""


@dataclass(frozen=True)
class RoleComposition:
    role: str
    offset: float
    episodes_per_cell: int          # per (family, team_size, source_policy)
    layout_instances_per_family: int
    purpose: str
    sizing_basis: str
    open_loop_event_acquisition: bool

    @property
    def source_episode_count(self) -> int:
        return self.episodes_per_cell * CELLS

    @property
    def episodes_per_family_team_size_cell(self) -> int:
        return self.episodes_per_cell * len(SOURCE_POLICIES)

    @property
    def layout_count(self) -> int:
        return self.layout_instances_per_family * len(FAMILIES)

    @property
    def episodes_per_layout(self) -> int:
        return self.source_episode_count // self.layout_count

    @property
    def maximum_selected_source_events(self) -> int | None:
        """K x episodes, for the open-loop roles only.

        The closed-loop roles are analysed with the EPISODE as the unit, so the
        decision-event expansion does not apply to them.
        """
        if not self.open_loop_event_acquisition:
            return None
        return K_MAX_SELECTED_SOURCE_EVENTS_PER_EPISODE * self.source_episode_count


ROLE_COMPOSITION: Mapping[str, RoleComposition] = {
    "TRAIN-R": RoleComposition(
        "TRAIN-R", 0.00, 4, 1, "train the final clean-room predictors from scratch",
        "preserves the official pilot TRAIN scientific budget exactly: 1200 source "
        "episodes and 24 episodes per (family, team size) cell. The pilot reached that "
        "with two layout variants per family; TRAIN-R reaches it with one, because V3 "
        "froze TRAIN-R to a single offset.", True),
    "SELECT-R": RoleComposition(
        "SELECT-R", 0.11, 1, 1, "one-shot predictor-family selection",
        "preserves the official pilot VALIDATION selection-evidence budget exactly: 300 "
        "source episodes, 6 per (family, team size) cell, one layout per family.", True),
    "CL-DEV-R": RoleComposition(
        "CL-DEV-R", 0.44, 1, 1, "closed-loop controller development and the oracle ceiling",
        "precision-based: at 300 episodes a 95 percent interval on an episode rate has "
        "half-width 0.057 at the worst-case rate, adequate for development ranking, and "
        "the universe is reused across all logged configurations so comparisons stay "
        "paired. Kept to the smallest balanced multiple because up to 40 configurations "
        "are run over it.", False),
    "MAIN-R": RoleComposition(
        "MAIN-R", 0.55, 3, 1, "one-shot main closed-loop confirmation",
        "prospective power: 900 episodes gives 0.96 power against a planning alternative "
        "of twice the frozen 0.08 threshold, under a deliberately conservative variance "
        "model. 600 would give only 0.87.", False),
    "MECH-R": RoleComposition(
        "MECH-R", 0.66, 3, 1, "surgical mechanism confirmation",
        "fixed at MAIN-R's size, which satisfies the conservative rule of being at least "
        "as large as MAIN-R. Each mechanism contrast is its own paired comparison on the "
        "same universe, so each inherits MAIN-R's power.", False),
    "PROTECTED-R": RoleComposition(
        "PROTECTED-R", 0.79, 2, 1,
        "final generalization to unseen layout instances within known families",
        "precision-based: 600 episodes gives a 95 percent interval half-width of 0.040 at "
        "the worst-case rate, tighter than the 0.05 target, for an estimation role that "
        "runs no hypothesis test.", False),
}

# Planning inputs for the confirmatory roles. All frozen, none outcome-derived.
MAIN_R_PLANNING = {
    "endpoint": "episode_task_success_rate",
    "threshold": 0.08,
    "planning_alternative": 0.16,
    "planning_alternative_justification":
        "twice the frozen practical threshold. The rule requires the LOWER 95 percent "
        "bound to exceed 0.08, so the true effect must clear the threshold by roughly the "
        "width of the bound. Setting the minimum detectable effect at 2x the frozen "
        "threshold uses only frozen numbers and introduces nothing outcome-derived.",
    "alpha_one_sided": 0.05,
    "target_power": 0.90,
    "variance_model":
        "arms treated as INDEPENDENT with worst-case Bernoulli variance 0.25 each, so "
        "Var(delta) = 0.5/n. The real design is PAIRED by source episode, and pairing can "
        "only reduce variance, so this is strictly conservative.",
    "pilot_information_used": "NONE in the arithmetic. The pilot's decisive-event "
        "discordance counts exist and show that topology choice is decisive for a nonzero "
        "share of decision events, which is what makes any closed-loop benefit possible, "
        "but they are DECISION-EVENT quantities, not paired closed-loop episode rates, "
        "and were deliberately kept out of the sizing.",
    "achieved_power_at_chosen_size": 0.9599,
}


def _int_from_digest(digest: bytes, modulus: int) -> int:
    return int.from_bytes(digest[:8], "big") % modulus


GENERATION_SEED_MODULUS = 2 ** 32       # the generator's seeds are uint32
GENERATION_SEED_DOMAIN = "GENERATION"


def generation_seed(role: str) -> int:
    """seed(role) = int(SHA256(V3_root | role | "GENERATION")[:8]) mod 2**32.

    Deterministic from immutable authority, so no seed was ever hand-picked and
    any independent party can recompute every one of them.
    """
    if role not in ROLE_COMPOSITION:
        raise CompositionContractError(f"unknown clean-room role: {role}")
    payload = "|".join((V3_ROOT, role, GENERATION_SEED_DOMAIN)).encode("ascii")
    return _int_from_digest(hashlib.sha256(payload).digest(), GENERATION_SEED_MODULUS)


EPISODE_ID_NAMESPACE = "rvt-clean-room-generation-identity/v4/source_episode"


def episode_id(role: str, family: str, team_size: int, source_policy: str,
               index: int) -> str:
    """A deterministic function of frozen manifest fields only.

    The layout hash is deliberately NOT part of the id, so the full expected
    universe can be enumerated before the generator runs or any layout is
    compiled. The resolved layout hash is bound separately in the manifest.
    """
    return (f"{EPISODE_ID_NAMESPACE}/{role}/{family}/N{team_size}/"
            f"{source_policy}/episode-{index}")


def enumerate_episode_ids(role: str) -> Iterator[str]:
    """The complete expected source-episode universe for a role, in canonical order."""
    comp = ROLE_COMPOSITION.get(role)
    if comp is None:
        raise CompositionContractError(f"unknown clean-room role: {role}")
    for family in FAMILIES:
        for team_size in TEAM_SIZES:
            for policy in SOURCE_POLICIES:
                for index in range(comp.episodes_per_cell):
                    yield episode_id(role, family, team_size, policy, index)


def replicas_per_candidate(family: str) -> int:
    if family not in FAMILIES:
        raise CompositionContractError(f"unknown scenario family: {family}")
    return 3 if family in REPLICA_FAMILIES_R3 else 1


def verify_role_arithmetic(role: str) -> Mapping[str, int]:
    """Recompute a role's counts and refuse if the grid does not divide exactly."""
    comp = ROLE_COMPOSITION.get(role)
    if comp is None:
        raise CompositionContractError(f"unknown clean-room role: {role}")
    ids = list(enumerate_episode_ids(role))
    if len(ids) != comp.source_episode_count:
        raise CompositionContractError(
            f"{role}: enumerated {len(ids)} ids but the composition says "
            f"{comp.source_episode_count}")
    if len(set(ids)) != len(ids):
        raise CompositionContractError(f"{role}: the enumeration contains duplicates")
    if comp.source_episode_count % comp.layout_count:
        raise CompositionContractError(
            f"{role}: {comp.source_episode_count} episodes do not divide evenly across "
            f"{comp.layout_count} layouts")
    return {"source_episodes": comp.source_episode_count,
            "cells": CELLS,
            "episodes_per_cell": comp.episodes_per_cell,
            "episodes_per_family_team_size_cell": comp.episodes_per_family_team_size_cell,
            "layouts": comp.layout_count,
            "episodes_per_layout": comp.episodes_per_layout}


def all_roles_disjoint() -> bool:
    """Episode ids embed the role, so the six universes are disjoint by construction."""
    seen: set[str] = set()
    for role in ROLE_COMPOSITION:
        ids = set(enumerate_episode_ids(role))
        if seen & ids:
            return False
        seen |= ids
    return True


# The frozen fingerprint of the whole composition. Any later stage that tries to
# resize a role -- MAIN-R after CL-DEV results, MECH-R after MAIN-R, PROTECTED-R
# after a reveal -- is refused here rather than in prose.
def composition_fingerprint() -> str:
    payload = "|".join(
        f"{r}:{c.offset}:{c.episodes_per_cell}:{c.layout_instances_per_family}:"
        f"{generation_seed(r)}"
        for r, c in sorted(ROLE_COMPOSITION.items()))
    payload += "|" + ",".join(FAMILIES) + "|" + ",".join(str(n) for n in TEAM_SIZES)
    payload += "|" + ",".join(SOURCE_POLICIES)
    return hashlib.sha256(payload.encode("ascii")).hexdigest()


def assert_composition_unchanged(role: str, *, episodes_per_cell: int, offset: float,
                                 layout_instances_per_family: int,
                                 generation_seed_value: int) -> None:
    """Refuse any deviation from the frozen composition for a role."""
    comp = ROLE_COMPOSITION.get(role)
    if comp is None:
        raise CompositionContractError(f"unknown clean-room role: {role}")
    frozen = (comp.episodes_per_cell, comp.offset, comp.layout_instances_per_family,
              generation_seed(role))
    proposed = (episodes_per_cell, offset, layout_instances_per_family,
                generation_seed_value)
    if proposed != frozen:
        raise CompositionContractError(
            f"{role} composition is frozen at {frozen}; refusing {proposed}")
