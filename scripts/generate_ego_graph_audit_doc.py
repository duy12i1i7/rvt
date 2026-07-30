"""Regenerate docs/EGO_GRAPH_FEATURE_AUDIT.md from the code.

The audit document is generated, never hand-edited:
`tests/test_ego_graph_locality.py::test_audit_document_matches_code` fails if
the checked-in table drifts from `ego_graph.audit_markdown()`.

Usage:
    cd /Users/udy/rvt && PYTHONPATH=. .venv/bin/python scripts/generate_ego_graph_audit_doc.py
"""

from __future__ import annotations

import pathlib

from rvt_swarm.decentralized.ego_graph import (
    EDGE_DIM,
    EDGE_LAYOUT,
    FEATURE_DIM,
    REJECTED_GLOBAL_FEATURES,
    audit_markdown,
    feature_audit,
)
from rvt_swarm.decentralized.system_model import PERMITTED_LOCAL_SOURCES

REPO = pathlib.Path(__file__).resolve().parents[1]
OUT = REPO / "docs" / "EGO_GRAPH_FEATURE_AUDIT.md"

TEMPLATE = """# Ego-graph feature audit

Machine-readable source: `rvt_swarm.decentralized.ego_graph.feature_audit()`.
This file is **generated** by `scripts/generate_ego_graph_audit_doc.py`; the
table below is the exact output of `ego_graph.audit_markdown()`, and
`tests/test_ego_graph_locality.py::test_audit_document_matches_code` fails if
the two drift apart. Do not hand-edit the table.

Every row states which columns of `node_x` it owns, which node kinds carry a
non-zero value there, and which entry of
`system_model.PERMITTED_LOCAL_SOURCES` the number comes from. The audit tiles
`[0, {feature_dim})` exactly: no column is unattributed and no two rows claim
the same column
(`tests/test_ego_graph_locality.py::test_every_feature_traces_to_a_permitted_local_source`
asserts both, and additionally checks the zero-block claim on real tensors --
for a node of kind k, every column whose row does not list k is exactly zero).

* `FEATURE_DIM` = {feature_dim}
* `EDGE_DIM` = {edge_dim}
* permitted sources actually used: {used}
* permitted sources deliberately unused by the feature builder: {unused}

## Node feature table

{table}

## Edge attribute table

Edges exist only between the centre and another node, in both directions.

| Columns | Attribute | Justification |
| --- | --- | --- |
{edge_rows}

## What is *not* in the features, and what replaced it

Each row is a quantity that a centralized selector would use and that this
design refuses. `ego_graph.REJECTED_GLOBAL_FEATURES` is the machine-readable
form of this table.

| Rejected feature | Why, and what replaced it |
| --- | --- |
{rejected}

## Two features that are constant by construction

`nb_link_valid` and `obs_valid` are 1.0 on every admitted node under the
nominal admission rule, because a record that fails the rule produces no node
at all. They are kept as explicit columns so that a degraded-link variant --
one that admits a stale record with the flag set to 0.0 instead of dropping it
-- has the identical feature width and can load the same weights. This is
stated rather than hidden: they carry no information in the nominal
configuration, and `test_stale_and_dead_links_produce_no_node` asserts exactly
that.

## Sources that exist in the contract but are not used here

Permitted sources that do not appear in `node_x`: {unused}.
`controller_parameters` belongs to `local_controller`, not to the graph
builder. `self_state` contributes robot i's velocity and the origin of the ego
frame, but robot i's **absolute position is deliberately excluded** even though
it is permitted: leaving it out makes every geometric column
translation-invariant, which is what makes the out-of-range-robot tests
meaningful instead of accidental. Robot IDs are excluded for the analogous
reason -- see `robot_id_as_feature` in the rejected table.
"""


def main() -> None:
    rows = feature_audit()
    used = sorted({s for r in rows for s in r["permitted_source"]})
    unused = sorted(set(PERMITTED_LOCAL_SOURCES) - set(used))

    edge_rows = "\n".join(
        "| `[{}:{}]` | `{}` | {} |".format(a, b, name, just)
        for (a, b), (name, just) in EDGE_LAYOUT.items()
    )
    rejected = "\n".join(
        "| `{}` | {} |".format(name, text)
        for name, text in REJECTED_GLOBAL_FEATURES.items()
    )
    text = TEMPLATE.format(
        feature_dim=FEATURE_DIM,
        edge_dim=EDGE_DIM,
        used=", ".join("`{}`".format(s) for s in used),
        unused=", ".join("`{}`".format(s) for s in unused),
        table=audit_markdown(),
        edge_rows=edge_rows,
        rejected=rejected,
    )
    OUT.write_text(text)
    print("wrote {} ({} chars, {} feature rows)".format(OUT, len(text), len(rows)))


if __name__ == "__main__":
    main()
