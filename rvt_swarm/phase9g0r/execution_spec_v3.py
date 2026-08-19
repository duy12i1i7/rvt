"""Additive V3 layout execution-specification compilation.

The official V3 layout domain was frozen as *geometry* -- the registry pins a
`geometry_sha256`, a parameter-tuple hash, a horizon and a seed commitment for
every layout -- but the compiled *executable binding* was never produced, so
`build_source_session` could not bind an official V3 episode. This module
supplies exactly that missing compilation and nothing else.

Three properties make it safe:

* **Nothing new is invented.** `phase8e.compiler.compile_layout_record` is a
  pure function of (frozen layout record, split, frozen executable protocol);
  it emits `category_d_count: 0` and `build_binding` refuses any specification
  that does not. The layout record itself comes from the frozen generator
  `phase8.scenario._layout`, re-derived and then checked against the registry
  hashes rather than trusted.
* **Historical enumeration is untouched.** `_SPLIT_VARIANTS` still reads
  `{train: (0, 1), validation: (0,)}`; it is only the *enumeration* helper.
  `_layout` itself takes the variant index as an argument, so the V3 offsets
  0.22, 0.54 and 0.65 are reachable without changing a frozen constant. The
  input domain here is the frozen V3 registry, never a split enumeration and
  never a free-form offset.
* **Split never comes from a string.** `validation-f1-01` is a V3 *TRAIN*
  layout. Its V3 split comes from registry membership; the directory it is
  written to is its *geometry namespace*, which is a different thing and is
  read from the registry's `generator_split_namespace` field.

On that last point, one deviation from the phase text is worth stating plainly:
the phase asked that a V3 TRAIN layout resolve to a "TRAIN execution-spec
namespace". The frozen runtime loader hard-requires
`split in ("train", "validation")` and `source_layout.split == split`, and it
builds the path from that same value, so a `v3_train` directory would require
editing frozen V1/V2 runtime code that this phase equally forbids touching. The
directory therefore stays the geometry namespace, and the V3 *lookup* is done
through `load_v3_execution_specification`, which resolves by registry
membership and verifies the V3 split explicitly.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

from ..phase8.common import attach_canonical_hash, sha256_document
from ..phase8.scenario import _layout
from ..phase8.splits import layout_record
from ..phase8e.compiler import compile_layout_record
from ..phase8e.protocol import LAYOUT_EXECUTION_SPECIFICATION_SCHEMA_VERSION
from .compiler_v3 import (
    FORBIDDEN_OFFSETS, RESERVE_OFFSET, V3_TRAIN, V3_VALIDATION,
    V3CompilerError, load_v3_layout_registry,
)
from .contracts_v3 import LAYOUT_SPLIT_REGISTRY_V2_SHA256

V3_EXECUTION_SPEC_REGISTRY_SCHEMA_VERSION = (
    "rvt-v3-layout-execution-spec-registry/v1")
V3_EXECUTION_SPEC_REGISTRY_NAME = "V3_LAYOUT_EXECUTION_SPEC_REGISTRY_V1"

#: The registry groups that carry official V3 membership. RESERVE is excluded
#: on purpose -- offset 0.33 is UNUSED_RESERVE and must never be compiled into
#: the official domain "for extra diversity".
OFFICIAL_GROUPS: Mapping[str, str] = {"TRAIN": V3_TRAIN, "VALIDATION": V3_VALIDATION}

#: Geometry namespaces the frozen runtime loader will accept.
GEOMETRY_NAMESPACES: Tuple[str, ...] = ("train", "validation")


class V3ExecutionSpecError(V3CompilerError):
    """An execution-specification failure that must fail closed."""


def _protocol(root: Path) -> Mapping[str, Any]:
    """The frozen executable protocol the historical compiler was built for."""
    path = Path(root) / "results/rvt_fd24/executable_scientific_protocol_v1.json"
    if not path.exists():
        raise V3ExecutionSpecError("frozen executable protocol is missing")
    return json.loads(path.read_text(encoding="ascii"))


def frozen_v3_layout_entries(root: Path) -> Tuple[Mapping[str, Any], ...]:
    """The thirty official V3 layouts, from registry authority only."""
    registry = load_v3_layout_registry(root)
    if registry["v3_layout_split_registry_v2_sha256"] != LAYOUT_SPLIT_REGISTRY_V2_SHA256:
        raise V3ExecutionSpecError("V3 layout registry root drifted")
    entries = []
    for group, v3_split in OFFICIAL_GROUPS.items():
        members = set(registry["assignment"][group]["layout_ids"])
        for record in registry["layout_records"][group]:
            layout_id = str(record["layout_id"])
            if layout_id not in members:
                raise V3ExecutionSpecError(
                    f"{layout_id} is not a declared member of {group}")
            offset = float(record["offset"])
            if offset == RESERVE_OFFSET:
                raise V3ExecutionSpecError(
                    "the 0.33 reserve offset may not enter the official domain")
            if offset in FORBIDDEN_OFFSETS:
                raise V3ExecutionSpecError(f"offset {offset} is forbidden")
            namespace = str(record["generator_split_namespace"])
            if namespace not in GEOMETRY_NAMESPACES:
                raise V3ExecutionSpecError(
                    f"unknown geometry namespace {namespace!r}")
            entries.append({
                "layout_id": layout_id,
                "family": str(record["family"]),
                "v3_split": v3_split,
                "registry_group": group,
                "geometry_namespace": namespace,
                "variant_index": int(record["variant_index"]),
                "offset": offset,
                "geometry_sha256": str(record["geometry_sha256"]),
                "parameter_tuple_sha256": str(record["parameter_tuple_sha256"]),
                "layout_sha256": str(record["layout_sha256"]),
                "episode_horizon_seconds": float(record["episode_horizon_seconds"]),
                "generation_seed_commitment":
                    str(record["generation_seed_commitment"]),
            })
    if len(entries) != 30:
        raise V3ExecutionSpecError(
            f"the official V3 layout domain resolved {len(entries)} layouts, not 30")
    return tuple(sorted(entries, key=lambda item: item["layout_id"]))


def reconstruct_layout_record(entry: Mapping[str, Any]) -> Mapping[str, Any]:
    """Re-derive the frozen layout, then check it against the registry.

    The generator is called with the registry's own (family, namespace,
    variant) triple. Every hash it produces is compared to the frozen value; a
    mismatch is an error, never something to reconcile by rewriting a hash.
    """
    layout = _layout(entry["family"], entry["geometry_namespace"],
                     entry["variant_index"])
    if layout.layout_id != entry["layout_id"]:
        raise V3ExecutionSpecError(
            f"regenerated layout id {layout.layout_id!r} != frozen "
            f"{entry['layout_id']!r}")
    if layout.geometry_sha256() != entry["geometry_sha256"]:
        raise V3ExecutionSpecError(
            f"{entry['layout_id']}: regenerated geometry hash does not match the "
            "frozen registry value")
    if layout.parameter_tuple_sha256() != entry["parameter_tuple_sha256"]:
        raise V3ExecutionSpecError(
            f"{entry['layout_id']}: parameter-tuple hash does not match")
    if layout.generation_seed_commitment != entry["generation_seed_commitment"]:
        raise V3ExecutionSpecError(
            f"{entry['layout_id']}: seed commitment does not match")
    if float(layout.episode_horizon_seconds) != entry["episode_horizon_seconds"]:
        raise V3ExecutionSpecError(
            f"{entry['layout_id']}: horizon does not match")
    return layout_record(layout)


def compile_v3_execution_specification(
    root: Path, entry: Mapping[str, Any],
) -> Mapping[str, Any]:
    """One specification, compiled by the frozen Phase-8E compiler."""
    record = reconstruct_layout_record(entry)
    specification = compile_layout_record(
        record, entry["geometry_namespace"], _protocol(root))
    if specification["schema_version"] != LAYOUT_EXECUTION_SPECIFICATION_SCHEMA_VERSION:
        raise V3ExecutionSpecError("unexpected execution-specification schema")
    if int(specification["category_d_count"]) != 0:
        raise V3ExecutionSpecError(
            "the compiled specification declares an unbound scientific value")
    source = specification["source_layout"]
    if source["geometry_sha256"] != entry["geometry_sha256"]:
        raise V3ExecutionSpecError("compiled specification lost its geometry hash")
    if float(specification["episode_horizon_seconds"]) != entry["episode_horizon_seconds"]:
        raise V3ExecutionSpecError("compiled specification lost its horizon")
    return specification


def specification_path(root: Path, entry: Mapping[str, Any]) -> Path:
    """Where the frozen runtime loader will look for this specification."""
    return (Path(root) / "results/rvt_fd24/layout_execution_specifications"
            / entry["geometry_namespace"] / f"{entry['layout_id']}.json")


def compile_all_v3_execution_specifications(
    root: Path, *, write: bool = False,
) -> Mapping[str, Any]:
    """Compile all thirty. Never overwrites an existing specification."""
    entries = frozen_v3_layout_entries(root)
    compiled = []
    for entry in entries:
        path = specification_path(root, entry)
        specification = compile_v3_execution_specification(root, entry)
        existing = None
        if path.exists():
            existing = json.loads(path.read_text(encoding="ascii"))
            if existing["layout_execution_specification_sha256"] != specification[
                    "layout_execution_specification_sha256"]:
                raise V3ExecutionSpecError(
                    f"refusing to overwrite a different specification at {path}")
        elif write:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(specification, indent=1, sort_keys=True) + "\n",
                encoding="ascii")
        compiled.append({
            **{key: entry[key] for key in (
                "layout_id", "family", "v3_split", "registry_group",
                "geometry_namespace", "variant_index", "offset",
                "geometry_sha256", "parameter_tuple_sha256", "layout_sha256",
                "episode_horizon_seconds", "generation_seed_commitment")},
            "execution_spec_sha256":
                specification["layout_execution_specification_sha256"],
            "path": str(path.relative_to(Path(root))),
            "pre_existing": existing is not None,
        })
    return {"entries": tuple(compiled), "written": bool(write)}


def v3_execution_spec_registry(root: Path) -> Mapping[str, Any]:
    """V3_LAYOUT_EXECUTION_SPEC_REGISTRY_V1, canonically hashed."""
    compiled = compile_all_v3_execution_specifications(root)["entries"]
    layouts = [
        {
            "study": "study_a_zero_shot",
            "v3_split": item["v3_split"],
            "geometry_namespace": item["geometry_namespace"],
            "family": item["family"],
            "layout_id": item["layout_id"],
            "layout_sha256": item["layout_sha256"],
            "geometry_sha256": item["geometry_sha256"],
            "parameter_tuple_sha256": item["parameter_tuple_sha256"],
            "execution_spec_sha256": item["execution_spec_sha256"],
            "episode_horizon_seconds": item["episode_horizon_seconds"],
            "variant_index": item["variant_index"],
            "offset": item["offset"],
        }
        for item in compiled
    ]
    body = {
        "schema_version": V3_EXECUTION_SPEC_REGISTRY_SCHEMA_VERSION,
        "name": V3_EXECUTION_SPEC_REGISTRY_NAME,
        "additive": True,
        "compiler_authority": {
            "execution_spec_compiler":
                "rvt_swarm/phase8e/compiler.py::compile_layout_record",
            "layout_generator": "rvt_swarm/phase8/scenario.py::_layout",
            "layout_record_builder": "rvt_swarm/phase8/splits.py::layout_record",
            "v3_enumeration": "rvt_swarm/phase9g0r/execution_spec_v3.py",
            "historical_split_enumeration_used": False,
            "split_variants_modified": False,
        },
        "v3_layout_split_registry_v2_sha256": LAYOUT_SPLIT_REGISTRY_V2_SHA256,
        "layout_execution_specification_schema_version":
            LAYOUT_EXECUTION_SPECIFICATION_SCHEMA_VERSION,
        "layout_count": len(layouts),
        "train_layouts": sum(1 for item in layouts if item["v3_split"] == V3_TRAIN),
        "validation_layouts": sum(
            1 for item in layouts if item["v3_split"] == V3_VALIDATION),
        "reserve_layouts_compiled": 0,
        "layouts": layouts,
    }
    return attach_canonical_hash(body, "v3_layout_execution_spec_registry_v1_sha256")


# ---------------------------------------------------------------------------
# V3 lookup -- registry authority, never a layout-id string
# ---------------------------------------------------------------------------
def load_v3_execution_specification(
    root: Path, layout_id: str, *, expected_v3_split: Optional[str] = None,
) -> Mapping[str, Any]:
    """Resolve one V3 specification through registry membership.

    Fails closed on a missing file, a hash mismatch, a geometry mismatch, a
    split mismatch, a reserve layout or an unknown layout.
    """
    entries = {item["layout_id"]: item for item in frozen_v3_layout_entries(root)}
    entry = entries.get(layout_id)
    if entry is None:
        raise V3ExecutionSpecError(
            f"{layout_id!r} is not an official V3 layout; reserve and unknown "
            "layouts have no official execution specification")
    if expected_v3_split is not None and entry["v3_split"] != expected_v3_split:
        raise V3ExecutionSpecError(
            f"{layout_id!r} belongs to {entry['v3_split']}, not "
            f"{expected_v3_split!r}")
    path = specification_path(root, entry)
    if not path.exists():
        raise V3ExecutionSpecError(f"no compiled execution specification at {path}")
    specification = json.loads(path.read_text(encoding="ascii"))
    from ..phase8.common import verify_canonical_hash
    if not verify_canonical_hash(
            specification, "layout_execution_specification_sha256"):
        raise V3ExecutionSpecError(
            f"execution specification hash mismatch at {path}")
    source = specification.get("source_layout")
    if not isinstance(source, Mapping):
        raise V3ExecutionSpecError(f"specification lacks source identity at {path}")
    if str(source.get("layout_id")) != layout_id:
        raise V3ExecutionSpecError(f"specification identity mismatch at {path}")
    if str(source.get("split")) != entry["geometry_namespace"]:
        raise V3ExecutionSpecError(f"specification namespace mismatch at {path}")
    if str(source.get("geometry_sha256")) != entry["geometry_sha256"]:
        raise V3ExecutionSpecError(
            f"specification geometry hash does not match the frozen registry "
            f"at {path}")
    if float(specification["episode_horizon_seconds"]) != entry["episode_horizon_seconds"]:
        raise V3ExecutionSpecError(f"specification horizon mismatch at {path}")
    return specification


def v3_split_of_official_layout(root: Path, layout_id: str) -> str:
    """The V3 dataset split of a layout, from membership only."""
    entries = {item["layout_id"]: item for item in frozen_v3_layout_entries(root)}
    if layout_id not in entries:
        raise V3ExecutionSpecError(f"{layout_id!r} is not an official V3 layout")
    return entries[layout_id]["v3_split"]


def assert_execution_spec_registry_root(root: Path, expected: str) -> str:
    """Fail closed on a wrong execution-spec registry root."""
    actual = v3_execution_spec_registry(root)[
        "v3_layout_execution_spec_registry_v1_sha256"]
    if actual != expected:
        raise V3ExecutionSpecError(
            f"V3 execution-spec registry root is {actual[:16]}..., expected "
            f"{str(expected)[:16]}...")
    return actual
