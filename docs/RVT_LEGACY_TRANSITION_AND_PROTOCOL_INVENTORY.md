# RVT Legacy Transition and Protocol Inventory

Inventory frozen before the Phase 7 protocol implementation.  The approved
baseline is commit `5f23666d872aa45258ffef78f0651b45c000fc2d`.  "Historical"
means retained evidence or a superseded path, not an approved Phase 7 runtime.

## Path inventory

| Module or function | Runtime status | Event semantics | Topology support | Local or global | Leaderless status | Message type | Diameter coverage | Freshness handling | Known defect | Recommended disposition |
|---|---|---|---|---|---|---|---|---|---|---|
| `decentralized/epoch.py::EpochState` | Active in the legacy scientific runtime | Trigger, score, confirm, commit, dwell and close | KEEP/LINE only | Per-robot mutable state | Same code per robot | Trigger and confirmation | Repaired `k_trigger`, `k_confirm` derive from the declared diameter | Token ordering, epoch checks and commitment timing | No generic candidate, no readiness phase, binary topology assumptions | Preserve for historical reproduction; do not extend |
| `epoch.py::local_trigger` | Legacy active | Local obstacle clearance requests KEEP to LINE | KEEP to LINE | Robot-local `RobotView` | Originator only introduces a token | Trigger | Uses epoch propagation | Evidence persistence and commitment lock | Pair-specific event logic | Keep out of the generic protocol core; expose only as an optional intent source |
| `epoch.py::forward_opening_evidence`, `local_recovery_trigger` | Legacy active | Role-dependent local opening requests LINE to KEEP | LINE to KEEP | Robot-local sensing | Originator only introduces a token | Trigger | Uses epoch propagation | Persistence, passage latch, commitment lock | Safe for the originator but not an authorization for other roles | Preserve as an intent fixture; require Phase 7 all-ready authorization |
| `epoch.py::PassageLatch`, recovery lifecycle | Legacy active | BEFORE_ENTRY, INSIDE, COMPLETE suppresses repeated recovery | KEEP/LINE | Robot-local evidence | N/A | None | N/A | Physical-time-derived persistence and rearm | Specialized to one passage lifecycle | Historical compatibility only |
| `epoch.py::TriggerToken`, `simulate_trigger_consensus` | Legacy active and test scheduler | Lexicographic max adopts one trigger token | KEEP/LINE | Neighbour graph simulation | Leaderless max consensus; originator is not coordinator | 21-byte fixed trigger | Configured causal bound | Duplicate token and stale epoch checks | Token identity includes originator, so equivalent evidence from different originators is not one canonical event | Replace in Phase 7 with canonical intent identity and versioned decoding |
| `consensus.py::ConsensusNode`, `simulate_consensus` | Legacy active | Metropolis averaging of two candidate scores | KEEP/LINE | Robot-local scalar messages; delivery orchestrated by simulator | Leaderless averaging | Fixed score message | `k_score` from diameter contract | Epoch, round, sender and duplicate checks | Binary score vector; learned-selector hook exists; no unavailable-score lattice | Preserve for legacy results; create a generic diagnostic scalar interface |
| `epoch.py::ConfirmMessage`, `simulate_confirm_consensus` | Legacy active | Propagates min/max proposed mode set before commit | KEEP/LINE | Per-robot state and neighbour messages | Leaderless set agreement | 16-byte fixed confirmation | Repaired `k_confirm >= D_max` | Epoch and round checks | Confirmation does not prove transition readiness | Consolidate semantics into Phase 7 confirmation after all-ready |
| `runtime.py::simulate_decentralized_episode` | Legacy scientific runtime | Orchestrates sensing, events, epochs, scores, confirmation, control | KEEP/LINE | Robot-local decisions inside a centralized simulator boundary | Protocol nodes are leaderless; simulator only delivers | Beacon, trigger, score, confirmation | Runtime configuration derived | Neighbour table and epoch checks | Pair-specific, readiness absent, legacy controller path, learned selector can be selected explicitly | Do not silently replace; Phase 7 gets a disabled-by-default strict diagnostic runtime |
| `runtime.py::_robot_decision` | Legacy selectable path | Always, geometric or model score generation | KEEP/LINE | Robot-local ego graph for deployable choices | No coordinator | Score | Inherits score rounds | Epoch-scoped | Phase 5 model hook exists and is not approved for topology selection | Keep inactive in Phase 7 and guard imports/calls |
| `runtime.py` scripted diagnostics | Diagnostic/historical | Scripted planes or scripted schedule can assign a mode | KEEP/LINE | Uses simulator/global fixture knowledge | Not a protocol | None | None | None | Direct topology assignment bypasses intent, score, readiness and confirmation | Prohibit in strict Phase 7 runtime |
| `forced_topology_runtime.py` | Approved Phase 6 qualification runtime | Fixed topology for stabilization/translation | KEEP/COMPACT/LINE | Every robot computes its own action; topology is a fixture constant | No transition protocol by design | Beacon/local view | Communication fixture contract | Beacon freshness | Direct forced topology is valid only because no online transition occurs | Reuse controller/safety execution after Phase 7 commitment, not as authorization |
| `robot_local_controller.py` and `local_safety_projection.py` | Approved Phase 6 authoritative control | Computes robot i action for one committed topology | KEEP/COMPACT/LINE | Strictly robot-local | N/A | Local view input | N/A | Fresh peer observations required by adapters | Does not implement lifecycle or swarm agreement | Reuse unchanged for transition execution |
| `comms.py::Beacon`, `NeighbourTable` | Active | One-hop state/role/topology discovery | Encodes legacy committed mode | Robot-local table; simulator broadcasts | Peer-to-peer | 49-byte beacon | One hop per broadcast | Duplicate and stale sequence/timestamp rejection | Beacon topology field predates the three-topology transition lifecycle | Reuse delivery pattern; do not treat a beacon as authorization |
| `comm_cost.py::MessageAccountant` | Active analysis support | Records transmitted and received payloads | Legacy schema registry | Per-message accounting, globally summarized offline | N/A | Beacon, trigger, score, confirmation | N/A | N/A | Current accountant requires fixed registered sizes; older reports once used provisional trigger/confirm estimates | Phase 7 accounting records exact serialized payload lengths by phase |
| `post_parameter_repair_regression.py` | Frozen historical harness | Replays detector A/B and three-cell closed loop | KEEP/LINE | Global offline evaluation plus legacy local runtime | Protocol under test is leaderless | Legacy messages | Repaired diameter bound | Frozen traces/seeds | Common LINE to KEEP commitment authorizes outer roles that remain constrained | Preserve outputs; use the failure as a predeclared Phase 7 fixture |
| `formation_metric_v3.py` | Approved offline evaluator | Centred target-tube entry and dwell | Registry topologies through adapters | Global offline metric only | N/A | None | N/A | Consecutive physical-time dwell | Centroid is intentionally evaluator-only and cannot enter runtime authorization | Reuse unchanged only for qualification/completion measurement |
| Historical periodic `step % decision_interval` and lockstep `epoch_ids` | Superseded, documented in `DECENTRALIZED_RUNTIME_INTEGRATION_AUDIT.md` | Timer opened centrally synchronized epochs | KEEP/LINE | Global harness | Not leaderless | None | No causal proof | Direct step timer | Duplicated/shadow epoch implementation and vacuous agreement | Never restore |
| Historical no-op retry loop | Superseded behavior, retained in `EPOCH_CHURN_AUDIT.md` | Persistent trigger reopened mode-equal epochs | KEEP/LINE | Mixed | Protocol messages were leaderless | Trigger/score/confirm | Historical configuration | Commitment dwell only | 16.2 epochs per passage, about 14 no-ops, topology chatter risk | Reject source-equals-target before lifecycle creation |
| Legacy environment majority committed mode | Simulator bookkeeping | Chooses one environment label from robot modes | KEEP/LINE | Global | Not an authorization protocol | None | N/A | None | Centralized vote-like aggregation would be invalid if used to command robots | Keep outside protocol and exclude from strict runtime decisions |

## Explicit defect findings

- **Direct assignment:** scripted diagnostic schedules and forced-topology
  qualification set topology without a transition protocol.  Only the latter is
  valid for Phase 6 because it contains no online topology change.
- **Originator-as-leader:** no permanent coordinator exists, but the legacy
  trigger token includes originator identity in event identity.  Equivalent
  physical events can therefore produce different tokens.  Phase 7 must make
  canonical event identity independent of the introducer and grant the
  originator no additional authority.
- **Centralized aggregation:** historical lockstep epoch IDs, simulator mode
  majority bookkeeping, and scripted global schedules are centralized paths.
  None may authorize a strict-runtime transition.
- **Complete-state events and global exit planes:** scripted-plane diagnostics
  and offline evaluators may use global geometry.  The deployable legacy
  forward-opening detector is local after the parameter repair; Phase 7 must
  keep global planes, maps, centroids and joint state out of readiness.
- **Diameter rounds:** early historical paths used direct/fixed timing.  The
  approved configuration now derives trigger and confirmation bounds; Phase 7
  must derive intent, score, readiness and confirmation rounds and enforce each
  against the same diameter contract.
- **Readiness:** every legacy commit path lacks a per-robot transition-readiness
  certificate and all-ready agreement.
- **No-op epochs and chatter:** the historical trigger loop opened 16.2 epochs
  per passage.  A later guard skipped some work but did not stop creation.
  Source-equals-target must create zero Phase 7 epochs.
- **Duplicated epoch semantics:** a historical inline periodic implementation
  shadowed `epoch.py`; current legacy orchestration still combines pair-specific
  lifecycle logic in multiple helpers.  Phase 7 must have one authoritative
  state machine.
- **Timer units:** historical code and reports contain control-step timers.
  Current runtime configuration derives steps from declared seconds.  Phase 7
  APIs must accept physical time and expose derived rounds/steps as provenance.
- **Communication cost:** current legacy trigger/confirm encoders are measured,
  but provisional 16/17-byte estimates existed historically.  Phase 7 reports
  must count the bytes returned by actual versioned serializers, including
  retransmission and timeout traffic.
- **Unsafe common KEEP:** all 16 post-parameter-repair failures were category B:
  centre roles originated locally valid opening evidence and the whole
  component committed KEEP while at least one outer role still observed wall
  material inside its expansion region.  This is the principal historical
  defect Phase 7 readiness must block.

## Disposition boundary

Phase 7 adds a separate, explicitly enabled diagnostic runtime and leaves the
legacy scientific runtime and historical results untouched.  The Phase 5 model,
scientific labels and residual actions remain inactive.  The Phase 6 controller,
safety projection, topology registry, physical parameters and Metric V3 remain
authoritative and unchanged.
