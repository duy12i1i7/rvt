# Epoch Churn Audit (Task 4R-6)

Fixture `B_line_only_corridor`, N = 6, 5 seeds, geometric scripted proposals.
Tests `tests/test_no_redundant_reconfiguration_epochs.py` (7).

---

## 1. Measured churn, before the guard

| quantity | per episode |
|---|---|
| decision epochs opened | **16.2** |
| epochs producing a K → L transition | 1 (all 6 robots) |
| epochs producing a L → K transition | 1 (all 6 robots) |
| **epochs changing nothing** | **~14** |
| disagreement events | 4.8 |
| protocol bytes (trigger + score + confirm) | 100 685 |
| bytes attributable to non-transition epochs | **~26 %** |

A single corridor traversal should need one successful K → L epoch and one
successful L → K epoch. It was opening sixteen.

## 2. Classification

| class | cause |
|---|---|
| valid entry transition | 1 per episode — the corridor squeeze |
| valid recovery transition | 1 per episode — clearance reopening downstream |
| **no-op** | the dominant class: the trigger refires after `h_commit` expires while the local geometry still satisfies the trigger condition, consensus re-proposes the mode already committed, and the epoch completes having changed nothing |
| confirmation failure / disagreement | 4.8 per episode, correctly retained rather than split |
| stale / duplicate | none observed — already rejected by the token and staleness rules |

The no-op class is structural, not a bug in the trigger: while the team is
inside the corridor, `local_trigger`'s low-clearance condition is legitimately
true on every step. The dwell bound `h_commit` suppresses it for 10 steps at a
time, then it fires again.

## 3. Guards

Already enforced before this audit, and re-tested here:

- an entry trigger is only consulted when the robot is in KEEP, and
  `local_recovery_trigger` refuses unless the robot is in LINE — so neither
  direction can re-trigger itself;
- no trigger of either direction fires inside the commitment interval;
- a stale token cannot reopen a closed epoch.

**Added by this audit — the no-op guard.** After score consensus, if every
scoring robot's post-consensus proposal already equals its committed mode, the
epoch is closed immediately and the confirmation round is skipped.

## 4. Effect

| | before | after |
|---|---|---|
| epochs opened | 16.2 | 16.2 |
| of which identified as no-ops | — | **13.4** |
| protocol bytes per episode | 100 685 | **77 107** |
| reduction | — | **23 %** |

The epoch *count* is unchanged, because the trigger still fires — the guard
acts after scoring, not before triggering. What it removes is the expensive
part: a no-op epoch no longer runs a confirmation round. That is reported as a
cost reduction, not as churn elimination.

**Legitimate retries are not suppressed.** An epoch whose proposal differs from
the committed mode still runs confirmation in full, and a confirmation failure
still retains the previous mode and records a `DisagreementEvent`. The guard
only fires when the proposal and the committed mode already agree, in which
case confirmation could not change any outcome.

## 5. Remaining work

Reducing the epoch *count* would require rate-limiting the trigger itself — for
example requiring the local geometry to change materially since the last epoch,
rather than merely satisfying the threshold. That is a protocol change with its
own predeclaration requirements and is left for Task 5, where the trigger's
sensitivity will be exercised against six scenario families rather than one
fixture.
