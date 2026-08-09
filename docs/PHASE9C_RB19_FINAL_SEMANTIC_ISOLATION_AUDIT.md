# Phase 9C-RB19 — Final Semantic, Provenance, Sealed-Domain and Isolation Audit

**Result: provenance closure is complete and no leakage exists. Verdict C.**

RB-18 found that the RB-17 generation-contract root resolved twelve of thirteen
required contracts but never cited **Target V4**. RB-19 closes that gap
additively, then audits every current semantic path end to end.

| artifact | hash |
|---|---|
| RB-19 final semantic/isolation audit | `7d8ac4c55ec46a6c46ceb1506b43eb2c699bd762ee01bd108076a88204dff813` |
| **RB-19 current generation provenance root** | `e8317ad3e9facc76511098503cdad55dfc065dedd8fc2b530a2b25845c3f5571` |
| Target V4 execution contract | `54a0e0baff79fbdc320800b772f47a40ac06ac4f0e70d4fab1bf676c54b918ee` |

RB-20 and RB-21 consume the RB-19 root. The RB-17 root is retained unmodified as
historical evidence.

## Target V4 was missing from RB-17 provenance closure

The contract is `rvt-target-v4-execution-contract/v1`, read from the committed
artifact and verified self-consistent. Its hash agrees exactly with both
independent references that already used it — headroom v6's `protocol_hashes` and
the RB-18 recoverability canary. Three dispositions
(`RECOVERABLE_POSITIVE` / `VALID_TASK_NEGATIVE` / `GENERATION_INVALID`), ten raw
predicates, positive rule "GOAL_COMPLETE and all ten predicates true", valid
negative "generation valid and positive rule false", and a typed
`EXECUTOR_EXCEPTION` policy that never becomes an implicit label.

**No executable semantic mismatch was found in RB-18.** The defect was a missing
citation, not a wrong contract: RB-18 ran the recoverability branch against
exactly this contract.

## RB-19 repairs provenance additively

The RB-17 root is **not** edited. A superseding root resolves 37 nodes covering
all 29 required concepts, each classified exactly once:

| status | count | examples |
|---|---:|---|
| CURRENT | 30 | protocol, splits, ET timing, Target V4, Residual Expert V2, model V2 repair, identity contracts |
| SUPERSEDED_EVIDENCE | 2 | failed RB-16 frame audit; incomplete RB-17 root |
| HISTORICAL_IMMUTABLE | 2 | generation budget V1; historical job manifest |
| DIAGNOSTIC_ONLY | 1 | RB-18 structural canary |
| PENDING_OPERATIONAL_QUALIFICATION | 2 | residual job manifest V2; Residual V2 generation timeout |

**Missing required contracts 0 · ambiguous current contracts 0 · current nodes
pointing only to superseded evidence 0.**

## Stale-semantics audit

All fourteen named stale semantics are blocked in current paths: MISSION model
output, model V1 residual semantics, the old diagnostic candidate fixture,
candidate count ≠ 9, post-safety residual, rotation augmentation, the 1800 s
timeout, an identity without candidate-evaluation dimension, missing orientation,
KEEP online, provisional headroom, local dwell as distributed COMPLETE, hardcoded
SAFE readiness, and a persistent lifecycle queue. **Stale current references: 0.**

## Semantics

**Recoverability** runs decision state → candidate topology → snapshot →
replica/matched streams → qualified executor → transition lifecycle → raw Target
V4 predicates → disposition → aggregate label. No proxy classifier, no
terminal-collision shortcut, no global runtime controller; raw termination causes
survive alongside the disposition; safety infeasibility and solver failure stay
distinct. The F8/F9 rule is frozen at three matched all-success replicas — and its
**p³-style confidence/strictness confound is recorded as a known scientific
limitation, not altered post hoc.**

**Residual** runs the full V2 path with nine candidates, pre-safety injection,
matched counterfactuals, the four V2 utilities, and the unchanged V1 selector and
target builder. No hidden fallback, no target rotation, no candidate subset, no
short-horizon optimization, no data-dependent normalization.

`NO_ELIGIBLE_ACTION` is attempted, counted, emits zero rows, is neither
execution-invalid nor infrastructure failure, is deterministic on retry, and
creates no zero, clipped or fallback target anywhere — including in writers.

**Frame** is WORLD for expert target, scientific target, model output and runtime
insertion, with WORLD componentwise bounds, MISSION input features and **no
rotation-equivariance claim**.

## Splits and seals

Permitted layout sources are train and validation only; final-test job
construction is `prohibited`. **Study A N=24 stays sealed for zero-shot
evaluation only** — training, early stopping, hyperparameter search and
checkpoint selection are all prohibited consumers, and its namespace holds only
its manifest. **Study B N=24 is a separate study** whose N24 *is* trainable within
its own namespace; the two must never be conflated, and this phase accessed
neither. Final-test geometry is not materialized, access count 0.

Class weighting is `NOT_SELECTED`, no normalization, sampling weights or
thresholds were chosen, and no train/validation pooling exists. The frozen
hyperparameter budget (12 configurations, 50,000 steps, seeds {11, 29, 47}) is
unchanged: **no new hyperparameter** came from Residual V2, the WORLD repair, the
orientation context or the generation contracts. The +192 residual-head parameters
are a repair, not a hyperparameter.

## Preflight

53 checks pass positively. A ten-case negative matrix is executed, and every case
is rejected: missing Target V4 provenance, wrong Target V4 hash, incomplete
closure, a root citing the failed RB-16 as current, KEEP online, premature
`AUTHORIZED`, an unsealed final test, an unsealed Study A N24, a `NO_ELIGIBLE`
fallback, and stale current semantics — plus a missing-root case. No positive
semantics were weakened to implement them.

## Status

No scientific data has yet been generated: recoverability rows 0, residual rows 0,
shards 0, checkpoints 0, optimizer states 0, final-test accesses 0, Study A N=24
accesses 0, locality violations 0.

Operational decisions remain pending RB-21: `RESIDUAL_V2_GENERATION_TIMEOUT =
PENDING_RB21_PERFORMANCE_QUALIFICATION`, worker count and chunk size `UNFROZEN`,
parallel efficiency unmeasured. These do not make the scientific semantics
ambiguous — they keep official execution unauthorized.

**RB-20 clean detached reproduction remains mandatory before any execution
authorization.**
