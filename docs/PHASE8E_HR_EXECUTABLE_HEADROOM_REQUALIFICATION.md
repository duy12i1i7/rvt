# Phase 8E-HR — Executable Headroom Requalification

Owner decision 2: executable headroom overrides historical diagnostic
classification. Categories and their frozen definitions are unchanged; only the
evidence is recomputed, using the real controller, real safety, real readiness,
real mission staging, the frozen role-space profile, real Metric V3 dwell and
the real Target V4 evaluator. No learned model, no historical shortcut, no
dataset row.

**The transition-motion ambiguity and the historical headroom inconsistency were
both discovered before any scientific dataset generation or model training.**

## Coverage limitation, stated first

The frozen unit of analysis is the **layout/team-size cell**. This
requalification covers the **N=6 slice**: 30 cells of the 180-cell grid. The
remaining 150 cells are not yet requalified. Every count below is therefore an
N=6 count, and the comparison against the historical layout-level counts is
like-for-like in cardinality (20 train, 10 validation) but not in unit.

## Results, N=6

| category | train old | train new | validation old | validation new |
|---|---:|---:|---:|---:|
| COMPACT_ONLY_SUCCESS | 1 | **0** | 1 | **0** |
| LINE_ONLY_SUCCESS | 6 | 6 | 3 | 3 |
| BOTH_SUCCESS | 7 | **6** | 3 | 3 |
| BOTH_FAIL | 2 | **6** | 1 | **3** |
| RECONFIGURATION_REQUIRED | 4 | **2** | 2 | **1** |

`RECONFIGURATION_REQUIRED` remains **nonzero in both splits**, so HR-G4 passes
and H2 stays falsifiable against both fixed baselines.

## Changed classifications

| family | cells | old (declared/historical) | new | reason |
|---|---|---|---|---|
| F5 | `train-f5-00`, `train-f5-01`, `validation-f5-00` | RECONFIGURATION_REQUIRED | **LINE_ONLY_SUCCESS** | fixed LINE completes the task, which the frozen definition excludes |
| F3, F4, F6 | 7 cells | mixed | **BOTH_FAIL** | neither fixed policy nor the oracle completes at N=6 |
| F8 | 3 cells | RECONFIGURATION_REQUIRED (declared) | **BOTH_SUCCESS** | both fixed policies complete |
| F9 | `train-f9-00`, `train-f9-01`, `validation-f9-00` | — | **RECONFIGURATION_REQUIRED** | both fixed fail; the oracle completes |

The earlier headroom was computed before the S2 topology-override failure, the
dead Phase 7 lifecycle, asserted readiness, immediate topology switch, the
missing Metric V3 dwell clock and the event-timing defect were found. Recomputing
with all ten integration defects fixed moves cells in both directions; none is
retained by name or history.

## H2 viability — Severity 2 limitation

`RECONFIGURATION_REQUIRED` now sits in **exactly one family (F9)**: 2 train
cells and 1 validation cell. H2 remains falsifiable, but the switching headroom
that supports it is concentrated rather than broad, and it is carried by the
dynamic-obstacle family rather than by the sequential-bottleneck family that was
designed for it. This is quantified rather than smoothed over.

## F5 wording correction (additive)

`RVT_FD24_SCENARIO_FAMILY_CONTRACT.md` line 14 declares, historically:

| F5 | SEQUENTIAL_BOTTLENECKS | RECONFIGURATION_REQUIRED | ... | repeated C->L->C | ... |

That artifact is **not edited**. The additive correction, supported by the
requalified results:

> **F5 — SEQUENTIAL_BOTTLENECKS: sequential bottlenecks exposing repeated
> topology-reconfiguration opportunities.**

The stronger claim — that repeated online reconfiguration is *required* — is not
supported: fixed LINE completes every requalified F5 cell, so no F5 cell can
carry `RECONFIGURATION_REQUIRED` under the frozen definition. The declared
`repeated C->L->C` pattern remains an available opportunity, not a necessity.

## Provenance

`results/rvt_fd24/headroom_requalification_v2.json`, schema
`rvt-headroom-requalification/v2`, canonical hash
`2229e7d62a12c3756b03c670db7aa342acc40cc2bbbc1c122828cf2be107894a`. Historical
headroom artifacts are untouched.

---

# Full executable requalification (Phase 8E-HR-FULL)

Supersedes the N=6 slice above. The v2 artifact is preserved; the full result is
`results/rvt_fd24/headroom_requalification_v3.json`, schema
`rvt-headroom-requalification/v3`, canonical hash
`fd300e0b11c2ef8421058ecb2cb005fb6ed5927ab37ec70a81b9a799d747ebf7`.

**150 of 150 Study A train/validation cells evaluated** (30 layouts x N in
{5,6,8,12,16}), 450 episodes, zero executor exceptions. N=24 sealed and
final-test geometry were not accessed.

## Authoritative cell-level counts

| category | train (100) | validation (50) |
|---|---:|---:|
| BOTH_SUCCESS | 29 | 19 |
| LINE_ONLY_SUCCESS | 28 | 10 |
| BOTH_FAIL | 25 | 11 |
| RECONFIGURATION_REQUIRED | **8** | **4** |
| INVALID_OR_AMBIGUOUS | 10 | 5 |
| COMPACT_ONLY_SUCCESS | 0 | 1 |

**104 of 150 cells changed category.** The layout-level projection used by the
historical artifact is no longer well defined: 20 of 30 layouts now vary across
N, where historically none did.

## H2

`RECONFIGURATION_REQUIRED` is nonzero in both splits, so H2 remains falsifiable
against both fixed baselines. Concentration is **class B**: one family (F9)
across four team sizes (5, 6, 8, 12). No other family provides switching
headroom at any N. This is a Severity 2 concentration and is recorded as such
rather than smoothed over.

## F5 across scale

The N=6 finding generalises. Across all 15 F5 cells, **no cell is
RECONFIGURATION_REQUIRED at any N**: 12 are LINE_ONLY_SUCCESS and 3 are
BOTH_SUCCESS. Fixed LINE completes every F5 cell. The additive wording
correction stands unchanged and is not strengthened.

## INVALID_OR_AMBIGUOUS — a newly exposed binding gap

All 15 invalid cells have the same root cause: **S2 (ALWAYS LINE) raises
`INITIALIZATION_INVALID`**. The frozen compiler validated the **COMPACT**
initial state only (`initial_topology_id = 5`); S2's forced LINE start has no
compiled nominal-validity record at any N. At larger N the LINE longitudinal
span (6.3 m at N=8, 13.5 m at N=16) makes that start pose invalid against the
compiled geometry.

Twelve of the fifteen cells carry `binding_validity = RUNTIME_BINDING_VALID`,
which refers to the COMPACT start and therefore does not contradict the compiled
record — it simply does not cover the LINE start that the headroom protocol
requires as a diagnostic policy.

Per HRF-14 this is **reported, not patched**: running additional team sizes
exposed a runtime binding gap, so the sweep stops here rather than fixing it
mid-flight.
