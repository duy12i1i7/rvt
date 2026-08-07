# Phase 8E Source Policy Execution Contracts

## Typed interface

Every S0-S5 policy receives one robot-local view, local lifecycle state,
immutable local topology metadata, shared mission clock, source-job seed and
episode horizon. It returns a local action source, an optional candidate request
and event eligibility. Headroom, future outcomes, future obstacle/disturbance
state, global task result and final-test metadata are absent from the type.

All policies use predeclared Phase 9B decision slots only while the episode is
active. A slot after termination is unavailable and is never moved or replaced.
Termination is goal completion, horizon, or a typed terminal failure.

## S0 scripted diagnostic

S0 is offline collection-only. Phase 6 local control and safety remain active.
The desired topology follows the frozen smooth role-space profile; this
diagnostic oracle bypasses Phase 7 agreement but never safety. Each one-shot
event occurs at normalized horizon time and is skipped, not moved, if blocked.

| Family | Script `(normalized time, desired topology)` |
|---|---|
| F1 | none; hold COMPACT |
| F2, F3 | `(0.20,LINE)`, `(0.65,COMPACT)` |
| F4 | `(0.20,LINE)`, `(0.70,COMPACT)` |
| F5 | `(0.15,LINE)`, `(0.35,COMPACT)`, `(0.55,LINE)`, `(0.75,COMPACT)` |
| F6 | `(0.50,LINE)` |
| F7 | `(0.33,LINE)`, `(0.67,COMPACT)` |
| F8 | `(0.20,LINE)`, `(0.70,COMPACT)` |
| F9 | `(0.33,LINE)`, `(0.67,COMPACT)` |
| F10 | `(0.40,LINE)` |

The exact table is machine-readable in `source_policy_contracts_v1.json`.

## S1 and S2 fixed topology

S1 initializes and holds COMPACT, issues no request, and uses the Phase 6 COMPACT
controller plus safety projection throughout mission and obstacle response.

S2 uses the offline forced-topology initialization interface to establish LINE
targets at time zero, creates no source-equals-target epoch, then holds LINE with
the Phase 6 controller and safety projection. Primary publication initialization
still remains COMPACT.

## S3 local geometric selector

S3 uses own state, fresh one-hop messages, ego-relative obstacle support disks,
mission direction, local COMPACT/LINE role metadata and local lifecycle only.
For topology `tau`, required corridor width is

`lateral_role_span(tau) + 2*(robot_radius + 0.02 m)`.

The width statistic is minimum free inner-surface separation from paired left and
right supports in the role-dependent lookahead sector.

- COMPACT to LINE: after `evidence_persistence_seconds`, request LINE iff width
  is at least LINE-required width and below COMPACT-required width plus
  `spacing_margin_meters`.
- LINE to COMPACT: after the same persistence, request COMPACT iff complete
  observation is open or width is at least COMPACT-required width plus twice the
  spacing margin.
- One side, incomplete extent, width below LINE requirement, contradictory data,
  ties, or stale evidence is UNKNOWN: hold and emit no intent.

Minimum commitment is the frozen protocol commitment time. A robot originates
only on its own threshold crossing; adopting an active intent suppresses later
origins. Every request uses unchanged Phase 7 readiness, agreement,
confirmation, profile, abort and rearm semantics. Thresholds come only from
topology geometry and physical configuration, never label balance.

## S4 transition-protocol trajectory

S4 is offline collection-only and exercises the real Phase 7 protocol. Local
role `role-0000` emits one LINE event at `0.25H` and one COMPACT event at `0.65H`
when the candidate differs from committed topology. This deterministic
originator follows the already qualified diagnostic fixture pattern; propagation,
score agreement, readiness, all-ready, confirmation and commitment remain
leaderless per-robot states.

Every robot's diagnostic candidate score is exactly `1.0` with semantics
`bounded_diagnostic_candidate_available`; existing Phase 7 min/max aggregation
is used. Phase 5 is inactive. Timeout is remaining horizon. Abort/rearm is
unchanged and a scheduled event is not retried.

## S5 bounded perturbation

S5 uses S1 as base. Seed modulo N selects one robot without outcomes. At the
first control tick at or after `0.40H`, add one mission-frame uniform-disk
acceleration of maximum magnitude `0.25*a_max` before safety projection for one
control period. There is exactly one perturbation. It is never regenerated,
repeated or moved toward a decision slot. Nonfinite output records invalidity.

Rejected alternatives include future-label scripts, global corridor width,
learned S4 score, all-robot simultaneous diagnostic origination, repeated S5
search, and using the historical KEEP/LINE selector. Each violates locality,
frozen candidate scope, protocol mechanics or post-hoc independence.
