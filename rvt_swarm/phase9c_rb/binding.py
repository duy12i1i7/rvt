"""Authoritative scenario-to-runtime binding schema and adapter (RB-1, RB-2).

`ScenarioRuntimeBinding` is the single object the publication executor consumes.
Building one makes **no scientific choices**: it copies already-compiled values
out of a layout execution specification and cross-checks them against the frozen
protocol. If a required value were missing the adapter raises rather than
substituting a default -- that is the rule the previous blocked phase stopped
on, and it is enforced here instead of being restated.

Legacy interface note (RB-2). `ScenarioLayout.start_center_meters` is an
explicit approved Phase 8 scientific field and is used, via the compiled
`mission_frame.initial_topology_origin_meters`. The forbidden thing is the
*legacy environment* `start_center` attribute on the historical simulator, which
this package never touches. `tests/test_phase9c_no_legacy_environment_binding.py`
discriminates the two rather than grepping for a substring that matches both.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Mapping, Optional, Sequence, Tuple

from ..phase8.common import canonical_json_bytes
from ..runtime_configuration import DEFAULT_RUNTIME_CONFIG, RuntimeConfig
from ..topology_registry import COMPACT, LINE
from . import SCHEMA_VERSION

LAYOUT_EXECUTION_SPEC_SCHEMA = "rvt-layout-execution-specification/v1"
EXECUTABLE_PROTOCOL_SCHEMA = "rvt-executable-scientific-protocol/v1"
ADMITTED_INITIAL_TOPOLOGIES: Tuple[int, ...] = (COMPACT,)
ADMITTED_CANDIDATES: Tuple[int, ...] = (COMPACT, LINE)

QUALIFIED_TEAM_SIZES: Tuple[int, ...] = (5, 6, 8, 12, 16, 24)


class BindingError(ValueError):
    """A required executable value is absent, malformed or contradictory."""


def canonical_sha256(document: object) -> str:
    return hashlib.sha256(canonical_json_bytes(document)).hexdigest()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@dataclass(frozen=True)
class ScenarioRuntimeBinding:
    """Immutable executable description of one (layout, team size, policy) cell."""

    schema_version: str
    executable_protocol_hash: str
    layout_execution_spec_hash: str
    layout_hash: str
    layout_id: str
    split: str
    family: str
    team_size: int
    source_policy: str
    mission_frame: Mapping[str, object]
    initialization: Mapping[str, object]
    goal_contract: Mapping[str, object]
    static_world_contract: Mapping[str, object]
    dynamic_obstacle_contract: Mapping[str, object]
    communication_contract: Mapping[str, object]
    disturbance_contract: Mapping[str, object]
    horizon_contract: Mapping[str, object]
    target_v4_contract: Mapping[str, object]
    config_hashes: Mapping[str, str]
    validity: str

    def as_document(self) -> Dict[str, object]:
        return json.loads(json.dumps(asdict(self)))

    def binding_sha256(self) -> str:
        return canonical_sha256(self.as_document())

    @property
    def horizon_seconds(self) -> float:
        return float(self.horizon_contract["episode_horizon_seconds"])

    @property
    def nominal_positions(self) -> Tuple[Tuple[float, float], ...]:
        return tuple((float(p[0]), float(p[1]))
                     for p in self.initialization["nominal_positions_meters"])  # type: ignore[index]

    @property
    def role_ids(self) -> Tuple[str, ...]:
        return tuple(str(r) for r in self.initialization["role_ids"])           # type: ignore[index]


def load_execution_specification(root: Path, split: str, layout_id: str) -> Dict[str, object]:
    if split not in ("train", "validation"):
        raise BindingError(
            f"split {split!r} is not runtime-accessible; final-test geometry is gated")
    path = root / "layout_execution_specifications" / split / f"{layout_id}.json"
    if not path.exists():
        raise BindingError(f"no compiled execution specification at {path}")
    return json.loads(path.read_text())


def build_binding(specification: Mapping[str, object], *, team_size: int,
                  source_policy: str, protocol: Mapping[str, object],
                  target_contract: Mapping[str, object],
                  source_policy_contracts: Mapping[str, object],
                  runtime_config: RuntimeConfig = DEFAULT_RUNTIME_CONFIG,
                  ) -> ScenarioRuntimeBinding:
    """Map one compiled specification into a runtime binding. Verifies RB-2."""
    if str(specification.get("schema_version")) != LAYOUT_EXECUTION_SPEC_SCHEMA:
        raise BindingError("unexpected layout execution specification schema")
    if str(specification.get("validity")) != "COMPILED_SPECIFICATION":
        raise BindingError(f"specification validity {specification.get('validity')!r}")
    if int(specification.get("category_d_count", -1)) != 0:
        raise BindingError("specification still declares unresolved Category D values")
    if team_size not in QUALIFIED_TEAM_SIZES:
        raise BindingError(f"team size {team_size} is not mechanically qualified")

    declared_policies = tuple(str(p) for p in specification["source_policy_ids"])  # type: ignore[index]
    if source_policy not in declared_policies:
        raise BindingError(f"source policy {source_policy!r} not declared for this layout")
    if source_policy not in source_policy_contracts["policies"]:                  # type: ignore[index]
        raise BindingError(f"source policy {source_policy!r} has no frozen contract")

    initial_topology = int(specification["initial_topology_id"])
    if initial_topology not in ADMITTED_INITIAL_TOPOLOGIES:
        raise BindingError(
            f"initial topology {initial_topology} is not admitted for publication execution")

    if str(specification["executable_protocol_sha256"]) != str(protocol["protocol_hash"]):
        raise BindingError("specification was compiled against a different executable protocol")
    if str(specification["target_v4_contract_sha256"]) != str(
            target_contract["target_v4_execution_contract_sha256"]):
        raise BindingError("specification was compiled against a different Target V4 contract")

    initialization = dict(specification["initialization_by_team_size"])          # type: ignore[arg-type]
    if str(team_size) not in initialization:
        raise BindingError(f"no compiled initialization for N={team_size}")
    per_team = dict(initialization[str(team_size)])

    nominal_validity = dict(specification["nominal_initial_validity_by_team_size"])  # type: ignore[arg-type]
    validity_entry = dict(nominal_validity[str(team_size)])

    source = dict(specification["source_layout"])                                # type: ignore[arg-type]
    mission_frame = dict(specification["mission_frame"])                         # type: ignore[arg-type]

    static_contract = {
        "world_bounds_meters": specification["world_bounds_meters"],
        "static_obstacles": specification["static_obstacles"],
        "passages": specification["passages"],
        "bypass": specification["bypass"],
        "nominal_passage_width_meters": specification["nominal_passage_width_meters"],
        "centerline": specification["centerline"],
        "collision_inflation": protocol["static_obstacle_contract"]["collision_inflation"],   # type: ignore[index]
        "sensor_conversion": protocol["static_obstacle_contract"]["sensor_conversion"],       # type: ignore[index]
    }

    return ScenarioRuntimeBinding(
        schema_version=SCHEMA_VERSION,
        executable_protocol_hash=str(protocol["protocol_hash"]),
        layout_execution_spec_hash=str(specification["layout_execution_specification_sha256"]),
        layout_hash=str(source["geometry_sha256"]),
        layout_id=str(source["layout_id"]),
        split=str(source["split"]),
        family=str(source["family_id"]),
        team_size=int(team_size),
        source_policy=str(source_policy),
        mission_frame=mission_frame,
        initialization={
            **per_team,
            "initial_topology_id": initial_topology,
            "nominal_validity": validity_entry,
            "contract": protocol["initialization_contract"],
        },
        goal_contract=dict(specification["goal_contract"]),                      # type: ignore[arg-type]
        static_world_contract=static_contract,
        dynamic_obstacle_contract={
            "dynamic_obstacles": specification["dynamic_obstacles"],
            "contract": protocol["dynamic_obstacle_contract"],
        },
        communication_contract=dict(specification["communication"]),             # type: ignore[arg-type]
        disturbance_contract=dict(protocol["disturbance_contract"]),             # type: ignore[arg-type]
        horizon_contract={
            "episode_horizon_seconds": float(specification["episode_horizon_seconds"]),
            "control_period_seconds": float(runtime_config.physical.control_period_seconds),
            "timeout": protocol["simulator_semantics"]["timeout"],               # type: ignore[index]
        },
        target_v4_contract={
            "schema_version": str(target_contract["schema_version"]),
            "sha256": str(target_contract["target_v4_execution_contract_sha256"]),
        },
        config_hashes={
            "runtime_configuration_sha256": str(per_team["runtime_configuration_sha256"]),
            "executable_protocol_sha256": str(protocol["protocol_hash"]),
            "source_policy_contract_sha256": str(
                source_policy_contracts["source_policy_contract_sha256"]),
            "target_v4_execution_contract_sha256": str(
                target_contract["target_v4_execution_contract_sha256"]),
            "phase8_protocol_sha256": str(protocol["phase8_protocol_hash"]),
        },
        validity="RUNTIME_BINDING_VALID" if validity_entry["valid"]
                 else "NOMINAL_INITIAL_STATE_INVALID",
    )
