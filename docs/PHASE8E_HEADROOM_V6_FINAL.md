# Phase 8E-HR-V6 — Final Executable Headroom Requalification

**Status: AUTHORITATIVE_PRE_DATA_HEADROOM.** Promoted from
`CANDIDATE_AUTHORITATIVE` after clean detached reproduction.

| record | value |
|---|---|
| candidate commit | `8565113e6f432f07caf10db8ce8012fa6ecb63ca` (tag `rvt-headroom-v6-candidate-v1`) |
| execution-runtime source commit | `990accb0e240a9bb03243a2cd064b36c4ab5605a` |
| v6 artifact hash | `d044d6b99d7a2bbb83565b121d188a35e335bfd856e3eb0e885823ca1a6742ef` |
| detached reproduction hash | `1f08ba77315e6fdbabfeac8f9350e6f5cd64468c431ecc9fba19747fcd26af32` |
| authority record hash | `fafe1460c69ef37ca9134c2fc17721adddda92607e3e4e3c084d6a29d9dab509` |

The committed candidate artifact is **not** edited. Promotion and the one
analysis correction below live in
`results/rvt_fd24/headroom_authority_record_v1.json` and
`results/rvt_fd24/headroom_v6_detached_reproduction_v1.json`, which reference the
v6 hash. v2–v5 remain unchanged as historical/provisional artifacts.

## The five statements this phase must make

1. **v6 establishes executable topology headroom before scientific dataset
   generation.** 150 layout × team-size cells, 450 policy executions, all from
   the frozen runtime with defects 9–13 closed and the PCA conformance audit
   complete. No dataset row, shard, checkpoint or optimizer state was produced.
2. **v6 does NOT establish the ≥ 0.10 H2 effect size.** No trained method was
   evaluated, and the ≥ 0.10 absolute criterion is not tested by a headroom
   artifact. `H2_EMPIRICALLY_CONFIRMED` is **false** at this phase.
3. **The exact frozen H2 remains experimentally viable and falsifiable.**
   Genuine headroom exists (7 cells, 5 train / 2 validation), the fixed
   baselines are executable and meaningfully comparable, and both outcomes of
   the later experiment remain reachable.
4. **Six headroom cells exhibit complete C→L→C multi-epoch switching
   opportunities**, and detached verification confirms them: all six were rerun
   executably, each with two distinct lifecycle IDs, `mode_epoch_count = 2`, two
   distributed COMPLETE agreements, two frozen-profile executor windows, and an
   observed committed sequence of exactly `COMPACT → LINE → COMPACT`.
5. **The F5 zero-completed-epoch headroom cell is described from its exact
   detached trace and is not presented as a completed switch.** See below.

## Integrity

150 cells (100 train, 50 validation), 450 policy executions, 0 errors, 0
duplicate keys, `N ∈ {5,6,8,12,16}`, no N=24, no final test.

| category | train (100) | validation (50) |
|---|---:|---:|
| BOTH_FAIL | 48 | 20 |
| BOTH_SUCCESS | 16 | 13 |
| LINE_ONLY_SUCCESS | 16 | 7 |
| COMPACT_ONLY_SUCCESS | 13 | 7 |
| **RECONFIGURATION_REQUIRED** | **5** | **2** |
| INVALID_OR_AMBIGUOUS | 2 | 1 |

## Clean detached reproduction

A detached worktree at exactly the candidate commit — not the development tree —
with `git status --porcelain` empty. The v6 canonical hash was verified from the
committed artifact *before* anything was re-executed.

The reproduction rule is machine-readable and fixed in advance: order cells by
`(split, family, layout_id, team_size)`, take the first cell satisfying each
required coverage class, never replace a selected cell. That yields 18 records.
Rather than stop there, **all 150 cells were re-executed with all three
policies**: 450 executions, exact canonical equality on every stored field, no
tolerance introduced, **0 mismatches**, and every reproduced headroom category
identical to the recorded one.

One declared coverage class is empty in this domain:
`PCA15_UNRESOLVED_AT_HORIZON_NEGATIVE`. No execution among the 450 terminates at
the horizon, so that path is covered by the PCA-15 conformance fixture rather
than by a headroom cell.

## A measurement defect I caught and corrected

The sweep initially recorded switching epoch count as
`mechanical_transition_epoch_count`. That counter increments in exactly one
place — `FixedTopologyPolicy.observe`, S2's forced initialization — so it is
structurally 0 for the switching diagnostic. It reported "all 7
RECONFIGURATION_REQUIRED cells used 0 switching epochs", which is an artefact.

The authoritative field is `completion_agreements`, distributed lifecycle
completions actually reached:

| RECONF cells | completed switching epochs |
|---:|---|
| 6 | **2** |
| 1 | 0 |

`tests/test_phase8e_switching_epoch_measurement.py` now prevents the defect from
returning: it pins the single legitimate increment site, shows live that a
two-epoch cell reads `mechanical = 0` while reaching two distributed
completions, and shows that the v6 distribution is reproducible from
`completion_agreements` and **not** reproducible from the mechanical counter.

## The F5 zero-completed-epoch cell — `train/train-f5-00/N8`

Mechanism classification: **B — partial transition effect.**

| policy | outcome |
|---|---|
| S1 fixed COMPACT | COLLISION at step 69 (10.35 s), VALID_TASK_NEGATIVE, min sep 0.44972 m, 0 lifecycles, 0 staged steps |
| S2 fixed LINE | COLLISION at step 74 (11.10 s), VALID_TASK_NEGATIVE, min sep 0.46383 m, 1 forced lifecycle, aborted on readiness, 6 staged steps, LINE never established |
| switching | GOAL_COMPLETE at step 133 (19.95 s), RECOVERABLE_POSITIVE, min sep 0.41796 m |

The switching trace: two LINE intents originate at landmarks `passage_entry-0`
and `passage_entry-1` (lifecycles 1 and 2). Both reach `ALL_READY_AGREEMENT` and
both abort with `READINESS_AGREEMENT_FAILED`, at step 6 and step 74.
`mode_epoch_ids` stays `[0]`, no transition executor ever runs, local dwell is
never complete, there is no distributed COMPLETE, and the committed topology is
COMPACT for the entire episode.

What changes the trajectory is mission staging. While a robot is inside an
active intent it suppresses only its own goal term, so the team is staged for 39
of 133 control steps in two windows — steps 1–7 and 42–75. Fixed COMPACT opens
no lifecycle, never stages, and collides at step 69, **inside** the second
window; fixed LINE stages once for 6 steps and collides at step 74, also inside
it.

This is an *attempted* reconfiguration effect mediated by the frozen
mission-staging rule (owner decision 1), not a completed topology switch. It is
inside the frozen topology-control policy — staging is gated purely by a robot's
own lifecycle state, and S2 stages identically for its one forced attempt — so
it is not a fairness defect. The asymmetry is that the online policy opens
intents repeatedly and the fixed baselines by construction do not, which is a
property of the policies, not of the evaluation.

Consequence: the cell keeps its `RECONFIGURATION_REQUIRED` category, whose
definition it still satisfies, but it must **not** be counted as
completed-reconfiguration headroom and must never be cited as evidence of a
completed switch.

## Attribution (corrected)

| attribution | v6 recorded | corrected |
|---|---:|---:|
| MIXED | 6 | 6 |
| INITIAL_CONVERSION_DRIVEN | 1 | 0 |
| LATER_TASK_DRIVEN | 0 | 0 |
| **PARTIAL_ATTEMPT_EFFECT** | — | **1** |

The six F9 cells are MIXED because both effects are material from the trace:
fixed LINE fails its forced initial conversion, **and** the switching diagnostic
completes two during-task epochs ending back at COMPACT. The single F5 cell
moves to `PARTIAL_ATTEMPT_EFFECT` for the reason above. This correction is
additive; the candidate artifact is left byte-identical so its hash stays
verifiable.

Across all 63 successful switching cells: 36 completed 0 epochs (topology
retention), 18 completed 1, 9 completed 2.

## H2

Exact wording, `docs/RVT_FD24_RESEARCH_QUESTIONS_AND_HYPOTHESES.md:25`:

> **H2.** Online COMPACT/LINE reconfiguration improves episode task success by at
> least 0.10 absolute over each fixed topology in predeclared families with
> genuine topology headroom.

```
H2_REQUIRED_SCOPE                  = LEVEL_A
GENUINE_HEADROOM_PRESENT           = true
H2_PRE_DATA_VIABILITY              = true
V6_HEADROOM_SUPPORTS_H2_VIABILITY  = true
H2_EMPIRICALLY_CONFIRMED           = false
```

v6 is a **pre-data headroom qualification**. It establishes that executable
genuine topology headroom exists, that fixed policies can be meaningfully
compared against online switching, and that H2 stays falsifiable. It does not
evaluate the ≥ 0.10 absolute criterion; that requires the later trained and
evaluated primary method comparing the final online method against **each** fixed
topology.

The six C→L→C cells may be reported as evidence that multi-epoch reconfiguration
opportunities genuinely exist. They are not proof of the final H2 effect size.

## F5

15 cells: LINE_ONLY_SUCCESS 6, BOTH_FAIL 4, BOTH_SUCCESS 3, COMPACT_ONLY 1,
RECONFIGURATION_REQUIRED 1. The conservative additive wording — "sequential
bottlenecks exposing repeated topology-reconfiguration opportunities" — is
retained. The historical "requiring repeated C→L→C" phrasing is **not** restored:
only one F5 cell carries switching headroom, and that cell completed zero
transition epochs.

## F9

15 cells: RECONFIGURATION_REQUIRED 6, LINE_ONLY_SUCCESS 6, BOTH_FAIL 3. F9
dominates headroom (6 of 7 cells), with MIXED attribution and two completed
epochs per cell. All 12 of F9's switching successes involve at least one
completed reconfiguration, so the family's diagnostic advantage does not rest on
attempt-only effects.

## Timeout / horizon audit

**Zero** of the 450 executions terminated through the unresolved-at-horizon path.
Collisions: S1 98, S2 95, switching 73. S2's forced conversion succeeded in 46 of
150 cells and failed in 104, always with `topology_selection_epoch_count = 0`.

## Isolation

Final-test geometry access 0 (the compiled directory does not exist), Study A
N=24 access 0, dataset rows 0, shards 0, checkpoints 0, optimizer states 0,
locality violations 0. The generation-budget hash and all six protected
scientific hashes are unchanged and self-consistent.

## Outstanding

The detached gates are closed. Phase 9C-RB may resume from RB-15 **on explicit
owner instruction only** — it is not resumed automatically here, and no Phase 9
scientific dataset is generated and no training is performed by this phase.
