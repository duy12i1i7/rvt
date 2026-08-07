# Phase 8E-PC — Executable Scientific Protocol Semantic Review

Independent review-only audit. No specification file was modified. No simulator
step, rollout, dataset row, checkpoint or optimizer state was produced. No
final-test geometry was compiled or inspected.

**Source commit (40 char): `554d44b6ae6c2f3fff04b0acdc503ecd6e31af4e`**
Branch: `research/rvt-executable-protocol-completion-v1`

---

## 1. Verdict

> ### **C — The executable scientific protocol is scientifically coherent, pre-data justified and sufficiently specified. Phase 9C-RB runtime binding may begin.**

No Severity 3 or 4 defect was found. Eight Severity 2 limitations are recorded
in §14; none invalidates H1–H3, because every method faces the same criteria
within the same scenario set. Two of them (§14.1, §14.2) constrain how results
may be *interpreted across families* and must be carried into the paper.

Not A: no semantic defect blocks binding.
Not B: the limitations are interpretive, not claim-invalidating.
Not D: the audit read the committed artifacts directly, not test names.

## 2. File provenance (SR-1)

Git alone **cannot** establish scientific authorship: every Phase 8E-PC file has
exactly one introducing commit, `554d44b`, because the files were staged but
uncommitted beforehand. The author field records the repository's committer
identity, not an authoring agent.

Filesystem metadata does separate them, and **corroborates** the previous
agent's account:

| artifact group | mtime | committed in | authorship |
|---|---|---|---|
| branch `…executable-protocol-completion-v1` created | 2026-08-04 01:28:37 (reflog) | — | — |
| 8 docs + 3 JSON contracts + 30 layout records | 2026-08-04 01:45–01:54 | `554d44b` | **unknown** — pre-dates the previous agent's session by 3 days |
| 12 `tests/test_phase8e_*.py` | 2026-08-04 01:52:53 | `554d44b` | **unknown** — same window |
| `rvt_swarm/phase8e/{artifacts,compiler,protocol,target}.py` | 2026-08-04 | `554d44b` | **unknown** |
| `tests/test_phase8e_keep_prohibition.py` | **2026-08-07 08:58:21** | `554d44b` | **previous agent** |
| commit created | 2026-08-07 09:02:30 | — | previous agent |

The claim "only the KEEP prohibition test was authored by the previous agent" is
**consistent with all available evidence**, and mtimes place a clean 3-day gap
around it. Caveat stated plainly: mtimes are mutable and are not cryptographic
provenance. No author identity is asserted beyond what Git and the filesystem
support.

## 3. Scenario geometry F1–F10 (SR-2)

Frozen references: spacing 0.9, robot radius 0.18, r_obs = r_comm = 3.0,
robot-robot clearance 0.40, robot-obstacle 0.55, ε_form 0.55.

| family | phenomenon isolated | width (m) | horizon | statics | dyn | passages | bypass | verdict |
|---|---|---|---|---|---|---|---|---|
| F1 | open field, no constriction | 4.0 | 90 | 2 | 0 | 0 | no | **PASS** |
| F2 | straight passage | 1.300–1.352 | 120 | 1 | 0 | 1 | no | **PASS** |
| F3 | offset entrance | 1.350–1.393 | 135 | 1 | 0 | 1 | no | **PASS** |
| F4 | curved / S-shaped passage | 1.400–1.443 | 150 | 1 | 0 | 1 | no | **PASS** |
| F5 | sequential bottlenecks | 1.400–1.443 | 180 | 2 | 0 | **2** | no | **PASS** |
| F6 | false bottleneck with bypass | 4.0 | 130 | 1 | 0 | 0 | **yes** | **PASS** |
| F7 | neutral clutter | 4.0 | 110 | 3 | 0 | 0 | no | **PASS** |
| F8 | communication degradation | 1.450–1.484 | 180 | 1 | 0 | 1 | no | **PASS** |
| F9 | dynamic obstacle | 4.0 | 150 | **0** | **1** | 0 | no | **PASS w/ limitation** |
| F10 | provably infeasible | 0.650–0.702 | 90 | 1 | 0 | 1 | no | **PASS** |

**Q6 — can families accidentally compile to equivalent environments?** No.
The four width-4.0 families are separated by obstacle content (F1: 2 statics;
F6: 1 static + bypass; F7: 3 statics; F9: 0 statics + 1 dynamic). F4 and F5
share a width range but differ by passage count (1 vs 2). Measured directly:
**0 duplicate semantic geometries** across all 30 records (identical
centerline + statics + width), and 30/30 distinct specification hashes.

**Q7/Q8 — geometry chosen to create a headroom category?** No.
`diagnostic_headroom_by_team_size` appears only in `audit_only_fields`; the
string "headroom" appears in **no** execution field of any record. Widths form a
monotone physical ladder (0.65 infeasible → 1.30–1.48 passage → 4.0 open) with
no gap tuned to a category boundary.

**Q9 — train/validation geometrically distinct?** Yes: 20 train + 10 validation,
all 30 hashes unique, with related but non-identical widths per family
(e.g. F2 1.3000 / 1.3132 / 1.3516).

## 4. Initialization (SR-3) — **PASS**

Every stochastic quantity carries distribution, bounds, frame, draw key and
reset behaviour:

| quantity | distribution | bound | frame |
|---|---|---|---|
| position perturbation | independent uniform closed | ±`spacing_margin` per component | mission |
| velocity perturbation | independent uniform closed | ±`max_speed·control_period` = **±0.135 m/s** | mission, rejected if speed > max |
| initial acceleration | deterministic | `[0.0, 0.0]` | — |

**Hidden-favourable-initialization checks, all negative:**
- Perturbations are **not** vestigial — ±0.135 m/s per component is 15 % of max speed.
- Initial velocity is **not** forced to zero (only acceleration is).
- **LINE does not get a favourable start.** `initial_topology.required_layout_value = 5` (COMPACT) for all 30 records, and S2_ALWAYS_LINE explicitly initialises at COMPACT poses then drives to LINE role targets — it does not spawn pre-formed.
- KEEP is `"prohibited"`, guarded by the test added at `554d44b`.
- `invalidity_handling: "record one rejected scientific slot; never resample or replace"` — no rejection sampling.
- Counterfactual matching gives both candidates the same realization (§9).

## 5. F8 communication (SR-4) — **PASS**

The contract separates the two classes explicitly and *before* runtime:

| profile | class | delay ≤ | drop | cut |
|---|---|---|---|---|
| bounded_delay_loss | `inside_method_assumptions` | 0.050 s | 0.020 | — |
| bounded_delay_loss | `inside_method_assumptions` | 0.093 s | 0.0415 | — |
| temporary_disconnection_then_restore | **`explicit_assumption_violation_stress`** | 0.061 s | 0.0255 | **3.6 s / 24 ticks**, partition ordinal 6 |

Classification is fixed in advance, not decided dynamically: Target V4
`protocol_resolved.assumption_violation = "valid task-negative, not
generation-invalid"`. That is the defensible choice — a method that cannot
tolerate a declared-out-of-assumption partition has legitimately failed the
task, and discarding those episodes would silently remove the hardest cases.

**Not trivial** (a 3.6 s cut is 8× `maximum_message_age` 0.45 s) and **not
universally fatal** (only 1 of 3 F8 layouts carries the cut).

**"Can F8 test communication robustness without changing physical difficulty?"
Yes.** F8 widths (1.450–1.484) sit in the same passage band as F4/F5
(1.400–1.443), so the physical task is comparable and communication is the
varied factor.

## 6. F9 dynamic obstacle (SR-5) — **PASS WITH LIMITATION**

Circle, radius 0.35, piecewise-linear timestamped waypoints, hold after final,
no looping, no reflection. Realised motion: (−0.5, −2.5) → (−0.5, +2.5) over
12.0 s — a **5 m lateral sweep at 0.4167 m/s**, i.e. **46 % of robot max speed**,
crossing perpendicular to the mission axis in a 4.0 m-wide region.

- **Sufficiently dynamic:** yes — it traverses the full corridor width during the
  episode; it is not effectively static.
- **Unavoidable collisions:** unlikely — 0.4167 m/s against 0.9 m/s robots in
  open space leaves evasion feasible.
- **No future leakage:** `future_trajectory_robot_visible: false`,
  `future_waypoints_robot_visible: false`; observation gated by
  `center distance <= obstacle_sensing_range_meters`, latency 0, noise disabled.
- **Matched candidates:** `"identical snapshot and dynamic_obstacle seed for
  both candidates"`.

*Limitation (§14.6):* the layout metadata declares
`declared_speed_meters_per_second_audit_only: 0.15` while execution runs
**0.4167 m/s** — a 2.8× discrepancy. The contract resolves it explicitly
(`"waypoint timestamps win because they form complete position-time pairs"`) and
records the rejected alternative, so it is not ambiguous; but a reader consulting
the layout record rather than the contract would be misled.

## 7. Source policies S0–S5 (SR-6)

| policy | deployability | information used | verdict |
|---|---|---|---|
| S0 scripted diagnostic | offline only | per-family normalized-horizon script table | **PASS w/ limitation** |
| S1 always COMPACT | diagnostic + collection | local only | **PASS** |
| S2 always LINE | diagnostic + collection | local only | **PASS** |
| S3 local geometric selector | **robot_local** | own state, one-hop msgs, ego obstacle discs, mission dir, local role metadata, lifecycle | **PASS** |
| S4 frozen transition protocol | offline only | role-0000 mission clock; constant score 1.0 | **PASS w/ limitation** |
| S5 bounded perturbation | offline only | S1 + one bounded accel impulse | **PASS** |

**S3 is the critical one and it is not an oracle.** Every threshold is derived,
none free:

| threshold | formula | class |
|---|---|---|
| required width | `candidate lateral role span + 2·(robot_radius + obstacle_surface_margin)` | topology + physical |
| COMPACT→LINE | width ≥ LINE-required **and** < COMPACT-required + `spacing_margin` | topology-derived |
| LINE→COMPACT | fully open **or** width ≥ COMPACT-required + **2**·`spacing_margin` | topology-derived + one explicit design factor |
| hysteresis | `spacing_margin_meters` | protocol-derived |
| min commitment | `protocol.commitment_seconds` | protocol-derived |

The asymmetric 1× / 2× margin is the only free choice; it is the standard
anti-chatter construction and is documented. S3 is **total**: `tie_behavior` =
hold, `unknown_behavior` = hold and emit no intent. It sees no family ID, no
headroom, no global width, no future.

**S4** exercises the real Phase 7 lifecycle (intent → score → readiness →
all-ready → confirmation → profile → dwell) with `diagnostic_score` a constant
1.0, so the score channel carries no future information. *Limitation (§14.4):*
`lifecycle_origination: "role-0000 only"` — a fixed originator. Propagation and
decisions remain leaderless, and S4 is offline-only, but S4's state distribution
systematically originates at one role.

**S5** does exactly what the phase demands: one perturbation
(`repeat_count: 1`), magnitude `0.25·max_accel`, uniform disk, robot chosen by
`seed mod team_size`, start at first tick ≥ `0.40·horizon`, and
`"record invalid without resampling if perturbed command is nonfinite"` —
**no rejection sampling for interesting states**, and sampling slots are
"not moved toward the perturbation".

**Do S0–S5 give genuinely different distributions?** Yes — S1/S2 are fixed-topology
holds, S0 is a scripted multi-transition oracle bypassing agreement, S3 is
geometry-triggered, S4 is clock-triggered through the full protocol, S5 is S1
plus an impulse. They are not six aliases.

## 8. Target V4 predicate review (SR-7)

Classification is a **clean three-way partition by construction**:

```
generation-invalid  ->  GENERATION_INVALID
else GOAL_COMPLETE and all ten predicates true  ->  RECOVERABLE_POSITIVE
else                                            ->  VALID_TASK_NEGATIVE
```

`valid_negative_rule = "generation valid and positive rule false"` is the
complement, so exactly one classification always results; `evaluation_precedence`
(8 groups) orders the *termination cause*, not the classification. 18 termination
causes are enumerated. `exception_policy`: "every exception becomes typed
EXECUTOR_EXCEPTION; never an implicit label".

| # | predicate | definition | disposition |
|---|---|---|---|
| 1 | collision | **continuous** — min distance of linearly interpolated centres over each closed interval; r-r 0.40 m; tol 1e-9 | valid negative |
| 2 | deadlock | fitted topology-origin displacement along mission longitudinal axis ≥ **0.05 m per 3.75 s** unpaused window; 7 protocol states paused | valid negative |
| 3 | commitment | all nodes commit in one lifecycle, no partial; candidate=current true without an epoch | valid negative |
| 4 | transition | Phase 7 profile reaches candidate tube without abort/timeout | valid negative |
| 5 | Metric V3 dwell | e_inf ≤ ε_form for **3.0 s**, interruption resets clock | valid negative |
| 6 | goal | **least-squares candidate topology origin** within 0.55 m, dwell 0.15 s | valid negative |
| 7 | protocol | failure states ABORTED / active-at-horizon / partial commitment; **assumption violation = valid negative** | valid negative |
| 8 | safety projection | conservative fallback is *not* failure; infeasible/solver failure latches | valid negative |
| 9 | numerical | all values finite and schema-valid | **generation-invalid** |
| 10 | irreversible progress loss | after a drop > `spacing` from max longitudinal progress, must return within `spacing_margin` before termination | valid negative |

**Specific concerns, answered:**
- *Between-step collisions?* No — checking is continuous over each closed
  interval, consistent with the linear-interpolation integration.
- *Topology-neutral deadlock?* Yes — the fitted **topology-origin** displacement
  uses the same estimator for COMPACT and LINE.
- *Readiness waiting mislabelled as deadlock?* No —
  `WAITING_FOR_LOCAL_READINESS`, `ALL_READY_AGREEMENT`, `TOPOLOGY_CONFIRMATION`,
  `TRANSITION_EXECUTION`, `TARGET_DWELL` and two others are paused states.
- *Escape deadlock by oscillating?* No — the metric is net displacement **along
  the mission axis**, so oscillation nets ≈ 0.
- *Does one topology get an easier goal?* **No** — this is the design's best
  detail. The goal quantity is the least-squares fitted topology origin, not
  "all robots within X" (which would penalise LINE's 4.5 m span) nor "any robot"
  (which would favour it).
- *Metric V3 dwell unchanged?* Yes — 3.0 s, ε_form entry, reset on interruption,
  matching the frozen L_recover semantics.
- *Method failures removed as invalid?* **No, and this is the critical polarity
  check.** Collision, deadlock, protocol abort/timeout, transition abort/timeout,
  safety infeasibility and irreversible progress loss are **all valid negatives**.
  Only initialization/geometry/schedule/numerical/schema/executor validity
  failures are generation-invalid. The contract does not discard hard failures.
- *Irreversible progress loss well-formed?* Objectively measurable (longitudinal
  progress vs running maximum), topology-neutral (fitted origin), non-redundant
  with deadlock (lost-and-not-recovered vs no-forward-motion), and fixed pre-data.

## 9. Counterfactual fairness (SR-8) — **PASS**

Matched on: initial snapshot hash, source lifecycle hash, horizon, communication
schedule identity, matched disturbance seed, dynamic-obstacle snapshot and seed,
runtime configuration. `clone_rule`: two independent deep clones with
**byte-identical canonical snapshot hash**. `candidate_injection_time`: same next
communication tick in both clones. `candidate_timeout`: remaining episode horizon,
**"no independent hidden timeout"**. Acceleration disturbance uses
`"same vector for matching robot and step"`.

Candidate-equals-current holds/continues and creates **no** source-equals-target
epoch; candidate-differs originates through the full Phase 7 protocol — so
neither candidate bypasses the protocol, and neither is charged an epoch it did
not need.

`aggregation: "all_success"`, `replicas: "one except three matched replicas for
F8 and F9"`. All-success is the conservative reading of recoverability: a
candidate counts positive only if it succeeds under *every* sampled realization.
It was frozen before generation. See §14.1 for the interpretive consequence.

## 10. Numeric constant audit (SR-9)

| constant | value | units | used by | source | class |
|---|---|---|---|---|---|
| robot-robot collision threshold | 0.40 | m | Target V4 #1 | frozen runtime config | **A derived** |
| collision tolerance | 1e-9 | m | Target V4 #1 | numerical guard | **A** |
| deadlock progress threshold | 0.05 | m | Target V4 #2 | design | **C** (§14.7) |
| deadlock window | 3.75 | s | Target V4 #2 | = `rearm_inactive_seconds` | **B inherited** |
| goal tolerance | 0.55 | m | Target V4 #6 | = ε_form | **B** |
| goal dwell | 0.15 | s | Target V4 #6 | = one control period | **A** |
| Metric V3 dwell | 3.0 | s | Target V4 #5 | frozen L_recover | **B** |
| position perturbation bound | ±`spacing_margin` | m | init | derived | **A** |
| velocity perturbation bound | ±0.135 | m/s | init | `max_speed·control_period` | **A** |
| accel disturbance magnitude | 0.05·`max_accel` | m/s² | counterfactual | derived | **A** |
| S5 perturbation magnitude | 0.25·`max_accel` | m/s² | S5 | derived fraction | **C** |
| S5 start time | 0.40·horizon | — | S5 | design | **C** |
| S4 event times | 0.25 / 0.65·horizon | — | S4 | design | **C** |
| S3 hysteresis factor | 1× vs 2×`spacing_margin` | — | S3 | anti-chatter design | **C** |
| F8 delay / drop | 0.050–0.093 s / 0.020–0.0415 | s, — | F8 | layout parameters | **C** |
| F8 cut duration | 3.6 (24 ticks) | s | F8 stress | design | **C** |
| F9 obstacle speed | 0.4167 | m/s | F9 | waypoint endpoints | **A derived** |
| F9 radius | 0.35 | m | F9 | frozen obstacle primitive | **B** |
| passage widths | 0.65–4.0 | m | geometry | family ladder | **C** |
| episode horizons | 90–180 | s | geometry | per-family | **C** |

**No class-unknown constant remains.** Every class-C value has a stated pre-data
rationale in its contract; none was selected from labels, success rates or model
performance (no model exists, and no rollout has been run).

## 11. Information-leakage audit (SR-10) — **PASS**

Static semantic audit of what can reach deployable code (S3, controller,
readiness, candidate score, ego graph):

| quantity | reachable by deployable code? |
|---|---|
| family ID | **no** — appears only in `source_layout` metadata and offline S0 script selection |
| headroom category | **no** — `audit_only_fields` only; absent from every execution field |
| future dynamic-obstacle trajectory | **no** — `future_trajectory_robot_visible: false` |
| global corridor width | **no** — S3 uses ego-relative obstacle support discs |
| complete obstacle geometry | **no** — observation gated by `obstacle_sensing_range_meters` |
| candidate rollout outcome | **no** — S4 score is a constant 1.0 |
| global progress / centroid | **offline evaluator only** (deadlock, IPL, goal use fitted origin) |

The simulator-global / robot-visible boundary is explicit: global state serves
physics, sensor rendering, the offline evaluator and dataset audit metadata; the
robot-visible set is enumerated per policy.

## 12. Compiled-layout audit (SR-11)

30 records (20 train, 10 validation), all 10 families, at least one train and one
validation record inspected per family.

- unique specification hashes: **30 / 30**
- duplicate semantic geometries: **0**
- initial topology: **{5 (COMPACT): 30}**
- headings: 29 distinct, range **[0.031713, 0.033307] rad** (§14.2)
- goal: x = **6.00 for all 30**, 1 distinct value (§14.3)
- every record `validity = COMPILED_SPECIFICATION`
- **Category D total: 0**
- no `final_test` specification directory exists

## 13. Hypothesis falsifiability (SR-12) — **PASS**

| hypothesis | fair opportunity to be falsified? |
|---|---|
| H1 recoverability vs direct/geometric selection | **Yes** — S3 is a genuine local geometric selector with derived thresholds; it can beat or match a learned selector |
| H2 online COMPACT↔LINE vs fixed policies | **Yes** — S1/S2 fixed baselines run the same physics, controller and safety projection; F6 (false bottleneck) and F7 (clutter) are cases where switching should *not* help |
| H3 decentralized vs centralized diagnostic | **Yes** — S0 is the centralized-style scripted oracle and shares physics, controller and safety projection with the deployable policies |

None of the bad-design patterns is present: constrained scenarios are not all
trivially LINE (F6 has a bypass, F7 is clutter without a passage), open scenarios
are not all trivially COMPACT (F9 injects a dynamic obstacle into open space),
no event type is exclusive to a learned method, fixed baselines are not given
impossible tasks (F10 is impossible for *everything*, by design, as a control),
and both-success/both-fail states are preserved by the width ladder.

## 14. Severity 2 limitations (documented, preserved, not repaired)

1. **Non-uniform positive criterion across families.** F8/F9 use three matched
   replicas with `all_success`; other families use one. For per-replica success
   probability `p`, the positive rate is `p³` vs `p`. F8/F9 will show
   systematically lower positive rates for a reason that is *criterion strictness*,
   not task difficulty. Method comparison within a family is unaffected;
   cross-family positive-rate comparison is confounded and must be reported as such.
2. **Mission heading is effectively constant.** All 30 headings lie in
   [0.0317, 0.0333] rad (≈1.82°, spread 0.09°). The frame is explicit, so the
   geometry is reproducible — but rotation invariance is never exercised, so a
   world-frame/mission-frame confusion would not be caught by this scenario set.
3. **Goal x is identical (6.00) in all 30 layouts.** Good for controlled
   comparison; means goal distance is not a studied factor.
4. **S4 originates only at role-0000.** Propagation stays leaderless and S4 is
   offline-only, but S4's state distribution is systematically origination-biased.
5. **S0's script is family-conditioned** on a normalized-horizon table, so S0
   states are not representative of what a deployable geometric trigger produces.
6. **F9 declared speed 0.15 m/s vs executed 0.4167 m/s** (2.8×). Explicitly
   resolved by the contract and the rejected alternative is documented, but the
   layout metadata alone would mislead.
7. **Deadlock threshold is permissive:** 0.05 m per 3.75 s ≈ 0.0133 m/s ≈ 1.5 %
   of max speed. Conservative in the safe direction (few false deadlock labels),
   but "no deadlock" is correspondingly a weak claim.
8. **`SAFETY_INFEASIBLE` and `SAFETY_SOLVER_FAILURE` are distinct termination
   causes but identically dispositioned** (both latch → valid negative). A solver
   defect would therefore be recorded as a task failure. The direction is the
   safer one (the phase warns against discarding genuine failures), and the
   distinct cause code preserves the information for post-hoc audit — but the
   rates should be monitored separately during generation.

## 15. Severity 3 / 4 defects

**None found.**

## 16–21. Structural re-verification (SR-14)

| item | value |
|---|---|
| executable protocol sha256 | `8da0b94e5ae83cf35ea38c38504d11d6e6fdce6da09766bf8cb14c4cc252158a` |
| source-policy contract sha256 | `aaf4e35a539d1ae864805ee52cfbd8be7579e7a61103e3807fbbc6d1706168df` |
| Target V4 execution contract sha256 | `54a0e0baff79fbdc320800b772f47a40ac06ac4f0e70d4fab1bf676c54b918ee` |
| full suite | **2082 passed**, 1 pre-existing warning |
| Category D | **0** |
| train layouts compiled | **20** |
| validation layouts compiled | **10** |
| simulator steps executed | **0** |
| dataset rows / shards | **0** |
| checkpoints / optimizer state under `results/rvt_fd24` | **0** |
| final-test runtime access count | **0** |
| final-test geometry compiled | **no** (`final_test` spec directory absent) |
| Study A N=24 access count | **0** — the single `24` occurrence is a docstring justifying world-bounds sizing (`phase8e/protocol.py:172`), not an access |

## 22. Recommendation

**Phase 9C-RB runtime binding may begin**, binding against
`executable_scientific_protocol_v1` (`8da0b94e…`) together with the frozen
Phase 8 protocol hash `0bb68dd5…` and Phase 9B budget hash `3853b8ad…`.

Two items to carry forward rather than discover later:

- record §14.1 in the generation report so F8/F9 positive rates are never
  compared to single-replica families without the replica-count caveat;
- instrument `SAFETY_SOLVER_FAILURE` separately from `SAFETY_INFEASIBLE` during
  generation (§14.8), so an implementation defect cannot masquerade as a task
  negative in aggregate.

Neither is a blocker for binding.
