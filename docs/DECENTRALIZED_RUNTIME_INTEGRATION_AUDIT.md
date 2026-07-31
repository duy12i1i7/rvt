# Decentralized Runtime Integration Audit (Task 3A)

Inspection of the **deployable call graph**, not of module imports. Baseline is
`b2c065f`, before any Task 3 change.

---

## 1. The six questions

| # | question | answer | evidence |
|---|---|---|---|
| 1 | Does `runtime.py` import `epoch.py`? | **NO** | no `epoch` in the import block; `runtime.py:106` keeps a bare `epoch_ids = [0] * n` list it manages itself |
| 2 | Does it use the epoch state machine in a real episode? | **NO** | `EpochState` never constructed; no phase ever leaves the implicit IDLE |
| 3 | Does it use mode confirmation? | **NO** | `confirm_mode` / `commit_or_retain` never called; modes are taken straight from `res["decisions"]` at `runtime.py:136` |
| 4 | Does it use `comm_cost.py` for messages actually transmitted? | **NO** | no import; no accountant anywhere in the episode loop |
| 5 | Does an inline periodic decision path remain? | **YES** | `runtime.py:120` — `if forced_mode is None and step % decision_interval == 0:` |
| 6 | Are there duplicate protocol implementations? | **No duplicate definitions, but one shadow implementation** | see §2 |

## 2. Duplicate-implementation check

Each protocol symbol has exactly **one** authoritative definition:

| symbol | defining module |
|---|---|
| `local_trigger`, `confirm_mode`, `EpochState`, `token_max` | `epoch.py` |
| `metropolis_weight`, `simulate_consensus`, `ConsensusNode` | `consensus.py` |
| `Beacon`, `NeighbourTable`, `simulate_broadcast_round` | `comms.py` |
| wire schemas, `MessageAccountant` | `comm_cost.py` |

There is no second copy of any function. What exists instead is a **shadow
implementation of the epoch concept** inside `runtime.py`: a plain
`epoch_ids: List[int]` incremented in lockstep for every robot
(`runtime.py:137`, `epoch_ids = [e + 1 for e in epoch_ids]`), plus a periodic
timer standing in for the trigger.

That lockstep increment is worth naming precisely, because it is the most
misleading part of the old runtime: **every robot's epoch id advances
simultaneously by construction**, so epoch agreement was guaranteed by the
harness rather than achieved by the protocol. Any measurement of
"decision-epoch synchronisation" against that code would have been vacuous.

## 3. Traceability, as of the baseline

| runtime requirement | runtime entry point | implementation module | function/class | integration test | status |
|---|---|---|---|---|---|
| neighbour discovery | `simulate_decentralized_episode` | `comms.py` | `simulate_broadcast_round` | none | **integrated, untested at episode level** |
| ego graph | `_robot_decision` | `ego_graph.py` | `build_ego_graph` | none | **integrated, untested at episode level** |
| score consensus | `simulate_decentralized_episode` | `consensus.py` | `simulate_consensus` | none | **integrated, untested at episode level** |
| robot-local control | `simulate_decentralized_episode` | `local_controller.py` | `local_controller` | none | **integrated, untested at episode level** |
| **local trigger** | — | `epoch.py` | `local_trigger` | unit only | **NOT INTEGRATED** |
| **trigger propagation** | — | `epoch.py` | `max_consensus_trigger` | unit only | **NOT INTEGRATED** |
| **epoch state machine** | — | `epoch.py` | `EpochState` | unit only | **NOT INTEGRATED** |
| **mode confirmation** | — | `epoch.py` | `confirm_mode`, `commit_or_retain` | unit only | **NOT INTEGRATED** |
| **communication accounting** | — | `comm_cost.py` | `MessageAccountant` | unit only | **NOT INTEGRATED** |
| periodic decision | `runtime.py:120` | `runtime.py` (inline) | `step % decision_interval` | none | **MUST BE REMOVED (Task 3B)** |

## 4. Consequence for previously reported numbers

Unit coverage of 38/38 and 40/40 was obtained by importing `epoch.py` and
`comm_cost.py` directly. That demonstrates the modules are correct in isolation;
it demonstrates **nothing** about the deployable runtime, which never calls
them. The distinction is exactly the one Task 3A was written to force.

Restating what this invalidates and what it does not:

- **Invalid:** any claim about mode-confirmation success, decision-epoch
  synchronisation, trigger propagation, or trigger/confirmation communication
  cost in a closed-loop episode. None of that code ran.
- **Still valid:** the score-consensus result (0.250 → 0.861 success,
  0.250 → 1.000 agreement), Gate D5's controller numbers, and the locality
  evidence. Those exercise `consensus.py`, `local_controller.py`, `comms.py`
  and `guards.py`, which are genuinely on the deployable path.

## 5. Gate

> Task 3A's stop rule — "do not continue until every deployable protocol
> component has exactly one authoritative implementation" — is **satisfied for
> definitions** (§2) and **violated for integration** (§3): five components have
> an authoritative implementation that the runtime does not call, and one
> component (periodic decisions) is implemented only inline, in the runtime,
> where it does not belong.

Tasks 3B–3D resolve this by deleting the inline path and routing the runtime
through `epoch.py` and `comm_cost.py`.
