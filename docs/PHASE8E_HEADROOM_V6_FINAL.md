# Phase 8E-HR-V6 — Final Executable Headroom Requalification

**Status: CANDIDATE_AUTHORITATIVE.** Authority is conditional on clean detached
reproduction, which has **not** been run.

Execution-runtime source commit: `990accb0e240a9bb03243a2cd064b36c4ab5605a`
(the PCA-complete tree). Artifact hash:
`d044d6b99d7a2bbb83565b121d188a35e335bfd856e3eb0e885823ca1a6742ef`.

## Provenance

Defects 9-13 and the S2 mechanical ambiguity were all resolved **before** any
scientific dataset generation, and the protocol-adapter conformance audit
(PCA-8/15/16/18) completed **before** this sweep. v2, v3, v4 and v5 remain
unchanged as historical/provisional artifacts; v5 keeps `PROVISIONAL_PRE_D12`.
v6 is the first candidate authoritative executable headroom artifact.

## Integrity (V6-22)

150 cells, 100 train, 50 validation, 450 policy executions, 0 errors, 0
duplicate keys, `N in {5,6,8,12,16}`, no N=24, no final test.

## Authoritative counts

| category | train (100) | validation (50) |
|---|---:|---:|
| BOTH_FAIL | 48 | 20 |
| BOTH_SUCCESS | 16 | 13 |
| LINE_ONLY_SUCCESS | 16 | 7 |
| COMPACT_ONLY_SUCCESS | 13 | 7 |
| **RECONFIGURATION_REQUIRED** | **5** | **2** |
| INVALID_OR_AMBIGUOUS | 2 | 1 |

## A measurement defect I caught and corrected

The sweep initially recorded switching epoch count as
`mechanical_transition_epoch_count`. That counter increments **only** for S2's
forced initialization, so it is structurally 0 for the switching diagnostic. It
reported "all 7 RECONFIGURATION_REQUIRED cells used 0 switching epochs", which
is an artefact, not a result.

The authoritative field is `completion_agreements` — distributed lifecycle
completions actually reached. Recomputed:

| RECONF cells | completed switching epochs |
|---:|---|
| 6 | **2** |
| 1 | 0 |

This changes the scientific reading materially, so it is recorded rather than
quietly fixed.

## Headroom and attribution (V6-12)

`RECONFIGURATION_REQUIRED`: **5 train, 2 validation** — the frozen hard gate
passes. By family: F9 = 6, F5 = 1. By N: N=8 -> 4, N=12 -> 3.

Corrected attribution, using both the S2 failure mode **and** the switching
mechanism:

| attribution | count |
|---|---:|
| MIXED | 6 |
| INITIAL_CONVERSION_DRIVEN | 1 |
| LATER_TASK_DRIVEN | 0 |

The six F9 cells are MIXED because both effects are demonstrably material: fixed
LINE fails its forced initial conversion, **and** the switching diagnostic
succeeds by completing two during-task epochs (`mode_epoch_count = 2`, final
topology COMPACT — a genuine COMPACT -> LINE -> COMPACT cycle). That is not the
initial-admissibility artefact the provisional v5 suggested.

Across all 63 successful switching cells: 36 completed 0 epochs (topology
retention), 18 completed 1, 9 completed 2.

## H2 (V6-14)

Exact wording, `docs/RVT_FD24_RESEARCH_QUESTIONS_AND_HYPOTHESES.md:25`:

> **H2.** Online COMPACT/LINE reconfiguration improves episode task success by at
> least 0.10 absolute over each fixed topology in predeclared families with
> genuine topology headroom.

**H2 requires LEVEL A** — "over each fixed topology". It makes no during-task
(Level B) or repeated-reconfiguration (Level C) claim.

**v6 supports LEVEL A**, and additionally provides Level C evidence in 6 of 7
headroom cells (two completed during-task epochs each).

The frozen hard gate — `RECONFIGURATION_REQUIRED > 0` in both train and
validation at cell level — **passes** (5 and 2).

## F5

15 cells: LINE_ONLY_SUCCESS 6, BOTH_FAIL 4, BOTH_SUCCESS 3, COMPACT_ONLY 1,
RECONFIGURATION_REQUIRED 1. The conservative additive wording — "sequential
bottlenecks exposing repeated topology-reconfiguration opportunities" — is
retained. The historical "requiring repeated C->L->C" phrasing is **not**
restored: only one F5 cell carries switching headroom, and that cell's switching
success completed zero transition epochs.

## F9

15 cells: RECONFIGURATION_REQUIRED 6, LINE_ONLY_SUCCESS 6, BOTH_FAIL 3. F9 still
dominates headroom (6 of 7 cells), but now with MIXED attribution and two
completed epochs per cell rather than the provisional initial-conversion-only
reading.

## Timeout / horizon audit (V6-20)

**Zero** executions across all 450 terminated through the unresolved-at-horizon
path. Collisions: S1 98, S2 95, switching 73. S2's forced conversion succeeded in
46 of 150 cells and failed in 104, always with
`topology_selection_epoch_count = 0`.

## Outstanding

Clean detached reproduction (DETACHED-1 through DETACHED-5) has not been run.
Until it does, v6 is CANDIDATE_AUTHORITATIVE, not authoritative.
