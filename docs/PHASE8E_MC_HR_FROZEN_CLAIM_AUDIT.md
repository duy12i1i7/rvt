# Phase 8E-MC-HR — Frozen Claim Audit (MC-1)

Read from the repository, not from memory. Short exact fragments only.

## F5 family declaration

`docs/RVT_FD24_SCENARIO_FAMILY_CONTRACT.md`, line 14:

| F5 | SEQUENTIAL_BOTTLENECKS | RECONFIGURATION_REQUIRED | separation 3.0-4.8 m, width 1.40-1.65 m | repeated C->L->C | nominal | 180 s |

The contract states the family **archetype** (`SEQUENTIAL_BOTTLENECKS`), a
**declared expected headroom** (`RECONFIGURATION_REQUIRED`) and an expected
transition pattern (`repeated C->L->C`).

Answer to MC-1 question 1: the wording is neither of the two candidate phrases.
It is a **declared headroom category**, not prose about opportunity versus
necessity. That matters, because a declared category is falsifiable against the
executable definition below, whereas prose would not be.

## RECONFIGURATION_REQUIRED definition

`docs/RVT_FD24_SCENARIO_HEADROOM_PROTOCOL.md`, line 10, verbatim:

> **RECONFIGURATION_REQUIRED:** neither fixed policy completes the whole task
> but the frozen scripted COMPACT/LINE oracle succeeds.

Answer to MC-1 question 2: **yes**, the definition is exactly the conjunction

    (neither fixed policy completes) AND (frozen scripted oracle completes)

and it is to be enforced literally. F8 carries the same category
(`RECONFIGURATION_REQUIRED with agreement stress`).

## Executable evidence against that definition

`train-f5-00`, N=6, real controller, real safety, real readiness, frozen
`generic_role_space_profile`, real Target V4:

| policy | result | required by the definition |
|---|---|---|
| fixed COMPACT (S1) | COLLISION at progress 0.98 m | must fail — **holds** |
| fixed **LINE** (S2) | **GOAL_COMPLETE**, passes both bottlenecks | must fail — **violated** |
| scripted oracle (S0) | readiness UNSAFE, lifecycle ABORTED, COLLISION | must succeed — **violated** |

Both conjuncts fail. `train-f5-00` cannot be `RECONFIGURATION_REQUIRED` under
the literal frozen definition; on these outcomes it is `LINE_ONLY_SUCCESS`.

## MC-1 question 3 — what transition motion was actually qualified

The Phase 7R reference fixture is named `exact_source` and starts from the exact
source template **at rest**. Its qualified minimum robot-robot clearance for
COMPACT -> LINE at N=6 is **0.5247 m** against the frozen 0.4000 m requirement.

No frozen document states whether a topology transition may execute while the
mission translation term is active. The qualification covers the at-rest case
only.
