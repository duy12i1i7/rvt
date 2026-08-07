# Phase 8E-HRF — Headroom Unit-of-Analysis Audit (HRF-1)

Read from the frozen artifacts, not inferred from filenames or prior reports.

## Exact frozen wording

`docs/RVT_FD24_SCENARIO_HEADROOM_PROTOCOL.md`, opening line:

> Every layout/team-size cell is assigned by frozen diagnostic policies before
> model training

and later:

> The split manifests report diagnostic category by layout and team size.

## Old artifact schema

The authoritative historical record is the split manifest, not a standalone
headroom file:

| property | train | validation |
|---|---|---|
| file | `results/rvt_fd24/splits/train_layouts.json` | `.../validation_layouts.json` |
| schema | `rvt-layout-split/v1` | same |
| `layout_count` | 20 | 10 |
| record keys | `layout_id`, `family_id`, `geometry`, `geometry_sha256`, `canonical_parameter_tuple_sha256`, `generation_seed_commitment`, **`diagnostic_headroom_by_team_size`** | same |

`diagnostic_headroom_by_team_size` is a list of `[N, category]` pairs covering
`N in {5, 6, 8, 12, 16, 24}`. **N appears in every record.** The unit is
therefore unambiguously the **layout x team-size cell**, exactly as the protocol
states.

## How the historical 20/10 counts were produced

`headroom_category_distribution` in each manifest is a **layout-level summary**:

* train `{COMPACT_ONLY_SUCCESS: 1, LINE_ONLY_SUCCESS: 6, BOTH_SUCCESS: 7, BOTH_FAIL: 2, RECONFIGURATION_REQUIRED: 4}` = 20
* validation `{1, 3, 3, 1, 2}` = 10

Measured directly: **0 of 30 layouts vary in category across N.** Every layout
carries the same category at all six team sizes. The layout-level distribution
is consequently the *trivially-identical projection* of the per-cell assignment,
and it equals the per-cell distribution at N=5, 6, 8, 12, 16 **and** 24 alike.

This is outcome 1/2 of the four candidate explanations: the historical artifact
classified per cell, and the layout summary needed **no aggregation rule**
because the cells never disagreed. There is no inconsistency in the frozen
artifact, and no new aggregation rule has to be chosen. HRF-G1 is satisfied
without invoking the Verdict-A stop condition.

## Authoritative units for this requalification

* **Requalification unit:** layout x team-size cell.
* **H2 count unit:** layout x team-size cell.

The layout-level projection is *no longer* well defined under executable
evaluation: **20 of 30 layouts now vary across N**. Cell-level counts are
therefore reported as authoritative, and no layout-level projection is asserted.
That change is a property of the new evidence, not of the frozen protocol.

## Evaluation domain (HRF-2)

Study A pre-zero-shot train and validation, `N in {5, 6, 8, 12, 16}` — 150 cells
(100 train, 50 validation). N=24 is the sealed Study A zero-shot namespace and
was not accessed. Final-test geometry was not accessed. Study B was not run and
is not mixed in; the frozen headroom protocol defines the diagnostic over the
split manifests, which are Study A train/validation.

## Replica rule (HRF-6)

The frozen protocol says a cell is stable "when deterministic reruns agree, or
when stochastic replicas produce the same category under the predeclared
all-success aggregation". The executable diagnostic path is deterministic given
the frozen seeds — no disturbance stream is active for S0, S1 or S2 — so one
run per policy per cell is used and determinism is checked by rerun. The Target
V4 three-replica rule for F8/F9 belongs to counterfactual recoverability and is
**not** reused here, because the headroom protocol does not say so.
