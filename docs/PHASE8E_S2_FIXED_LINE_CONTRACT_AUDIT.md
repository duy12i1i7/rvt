# Phase 8E-S2-ME — Fixed-LINE Baseline Contract Audit

## Authoritative sources (S2ME-1)

| file | field / wording | physical initial topology | target | selection semantics | mechanical semantics | complete? |
|---|---|---|---|---|---|---|
| `results/rvt_fd24/source_policy_contracts_v1.json` | `S2_ALWAYS_LINE.initial_topology = 5`; `topology_behavior: "at time zero use the offline forced-topology qualification interface to initialize LINE role targets; no online request or epoch is created"` | COMPACT (5) | LINE (2) | none — target predetermined | **underspecified**: no path from COMPACT poses to LINE targets | no |
| `docs/PHASE8E_SOURCE_POLICY_EXECUTION_CONTRACTS.md` | "S2 uses the offline forced-topology initialization interface to establish LINE targets at time zero … **Primary publication initialization still remains COMPACT.**" | COMPACT | LINE | none | not stated | no |
| `docs/PHASE8E_INITIALIZATION_AND_DISTURBANCE_CONTRACT.md` | "the offline forced topology interface **initializes LINE role targets** at time zero without creating a source-equals-target epoch" | COMPACT | LINE | none | not stated | no |

All three agree on the physical initialization and the target, and all three are
silent on the mechanical realization.

**Defect 11** — the runtime physically relocated S2 to LINE poses,
`origin + R(psi) * line_offset_i`. That granted a free instantaneous
reconfiguration no document offers, and at N >= 8 the long LINE formation
intersected compiled geometry.

## Additive correction (not a rewrite)

> "No online topology-**selection** epoch is created. S2 performs one
> deterministic forced mechanical initialization transition solely to realize its
> fixed LINE target safely from the common COMPACT physical initial state."

Machine-readable in
`results/rvt_fd24/s2_fixed_line_mechanical_initialization_v1.json`
(`19f146b5701b9cc830b60382b9204155e401e0c771700038fab4f98dbc983413`). The
historical artifact is untouched.

## Selection versus mechanical coordination

S2 has no topology **selection**: no score, no candidate comparison, no learned
model, no geometry oracle. It does use mechanical **coordination**, because a
safe topology change requires it. Measured across all 150 cells:
`topology_selection_epoch_count` is **0** everywhere;
`mechanical_transition_epoch_count` is 0 or 1.

## Open-field regression (S2ME-13)

`train-f1-00`, N=6. S1 and S2 start from byte-identical physical state.

| implementation | min pair separation | result |
|---|---:|---|
| unmanaged direct target convergence | 0.3635 m | COLLISION at step 8 |
| **forced mechanical initialization** | **0.4264 m** | **GOAL_COMPLETE** |

Lifecycle observed: score agreement -> all-ready -> confirmation -> transition
execution -> target dwell -> COMPLETE. LINE dwell 17.25 s. No clearance,
readiness threshold or profile parameter was retuned.

## Executable headroom under corrected S2 (v5)

`results/rvt_fd24/headroom_requalification_v5.json`, hash
`b4830e22632491ad7e5d51e0b09bbb28e89f0ac16124fa5b87200bb3f136b4ac`.
150 cells, 450 episodes, zero exceptions.

| category | train (100) | validation (50) |
|---|---:|---:|
| BOTH_FAIL | 51 | 21 |
| COMPACT_ONLY_SUCCESS | 21 | 15 |
| LINE_ONLY_SUCCESS | 14 | 6 |
| BOTH_SUCCESS | 8 | 5 |
| RECONFIGURATION_REQUIRED | **4** | **2** |
| INVALID_OR_AMBIGUOUS | 2 | 1 |

S2 outcome modes across all 150 cells: **33 success, 104 failed during the
forced initial conversion, 13 failed later in the mission.**

## H2 — passes the gate, with a major interpretation limitation

`RECONFIGURATION_REQUIRED` is nonzero in both splits (4 train, 2 validation), so
the hard gate passes and H2 remains falsifiable. All six cells are F9, at N=8 and
N=12.

**All 6 of 6 are initial-conversion-driven**: fixed LINE loses because it cannot
realize its own topology from the common COMPACT start, not because of later
dynamic task behaviour. Zero cells are later-task-driven. Under S2ME-12 that
conversion cost is the intended fairness accounting, but it means the observed
switching advantage is an *initial-admissibility* effect rather than a
demonstrated dynamic-reconfiguration advantage. This must be stated in the paper.

## F5

3 LINE_ONLY_SUCCESS (all N=5, where S2's conversion succeeds), 5 BOTH_FAIL,
4 COMPACT_ONLY_SUCCESS, 3 further BOTH_FAIL. No F5 cell is
RECONFIGURATION_REQUIRED. The conservative wording — "sequential bottlenecks
exposing repeated topology-reconfiguration opportunities" — is retained and the
necessity claim is not restored.

## Remaining blocker

A **second** lifecycle launched after S2's completed forced initialization
(LINE -> COMPACT) does not reach `TARGET_DWELL`/`COMPLETE`. Five tests are marked
`xfail(strict=True)` with that reason so the defect is recorded rather than
silenced. The forced initialization itself is verified; chaining a further
transition after it is not.
