# Predeclared Decentralization Gates D1–D7

**Frozen before the decentralized dry run.** Nothing in this document may be
changed after any D-gate number is observed. Amendments are permitted only by
adding a dated, signed amendment section that states what changed, why, and
which results already existed at the time — never by editing a threshold in
place.

| | |
|---|---|
| Branch | `research/fully-decentralized-selector-v1` |
| HEAD at freeze | `c74f0c9` — *decentralized Tasks 0-5,7,11: system model, comms, ego graph, roles, consensus, local controller, guards* |
| Date of freeze | 2026-07-30 |
| Status of results | **None of D1–D4, D6, D7 has been measured.** D5 is already measured (§D5). No selector has been trained. No number in this document is a result except those explicitly cited from an existing artifact. |
| Data | **Validation layouts only.** `build_layouts("test")` is not read by anything in this document, at any point, for any purpose. |

Consistency anchors — this document is written to be consistent with, and
subordinate to, the following already-frozen specifications:

- [`BINARY_MODE_SEED0_DRY_RUN_V2.md`](BINARY_MODE_SEED0_DRY_RUN_V2.md) — **verdict B**
- [`DECISIVE_MODE_METRIC_SPECIFICATION.md`](DECISIVE_MODE_METRIC_SPECIFICATION.md)
- [`BINARY_MODE_PILOT_HYPOTHESIS.md`](BINARY_MODE_PILOT_HYPOTHESIS.md) — gates G1–G4
- [`RECOVERY_EVENT_V2_DEFINITION.md`](RECOVERY_EVENT_V2_DEFINITION.md)
- [`FULLY_DECENTRALIZED_SYSTEM_MODEL.md`](FULLY_DECENTRALIZED_SYSTEM_MODEL.md)
- `rvt_swarm/decentralized/system_model.py` — the machine-readable contract

---

## 0. Inheritance from verdict B — why every closed-loop gate uses fixed-controller execution

Dry run V2 established, on 20 validation episodes, that the learned mode
selector works and the **learned low-level action head does not**: decisive
accuracy 0.965 with selector-only success 0.800 (classifier) and 0.500
(`rvt_binary_recovery`) against an always-keep reference of 0.450, but
**end-to-end success 0.000** for both mode-conditioned models, localised to the
line action head (forced-line: expert 1.000, learned 0.000).

The recommended response in that document was option 1: *run the pilot as a
selector-only study with trusted fixed-controller execution.*

**This document adopts that framing without re-litigating it.** Consequently:

> **Every closed-loop measurement in gates D3, D4, D6 and D7 executes with the
> decentralized fixed controller `local_controller.local_controller`, never with
> a learned action head.** The learned component under test in D2–D4, D6 and D7
> is the **mode decision only**.

This is not a convenience. It is what makes the gates measure decentralization
rather than re-measuring the known action-head failure: with a learned executor
every arm would read 0.000 and every gate would be vacuously satisfied or
vacuously failed. Any future report that runs a D-gate with a learned executor
is running a different experiment and must say so.

---

## 1. Shared measurement protocol

Fixed here once so that no gate can be computed on a quietly different sample.

### 1.1 Data

| | |
|---|---|
| Layout source | `build_layouts("val")` only |
| Constrained families | `line_corridor`, `keep_line_keep` — **5** validation layouts (`val_line_corridor_001/002/003`, `val_keep_line_keep_001/002`) |
| Control families | `keep_open`, `ambiguous` — reported, never used to set a threshold |
| Team sizes | `N ∈ {4, 6}` |
| Episode seeds | `setting_episode_seeds(VALIDATION, 0, n, episodes_per_cell, 0)` |
| Scenario | `"cluttered"` |
| Excluded absolutely | `build_layouts("test")`, the `infeasible` family in any selection role, `split_around`, `keep_split_merge` |

### 1.2 Episode budget and resolution

| Budget | Cells | Episodes | Resolution (1 episode) | Used by |
|---|---|---|---|---|
| `episodes_per_cell = 2` | 5 layouts × 2 sizes × 2 seeds | **20** | 0.050 | **D5 only** (already measured at this budget) |
| `episodes_per_cell = 5` | 5 layouts × 2 sizes × 5 seeds | **50** | 0.020 | **D3, D4, D6, D7 closed-loop arm** |

The 50-episode budget is predeclared *because* the D4 and D6 thresholds (0.10)
and the D3 material-degradation tolerance (0.03) are finer than the 20-episode
resolution of 0.05. A 0.03 tolerance measured at 0.05 resolution is not a
tolerance, it is a coin flip. D5 is exempt and is **not re-run**: it is recorded
as measured, at the budget in force when it was measured, and it passes by a
margin (155.6 % vs the 80 % rule) far larger than any budget effect.

Every reported proportion must be accompanied by its denominator. A gate
comparison whose difference is smaller than one episode at the budget used is
reported as **INCONCLUSIVE**, which is *not* a pass.

### 1.3 Metric names — no metric may be reported under a name it does not have

| Name used in D-gate tables | Exact definition | Source |
|---|---|---|
| `closed_loop_success_proxy` | `EpisodeAccumulator.finalize()["success"]` = latched `goal_reached` **and** episode-wide `collision_free` **and** terminal `form_ok` | `rvt_swarm/metrics.py:177` |
| `decisive_accuracy`, `decisive_balanced_accuracy`, recalls, references, tie rate | exactly as specified in `DECISIVE_MODE_METRIC_SPECIFICATION.md` §3–§5 | `binary_pilot.decisive_mode_metrics` |
| `agreement_rate` | 1.0 iff every robot committed the same mode, per decision epoch | `consensus.agreement_rate` |
| `component_agreement` | mean over connected components of within-component unanimity | `consensus.component_agreement` |
| `consensus_residual` | `max_i max_{c∈{keep,line}} \|z_{i,c} − z̄_c\|` after the final round | `consensus.consensus_residual` |
| `Y_task` / Recovery Event V2 label | the counterfactual rollout label, `H_commit = 10` | `recovery_v2.rollout` |

> **Honesty note, load-bearing.** `closed_loop_success_proxy` is **not**
> `Y_task`. It has no `crossed_exit` conjunct and it uses the *terminal*
> `form_ok` flag rather than an `L`-consecutive-step in-tube window
> (`RECOVERY_EVENT_V2_DEFINITION.md` §3). It is the same quantity the code calls
> `task_recovery_proxy_success` in `binary_pilot._run_family_episodes` and
> `success` in `results/decentralized/gate_d5_local_controller.txt`. Wherever
> the task description of these gates says "closed-loop Task-Recovery V2", the
> measured quantity is this proxy, and every table must print the proxy name.
> Calling it Task-Recovery V2 unadorned would overclaim, because on a scenario
> with a bottleneck the proxy can fire without a verified traversal — exactly
> the V1 defect V2 was built to repair. This divergence is recorded as a
> **known limitation of the D-gates**, not silently absorbed.

### 1.4 Decision-epoch protocol (all agreement gates)

- Decision epochs open on the forced cadence `decision_interval = 25` control
  steps, plus any trigger epochs, per `ConsensusParams`.
- Consensus runs `K_score` rounds of `simulate_consensus`; each robot then
  decides by `ConsensusNode.decide()` (ties → KEEP, declared in code).
- `G_c` connectivity is **measured** per epoch via `connected_components` on the
  link graph, never assumed.
- **Swarm-wide agreement is computed only over epochs in which `G_c` is
  connected.** Disconnected epochs are reported separately with their component
  structure and enter only `component_agreement`
  (`LINK_ASSUMPTIONS["connectivity"]`, `FULLY_DECENTRALIZED_SYSTEM_MODEL.md` §12).
- Configuration stratification is **mandatory** in every agreement table: `N=4`
  keep, `N=4` line, `N=6` keep are **one-hop complete** on template; only `N=6`
  **line** has diameter 2. An aggregate agreement number that hides this is a
  one-hop broadcast result wearing a consensus label.

---

## 2. The gates

### D1 — LOCALITY (binary, veto)

**Metric.** All of the following, jointly. Binary: any single failure fails D1.

| # | Check | Instrument | Threshold |
|---|---|---|---|
| 1.1 | `guards.audit()` over the whole `rvt_swarm.decentralized` package | `guards.audit()` | returns **exactly `[]`** |
| 1.2 | Declared locality suite passes | `tests/test_ego_graph_locality.py` (12 tests at freeze) | **100 %**, 0 skips counted as passes |
| 1.3 | Guard suite passes | `tests/test_decentralization_guards.py` — **does not exist at freeze; must be written before D1 is claimed** | **100 %** |
| 1.4 | Mutation evidence | each of `scan_signatures`, `scan_prohibited_obs_keys`, `scan_boundary_reachability`, and the return-shape scanner of 1.6 | each must be shown **red** under ≥ 1 injected offender, with the offender and the resulting `Violation` pasted into the gate report |
| 1.5 | No deployable call path accepts the joint state | `scan_signatures()` | 0 violations; every deployable function takes a `RobotView` (or scalars) plus constants |
| 1.6 | No central joint-action generation | **new scanner required** (§2.D1.a) | no deployable function returns an array indexed over more than one robot |
| 1.7 | No global pooling | ego-graph locality property 7 | asserted, no `global_mean_pool` / `pooled_graph_features` / `all_reduce` reachable |
| 1.8 | Boundary discipline | `scan_boundary_reachability()` | no control-loop function calls a `simulate_*` function |
| 1.9 | Strict runtime on | `guards.strict_enabled()` | `True` for every validation run that produces a D-gate number |

**Data.** Static analysis of the package plus the test suite. No episodes.

#### §2.D1.a — the gap that must be closed before D1 can be claimed

`guards.py` checks **parameters** (`scan_signatures`), **obs-key subscripts and
forbidden calls** (`scan_prohibited_obs_keys`) and **boundary reachability**
(`scan_boundary_reachability`). It does **not** check **return shapes**. The D1
requirement "no central joint-action generation" is therefore *currently
unenforced*: a deployable function returning an `(N, 2)` action array for the
whole team would pass today's `audit()`. A scanner `scan_joint_action_returns()`
must exist and be mutation-tested before D1 is reported as passing. Recording
this here, before the run, so it cannot later be presented as an oversight that
happened not to matter.

Likewise, no test file currently exercises `guards.audit()` at all (verified:
`grep -rn "guards" tests/` returns nothing at freeze). Check 1.3 is therefore a
requirement, not a description.

**FAIL means.** *Veto.* The permissible claim in
`FULLY_DECENTRALIZED_SYSTEM_MODEL.md` §12 — "leaderless, fully decentralized
execution using local observations and finite-round peer-to-peer communication"
— **may not be made in any form**, and no other gate result is reportable as
evidence for decentralization. There is no partial credit and no "mostly local"
wording. The recommendation becomes: fix the violation, or reframe the entire
contribution as a centralized selector with a local controller.

---

### D2 — NOMINAL AGREEMENT (connected graph)

**Data.** Validation layouts, all four pilot families, nominal link model
(`packet_loss = 0.0`, `delay_steps = 0`, symmetric), `K_score = K*` as selected
in §3.1. Only decision epochs with **connected `G_c`**.

| Sub-gate | Metric | Threshold |
|---|---|---|
| D2.a | full-swarm `agreement_rate` over connected epochs | **≥ 0.95** |
| D2.b | mode-confirmation success (defined below) | **≥ 0.95** |
| D2.c | **median** `consensus_residual` over connected epochs | **≤ 0.06 logits** |

**D2.b, mode-confirmation success — exact definition.** An epoch's confirmation
succeeds iff, within `K_confirm = 4` rounds, all four hold:

1. every robot in the swarm has reached a commit decision (no robot still
   uncommitted at round `K_confirm`);
2. all committed modes are identical;
3. each robot's own `|z_keep − z_line| ≥ confirm_margin` (nominally 0.0);
4. each robot's committed mode equals `ConsensusNode.decide()` on its own
   post-consensus `z` — i.e. no override path silently replaced the robot's own
   decision.

Denominator = connected decision epochs. Condition 4 exists because a
confirmation protocol that quietly rewrites a robot's decision would score 1.000
on conditions 1–3 while being a leader in disguise.

#### D2.c — derivation of the 0.06 tolerance (predeclared, not chosen after the fact)

The tolerance is derived from the logit scale, in four steps, each of which
cites a number that already exists in a frozen document:

1. **Units.** `z` is a task-recovery **logit**; the deployed probability is
   `p = σ(z)` (`models.py`: `probs = torch.sigmoid(logits)`). `consensus_residual`
   is the max per-component deviation of any robot's `z` from the swarm mean `z̄`.
2. **What error budget is admissible.** The selector's own predeclared
   calibration tolerance is **ECE ≤ 0.15** (gate G1,
   `BINARY_MODE_PILOT_HYPOTHESIS.md` §8). Consensus is numerical machinery, not
   the object of study; it must not be a comparable error source. Requiring it
   to contribute **at most one tenth** of the calibration budget — the standard
   "not the dominant error term" criterion — gives a probability-space budget
   `ε_p = 0.15 / 10 = 0.015`.
3. **Logit → probability sensitivity.** `sup_z |dσ/dz| = 1/4` (attained at
   `z = 0`, i.e. `p = 0.5`, the worst case and the one that matters because it
   is where mode decisions are close). Hence `|Δp| ≤ (1/4)|Δz|`.
4. **Invert.** To guarantee `|Δp| ≤ ε_p` for every `z`, require
   `|Δz| ≤ 4 ε_p = 4 × 0.015 = **0.06**`. That quantity is exactly what
   `consensus_residual` measures.

> **Tolerance: `median consensus_residual ≤ 0.06` logits.**
> The 95th percentile and the maximum are also reported, but only the median
> gates — a single pathological epoch is a data point, not a verdict.

**Consequence, stated so it can be checked rather than assumed.** A residual at
tolerance perturbs a robot's decision margin `m_i = z_{i,line} − z_{i,keep}` by
at most `2 × 0.06 = 0.12` logits relative to the swarm-mean margin (triangle
inequality over two components). So consensus error can flip a robot's mode only
where the mean margin is below 0.12 logits — about a 0.03 difference in
predicted recovery probability near `p = 0.5`. That is a near-indifferent state
by construction, and the flip costs correspondingly little.

**Anti-degeneracy guard (predeclared).** The 0.06 tolerance is only meaningful
if the learned logits have a scale against which it is small. Therefore: if the
**median `|m|` over decisive validation states is below 0.12 logits**, the
learned margin has collapsed to the same order as the consensus tolerance, and
D2.c is reported as **FAIL — UNINFORMATIVE**, never as a pass. A tiny residual
achieved by a selector that expresses no preference is not agreement, it is
silence.

**FAIL means.** The claim degrades from swarm-wide to per-component: the paper
may say "robots within a connected component agree" and may **not** say "the
swarm agrees". If D2.c fails while D2.a/b pass, the honest statement is that
robots agree on the *argmax* without having agreed on the *value*, i.e. finite
`K` has not converged the score, and the consensus contribution is presentational
rather than numerical. If D2.a fails on the `N=6` line configuration
specifically — the only genuinely multi-hop case — the consensus claim fails
where it matters most, and no aggregate that pools it with the three one-hop-
complete configurations may be reported in its place.

---

### D3 — CONSENSUS VALUE (does communication buy anything?)

**Comparison.** `K_score = K*` (selected per §3.1) versus `K_score = 0`
(independent local decisions — no consensus messages at all). Everything else
identical: same weights, same layouts, same seeds, same controller, same
`H_commit`, same `decision_interval`.

**The three metrics.**

| | Metric | Sample |
|---|---|---|
| M1 | full-swarm `agreement_rate` (connected epochs) | all pilot families, nominal link |
| M2 | `decisive_accuracy` per `DECISIVE_MODE_METRIC_SPECIFICATION.md` | validation decisive subset |
| M3 | `closed_loop_success_proxy`, constrained families | 50 episodes |

**Gate.** Consensus passes iff **both**:

- **(improvement)** at least one of {M1, M2, M3} improves by **≥ 0.05 absolute**
  (`K*` minus `K=0`). At the 50-episode budget the smallest realisable
  improvement satisfying this on M3 is **3 episodes = 0.06**; state the realised
  episode count, not just the proportion; **and**
- **(no material degradation)** neither of the other two metrics degrades by
  more than the material-degradation tolerance.

**Material degradation — predeclared numerically.**

> **A drop of more than 0.03 absolute on M1, M2 or M3 is material.**

Derivation, by precedent rather than by invention: 0.03 is the degradation
allowance already frozen in gate G2 for the control family
(`BINARY_MODE_PILOT_HYPOTHESIS.md` §8: "≤ 0.03 absolute degradation vs
`always_keep` on `keep_open`"). Reusing it keeps one tolerance scale across the
whole project instead of introducing a second, more convenient one here. At the
50-episode budget: a 1-episode drop (0.02) is within tolerance; a 2-episode drop
(0.04) is material. On M1 and M2 the denominators are larger and 0.03 is
comfortably resolvable.

**FAIL means.** The leaderless consensus layer is **not a contribution**. The
recommendation becomes: report the system as independent per-robot local
decisions (`K_score = 0`), and report the consensus result as a **negative
result with its measured numbers** — not as an unmentioned design that quietly
disappeared. A specific and likely sub-case is worth naming in advance: if
`K* = 0` is itself selected by §3.1, D3 fails by construction and must be
reported that way, immediately, in the same table.

---

### D4 — GLOBAL-REFERENCE GAP

**Metric.**

```
gap = | closed_loop_success_proxy(decentralized)
      − closed_loop_success_proxy(centralized_diagnostic_selector) |
```

**Threshold: `gap ≤ 0.10`** on constrained validation layouts, 50 episodes,
matched layouts / team sizes / seeds.

**The centralized diagnostic selector — exact definition.** Same trained
selector weights. The mode is chosen once per decision epoch from the
**full-swarm graph** (the existing `infer_learned_action(...)["topology"]` path,
which pools over all robots) and applied to every robot. **Execution is the same
decentralized `local_controller` in both arms.** Same layouts, seeds, `N`,
`H_commit = 10`, `decision_interval = 25`. The two arms therefore differ in
**exactly one thing**: whether the mode came from a pooled global graph or from
ego graphs plus `K*` rounds of peer-to-peer consensus.

This reference is `centralized_diagnostic_selector`, a `TRAINING_ONLY_SOURCES`
entry. It is labelled *centralized* in every table and is **never** a component
of the decentralized system.

**Two-sided by predeclaration.** The gate is on the absolute gap. If the
decentralized arm *exceeds* the centralized arm by more than 0.10, D4 **fails**
and is reported as an **unmatched comparison**, not as a win — because the two
arms are constructed to differ only in mode sourcing, and a gap that large in
that direction is evidence that something else differs. Announcing this before
the run removes the temptation to keep a flattering number and discard the
symmetric unflattering one.

**FAIL means.** The paper may not present decentralization as coming at
negligible cost. The measured gap becomes a headline limitation, stated with its
sign and its confidence interval, and the recommendation is to report the
centralized selector as the performance reference and the decentralized selector
as the deployable one, with the cost explicit in the abstract.

---

### D5 — LOCAL CONTROLLER — **ALREADY MEASURED, PASSING**

**Fraction rule, stated exactly.**

```
fraction(mode) = closed_loop_success_proxy( local_controller,   forced mode )
               / closed_loop_success_proxy( centralized fixed controller, forced mode )

D5 passes  iff  fraction(keep) ≥ 0.80  AND  fraction(line) ≥ 0.80
```

Evaluated **separately per forced mode**; both must pass. The mean of the two is
not the gate — averaging would let a working keep controller carry a broken line
controller, which is precisely the failure mode dry run V2 found in the *learned*
head (`BINARY_MODE_SEED0_DRY_RUN_V2.md` §6.1).

**Degenerate-denominator rule (predeclared for completeness).** If the
centralized reference for a mode is exactly 0.000, the ratio is undefined; the
fraction rule is then replaced by the absolute rule
`local ≥ centralized − 0.02` (one episode at the 50-episode budget). This did
not arise — both denominators are non-zero — but the rule is fixed here so it
cannot be invented later.

**Measured result.** Source of record:
`/Users/udy/rvt/results/decentralized/gate_d5_local_controller.txt`, verbatim:

```
keep  centralized : success=0.450  (20 episodes)
keep  local(init) : success=0.700  (20 episodes)
keep  local(index): success=0.700  (20 episodes)
line  centralized : success=1.000  (20 episodes)
line  local(init) : success=1.000  (20 episodes)
line  local(index): success=1.000  (20 episodes)
```

| forced mode | centralized | local (deployable, `from_index`) | fraction | ≥ 0.80 ? |
|---|---|---|---|---|
| keep | 0.450 | 0.700 | **1.556** (155.6 %) | **PASS** |
| line | 1.000 | 1.000 | **1.000** (100.0 %) | **PASS** |

> ### D5: **PASS** — recorded as already measured, not re-run.

Notes on how to read it, so the pass is not over-read:

- The gate is evaluated on `local(index)` — `RoleAssignment.from_index`, the
  strictly-deployable variant that reads no joint state at any point.
  `local(init)` (roles seeded by the boundary function
  `simulate_mission_setup_from_initial_formation`) is reported alongside and
  measured **identical** in both modes.
- The keep fraction exceeds 1.0. This is **not** a claim that the local
  controller is better than the centralized one. At the 20-episode budget the
  0.250 difference is 5 episodes; the honest statement is *"the local controller
  is not worse, and clears the 80 % bar with large margin"*.
- The "matched" in "matched centralized fixed-controller performance" is
  mechanical, not rhetorical: `local_formation_error` normalised by `(|N_i| + 1)`
  equals the centralized `controllers.expert_action` `form_err_i` to float32
  precision (4e-7) under full connectivity. Dividing by `|N_i|` instead inflates
  by `n/(n−1)`, and that is the one line that would silently unmatch the
  comparison.
- The centralized keep value 0.450 is the same always-keep reference that
  appears in dry run V2 §6, so D5 and the binary pilot are on one scale.

**FAIL means** (recorded for completeness; it did not occur). No closed-loop
decentralized claim of any kind. The controller would have to be redesigned
before D3, D4, D6 or D7 could be measured at all, because every one of them
executes with it.

---

### D6 — COMMUNICATION DEGRADATION

**Data.** Identical to D2/D3 but with `packet_loss = 0.10`, `delay_steps = 0`,
`K_score = K*`. Compared against the **same configuration at
`packet_loss = 0.0`** — never against an absolute standard, because the question
is degradation, not level.

**Stochastic-link protocol.** Packet loss is random, so each of the 50 episodes
is run with **3 independent communication seeds** (`comm_seed ∈ {0, 1, 2}`,
derived deterministically from the episode seed), giving 150 episode-runs. The
report prints the mean **and** the per-comm-seed min/max. If the across-seed
range exceeds the gate margin, D6 is reported **INCONCLUSIVE** — not a pass.

**"Graceful" — predeclared numerically.** All three must hold:

| Sub-gate | Metric | Threshold | Derivation |
|---|---|---|---|
| D6.a | `component_agreement` (per connected component of `G_c`) | **≥ 0.90** | at most 0.05 below the D2 nominal floor of 0.95; within a component the algorithm is still supposed to work |
| D6.b | full-swarm `agreement_rate` on epochs where `G_c` is connected | **≥ 0.85** | 0.10 below the D2 floor. A larger allowance than D6.a because loss thins `N_i` and can transiently disconnect the *delivered-message* graph even when the *link* graph is connected (`LINK_ASSUMPTIONS["directed"]`) — that is a communication fact, not a consensus failure |
| D6.c | `closed_loop_success_proxy`, constrained families | drop **≤ 0.10 absolute** vs 0 % loss | set equal to the D4 tolerance by design: **losing 10 % of packets may cost at most as much as removing the global view entirely.** If it costs more, communication robustness is the binding problem, not decentralization |

**"Collapse" — the disqualifying observation, defined so it is falsifiable.**
Any one of:

- full-swarm `agreement_rate` on connected epochs **< 0.50** (worse than a coin
  flip between agreeing and not);
- `closed_loop_success_proxy` drop **> 0.10** absolute (D6.c breached);
- the committed-mode distribution degenerating to a single mode when it was not
  degenerate at 0 % loss — i.e. the swarm stops selecting and starts defaulting.
  Measured as: the minority committed-mode share over decision epochs falls
  below 0.05 having been above it at 0 % loss.

**Explicitly NOT required.** Full agreement under a **disconnected** `G_c` is
**not** required and **not** measured as a failure. Robots that cannot exchange
a single message are not expected to agree, and scoring them as a consensus
failure would misattribute a connectivity fact to the algorithm
(`consensus.component_agreement` docstring;
`FULLY_DECENTRALIZED_SYSTEM_MODEL.md` §12). Disconnected epochs are reported
separately, with their component structure and their share of all epochs.

**Reporting requirement.** The full frozen sweep (loss 0 / 10 / 30 / 50 %, delay
0 / 1 / 2 / 5 steps) is reported for context. **Only the 10 % loss / 0 delay
point gates.** The rest is description, and — see §3.3 — is never used to
re-pick a parameter.

**FAIL means.** The communication-robustness claim is removed from the paper
entirely. Results are reported for the nominal link model only, and the loss
sensitivity becomes a stated limitation with its measured curve. It does **not**
invalidate D1–D4: a system can be genuinely decentralized and genuinely fragile,
and conflating the two would hide the more interesting finding.

---

### D7 — SCIENTIFIC SIGNAL (is there information, or just a majority vote?)

**Data.** Validation **decisive** subset only, exactly as defined in
`DECISIVE_MODE_METRIC_SPECIFICATION.md` §2 (`keep_only` ∪ `line_only`;
`both_succeed` and `both_fail` contribute nothing, in either direction). Modes
are the post-consensus committed modes of the decentralized selector at
`K_score = K*`. Ordering invariance and the 0.5-for-tie rule of §5 apply
unchanged.

**References** — mandatory, on the **exact same decisive subset**, per §4 of
that specification:

```
always_keep_ref = keep_only / decisive
always_line_ref = line_only / decisive
majority_ref    = max(keep_only, line_only) / decisive
```

**Gate.** All three must hold:

| Sub-gate | Criterion | Threshold |
|---|---|---|
| D7.a | `decisive_accuracy` exceeds the strongest reference | **≥ majority_ref + 0.10** |
| D7.b | `decisive_balanced_accuracy` | **≥ 0.60** |
| D7.c | tie fraction on the decisive subset | **≤ 0.05** |

**D7.a — why `majority_ref` and why +0.10.** `majority_ref = max(always_keep_ref,
always_line_ref)` by construction, so the majority reference is the binding one
and the other two are reported for transparency, never as an easier bar. The
margin 0.10 is calibrated against the separation the metric has already been
shown to produce: under the decisive metric an always-keep predictor scored
**0.228** while both mode-conditioned models scored **0.965** — a separation of
**0.737** (dry run V2 §1, §3). A required margin of 0.10 is roughly one seventh
of that demonstrated separation: large enough that noise and tie-breaking cannot
manufacture it, small enough that the decentralized selector is not required to
match a centralized model to be judged informative. It is also numerically equal
to the D4 tolerance, so the project carries one 0.10 scale rather than several.

**D7.b — why balanced accuracy is the anti-degeneracy criterion.** A constant
predictor has one recall 1.0 and the other 0.0, so its balanced accuracy is
**exactly 0.50 by construction**, whatever the class prevalences. Requiring
≥ 0.60 therefore demands real information about **both** classes and cannot be
satisfied by any always-keep or always-line policy — which is exactly the
failure the v1 metric rewarded (`DECISIVE_MODE_METRIC_SPECIFICATION.md` §1).

A **consequence**, not a fourth threshold: since each recall ≤ 1.0, a mean ≥ 0.60
forces `min(decisive_keep_recall, decisive_line_recall) ≥ 0.20`. Both recalls and
the full 2×2 confusion matrix are reported, but no separate recall threshold is
declared — one derived floor is cleaner than two hand-set ones.

**D7.c — why ties gate.** Under §5 an exact tie scores 0.5. A selector that ties
often can drift toward 0.5 accuracy while expressing no preference at all, and
ties are more likely here than in the centralized pilot because averaging
consensus pulls robots toward a common value. Above a 5 % tie rate the accuracy
number is measuring indecision, and D7 is reported **FAIL**.

**Stratification requirement.** D7 must be reported separately for `N=6` line —
the only multi-hop configuration — as well as pooled. A pooled pass carried
entirely by one-hop-complete configurations is reported as such.

**FAIL means.** No scientific claim may be made for the decentralized recovery
selector. The honest report is that it does not carry useful mode information
beyond the majority mode on decisive states, and the recommendation is: **do not
run the multi-seed decentralized study.** A three-seed run of a majority-class
predictor buys nothing, which is the same structural argument that produced
verdict B in dry run V2 §8.

---

## 3. Predeclared parameter-selection rules

### 3.1 `K_score` selection

- **Grid:** `K_SCORE_GRID = (0, 1, 2, 3, 4, 6)`, frozen in
  `system_model.py:144` before any run.
- **Data:** validation layouts **only**. `build_layouts("test")` is not read.
- **Criterion — a frozen hierarchy, evaluated in order, mirroring the existing
  checkpoint-selection hierarchy so the project has one selection idiom:**

  1. full-swarm `agreement_rate` on connected decision epochs — **higher better**;
  2. tie-break: **median `consensus_residual`** — lower better;
  3. tie-break: `closed_loop_success_proxy` on constrained families — higher better;
  4. final tie-break: **smallest `K`** — communication cost. Guarantees the
     selection is single-valued with no discretion left.

- **`K_score = 0` is eligible.** It is in the grid as the no-communication
  control and is the D3 comparator. If it wins the hierarchy, that is the
  result: it is recorded, D3 fails by construction, and no post-hoc reason is
  offered for excluding it.
- **Ordering:** `K*` is selected and **written into the report before any of
  D2, D3, D4, D6, D7 is computed**. The selected value and the full per-`K`
  table are published together, so a reader can see what the other five points
  scored.
- The default `k_score = 4` in `ConsensusParams` is a **placeholder, not a
  validated choice** (`FULLY_DECENTRALIZED_SYSTEM_MODEL.md` §13) and carries no
  privilege in the selection.
- Diameter context, so the grid is read correctly: the on-template `N=6` line
  graph has diameter **2** at `R_comm = 3.0`; the other three configurations are
  one-hop complete (diameter 1). Metropolis–Hastings propagates **exactly one
  hop per round**, so `K ≥ 2` is the minimum that can move information end to
  end in the only multi-hop configuration. `K = 0` is no communication; `K = 6`
  is three times the diameter.

### 3.2 `H_commit` is fixed at 10 and is not selected

`H_commit = 10` control steps (`ConsensusParams.h_commit`) and is **not swept,
not tuned, and not re-selected** anywhere in this study.

It **must** equal `recovery_v2.rollout(h_commit=10)`, the horizon at which the
Recovery Event V2 labels that supervise the selector are generated
(`RECOVERY_EVENT_V2_DEFINITION.md` §5–§6;
`FULLY_DECENTRALIZED_SYSTEM_MODEL.md` §4). If the runtime commit horizon
differed from the labelling commit horizon, the selector would be trained on a
decision it never gets to make, and every D-gate number would be measuring a
mismatch rather than a system. The predeclared `H_commit` grid `{5, 10, 20}`
belongs to the label-sensitivity study, not to this one; touching it here would
silently invalidate the labels. `decision_interval = 25 > 10` so each commit
horizon completes before the next forced epoch.

### 3.3 `R_comm` and `Delta_stale` are not tuned — on final-test data or at all

`R_comm = 3.0 m` and `Delta_stale = 3` control steps are fixed at their
`CommParams` defaults. They were justified **from environment geometry before
any run** (`FULLY_DECENTRALIZED_SYSTEM_MODEL.md` §4, §4.1): 3.0 m keeps the
`N=6` line connected but genuinely multi-hop (span 4.5 m; end robots out of
range) while the `N=6` keep grid at 2.012461 m is one-hop complete; 3 steps is
0.45 s, within which a neighbour at `max_speed = 0.9 m/s` moves at most 0.405 m,
comfortably inside `nominal_spacing = 0.9 m`.

Predeclared, absolutely:

- **Neither is selected on final-test data.** No final-test data is read.
- **Neither is selected on validation data either.** They are not free
  parameters of this study; only `K_score` is.
- The stress sweep (loss 0/10/30/50 %, delay 0/1/2/5 steps) is a **reporting**
  sweep, not a selection sweep. No nominal value is re-picked from its results.
  If some swept point looks better than the nominal one, that observation is
  **reported**, not adopted.
- If a change to either is ever judged necessary, it requires a dated amendment
  to this document stating which results already existed at the time, and every
  affected number must be re-measured and re-reported — not retro-fitted.

### 3.4 Final-test protocol

No gate in this document reads the final-test set. If, and only if, D1 passes
and a majority of D2–D7 pass, a single final-test evaluation may be run **once**,
with no re-tuning of anything, using the already-frozen `K*`, `H_commit`,
`R_comm`, `Delta_stale`, and the already-selected checkpoint.

---

## 4. What would falsify this design

For each gate, the concrete observation that fails it. Written before the run so
that these outcomes are predictions the design can lose, not surprises to be
narrated afterwards.

| Gate | Concrete falsifying observation |
|---|---|
| **D1** | `guards.audit()` returns any non-empty list. **Or:** any test in `test_ego_graph_locality.py` fails, or the required `test_decentralization_guards.py` cannot be written to pass. **Or:** a scanner cannot be made to go red under an injected offender — a guard that never fails is not evidence. **Or:** the return-shape scanner of §2.D1.a, once written, finds a deployable function emitting an `(N, 2)` action array. **Or:** `local_progress` turns out to be populated from `obs["progress"]` — the name check passes, the contract is violated, and this is flagged in the system model as the single most likely silent violation. |
| **D2** | Full-swarm agreement 0.93 on connected epochs — close, and still a fail. **Or:** agreement ≥ 0.95 pooled but < 0.95 on `N=6` line, the only multi-hop configuration: the aggregate would then be a one-hop broadcast result. **Or:** median residual 0.09 with agreement 1.000 — argmax agreement without value convergence, meaning finite `K` has not converged. **Or:** median residual 0.004 achieved because the median decisive margin is 0.05 logits: the anti-degeneracy guard fires and this is a FAIL, not a pass. **Or:** confirmation condition 4 fails — robots commit a mode that is not their own post-consensus argmax, i.e. a leader in disguise. |
| **D3** | `K* = 0` wins the §3.1 hierarchy. **Or:** `K*` improves agreement from 0.90 to 0.99 (+0.09, passes the improvement arm) while `closed_loop_success_proxy` falls from 0.62 to 0.56 (−0.06 > 0.03): material degradation, gate fails. **Or:** all three metrics move by less than 0.05 — consensus changes nothing measurable, and "no effect" fails the improvement arm just as an adverse effect would. **Or:** the only improvement is 2 episodes on M3 (0.04 < 0.05) — below threshold and below the realisable-improvement floor of 3 episodes. |
| **D4** | Decentralized 0.52 vs centralized 0.68: gap 0.16 > 0.10, fails. **Or:** decentralized 0.80 vs centralized 0.62: gap 0.18 in the *favourable* direction — also fails, as an unmatched comparison, because the arms are built to differ only in mode sourcing. **Or:** the gap is 0.06 but the two arms turn out not to be matched (different seeds, different executor, different `H_commit`), in which case the number is void regardless of its size. |
| **D5** | *(Already measured; these are what would have falsified it.)* Local keep 0.340 against centralized 0.450 → fraction 0.756 < 0.80. **Or:** local line 0.700 against centralized 1.000 → fraction 0.700 < 0.80, failing on line alone — which the per-mode rule catches and a mean over modes (0.5 × (1.556 + 0.700) = 1.128) would have hidden. **Or:** the `(|N_i| + 1)` normalisation is found to have drifted to `|N_i|`, inflating the local error by `n/(n−1)` and unmatching the comparison at its root. |
| **D6** | At 10 % loss: full-swarm agreement on connected epochs 0.78 < 0.85. **Or:** `component_agreement` 0.86 < 0.90 — robots that *could* hear each other still failed to agree. **Or:** `closed_loop_success_proxy` 0.62 → 0.46, a drop of 0.16 > 0.10. **Or:** the minority committed-mode share collapses from 0.31 to 0.02 — the swarm has stopped selecting and started defaulting. **Or:** the across-comm-seed range on the gating metric is 0.14 against a margin of 0.10 → INCONCLUSIVE, which is not a pass. **Not falsifying:** disagreement between robots in different components of a disconnected `G_c`. |
| **D7** | `decisive_accuracy` 0.71 with `majority_ref` 0.68 — a 0.03 margin, below the required 0.10, so the selector is a majority-class predictor with noise. **Or:** `decisive_accuracy` 0.88 with `decisive_balanced_accuracy` 0.53 — high pooled accuracy, one recall near zero, and the constant-predictor floor of 0.50 barely cleared. **Or:** tie fraction 0.22 — consensus averaged the robots into indifference and the accuracy figure is measuring coin flips. **Or:** pooled pass with `N=6` line at chance — the multi-hop case, which carries the evidential weight, has no signal. |

---

## 5. What each failure does to the recommendation

| Gate | FAIL ⇒ recommendation |
|---|---|
| D1 | **Veto.** No decentralization claim in any form. Fix, or reframe as a centralized selector with a local controller. |
| D2 | Drop "swarm-wide agreement"; claim per-component agreement only, with the component structure printed. |
| D3 | Consensus is not a contribution. Report `K_score = 0` as the system; publish the consensus result as a measured negative. |
| D4 | Decentralization is not free. Report the measured cost as a headline limitation, with sign and CI, in the abstract. |
| D5 | **(Passing.)** Had it failed: redesign the controller before measuring anything else — every other closed-loop gate executes with it. |
| D6 | Remove the communication-robustness claim. Report nominal-link results only; publish the loss curve as a stated limitation. Does not invalidate D1–D4. |
| D7 | No scientific claim for the decentralized selector. **Do not run the multi-seed study.** |

**Aggregate rule, predeclared.** The full claim in
`FULLY_DECENTRALIZED_SYSTEM_MODEL.md` §12 requires **D1 ∧ D2 ∧ D5 ∧ D7** at
minimum: locality, agreement, a controller that works, and a selector that
carries information. D3, D4 and D6 shape what may be claimed *about* the design
(contribution of consensus, cost of decentralization, robustness); they do not
gate the existence of the decentralization claim itself. No combination of
passes substitutes for a D1 failure.

---

## 6. Reporting rules that apply to every gate

1. Every proportion is printed with its denominator and its resolution.
2. Every agreement number is stratified by configuration; `N=6` line is always
   broken out, because it is the only genuinely multi-hop case.
3. Every `decisive_accuracy` is printed beside `always_keep_ref`,
   `always_line_ref`, `majority_ref`, the 2×2 confusion matrix, the tie count,
   and `decisive_coverage` — the mandatory reference policy of
   `DECISIVE_MODE_METRIC_SPECIFICATION.md` §4, which exists so a degenerate
   result cannot recur silently.
4. Centralized references are labelled *centralized* in every table.
5. `closed_loop_success_proxy` is never printed as "Task-Recovery V2" without
   the proxy qualifier (§1.3).
6. A gate whose margin is below the measurement resolution is **INCONCLUSIVE**,
   not a pass.
7. Failing gates are reported with the same prominence as passing ones, in the
   same table, in D1–D7 order.

---

## 7. Known gaps in the apparatus at freeze time

Stated now so that none of them can later be described as a detail that emerged
during the run.

1. **`tests/test_decentralization_guards.py` does not exist.** No test currently
   exercises `guards.audit()` (verified by grep at freeze). D1 check 1.3 is a
   requirement to be met, not a description of the present state.
2. **No return-shape scanner exists.** "No central joint-action generation" is
   unenforced today; see §2.D1.a.
3. **`closed_loop_success_proxy ≠ Y_task`.** The closed-loop gates measure a
   proxy that omits the `crossed_exit` conjunct and uses terminal `form_ok`; see
   §1.3.
4. **The confirmation protocol (`K_confirm`) is specified but not implemented.**
   D2.b defines what must be measured; the code that measures it does not yet
   exist.
5. **No decentralized selector has been trained.** D2, D3, D4, D6 and D7 all
   presuppose a trained selector and a selected checkpoint; neither exists at
   freeze.
6. **`RobotView.obstacles` tuple layout is still unfixed in the contract**
   (`FULLY_DECENTRALIZED_SYSTEM_MODEL.md` §9). It must be ego-relative
   `(rel_x, rel_y, radius)`; an absolute layout would smuggle world coordinates
   into a deployable structure and would be a D1 failure.
