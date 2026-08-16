# Phase 9D-R2 Recoverability Invalid Causal Audit

## Executive result

**PHASE 9D-R2 VERDICT: CATEGORY B — SOURCE_EVENT_ACQUISITION_DESIGN_FAILURE.**

All 5,557 dropped TRAIN events and all 1,380 dropped VALIDATION events terminated before their scheduled recoverability sampling step. They had no source snapshot, no candidate-local graph, no COMPACT counterfactual rollout and no LINE counterfactual rollout. Raw candidate `GENERATION_INVALID` executions were therefore **0**, not 11,114. The 11,114 TRAIN figure is two non-evaluated candidate slots for each of 5,557 unrealized source events, represented by prior final accounting as `GENERATION_INVALID`; it is not a count of failed candidate rollouts.

The terminal-before-capture ordering hypothesis is **REFUTED**. The producer rejects only when `session.control_step < task.resolved_control_step`. Terminal at equality falls through to `snapshot(session)`. Two existing events demonstrate this: one TRAIN `GOAL_COMPLETE` and one VALIDATION `COLLISION` at the exact scheduled step were snapshotted, evaluated and published with exactly `2*N` rows.

The frozen pair implementation is **CONFORMANT**. Infrastructure contamination is **0**. Category A, C and D contributions to dropped events are each **0** under their stated definitions. In particular, no labelable partner candidate was removed by pair atomicity because neither candidate was evaluated for any dropped event.

**Recommended next action: `PROSPECTIVE_SOURCE_ACQUISITION_PROTOCOL_V2_REQUIRED`.** This audit does not implement that recommendation.

## Authority, environment and scope

- Required and audited commit: `c16f16a97dca423e4c3ce15d2f7e398f1f98607e`.
- Audit branch: `research/rvt-phase9d-r2-recoverability-causal-audit-v1`.
- Initial worktree: clean; no submodules; `git fetch origin --prune` completed and the authoritative commit was verified.
- Local audit environment: macOS 26.5 arm64, Python 3.9.6, NumPy 2.0.2, PyTorch 2.8.0, pytest 8.4.2.
- Read-only extraction host: `100.71.102.9`, WSL2 Linux 6.18.33.2, Python 3.12.3.
- Existing dataset scientific source commit: `848e8b352a91e95af777ebbeccd5fbb43d53777e` for both splits.
- TRAIN manifest/seal: `4ac3d2cb65a8b5d656a5d982b344466868f8deaa8cef2b93af7ce824e9387caf` / `5b9e6726b548722ee651eefa7106662e2b119147d9b0c31ec4d4cbe0a1de58f5`.
- VALIDATION manifest/seal: `c991aa3016b38b524a14d9b7037b63d97c2cbbb7d92279fc5a297b9c55d4989e` / `c7583b124c573c52b57cd91dc1b54aff8fc02b33cf0a15d5449936a8d540637f`.
- Qualified generation image recorded by the finalized lineage: `sha256:8e26da918841eb146529bbb4ff95f3a55acf9793dcbc534f44dce0700d183a90`.
- FINAL and STAGING transaction paths were verified as the same files. All transaction, manifest, seal and scientific-row hashes validated.
- The read-only namespace checkpoint was unchanged before/after: 15,019 files, 483,189,906 bytes, inventory hash `d013f2c79d485871fc14aa45afb7130a9ab4b7edf6b79781af3d12f5aacda3ec`.

No official generation, Residual V2 generation, training, hyperparameter search, class-weight selection, checkpoint creation or scientific mutation occurred.

## Actual executable path

The complete stable source binding, including Git blob IDs and source-range hashes, is in `phase9d_r2_recoverability_execution_binding_v1.json`. The executable path is:

```text
SCENARIO_FAMILIES / generated layout
  -> build_phase9_job_manifest()
  -> map_event_slots()
  -> compile_recoverability_tasks()
  -> build_source_session()
  -> SimulatorEpisodeSession(... source_policy ...)
  -> _run_source_to_step()
       -> SimulatorEpisodeSession.step()
       -> SourcePolicy.observe() for each robot
  -> produce_recoverability_candidate(COMPACT or LINE)
       -> reject only terminal step < scheduled step
       -> snapshot(session)
       -> RobotLocalEgoGraphRuntimeAdapter.build() for each robot
       -> execute_candidate() for each matched replica
       -> build_execution_summary()
       -> evaluate_target_v4()
       -> _candidate_disposition()
  -> reconcile_recoverability_candidate_results()
       -> reconcile_candidate_pair()
       -> construct N COMPACT + N LINE rows only if both are labelable
  -> CanonicalGenerationWriter.write_recoverability_transaction()
       -> canonical temporary file + fsync + atomic replace
```

Important bindings:

| Stage | Actual symbol | Source lines | Branch/result |
|---|---|---:|---|
| Family/horizon | `SCENARIO_FAMILIES` | `rvt_swarm/phase8/scenario.py:181-263` | F1..F10 declare 90–180 s horizons |
| Sampling schedule | `map_event_slots` | `rvt_swarm/phase9b/identity.py:219-256` | fixed normalized slot -> `ceil(t/dt)` |
| Denominator | `build_phase9_job_manifest` | `rvt_swarm/phase9c/manifest.py:148-260` | all event IDs created as pending before source execution |
| Task binding | `compile_recoverability_tasks` | `rvt_swarm/phase9g0r/compiler.py:155-199` | fixed event step and candidate replica universe |
| Source run | `_run_source_to_step` | `rvt_swarm/phase9g0r/producer.py:133-139` | stop at target step or earlier terminal |
| Runtime order | `SimulatorEpisodeSession.step` | `rvt_swarm/phase9c_rb/session.py:473-568` | actual one-step ordering below |
| Capture gate | `produce_recoverability_candidate` | `rvt_swarm/phase9g0r/producer.py:235-289` | strict `<` is no-snapshot; equality is captured |
| Snapshot | `snapshot` | `rvt_swarm/phase9c_rb/counterfactual.py:140-209` | canonical state hash plus complete deep copy |
| Candidate rollout | `execute_candidate` | `rvt_swarm/phase9c_rb/counterfactual.py:320-401` | real protocol and simulator to terminal |
| Target | `evaluate_target_v4` | `rvt_swarm/phase8e/target.py:87-114` | invalid / positive / valid negative kept distinct |
| Aggregate | `_candidate_disposition` | `rvt_swarm/phase9g0r/producer.py:180-194` | raw candidate result before pair rule |
| Pair | `reconcile_candidate_pair` | `rvt_swarm/phase9g0r/contracts.py:487-530` | infra pending; invalid 0 rows; labelable exactly `2*N` |
| Publication | `write_recoverability_transaction` | `rvt_swarm/phase9g0r/writer.py:57-127` | duplicate-safe atomic transaction |

## Exact event/terminal ordering

Initialization performs role and initial-state construction, then rejects excessive initial speed, nominal-invalid geometry or an initial collision before control step 0 completes (`session.py:235-312`). For each nonterminal control step, the actual order is:

1. Communication physical edges are evaluated, state messages are sent, and currently due messages are delivered (`session.py:439-468`).
2. For each robot, local inputs are built and `source_policy.observe(...)` runs.
3. The Phase-6 controller evaluates; mission staging and the unchanged local safety projection run.
4. Source disturbance is added and safety projection is reapplied; safety infeasible/solver flags are recorded.
5. A nonfinite action terminates immediately as `NUMERICAL_INVALID` before integration and before clock advancement.
6. Semi-implicit dynamics integration updates velocity and position.
7. `control_step` and physical time increment; the communication channel advances.
8. Swept static, dynamic, world-boundary and robot-robot collision checks run.
9. Progress, irreversible-loss state, deadlock window, Metric-V3 dwell and goal dwell/goal completion run.
10. The topology-transition lifecycle runs.
11. If still nonterminal and horizon time is reached, `HORIZON_COMPLETE` is set.
12. `_run_source_to_step` returns when terminal or when `control_step == resolved_control_step`.
13. The capture gate rejects only `termination is not None AND control_step < resolved_control_step`.
14. Otherwise, including terminal at equality, `snapshot(session)` serializes and deep-copies the state; graph construction follows.

There is no separate geometry/progress recoverability-event predicate at runtime. The predicate is reaching the precompiled control step. Source-policy events such as S0 landmarks and S3/S4 local evidence affect source behavior, not the recoverability sampling schedule.

## Source termination paths

| Authoritative cause | Executable condition | Position relative to capture | Snapshot/current mapping | Scientific vs infra |
|---|---|---|---|---|
| `INITIALIZATION_INVALID` | initial speed over maximum, nominal initial validity false, or initial static/boundary/robot collision (`session.py:253-312`) | always before positive sampling steps | no snapshot; pair recorded nonpublished | scientific source termination |
| `NUMERICAL_INVALID` | any controller action is nonfinite (`session.py:537-542`) | before integration at current step; therefore earlier than a loop target that caused the step | no snapshot when target is later | scientific generation validity condition, not infra |
| `COLLISION` | swept static, dynamic or robot-robot clearance violation (`session.py:578-615`) | after integration and clock increment | earlier step: no snapshot; same step: snapshot | scientific task outcome |
| `WORLD_BOUNDARY_EXIT` | post-integration robot position exits world (`session.py:600-604`) | after integration and clock increment | earlier step: no snapshot; same step: snapshot | scientific task outcome |
| `PERSISTENT_DEADLOCK` | unpaused deadlock window lacks required progress (`session.py:665-678`) | after collision and progress update | earlier step: no snapshot; same step: snapshot | scientific task outcome |
| `GOAL_COMPLETE` | goal tolerance and required dwell both satisfied (`session.py:689-697`) | after collision/deadlock/dwell update | earlier step: no snapshot; same step: snapshot | scientific task outcome |
| `HORIZON_COMPLETE` | time reaches source horizon, or `run_episode()` finalizes it (`session.py:566-568,719-728`) | last terminal check | all Study-A slots are at or before 0.9H | scientific completion |

Safety infeasibility and solver failure set robot flags but do not terminate a source episode. No executable source-episode `TASK_FAILURE`, transition-abort or communication-failure terminal constructor exists in this session. Those conditions can affect candidate Target-V4 predicates without becoming source terminal causes.

Observed dropped-event causes were only:

| Split | `COLLISION` | `GOAL_COMPLETE` | `INITIALIZATION_INVALID` | Total |
|---|---:|---:|---:|---:|
| TRAIN | 3,517 | 1,920 | 120 | 5,557 |
| VALIDATION | 796 | 554 | 30 | 1,380 |

## Event scheduling semantics

`S0..S5` are six source-policy classes. They are **not** five recoverability event stages. The actual recoverability stages are `event-0..event-4`, scheduled at normalized source-horizon positions 0.10, 0.30, 0.50, 0.70 and 0.90. The manifest constructs every identity before running its source episode and marks availability `PENDING_SOURCE_EXECUTION`.

| Family | Horizon (s) | Scheduled control steps (`dt=0.15 s`) |
|---|---:|---|
| F1, F10 | 90 | 60, 180, 300, 420, 540 |
| F2 | 120 | 80, 240, 400, 560, 720 |
| F3 | 135 | 90, 270, 450, 630, 810 |
| F4, F9 | 150 | 100, 300, 500, 700, 900 |
| F5, F8 | 180 | 120, 360, 600, 840, 1080 |
| F6 | 130 | 87, 260, 434, 607, 780 |
| F7 | 110 | 74, 220, 367, 514, 660 |

These slots are time-based, not progress-, geometry- or event-predicate-based. They are not guaranteed reachable. An event identity can therefore exist after source terminal state even though no counterfactual state exists. This behavior is explicit and hash-frozen in the current manifest/compiler, not an accidental missing job; its scientific adequacy is the upstream design failure identified here.

## Candidate and pair semantics

For a realized source event, each candidate is independently cloned from the same snapshot. F8/F9 use three matched replicas; all other families use one. Candidate aggregate validity is evaluated before pair reconciliation: any replica `GENERATION_INVALID` invalidates that candidate; otherwise the aggregate label is all-replica success.

The pair contract then behaves exactly as frozen:

- both candidates labelable -> exactly N COMPACT rows plus N LINE rows;
- either candidate scientifically invalid -> zero rows;
- infrastructure failure -> unresolved/pending, zero rows and no scientific reconciliation.

All 563 realized pairs were labelable. No realized source snapshot led to COMPACT-only invalid, LINE-only invalid, both invalid, pair-only rejection or infrastructure failure. Across the 705 matched replica pairs, disturbance-seed mismatches and initial-clone-hash mismatches were both 0. The finalized matrix contains no partial rows, duplicates, stale pair transaction, timeout reclassification or candidate-dependent row leakage.

## Accounting reconstruction

| Quantity | TRAIN | VALIDATION |
|---|---:|---:|
| Scheduled source events | 6,000 | 1,500 |
| Realized source states/snapshots | 443 | 120 |
| Source event not reached | 5,557 | 1,380 |
| Candidate slots scheduled | 12,000 | 3,000 |
| Candidate aggregates actually evaluated | 886 | 240 |
| Candidate slots not evaluated: no source snapshot | 11,114 | 2,760 |
| Producer pre-pair enum `GENERATION_INVALID` (source unavailable) | 11,114 | 2,760 |
| Raw candidate rollout `GENERATION_INVALID` | 0 | 0 |
| Candidate aggregates removed only because partner was invalid | 0 | 0 |
| Retained/dropped pairs | 443 / 5,557 | 120 / 1,380 |
| Actual replica executions | 1,094 | 316 |
| Published robot-local rows | 8,340 | 2,294 |
| Potential `2*N` rows prevented by absent source state | 104,460 | 25,906 |

The prior 11,114/2,760 headline is arithmetically valid as final candidate-slot accounting, but causally misleading if called failed rollouts. It is `2 * source_event_not_reached`. Pair atomicity did not remove a valid partner candidate in any event. Changing reconciliation would not create the absent source state and would only hide or weaken the matched-pair contract.

Raw disposition combinations over all 7,500 events:

| Raw COMPACT | Raw LINE | Events |
|---|---|---:|
| `NOT_EVALUATED_NO_SOURCE_SNAPSHOT` | `NOT_EVALUATED_NO_SOURCE_SNAPSHOT` | 6,937 |
| `RECOVERABLE_POSITIVE` | `RECOVERABLE_POSITIVE` | 211 |
| `RECOVERABLE_POSITIVE` | `VALID_TASK_NEGATIVE` | 90 |
| `VALID_TASK_NEGATIVE` | `RECOVERABLE_POSITIVE` | 174 |
| `VALID_TASK_NEGATIVE` | `VALID_TASK_NEGATIVE` | 88 |

## Family, event-stage and N concentration

The complete split × family × event-stage × N matrix (500 cells) is in the causal summary JSON. Family-level realization is:

| Family | TRAIN realized / 600 | VALIDATION realized / 150 |
|---|---:|---:|
| F1 | 137 | 29 |
| F2 | 40 | 14 |
| F3 | 7 | 0 |
| F4 | 0 | 0 |
| F5 | 25 | 7 |
| F6 | 32 | 7 |
| F7 | 120 | 31 |
| F8 | 10 | 4 |
| F9 | 42 | 15 |
| F10 | 30 | 13 |

Later scheduled stages dominate the loss:

| Stage | TRAIN realized / 1,200 | VALIDATION realized / 300 |
|---|---:|---:|
| event-0 (0.10H) | 371 (30.92%) | 99 (33.00%) |
| event-1 (0.30H) | 35 (2.92%) | 12 (4.00%) |
| event-2 (0.50H) | 16 (1.33%) | 5 (1.67%) |
| event-3 (0.70H) | 13 (1.08%) | 3 (1.00%) |
| event-4 (0.90H) | 8 (0.67%) | 1 (0.33%) |

N is not the dominant axis. TRAIN realization rates for N=5,6,8,12,16 are 7.50%, 7.83%, 7.25%, 6.08%, 8.25%; VALIDATION rates are 7.67%, 7.33%, 8.00%, 9.00%, 8.00%. The strongest concentration is F3/F4/F8 and the later time slots, not one candidate topology or large N.

## Concrete event evidence

All records below are in `phase9d_r2_recoverability_event_causal_matrix_v1.jsonl`.

1. Collision before first event: TRAIN F1, N=12, `S2_ALWAYS_LINE`, episode 0, event-0. Source terminal step 27; scheduled step 60. Snapshot absent; COMPACT/LINE both `NOT_EVALUATED_NO_SOURCE_SNAPSHOT`; pair nonpublished.
2. Goal before later event: TRAIN F1, N=12, `S0_SCRIPTED_DIAGNOSTIC`, episode 0, event-1. Source terminal step 95; scheduled step 180. Snapshot absent; neither candidate evaluated; pair nonpublished.
3. Invalid initialization: TRAIN F4, N=16, `S0_SCRIPTED_DIAGNOSTIC`, episode 0, event-0. Source terminal step 0; scheduled step 100. Snapshot absent; neither candidate evaluated; pair nonpublished.

Same-step ordering controls:

- TRAIN F7, N=12, S0 episode 1, event-2: `GOAL_COMPLETE` at the scheduled step; snapshot exists; COMPACT valid negative, LINE positive; 24 rows published.
- VALIDATION F10, N=5, S3 episode 0, event-0: `COLLISION` at the scheduled step; snapshot exists; both candidates valid negative; 10 rows published.

## Infrastructure versus science

The finalized transaction evidence contains 1,410 completed replica infrastructure-attempt records, 0 exception attempts, 0 retries, 0 unresolved failures and 0 writer failures. Historical TRAIN lineage records two pre-A1C infrastructure timeouts and one startup launch failure before scientific execution; the closure audit records 0 timeouts during A1C, 0 unresolved infrastructure failures, 0 scientific retries, 0 writer failures and 0 regenerated existing rows. VALIDATION records 0 timeouts, retries, failure attempts, writer failures or unresolved failures.

No timeout, worker/process condition, missing result or writer state was converted into a valid negative or scientific invalid record. Source terminal causes are simulator outcomes, not infrastructure outcomes.

## Root-cause classification

For dropped events:

| Category | Contribution | Evidence |
|---|---:|---|
| A — implementation conformance defect | 0 / 6,937 | strict-before gate and two same-step captured controls |
| B — source-event acquisition design failure | 6,937 / 6,937 (100%) | terminal step strictly earlier; no snapshot/candidate audit |
| C — genuine counterfactual infeasibility | 0 / 6,937 | no realized snapshot had an invalid candidate aggregate |
| D — pair atomicity amplification of a partner loss | 0 / 6,937 | no one-invalid/one-labelable candidate pair occurred |
| E — multi-cause | not applicable | one supported primary cause explains every drop |
| F — insufficient evidence | 0 | final transaction provenance resolves every event |

The pair-level accounting multiplies one absent source event into two absent candidate slots, but that is not Category D as defined: no partner candidate was independently labelable and then removed. Both counterfactuals were never run.

## Required questions

**Q1. Of dropped TRAIN events, how many never had a realizable source snapshot?** 5,557.

**Q2. How many had a source snapshot but COMPACT alone was invalid?** 0.

**Q3. How many had a source snapshot but LINE alone was invalid?** 0.

**Q4. How many had both candidates independently invalid?** 0.

**Q5. How many candidate aggregates were removed only because their partner was invalid?** 0. No dropped event contained an independently labelable partner.

**Q6. How many dropped events are caused by implementation ordering rather than scientific semantics?** 0. The hypothesis is REFUTED.

**Q7. How many are infrastructure failures?** 0 unresolved/scientifically contaminating events.

**Q8. Which family/event-stage/N combinations dominate?** F4 is 0/600 TRAIN and 0/150 VALIDATION; F3 is 7/600 and 0/150; F8 is 10/600 and 4/150. Event-1..4 realization is at most 4% in either split and declines to 0.67%/0.33% at event-4. N rates remain close (approximately 6–9%), so N is not dominant. Exact 500-cell values are machine-readable.

**Q9. Does source termination usually happen before later scheduled events?** Yes. TRAIN realized events fall from 371 at event-0 to 8 at event-4; VALIDATION falls from 99 to 1.

**Q10. Does the current denominator count scheduled-but-never-realized events?** Yes: 6,000/1,500 scheduled versus 443/120 realized. This is explicit in the hash-frozen manifest construction, which creates event identities before source execution.

**Q11. Does any source event become `GENERATION_INVALID` even though no candidate rollout ran?** Yes: the producer emits pre-pair `GENERATION_INVALID` for both candidate wrappers on all 5,557 TRAIN and 1,380 VALIDATION dropped events. The causal matrix preserves that enum separately while recording the counterfactual rollout state as `NOT_EVALUATED_NO_SOURCE_SNAPSHOT`.

**Q12. Is 11,114 genuinely invalid rollouts?** No. Genuine raw candidate rollout invalids are 0. It is mainly two non-evaluated candidate slots per 5,557 absent source states.

**Q13. Would changing pair reconciliation address the root cause?** No. It cannot materialize a missing source snapshot and would only hide the upstream acquisition failure or break the matched-pair scientific unit.

**Q14. Is the frozen recoverability definition wrong, or is the problem upstream?** Existing evidence locates the defect upstream in source-state acquisition. Target V4, candidate execution and pair reconciliation are not implicated by these drops.

**Q15. Can the existing protocol be preserved unchanged after an implementation repair?** There is no supported implementation repair because implementation conforms. Target V4, candidate semantics and pair semantics can remain unchanged, but improving source-state realization requires a prospectively owner-approved acquisition Protocol V2; the current acquisition protocol cannot remain unchanged for that goal.

## Tests and artifact hashes

- Focused causal regression: 9 passed, 0 failed.
- First full-suite invocation without repo-root `PYTHONPATH`: 3,170 passed and 2 subprocess import failures (`ModuleNotFoundError: rvt_swarm` before either script executed).
- Authoritative full-suite invocation with `PYTHONPATH=/Users/udy/rvt`: **3,172 passed, 0 failed, 1 warning in 382.15 s**.
- Event matrix file SHA-256: `aaed92457552c40c45efc618b68bdf86dd69177d4fad092ef03afecdf78acfd1`.
- Causal summary canonical SHA-256: `a66b3106a5f71854b78eb27423e59365560a3b8528459af150af31ffda55f72d`.
- Execution-binding canonical SHA-256: `6ff45132ecbe84a31d4931bc0e5674fa29a641d7085a8cd8450088fd26a0512f`.

Artifacts:

- `results/rvt_fd24/phase9d_r2_recoverability_event_causal_matrix_v1.jsonl`
- `results/rvt_fd24/phase9d_r2_recoverability_causal_summary_v1.json`
- `results/rvt_fd24/phase9d_r2_recoverability_execution_binding_v1.json`

## Sealed-scope and stop evidence

- Study-A N24 dataset accesses: **0**.
- Study-B dataset accesses: **0**.
- Final-test dataset accesses: **0**.
- Training operations: **0**.
- Official generation operations: **0**.
- Residual V2 started: **NO**.
- Scientific repair implemented: **NO**.

This phase stops at diagnosis. No event scheduling, producer, simulator, Target V4, topology, pair, row, safety, controller, communication, lifecycle, timeout or randomness semantics were changed.
