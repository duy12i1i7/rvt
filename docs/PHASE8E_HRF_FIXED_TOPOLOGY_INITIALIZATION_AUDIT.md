# Phase 8E-HVA — Fixed-Topology Initialization Audit (HVA-1)

## The frozen S2 contract, read verbatim

`results/rvt_fd24/source_policy_contracts_v1.json`, `policies.S2_ALWAYS_LINE`:

```json
{
  "initial_topology": 5,
  "topology_behavior": "at time zero use the offline forced-topology qualification interface to initialize LINE role targets; no online request or epoch is created",
  "hold_semantics": "LINE remains committed for the complete episode",
  "event_rule": "no online candidate request"
}
```

`5` is COMPACT. The behaviour clause says LINE role **targets**, not LINE poses.
Two documents corroborate:

* `PHASE8E_SOURCE_POLICY_EXECUTION_CONTRACTS.md`: "S2 uses the offline
  forced-topology initialization interface to establish LINE targets at time
  zero ... **Primary publication initialization still remains COMPACT.**"
* `PHASE8E_INITIALIZATION_AND_DISTURBANCE_CONTRACT.md`: "the offline forced
  topology interface **initializes LINE role targets** at time zero without
  creating a source-equals-target epoch."

`initial_topology: 5` is uniform across S0-S5 — it names the scenario's compiled
initial topology, not a per-policy placement. S2's LINE-ness lives entirely in
the controller's target.

## Defect 11 — S2 physically relocated the formation

The publication runtime placed robots at `origin + R(psi) * line_offset_i` at
t=0. That is a LINE **placement**, which no frozen document requests. It gave
the fixed-LINE baseline a free, instantaneous reconfiguration that the frozen
contract does not grant, and at larger N the long LINE formation intersected
compiled obstacle geometry, producing 15 spurious `INITIALIZATION_INVALID`
cells.

Corrected: S2 places robots at the compiled COMPACT poses and forces only the
controller target topology to LINE.

## Consequence for the owner's decision

The owner froze a `POLICY_INITIAL_STATE_INFEASIBLE` status for fixed baselines
whose own topology cannot instantiate at the mission start. **Under the frozen
contract that situation cannot arise**: no fixed baseline ever instantiates a
topology-specific formation, because both S1 and S2 start from the same compiled
COMPACT placement. The status was therefore not implemented, and no cell needs
it — 0 of 23 `RECONFIGURATION_REQUIRED` cells are admissibility-driven.

The premise behind the decision was a defect in my runtime, not a gap in the
protocol. Reporting that is more useful than encoding machinery for a case the
contract excludes.

## Verification

| check | result |
|---|---|
| HVA-5 COMPACT vs compiled `nominal_initial_validity_by_team_size` | **150 cells checked, 0 disagreements** |
| HVA-7 fairness: S1 and S2 initial placement | **byte-identical**; only committed topology differs |
| remaining `INVALID_OR_AMBIGUOUS` | 3 cells, all F4 at N=16, all with `compiled_nominal_valid = false` |
| unexplained cases | **0** |

---

# Blocking finding: neither S2 reading yields a usable fixed-LINE baseline

Implementing the contract-faithful reading revealed that it does not work
either. Both readings were executed over all 150 Study A cells.

## Reading A — physical LINE placement (the committed runtime, artifact v3)

Robots spawn at `origin + R(psi) * line_offset_i`.

* Contradicts `initial_topology: 5` and all three corroborating documents.
* At N >= 8 the LINE formation spans 6.3-13.5 m longitudinally and intersects
  compiled obstacle geometry, producing 15 `INVALID_OR_AMBIGUOUS` cells.
* Grants the baseline a free, instantaneous reconfiguration the contract never
  offers.

## Reading B — COMPACT poses, LINE targets (contract-faithful, artifact v4)

* Matches `initial_topology: 5`, "LINE role **targets**", and "Primary
  publication initialization still remains COMPACT".
* HVA-5: reproduces the compiled COMPACT initial validity in **150/150 cells,
  0 disagreements**.
* HVA-7: S1 and S2 initial placement is byte-identical; only the committed
  topology differs.
* **But**: S2 creates no epoch by contract, so it receives neither mission
  staging nor the frozen role-space profile. Its step-1 unmanaged COMPACT->LINE
  convergence collides at **step 8, robots 2-3 at 0.3635 m against the 0.4000 m
  clearance, in the open field F1**, where fixed COMPACT reaches GOAL_COMPLETE.
  Fixed LINE therefore degenerates to an immediate collision in essentially
  every cell.

Under reading B the corrected counts are train `{COMPACT_ONLY 28, BOTH_FAIL 52,
RECONF 15, LINE_ONLY 2, BOTH_SUCCESS 1, INVALID 2}` and validation
`{COMPACT_ONLY 19, BOTH_FAIL 21, RECONF 8, BOTH_SUCCESS 1, INVALID 1}` — with
**94 of 150 cells changing from reading A alone**, and `RECONFIGURATION_REQUIRED`
rising to 23 cells across four families (F2, F5, F9, F10) with **0 of 23**
admissibility-driven.

## The unstated scientific choice

Defects 9, 10 and the mission-staging decision jointly established that a safe
topology change needs the role-space profile, a computed readiness certificate
and mission staging. S2 is defined to create **no epoch**, so it can receive
none of them — yet it is required to reach LINE role targets from COMPACT poses.
No frozen document says how.

Neither reading is usable: A contradicts the contract and is geometrically
invalid at scale; B is contract-faithful and collides immediately everywhere.
The owner must decide whether S2 is entitled to staging/profile despite creating
no epoch, or whether its initial placement is LINE after all.

**The runtime is left at reading A** (unchanged in this commit) so the repository
stays consistent while the decision is pending. `v4` is recorded as
`EVIDENCE_ONLY_PENDING_OWNER_DECISION` and is explicitly **not** authoritative.
