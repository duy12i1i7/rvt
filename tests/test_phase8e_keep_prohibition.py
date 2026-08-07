"""Phase 8E-PC — KEEP must not appear in publication execution.

The phase requires a test proving "no KEEP publication initialization exists".
The protocol artifact declares `initial_topology.keep_status = "prohibited"`,
but no Phase 8E test guarded it, so the declaration could drift from the
compiled records without anything going red.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from rvt_swarm.topology_registry import COMPACT

RESULTS = pathlib.Path("results/rvt_fd24")
SPECS = RESULTS / "layout_execution_specifications"


def protocol() -> dict:
    return json.loads((RESULTS / "executable_scientific_protocol_v1.json").read_text())


def compiled_records():
    for split in ("train", "validation"):
        for p in sorted((SPECS / split).glob("*.json")):
            yield p.name, json.loads(p.read_text())


def test_protocol_declares_keep_prohibited() -> None:
    init = protocol()["initialization_contract"]["initial_topology"]
    assert init["keep_status"] == "prohibited", init


def test_every_compiled_record_initialises_compact_not_keep() -> None:
    records = dict(compiled_records())
    assert records, "no compiled layout records found"
    for name, rec in records.items():
        assert rec["initial_topology_id"] == COMPACT, (name, rec["initial_topology_id"])


def test_compact_is_the_registry_value_not_a_literal() -> None:
    """Guards against the id drifting away from the registry definition."""
    from rvt_swarm import topology_registry
    assert COMPACT == topology_registry.COMPACT
    records = dict(compiled_records())
    assert {r["initial_topology_id"] for r in records.values()} == {COMPACT}


def test_no_compiled_record_names_keep_as_an_executable_topology() -> None:
    for name, rec in compiled_records():
        blob = json.dumps(rec)
        assert '"KEEP"' not in blob, f"{name} names KEEP in an execution field"
