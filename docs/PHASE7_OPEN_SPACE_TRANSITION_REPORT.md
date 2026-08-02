# Phase 7 Open-Space Transition Report

## Matrix

The frozen matrix contains 6 team sizes x 6 directed pairs x 4 fixtures = 144
episodes.  Fixtures are exact source, bounded source perturbation, translated
mission, and rotated mission.  Candidate scores are constant deterministic
diagnostic values; no model output is called.

| N | episodes | completed target dwell | collision-free | median bytes |
|---:|---:|---:|---:|---:|
| 5 | 24 | 11 | 24 | 67,486 |
| 6 | 24 | 15 | 24 | 125,815 |
| 8 | 24 | 5 | 24 | 281,445 |
| 12 | 24 | 4 | 24 | 984,495 |
| 16 | 24 | 8 | 24 | 2,493,702 |
| 24 | 24 | 4 | 24 | 8,440,705 |
| **all** | **144** | **47 (32.6%)** | **144 (100%)** | - |

Every episode reached intent, score, all-ready and confirmation agreement; every
precommit certificate was SAFE.  Every episode produced exactly one committed
topology epoch, with zero no-op, retry, partial-commitment, strict-guard, or
learned-model events.

## Pair results

| pair | successes / 24 | primary remaining outcome |
|---|---:|---|
| KEEP -> COMPACT | 0 | safety projection infeasible |
| COMPACT -> KEEP | 4 | safety projection infeasible in 20 |
| KEEP -> LINE | 8 | safety projection infeasible in 16 |
| LINE -> KEEP | 4 | safety projection infeasible in 20 |
| COMPACT -> LINE | 7 | safety projection infeasible in 17 |
| LINE -> COMPACT | 24 | none |

Ten of 36 N/pair cells pass all four fixtures: N5 KEEP->LINE and LINE->COMPACT;
N6 LINE->KEEP, COMPACT->LINE and LINE->COMPACT; N8 LINE->COMPACT; N12
LINE->COMPACT; N16 COMPACT->KEEP and LINE->COMPACT; N24 LINE->COMPACT.  The
other 26 cells fail the predeclared 0.90 dwell gate.  KEEP->LINE at N6 and
COMPACT->LINE at N5 each pass 3/4 and therefore still fail the cell gate.

The 97 failed episodes stop at the first `projection_infeasible` or solver-fail
status before integrating that action.  This is why collision-free rate remains
1.00; it is not counted as successful transition control.  No controller gain,
geometry, margin, timeout, or evaluator was changed after observing this result.

## Communication

Across the matrix, transmitted serialized bytes sum to: intent 5,185,812;
score 88,423,368; readiness 98,951,663; confirmation 84,947,976; lifecycle
status 19,938,778.  Per-episode traces include intent and agreement times,
per-robot readiness/margin, commit, Metric V3 tube/dwell, clearances,
projection interventions, abort, mode epochs, and byte phase totals in
`results/phase7_transition_protocol/open_space/episodes.json`.

P7-G5 fails on target dwell reliability.  Its collision-free subgate passes.
