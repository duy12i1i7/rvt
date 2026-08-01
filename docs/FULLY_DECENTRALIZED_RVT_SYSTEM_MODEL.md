# Fully Decentralized RVT System Model

## 1. Status and scope

This document is the normative Phase 1 information-boundary and system model
for the RVT-Swarm reconstruction.

- Approved reconstruction base: `1795809bcb2025bf9777cf08a5f6b287082732a6`
- Phase 0 audit commit used for this specification:
  `5d6aa95f0f04f4c4ab258eda48dca1095c563e77`
- Development branch: `research/rvt-swarm-fd24-v1`
- Scope: contracts, ownership, information flow, and current-code gap analysis
- Out of scope: runtime changes, new topology code, model reconstruction,
  residual actions, readiness consensus, data generation, training, and
  scientific experiments

The words MUST, MUST NOT, MAY, and OUT OF SCOPE are normative. A future phase
may refine an implementation detail, but it may not weaken a MUST or MUST NOT
without a new, explicit architecture decision.

This document distinguishes the intended deployable system from the selected
base. A row marked missing or partial is not evidence that the base already
implements the target architecture.

## 2. Strict claim boundary

The selected base establishes local-information primitives, a two-candidate
KEEP/LINE scorer, a leaderless finite-round protocol, and per-robot local
control. It does **not** currently establish any of the following:

- a COMPACT topology or a generic topology registry;
- a generic local readiness certificate or all-ready consensus;
- a learned decentralized residual action head;
- a distinct local safety-projection module with a formal projection contract;
- variable-team-size scientific validity;
- closed-loop scientific validity for `N = 24`;
- robustness to dynamic role reassignment, robot addition, or dropout;
- a production robot-process deployment adapter.

The preserved negative common-KEEP regression remains a known unresolved
result. Phase 1 neither overwrites it nor reinterprets it as a positive result.

Mechanical construction for a team size, where later demonstrated, is not a
scientific performance claim for that team size. Training labels, validation
metrics, and final-test results are never runtime inputs.

## 3. Execution domains

The same repository may contain centralized offline code and fully
decentralized runtime code. The boundary is defined by data flow, not by file
name.

| Domain | Permitted information | Permitted outputs | Runtime status |
|---|---|---|---|
| Centralized simulation | Joint simulated state, complete obstacle state, radio/link simulator state, scenario geometry, random seeds | Synthetic sensor packets, one-hop message deliveries, dynamics transitions, raw episode traces | Prohibited on a robot; it replaces the physical world and device drivers |
| Counterfactual label generation | Frozen training traces, joint state, oracle rollouts, candidate topology outcomes, expert actions | Training labels and label provenance | Centralized training-only |
| Centralized training | Training split examples, counterfactual labels, batched local ego graphs, optimizer state | Shared model parameters, normalizer/config metadata, training diagnostics | Centralized training-only |
| Validation | Validation split traces and global validation metrics | Model-selection decision and validation report | Centralized evaluation-only; may select but may not train on validation examples |
| Deployable runtime | One robot's information set `I_i(t)`, shared immutable configuration, shared frozen model parameters | That robot's messages, protocol state, topology commitment, and actuator command | The only domain allowed to produce a physical command |
| Offline evaluation | Frozen evaluation traces, joint state, global metrics, communication logs, ground truth | Reports, plots, aggregate metrics, failure attribution | Centralized evaluation-only; no within-episode feedback to runtime |

Final-test layouts and results MUST NOT enter counterfactual labeling,
training, normalization, threshold selection, validation-driven model
selection, or runtime configuration.

### 3.1 Serialization firewall

A deployable example, checkpoint input schema, or runtime message MUST NOT
serialize a training-only global feature. In particular, it MUST NOT contain:

- joint positions or velocities;
- a full-swarm graph or global pooled embedding;
- global centroid, global formation error, global minimum clearance, or global
  time-to-collision;
- complete obstacle maps or out-of-range robot states;
- oracle outcome, counterfactual return, expert action, or future trajectory;
- layout identity, final-test membership, or a split-specific statistic;
- centralized topology choice, centralized event trigger, or joint action.

It is valid for shared model weights to have been learned from centralized
labels. The labels themselves and any label-only feature MUST NOT be an input
to the deployed model. A deployable checkpoint MAY contain model weights,
declared input normalization constants fitted on the training split, topology
metadata, and an immutable schema version. It MUST NOT contain per-layout
state or hidden oracle features.

## 4. Formal decentralized runtime model

Let the configured robot identities be `V = {0, ..., N-1}`. Robot `i` has
physical state `x_i(t)`, persistent role `rho_i`, local memory `m_i(t)`, and
committed topology `tau_i(t)`. Let `C` be shared immutable configuration and
`theta` be shared frozen model parameters.

The complete information available to robot `i` at runtime is

```text
I_i(t) = {
  own state,
  own persistent role,
  current local observations,
  fresh messages received from one-hop peers,
  local protocol and controller memory,
  shared immutable configuration
}.
```

More formally,

```text
I_i(t) = {x_i(t), rho_i, O_i(t), M_i^fresh(t), m_i(t), C}.
```

All robot decisions and physical actions MUST be functions only of this set
and shared frozen parameters:

```text
intent_i(t)     = f_intent(I_i(t); theta)
score_i(tau,t)  = f_score(I_i(t), tau; theta)
ready_i(tau,t)  = f_ready(I_i(t), tau; theta)
commit_i(t)     = f_protocol(I_i(t), m_i(t))
u_base_i(t)     = f_base(I_i(t), commit_i(t))
delta_u_i(t)    = f_residual(I_i(t), commit_i(t); theta)
u_i(t)          = f_safe(I_i(t), u_base_i(t) + delta_u_i(t))
```

The residual and readiness functions are target interfaces, not claims about
the selected base. Every robot computes only its own `u_i(t)` and sends only
that command to its own actuator. There is no runtime function
`F(x_0, ..., x_(N-1)) -> (u_0, ..., u_(N-1))`.

### 4.1 Own state and local observations

Own state MAY include the robot's own pose, velocity, clock, battery or health
flags required by a declared controller, and local state-estimator covariance.
Local observations MAY include range/bearing detections inside the physical
sensor footprint, locally estimated obstacle motion, and direct-link status.
They MUST NOT be silently completed from simulator ground truth.

On hardware, the local observation builder consumes device-driver data. In
simulation, a centralized boundary MAY synthesize the same local tuples from
joint ground truth. The centralized boundary output must satisfy the same
schema and visibility limits as the physical sensor interface.

### 4.2 One-hop messages

`M_i^fresh(t)` contains only messages actually delivered to `i` by its current
one-hop communication links and accepted by the freshness/sequence contract in
Section 7. A message may contain sender-local values and protocol accumulators
computed from previously accepted messages. For example, a peer may disclose
its local neighbor degree or a propagated epoch token. This is still a
one-hop message input; it does not authorize forwarding raw third-party state.

### 4.3 Local memory

Local memory belongs to one robot process. It MAY contain accepted sequence
numbers, neighbor-table entries, finite histories of that robot's observations,
protocol epochs, proposal/confirmation state, and controller integrator state.
It MUST NOT be a shared mutable array indexed by all robots. Simulation MAY
store all local-memory objects in one host process only if each update receives
one robot's view and one robot's inbox, and no object can inspect another
robot's memory.

### 4.4 Shared immutable configuration

`C` MAY contain platform constants, sensor and communication limits, timing,
the configured identity set, role definitions, topology definitions, declared
temporal-diameter bounds, model schema, and protocol constants derived before
an episode. It MUST be immutable during an episode and MUST NOT encode a
layout-specific solution or measured global runtime state.

## 5. Coordinate-frame contract

The system uses four explicit frame concepts:

| Frame | Definition | Allowed use |
|---|---|---|
| Robot/body frame `F_i` | Origin at robot `i`; orientation from its own state estimator | Raw local sensing and actuation |
| Shared mission orientation `R_M` | Immutable 2-D orientation established before deployment | Rotate role offsets and mission direction consistently |
| Role frame `F_R` | Static role coordinates with arbitrary origin and orientation `R_M` | Persistent role metadata and pairwise desired offsets |
| Simulator/world frame `F_W` | Centralized coordinate system of the simulator | Simulation and offline evaluation only, except a robot's own estimate or a peer pose explicitly sent on the wire |

For topology `tau`, role `rho_i` has static coordinate `r_i^tau`. Robot `i`
computes a pairwise desired displacement without a centroid:

```text
d_ij^tau = R_M (r_j^tau - r_i^tau).
```

The global origin of `F_R` cancels. No runtime formation term may require a
swarm centroid. A wire protocol MAY transmit the sender's own pose in a shared
mission-aligned frame; the receiver MUST transform it to a relative record
before feature construction. Frame ID, orientation convention, units, and
timestamp semantics are immutable configuration and message-schema fields.

Dynamic frame realignment based on all robot poses is prohibited at runtime.
Each run must declare whether `R_M` is aligned to a fixed mission heading or
to a predeclared goal direction. A robot may estimate its own heading relative
to that convention; it may not recompute the convention from a runtime swarm
centroid or a centralized aggregate.

## 6. Persistent role contract

Each configured robot ID has exactly one persistent role record containing a
role identity and one coordinate for every registered topology. Roles are
loaded before runtime or derived during an explicitly declared mission-setup
boundary before `t = 0`.

Runtime requirements:

- role identity remains unchanged across topology transitions;
- peer roles are learned only from fresh peer messages or immutable preloaded
  team metadata;
- formation control uses pairwise role offsets, not centralized assignment;
- a missing peer leaves its role unobserved/unoccupied; another robot does not
  silently take that role;
- every topology candidate must define the role or return an explicit
  unsupported-configuration result.

Dynamic reassignment, addition/removal of robots, replacement of a dropped
role, and post-dropout formation repair are OUT OF SCOPE. No attrition or
dropout-recovery claim may be made from this contract.

## 7. Communication and topology contract

### 7.1 Neighbor definition

At protocol round `k`, directed edge `(j, i)` exists only when the communication
driver delivers a valid message from `j` to `i` under the configured radio
contract. In simulation the radio boundary may derive edges from range, loss,
and delay. A robot does not inspect the global adjacency matrix or infer links
that did not deliver a message.

The accepted direct-neighbor set is

```text
N_i(k) = {j | a valid, fresh, one-hop message from j is accepted by i at k}.
```

Sensor detections are not communication neighbors unless identity-bearing
communication also satisfies this rule.

### 7.2 Freshness and duplicate suppression

Each runtime message has a sender ID, message type/schema version, sender
timestamp or protocol round, monotonic sequence number, and protocol epoch
where applicable.

- Future-dated messages are rejected.
- Messages older than `delta_stale` are rejected.
- A duplicate or out-of-order `(sender, message type, epoch, sequence)` is
  rejected after the first accepted copy.
- Cached peer state expires after `delta_stale`; expired state is not padded
  from ground truth.
- Epoch-specific messages are ignored outside their compatible local epoch.
- Sequence wraparound, if supported, must be explicit in the schema.

### 7.3 Bounded delay and diameter

Let `B_msg` be the declared upper bound on delivery rounds for an accepted
message. Let `D_graph` be the declared diameter bound for the required temporal
communication graph. Phase 2 must derive a causal propagation bound
`D_causal = g(D_graph, B_msg, scheduling semantics)` rather than insert an
unexplained constant. Intent, score, readiness, and confirmation round counts
must each satisfy their declared propagation requirement, normally

```text
k_phase >= D_causal.
```

A proof or mechanical test must use the same round and delay semantics as the
runtime. A static shortest-path diameter is insufficient when delay or
time-varying links are claimed.

### 7.4 Temporary disconnection

The propagation claim is conditional on the declared temporal-connectivity
contract. A short disconnection is tolerated only if the temporal union still
satisfies `D_causal`. If the bound is violated, affected robots must retain the
current topology, mark readiness/confirmation UNKNOWN or abort the epoch, and
start a fresh epoch after communication is restored. They MUST NOT silently
commit a partition.

Two claim scopes are distinct:

- **Component scope:** a theorem or diagnostic may report agreement within
  each communication component that satisfied its own temporal contract.
- **Swarm scope:** a topology commitment may be called swarm-wide only when
  all configured persistent role IDs belong to the connected temporal graph
  for that epoch and the full-team propagation/confirmation contract holds.

Component agreement is not swarm agreement. A component-local success metric
must not be reported as full-team commitment.

## 8. Leaderless protocol contract

An originator is the robot that first emits an epoch token after a local event.
It is not a leader. Concurrent tokens are resolved using an immutable total
order that every robot can compute from token fields. The winning token
identifies the epoch; it does not choose the outcome.

The originator MUST NOT:

- choose the final topology for peers;
- bypass intent, score, readiness, or confirmation propagation;
- read global state, global metrics, or a global adjacency matrix;
- issue a joint action or another robot's actuator command;
- force commitment when any required certificate is UNKNOWN or UNSAFE;
- retain special authority after token propagation.

Every robot independently computes local candidate scores and local readiness,
updates the same distributed protocol from its own inbox, and commits only
after the declared confirmation rule is satisfied. Deterministic tie-breaking
is shared static logic, not centralized arbitration.

## 9. Runtime information matrix

The following matrix is normative for the target architecture. A dash means the
component receives no input in that category.

| Component | Robot-local inputs | Peer-message inputs | Shared static inputs | Training-only inputs | Forbidden inputs | Outputs |
|---|---|---|---|---|---|---|
| Local observation builder | Own state-estimator output, local sensor detections, local clock and memory | Fresh beacon payloads, transformed immediately to relative peer records | Sensor/radio limits, units, frame schema, stale horizon | Simulator joint state only behind the simulation adapter | Full map, out-of-range state, global centroid, future state | One `RobotView` for robot `i` |
| Ego-graph builder | One `RobotView`, own committed topology | Relative fresh peer records already in the view | Feature schema, local radius/caps, candidate topology registry | Dataset batching metadata outside graph features | Full-swarm graph, global pooling, padded hidden robots, global metrics | Candidate-conditioned local graph `G_i^tau` |
| Topology registry | Own role ID when resolving one role | Peer role IDs only when pairwise offsets are requested | Immutable topology IDs, role coordinates, support constraints | Training curriculum metadata outside runtime registry | Runtime centralized assignment, layout-specific topology, dynamic oracle choice | Validated role/topology records or unsupported result |
| Recoverability encoder and head | `G_i^tau`, own local memory if declared | Only peer data represented in `G_i^tau` | Frozen weights `theta_rec`, normalization/schema | Counterfactual labels and losses during training only | Oracle return, global label, joint graph, global pooled embedding | Local score or calibrated recoverability value `q_i(tau)` |
| Residual-action head | Local encoder state, own base action, own limits | Only encoded fresh peer records | Frozen weights `theta_res`, residual bounds | Expert residual target and imitation loss | Expert action at runtime, joint action, global safety signal | Bounded local residual `delta_u_i` |
| Local base controller | Own state, role, local observations, committed topology | Fresh relative peer state and peer role | Controller gains, limits, pairwise role offsets | Expert-generation diagnostics only | Centroid, centralized target assignment, another robot's command | Own nominal action `u_base_i` |
| Local safety projection | Own state, proposed own action, local obstacle detections | Fresh relative peer state and declared peer intent if schema permits | Robot geometry, acceleration/speed limits, safety margins | Offline feasibility labels only | Global collision oracle, future joint trajectory, centralized QP over all actions | Own feasible projected action `u_i` or explicit infeasible status |
| Transition-intent generator | Local trigger evidence, local epoch state | Fresh propagated intent tokens | Token order, timing and propagation bounds | - | Central event trigger, global exit plane, global progress | Local epoch token and intent messages |
| Score consensus | Own candidate score vector and local consensus state | Fresh neighbor score/weight messages | Candidate order, consensus rule, round bound | - | Global all-reduce, centralized mean, hidden component membership | Local consensus estimate and score messages |
| Readiness certificate | Own proposed transition, own prospective local path/region, local observations | Fresh peer state needed by the declared local certificate | Topology geometry, safety margins, horizon, UNKNOWN policy | Offline certificate diagnostics only | Global safe-expansion oracle, future joint rollout, global minimum clearance | `SAFE`, `UNSAFE`, or `UNKNOWN` for robot `i` |
| Readiness consensus | Own readiness certificate and epoch state | Fresh propagated readiness messages | Logical aggregation rule and round bound | - | Central all-ready flag, global component query | Local all-ready/blocked/unknown result and messages |
| Topology confirmation | Own selected candidate, margin, readiness result, epoch | Fresh peer confirmation records | Confirmation rule, quorum/full-team contract, round bound | - | Originator override, centralized topology decision | Local confirmed/not-confirmed state and messages |
| Commitment lifecycle | Own current topology, epoch, dwell/retry timers, local protocol state | Accepted trigger/readiness/confirmation messages | Transition graph, timing, retry and abort rules | - | Shared mutable mode variable, simulator majority mode as an input | Own committed topology and transition log |
| Evaluation-only metrics | Raw frozen trace and per-robot logs | Complete communication log offline | Metric definitions, frozen episode manifest | Ground truth and oracle labels only for declared diagnostics | Any feedback to an active episode or deployable model input | Offline per-episode and aggregate reports |

The local safety projection may be optimization-based, but its decision problem
must be owned by one robot and return only that robot's action. A centralized
optimization over the joint action is prohibited.

## 10. Exact module classification

Classification applies to a logical module or symbol group. This unit is
necessary because the selected base co-locates simulator adapters and local
primitives in several physical files. Each row below has exactly one class from
the approved taxonomy. `Prohibited at runtime` means permitted only behind a
declared simulator/offline boundary, never importable or callable from a robot
decision path.

| Logical module or symbol group | Current owner | Exact class | Boundary note |
|---|---|---|---|
| Package exports | `decentralized/__init__.py` | Shared static | Names only; no mutable team state |
| Information schemas and constants | `decentralized/system_model.py` | Shared static | `RobotView`, message-independent contracts, topology IDs |
| Typed parameter/derivation helpers | `decentralized/parameters.py` | Shared static | Incomplete target coverage is tracked below |
| Persistent role definitions and pairwise offsets | `decentralized/roles.py` | Shared static | Pairwise offset evaluation uses local inputs plus static roles |
| Mission-setup role inference | `roles.simulate_mission_setup_from_initial_formation` | Prohibited at runtime | Joint positions allowed only before `t = 0` in simulation |
| Beacon, neighbor table, local history | `decentralized/comms.py` | Fully robot-local | One instance per robot |
| Radio channel and sensor/message synthesis | `comms.RadioChannel`, `comms.simulate_*` | Prohibited at runtime | Centralized simulation adapter |
| Candidate local graph construction | `decentralized/ego_graph.py` | Fully robot-local | Accepts `RobotView`, center readout only |
| Ego encoder and KEEP/LINE score heads | `decentralized/models.py` | Fully robot-local | Frozen shared weights; no global pooling |
| Pairwise formation and obstacle controller | `decentralized/local_controller.py` | Fully robot-local | Produces one action from one `RobotView` |
| Per-robot score-consensus node | `consensus.ConsensusNode` | Neighbour-distributed | Update receives one local inbox |
| Consensus host scheduler and global diagnostics | `consensus.simulate_consensus`, agreement helpers | Prohibited at runtime | Simulation/evaluation boundary |
| Per-robot epoch/token state machine | `epoch.EpochState` and local trigger/commit helpers | Neighbour-distributed | No special originator authority |
| Trigger/confirmation host schedulers | `epoch.simulate_*` | Prohibited at runtime | Simulation adapter only |
| Decentralized episode host harness | `runtime.simulate_decentralized_episode` | Prohibited at runtime | Stacks local commands to step the centralized simulator |
| Environment geometry helpers | `decentralized/env_geometry.py` | Prohibited at runtime | Used only for synthetic environment construction and offline inspection |
| Qualification fixtures | `decentralized/qualification_fixtures.py` | Centralized evaluation-only | Frozen diagnostic fixtures |
| Formation metric V3 | `decentralized/formation_metric_v3.py` | Centralized evaluation-only | Joint-state metric, never a controller input |
| Reconfiguration metrics | `decentralized/reconfiguration_metrics.py` | Centralized evaluation-only | Trace accumulator only |
| Training data/model fitting | `decentralized/training.py` | Centralized training-only | Labels may be global; model inputs remain local graphs |
| Communication accounting | `decentralized/comm_cost.py` | Centralized evaluation-only | Message types are static; aggregate accounting is offline |
| Static runtime guard/auditor | `decentralized/guards.py` | Centralized evaluation-only | CI/audit tool; not a robot decision module |
| Future topology registry | Phase 3 module | Shared static | Not implemented in selected base |
| Future recoverability/residual model | Phase 5 module | Fully robot-local | Not implemented in target form |
| Future local safety projection | Phase 6 module | Fully robot-local | Not implemented |
| Future readiness and generic transition protocol | Phase 7 module | Neighbour-distributed | Not implemented |
| Counterfactual labeler | Phase 9 module | Centralized training-only | Not implemented |
| Dual-regime dataset compiler | Phase 10 module | Centralized training-only | Not implemented |
| Scientific evaluator | Later evaluation phases | Centralized evaluation-only | Must remain disconnected from active runtime |
| Repository configuration and pure utilities | `config.py`, declared pure symbols in `utils.py` | Shared static | Runtime may consume only the immutable subset |
| Legacy simulator, layouts, and regions | `environment.py`, `layouts.py`, `regions.py` | Prohibited at runtime | Centralized world state and geometry |
| Legacy whole-graph model/policy/safety path | top-level `models.py`, `policy_runtime.py`, `safety.py` | Prohibited at runtime | Preserved for provenance and offline comparison, never the target robot path |
| Label, dataset, expert, and fitting path | `dataset.py`, `controllers.py`, `recoverability.py`, `recovery_v2.py`, `train.py`, training symbols in `binary_pilot.py` and `baselines.py` | Centralized training-only | May use joint state under the training firewall |
| Evaluation, consistency, provenance, and visualization path | `evaluate.py`, `metrics.py`, `consistency.py`, `provenance.py`, `visualize.py`, evaluation symbols in `binary_pilot.py` and `baselines.py` | Centralized evaluation-only | Reports only; no active-episode feedback |
| Split definitions and artifact writer locks | `splits.py`, `writer_lock.py` | Centralized training-only | Establish immutable data ownership; not serialized as model features |

The host schedulers may iterate over all simulated robots to deliver messages,
but they must call the same per-robot transition function that a robot process
would call. A host scheduler is not evidence of a deployable robot adapter.

## 11. Existing-code gap map

The audit below is against the Phase 1 target contract, not against the older
KEEP/LINE experiment's narrower claims.

| Requirement | Existing module | Currently compliant | Partially compliant | Missing | Known violation | Future phase responsible |
|---|---|---:|---:|---:|---|---|
| Explicit local information schema | `system_model.py`, `RobotView` | Yes | No | No | None found | Phase 1 freezes contract; all later phases preserve it |
| Physical local-observation builder | `comms.py` simulation builders | No | Yes | Yes | Only simulator synthesis exists; no production device adapter | Phase 4 feature boundary and Phase 8 communication integration |
| Candidate-conditioned ego graph | `ego_graph.py` | Yes for KEEP/LINE | Yes | No | Candidate set and defaults are not yet generic/FD24 | Phase 4 |
| Generic topology registry including COMPACT | mode constants in `system_model.py`, role coordinates | No | No | Yes | Current runtime supports only KEEP and LINE | Phase 3 |
| Recoverability encoder/head | `models.py` | Yes for local execution | Yes | No | Head is the preserved two-candidate selector, not the reconstructed target model | Phase 5 |
| Learned bounded residual head | none | No | No | Yes | No decentralized residual policy exists | Phases 5 and 11 |
| Local base controller | `local_controller.py` | Yes for one action/local inputs | Yes | No | Formal target decomposition and variable-size validation remain incomplete | Phase 6 |
| Distinct local safety projection | local avoidance terms only | No | Yes | Yes | No explicit projection/infeasible-result contract | Phase 6 |
| Leaderless intent token | `epoch.py` | Yes for KEEP/LINE epochs | Yes | No | Not generalized to topology registry/readiness lifecycle | Phase 7 |
| Neighbor score consensus | `consensus.py` | Yes | Yes | No | Peer degree is a disclosed sender-local aggregate; propagation contract is not yet fully config-derived | Phases 2 and 8 |
| Local `SAFE/UNSAFE/UNKNOWN` readiness certificate | none | No | No | Yes | No generic readiness certificate exists | Phase 7 |
| Distributed readiness consensus | none | No | No | Yes | No all-ready propagation exists | Phase 7 |
| Topology confirmation | `epoch.py` | Yes for existing two-mode protocol | Yes | No | No generic candidate/readiness binding | Phase 7 |
| Commitment lifecycle | `EpochState` | Yes for preserved flow | Yes | No | No generic transition graph; retry/abort/disconnection semantics need reconstruction | Phase 7 |
| Safe simultaneous LINE-to-KEEP transition | forward-opening detector and common commitment in `epoch.py` | No | Yes | Yes | Frozen negative common-KEEP regression shows outer roles can be locally unsafe at the shared commitment time | Phase 7 |
| Freshness and duplicate suppression | `NeighbourTable`, epoch/consensus messages | Yes for beacons | Yes | No | Message-family-wide schema and bounded-delay contract are incomplete | Phase 8 |
| Diameter-derived phase durations | `ConsensusParams`, current tests/config | No | Yes | Yes | Selected base still has incomplete typed derivation coverage | Phase 2 |
| Temporary-disconnection handling | stale expiry and component diagnostics | No | Yes | Yes | No normative UNKNOWN/abort behavior for every protocol phase | Phases 7 and 8 |
| Persistent roles and centroid-free pairwise offsets | `roles.py`, `local_controller.py` | Yes | No | No | Dynamic reassignment/dropout are intentionally unsupported | Phase 3 preserves contract; unsupported features remain out of scope |
| Explicit coordinate frames | role/mission transforms across current modules | No | Yes | Yes | Frame semantics are distributed across code rather than one validated schema | Phases 2, 3, and 4 |
| Training/runtime serialization firewall | `training.py`, `ego_graph.py`, `guards.py` | Yes for current local graph inputs | Yes | No | No versioned artifact-schema audit yet | Phases 5, 10, and 12 |
| Centralized metrics kept offline | formation and reconfiguration metric modules | Yes | No | No | None found in robot decision reachability | All evaluation phases preserve boundary |
| Simulator topology bookkeeping isolated from decisions | `runtime.py`, `environment.py` | Yes for per-robot action computation | Yes | No | Simulator receives majority committed mode; it affects simulator topology bookkeeping and global metrics, so it must never be described as a robot coordination primitive | Phase 6 simulator adapter/evaluator review |
| Production one-process-per-robot execution adapter | none | No | No | Yes | Current evidence is a host simulation harness plus local pure functions | Phase 8 integration; not a present deployment claim |
| FD24 mechanical invariance | none at target architecture level | No | No | Yes | No current FD24 claim is valid | Phases 3, 4, 8, and 12 |
| N=24 scientific validation | none | No | No | Yes | Explicitly not established | Later predeclared scientific phases only |

### 11.1 Disclosed boundary facts

The current beacon carries the sender's own pose/velocity and local degree. The
receiver converts pose to a relative neighbor record before graph construction.
Degree can reveal that the sender has additional links, but it reveals no raw
third-party state; it is an explicit protocol field used by the consensus
weighting rule.

The current simulator passes the majority of local committed modes into a
legacy single-team `environment.step` interface. Robots do not read that value,
and their actions are computed before the simulator step from separate local
views. The value can affect simulator topology bookkeeping and global formation
metrics, so future evaluation must continue to classify it as centralized
simulation state. It is not deployable consensus and cannot support a runtime
decentralization claim by itself.

The strict guard intentionally excludes declared offline modules and
`simulate_*` boundaries. Therefore a zero-violation result proves that no
prohibited source is reachable through the scanned robot-decision call graph;
it does not prove that every function named `simulate_*` is harmless. Boundary
functions still require code review and schema tests.

## 12. Required verification obligations for later phases

Every later implementation phase must preserve all of the following:

1. Static guard: no prohibited symbol, observation key, global reducer, or
   offline call is reachable from a robot decision/action function.
2. Schema guard: deployable examples and checkpoints contain only allowlisted
   local features, shared immutable metadata, and frozen model parameters.
3. Perturbation guard: changing out-of-range robot or obstacle state while
   preserving `I_i(t)` cannot change robot `i`'s score, readiness, commitment,
   or action.
4. Process-equivalence guard: host-scheduled per-robot updates equal updates
   produced by isolated robot processes receiving the same inboxes.
5. Communication guard: delay, duplicates, stale packets, and temporary link
   loss follow Section 7 and never create partial unsafe commitment.
6. Ownership guard: each actuator command has exactly one robot owner and no
   centralized post-processing step changes the joint action.
7. Metric firewall: centralized metrics and oracle labels cannot influence an
   active episode.
8. Claim guard: mechanical tests and scientific experiments are reported at
   their actual team sizes and split scope.

## 13. Phase ownership summary

- Phase 2 owns immutable configuration and derivation of timing/diameter
  quantities.
- Phase 3 owns the generic KEEP/COMPACT/LINE topology registry and role support.
- Phase 4 owns the target ego-graph schema and local-observation invariance.
- Phase 5 owns the local recoverability and residual-head architecture.
- Phase 6 owns base-controller decomposition, bounded residual composition, and
  local safety projection.
- Phase 7 owns generic intent, readiness, confirmation, and commitment.
- Phase 8 owns the complete message, delay, topology, and disconnection
  contract in executable form.
- Phases 9 and 10 own centralized counterfactual labels and data generation.
- Phases 11 and 12 own residual learning and variable-size training.
- Later predeclared phases alone own scientific validation and N=24 claims.

No future phase may solve an implementation gap by granting a runtime module
access to centralized training or evaluation data.

## 14. Phase 1 verdict

**C. The model and current gap map are valid; proceed to Phase 2.**

The verdict is limited to source-boundary inspection of the approved base. It
does not assert that missing COMPACT, readiness, residual-control, deployment,
or N=24 functionality already works. No undisclosed runtime centralization
violation was found; disclosed simulator boundaries and missing target modules
are recorded above.
