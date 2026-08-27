"""No-execution generation call plans.

Every expected clean-room source episode is turned into the exact frozen
OfficialSourceTask the historical producer consumes. Nothing is simulated: this
proves the invocation is constructible from frozen authority alone, with no
unknown argument, no missing argument and no operator-chosen constant.
"""
from __future__ import annotations

import dataclasses
from typing import Mapping, Sequence

from rvt_swarm.cleanroom.generation.identity import CleanRoomSourceEpisodeIdentity
from rvt_swarm.cleanroom.generation.layouts import resolve_layout
from rvt_swarm.cleanroom.generation.ledger import enumerate_role
from rvt_swarm.cleanroom.generation.roles import ROLES, role
from rvt_swarm.cleanroom.generation.seeds import source_episode_seeds
from rvt_swarm.phase8 import scenario as _scenario
from rvt_swarm.phase8.common import sha256_document
from rvt_swarm.phase9g0r.compiler import OfficialSourceTask

REQUIRED_FIELDS = tuple(f.name for f in dataclasses.fields(OfficialSourceTask))


class CallPlanError(ValueError):
    """A call-plan violation that must fail closed."""


def _horizon(role_name: str, family: str) -> float:
    r = role(role_name)
    layout = _scenario._layout(family, r.generator_split_namespace, r.layout_variant_index)
    return float(layout.episode_horizon_seconds)


def call_arguments(identity: CleanRoomSourceEpisodeIdentity) -> Mapping[str, object]:
    """The exact keyword arguments for one frozen OfficialSourceTask."""
    cell = identity.cell
    r = role(identity.role)
    return {
        "job_id": identity.source_episode_id(),
        "dataset_id": cell.dataset_id,
        "study": cell.study,
        "split": cell.split,
        "layout_source_split": r.generator_split_namespace,
        "family": cell.family_id,
        "layout_id": identity.layout_id,
        "layout_sha256": cell.layout_sha256,
        "team_size": cell.team_size,
        "source_class": identity.source_class,
        "episode_index": identity.episode_index,
        "horizon_seconds": _horizon(identity.role, cell.family_id),
        "seeds": dict(source_episode_seeds(identity)),
    }


def build_call(identity: CleanRoomSourceEpisodeIdentity) -> OfficialSourceTask:
    args = call_arguments(identity)
    unknown = sorted(set(args) - set(REQUIRED_FIELDS))
    missing = sorted(set(REQUIRED_FIELDS) - set(args))
    if unknown:
        raise CallPlanError(f"unknown arguments for OfficialSourceTask: {unknown}")
    if missing:
        raise CallPlanError(f"missing required arguments for OfficialSourceTask: {missing}")
    return OfficialSourceTask(**args)


def role_call_plan(role_name: str) -> Sequence[Mapping[str, object]]:
    return [call_arguments(i) for i in enumerate_role(role_name)]


def validate_all() -> Mapping[str, object]:
    """Construct every clean-room call. No simulator is invoked."""
    per_role, unknown, missing, calls = {}, 0, 0, 0
    payload = []
    for name in ROLES:
        n = 0
        for ident in enumerate_role(name):
            args = call_arguments(ident)
            unknown += len(set(args) - set(REQUIRED_FIELDS))
            missing += len(set(REQUIRED_FIELDS) - set(args))
            task = OfficialSourceTask(**args)          # constructs or raises
            payload.append([task.job_id, task.dataset_id, task.study, task.split,
                            task.family, task.layout_sha256, task.team_size,
                            task.source_class, task.episode_index,
                            sorted(dict(task.seeds).items())])
            n += 1; calls += 1
        per_role[name] = n
    return {"calls": calls, "per_role": per_role, "unknown_arguments": unknown,
            "missing_required_arguments": missing,
            "required_fields": list(REQUIRED_FIELDS),
            "call_plan_root": sha256_document(payload)}
