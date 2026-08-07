# Phase 8E-PC-ET — Source Event-Timing Failure Audit (ET-1)

Audit of every S0 and S4 event definition present at the blocked commit
`900a43f884dcb355bf544dd729e32a880cfd5f3a`, before any new semantics were
written. Sources inspected: `source_policy_contracts_v1.json`,
`executable_scientific_protocol_v1.json`, the 30 compiled train/validation
layout execution records, `docs/PHASE8E_SOURCE_POLICY_EXECUTION_CONTRACTS.md`,
and the partial runtime implementation in `rvt_swarm/phase9c_rb/policies.py`.

Specification-only. No simulator episode was run to produce this audit.

## The invariant every event is measured against

All 30 layouts share one mission: topology origin at `x = -6.0`, goal centre at
`x = +6.0`, mission distance **12.01 m**. The frozen platform maximum speed is
**0.9 m/s**. An ideal unconstrained traversal therefore takes at least

    12.01 / 0.9 = 13.34 s

before any formation constraint, obstacle detour, safety projection, transition
profile or dwell is applied. Any event scheduled after 13.34 s is not reachable
in a nominally completing episode.

## Classification

* **A** — reachable and meaningful
* **B** — reachable but unrelated to the intended physical event
* **C** — normally unreachable
* **D** — ambiguous

## S0 scripted diagnostic — superseded `machine_readable_script`

| family | policy | event type | current trigger | current physical time (s) | mission landmark intended | earliest completion (s) | reachable | scientific purpose | class |
|---|---|---|---|---:|---|---:|---|---|:--:|
| F1 | S0 | — | none declared | — | none | 13.34 | n/a | open field: no topology event | **NO_EVENT** |
| F2 | S0 | `local_constriction` | 0.20 H | 24.0 | straight passage entry | 13.34 | no | enter LINE for the passage | **C** |
| F2 | S0 | `local_opening` | 0.65 H | 78.0 | straight passage exit | 13.34 | no | return to COMPACT after | **C** |
| F3 | S0 | `local_constriction` | 0.20 H | 27.0 | offset passage entry | 13.34 | no | enter LINE | **C** |
| F3 | S0 | `local_opening` | 0.65 H | 87.8 | offset passage exit | 13.34 | no | return to COMPACT | **C** |
| F4 | S0 | `local_constriction` | 0.20 H | 30.0 | S-passage entry | 13.34 | no | enter LINE | **C** |
| F4 | S0 | `local_opening` | 0.70 H | 105.0 | S-passage exit | 13.34 | no | return to COMPACT | **C** |
| F5 | S0 | `local_constriction` | 0.15 H | 27.0 | bottleneck 0 entry | 13.34 | no | first cycle | **C** |
| F5 | S0 | `local_opening` | 0.35 H | 63.0 | bottleneck 0 exit | 13.34 | no | first cycle | **C** |
| F5 | S0 | `local_constriction` | 0.55 H | 99.0 | bottleneck 1 entry | 13.34 | no | second cycle | **C** |
| F5 | S0 | `local_opening` | 0.75 H | 135.0 | bottleneck 1 exit | 13.34 | no | second cycle | **C** |
| F6 | S0 | `local_constriction` | 0.50 H | 65.0 | central blocker | 13.34 | no | false-bottleneck probe | **C** |
| F7 | S0 | `local_constriction` | 0.33 H | 36.3 | first clutter circle | 13.34 | no | neutral clutter probe | **C** |
| F7 | S0 | `local_opening` | 0.67 H | 73.7 | past the clutter | 13.34 | no | return to COMPACT | **C** |
| F8 | S0 | `local_constriction` | 0.20 H | 36.0 | passage entry | 13.34 | no | enter LINE under degraded comms | **C** |
| F8 | S0 | `local_opening` | 0.70 H | 126.0 | passage exit | 13.34 | no | return to COMPACT | **C** |
| F9 | S0 | `local_constriction` | 0.33 H | 49.5 | dynamic obstacle band | 13.34 | no | react to the crossing circle | **C** |
| F9 | S0 | `local_opening` | 0.67 H | 100.5 | past the crossing | 13.34 | no | return to COMPACT | **C** |
| F10 | S0 | `local_constriction` | 0.40 H | 36.0 | sub-clearance passage | 13.34 | no | infeasible-family control | **C** |

## S4 frozen transition protocol — superseded `0.25H` / `0.65H`

S4's schedule was family-independent, so every family carries the same two
events. None is reachable.

| family | H (s) | LINE event at 0.25 H (s) | COMPACT event at 0.65 H (s) | earliest completion (s) | class |
|---|---:|---:|---:|---:|:--:|
| F1 | 90 | 22.5 | 58.5 | 13.34 | **C** |
| F2 | 120 | 30.0 | 78.0 | 13.34 | **C** |
| F3 | 135 | 33.8 | 87.8 | 13.34 | **C** |
| F4 | 150 | 37.5 | 97.5 | 13.34 | **C** |
| F5 | 180 | 45.0 | 117.0 | 13.34 | **C** |
| F6 | 130 | 32.5 | 84.5 | 13.34 | **C** |
| F7 | 110 | 27.5 | 71.5 | 13.34 | **C** |
| F8 | 180 | 45.0 | 117.0 | 13.34 | **C** |
| F9 | 150 | 37.5 | 97.5 | 13.34 | **C** |
| F10 | 90 | 22.5 | 58.5 | 13.34 | **C** |

## Result

**19 of 19 declared S0 events and 20 of 20 declared S4 events are class C.**
Not one class-A event existed. No event was class B or D: the *intent* of each
event was clear and correctly matched to a real physical feature — only the
trigger was wrong.

F1 is the sole family whose S0 declaration was already correct: it declares no
event, and its two circles sit at |lateral| >= 3.06 m against a frozen
`R_obs = 3.0 m`, so no topology event is locally observable there at any team
size. The absence of an event in F1 is geometry, not an omission.

## Non-vacuity

The conclusion does not rest on the single `train-f2-00` execution that first
exposed the problem. The table above is derived from frozen geometry and the
frozen maximum speed for all ten families and all 30 layouts, independently of
any execution. The F2 run is corroborating evidence, not the basis:
that episode terminated by collision at **t = 4.8 s**, which is 19.2 s before
its scripted LINE event and 8.5 s before the ideal completion bound — consistent
with, but not required by, the static argument.

## Additional finding — declared sequence order (F5)

While anchoring events to landmarks, the audit found that F5's second
bottleneck entry becomes locally observable at longitudinal **2.66 m** while
its first bottleneck exit is at **3.50 m**. A purely position-triggered plan
would therefore fire event #2 before event #1, the #2 LINE request would be a
no-op against an already-LINE commitment, and F5 would collapse from two
bottleneck cycles to one. The repaired contract clamps each trigger to be no
earlier than its predecessor, which preserves the declared four-event sequence
exactly as ET-2 requires.
