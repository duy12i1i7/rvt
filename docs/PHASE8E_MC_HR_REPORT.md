# Phase 8E-MC-HR Report

Branch `research/rvt-transition-mission-headroom-repair-v1`, from
`f51108b71253ce353602c2e0e895ca08d609174c` (tagged
`rvt-phase9c-real-readiness-scientific-block-v1`).

Specification/audit only. No code changed, no dataset row, no shard, no
checkpoint, no training, no final-test geometry, no Study A N=24 access.

## Verdict

> ### **A — transition-motion semantics cannot be resolved without a new scientific constant, and the frozen F5 headroom claim is contradicted by executable evidence.**

Two independent stop conditions fired, both of them conditions this phase
defined in advance.

## Stop 1 — MC-5: no existing motion-settle tolerance

MC-2 first ruled out the ordinary explanation. The frozen profile interpolates
role offsets and emits pairwise `desired_offset_from_observer_meters`, so it is
translation-invariant by construction and the adapter does not anchor it to a
static world origin. Holding position, goal and obstacles fixed and zeroing only
velocity lifts the minimum separation from **0.3979 m to 0.4166 m** — a
velocity-dependent effect, not a position-dependent frame bug.

MC-3 staging would then be the route, but it needs a `MOTION_SETTLED`
predicate, and MC-5 forbids inventing one. No velocity or settling tolerance
exists anywhere in the frozen configuration or the Phase 6/7/readiness modules;
every speed-related constant is a bound, and every tolerance is spatial. MC-5's
own rule applies: stop rather than choose a number.

## Stop 2 — HR: F5's frozen category is falsified

Frozen definition, verbatim from `RVT_FD24_SCENARIO_HEADROOM_PROTOCOL.md`:

> **RECONFIGURATION_REQUIRED:** neither fixed policy completes the whole task
> but the frozen scripted COMPACT/LINE oracle succeeds.

`RVT_FD24_SCENARIO_FAMILY_CONTRACT.md` declares F5 as
`RECONFIGURATION_REQUIRED` with `repeated C->L->C`.

Executable outcomes for `train-f5-00` at N=6 under the fully corrected runtime:

| policy | result | definition requires | verdict |
|---|---|---|---|
| fixed COMPACT | COLLISION at 0.98 m | must fail | holds |
| **fixed LINE** | **GOAL_COMPLETE** | must fail | **violated** |
| scripted oracle | readiness UNSAFE, ABORTED, COLLISION | must succeed | **violated** |

Both conjuncts fail, so this cell cannot be `RECONFIGURATION_REQUIRED`; on these
outcomes it is `LINE_ONLY_SUCCESS`. HR-2 is explicit that a fixed-LINE success
excludes the category and that the family name does not decide it.

Full requalification (HR-1, HR-3, HR-5, HR-6) was **not** run, because it
depends on transition-motion semantics that Stop 1 leaves unfrozen: the
switching-oracle arm of the definition cannot be evaluated until it is known
whether the oracle may transition while translating. Running it now would
produce categories that a later semantics decision would invalidate.

## Consequence for the primary study

HR-5 asks whether executable `RECONFIGURATION_REQUIRED` headroom still exists in
both train and validation. On present evidence F5 — one of the two families
declared to carry that category, the other being F8 — does not, and F8 shares
the geometry-plus-transition structure that failed here. Whether any cell
survives cannot be established until the semantics are frozen. That is the
substance of the H2 risk, and it is reported rather than resolved.

## What the protocol owner must decide

1. Whether a topology transition may execute while the mission translation term
   is active. If yes, the Phase 7R qualification and the readiness envelope are
   incomplete: five robots certify SAFE with margins 0.098-0.191 m while swept
   paths breach the 0.4000 m clearance by ~3 mm. If no, a `MOTION_SETTLED`
   tolerance must be frozen, since none exists.
2. Whether F5's declared `RECONFIGURATION_REQUIRED` category, and the family
   contract wording `repeated C->L->C`, are amended to match executable
   behaviour, or whether the geometry is changed so the declared category
   becomes true. This phase changed neither.

## Isolation

Protected artifacts unchanged; strict-decentralization violations 0;
final-test access 0; Study A N=24 access 0; dataset rows 0; shards 0;
checkpoints 0; optimizer states 0. Test count unchanged at 2430.
