# Phase 9C-RB Runtime Binding — Continuation Report

Branch `research/rvt-phase9-runtime-binding-final-v1`, created from the approved
ET commit `1457a892171a72b4c1b16938ccdd5245aeda127f`, which is tagged
`rvt-source-event-timing-addendum-v1`. No existing tag was moved.

**This phase is incomplete and is reported as such.** RB-A, RB-B, RB-C and the
blocking RB-D check are complete and formally tested. RB-7, RB-8, RB-9, RB-13,
RB-14, RB-15, RB-16, RB-17, RB-18, RB-19, RB-20 and RB-21 were not implemented.

---

## 1. Verdict

> ### **D — the implementation is incomplete.**

RB-D, the one gate that could have forced verdict A, is **resolved**: the F5
four-event sequence needs no unstated scientific choice. Everything implemented
so far is formally tested and passing. But the counterfactual half of the
pipeline — snapshot, clone, matched streams, candidate execution, Target V4
runtime evaluation, residual adapter, rotation fixtures, manifests and the
structural canary — does not exist, so gates RB-G7 through RB-G14 are
`NOT_EVALUATED`. Verdict C would assert a canary that was never run.

---

## 2. RB-D — the blocking check, resolved

**No queue duration, replay time, debounce interval, suppression rule or merge
rule had to be invented.**

F5's addendum plan at N=6:

| # | event | topology | landmark | trigger (m) |
|---:|---|---:|---|---:|
| 0 | `local_constriction` | LINE | `passage_entry-0` | -1.838 |
| 1 | `local_opening` | COMPACT | `passage_exit-0` | 3.502 |
| 2 | `local_constriction` | LINE | `passage_entry-1` | 3.502 |
| 3 | `local_opening` | COMPACT | `passage_exit-1` | 8.004 |

Events #1 and #2 share a trigger because the addendum clamps #2 up from its raw
observability position of 2.66 m. Two frozen rules decide the rest:

1. The S0 contract's retry field, verbatim: `"none; skipped or blocked script
   entries are not moved"`. An entry is **consumed at its trigger** whatever
   follows.
2. `request_candidate` refuses a candidate equal to the committed topology, so
   no source-equals-target lifecycle can open.

Therefore #2 is consumed at 3.502 m and is `NO_OP_ALREADY_COMMITTED` against the
already-committed LINE.

One residual ambiguity exists — whether a control step may consume one entry or
several — and it is **immaterial**: `test_both_admissible_readings_give_the_same_disposition`
runs both readings and both produce the identical disposition triple
(`ORIGINATED`, `ORIGINATED`, `NO_OP_ALREADY_COMMITTED`). An ambiguity whose
readings agree requires no scientific choice.

Every declared event now records an explicit, auditable disposition: ordinal,
event type, candidate topology, landmark, trigger, control step, time, committed
topology, protocol state, and outcome in
`{ORIGINATED, SKIPPED_ORIGINATION_BLOCKED, NO_OP_ALREADY_COMMITTED}`.

**Real F5 runtime outcome, reported honestly.** `train-f5-00` at N=6 under S0
originates event #0 at control step 0 and then terminates with `COLLISION` at
step 16 (t = 2.4 s), before reaching the 3.502 m co-trigger. The first bottleneck
entry is only 2.00 m from the topology origin, while the Phase 7 lifecycle plus
the frozen 3.0 s Metric V3 dwell needs roughly 4.7 m of lead distance at 0.9 m/s.
That is frozen physics and a valid task-negative under Target V4, not a timing
defect — and RB-D explicitly does not require every event to cause a transition.
It does mean F5's co-trigger is exercised by fixture rather than by a surviving
episode, which is why the fixture test above is the evidence.

---

## 3. RB-B — dynamic obstacle relative velocity

A real defect was found in the blocked implementation and fixed.

`RobotView.obstacles` carries no velocity, so the frozen
`ForcedTopologyRuntimeAdapter` assigns every entry `v_relative = -v_robot` —
correct for walls and circles. The blocked code put F9 obstacles into
**both** `RobotView.obstacles` and the corrected dynamic-state tuple, so each
dynamic obstacle entered the controller **twice**: once stationary, once
correct. The stationary duplicate would have driven the time-to-collision term.

Fix: `_build_robot_view` now emits static tokens only, and dynamic obstacles are
supplied solely through `_dynamic_obstacle_relative_states` with
`v_relative = v_obstacle - v_robot`. The controller and the TTC equations are
untouched.

Eleven tests in `tests/test_phase9c_obstacle_relative_velocity.py` cover the
static convention, robot-stationary, same-direction, opposite-direction,
velocity-matched, frame covariance at 30/90/137 degrees, the no-double-count
regression, and the direct assertion that a moving obstacle is never reported
stationary.

---

## 4. A second real defect: per-team-size runtime configuration

The blocked session always used `DEFAULT_RUNTIME_CONFIG`, whose
`mission.team_size` is 6. The frozen `TransitionProtocolNode` requires
`mission.team_size == len(member_ids)`, so **every team size except 6 raised**.
The session now derives `RuntimeConfig.for_team_size(N)` — the same approved
constructor the Phase 8E compiler used — and asserts its canonical hash equals
the compiled `runtime_configuration_sha256` for that team size, failing loudly
otherwise. All six qualified team sizes bind and initialise.

This is exactly the class of defect RB-A exists to catch: it was invisible to
direct execution at N=6.

---

## 5. RB-A — formal tests replacing direct-execution evidence

| RB-A item | file | result |
|---|---|---|
| 1 compiled layout -> binding | `test_phase9c_layout_execution_binding.py` | **PASS** — all 30 layouts, all 6 team sizes |
| 2 no legacy `start_center` | `test_phase9c_no_legacy_environment_binding.py` | **PASS** — AST-based, discriminates the approved field from the legacy attribute |
| 3 executor initialization | `test_phase9c_publication_executor.py` | **PASS** |
| 4/5 forced COMPACT / LINE | same | **PASS** |
| 6 F8 execution | partially — channel exercised, dedicated file not written | **PARTIAL** |
| 7 F9 execution | `test_phase9c_obstacle_relative_velocity.py` | **PASS** |
| 8 S0-S5 beyond step 0 | `test_phase9c_publication_executor.py` | **PASS** — all six, parameterised |
| 9 robot-local boundary | `test_phase9c_runtime_information_boundary.py` | **PASS** — 12 intervention tests |
| 10 Phase 6 equivalence | `test_phase9c_phase6_controller_equivalence.py` | **PASS** |
| 11 Phase 7 equivalence | dedicated file not written | **NOT_EVALUATED** |

The boundary tests are interventions, not inspections: moving a far robot,
mutating the binding's family and layout id, adding a distant circle to the
world, and perturbing evaluator state all leave robot 0's controller input
byte-identical, while moving a near peer or the robot itself changes it — so the
boundary is not trivially inert.

---

## 6. Work not performed

RB-7 snapshot/restore; RB-8 clone isolation; RB-9 matched streams; RB-13
counterfactual candidate executor; RB-14 Target V4 runtime evaluator; RB-15
residual-expert adapter; RB-16 synthetic rotation fixtures; RB-17 manifests;
RB-18/19 structural canary; RB-20 clean-checkout reproduction; RB-21 performance
micro-audit. Dedicated F8 and Phase 7 equivalence test files. The five required
`PHASE9C_*` documents other than this report.

Consequently **no** `scenario_runtime_binding_v1.json`,
`phase9_execution_protocol_v1.json` or canary namespace exists.

---

## 7. Gates

| Gate | Result |
|---|---|
| RB-G1 all layouts bind | **PASS** — 30/30, no new scientific choice |
| RB-G2 no legacy publication runtime | **PASS** |
| RB-G3 locality boundary | **PASS** — by intervention |
| RB-G4 Phase 6 equivalence | **PASS** |
| RB-G5 Phase 7 equivalence | **NOT_EVALUATED** |
| RB-G6 S0-S5 with ET semantics | **PASS** |
| RB-G7 snapshot/restore | **NOT_EVALUATED** |
| RB-G8 cloning and matching | **NOT_EVALUATED** |
| RB-G9 F8/F9 runtime | **PARTIAL** — F9 fully tested, F8 exercised but no dedicated file |
| RB-G10 Target V4 | **NOT_EVALUATED** |
| RB-G11 rotation tests | **NOT_EVALUATED** |
| RB-G12 structural canary | **NOT_RUN** |
| RB-G13 F5 multi-event semantics | **PASS** — no unstated choice |
| RB-G14 clean-checkout reproducibility | **NOT_EVALUATED** |
| RB-G15 final-test access = 0 | **PASS** |
| RB-G16 Study A N=24 access = 0 | **PASS** |
| RB-G17 no generation or training | **PASS** |

---

## 8. RB-22 no-scope-creep

Eight artifacts byte-identical, including the two approved ET artifacts:

| artifact | file SHA-256 |
|---|---|
| `executable_scientific_protocol_v1.json` | `342ae8b901315df2d178d7c8a0d2bdbfa8a659c99cfae1774d6d4211519ce770` |
| `source_policy_contracts_v1.json` | `c80f2a8d1fb608c27f5ec8d68d40eb88563a98e944cf84f8fc0d983086f8a8c5` |
| `target_v4_execution_contract_v1.json` | `a3abf73330314fdf332b0e9d69657dd1e9e1cae8a6ba53c83320186d8a2eb23c` |
| `generation_budget_v1.json` | `e12e42052fd48a6647b4b7fdac77db3a20340d550617ff196fb40b7541da5492` |
| `dataset_generation_protocol_v1.json` | `06284aae2a58fbc1b670bfa261ef40cdebb7c5cc46a1c24d13ef940272730a68` |
| `phase9_job_manifest.json` | `9d094d7dca34e2daf8edc05c018d0372d7c4d2219a710032a6b066be494ea49f` |
| `event_timing_static_audit_v1.json` | `65ea54b5fde4290eebb89eba08882133f653b966c680074e56302e1f3f756ab1` |
| `source_event_timing_addendum_v1.json` | `c7f0b3e9d75740706c6f1c21299ac59ef38bf7964f97b9cccdfded012880b875` |

Canonical content hashes unchanged: protocol `8da0b94e…`, source policy
`aaf4e35a…`, Target V4 `54a0e0ba…`, job manifest `801fe4e2…`, ET audit
`26562721…`, ET addendum `fba87e43…`.

No new layout, no changed mission length, speed, horizon, budget, sample slot or
seed. No class weighting, resampling, DAgger or training. No online KEEP. No
final-test geometry access. No Study A N=24 access. Strict-decentralization
violations 0. Dataset shards 0, checkpoints 0, optimizer states 0.

---

## 9. Blockers for full Phase 9 generation

1. RB-7 through RB-21 as listed in §6 — the entire counterfactual half of the
   pipeline plus the canary and its clean-checkout reproduction.
2. F5's first bottleneck sits 2.00 m from the topology origin while the frozen
   lifecycle plus the 3.0 s Metric V3 dwell needs roughly 4.7 m of lead at
   0.9 m/s. Under the repaired ET timing the event now fires at the earliest
   physically observable moment — step 0 — so this is no longer an event-timing
   problem. Whether F5 is expected to yield a completing S0 trajectory at all,
   or is intended to be a valid-negative-dominated family, is a scientific
   question worth settling before generation, since it will shape F5's label
   distribution. It is recorded here rather than acted on.

Full Phase 9 generation must remain blocked.
