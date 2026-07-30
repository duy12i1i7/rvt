# Fully Decentralized Selector — Seed-0 Gate Report

Branch `research/fully-decentralized-selector-v1` from tag
`binary-mode-end-to-end-diagnosis-v1`.
Validation layouts only · **no final-test layout was loaded** · seed 0 · 330 tests pass.

Results: `results/decentralized/dry_run_seed0/` ·
Gates: [`PREDECLARED_DECENTRALIZATION_GATES.md`](PREDECLARED_DECENTRALIZATION_GATES.md)

---

## 1. Recommendation

> ### **D — The implementation is free of hidden centralized dependencies, but the experiment contains validity defects that must be repaired before a three-seed pilot.**

This is **not** a finding of hidden centralization. Locality is clean and
demonstrated (§3). The defects are in the *experiment*, and there are three:

1. **The validation scenario set no longer has keep/line headroom.** With the
   robot-local controller, `always_line` succeeds on **every** validation family
   (1.000), while the best learned arm reaches 0.861. A mode selector cannot be
   shown to help when one fixed mode already wins everywhere.
2. **The Task-6 periodic epoch protocol degrades performance** and misses gate
   D2 (0.933 < 0.95). Re-deciding every 25 steps scores 0.611 against 0.861 for
   a single commitment at t=0.
3. **The validation-selected `K_score = 1` disables consensus under any delay
   ≥ 1 step**, because a delayed message cannot arrive within a single round.
   Agreement collapses 0.933 → 0.039.

A three-seed pilot run today would measure a decision that does not change
outcomes, using a protocol that hurts, at a consensus depth that fails under
delay. None of that is fixed by more seeds.

## 2. The headline result, stated plainly

**Leaderless consensus is the component that works, and it works dramatically.**

| arm | success | full agreement |
|---|---|---|
| recovery selector, **no** consensus (K=0) | 0.250 | 0.250 |
| recovery selector, **with** consensus (K=1) | **0.861** | **1.000** |
| periodic epochs, no consensus | 0.000 | 0.161 |
| periodic epochs, with consensus | 0.611 | 0.933 |

Without consensus the robots disagree, the formation tears apart, and the
episode fails. With it they commit to one mode and the episode succeeds. Gate
D3 asked whether consensus adds value; it adds **+0.611 success and +0.750
agreement**. That is the strongest result in this dry run.

Note the offline K-sweep is nearly **flat** (Brier 0.159 at K=0 → 0.123 at
K≥1, unchanged thereafter) while the closed-loop effect is enormous. The offline
metric scores a *team-averaged probability*; the closed loop requires every
robot to commit to the *same mode*. Selecting K on the offline proxy is what
produced K=1, and K=1 is what fails under delay (§6). **The K-selection
procedure is measuring the wrong thing.**

## 3. Gate results

| gate | criterion | measured | verdict |
|---|---|---|---|
| **D1** locality | 100 % of forbidden-access tests pass | `guards.audit()` = **0 violations**; 16 guard tests; 330 total | **PASS** |
| **D2** nominal agreement | full agreement ≥ 0.95, confirmation ≥ 0.95 | single-decision **1.000**; periodic **0.933** | **PASS (single) / FAIL (periodic)** |
| **D3** consensus value | improves ≥ 1 of {agreement, decisive acc, task recovery} without material loss | success 0.250 → **0.861**; agreement 0.250 → **1.000** | **PASS, decisively** |
| **D4** global-reference gap | ≤ 0.10 absolute vs centralized diagnostic | offline AUROC **0.946 vs 0.937**, Brier **0.094 vs 0.095** | **PASS (offline)**; closed-loop centralized arm **not run** |
| **D5** local controller | ≥ 80 % of matched centralized | keep **0.700 vs 0.450 (156 %)**, line **1.000 vs 1.000 (100 %)** | **PASS** |
| **D6** 10 % packet loss | graceful, not collapse | success 0.611 → **0.667**, agreement 0.933 → **0.806** | **PASS** |
| **D7** scientific signal | beats majority-mode reference | decisive accuracy **0.877–0.930** vs always-keep **0.228** | **PASS** |

D1 evidence is executable, not asserted. The guard is annotation- and AST-based,
walks the whole package including classmethods, and was verified to catch six
injected offenders (bulk `np.ndarray` parameter, unannotated `all_poses`,
`joint_state`, prohibited `obs["positions"]` read, `pooled_graph_features` call,
`expert_action` call, and a boundary call inside a control-loop function). The
predecessor guard asserted `[] == []` and stayed green under injection.

## 4. Answers to the required questions

1. **Does every deployable robot use only permitted local information?** Yes,
   with one disclosed exception: neighbour **degree**. `deg_j` rides in the
   beacon (required by the Metropolis-Hastings weight rule and permitted by the
   protocol spec) and counts robots that may lie outside `N_i`, so a two-hop
   robot can shift `w_ij` from 1/3 to 1/2. Recorded in
   `system_model.DISCLOSED_AGGREGATE_CHANNELS` and pinned by a test that asserts
   degree is the *only* field that differs. One integer per neighbour per
   message; no identity, position, or state.
2. **Any hidden centralized call path?** None found. 0 guard violations.
3. **Is neighbour discovery genuinely peer-to-peer?** Yes. Beacons carry the
   sender's own state and no list-valued field, so nothing travels two hops.
4. **Is the ego graph truly local?** Yes — 28 features, every one traced to a
   permitted source, no global pooling operator, and a center-node readout so
   "no pooling" is structural rather than argued.
5. **Is score aggregation leaderless?** Yes. Identical update on every robot;
   no aggregator object; verified average-preserving.
6. **Does any robot act as coordinator?** No.
7. **Can every robot compute its own action?** Yes. `local_controller` takes one
   `RobotView` and returns one 2-vector.
8. **Does consensus improve agreement?** Yes: 0.250 → 1.000.
9. **Does consensus preserve selector performance?** Yes, and improves it.
10. **Does the local controller execute both modes?** Yes — keep 0.700, line
    1.000, both at or above the centralized reference.
11. **Under packet loss and delay?** Loss degrades gracefully (0.667 at 10 %,
    0.306 at 30 %, 0.194 at 50 %). **Delay does not** — see §6.
12. **Under disconnection?** Component-wise agreement is reported and swarm-wide
    agreement is not claimed. At half range, full agreement 0.490 vs component
    agreement 0.540.
13. **What connectivity assumptions are needed?** Swarm-wide agreement requires
    a connected `G_c`. At `r_comm = 3.0` on these layouts the graph is
    **one-hop complete for 96.6 % of robots** (mean degree 4.20) — see §5.
14. **What bandwidth?** Beacon payload is 49 bytes by the declared wire schema.
15. **Can it honestly be called fully decentralized?** **Yes**, with the stated
    connectivity assumption and the disclosed degree channel.
16. **Is a three-seed pilot justified?** **No** — for the reasons in §1.

## 5. The finding that undermines the experiment

At `r_comm = 3.0 m`, **96.6 % of robots see the entire team in one hop**
(mean degree 4.20 at N ∈ {4, 6}). The keep grid at N=6 spans ~2.0 m, well inside
3.0 m, and these episodes stay compact. So the communication graph is nearly
always complete and consensus has little topological work to do — which is
exactly why the offline K-sweep is flat.

More seriously, **`always_line` succeeds on every validation family**:

| family | always_line | best learned (single + consensus) |
|---|---|---|
| line_corridor | 1.000 | 0.833 |
| keep_line_keep | 1.000 | 0.625 |
| keep_open | 1.000 | 1.000 |
| ambiguous | 1.000 | 1.000 |

The keep/line headroom that motivated this study was established against the
**centralized** controller. The robot-local controller is *better* (§D5), and it
is good enough that line now works everywhere — so the headroom is gone. This is
a consequence of an improvement, not a regression, but it means the current
validation set cannot demonstrate any benefit from mode selection.

**The selector is not the problem.** Offline it reaches AUROC 0.946 / Brier
0.094 / decisive accuracy up to 0.930 against an always-keep reference of 0.228.
It knows which mode is better. There is simply no longer a penalty for getting
it wrong.

## 6. Communication stress (validation only, seed 0)

| packet loss | 0 % | 10 % | 30 % | 50 % |
|---|---|---|---|---|
| success | 0.611 | 0.667 | 0.306 | 0.194 |
| agreement | 0.933 | 0.806 | 0.518 | 0.389 |

| delay (steps) | 0 | 1 | 2 | 5 |
|---|---|---|---|---|
| success | 0.611 | **0.000** | **0.000** | 0.472 |
| agreement | 0.933 | **0.039** | **0.083** | 0.076 |

| `r_comm` | ×1.0 | ×0.75 | ×0.5 |
|---|---|---|---|
| success | 0.611 | 0.722 | 0.528 |
| full agreement | 0.933 | 0.844 | 0.490 |
| component agreement | 0.933 | 0.844 | 0.540 |

**The delay row is a design defect, not noise.** With `K_score = 1` there is
exactly one consensus round, so a message delayed by even one step arrives after
the round has closed and is never applied — consensus silently degrades to the
K=0 arm, whose agreement is 0.161. The delay-5 success of 0.472 is *not* a
recovery: its agreement is 0.076, i.e. it is the no-consensus arm and the
success figure is sampling noise on 36 episodes.

Separately, `Delta_stale = 3` means any delay > 3 steps is rejected as stale by
design; robots then keep their own pre-consensus value rather than act on stale
data. Correct behaviour, and it must be stated rather than presented as
robustness. **`K_score` must exceed the expected delay for consensus to
function at all.**

## 7. Defects found and fixed during this work

Nine real defects, six from an adversarial audit of the first build and three
found by the tests:

| defect | consequence |
|---|---|
| consensus admission gated on round index | any delay ≥ 1 rejected **every** message; consensus stalled at `applied = 0` |
| then gated on `round > self.round` | a clock-offset robot rejected all traffic; it and everything behind it were severed |
| `guards.py` did not exist although `system_model.py` claimed it did | the entire locality claim was undefended |
| old guard asserted `[] == []` | an injected `build_team_features(p_all: np.ndarray)` left it green |
| `from_initial_formation` read the joint state without the boundary prefix | the one joint-state reader was the one function the tests certified clean |
| `desired_offset_for_neighbour` had no input gate | a (6,2) joint-state array was smuggled through the call the controller uses |
| neighbour degree presented as one-hop-only | the two-hop test was constructed to avoid the failing case |
| peer sequence-counter restart | a rebooted neighbour was rejected as a duplicate **forever** |
| empty ego graph at 50 % loss | `scores.max()` crashed on an isolated robot |

Two of my own: the keep template's lateral axis had the opposite sign to the
centralized convention, and base terms were summed where the centralized
controller means them. Both were caught by the exact-correspondence check.

Four tests were rewritten: three asserted convergence tolerances unreachable in
the rounds they ran (1e-9 after 16 MH rounds on a path graph — the true value is
4.9e-2, reaching 5.6e-16 only by K=400), and two had been written to **pin the
buggy behaviour** they had just discovered.

## 8. Two exact properties, verified not assumed

- **Formation correspondence.** The mean over neighbours of `(p_j − p_i) − d_ij`,
  normalised by `(|N_i| + 1)`, equals the centralized `form_err_i` to **4×10⁻⁷**
  under full connectivity. The denominator is load-bearing: `|N_i|` inflates it
  by `n/(n−1)`, a 20 % error at N=6.
- **Train/deploy consensus identity.** The differentiable training recursion
  equals the runtime's message-passing implementation to **8×10⁻⁸** across
  path/ring/complete graphs at N ∈ {4,6}, K ∈ {0,1,2,4,6}. The model is not
  trained on a recursion it does not execute.

## 9. Required before any three-seed pilot

1. **Restore keep/line headroom.** Re-qualify the scenario families against the
   *robot-local* controller, not the centralized one. Either find geometries
   where line genuinely fails, or accept that binary keep/line selection has no
   headroom under this controller and reframe the question. This is the blocking
   item.
2. **Decide the decision regime on evidence.** Single commitment (0.861) beats
   periodic re-decision (0.611). If the epoch protocol is kept, its interval and
   commitment length need justifying against this measurement; note the previous
   pilot's standing prohibition on topology-switching claims applies directly to
   the periodic arm.
3. **Select `K_score` on a closed-loop criterion**, not offline Brier, and
   require `K_score > expected delay`. The flat offline sweep cannot see the
   effect that matters.
4. **Run the centralized diagnostic selector closed-loop** so D4 has a
   like-for-like comparison rather than an offline-only one.
5. Investigate why `direct_single_consensus` reaches 0.000 with agreement 0.000
   — its masked-CE logits are near-tied, so robots split; this may be a
   calibration artefact of training on decisive states only.

## 10. Scope and limits

Seed 0 only. 36 episodes per stress cell, 2 per (layout, N). **No robustness or
superiority claim is made from one seed.** Every number above is validation-set
only; no final-test layout was loaded at any point, which
`test_no_central_runtime_access.py` asserts by scanning the sources.

The permissible claim, and the only one made here: *leaderless, fully
decentralized execution using local observations and finite-round peer-to-peer
communication, under an explicitly stated communication-connectivity
assumption.* Swarm-wide agreement is **not** claimed when `G_c` is disconnected.
