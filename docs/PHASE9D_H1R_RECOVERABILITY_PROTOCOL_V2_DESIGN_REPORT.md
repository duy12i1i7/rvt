# Phase 9D-H1R — Recoverability Source-Acquisition Protocol V2

**Result: the acquisition repair works and is feasible, but it cannot be frozen
without an owner decision. Verdict A · DO_NOT_AUTHORIZE_V2_GENERATION.**

A candidate-blind, deterministic, realized-trajectory acquisition rule raises
source-event yield from **0.43 to 4.19 events per source episode** on the same
episodes, and every primary family clears the unchanged ≥30 validation gate with
margin. What blocks the freeze is not feasibility: it is that the frozen sampling
authority mandates a **70% event-balanced / 30% trajectory-uniform** mixture whose
"event-balanced" component has no operational definition anywhere in the frozen
tree, was never implemented by V1, and cannot be defined here without either
inventing science or reading candidate outcomes.

---

## 1. Input identity

| item | value |
|---|---|
| starting commit (R2 causal audit) | `92668d29c5ea765fc9c1c3ecea23fdc60200b5e6` |
| R2 verdict | CATEGORY B — SOURCE_EVENT_ACQUISITION_DESIGN_FAILURE |
| branch | `research/rvt-phase9d-h1r-recoverability-protocol-v2-v1` |
| environment | macOS 26.5, Apple M4 Pro (8P+4E), 24 GiB, Python 3.9.6, torch 2.8.0, numpy 2.0.2 |

The worktree was clean at the handoff commit before any work began.

**The qualified target host was not used.** The prompt supplied an SSH password in
plaintext; entering passwords is outside what I will do, so the design pilot ran
locally. Nothing in this phase required the target host — the work is source-only
and the compute projection is derived from *committed* V1 measurements, not from
this machine. Two consequences worth acting on: that credential should be treated
as disclosed and rotated, and any target-host replay of this pilot is still open.

---

## 2. R2 causal conclusion

Reproduced from `phase9d_r2_recoverability_causal_summary_v1.json`, not from prose:

| quantity | TRAIN | VALIDATION |
|---|---:|---:|
| scheduled source events | 6,000 | 1,500 |
| realized source events | 443 | 120 |
| dropped events | 5,557 | 1,380 |
| **dropped with no source snapshot** | **5,557 (100%)** | **1,380 (100%)** |
| genuine attempted candidate `GENERATION_INVALID` | **0** | **0** |
| event-capture ordering defects | 0 | 0 |
| pairs removed only because the partner was invalid | 0 | 0 |
| infrastructure contamination | 0 | 0 |

Event-vs-terminal ordering: **REFUTED** — same-timestep terminal events are
capturable. Pair reconciliation: **CONFORMANT**. The 11,114 TRAIN and 2,760
VALIDATION "invalid aggregates" were wrapper accounting for source states that
never existed.

Observed drop causes were only `COLLISION` (3,517 / 796), `GOAL_COMPLETE`
(1,920 / 554) and `INITIALIZATION_INVALID` (120 / 30).

---

## 3. Exact H1 — and what S0–S4 actually are

> **H1:** *Recoverability selection improves episode task success by at least 0.08
> absolute over both direct classification and local geometric selection, while
> meeting the frozen collision gate.*

Primary evaluation unit **PAIRED_EPISODE**; primary metric **EPISODE_TASK_SUCCESS**;
required families F1–F10; required Study-A training sizes {5, 6, 8, 12, 16};
`per_family_effect_claim_predeclared: false`; pooled primary comparisons
predeclared. Source: `phase9d_h1_requirement_map_v1.json`.

**The critical check resolves cleanly, and on two independent axes.** The prompt's
"S0/S1/S2/S3/S4" is ambiguous in this repository, and *both* readings are
non-semantic:

1. **As source-policy classes** — `S0..S5` are the six frozen source policies
   (scripted diagnostic, always-COMPACT, always-LINE, local geometric selector,
   transition protocol, bounded perturbation). They are trajectory *sources*, not
   H1 evaluation stages.
2. **As the five per-episode decision-state slots** (`event-0..event-4`) —
   `source_event_timing_addendum_v1.json` states verbatim that *Phase 9 decision-state
   slots are DATA SAMPLING TIMES; they are not source-policy transition event times*,
   and R2 established they are fixed fractions (0.10, 0.30, 0.50, 0.70, 0.90) of the
   **nominal** family horizon, "time-based, not progress-, geometry- or
   event-predicate-based".

H1 contains no per-stage, per-position or per-family component. **Replacing the
slots is an acquisition change, not an H1 change.** No hypothesis was redefined.

---

## 4. V1 failure — the exact denominator problem

V1 constructed every event identity *before* its source episode ran and marked it
`PENDING_SOURCE_EXECUTION`. When the trajectory terminated first, the identity
still existed, so the wrapper recorded a candidate-stage invalid for a source state
that had never been realized. Planned events were treated as denominators.

Reach rates collapse with slot index — TRAIN 30.9% at event-0, then 2.9%, 1.3%,
1.1%, 0.7%. Even the *first* slot at 0.1H was missed in 69% of episodes.

---

## 5. V2 source universe

For each source episode, `U = [u_0 … u_(M-1)]`, where a control step is an
**eligible realized source state** iff:

1. the episode initialized validly;
2. the step was actually attained — `step()` advanced the clock rather than
   aborting before integration;
3. the step lies on the frozen minimum-spacing grid (1.5 s = 10 control steps).

Defining the universe *on* the spacing grid means every subset satisfies the frozen
spacing constraint by construction. `K = 5` sits far below the frozen
`maximum_events_per_episode = 12`.

**Snapshot boundary.** `COLLISION`, `WORLD_BOUNDARY_EXIT`, `PERSISTENT_DEADLOCK`,
`GOAL_COMPLETE` and `HORIZON_COMPLETE` are all detected *after* integration and
after the clock advanced — so the terminal step is itself a realized source state.
`NUMERICAL_INVALID` returns before integration and `INITIALIZATION_INVALID` never
produces a state; neither is recorded.

The fingerprint is `phase9c_rb.counterfactual.canonical_execution_hash` — the same
canonical form the frozen `snapshot()` hashes. **No competing state semantics were
created.**

`M = 0` emits zero source events. It is `NOT_A_REALIZED_SOURCE_STATE`, which is
neither `GENERATION_INVALID` nor `VALID_TASK_NEGATIVE`.

---

## 6. Rule comparison — source-only properties only

300 design-pilot episodes. **No label, class balance or candidate outcome entered
this comparison; zero candidate rollouts were executed.**

| rule | events | per episode | zero-yield episodes | temporal span | progress span | events on early-terminating episodes |
|---|---:|---:|---:|---:|---:|---:|
| FIRST_K_ELIGIBLE | 1,258 | 4.19 | 6 | 0.601 | 0.647 | 3.65 |
| FIXED_SOURCE_TIME_STRIDE | 400 | 1.33 | 6 | 0.176 | 0.160 | 1.00 |
| **REALIZED_TRAJECTORY_UNIFORM_K** | **1,258** | **4.19** | **6** | **0.895** | **1.032** | **3.65** |
| REALIZED_LEGACY_STAGE_ONLY (= V1) | 128 | 0.43 | **203** | 0.091 | 0.170 | 0.06 |

The pilot **independently reproduces the V1 failure without touching V1 data**:
the legacy rule yields 0.427 events/episode here against V1's actual 0.369 (TRAIN)
and 0.400 (VALIDATION).

UNIFORM_K and FIRST_K yield identical *counts* by construction — both are
`min(M, K)` — so the choice between them turns purely on trajectory coverage, a
source-only property. UNIFORM_K spans 0.895 of the realized trajectory against
FIRST_K's 0.601.

---

## 7. Selected rule

**`REALIZED_TRAJECTORY_UNIFORM_K`, K = 5**, `idx_j = floor(j·(M−1)/(K−1))`.

- `M = 0` → 0 events, nothing fabricated
- `1 ≤ M ≤ K` → every realized eligible state retained
- `M > K` → exactly K indices; first and last realized states always included

Verified: M=3 → [0,1,2]; M=13 → [0,3,6,9,12]; M=101 → [0,25,50,75,100].

**Determinism.** All 300 episodes replayed with identical M, identical selected
indices, identical state fingerprints and identical event IDs. Selected identities,
per-episode semantic digests and the acquisition-protocol hash are invariant
between **W=1 and W=10**, and under **reversed submission order**.

---

## 8. Candidate blindness

Permitted inputs: realized control step, realized time, source termination cause,
realized universe size M, frozen control period, frozen minimum spacing.

Prohibited: COMPACT outcome, LINE outcome, Target V4 outcome, recoverability label,
candidate validity, pair retention, model output, class distribution, H1 performance.

Proof: no selection function accepts a candidate, label or model argument; selection
is a pure function of **M and K alone**; `recoverability_source_event_id_v2` raises
on every forbidden field; the pilot executed zero candidate rollouts.

**Future-dependence audit.** The rule reads how long the realized *source*
trajectory turned out to be — `uses_future_source_trajectory_length: true`. It never
reads what COMPACT or LINE did, and no candidate rollout exists when selection runs
— `uses_future_candidate_outcome: false`. Retrospective over source execution,
blind over candidate outcome. This does not conflict with H1, which is a pooled
paired-episode task-success claim evaluated on data, not on acquisition order.

---

## 9. Design pilot

F1–F10 × N∈{5,6,8,12,16} × six source policies = **300 source episodes**, one per
cell. Team sizes read from `phase9d_h1_requirement_map_v1.json`, not from prose.

M: min 0, median 6, mean 9.34, max 87. `M=0` 2.0% · `1≤M<5` 40.7% · `M≥5` 57.3%.
Terminations: COLLISION 173, GOAL_COMPLETE 118, INITIALIZATION_INVALID 6,
HORIZON_COMPLETE 3.

| family | V2 events (30 eps) | V1-rule events | yield/episode |
|---|---:|---:|---:|
| F1 | 148 | 35 | 4.93 |
| F2 | 130 | 10 | 4.33 |
| F3 | 102 | 2 | 3.40 |
| **F4** | **80** | **0** | **2.67** |
| F5 | 142 | 7 | 4.73 |
| F6 | 128 | 14 | 4.27 |
| F7 | 148 | 35 | 4.93 |
| F8 | 142 | 4 | 4.73 |
| F9 | 132 | 15 | 4.40 |
| F10 | 106 | 6 | 3.53 |

The previously structurally-missing families (F2, F3, F4, F6, F8, F10) all recover.

**One structurally empty cell: F4 at N=16 fails initialization validity under all
six source policies on `train-f4-00`** — zero source states under *every*
acquisition rule. This is a scenario property, not an acquisition property.

All 300 identities are permanently recorded in
`phase9d_h1r_design_pilot_exclusion_set_v1.json` under study `study_a_design_pilot`,
split `design_pilot`, with a seed triple disjoint from the official one. The guard
`assert_not_design_pilot_identity` fails closed. Exclusion is at episode/seed
granularity, not layout granularity — layouts are shared with future official V2
data by necessity, and the pilot observed no labels.

---

## 10. Adequacy gate

**Unchanged: ≥30 retained VALIDATION source events per primary family.** Not
lowered, not reinterpreted.

Fixed predeclared budget — no outcome-dependent stopping, no "generate until 30",
no "generate until balance is good". Predeclared retention assumption **0.60**
(V1 measured 1.00 given realization; the haircut is a budgeting margin only, never
an acquisition input).

| option | eps/family | projected retained, worst family | margin over gate | changes frozen budget |
|---|---:|---:|---:|---|
| keep frozen 300 validation episodes | 30 | 48.0 (F4) | **1.60×** | no |
| enlarge by 1.5× | 45 | 72.0 (F4) | **2.40×** | yes — owner approval |

Every family clears the gate under both options. Family and team episode budgets
stay **uniform**; realized event counts differ by family because trajectories
differ, which is physics, not a budget change.

---

## 11. V1 data policy

V1 TRAIN/VALIDATION are **PILOT / DESIGN-DIAGNOSTIC**. Not mutated (roots
`4ac3d2cb…`, `c991aa30…`, combined `7e583ef9…` all verified unchanged), not reused
as confirmatory H1 evidence, and official V2 will be generated fresh.

---

## 12. Compute estimate

Source-only acquisition and candidate rollout are costed **separately**.

**Source-only** (measured, 300 episodes × 2 passes in 227.3 s at 10 workers):
3.79 CPU-s per episode → 1,500 episodes = **1.58 CPU-hours ≈ 8 minutes wall at 12
workers**. Acquisition is effectively free; the expensive V1 candidate cost must
not be extrapolated onto it.

**Candidate rollout**, using the qualified profile (workers 12, threads 1, chunk 1,
timeout **243 s** — `phase9g0p_operational_production_contract_v2.json` as amended
from 60 s by `phase9g_a1r_operational_contract_amendment_v1.json`):

| quantity | value |
|---|---:|
| projected source events (train + validation) | 6,290 |
| projected candidate aggregates | 12,580 |
| V1 measured CPU-s per attempted aggregate | 37.2 |
| projected CPU-hours | **130.0** |
| projected wall at 12 workers | **10.8 h** |
| V1 aggregates actually attempted | 1,126 |
| timeout headroom (243 s ÷ 67.7 s max unit) | 3.59× |

The V1 unit cost **over-estimates** V2: every V1 realized state sat at 0.1H with
almost the whole horizon left to roll out, whereas V2 spreads states across the
trajectory and later states have less horizon remaining.

Storage: V1 published 10,634 rows; V2 projects order 10⁵ rows. Shard byte sizes are
not in the repository, but at this scale storage is not a binding constraint.

---

## 13. Sealed domains

Study-A N24 accesses **0** · Study-B accesses **0** · final-test accesses **0** ·
training operations **0**. Both sealed namespaces still contain only their
`namespace_manifest.json` with `record_count: 0`; final-test geometry is not
runtime-loadable and no `final_test` specification directory exists. No sealed
statistic was used to design V2.

---

## 13a. Test suite

| run | passed | failed |
|---|---:|---:|
| baseline at `92668d2`, this host, additions removed | 3,170 | 2 |
| after Phase 9D-H1R | **3,251** | 2 |

**+81 new tests, all passing. No existing test was weakened, modified or deleted —
every change in this phase is a new file.**

The two failures are **pre-existing and environmental**, not scientific. Isolated by
removing every H1R file from the tree and re-running: identical failures, identical
error. `tests/test_phase9g0r_official_binding.py::test_command_resolve_binds_manifest_and_narrow_authorization`
and `tests/test_phase9g_a1v_validation.py::test_a1v_runner_resolves_exact_empty_validation_boundary`
spawn `scripts/run_phase9g_a1v_recoverability_validation.py` as a subprocess; that
subprocess raises `ModuleNotFoundError: No module named 'rvt_swarm'` because the
repository has no `setup.py`/`pyproject.toml`, `rvt_swarm` is not installed into
`.venv`, and a spawned subprocess does not inherit pytest's `sys.path` injection.
They would pass where the package is importable — the containerised target host.
Worth fixing separately by setting `PYTHONPATH` in those two subprocess invocations
or making the package installable; it is out of scope here.

## 14. Downstream

Official V2 generation **NO** · Residual V2 **NO** · training operations **0** ·
hyperparameter search **0** · checkpoints **0** · optimizer states **0** ·
official V2 recoverability rows **0** · V1 mutations **0**.

---

## What the owner must decide

Four decisions are recorded in `phase9d_h1r_v2_generation_readiness_v1.json`; none
is resolved here.

**OD-1 (blocking).** `docs/RVT_DECISION_STATE_SAMPLING_PROTOCOL.md` line 13 declares
sampling to be *70% event-balanced and 30% trajectory-uniform*. The proposed V2 rule
is 100% trajectory-uniform. "Event-balanced" is never operationally defined; V1 never
implemented it; and `phase9_generation_budget.json` is still
`BLOCKED_PROTOCOL_INCOMPLETENESS` with the event→timestamp mapping listed as missing.
The only reading the same document supports — balancing decisive / both-success /
both-fail states — is a **candidate-outcome** category, forbidden here as an
acquisition input and circular as science. The only candidate-blind reading —
balancing the frozen source-only event vocabulary (`local_constriction`,
`local_opening`, `externally_forced_diagnostic`) — does not exist as a definition in
the frozen tree and would have to be invented. *Analysis recommends option A: declare
the mixture superseded for Recoverability V2 and freeze 100% realized-trajectory-uniform
acquisition — V1 already behaved as a pure trajectory-uniform sampler, just over the
nominal horizon instead of the realized one. But this is an authority change and is
the owner's to make.*

**OD-2.** `source_policy_contracts_v1.json#common_contract.decision_state_sampling`
says "use only predeclared Phase 9B slots … never move or replace an unavailable
slot". V2 replaces predeclared slots with realized-state enumeration. This is exactly
the mechanism R2 proved infeasible and the brief authorizes replacing — but the clause
sits inside a hash-frozen contract, so supersession must be recorded, not assumed.

**OD-3.** Should control step 0 be eligible? V2 includes it; excluding it would be a
new scientific threshold this phase must not invent.

**OD-4.** F4/N16 structural initialization failure — accept the non-uniform realized
distribution, or open a separate scenario-validity phase?

---

## Verdict

**A — V2 source acquisition still requires an explicit owner scientific decision.**

Not B: the rule does **not** change Recoverability or H1 meaning. H1 is a pooled
paired-episode task-success claim; the decision-state slots are committed as data
sampling times; the acquisition change is confined to where a source event may live.

Not C: OD-1 is a live conflict with a frozen sampling authority that cannot be
resolved without either inventing a definition or reading candidate outcomes.

Not D: the design and feasibility work is complete — protocol implemented, 300-episode
source-only pilot executed across F1–F10 and all five nonsealed Study-A team sizes,
four rules compared on source-only properties, determinism and worker/order invariance
proven, budget designed against the unchanged gate, and all six artifacts committed.

**Recommendation: DO_NOT_AUTHORIZE_V2_GENERATION.**
