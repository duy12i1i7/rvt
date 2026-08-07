# Phase 8E-PC-ET — Source Event-Timing Report

Branch `research/rvt-source-event-timing-addendum-v1`, created from the blocked
Phase 9C-RB commit `900a43f884dcb355bf544dd729e32a880cfd5f3a`, which is tagged
`rvt-phase9-runtime-binding-event-timing-blocked-v1`.

Specification-only. No simulator episode was run, no label produced, no dataset
row written, no model trained.

---

## 1. Verdict

> ### **C — The S0/S4 event-timing semantics are repaired and frozen. Phase 9C-RB may resume from the blocked implementation and continue RB-7 onward.**

Every declared S0 diagnostic event is now statically reachable before nominal
goal completion, in **180 of 180** (layout, team-size) cells. S4 no longer has a
clock trigger of any kind. No frozen physical constant, geometry value,
horizon, budget, job identity, seed or split changed.

Not A: no event is unreachable or ambiguous.
Not B: nothing frozen was altered; the six protected artifacts are byte-identical.
Not D: the audit is reproducible and its hashes verify.

---

## 2. This was a falsification, stated plainly

The original event timing was **fully specified and internally consistent**, and
it passed an independent semantic review that found Category D = 0. It was
falsified by the very first attempt to execute it, before any dataset row
existed.

That is the intended order. The cost was one blocked runtime-binding phase; the
alternative would have been 42,840 candidate rollouts in which S0 and S4 silently
produced COMPACT-hold trajectories and the recoverability dataset carried almost
no transition states. This is a pre-data protocol correction, not a post-hoc
adjustment: no label, no class distribution and no learned result informed it.

---

## 3. Failure attribution (ET-1)

All 30 layouts share a 12.01 m mission at a frozen 0.9 m/s, so an ideal
traversal takes at least **13.34 s**.

**19 of 19 declared S0 events and 20 of 20 declared S4 events were class C
(normally unreachable). Not one was class A.** None was class B or D — the
*intent* of every event was clear and correctly matched to a real physical
feature; only the trigger was wrong.

| family | H (s) | superseded S0 (s) | superseded S4 (s) | **new S0 trigger (s, N=6)** |
|---|---:|---|---|---|
| F1 | 90 | none | 22.5, 58.5 | **NO_EVENT** |
| F2 | 120 | 24.0, 78.0 | 30.0, 78.0 | **0.2, 8.9** |
| F3 | 135 | 27.0, 87.8 | 33.8, 87.8 | **0.0, 9.5** |
| F4 | 150 | 30.0, 105.0 | 37.5, 97.5 | **0.0, 10.0** |
| F5 | 180 | 27.0, 63.0, 99.0, 135.0 | 45.0, 117.0 | **0.0, 3.9, 3.9, 8.9** |
| F6 | 130 | 65.0 | 32.5, 84.5 | **2.4** |
| F7 | 110 | 36.3, 73.7 | 27.5, 71.5 | **1.6, 4.6** |
| F8 | 180 | 36.0, 126.0 | 45.0, 117.0 | **0.0, 9.4** |
| F9 | 150 | 49.5, 100.5 | 37.5, 97.5 | **1.8, 6.1** |
| F10 | 90 | 36.0 | 22.5, 58.5 | **0.1** |

Every superseded trigger exceeded 13.34 s. Every new trigger is at most 10.0 s.

The conclusion does not rest on the single `train-f2-00` execution that exposed
the problem; the table is derived from frozen geometry and speed for all ten
families independently of any run. That run (collision at t = 4.8 s, 19.2 s
before its scripted LINE event) is corroborating, not load-bearing.

---

## 4. Old versus new semantics

**S0** — offline geometry-scripted diagnostic.

| | superseded | repaired |
|---|---|---|
| trigger | normalized fraction of episode horizon | earliest nominal local observability of the corresponding landmark |
| constriction rule | — | landmark minus the approved observation extent, evaluated per template robot |
| opening rule | — | forward sector clears past the feature, under frozen opening hysteresis |
| absolute seconds present | yes | **no** |
| may read compiled landmark | n/a | yes (it is explicitly offline) |
| may read headroom or outcome | no | **no** |
| sets topology directly | no | **no** — every event enters Phase 7 |

**S4** — runtime-local evidence origination.

| | superseded | repaired |
|---|---|---|
| trigger | `0.25H` (LINE), `0.65H` (COMPACT) | first control step at which the frozen local evidence predicate enters `LOCAL_LINE_REQUIRED` / `LOCAL_OPENING_FOR_COMPACT` |
| originator | fixed `role-0000` | whichever robot detects first; **not** a leader |
| horizon-fraction trigger | yes | **no** |
| event implies authorization | — | **no** — readiness still gates commitment |
| no evidence | events fired anyway | **no transition**, correctly |

Replacing the fixed `role-0000` originator also retires the Severity 2
origination bias recorded as item 4 of the semantic review.

---

## 5. Local evidence predicate (ET-4)

Version `rvt-local-geometric-event-evidence/v1`, shared by S3 and S4,
implemented by the already approved
`rvt_swarm.phase8e.protocol.s3_local_geometric_decision`. **No second threshold
system was introduced.**

| declared state | frozen predicate value |
|---|---|
| `LOCAL_COMPACT_FEASIBLE` | `HOLD_COMPACT` |
| `LOCAL_LINE_REQUIRED` | `REQUEST_LINE` |
| `LOCAL_OPENING_FOR_COMPACT` | `REQUEST_COMPACT` |
| `LOCAL_GEOMETRY_UNKNOWN` | `HOLD_UNKNOWN` |

Prohibited inputs are enumerated and tested: family id as a runtime feature, the
`ScenarioLayout` object, global corridor width, the passage entry coordinate
directly, global obstacle geometry, headroom category, any future outcome.

---

## 6. Static reachability (ET-10)

`results/rvt_fd24/event_timing_static_audit_v1.json`, schema
`rvt-event-timing-static-audit/v1`.

* 30 layouts x 6 qualified team sizes = **180 cells**
* **180/180** have every declared event reachable before the goal
* **0** unreachable declared events
* every trigger lower bound is at most the minimum unconstrained traverse time
* `simulator_steps_executed: 0`

Observable at initialization (legitimate under ET-6): F3, F4, F5, F8.

---

## 7. Two findings worth recording

**F5 sequence inversion.** F5's second bottleneck entry becomes locally
observable at longitudinal **2.66 m** while its first bottleneck exit is at
**3.50 m**. A purely position-triggered plan would fire event #2 before event #1;
the #2 LINE request would then be a no-op against an already-LINE commitment and
F5 would collapse from two bottleneck cycles to one. The contract clamps each
trigger to be no earlier than its predecessor, preserving the declared
four-event sequence exactly as ET-2 requires.

**Template-aware observability is load-bearing.** F7's clutter circles sit at
|lateral| = 2.73–3.12 m against a frozen `R_obs = 3.0 m`. A point-mass test at
the topology origin calls several of them unobservable; a laterally offset
COMPACT role sees them. The observability rule is therefore evaluated over the
nominal role template, and that choice changes F7's classification.

---

## 8. F6 false bottleneck (ET-11)

F6 keeps exactly one reachable `local_constriction` event at 2.4 s, originated
from genuine local evidence at the central blocker. The event does **not**
encode that LINE is globally needed, that LINE will be committed, or that
COMPACT is unrecoverable — the distributed score, readiness and protocol
mechanics remain responsible. No headroom information suppresses or shapes the
event, and this is asserted by test rather than by prose. F6 remains available
for false-positive coverage.

---

## 9. No-event families (ET-12)

**F1 declares `NO_EVENT`**, and that is geometry rather than an omission: both
circles sit at |lateral| >= 3.06 m against `R_obs = 3.0 m`, so no topology event
is locally observable at any team size. Asserted directly by test.

No transition was forced into F1, F7 or F10 to make a policy "interesting", and
no event was deleted because both candidates might succeed or both might fail.
F10 keeps its single constriction with no opening — correct for a
provably-infeasible passage. F7 keeps both declared events.

---

## 10. Unchanged evidence

Six protected artifacts, byte-identical to the audited commit `554d44b`:

| artifact | file SHA-256 |
|---|---|
| `executable_scientific_protocol_v1.json` | `342ae8b901315df2d178d7c8a0d2bdbfa8a659c99cfae1774d6d4211519ce770` |
| `source_policy_contracts_v1.json` | `c80f2a8d1fb608c27f5ec8d68d40eb88563a98e944cf84f8fc0d983086f8a8c5` |
| `target_v4_execution_contract_v1.json` | `a3abf73330314fdf332b0e9d69657dd1e9e1cae8a6ba53c83320186d8a2eb23c` |
| `generation_budget_v1.json` | `e12e42052fd48a6647b4b7fdac77db3a20340d550617ff196fb40b7541da5492` |
| `dataset_generation_protocol_v1.json` | `06284aae2a58fbc1b670bfa261ef40cdebb7c5cc46a1c24d13ef940272730a68` |
| `phase9_job_manifest.json` | `9d094d7dca34e2daf8edc05c018d0372d7c4d2219a710032a6b066be494ea49f` |

Frozen job-manifest canonical hash remains
`801fe4e2bd694da0dda7c310226906e59d9bc5435d657fab2e3f132432aa2dc3`.

Also verified by test: max speed 0.9, max accel 0.6, robot radius 0.18, control
period 0.15, `R_obs` 3.0, spacing 0.9, formation tolerance 0.55; every family
horizon; start `x = -6.0` and goal `x = +6.0` in all 30 records; 20 train and 10
validation layouts; 15,300 decision-event slots; the five- and four-slot
sampling schedules.

---

## 11. Acceptance gates

| Gate | Result |
|---|---|
| ET-G1 no clock-horizon event bug | **PASS** — no S0/S4 physical event depends on absolute late time or a horizon fraction |
| ET-G2 S4 locality | **PASS** — origination uses only the frozen local evidence interface |
| ET-G3 S0 determinism | **PASS** — timing derives only from compiled geometry and frozen sensing |
| ET-G4 scientific distinction | **PASS** — S0, S3, S4 retain distinct roles; `aliases: false` |
| ET-G5 static reachability | **PASS** — 180/180 cells, 0 unreachable |
| ET-G6 false-bottleneck honesty | **PASS** — F6 event encodes no global correct topology |
| ET-G7 no post-hoc data use | **PASS** — `post_hoc_data_used: false`; no label or distribution exists |
| ET-G8 no physical retuning | **PASS** — six artifacts byte-identical; constants asserted |
| ET-G9 generation plan preserved | **PASS** — budget, slots, job identities, seeds unchanged |
| ET-G10 no execution | **PASS** — `simulator_steps_executed: 0`; no row, shard, checkpoint or optimizer state |

---

## 12. Blockers for resuming Phase 9C-RB

The §2 blocker that stopped the previous phase is resolved. What remains is the
implementation backlog that phase reported as unfinished, unchanged by this
addendum:

1. RB-7 complete snapshot/restore;
2. RB-8 candidate clone isolation;
3. RB-13 counterfactual candidate executor;
4. RB-14 Target V4 runtime evaluator;
5. RB-15 residual-expert adapter;
6. RB-16 synthetic rotation equivalence;
7. RB-17 execution manifests, RB-18/19 structural canary, RB-20 clean-checkout
   reproduction, RB-21 performance micro-audit;
8. the RB test files and four RB documents.

The resumed phase must consume both `source_policy_contracts_v1.json` and this
addendum, and its execution manifest must reference both hashes.
