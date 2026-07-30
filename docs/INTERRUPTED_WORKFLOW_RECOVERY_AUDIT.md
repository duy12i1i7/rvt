# Interrupted-Workflow Recovery Audit

All checks below were run from a **clean clone** of
`research/decentralized-reconfiguration-v2` at `02d443b` in `/tmp/rvt_clean`,
with a fresh interpreter — never from the working tree or a warm session.

Interrupted phase: workflow `wf_a56fd379-1b7`, in which **all ten agents hit the
session limit and returned no result**. Four files nevertheless landed on disk
before the cutoff and were committed in `ffa70fa`.

---

## 1. Verdict

> ### **BLOCKING. Two deployable protocol components are partial and untested. Scenario requalification must not begin until Task 1 is complete.**

The headline finding is worse than "insufficiently tested":

**`epoch.py` (1202 lines) and `comm_cost.py` (1115 lines) are unreferenced dead
code. Nothing in `rvt_swarm/`, `tests/`, or `scripts/` imports either module.**

```
$ grep -rn "import epoch|from .epoch|import comm_cost|from .comm_cost" rvt_swarm/ tests/ scripts/
  (no matches outside the modules themselves)
```

Both import cleanly and look substantial. Neither has ever executed.

## 2. Correction to the seed-0 gate report

`FULLY_DECENTRALIZED_SEED0_GATE_REPORT.md` labels one arm
"periodic epochs (Task 6 protocol)". **That attribution is wrong.**
`runtime.py` does not import `epoch.py`; it re-decides on an inline
`step % decision_interval == 0` test. The arm therefore exercised:

| Task 6 component | actually exercised? |
|---|---|
| local trigger from clearance / progress / formation error | **no** — a fixed timer |
| `TriggerToken` deterministic conflict resolution | **no** |
| max-consensus trigger propagation | **no** |
| epoch state machine (IDLE/TRIGGERED/SCORING/CONFIRMING/COMMITTED) | **no** |
| **mode confirmation (min/max consensus)** | **no** |
| commitment duration `H_commit` | **no** |
| score consensus | yes (`consensus.py`) |

Two consequences:

1. **Gate D2's "mode-confirmation success ≥ 0.95" was never measured.** There is
   no confirmation step anywhere in the runtime. That half of D2 must be marked
   **NOT MEASURED**, not PASS.
2. Trigger and confirmation **communication costs were never measured**, because
   no such message is ever sent.

**What still stands.** The substantive conclusions of the gate report are
unaffected, because they rest on code paths that are real and covered:

- always-line succeeds in every validation family (forced modes → `local_controller`);
- consensus lifts success 0.250 → 0.861 and agreement 0.250 → 1.000 (`consensus.py`, 14/14 functions covered);
- `K_score = 1` collapses under delay (`consensus.py`);
- periodic re-decision degrades 0.861 → 0.611 — true, but of a *simplified periodic
  protocol*, not of the Task-6 design, which remains untested rather than disproved.

Recommendation **D** is unchanged and is if anything reinforced.

## 3. Confirmed defects

### D1 — `epoch.TriggerMessage.payload_bytes()` raises on any non-token input
`rvt_swarm/decentralized/epoch.py:270`
```
AttributeError: 'int' object has no attribute 'epoch_counter'
```
`payload_bytes()` assumes `trigger_token` is a `TriggerToken` and dereferences
`.epoch_counter` unguarded. Serialising a message whose token is an int — or the
default — crashes. Direct proof the function has never been executed.

### D2 — communication accounting measures a schema that does not exist
`rvt_swarm/decentralized/comm_cost.py:423–438`

`verify_schema_sizes()` self-reports the failure:

| message | declared | measured | provisional | ok |
|---|---|---|---|---|
| beacon | 49 B | 49 B | no | **true** |
| score_consensus | 20 B | 20 B | no | **true** |
| trigger | 16 B | **None** | **yes** | **false** |
| mode_confirmation | 17 B | **None** | **yes** | **false** |

`comm_cost.py` declares its own provisional `TriggerMessage`/`ConfirmMessage`
whose fields disagree with `epoch.py`:

```
epoch.py     : [sender_id, epoch_counter, trigger_flag, trigger_token, timestamp_step]
comm_cost.py : [sender_id, epoch_id, round_index, trigger_flag, trigger_epoch, timestamp_step]
```

Half of the four message categories are unverified. The 49-byte beacon figure
quoted in the gate report is sound; nothing else about trigger/confirm bytes is.

### D3 — empty exception handlers hide D2
`comm_cost.py:427` and `:438`
```python
except TypeError:
    pass          # signature unknown; verify_schema_sizes reports it
```
The comment is accurate but the behaviour is silent at the point of failure. A
schema mismatch between two modules in the same package should be an error, not
a skipped sample.

### Not defects
- `models.py:124` `raise NotImplementedError` — abstract method on
  `_SelectorBase`, overridden by both concrete selectors. Correct.
- No `TODO`, `FIXME`, `XXX`, `HACK`, pass-only function, placeholder return,
  skipped test, or xfail anywhere in the package.
- **Byte counts are not derived from Python object size.** No `sys.getsizeof`,
  no `pickle`, no `__sizeof__`. Every figure traces to an explicit `struct`
  format. This requirement is met.
- No fallback branch silently bypasses consensus. `use_consensus=False` sets
  `k=0` explicitly and is reported as its own labelled arm.

## 4. Function-level coverage, measured

`trace.Trace` over the full suite from the clean checkout:

| module | functions | exercised | classification |
|---|---|---|---|
| `comms.py` | 33 | **33** | complete and tested |
| `consensus.py` | 14 | **14** | complete and tested |
| `ego_graph.py` | 21 | **21** | complete and tested |
| `guards.py` | 14 | **14** | complete and tested |
| `roles.py` | 11 | **11** | complete and tested |
| `system_model.py` | 5 | **5** | complete and tested |
| `local_controller.py` | 4 | **0** | complete, insufficiently tested |
| `models.py` | 13 | **0** | complete, insufficiently tested |
| `runtime.py` | 3 | **0** | complete, insufficiently tested |
| `training.py` | 9 | **0** | complete, insufficiently tested |
| `epoch.py` | 38 | **0** | **partial / unused** |
| `comm_cost.py` | 40 | **0** | **partial / unused** |

**104 of 205 functions have no test.**

The middle group is not dead: `local_controller` produced the Gate D5 numbers,
`runtime` produced every closed-loop figure, `models`+`training` produced the
offline metrics. They are *validated by scripts, untested by the suite* — real
evidence, but not regression-protected. `epoch.py` and `comm_cost.py` are
validated by nothing.

## 5. Traceability

| requirement | file | function/class | dedicated test | status |
|---|---|---|---|---|
| T2 neighbour discovery | `comms.py` | `NeighbourTable`, `Beacon`, `RadioChannel` | `test_neighbour_discovery.py` (30) | **complete** |
| T3 robot-local ego graph | `ego_graph.py` | `build_ego_graph`, `feature_audit` | `test_ego_graph_locality.py` (12) | **complete** |
| T4 roles / pairwise geometry | `roles.py` | `RoleAssignment`, `pairwise_offset` | `test_pairwise_formation_geometry.py` (63) | **complete** |
| T5 leaderless consensus | `consensus.py` | `ConsensusNode`, `simulate_consensus` | `test_leaderless_consensus.py` (27) | **complete** |
| T11 locality guards | `guards.py` | `audit`, `assert_local_only` | `test_no_central_runtime_access.py` (16) | **complete** |
| T7 robot-local controller | `local_controller.py` | `local_controller` | **none** | **untested** |
| T8 selector models | `models.py` | `build_selector`, `EgoTrunk` | **none** | **untested** |
| T9 training protocol | `training.py` | `simulate_build_team_dataset` | **none** | **untested** |
| T12 closed-loop runtime | `runtime.py` | `simulate_decentralized_episode` | **none** | **untested** |
| **T6 decision epochs** | `epoch.py` | `EpochState`, `local_trigger`, `confirm_mode` | **none** | **PARTIAL / UNUSED** |
| **T6 mode confirmation** | `epoch.py` | `confirm_mode` | **none** | **PARTIAL / UNUSED** |
| **T10 communication cost** | `comm_cost.py` | `MessageAccountant` | **none** | **PARTIAL / UNUSED** |

## 6. Clean-checkout verification

```
330 passed, 1 warning in 35.96s          # tests/, fresh interpreter
guards.audit(): 0 violations
strict_enabled: True
```

The suite is green and the locality guard is clean — but per §4 the suite does
not reach the two blocking modules, so green does not mean covered. That is
precisely the failure mode this audit was asked to look for.

## 7. Required before Task 2

Per the Task 0B stop rule, scenario requalification is blocked until:

1. `epoch.TriggerMessage.payload_bytes()` is fixed and tested (defect D1);
2. `comm_cost` trigger/confirm schemas are reconciled with `epoch.py`, the empty
   handlers replaced by explicit failure, and `verify_schema_sizes()` reports
   `ok: true` for all four categories (defects D2, D3);
3. `epoch.py` and `comm_cost.py` have dedicated tests covering every function;
4. `runtime.py` either **uses** `epoch.py` or `epoch.py` is deleted — a 1202-line
   unreferenced protocol implementation must not sit in the tree implying
   coverage it does not have. Task 9 requires event-triggered epochs, so the
   former is the intended path;
5. Gate D2 is restated with mode-confirmation marked NOT MEASURED until a
   confirmation step actually runs.

Regression tests for `local_controller`, `models`, `training` and `runtime`
should follow, but they are not blocking: those paths have real script-based
evidence behind the reported numbers.
