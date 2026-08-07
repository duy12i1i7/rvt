# Phase 8E-PC-ET — Source Event-Timing Contract

Additive addendum to `rvt-source-policy-contracts/v1`. Machine authority:
`results/rvt_fd24/source_event_timing_addendum_v1.json`, schema
`rvt-source-event-timing-addendum/v1`. The original
`source_policy_contracts_v1.json` is **not rewritten**; it remains byte-identical
and this addendum overrides only the event origination and timing fields named
below. Future execution manifests must reference both.

## Frozen principle

> **Source-policy transition events are anchored to physical mission state and
> local observability, never to a fraction of the episode wall-clock horizon.**

The episode horizon remains a timeout, an evaluation bound and a scientific
denominator. It no longer determines when a locally meaningful topology event
occurs.

## Exactly what is superseded

| policy | superseded field |
|---|---|
| S0 | `policies.S0_SCRIPTED_DIAGNOSTIC.machine_readable_script` (the normalized-time column only) |
| S0 | `policies.S0_SCRIPTED_DIAGNOSTIC.event_rule` |
| S4 | `policies.S4_FROZEN_TRANSITION_PROTOCOL.event_schedule_normalized_horizon` |
| S4 | `policies.S4_FROZEN_TRANSITION_PROTOCOL.event_rule` |

Explicitly **not** superseded: the event vocabulary; the per-family event order
and count; the target topology of each event; S1, S2 and S3; hysteresis and
rearm semantics; Target V4; the generation budget; the job manifest; seed
mapping; decision-state sampling slots; episode horizons; mission geometry;
maximum speed; the controller; the safety projection; the transition protocol;
readiness.

## Event vocabulary (unchanged)

`local_constriction`, `local_opening`, `externally_forced_diagnostic`. No new
scientific event category is introduced. This addendum changes the **trigger**
of an event, never its meaning.

## Local geometric evidence predicate

One authoritative interface, version `rvt-local-geometric-event-evidence/v1`,
shared by S3 and S4. Its implementation is the already approved
`rvt_swarm.phase8e.protocol.s3_local_geometric_decision`; no second threshold
system exists.

| declared state | frozen predicate value |
|---|---|
| `LOCAL_COMPACT_FEASIBLE` | `HOLD_COMPACT` |
| `LOCAL_LINE_REQUIRED` | `REQUEST_LINE` |
| `LOCAL_OPENING_FOR_COMPACT` | `REQUEST_COMPACT` |
| `LOCAL_GEOMETRY_UNKNOWN` | `HOLD_UNKNOWN` |

Permitted inputs: own robot-local state; locally observed obstacle primitives;
fresh permitted peer information; committed topology; local mission direction;
frozen topology geometry; frozen physical clearances.

Prohibited inputs: family id as a runtime feature; the `ScenarioLayout` object;
global corridor width; the passage entry coordinate directly; global obstacle
geometry; headroom category; any future outcome.

## S4 — runtime-local evidence origination

S4 no longer originates because `time >= 0.25 * episode_horizon` or any
equivalent fraction.

* Committed COMPACT: originate `local_constriction` at the first eligible
  control step at which the evidence predicate enters `LOCAL_LINE_REQUIRED`.
* Committed LINE: originate `local_opening` at the first eligible control step
  at which it enters `LOCAL_OPENING_FOR_COMPACT`, under the frozen S3
  hysteresis.

The event then goes through the real Phase 7 leaderless protocol. One robot may
detect first; that robot is **not** a leader. Propagation stays neighbour-only.
An event does not imply authorization — readiness still determines whether the
transition may commit. No global geometry is injected and no future outcome is
read. Duplicate, hysteresis and rearm behaviour use the already frozen source
and Phase 7 contracts unchanged. If local evidence never occurs, S4 correctly
produces no transition.

## S0 — offline geometry-scripted diagnostic origination

S0 remains an offline scripted diagnostic collection policy. It may read the
compiled landmark precisely because it is offline; robot-local deployment
claims do not apply to it. It may not read a headroom category or any future
rollout outcome.

Trigger derivation, with no event time in seconds hard-coded anywhere:

* **Constriction landmark.** The diagnostic fires at the earliest nominal local
  observability of the feature — the landmark position minus the approved local
  obstacle observation extent along the mission direction, evaluated over the
  nominal role template (see `PHASE8E_ET_MISSION_EVENT_LANDMARKS.md`).
* **Opening landmark.** The corresponding post-feature observability geometry,
  under the already frozen opening and hysteresis semantics.
* **Observable at initialization.** Where the frozen sensor and geometry
  contract makes the landmark visible at episode start — which is the case for
  F3, F4, F5 and F8 — the event may legitimately occur at the first eligible
  control step.
* **Sequence clamp.** A trigger is never earlier than its predecessor, so the
  declared per-family sequence cannot be reordered.

S0 never sets the topology directly. Every S0 event enters the normal Phase 7
protocol.

## S0 versus S3 versus S4 — distinct scientific roles

| policy | role | question it answers |
|---|---|---|
| S0 | offline geometry-scripted diagnostic event timing | what states are produced when a diagnostic event is scheduled at the physical observability landmark? |
| S3 | frozen deployable local geometric selector | what does a deployable local selector do? |
| S4 | runtime-local evidence-originated event timing | what states are produced when distributed robots themselves detect the local event and exercise the actual leaderless protocol? |

S0 and S4 may request the same topology at a similar moment, but their state
distributions are not aliases: S0's trigger is an offline geometric schedule
evaluated on the nominal template, while S4's is per-robot runtime evidence
subject to the actual observed obstacle set, message freshness, evidence
persistence and whichever robot crosses threshold first. They are not merged.

## Sampling slots are not event times

Phase 9 decision-state slots remain exactly `[0.10, 0.30, 0.50, 0.70, 0.90]`
for five-slot episodes and `[0.15, 0.40, 0.65, 0.90]` for four-slot episodes.
**These are data sampling times.** They are not source-policy transition event
times, they were not modified, and the 15,300 planned decision-event slots,
canonical job identities, seed mapping and generation budget are untouched.

## Horizon semantics

The episode horizon is frozen as: maximum rollout and evaluation duration;
timeout boundary; scientific denominator context. Using
`episode_horizon_fraction` as the sole detector of a physical source-policy
topology event is prohibited unless a future contract specifically defines a
purely temporal experiment. No current S0 or S4 physical topology event depends
on fraction-of-horizon timing.
