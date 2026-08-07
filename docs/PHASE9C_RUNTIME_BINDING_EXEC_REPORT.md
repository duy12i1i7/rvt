# Phase 9C-RB Executable Runtime Binding Report

Branch `research/rvt-phase9-runtime-binding-exec-v1`, created from semantic-review
HEAD `018f73d35ef300366014a727567e43770c929130`.

**This phase is incomplete and is reported as such.** A blocking scientific
inconsistency was found while executing the binding, and a substantial part of
the RB-7…RB-22 scope was not implemented. Both are itemised below. No scientific
constant, contract, layout, budget, job or split was modified.

---

## 1. Verdict

> ### **A — Runtime binding still requires an unstated scientific choice.**

The mechanical binding *does* execute: a compiled `ScenarioLayout` execution
specification now runs as a closed-loop episode through the frozen Phase 6
controller, the frozen safety projection, the frozen Phase 7 protocol, the F8
channel and the F9 dynamic obstacle, under all six source policies, reaching
`GOAL_COMPLETE` on open-field layouts. That much of RB-1…RB-6 and RB-9…RB-12 is
demonstrated below.

It cannot be declared valid-and-reproducible (verdict C) for two independent
reasons:

1. **§2 blocker** — the frozen normalized-time schedules fire after the mission
   can physically end, so S0 and S4 degenerate to S1 in every family. Resolving
   that requires a scientific decision that no frozen document makes and that
   this phase has no authority to make.
2. **§6** — RB-7, RB-8, RB-13, RB-14, RB-15, RB-16, RB-17, RB-18, RB-19, RB-20,
   RB-21 and the required test files and documents were not implemented, so
   gates RB-G7…RB-G13 are `NOT_EVALUATED`, not passed.

---

## 2. Blocking finding — normalized script times exceed the achievable mission time

Every one of the 30 compiled layouts has the same mission length, because the
start origin and goal centre are frozen at `x = -6.0` and `x = +6.0`:

* mission distance **12.01 m** in all 30 layouts;
* platform maximum speed **0.9 m/s** (frozen);
* therefore **minimum achievable traverse time = 13.3 s**, before any formation
  constraint, obstacle detour, safety projection or transition dwell.

Measured against the frozen `machine_readable_script` and the frozen Phase 9B
decision-event slots:

| family | horizon H (s) | min traverse (s) | first S0 script event (s) | first event slot (s) |
|---|---:|---:|---:|---:|
| F1 | 90 | 13.3 | none (script empty) | 9.0 |
| F2 | 120 | 13.3 | **24.0** | 12.0 |
| F3 | 135 | 13.3 | **27.0** | 13.5 |
| F4 | 150 | 13.3 | **30.0** | 15.0 |
| F5 | 180 | 13.3 | **27.0** | 18.0 |
| F6 | 130 | 13.3 | **65.0** | 13.0 |
| F7 | 110 | 13.3 | **36.3** | 11.0 |
| F8 | 180 | 13.3 | **36.0** | 18.0 |
| F9 | 150 | 13.3 | **49.5** | 15.0 |
| F10 | 90 | 13.3 | **36.0** | 9.0 |

Consequences under the frozen semantics, executed exactly as written:

* **S0 can never fire a scripted transition.** Its earliest event in any family
  is 24.0 s; the mission cannot last past ~13.3 s unless the team is blocked.
  `S0` is specified as "one-shot … skipped, not moved", so the event is
  consumed-or-skipped, never rescheduled. S0 therefore behaves identically to
  S1 (hold COMPACT) in all ten families.
* **S4 can never fire either.** Its events are at `0.25H` and `0.65H`, i.e.
  22.5 s–117 s, all beyond the achievable mission time.
* **Most decision-event slots are unavailable.** Only the earliest slots
  (F1 9.0 s, F7 11.0 s, F2 12.0 s, F6 13.0 s) precede the 13.3 s bound, and
  even those only when the episode has not already terminated. The contract
  correctly says an unavailable slot "is never moved or replaced", so this is
  not an executor defect — it is a planned-capacity consequence.

This is verified behaviour, not a projection: running F2 at N=6 under S1
terminates with `COLLISION` at **t = 4.8 s** (control step 32), on entry to the
1.3 m passage in COMPACT, which is 19.2 s before S0's scripted LINE event.

**What this phase deliberately did not do.** It did not rescale the horizons,
retime the scripts, raise the maximum speed, shorten the missions, or make the
script times absolute rather than normalized. Every one of those is a frozen
scientific value, and the instruction "do not change a scientific constant merely
because runtime implementation becomes inconvenient" applies exactly here. The
decision of which quantity is wrong — horizons, script normalization, mission
length, or the intent that S0/S4 produce transitions at all — belongs to the
protocol owner.

---

## 3. RB-0 — frozen references

Tag `rvt-executable-scientific-protocol-v1` -> `554d44b6ae6c2f3fff04b0acdc503ecd6e31af4e`
(created, not moved).

| artifact | exact SHA-256 (file) |
|---|---|
| `executable_scientific_protocol_v1.json` | `342ae8b901315df2d178d7c8a0d2bdbfa8a659c99cfae1774d6d4211519ce770` |
| `source_policy_contracts_v1.json` | `c80f2a8d1fb608c27f5ec8d68d40eb88563a98e944cf84f8fc0d983086f8a8c5` |
| `target_v4_execution_contract_v1.json` | `a3abf73330314fdf332b0e9d69657dd1e9e1cae8a6ba53c83320186d8a2eb23c` |
| `generation_budget_v1.json` | `e12e42052fd48a6647b4b7fdac77db3a20340d550617ff196fb40b7541da5492` |
| `dataset_generation_protocol_v1.json` | `06284aae2a58fbc1b670bfa261ef40cdebb7c5cc46a1c24d13ef940272730a68` |
| `phase9_job_manifest.json` | `9d094d7dca34e2daf8edc05c018d0372d7c4d2219a710032a6b066be494ea49f` |

Self-declared canonical-content hashes, which are what the manifests reference
and which differ from the file hashes above:

| document | canonical content SHA-256 |
|---|---|
| executable protocol | `8da0b94e5ae83cf35ea38c38504d11d6e6fdce6da09766bf8cb14c4cc252158a` |
| source-policy contract | `aaf4e35a539d1ae864805ee52cfbd8be7579e7a61103e3807fbbc6d1706168df` |
| Target V4 execution contract | `54a0e0baff79fbdc320800b772f47a40ac06ac4f0e70d4fab1bf676c54b918ee` |
| frozen job manifest | `801fe4e2bd694da0dda7c310226906e59d9bc5435d657fab2e3f132432aa2dc3` |

Both are recorded because conflating them is how a manifest reference silently
stops matching.

---

## 4. What was implemented and demonstrated

New package `rvt_swarm/phase9c_rb/`, additive; no existing module was modified.

| module | scope | status |
|---|---|---|
| `streams.py` | RB-9 counter-keyed PRF; no mutable RNG object anywhere | implemented |
| `world.py` | RB-2 static collision truth + support-disc sensor conversion | implemented |
| `dynamics.py` | RB-11 F9 timestamped piecewise-linear obstacle | implemented |
| `channel.py` | RB-10 F8 delay/loss + partition cut | implemented |
| `binding.py` | RB-1 `ScenarioRuntimeBinding` + RB-2 adapter | implemented |
| `session.py` | RB-3 executor, RB-4 locality boundary, RB-5 Phase 6 adapter | implemented |
| `protocol_session.py` | RB-6 Phase 7 session adapter | implemented |
| `policies.py` | RB-12 S0–S5 | implemented |

Demonstrated by direct execution:

* **RB-1/RB-2.** `train-f2-00` at N=6 under S1 binds to a valid
  `ScenarioRuntimeBinding`, binding hash
  `562061cc644bc6aa1d0dd189fc817d3d40c2c764b69d09c632cd89fb0b29cf47`,
  validity `RUNTIME_BINDING_VALID`. The adapter rejects a specification whose
  protocol hash, Target V4 hash, schema, validity or Category-D count disagrees,
  and raises rather than defaulting when an initialization entry is missing.
* **RB-3/RB-19 gate 2.** All six source policies execute well beyond step 0.
  On `train-f1-00` at N=6 every policy reaches `GOAL_COMPLETE` in 95 control
  steps (14.25 s), with all robots in `STABLE_TOPOLOGY`.
* **RB-4.** Robot-local input is constructed only in `_build_robot_view`.
  Peers come from the delivered-message neighbour table, never the joint state;
  obstacles are range-gated ego-relative tokens. Stale messages are excluded
  using the frozen `maximum_message_age_seconds`.
* **RB-5.** The Phase 6 base action and safety projection are obtained from
  `ForcedTopologyRuntimeAdapter` -> `RobotLocalController` ->
  `RobotLocalSafetyProjection`. No controller equation or gain is restated.
  Dynamic-obstacle relative velocity is corrected with `dataclasses.replace`
  on the frozen adapter's output — the frozen adapter assigns every obstacle
  the static relative velocity `-own_velocity`, which would make an F9 obstacle
  look stationary to the time-to-collision term.
* **RB-6.** One `TransitionProtocolNode` per robot; agreement is evaluated with
  the frozen `evaluate_intent_propagation` / `evaluate_score_agreement` /
  `evaluate_readiness_agreement` / `evaluate_confirmation_agreement`. The
  session never computes a team-wide readiness or a central candidate choice.
  The F8 partition is applied to the protocol adjacency, so the protocol
  experiences the declared assumption violation itself rather than a separate
  abstract fixture cut.
* **RB-10.** `train-f8-01` at N=6: 234 cross-partition messages destroyed by
  the declared cut and 46 dropped by the bounded-loss process, with the two
  regimes counted separately per LIMITATION L1/L3 reasoning. The per-team-size
  schedule is read from the compiled record (`start_tick`, `duration_ticks`,
  `partition_ordinal`), not recomputed.
* **RB-11.** F9 executes from the timestamped waypoints, i.e. the realised
  0.4167 m/s, **not** the audit-only declared 0.15 m/s. `train-f9-00` at N=6
  terminates with `COLLISION` at step 41 — the obstacle crossing is materially
  active, not decorative. No robot receives waypoints or future velocity.
* **RB-12.** All six policies build and run. S3 drives the frozen
  `s3_local_geometric_decision` with a width statistic measured from its own
  ego-relative support discs; it receives no family id, headroom, global width
  or future value.

Frozen event vocabulary is respected: `externally_forced_diagnostic` for S0/S4,
`local_constriction` for COMPACT->LINE and `local_opening` for LINE->COMPACT.
An earlier draft used invented event names and was rejected at runtime by the
frozen `transition_messages` validator; that is recorded rather than hidden.

---

## 5. Secondary observations (not acted on)

* **F2/F10 in COMPACT collide on passage entry.** Expected physics: the COMPACT
  lateral span exceeds the 1.30 m and 0.65 m free widths. Under Target V4 this
  is a valid task-negative, which is the correct disposition — but combined with
  §2 it means the *only* families where a transition is needed are also the
  families where no source policy can produce one.
* **Slab-edge distance.** The corridor primitive is active only inside its
  world-x slab. A robot just outside the slab is given the exact Euclidean
  distance to the wall material on the slab face rather than an infinite
  clearance, so it cannot graze the slab edge. This is a computation of the
  frozen geometry, not an added semantic.

---

## 6. Work not performed

Stated plainly, because the gates below depend on it:

| item | status |
|---|---|
| RB-7 complete snapshot/restore | **not implemented** |
| RB-8 candidate clone isolation | **not implemented** |
| RB-13 counterfactual candidate executor | **not implemented** |
| RB-14 Target V4 runtime evaluator | **not implemented** (the pure typed evaluator `phase8e.target.evaluate_target_v4` exists and is unmodified; the runtime summary that feeds it does not) |
| RB-15 residual-expert adapter | **not implemented** |
| RB-16 synthetic rotation equivalence | **not implemented** |
| RB-17 execution manifests | **not written** |
| RB-18/RB-19 structural canary | **not run** |
| RB-20 clean-checkout reproduction | **not run** |
| RB-21 performance micro-audit | **not run** |
| all 20 `tests/test_phase9c_*.py` files | **not written** |
| `PHASE9C_SCENARIO_RUNTIME_BINDING_CONTRACT.md`, `PHASE9C_PUBLICATION_EXECUTOR.md`, `PHASE9C_COUNTERFACTUAL_STATE_CLONING.md`, `PHASE9C_RUNTIME_BINDING_CANARY_REPORT.md` | **not written** |

No test was added, so the suite count is unchanged at **2082**; the new package
is exercised only by the direct executions reported in §4. That is weaker
evidence than a committed test and is labelled as such.

---

## 7. Acceptance gates

| Gate | Result | Reason |
|---|---|---|
| RB-G1 unique binding | **PASS** | every checked compiled specification maps to one binding with no additional scientific choice |
| RB-G2 no legacy publication runtime | **PASS** | the package imports no historical KEEP/LINE closed-loop runtime and no legacy environment `start_center`; it uses the approved compiled `mission_frame.initial_topology_origin_meters` |
| RB-G3 locality | **PARTIAL** | boundary implemented and single-sited; no intervention test committed |
| RB-G4 controller equivalence | **PARTIAL** | frozen modules composed, not duplicated; no equivalence test committed |
| RB-G5 protocol equivalence | **PARTIAL** | frozen nodes and evaluators used; no fixture-equivalence test committed |
| RB-G6 source completeness | **PASS mechanically / FAIL scientifically** | all six execute past step 0, but S0 and S4 can never fire an event (§2) |
| RB-G7 snapshot completeness | **NOT_EVALUATED** | not implemented |
| RB-G8 matched candidates | **NOT_EVALUATED** | not implemented |
| RB-G9 F8/F9 execution | **PASS** | both execute from the approved contracts with the documented magnitudes |
| RB-G10 Target V4 | **NOT_EVALUATED** | runtime evaluator not implemented |
| RB-G11 rotation validity | **NOT_EVALUATED** | not implemented |
| RB-G12 structural canary | **NOT_RUN** | not implemented |
| RB-G13 reproducibility | **NOT_EVALUATED** | canary not run |
| RB-G14 final-test isolation | **PASS** | `load_execution_specification` refuses any split other than train/validation; final-test access count 0 |
| RB-G15 N=24 seal | **PASS** | Study A N=24 access count 0 |
| RB-G16 no scientific generation | **PASS** | no dataset shard, checkpoint or optimizer state created |

---

## 8. RB-22 no-scope-creep audit

Verified unchanged: the 30 compiled layout execution specifications, the
executable scientific protocol, the source-policy contracts, the Target V4
contract, the generation budget, the job manifest, topology geometry, controller
behaviour, safety semantics, transition semantics, Metric V3 and the split
manifests. No full dataset generation, training, DAgger, class weighting or
resampling occurred. No final-test geometry and no Study A N=24 record was
accessed. No online KEEP publication path exists — `ADMITTED_INITIAL_TOPOLOGIES`
is `(COMPACT,)` and `ADMITTED_CANDIDATES` is `(COMPACT, LINE)`.

---

## 9. Required resolution before generation can resume

1. Resolve §2. Either the episode horizons, the normalized script/event times,
   the 12.01 m mission length, or the expectation that S0/S4 produce transitions
   must change — as an approved protocol amendment, not as a runtime patch.
2. Complete RB-7, RB-8, RB-13, RB-14, RB-15 and RB-16 with their tests.
3. Write the four missing documents and the two execution manifests.
4. Run the structural canary and reproduce it from a clean detached checkout.

Full Phase 9 generation must remain blocked.
