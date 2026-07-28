# RVT-Swarm — Prescreen Diagnosis, Claim Audit, and Scientific Redesign

**Manuscript audited:** Access-2026-23555, *"RVT-Swarm: Recoverability-Aware Topology Control for Decentralized Swarm Formation"* (desk-rejected, IEEE Access, 27-May-2026), together with the post-rejection revision currently in `latex/access.tex` (retitled *"Rollout-Supervised Resilient Formation Reconfiguration in Multi-Robot Systems"*, 13 pp.).

**Reference exemplar:** Goeckner et al., *MAGEC*, IROS 2024 — used only as a standard for research-question clarity, claim–experiment alignment, generalization design, disturbance design, and reproducibility. Not used as a numerical baseline (different task, discrete action space).

**Source code audited:** `/Users/udy/rvt` @ `fab222b`. All findings below that concern implementation are cited to `file:line` and, where marked **[VERIFIED BY EXECUTION]**, were confirmed by running the code, not by reading it.

---

## Contents

| Part | Content |
|---|---|
| 1 | Executive prescreen verdict |
| 2 | Ranked desk-reject causes |
| 3 | Claim–evidence matrix |
| 4 | Recommended central hypothesis |
| 5 | Recommended title and contributions |
| 6 | Components to keep / simplify / demote / remove |
| 7 | Baseline replacement plan |
| 8 | Mandatory experiment plan |
| 9 | Statistical protocol |
| 10 | Recoverability validation plan |
| 11 | Decentralization validation plan |
| 12 | Revised paper outline |
| 13 | Rewritten title, abstract, introduction |
| 14 | Revised method specification |
| 15 | Table and figure designs |
| 16 | Discussion, limitations, conclusion |
| 17 | Reproducibility checklist |
| 18 | Venue strategy |
| 19 | Week-by-week action plan |
| 20 | Special questions + final readiness checklist |

---

# PART 1 — EXECUTIVE PRESCREEN VERDICT

**PRESCREEN DECISION: DESK REJECT.** I reach the same decision the IEEE Access editor reached, and I would reach it again on the current revision. The retitling and the `shield`→`safety filter` terminology swap do not change the outcome, because the reasons for rejection are evidential, not lexical.

**The five decisive reasons.**

1. **The primary safety metric does not measure what the manuscript says it measures.** The paper defines `CollisionFree` as *"zero robot–robot and robot–obstacle collisions over the episode"* (`latex/access.tex:1049`). The evaluation code returns only the **final timestep's** metric dictionary (`rvt_swarm/evaluate.py:59-66`). **[VERIFIED BY EXECUTION]** an 8-robot narrow-passage episode was clean on 26.7 % of steps, was *not* episode-wide collision-free, and its terminal-step value — the value that enters every table — was the only one reported. Every "Coll-Free" number in Tables 1–2 and both appendix tables is a terminal-state snapshot. *This alone invalidates the safety column of the entire paper.* (Classification: **invalidates current conclusions**.)

2. **The collision metric is unsatisfiable by construction after any contact.** Robot radius 0.18 m; the simulator's overlap projection separates a contacting pair to **0.380 m** and pushes a robot off an obstacle to **0.540 m** (`rvt_swarm/environment.py:426-461`), while the collision thresholds are **0.400 m** and **0.550 m** (`rvt_swarm/config.py:18-19`). **[VERIFIED BY EXECUTION]**: post-resolution, `collision_free = 0.0` in both cases. Worse, at full compression the *commanded* formation spacing is `0.9 × (0.40/0.9) = 0.400 m`, exactly the collision threshold — the controller is instructed to drive the team onto the failure boundary. This is the mechanical explanation for collision-free rates of 0.11–0.49 across *all* methods, and it means the benchmark measures a simulator artifact rather than controller safety.

3. **Named baselines are not the algorithms described.** The manuscript's own "Compared Methods" text (`latex/access.tex:1084-1089`) describes ORCA as *"clipped goal tracking with velocity damping plus pairwise and obstacle repulsion"*, CBF-QP as *"the keep-topology expert action plus stronger reactive repulsion"*, and centralized MPC as *"the expert controller with a heuristic topology plus a centroid-to-goal bias"*. Those are `orca_like`, `cbf_qp_like`, and a legacy proxy (`rvt_swarm/baselines.py:159-207`). None is the named algorithm. An editor who reads that paragraph and then reads "RVT-Swarm outperforms ORCA / CBF-QP / MPC" stops reading. (The repository has since gained *genuine* ORCA-via-RVO2, a real per-robot CBF-QP, and a beam-search predictive controller — but the tables were never regenerated, so the paper and the code now disagree with each other.)

4. **The headline improvement is inside the noise of a single training seed with an unequal selection budget.** Success 0.315 vs. 0.310 for the plain GNN — a 0.005 gap, one seed (`rvt_swarm/train.py:305`), no confidence interval, no test. Meanwhile RVT-Swarm is trained for 300 epochs with ~30 rollout-validation checkpoint selections **plus** a top-5 re-check, while the GNN baseline gets 120 epochs and ~12 selections (`rvt_swarm/config.py:45-47`, `train.py:516-536`). The proposed method receives ≈2.5× the model-selection budget of the baseline it beats by 1.6 % relative.

5. **The system is not decentralized in the evaluated configuration.** At inference the entire team is packed into a *single* graph (`policy_runtime.py:21-28`, `batch_index` all zeros), and topology, recoverability, uncertainty, and auxiliary context are all read off a **mean pool over every robot in the team** (`models.py:270-283`). One topology is chosen centrally per team. The safety filter likewise consumes all robots' positions and all obstacles (`safety.py:70-105`). The word "Decentralized" in the submitted title is contradicted by the code that produced the numbers.

**Editorial confidence scores (1–10):** technical maturity **3**; novelty clarity **3**; empirical credibility **2**; presentation quality **3**; readiness for external review **2**.

**Minimum prescreen-pass conditions.** (i) Episode-wide safety metrics with a physically consistent collision threshold; (ii) baselines named honestly or replaced by faithful implementations with matched tuning budgets; (iii) ≥5 independent training seeds with paired uncertainty on every headline comparison; (iv) at least one genuine held-out generalization axis (unseen layout **or** unseen team size); (v) the words *decentralized*, *resilient*, *recoverability*, and *safe* either evidenced or removed; (vi) one falsifiable central question, ≤3 contributions, each mapped to a named experiment.

---

# PART 2 — MOST LIKELY DESK-REJECT CAUSES, RANKED

Ranked by my estimate of the probability that each independently caused the editor to stop.

| # | Cause | Category | Evidence | Fix class |
|---|---|---|---|---|
| 1 | **Absolute results are catastrophically weak while the language is triumphal.** Best success 0.315; best collision-free 0.488; collapse 0.430–0.699 for every method; ORCA at 0.005 success / 0.688 collapse. The abstract says "strongest overall performance"; the title says "resilient". A 31.5 %-success controller is not resilient. | weak experimental validation; inconsistent claims | `access.tex:1121-1134` | New experiments + claim removal |
| 2 | **Baseline fidelity.** Self-declared proxies presented under the names ORCA / CBF-QP / MPC with citations to `van2011orca`, `wang2017safety_barrier`, `jiang2024belief_mpc_formation`. ORCA at 0.005 success is a *prima facie* signal of a broken baseline; a competent editor knows ORCA does not fail 99.5 % of 2-to-24-robot navigation tasks. | unfair baseline comparison | `access.tex:1084-1090`; `baselines.py:159-207` | Re-implement + rename |
| 3 | **Self-serving checkmark table as the first table in the paper.** Table 1 gives RVT-Swarm ✓ in all seven capability columns and gives nine published papers ✗/△, with no operational definition of any column and no verification. This is the single most reliable desk-reject trigger in robotics venues. | unclear novelty; poor presentation | `access.tex:211-266` | Rewrite (no new experiments) |
| 4 | **Single training seed, 0.005 margin, no statistics.** The paper explicitly states "The paper reports a single-seed run, so multi-seed confidence intervals remain future work" — while simultaneously claiming superiority. | statistical weakness | `access.tex:1070-1071` | New training runs |
| 5 | **Terminology not licensed by evidence.** *Recoverability*, *decentralized*, *resilient*, *certifiable* (`InstantCert` is cited to a certifiable-reachability paper), *counterfactual*. None is formally defined and evidenced; the recoverability quantity is a hand-weighted shaped rollout return. | terminology problem | `recoverability.py:45-83` | Rewrite + new calibration experiment |
| 6 | **Ablation contradicts the title.** Removing topology selection entirely changes success by −0.003 (0.315→0.312) and *improves* formation satisfaction (0.438→0.444). The paper is titled after the component its own ablation shows to be nearly inert. | inconsistent claims | `access.tex:1198-1202` | Re-scope the paper |
| 7 | **Metric definitions in the paper do not match the code.** Episode-wide vs. terminal-step; "matched random starts" when starts are deterministic. **[VERIFIED BY EXECUTION]**: identical spawn positions for seeds 1 and 99 999. | lack of reproducibility; inconsistent claims | `evaluate.py:59-66`; `environment.py:80-92` | Rewrite + re-run |
| 8 | **Model selection on the test distribution.** Checkpoints are chosen by rollout validation on `narrow_passage` + `dynamic_obstacles` at N ∈ {8,16,24} using a lexicographic key over *success, goal-reached, collision-free, form-OK* — i.e. the reported test metrics, on the test distribution, with only a seed offset separating the episodes. There is no held-out split of any kind. | statistical weakness; weak validation | `train.py:376-424`, `config.py:63-67` | New experiments |
| 9 | **Presentation.** Placeholder DOI `10.1109/ACCESS.XXXX.XXXXXXX` and `Date of publication xxxx 00, 0000` on page 1; a dark, decorative, axis-free teaser with the word "Goal" overprinting the goal marker; a method figure whose column headers read "AI front-end encoder" / "AI back-end heads" and which embeds Python identifiers (`actions_by_topology`, `raw_pooled`); appendix tables with 37 columns compressed onto one page. | poor presentation | `access.tex:84-85`; `figures/teaser/a.png` | Rewrite (no new experiments) |
| 10 | **Scope signal.** Index terms are generic; no communication, no hardware, no sim-to-real, no formal result. Nothing marks the paper as an advance to an IEEE field of interest rather than a simulator study. | unclear scope | `access.tex:109-111` | Re-position |

**Problem classification summary**

- *Fixable by rewriting alone:* items 3, 9, 10; the self-favoring table; terminology; contribution list; metric definitions text.
- *Require additional explanation:* the training/inference information asymmetry; the role of the expert controller as a performance ceiling.
- *Require code changes:* episode-wide metric accumulation; collision-threshold/geometry consistency; decoupling training seed from evaluation seed; equalized epoch and selection budgets; per-robot inference path used for the reported numbers.
- *Require new experiments:* multi-seed training; faithful baselines; calibration of the recovery score; generalization splits; communication/decentralization study.
- *Invalidate current conclusions:* the terminal-step metric bug (#1, #7); baseline fidelity (#2); selection-budget asymmetry (#4, #8).
- *Require changing the title/central claim:* #5 (decentralized, recoverability, resilient) and #6 (topology selection is not carrying the result).

---

# PART 3 — CLAIM–EVIDENCE MATRIX

Verdict key: **S** supported · **P** partially supported · **U** unsupported · **C** contradicted by the manuscript's own evidence · **N** not testable from current evidence.

| # | Manuscript claim | Location | Type | Evidence provided | Evidence missing | Support | Risk if challenged | Rewrite fixes? | New experiment? | Recommended action |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | RVT-Swarm is **decentralized** | Title (submitted), abstract, contribution 1, Alg. 1 caption | decentralization | Verbal assertion; K=6 graph | Any evidence that inference is per-robot. Code packs the team into one graph (`policy_runtime.py:27`) and pools over all robots (`models.py:270-283`); safety filter uses all positions (`safety.py:78-105`) | **C** | Fatal — reviewer reads 15 lines of code | No | Yes — per-robot inference + agreement study | **[CLAIM MUST BE REMOVED]** from title until the ROS 2 per-robot path is the evaluated path |
| 2 | Performs **resilient** formation reconfiguration | Title (revision), abstract | robustness | Aggregate table | Any perturbation axis: no attrition, no packet loss, no delay, no sensor noise. Collapse ≥ 0.430 for the best method | **U** | Fatal — "resilient" with 43 % collapse | No | Yes — disturbance sweep | **[TERMINOLOGY MUST BE CHANGED]** → "formation reconfiguration" |
| 3 | Recoverability-aware reasoning improves control | Abstract, §4.2 | methodological | Ablation −Recoverability: 0.315→0.139 | The ablation is compound: it simultaneously (a) swaps KL+score+lower-bound+rank+uncertainty losses for a plain cross-entropy (`train.py:121-145`), (b) switches the runtime selector to `argmax(logits)` (`safety.py:546-550`), and (c) disables the shield's negative-recoverability escalation | **P** | High — reviewer will ask which of the three caused it | Partly | Yes — isolate into 3 variants | Split into `−score-loss`, `−score-selector`, `−shield-escalation` |
| 4 | Counterfactual rollout supervision is beneficial | Contribution 2, §4.3 | methodological | −Counterfactual: 0.315→0.263 | `use_counterfactual_topology` does **not** appear in `compute_loss`; training is byte-identical to Full. This ablation measures *only* selector substitution, not supervision | **C** (as labelled) | High — the label is wrong | Yes (relabel) | No for the relabel; yes for the real test | Relabel as "−score-based selection"; add a true no-rollout-supervision variant (behaviour cloning on `keep` only) |
| 5 | Explicit topology selection is necessary | Title, contribution 1 | novelty | −Topology: 0.312 vs 0.315 | Nothing shows necessity; F-OK is *better* without topology (0.444 vs 0.438) | **C** | Fatal for the title | No | Yes — bottleneck-stratified analysis | Demote from title; report as a conditional effect in narrow scenarios only |
| 6 | Adaptive geometry is necessary | Ablation row "Fixed formation" | methodological | 0.315 → 0.294 (−0.021), topo-switch 0.131 → 1.027 | One seed; no CI; `use_adaptive_formation_scale` also changes the *environment* (`environment.py:254`, `321-322`), so the variant is evaluated in a different dynamical system | **P** | Medium | No | Yes — multi-seed + fixed-environment variant | Keep as a secondary result once the environment confound is removed |
| 7 | The safety filter improves safety | Contribution 3, §4.4.3 | safety | −Filter: success 0.312 vs 0.315, C-Free 0.486 vs 0.488, collapse 0.468 vs 0.430 | Filter-activation rate, action-modification magnitude, minimum clearance, near-miss counts, deadlock cost — none reported. The only clean gain is collapse, which is dominated by the deadlock term | **P** | Medium — reviewer asks "why is it in the paper?" | No | Yes — safety-specific instrumentation | Keep, but reframe as *collapse-reducing*, not *safety*-improving; **[CLAIM MUST BE WEAKENED]** |
| 8 | Scales from 2 to 24 robots | §5.1, appendix tables | scalability | Per-N tables | Runtime/memory/bandwidth vs N; and performance *collapses* with N (RVT success 0.750 at N=2 → 0.180 at N=24) | **C** | High — the data show failure to scale | No | Yes — complexity measurements | Rewrite as "evaluated across 2–24 robots"; state the degradation explicitly |
| 9 | Generalizes across team sizes | Implicit throughout | generalization | Trained on all 12 team sizes (`dataset.py:283`), tested on the same 12 | No unseen-N split exists | **N** | High | No | Yes — leave-N-out protocol | Add train {2,6,10,14,18,22} / test {4,8,12,16,20,24} |
| 10 | Outperforms **ORCA** | Table 1 | performance | 0.315 vs 0.005 | The evaluated "ORCA" is goal-attraction + repulsion (`orca_like`) per the paper's own text | **U** | Fatal | Yes (rename) | Yes (re-run with RVO2) | **[CLAIM MUST BE REMOVED]** until re-run with `baselines.py:77` |
| 11 | Outperforms **CBF-QP** | Table 1 | performance | 0.315 vs 0.259 | Evaluated variant is expert + repulsion, not a QP | **U** | Fatal | Yes (rename) | Yes (re-run with `safety.py:264`) | As above |
| 12 | Outperforms **centralized MPC** | Table 1 | performance | 0.315 vs 0.053 | Evaluated variant is expert + centroid bias. Even the *new* `centralized_mpc` optimizes only over 5 discrete topology actions with horizon 1–2, beam 2–4, using the heuristic expert for control (`baselines.py:352-404`) — it is not MPC over control inputs | **U** | Fatal | Yes (rename) | Yes | Rename to *predictive topology search (centralized)*; **[CLAIM MUST BE REMOVED]** for "MPC" |
| 13 | Outperforms the **GNN** baseline | Table 1 | statistical | 0.315 vs 0.310 | One seed; no CI; unequal epochs (300 vs 120) and unequal checkpoint-selection budget | **U** | Fatal | No | Yes — 5–10 seeds, matched budget | Report as *comparable*; **[CLAIM MUST BE WEAKENED]** |
| 14 | Avoids excessive topology switching | Abstract, §5.1 | performance | T-Sw 0.131 vs 0.572 / 0.504 | Switch count is measured only on discrete `topology_mode` transitions; continuous scale motion is deliberately excluded (`environment.py:326-331`). Comparators are measured on a different mode alphabet (5 modes vs 3) | **P** | Medium | Partly | Yes — report scale-motion rate alongside | Report both `topology_switches` and `formation_scale_motion_rate`; define churn once |
| 15 | Suitable for practical decentralized deployment | Contribution 3, conclusion | practical deployment | None | No latency, bandwidth, packet-loss, or asynchrony experiment | **U** | High | Yes (delete) | Yes | **[CLAIM MUST BE REMOVED]** |
| 16 | ROS 2 deployment relevance | Fig. 3 caption ("ROS 2 interface") | practical deployment | A figure caption | The paper contains **no ROS 2 result whatsoever**. The node exists (`ros2_ws/.../agent_node.py`) but is never evaluated in the manuscript | **U** | High — figure promises what the paper does not deliver | Yes (remove from figure) | Yes, if the claim is kept | Either run the Gazebo study and report it, or delete "ROS 2" from Fig. 3 |
| 17 | The recoverability score reflects future formation recovery | §4.2, Eq. (recoverability) | methodological | Regression loss against the rollout target | No calibration, no AUROC/AUPRC, no reliability curve, no comparison against realized outcomes. The only reported related quantity is a per-step false-positive/negative rate against *terminal-step* collapse (`evaluate.py:50-54`) | **U** | Fatal for the title word | No | Yes — dedicated calibration study | **[TERMINOLOGY MUST BE CHANGED]** unless Part 10 is executed |
| 18 | *(implicit)* CollisionFree = zero collisions over the episode | §5.1 | methodological | Stated definition | Code returns terminal-step metrics. **[VERIFIED BY EXECUTION]** | **C** | Fatal | No | Yes — re-run everything | Fix accumulator, re-run, restate |
| 19 | *(implicit)* Episodes use matched **random starts** | §5.1 | methodological | Seed formula | Spawn is deterministic. **[VERIFIED BY EXECUTION]**: identical for seeds 1 and 99 999 | **C** | Medium | Partly | Yes — randomize starts | Randomize spawn, or state that starts are fixed |
| 20 | No hand-tuned thresholds are exposed | Appendix note | reproducibility | Assertion | The lexicographic selector encodes ~8 tie-break priorities; the MPC stage cost uses seven hand-chosen weights (`baselines.py:340-349`) | **C** | Low–medium | Yes | No | Delete the claim; report the priorities as design choices |

---

# PART 4 — RECOMMENDED CENTRAL HYPOTHESIS

## 4.1 Four candidate research questions

### Option A — Counterfactual supervision
> *Can short-horizon counterfactual rollout supervision improve the selection of formation responses in cluttered multi-robot navigation, relative to direct classification of the best mode?*

- **Hypothesis.** Distilling a per-mode rollout utility vector and training a *ranking* head over modes yields better end-task performance than training a classifier on the arg-max mode label, at equal capacity and equal selection budget.
- **Novelty.** Modest but real and *directly testable*: the comparison "soft rollout-ranking supervision vs. hard best-mode classification" is not standard in the formation-control literature.
- **Required components.** Rollout label generator; score head; ranking loss; mode-conditioned action bank.
- **Remove.** Uncertainty head, auxiliary head, lexicographic tie-breaks beyond keep-preference, latent geometry family beyond {keep, line, split}.
- **Minimum evidence.** 5 seeds × {rank-supervision, classification, no-mode-supervision}; paired bootstrap on matched episodes; ranking-accuracy and Brier score against realized rollouts.
- **Publication risk.** *Medium.* A reviewer can ask "why not learn the value function with RL?" — answerable, because the point is supervision efficiency, not asymptotic optimality.
- **Venues.** RA-L, IROS, *Robotics and Autonomous Systems*.

### Option B — Recovery prediction
> *Can a graph controller predict whether a candidate formation topology permits collision-free progress and return to a formation tube within a horizon H?*

- **Hypothesis.** A learned score over candidate topologies is a calibrated predictor of the empirical short-horizon recovery event, and its ranking of candidates matches realized outcomes better than distance-to-goal, formation error, minimum clearance, or a value head.
- **Novelty.** Highest of the four — this is the *only* option that makes "recoverability" a measurable object rather than a label.
- **Required components.** Binary recovery-event definition; stochastic multi-rollout labelling; score head; calibration machinery.
- **Remove.** Action bank (optional), uncertainty head (unless validated), safety filter (moved to an appendix), split/line geometry engineering.
- **Minimum evidence.** Reliability diagram, ECE, Brier, AUROC/AUPRC, false-safe rate, top-1 ranking accuracy, all stratified by N, obstacle density, and H — plus a downstream demonstration that better calibration yields better control.
- **Publication risk.** *Low-medium*, because the core claim is falsifiable and self-contained even if the control gain is small.
- **Venues.** RA-L, ICRA, *Autonomous Robots*.

### Option C — Topology-conditioned control
> *Do topology-conditioned action policies outperform topology-agnostic graph policies for formation navigation through bottlenecks?*

- **Hypothesis.** A shared backbone with a mode-conditioned action residual beats a single shared action head *specifically in bottleneck-dominated states*, with no difference in open space.
- **Novelty.** Low. Conditioning a policy on a discrete mode is standard.
- **Required components.** Action bank; a mode oracle or selector.
- **Remove.** Everything else.
- **Minimum evidence.** Stratified analysis (bottleneck score above/below threshold), 5 seeds, parameter-matched control.
- **Risk.** *High* — likely judged incremental on its own.
- **Venues.** IROS, ICRA workshop, *JIRS*.

### Option D — Adaptive formation
> *Can explicit structural modes plus smooth geometry adaptation improve formation navigation without excessive switching?*

- **Hypothesis.** Continuous scale adaptation plus a small discrete mode set achieves the passage-success of aggressive switching with substantially lower churn.
- **Novelty.** Low-medium; adjacent to Deng et al. 2025 and Xie et al. 2025.
- **Minimum evidence.** Churn–success Pareto front against a switching-heuristic family; multi-seed.
- **Risk.** *High* — the closest published competitors are strong and the current ablation already shows this is the weaker effect.
- **Venues.** *RAS*, *JIRS*, IROS.

## 4.2 Recommended positioning

**Adopt Option B as the primary question, with Option A as the mechanism and Option C as a supporting sub-result.**

Rationale, stated bluntly:

- Option B is the **only** framing under which the word your title is built on ("recoverability") becomes something you can *measure and be wrong about*. Prediction quality is falsifiable independently of whether the controller wins, so the paper survives even if the control margin stays small — which, given `−Topology` at 0.312 vs 0.315, it probably will.
- Option A is the training mechanism that makes B possible and gives you a clean second experiment.
- Option C becomes a stratified sub-analysis, not a contribution.
- Options D and the "decentralized" framing are dropped from the headline entirely.

The resulting paper satisfies the required structure: **one question** (can we predict short-horizon formation recovery per candidate mode, and does predicting it well help?), **one gap** (existing graph controllers and CBF filters score instantaneous safety, not horizon-H return-to-formation), **three contributions**, **hypothesis-driven experiments**, and terminology bounded by evidence.

---

# PART 5 — RECOMMENDED TITLE AND CONTRIBUTIONS

## 5.1 Ten title candidates

**Conservative (safe with current + minimally-fixed evidence)**

| # | Title | Central claim implied | Experiments required | Overclaim risk | Venue |
|---|---|---|---|---|---|
| C1 | *Counterfactual Rollout Supervision for Mode-Conditioned Multi-Robot Formation Navigation* | Rollout supervision is the contribution | Multi-seed + ablation A | Low | RA-L / IROS |
| C2 | *Learning to Rank Formation Reconfiguration Modes from Short-Horizon Rollouts* | Ranking is the object | Ranking accuracy + control | Low | RA-L |
| C3 | *Topology-Conditioned Graph Control for Multi-Robot Formation Navigation in Clutter* | Conditioning helps | Stratified bottleneck analysis | Low | IROS |
| C4 | *Mode-Conditioned Graph Policies for Formation Navigation Through Bottlenecks* | Narrow, honest | Bottleneck stratification | Very low | IROS |

**Recovery-prediction titles (allowed only once Part 10 is executed)**

| # | Title | Requirement |
|---|---|---|
| R1 | *Predicting Short-Horizon Formation Recovery for Mode Selection in Multi-Robot Navigation* | Calibration study (reliability, ECE, Brier, AUROC) |
| R2 | *Calibrated Recovery Prediction for Formation Reconfiguration in Cluttered Environments* | As R1 + comparison against value-head and geometric heuristics |
| R3 | *Horizon-H Recovery Scores for Formation Mode Selection in Multi-Robot Teams* | As R1 |

**Decentralized titles (allowed only once Part 11 is executed)**

| # | Title | Requirement |
|---|---|---|
| D1 | *Distributed Mode Selection for Multi-Robot Formation Navigation Under Communication Loss* | Per-robot inference is the evaluated path + agreement-rate study + packet-loss sweep |
| D2 | *Local-Observation Formation Reconfiguration with Consensus-Based Mode Agreement* | As D1 + an actual consensus mechanism |
| D3 | *Communication-Robust Formation Reconfiguration for Decentralized Multi-Robot Teams* | As D1 + latency/staleness sweep |

## 5.2 Recommended title

> ### **Predicting Short-Horizon Formation Recovery for Mode Selection in Multi-Robot Navigation**

with running head *Recovery Prediction for Formation Mode Selection*. If the calibration study is not completed, fall back to **C1**.

Every word is licensed: *predicting* (a supervised prediction problem), *short-horizon* (finite H, explicitly stated), *formation recovery* (an empirically defined event), *mode selection* (three templates, not "topology control"), *multi-robot navigation* (the task). No *decentralized*, no *resilient*, no *safe*, no *recoverability*.

## 5.3 Contributions — conservative list (current evidence + Stage-1/2 fixes only)

**Contribution 1**
- *Statement:* We formulate formation-mode selection as short-horizon **recovery ranking**: for each candidate mode we define a binary recovery event (collision-free, minimum progress, re-entry into a mode-conditioned formation tube within H) and learn a graph-level score that ranks candidate modes by predicted recovery.
- *Technical distinction:* Prior graph controllers regress actions or instantaneous safety values; barrier methods certify instantaneous constraint satisfaction. Neither produces a per-candidate, horizon-H return-to-formation prediction.
- *Closest prior approach:* Certifiable reachability learning (Li et al. 2025); RAIL (Jung et al. 2025) — both single-agent, neither formation-conditioned.
- *Required supporting experiment:* E1 (calibration) + E2 (ranking accuracy vs. baselines).
- *Result section:* §6.3.

**Contribution 2**
- *Statement:* We show that supervising this score with **soft, rank-preserving targets distilled from counterfactual rollouts** outperforms supervising a hard best-mode classifier at equal capacity and equal selection budget.
- *Technical distinction:* The comparison isolates supervision form (soft ranking vs. hard label) rather than architecture.
- *Closest prior approach:* Imitation-learned decentralized controllers (Gama et al. 2022) use action-only supervision.
- *Required supporting experiment:* E3 (supervision-form ablation, 5 seeds, paired).
- *Result section:* §6.4.

**Contribution 3**
- *Statement:* We provide a **matched-simulator benchmark** for formation navigation in clutter with faithful reference controllers (RVO2-ORCA, a per-robot CBF-QP, and a centralized predictive topology search), episode-wide safety accounting, and released code, seeds, and logs.
- *Technical distinction:* Existing formation-navigation comparisons rarely run reference implementations in the same dynamics with matched tuning budgets.
- *Required supporting experiment:* E0 (benchmark re-run) + Table 2 (fidelity table).
- *Result section:* §6.1–6.2.

## 5.4 Contributions — stronger list (if all mandatory experiments succeed)

Replace Contribution 3 with:

**Contribution 3′.** We characterize **distributed mode agreement**: each robot runs the score model on its own local graph, and we quantify agreement rate, disagreement duration, and the safety/progress cost of disagreement under packet loss ∈ {0,10,30,50,70,90} % and latency ∈ {0,50,100,200,500} ms, with a majority-vote coordination variant as the comparison point.

## 5.5 Claims that must stop being presented as contributions

- "We introduce a **decentralized** framework …" — unsupported by the evaluated code path.
- "RVT-Swarm achieves the **strongest overall performance** among the compared methods" — not a contribution; a result, and one that does not survive statistics.
- "A **recoverability-first inference stack** combining topology evidence, scores, uncertainty and auxiliary context …" — this is an engineering pipeline description, not a scientific claim, and the uncertainty and auxiliary heads have no isolated evidence.
- Anything referencing "viability", "certification", or "reachability" for this system.

---

# PART 6 — COMPONENTS TO KEEP, SIMPLIFY, DEMOTE, OR REMOVE

## 6.1 Component-by-component verdict

| Component | Novel? | Borrowed from | Isolated experiment exists? | Ablation supports it? | Verdict |
|---|---|---|---|---|---|
| Graph-based local observation | No | Gama 2022, GCBF+ | No | n/a | **Keep** — implementation detail |
| Attention message passing (3 layers, K=6) | No | Standard GAT-style | No | No | **Keep, demote** to implementation detail |
| Mode-conditioned action bank (`models.py:233-261`) | Weakly | Conditional policies | No | Only via `−Topology` (Δ = −0.003) | **Keep, simplify** — base + residual is fine; needs its own experiment (H3) |
| Mode classification head (`topology_logits`) | No | Standard | No | Serves as the `−Recoverability` selector | **Demote to a baseline**, not a component. It duplicates the score head's ranking function |
| Recovery score head | Yes (as framed) | — | No calibration | Compound ablation | **Primary contribution** — after Part 10 |
| Uncertainty head (`softplus`, `models.py:213-217`) | No | Heteroscedastic regression | **None** | Not isolated | **Remove.** Its target is `ReLU(r̂ − y)/std(r̂)` — the *training residual* of the score head. It is an in-sample optimism estimate with no held-out validation, and it enters both the score adjustment and the selector. It cannot be defended |
| Auxiliary head (4 scalars) | No | Auxiliary-task RL | **None** | Not isolated | **Remove.** Targets are `formation_scale, bottleneck, progress, split_active` (`dataset.py:302-307`) — all of which are *already input node features* (`dataset.py:215-218`). The head predicts its own inputs |
| Counterfactual rollout supervision | Yes (as framed) | Rollout/DAgger family | Mislabelled ablation | Ablation does not test it | **Primary contribution** — after the ablation is fixed |
| Pairwise ranking loss (`train.py:35-42`) | No | RankNet family | No | Bundled | **Keep, isolate** — needs its own row in the ablation |
| Lower-bound (conservatism) loss | No | Pessimistic value learning | No | Bundled | **Simplify** — fold into the calibration story or remove |
| Hard-negative mining (`dataset.py:327-344`) | No | Standard | **None** | No | **Remove or isolate.** As implemented it adds Gaussian noise to *action targets* while keeping node features, score targets, and topology targets identical — i.e. it injects label noise, it does not mine hard states |
| Lexicographic selector (`safety.py:517-535`) | No | Hand rule | No | Effectively what `−Recoverability` tests | **Keep, simplify** to `argmax_τ r̃_τ` with an explicit keep-preference tie-break; the remaining 6 tie-break levels are undocumented degrees of freedom |
| Keep/line/split templates | No | Standard formation shapes | No | `−Topology` | **Keep** — problem definition, not contribution |
| Adaptive formation scale | No | Standard | Confounded (changes the environment) | Partly | **Keep, demote** to secondary |
| Latent geometry update / split assignment | No | Hand rule | No | No | **Keep, demote** — move to appendix |
| Risk-triggered safety projection | No | CBF-QP (Ames 2017; Wang 2017) | No | Δsuccess = 0.003 | **Demote to appendix.** Reframe as an optional collapse-reducing layer |
| ROS 2 execution architecture | No | — | **None in the paper** | n/a | **Remove from the paper** or promote to a real experiment |

## 6.2 The five diagnostic questions

1. **Strongest currently supported contribution.** The *observation* that soft, rank-preserving mode targets distilled from rollouts train a better runtime selector than a hard classifier (Full 0.315 vs `−Recoverability` 0.139 is a large effect even if compound). This is the only large, reproducible-looking signal in the paper.
2. **Weakest claimed contribution.** "Decentralized framework" — contradicted by the code.
3. **The component that impressed the authors but not the editor.** The multi-head Recoverability Field Network with five branches. Five heads on one backbone reads as engineering surface area; four of the five have no isolated evidence. Architectural breadth is precisely what an editor discounts.
4. **The component that should become the central paper idea.** The **horizon-H recovery event and its predictor** — because it is the only element that can be validated on its own terms.
5. **The components that distract.** Uncertainty head; auxiliary head; hard-negative mining; the 10-level lexicographic key; the compress/recover latent modes that the learner never scores; the ROS 2 figure; the capability checkmark table.

## 6.3 Three model versions

**(V1) Minimum viable scientific model**
- *Architecture:* shared 3-layer attention GNN → mean pool → single score head over 3 modes. Actions from the same heuristic controller used for rollouts (so the paper studies *selection*, cleanly).
- *Loss:* `L = MSE(r̂, y_score) + λ·PairRank(r̂, y_score)`, λ = 1.
- *Inference:* `τ* = argmax_τ r̂_τ`, tie-break toward `keep`.
- *Expected contribution:* recovery prediction is learnable and useful for selection.
- *Required ablations:* {score+rank, score only, rank only, classifier, random, always-keep, oracle-rollout}.

**(V2) Recommended final model**
- V1 **+** mode-conditioned action residual `u_i^(τ) = tanh(φ_base(h_i) + 1[τ≠keep]·φ_Δ([h_i‖onehot(τ)]))`, trained with the keep anchor + rollout-weighted bank loss.
- *Loss:* `L = ½(L_act_keep + L_act_bank) + ½(MSE_score + PairRank)`.
- *Inference:* `τ* = argmax r̂`, then `u_i = U_i[τ*]`; optional QP projection reported separately.
- *Expected contribution:* Contributions 1–3 of Part 5.
- *Required ablations:* V1 set **+** {shared action head, parameter-matched topology-agnostic GNN, no bank}.

**(V3) Full model** — V2 + uncertainty + auxiliary + hard negatives + lexicographic selector. **Publish only if** each added component has its own row in the ablation table with 5-seed paired intervals *and* a positive effect. On current evidence, do not.

---

# PART 7 — BASELINE REPLACEMENT PLAN

## 7.1 Fidelity report on what the paper evaluated

| Name in manuscript | Original algorithm | Reference | What the paper evaluated | Faithful? | Critical differences | Keep the name? | Correction |
|---|---|---|---|---|---|---|---|
| ORCA | Optimal Reciprocal Collision Avoidance | van den Berg et al. 2011 | Goal attraction + velocity damping + pairwise/obstacle repulsion (`orca_like`, `baselines.py:159-184`) | **No** | No velocity obstacles, no reciprocity, no linear-programming velocity selection | **No** | Rename *reactive repulsion*; re-run with the vendored RVO2 path (`baselines.py:77-156`) |
| CBF-QP | Safety barrier certificates / CBF-QP | Wang 2017; Ames 2017 | Expert action + stronger repulsion, then clip (`cbf_qp_like`, `baselines.py:193-207`) | **No** | No barrier constraints, no QP | **No** | Rename *repulsion filter*; re-run with `cbf_qp` (`baselines.py:210-225`), which *is* a genuine per-robot CBF-QP |
| Centralized MPC | Belief-propagation MPC formation | Jiang 2024 | Expert + heuristic mode + centroid-to-goal bias | **No** | No finite-horizon optimization at all | **No** | Rename; and note the *new* implementation is still not MPC (below) |
| Adaptive Formation | Coordinated navigation with formation adaptation | Deng 2025 | Internal heuristic mode rule + shared expert (`baselines.py:187-190`) | **No** | Not the published algorithm | **No** | Rename *heuristic mode heuristic (internal)*; drop the citation from the table row |
| InstantCert | Certifiable reachability learning | Li 2025 | GNN + scalar head regressing the keep-mode margin | **No** | No certificate, no Lipschitz value function, no reachability | **No** | Rename *scalar-recovery head (internal)* |
| GNN | Decentralized controller synthesis via GNN + IL | Gama 2022 | Same backbone, action head only | **Partially** — a legitimate *internal* control, not a reproduction | Different task, dynamics, and supervision | **No** — call it *topology-agnostic GNN (internal)* | Rename; keep as the primary learned control |

## 7.2 Fidelity report on what the repository now contains

| Implementation | Verdict | Notes |
|---|---|---|
| `orca` (`baselines.py:77-156`) | **Fair, with one caveat** | Genuine RVO2/ORCA: reciprocal agents, static obstacles as polygons, dynamic obstacles as agents, correct `dt`/horizon/radius/max-speed wiring. **Caveat:** the preferred velocity comes from `expert_action` under a heuristic mode (line 85-90), i.e. ORCA is given *formation-aware* preferences. That is a legitimate and *favourable* configuration for ORCA and must be described exactly, not glossed |
| `cbf_qp` (`baselines.py:210-225` + `safety.py:264-380`) | **Fair** | An exact 2-D QP `min‖u−u*‖² s.t. aᵀu ≥ b, ‖u‖ ≤ a_max`, solved by active-set enumeration over interior / single-boundary / boundary-pair / boundary-circle candidates. Barriers are `h = ‖p_i−p_j‖² − d_safe²` with a discrete-time decrease condition. Honest description: **decoupled (non-reciprocal) discrete-time CBF-QP with a nominal formation controller** |
| `centralized_mpc` (`baselines.py:352-404`) | **Partially fair — must be renamed** | Beam search (horizon 1–2, beam 2–4) over **five discrete mode actions**, with the heuristic expert generating the continuous controls, under exact simulator dynamics. It optimizes a *mode sequence*, not a control trajectory, and its stage cost has seven hand-set weights (`baselines.py:340-349`). Call it **centralized predictive mode search (exact-model)**. Do **not** call it MPC |

## 7.3 Fair baseline hierarchy for the revision

**Group 1 — internal control baselines (honest names, no external citations in the row)**
1. `fixed-formation expert` — the shared heuristic controller with mode fixed to `keep`. *This is the true performance floor and the true ceiling for every behaviour-cloned method, and it is currently missing from the paper.* Adding it is non-negotiable.
2. `reactive repulsion` (formerly "ORCA") — retained as an ablative reference only.
3. `heuristic mode selection` (formerly "Adaptive Formation") — `_heuristic_topology` + expert.
4. `oracle mode selection` — the rollout arg-max mode executed by the expert. **This is the upper bound your learner is chasing and it belongs in every table.**

**Group 2 — learned internal baselines**
5. `GNN-BC` — topology-agnostic, parameter-matched, identical epochs and identical checkpoint-selection budget.
6. `classifier` — same backbone, hard best-mode cross-entropy, `argmax(logits)` selection.
7. `scalar-recovery` (formerly InstantCert).
8. `value-head` — regress the *scalar* rollout return of the executed mode (the natural "is this just a value function?" control).
9. `behaviour cloning of the bank without ranking` — action bank, no score head.

**Group 3 — external baselines**
10. `ORCA (RVO2)` — fair; must state the preferred-velocity source.
11. `CBF-QP (decoupled, discrete-time)` — fair.
12. `centralized predictive mode search` — partially fair; report the horizon/beam budget and note it is not a control-space MPC.
13. *Candidate additions if resources permit:* **GCBF+** (official code, distributed graph CBF, double-integrator dynamics match yours well) and **DGPPO**. Both are genuinely comparable on the *safety/navigation* axis; neither does formation, so report them on navigation and safety only and say so.

## 7.4 Mandatory Baseline Fidelity Table (to appear as Table 2)

| Baseline | Source | Official impl. | Dynamics matched | Observations matched | Objective matched | Hyperparameter budget | Adaptations | Known limitations | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| Fixed-formation expert | this work | n/a | ✓ | global | formation+goal | none | — | omniscient within cutoff radii | fair (internal) |
| Heuristic mode selection | this work | n/a | ✓ | global | formation+goal | none | — | hand rule | fair (internal) |
| Oracle mode selection | this work | n/a | ✓ | global + simulator clone | rollout-optimal | none | requires simulator | upper bound only | fair (internal) |
| GNN-BC | internal, inspired by [Gama 2022] | no | ✓ | graph | action MSE | **matched to ours** | parameter-matched | not a reproduction of [Gama 2022] | fair (internal) |
| Classifier | this work | n/a | ✓ | graph | CE on best mode | matched | — | — | fair (internal) |
| Value-head | this work | n/a | ✓ | graph | scalar return MSE | matched | — | — | fair (internal) |
| ORCA (RVO2) | [van den Berg 2011] | ✓ vendored | ✓ | full state | collision-free velocity | default + `[REQUIRES AUTHOR VALUE]` sweep over `timeHorizon` | pref. velocity from formation controller; obstacles as 8-gons | no formation objective → F-OK unfavourable by design | **fair on safety/progress; unsuitable for formation claims** |
| CBF-QP (decoupled) | [Ames 2017],[Wang 2017] | in-repo, exact 2-D QP | ✓ | full state | min-deviation safe control | α sweep `[REQUIRES AUTHOR VALUE]` | non-reciprocal; discrete-time condition | conservative; no formation objective | **fair** |
| Centralized predictive mode search | this work (MPC-inspired) | n/a | ✓ (exact model) | full state | 7-term stage cost | horizon 1–2, beam 2–4 | mode-space only | not a control-space MPC | **partially fair — rename** |
| GCBF+ | [Zhang 2025] | ✓ public | needs double-integrator port | graph | safe navigation | authors' defaults + light sweep | goal set, sensing radius | no formation | **fair on safety/navigation only** |

**Rule to state in the caption:** *no method may be claimed superior to any baseline marked "unsuitable" on the axis for which it is unsuitable.*

---

# PART 8 — MANDATORY EXPERIMENT PLAN

## 8.1 Hypotheses, variables, and falsification

| ID | Hypothesis | Independent variable | Control variant | Dependent metrics | Success condition | Analysis | If it fails |
|---|---|---|---|---|---|---|---|
| **H1** | Rollout-ranking supervision beats hard best-mode classification | supervision form | classifier, same backbone/capacity/budget | conjunctive success, episode-wide collision-free, F-OK, collapse | paired mean Δ success > 0 with 95 % CI excluding 0 over ≥5 seeds | paired bootstrap over matched episodes; Cliff's δ | Demote to "comparable"; pivot the paper onto H2 |
| **H2** | The learned score predicts realized short-horizon recovery | — | distance-to-goal, F-error, min-clearance, value head, classifier logit | AUROC, AUPRC, Brier, ECE, false-safe rate, top-1 ranking accuracy | AUROC ≥ 0.75 and ECE ≤ 0.10 on held-out states, beating every heuristic predictor | DeLong / bootstrap CIs on AUROC; reliability diagram | **The word "recovery" leaves the title**; report as a shaped utility |
| **H3** | Mode-conditioned actions beat a single shared head **in bottlenecks** | action head | shared head | success and clearance, stratified by bottleneck score | Δ > 0 in the high-bottleneck stratum, Δ ≈ 0 in open space | stratified paired test, Holm-corrected | Remove the action bank; keep selection only |
| **H4** | Explicit mode adaptation reduces collapse/deadlock in constrained maps | mode set | `keep` only | collapse, deadlock, passage time | Δcollapse < 0, CI excludes 0, in `narrow_passage` | paired per-scenario | Restrict claims to narrow scenarios or drop |
| **H5** | Smooth scale adaptation reduces churn without costing success | scale adaptation | frozen scale (**same environment**) | switch count, scale-motion rate, success | churn ↓ with success CI overlapping 0 | paired | Report as a churn-only result |
| **H6** | The QP filter reduces collision without excessive deadlock | filter | none, reactive repulsion, full CBF-QP | episode-wide collisions, near-misses, min clearance, deadlock, time frozen, activation rate, ‖Δu‖ | collisions ↓ with deadlock CI not increasing | paired | Move the filter to an appendix |
| **H7** | The controller generalizes to unseen layouts and unseen team sizes | train/test split | seen split | all task metrics | degradation ≤ that of GNN-BC | paired across splits | Report as an in-distribution study only; remove all generalization language |
| **H8** | Per-robot execution stays consistent and effective under communication degradation | packet loss, latency, staleness | perfect comms, centralized oracle | mode-agreement rate, disagreement duration, collision during disagreement, success | success degradation graceful to ≥30 % loss; agreement ≥ 0.9 at 0 % loss | per-condition paired | **"Distributed" leaves the title**; report the centralized configuration honestly |

## 8.2 Benchmark matrix

**A. Team size.** N ∈ {2,4,6,8,12,16,20,24}. *Train* on {2,6,10,14,18,22}; *test* on {4,8,12,16,20,24}. This immediately creates the unseen-N axis you currently lack, at zero extra training cost.

**B. Environment type.** open · narrow corridor · single bottleneck · multiple bottlenecks · dense static clutter · dynamic crossing · asymmetric passage · dead-end recovery · split-and-merge. *Currently you have 4 scenario generators and one fixed goal at (4.56, 0); at minimum add asymmetric passage, dead-end, and split-and-merge, and randomize goal placement.*

**C. Generalization splits.**

| Split | Train | Test | Priority |
|---|---|---|---|
| seen map / seen N | ✓ | ✓ | mandatory |
| unseen map / seen N | {open, cluttered, narrow} | {asymmetric, dead-end, split-merge} | **mandatory** |
| seen map / unseen N | N odd-index | N even-index | **mandatory** |
| unseen map / unseen N | both held out | both held out | strongly recommended |
| unseen obstacle density | 8 obstacles | 12, 16 | strongly recommended |
| unseen corridor width | 1.5 m | 1.1 m, 2.0 m | strongly recommended |
| unseen dynamics | a_max 0.6 | 0.4, 0.8 | optional appendix |

**D. Sensor conditions.** none · position noise σ ∈ {0.02, 0.05} m · velocity noise · LiDAR noise · LiDAR dropout 10 % · odometry drift. *Priority: position noise (mandatory), LiDAR dropout (recommended), rest optional.*

**E. Communication.** packet loss {0,10,30,50,70,90} % · latency {0,50,100,200,500} ms · stale peer state · reduced comms range {4,3,2} m · asynchronous updates · robot dropout. *Mandatory only if a "distributed" claim is made; otherwise strongly recommended as a limitations-supporting appendix.*

**F. Dynamics.** nominal · reduced acceleration · one-step control delay · actuation noise · heterogeneous v_max. *Optional appendix / future work.*

**Per-cell specification.** Every benchmark cell reports: training distribution, test distribution, 100 episodes minimum (4 scenarios × 25) with matched seeds across methods, **≥5 training seeds**, the full metric suite of Part 15, and the research question it answers.

## 8.3 Prioritization

**Mandatory for any publishable revision**
- **E0.** Fix the metric accumulator (episode-wide), fix the collision-threshold geometry, randomize starts and goals; re-run the entire benchmark. *Nothing else matters until this is done.*
- **E1.** 5 (preferably 10) independent training seeds for every learned method, with **equal epochs and equal checkpoint-selection budget**.
- **E2.** Faithful baselines: RVO2-ORCA, CBF-QP, predictive mode search, plus fixed-formation expert and oracle-mode upper bound.
- **E3.** Recovery-score calibration study (Part 10).
- **E4.** Unseen-layout and unseen-N generalization splits.
- **E5.** Isolated (non-compound) ablations, 5 seeds each.

**Strongly recommended**
- E6. Communication/decentralization study (Part 11) — becomes mandatory if "distributed" appears anywhere.
- E7. Safety-layer comparison with instrumentation (H6).
- E8. Runtime/memory/bandwidth vs N.

**Optional appendix**
- E9. Sensor noise; E10. dynamics perturbations; E11. GCBF+ external comparison.

**Future work**
- E12. Physical robots; E13. heterogeneous teams; E14. formal analysis.

## 8.4 Redesigned ablation study (isolated, no compounds)

| # | Variant | Modules removed | Losses removed | Unchanged | Params | Seeds | Hypothesis tested |
|---|---|---|---|---|---|---|---|
| 1 | **Full (V2)** | — | — | — | P | 5 | reference |
| 2 | − rollout ranking loss | — | PairRank | score MSE kept | P | 5 | H1 (loss form) |
| 3 | − score head; classifier only | score head | score/rank/LB | actions kept | ≈P | 5 | H1 (supervision form) |
| 4 | − score-based selection (argmax logits) | — | — | model identical to 1 | P | 5 | selector effect **(this is what the paper currently calls "−Counterfactual")** |
| 5 | − rollout supervision entirely (BC on `keep` only) | score, bank | all but action | — | <P | 5 | true no-counterfactual control |
| 6 | − action bank (shared head) | φ_Δ | bank loss | selection kept | <P | 5 | H3 |
| 7 | − mode selection (always `keep`) | selector | — | — | P | 5 | H4 |
| 8 | fixed scale (**environment held fixed**) | — | — | — | P | 5 | H5 |
| 9 | − split mode | split template | — | — | P | 5 | template value |
| 10 | − line mode | line template | — | — | P | 5 | template value |
| 11 | − uncertainty adjustment | σ head | L_unc | — | <P | 5 | is σ doing anything? |
| 12 | − auxiliary head | aux head | L_aux | — | <P | 5 | is aux doing anything? |
| 13 | − hard negatives | — | — | dataset changes | P | 5 | mining value |
| 14 | − QP filter | filter | — | — | P | 5 | H6 |
| 15 | filter → true CBF-QP (no blending) | blending | — | — | P | 5 | H6 |
| 16 | parameter-matched topology-agnostic GNN | all heads | all but action | width increased to match P | **P** | 5 | capacity control |
| 17 | oracle mode selection | learned selector | — | expert actions | n/a | n/a | selection headroom |

**Interpreting adverse outcomes — decide these rules *before* running:**

- *Removing mode selection has ≈ no effect* → the paper is not about topology control. Re-title around recovery prediction (Option B) and report mode selection as a conditional, bottleneck-only benefit. **This is the outcome your current data predict.**
- *Removing the safety filter has ≈ no effect* → move it to an appendix as an implementation detail; delete every safety claim.
- *Direct classification matches rollout ranking* → the contribution collapses to "mode-conditioned control"; pivot to Option C and shorten the paper to a letter.
- *Uncertainty does not improve calibration* → delete the head (expected).
- *Adaptive scale improves churn only* → report it as a churn/stability result with an explicit statement that success is unchanged.
- *The full model is worse than a simpler variant* → **publish the simpler variant as the method.** This is the correct scientific response and it will strengthen, not weaken, the paper.

---

# PART 9 — STATISTICAL PROTOCOL

## 9.1 Seed taxonomy — currently conflated, must be separated

`run_experiments.py:44-45` sets `cfg.train.seed`, which simultaneously determines (a) `set_seed` for network init and data-loader shuffling (`train.py:305`), (b) the dataset-generation seeds (`dataset.py:384-385`), and (c) **the evaluation episode seeds** (`evaluate.py:83-87`). Consequently the repository's "multi-seed" mode changes the *test set* along with the model — the runs are not comparable and cannot be paired.

**Required separation:**

| Seed | Controls | Protocol |
|---|---|---|
| `train_seed` ∈ {0..9} | network init, batch order | **≥5, preferably 10**, per learned method |
| `data_seed` (fixed) | expert-episode generation | fixed at 0 for all methods so every method trains on identical data |
| `eval_seed` (fixed) | scenario layouts, starts, goals, dynamic-obstacle phases | **fixed across all methods and all training seeds** — this is what makes pairing possible |
| `rollout_seed` | stochastic rollouts in labelling/calibration | separate stream |

## 9.2 Reporting requirements

For every learned method, every metric, every table cell: **mean ± SD across training seeds, 95 % CI, median, min, max, and the per-seed values in the supplement.** Non-learned baselines are deterministic given `eval_seed` and report a single value plus the episode-level distribution.

## 9.3 Tests

- **Primary (matched episodes, same method pair):** paired bootstrap CI on the mean difference (10 000 resamples over episodes, blocked by scenario × N), plus **Wilcoxon signed-rank** on episode-level paired outcomes. For binary metrics use McNemar's test on the discordant pairs.
- **Across training seeds:** paired permutation test on the seed-level means (exact enumeration when n ≤ 8; note that with 5 vs 5 the smallest attainable two-sided p is 1/126 ≈ 0.008, so *report the exact minimum attainable p in the caption*).
- **Effect size:** Cliff's δ for episode-level ordinal comparisons; standardized mean difference across seeds; paired absolute and relative improvement.
- **Multiple comparisons:** Holm–Bonferroni across the family {baselines × primary metric}, and separately across the ablation family. State the family explicitly.
- **Do not** use the current unpaired permutation test on 5 seed means (`run_experiments.py:208-222`) as the primary analysis; it discards the matched-episode structure and is badly underpowered.

## 9.4 Direct answers to the six required statistical questions

1. **Are 1 200 evaluation episodes sufficient with one trained model?** No. They estimate one *realization* of the training process with high precision; they say nothing about the training process itself. With a single seed, the sampling distribution of "success rate of a model trained this way" has an unestimated variance component that is typically the dominant one for a 0.005 effect. 1 200 episodes × 1 seed is 1 sample, not 1 200.

2. **Can 0.315 vs 0.310 be called an improvement?** **No.** Not as "outperforms", not as "improves", not as "achieves the strongest performance". At a per-episode success probability near 0.31 with 1 200 matched episodes, the paired standard error of a difference is roughly `sqrt(2·p(1−p)(1−ρ)/M)`; even under strong pairing (ρ ≈ 0.8) that is ≈ 0.008 — larger than the observed 0.005 — **before** adding across-seed variance. Permissible phrasing: *"performs comparably to the topology-agnostic GNN baseline (0.315 vs 0.310; paired 95 % CI [·, ·] includes zero)."*

3. **How many seeds to detect an effect of that magnitude?** If the true effect is 0.005 and across-seed SD of the success rate is σ, a paired design needs roughly `n ≈ 8·(σ/0.005)²` seeds for 80 % power at α = 0.05. For σ = 0.01 that is ≈ 32 seeds; for σ = 0.02, ≈ 128. **Conclusion: an effect this small is not worth chasing.** Either the fixed benchmark produces a substantially larger effect after the metric bug is repaired, or the paper must be positioned on prediction quality (H2) rather than control superiority. `[REQUIRES NEW EXPERIMENT]` to estimate σ.

4. **Statistical superiority or competitive performance?** **Competitive performance**, on every current comparison against the learned baselines. Superiority claims may be made only against the reactive-repulsion and (if it survives re-implementation) predictive-mode-search baselines, and only with CIs.

5. **Which results require confidence intervals?** All of them, without exception: main table, per-N table, every ablation row, every generalization cell, AUROC/ECE/Brier, and the runtime measurements.

6. **Which metrics are correlated and must not be counted as independent evidence?** `Success = GoalReached ∧ CollisionFree ∧ FormOK` is a deterministic function of three other reported columns — reporting all four as separate wins is quadruple-counting. `Collapse` contains `Deadlock` and `¬CollisionFree ∧ ¬FormOK` by construction (`environment.py:549-553`), so Collapse is largely redundant with Deadlock + CollisionFree + FormOK. `FormOK` and `form_rms` are threshold and continuous versions of one quantity. `stall_rate` and `deadlock` share `stall_counter`. **Designate one primary metric (conjunctive success), pre-register it, apply multiplicity correction to the rest, and state the dependency structure in the caption.**

---

# PART 10 — RECOVERABILITY VALIDATION PLAN

## 10.1 What the current quantity actually is

`rvt_swarm/recoverability.py:45-83`:

```
R(x, τ) = (1/H) Σ_{h} [ mean(collision_free, Δprogress, tube, recover_proxy, bottleneck_relief)
                       − mean(deadlock_pen, switch_pen, collapse) ]        (+ terminal bonus / penalty)
```

Answering the nine required questions:

1. **Computed from what?** A single deterministic rollout of the **heuristic expert** under a fixed mode τ, in a cloned copy of the simulator (`recoverability.py:28-42`) — i.e. it requires the full global state and a simulator, and it is available only at training time.
2. **Probability, value, ranking, score, or set property?** A **shaped, bounded average stage reward**: an equally-weighted mean of five positive and three negative normalized terms. It is a *value function of the expert policy under a hand-designed reward* — not a probability, not a set-membership property.
3. **Is "recoverability" defensible?** **No.** In control theory, recoverability/viability denotes membership in a set from which constraint satisfaction can be maintained. This quantity is neither a set indicator nor a bound on one, and the paper offers no proof, no conservatism guarantee, and no calibration.
4. **Distinguishable from a shaped rollout return?** **No** — it is exactly a shaped rollout return, normalized by horizon.
5. **Distinguishable from a value function?** **No** — it is `V^expert_R(x, τ)` for reward `R` = the bracketed expression. This is the single most damaging observation for the framing, and a reviewer will make it in one sentence.
6. **Does the model estimate actual future recovery?** Not as evaluated. It regresses `tanh(q/|q̄|)` (`recoverability.py:115`); the only recovery-adjacent evaluation is a per-step false-positive/negative rate against **terminal-step** collapse (`evaluate.py:50-54`), which is not a horizon-H recovery event.
7. **Is the score calibrated?** No calibration is reported or possible for a `tanh`-squashed shaped return — there is no probability to be calibrated against.
8. **False-positive "safe" predictions measured?** Only in the degenerate sense above; the per-step rate compares a sign test against a terminal-state indicator, and the reported false-negative definition (`(1−pred_safe) ∧ (1−fail_now)`) counts *correct* conservative predictions as errors whenever no collapse occurs — the metric is mis-specified.
9. **Rankings compared against realized outcomes?** No.

## 10.2 Three candidate definitions

**(A) Probability of recovery.**
`R_H(x,τ) = P( collision-free on [k, k+H] ∧ Δprogress ≥ p_min ∧ ∃ h ≤ H : form_rms(x_{k+h}; τ) < ε_form ∧ no irreversible collapse | x_k, τ )`
Estimated by M stochastic rollouts under a stochastic expert (action noise σ_a, sensor noise). **Calibratable, falsifiable, and directly matches the word.**

**(B) Binary horizon recovery label.**
`y_rec(x,τ) = 1` iff all four conditions hold in a *single* rollout; `0` otherwise. Cheapest change from the current pipeline: keep one rollout, replace the shaped sum with a conjunction. Trains a classifier with a proper scoring rule (BCE), giving Brier/ECE/AUROC for free.

**(C) Bounded rollout utility.**
The current quantity, renamed and honestly described: a normalized bounded score combining collision-free execution, progress, formation recovery, deadlock, collapse, and switching. **Must be labelled a rollout utility, never recoverability.**

## 10.3 Which matches the implementation, and what to do

**The current implementation is (C), unambiguously.** Therefore:

- **If you do nothing:** the term must become **"counterfactual rollout utility"** or **"mode preference score"**. `[TERMINOLOGY MUST BE CHANGED]`. Neither "recoverability" nor "recovery likelihood" nor "viability" is permitted.
- **Recommended:** migrate to **(A)** with **(B)** as the label generator. Cost estimate: `M` rollouts × `|T|`=3 modes × ~120 steps per sampled state instead of 1 × 3; with M = 8 that is an 8× increase in label-generation cost, parallelizable across the existing worker pool (`dataset.py:393-399`). This buys you the entire Part 5 title.

Under (A)/(B) the licensed term is **"empirical recovery probability"** or **"horizon-H recovery likelihood"**. **Formal reachability, viability-kernel, and certification language remains forbidden without proofs and verified assumptions.**

## 10.4 The calibration experiment (E3)

**Protocol.**
1. Sample S = `[REQUIRES AUTHOR VALUE]` (target ≥ 20 000) states from held-out episodes, stratified across scenario × N × bottleneck decile.
2. For each state and each τ ∈ {keep, line, split}, run M = 8 stochastic short-horizon rollouts (action noise, sensor noise, dynamic-obstacle phase jitter).
3. Record `y_rec ∈ {0,1}` per rollout; `p̂_emp = (1/M)Σ y_rec`.
4. Compare the model's score `r̂_τ` (mapped through a sigmoid if trained under (A)/(B)) against `p̂_emp`.

**Report.** Reliability diagram (10 equal-mass bins, with binomial CIs per bin); ECE and MCE; Brier score and its decomposition (reliability / resolution / uncertainty); AUROC with DeLong CI; AUPRC with the positive base rate stated; **false-safe rate** (predicted recoverable, realized non-recovery) at operating thresholds {0.5, 0.7, 0.9}; false-negative rate; error stratified by N, obstacle density, and H ∈ {7, 14, 28}; **top-1 mode-ranking accuracy** and Kendall's τ against the empirical ranking of {keep, line, split}.

**Comparators (all must be beaten to keep the word "recovery"):** distance-to-goal; formation error; minimum clearance; instantaneous collision risk (`safety.py:70`); a trained value head; the classifier logit; the raw un-normalized rollout return; the score without uncertainty adjustment.

**Minimum evidence to retain "recovery" in the title.**
`AUROC ≥ 0.75` (95 % CI lower bound > 0.70) **and** `ECE ≤ 0.10` **and** top-1 ranking accuracy strictly above the best geometric heuristic with a non-overlapping CI, on held-out layouts, at ≥3 team sizes. Anything less → fall back to title C1 and the term "rollout utility".

---

# PART 11 — DECENTRALIZATION VALIDATION PLAN

## 11.1 Information-flow audit

| Variable | Meaning | Level | Train | Infer | Locally observable? | Communicated? | Globally available? | Violation? | Clarification required |
|---|---|---|---|---|---|---|---|---|---|
| `p_i, v_i, head_i` | own kinematics | robot | ✓ | ✓ | ✓ | — | — | no — but **absolute world position** is used, not a body-frame quantity (`dataset.py:206`) | state the frame; absolute `p` breaks translation equivariance and inflates generalization |
| `g_i, ĝ_i` | goal vector | robot | ✓ | ✓ | ✓ (shared goal) | broadcast | ✓ | no | state the shared-goal assumption |
| `p_i − p̄` | offset from **team centroid** | graph→robot | ✓ | ✓ | **✗** | not modelled | ✓ | **YES** | requires all N positions |
| `e_i^τ` | formation error | robot | ✓ | ✓ | **✗** | — | ✓ | **YES** | derived from the centroid and the global mode |
| `p_i − p_obs,c` | offset from **obstacle centroid** | graph | ✓ | ✓ | **✗** | — | ✓ | **YES** | requires the full obstacle set |
| `κ_k` formation scale | latent geometry state | graph | ✓ | ✓ | ✗ | in ROS 2 msg | ✓ | **YES** in sim | shared latent state |
| `b_k` bottleneck score | env-computed from centroid + all obstacles (`environment.py:124-138`) | graph | ✓ | ✓ | **✗** | — | ✓ | **YES** | this is a *simulator-privileged* scalar; it also appears in **every edge feature** |
| `p_k^prog` normalized progress | centroid-to-goal | graph | ✓ | ✓ | **✗** | — | ✓ | **YES** | as above |
| `χ_k` split activity | latent | graph | ✓ | ✓ | ✗ | msg | ✓ | **YES** | |
| `onehot(m_k)` current mode | latent | graph | ✓ | ✓ | ✗ | msg | ✓ | consistent only if agreed | needs a protocol |
| LiDAR 36 rays | sensing | robot | ✓ | ✓ | ✓ | — | — | no | genuinely local ✔ |
| `TTC_i^min` | min TTC over **all** robots and obstacles (`dataset.py:145-177`) | robot | ✓ | ✓ | **✗** | — | ✓ | **YES** | no sensing-radius cutoff |
| `x̄` pooled raw context | mean of node features over **all** robots (`models.py:270`) | graph | ✓ | ✓ | **✗** | — | ✓ | **YES** | feeds score, aux, uncertainty, refine |
| `h̄` pooled latent | mean over all robots (`models.py:277`) | graph | ✓ | ✓ | **✗** | — | ✓ | **YES** | same |
| `r̂, σ̂, â, ℓ` | score / uncertainty / aux / logits | graph | ✓ | ✓ | ✗ | — | ✓ | **YES** | one vector per team |
| `τ*` selected mode | graph | ✓ | ✓ | ✗ | — | ✓ | **YES** | one decision per team |
| subteam ids | split assignment | graph | ✓ | ✓ | ✗ | msg | ✓ | **YES** | computed by a global lateral sort (`environment.py:146-155`) |

## 11.2 The eleven required determinations

1. **Does each robot build its own local graph?** In the benchmark, **no** — one graph per team (`policy_runtime.py:27`). In the ROS 2 node, **yes** (`agent_node.py:219-258`).
2. **Do all robots receive the same graph?** In the benchmark, trivially yes (there is one). In ROS 2, no — each robot's graph depends on its own comms radius and timeouts.
3. **Is pooling performed independently per robot?** In the benchmark, no. In ROS 2, yes — over that robot's own active team.
4. **Can different robots produce different scores?** In ROS 2, **yes, with no mechanism preventing it.**
5. **Is the mode selected independently or centrally?** **Centrally** in every number reported in the paper.
6. **Is the mode broadcast?** The ROS 2 `PeerState` message carries `topology_mode`, `formation_scale`, `split_active`, `subteam_id` — but the receiving robot only *stores* them; nothing reconciles conflicts.
7. **Is a leader used?** No.
8. **Voting or consensus?** The `TopologyConsensus` layer (`models.py:80-126`) is a *neural aggregation* inside one forward pass — one-hop vote averaging followed by a global pool. It is **not** a distributed consensus protocol: it has no rounds, no convergence property, and it terminates in a global mean.
9. **How are split assignments synchronized?** They are not. Each robot sorts *its own* active team by lateral projection (`agent_node.py:289-299`, `controllers.py:11-18`), so two robots with different neighbour sets can assign themselves to opposite lanes.
10. **How is inconsistent selection handled?** It is not handled at all.
11. **Is "decentralized" valid?** **No.** For the evaluated configuration: **[DECENTRALIZED TOPOLOGY CONSISTENCY IS UNSUPPORTED]**.

## 11.3 Choose one design and say so

| Option | Description | Honest for this code? |
|---|---|---|
| A. Fully independent decentralized selection | each robot decides alone, disagreement tolerated | matches the ROS 2 node, but **requires** the agreement study below before it can be claimed |
| B. Distributed consensus | rounds of vote exchange until agreement | not implemented |
| C. Leader-based | one robot decides and broadcasts | not implemented; would be a *cheap and defensible* addition |
| **D. Centralized mode selection with decentralized low-level control** | one team-level mode; per-robot actions | **This is exactly what the paper evaluated.** |

**Recommendation.** Report **D** as the configuration behind every result table, and add **A** as a dedicated study with a **C** (leader-broadcast) comparison. That is honest, and the D-vs-A gap becomes a genuine, publishable finding.

## 11.4 The decentralization study (E6)

**Setup.** Replace the single-graph inference path with per-robot inference: each robot i builds `G_i` from its own comms-radius neighbourhood, runs the model, and uses `u_i` and `τ_i`. Run in the simulator (not only Gazebo) so it is cheap and matched to the main benchmark.

**Coordination variants:** (i) independent; (ii) majority vote over one exchange round; (iii) leader broadcast (lowest ID in range); (iv) centralized oracle (current configuration, upper bound).

**Conditions:** packet loss {0,10,30,50,70,90} %; latency {0,50,100,200,500} ms; stale-state timeout {0.5,1,2} s; comms range {4,3,2} m; asynchronous control phases; robot dropout at t = T/3 and 2T/3 (the MAGEC attrition design is a good template here).

**Measure:** mode-agreement rate (fraction of steps where all robots hold the same mode); fraction of time in disagreement; maximum disagreement duration; **collision rate conditioned on disagreement vs. agreement**; split-assignment consistency (fraction of robots whose lane assignment matches the majority); recovery time after comms restoration; message rate (Hz) and bytes/s; success vs. comms range.

**Decision rule for the title:** claim **"distributed"** only if agreement ≥ 0.9 at 0 % loss *and* success degradation from 0 % to 30 % loss is within the CI of the centralized configuration. Otherwise the title says *local-observation* or nothing at all.

---

# PART 12 — REVISED PAPER OUTLINE

```
Title:  Predicting Short-Horizon Formation Recovery for Mode Selection
        in Multi-Robot Navigation

1  Introduction                                              (1.25 col-pages)
2  Related Work                                              (1.0)
   2.1 Graph policies for multi-robot control
   2.2 Formation navigation and adaptive formation
   2.3 Safe multi-agent navigation and barrier methods
   2.4 Reachability, viability, and recovery prediction
   2.5 Rollout supervision and counterfactual learning
   Table 1: neutral comparison table (objective columns only)
3  Problem Formulation                                       (1.25)
   3.1 Robots, dynamics, observations
   3.2 Formation modes, templates, and the formation tube
   3.3 The horizon-H recovery event            <- the paper's central object
   3.4 Mode-selection problem
   Table 2: symbol table with train/inference availability
4  Method                                                    (2.0)
   4.1 Local graph observation
   4.2 Candidate mode representation
   4.3 Mode-conditioned control policy
   4.4 Counterfactual rollout labelling (Alg. 1)
   4.5 Recovery-score prediction and training objective (Alg. 2)
   4.6 Online mode selection (Alg. 3)
   4.7 Formation geometry update
   4.8 Optional safety projection (Alg. 5)      <- demoted, brief
   4.9 Complexity and what is NOT guaranteed
5  Experimental Methodology                                  (1.5)
   simulator, dynamics, sensors, comms model, generators,
   train/val/test splits, methods, baseline fidelity (Table 3),
   tuning budgets, seed protocol, metrics, statistical tests, hardware
6  Results                                                   (3.0)
   6.1 Main benchmark (Table 4)
   6.2 Team-size behaviour (Fig. 5, Table 5)
   6.3 Recovery-score calibration        <- headline (Fig. 7, Table 8)
   6.4 Supervision-form study            <- headline (Table 10)
   6.5 Generalization: unseen layouts and unseen team sizes (Tables 6,7)
   6.6 Safety analysis (Table 9)
   6.7 Distributed execution and communication (Table 7b, Fig. 8-9)
   6.8 Computational cost (Table 11)
   6.9 Failure analysis (Fig. 11)
7  Discussion                                                (0.75)
8  Limitations                                               (0.5)
9  Conclusion                                                (0.25)
Appendix A  Feature definitions
Appendix B  Full per-N tables
Appendix C  Reproducibility card and command lines
```

---

# PART 13 — REWRITTEN TITLE, ABSTRACT, AND INTRODUCTION

## 13.1 Title

**Predicting Short-Horizon Formation Recovery for Mode Selection in Multi-Robot Navigation**

## 13.2 Abstract A — current-evidence version

> Multi-robot teams that must both reach a goal and hold a useful formation face a decision that instantaneous collision avoidance does not address: whether the shape they are currently holding still permits progress through the clutter ahead. We study formation-mode selection — keeping a compact formation, aligning into a single file, or splitting into two lanes — as a short-horizon prediction problem. For each candidate mode we define a horizon-H rollout utility that aggregates collision-free execution, goal progress, return toward a mode-conditioned formation tube, and irreversible-collapse events, and we train a graph neural controller to rank candidate modes by this utility while decoding a mode-conditioned action residual. We evaluate the controller in a matched 2-D simulator across [NUMBER OF SCENARIOS] scenario generators and team sizes from 2 to 24 robots, against a fixed-formation expert, a heuristic mode-selection controller, a rollout-oracle upper bound, a topology-agnostic graph policy, an ORCA implementation built on RVO2, and a decoupled discrete-time CBF quadratic program, using matched episode seeds and [NUMBER OF TRAINING SEEDS] independent training seeds. Rank-based mode supervision attains a conjunctive success rate of [MEAN ± STANDARD DEVIATION] versus [MEAN ± STANDARD DEVIATION] for a hard best-mode classifier ([95% CONFIDENCE INTERVAL] on the paired difference), while the topology-agnostic policy performs comparably to the full model on aggregate success. The scores are a shaped rollout utility rather than a formal recoverability certificate, mode selection is computed from a team-level graph rather than by independent robots, and all results are simulation-only.

*Why this abstract is honest:* it names the rollout utility as a utility, it reports the topology-agnostic baseline as comparable rather than beaten, it states the centralized selection, and it front-loads the limitation.

## 13.3 Abstract B — major-revision version (assumes all mandatory experiments complete)

> Decentralized formation navigation in clutter requires more than instantaneous collision avoidance: a team must judge whether a candidate formation shape still admits collision-free progress and a return to formation over the next few seconds. We formalize this as a **horizon-H recovery event** — collision-free execution, a minimum goal progress, and re-entry into a mode-conditioned formation tube within H steps — and we learn to predict its probability for each candidate mode from counterfactual rollouts. A graph neural controller maps a local interaction graph to a per-mode recovery probability and a mode-conditioned action residual; at run time each robot selects the mode with the highest predicted recovery probability. We evaluate on a matched benchmark of [NUMBER OF SCENARIOS] layout families and team sizes 2–24, with [NUMBER OF TRAINING SEEDS] independent training seeds, matched episode seeds, and faithful reference controllers (RVO2-ORCA and a decoupled discrete-time CBF-QP). The learned score is calibrated against empirical recovery frequency with AUROC [CALIBRATION RESULT] and expected calibration error [CALIBRATION RESULT], outperforming distance-to-goal, formation error, minimum clearance, and a trained value head. Rank-based supervision improves conjunctive success over hard best-mode classification by [MEAN ± STANDARD DEVIATION] ([95% CONFIDENCE INTERVAL], paired over matched episodes), and the advantage persists on unseen layouts ([UNSEEN-LAYOUT RESULT]) and unseen team sizes. Under independent per-robot execution, robots agree on the selected mode in [PACKET-LOSS RESULT] of steps at 30 % packet loss, and success degrades gracefully to [PACKET-LOSS RESULT]. We do not claim a formal viability kernel or a safety guarantee; the recovery score is an empirical probability estimate, and all evaluation is in simulation.

## 13.4 Abstract C — conference version (≈205 words)

> A multi-robot team moving through clutter must decide not only how to move but what shape to hold. Instantaneous safety filters answer the first question and ignore the second. We study formation-mode selection as short-horizon recovery prediction: for each candidate mode — keep, line, split — we define a horizon-H recovery event requiring collision-free execution, minimum goal progress, and re-entry into a mode-conditioned formation tube, and we estimate its probability from counterfactual rollouts of a shared expert controller. A graph neural network maps each robot's local interaction graph to per-mode recovery probabilities and a mode-conditioned action residual; the mode with the highest predicted probability is executed. We evaluate on a matched 2-D benchmark with team sizes 2–24, [NUMBER OF TRAINING SEEDS] training seeds, matched episode seeds, an RVO2-based ORCA controller, and a decoupled discrete-time CBF quadratic program. The predictor reaches AUROC [CALIBRATION RESULT] and expected calibration error [CALIBRATION RESULT] against empirical recovery frequency, beating geometric heuristics and a trained value head, and rank-based supervision improves conjunctive success over hard classification by [MEAN ± STANDARD DEVIATION] ([95% CONFIDENCE INTERVAL]). Gains persist on unseen layouts [UNSEEN-LAYOUT RESULT]. We claim no formal guarantee: the score is an empirical estimate, and evaluation is simulation-only.

## 13.5 Introduction — original-to-revised argument map

| Original paragraph | Original move | Problem | Revised move |
|---|---|---|---|
| ¶1 "Multi-robot formations are useful when they remain safe and task-capable… warehouse, inspection, SAR" | generic motivation + 3 citations | reads as filler; no problem stated | State the *decision* the paper is about within three sentences |
| ¶2 "Existing approaches usually solve only part of this problem" | 4-family sweep | lists families without a common axis | Organize around one axis: *what temporal object does the method score?* |
| ¶3 "This paper takes a different view… recoverable" | introduces the idea | the key term is undefined here and stays undefined | Define the recovery event *in the introduction*, concretely |
| ¶4 "The method does not claim an exact viability kernel" | disclaimer | disclaiming a claim you never earned draws attention to it | Replace with a positive statement of what *is* estimated and how it is validated |
| ¶5 two coupled stages | method preview | fine | keep, shorten |
| ¶6 4 contributions | contribution list | #1 and #4 are unsupported; #2–3 describe modules | 3 contributions, each with a named experiment |
| — | *missing* | no statement of scope/limits | add an explicit scope paragraph |

## 13.6 Rewritten Introduction

> **¶1.** A team of ground robots crossing a cluttered workspace must solve two coupled problems at once: avoid collisions, and hold a spatial arrangement that keeps the team useful — close enough to share sensing and communication, and shaped so the whole group can pass the geometry ahead. In warehouse aisles, pipeline inspection corridors, and rubble fields, the arrangement that is efficient in the open is the arrangement that blocks the team at a doorway. The team must therefore decide, repeatedly and quickly, what shape to hold.
>
> **¶2.** Collision avoidance alone does not make this decision. Reciprocal velocity-obstacle methods and control-barrier-function filters answer a question about the *present instant*: is the commanded velocity admissible right now? Both are effective at that question and both are indifferent to formation. A team can be certified collision-free at every instant and still arrive at a configuration from which no member can regain a workable formation before the mission window closes. The quantity that matters for the shape decision is not instantaneous admissibility but whether, over the next few seconds, the team can keep moving *and* return to a usable arrangement.
>
> **¶3.** Existing formation methods each address part of this. Fixed-formation controllers guarantee shape and fail at bottlenecks. Reactive adaptation schemes change shape by hand-designed switching rules keyed to local density, which produces chattering when the rule's trigger is noisy. Direct graph policies map local observations to actions and let shape emerge, which scales well but leaves the shape decision implicit and therefore un-inspectable and un-supervisable. None of these produces an explicit, per-candidate estimate of whether a given shape will still permit progress and re-formation.
>
> **¶4.** The gap we address is precisely this: *there is no learned, per-candidate estimate of short-horizon formation recovery that can be computed from a graph observation and used to select among structural modes at run time.* Reachability-based methods produce the right kind of object — a horizon-indexed feasibility quantity — but they are formulated for a single agent's state and are not conditioned on a team's formation template.
>
> **¶5.** Our hypothesis is that this estimate is (i) learnable from counterfactual rollouts, (ii) *calibrated* against realized outcomes, and (iii) useful: ranking candidate modes by predicted recovery yields better navigation than classifying the single best mode. We define the horizon-H recovery event explicitly — collision-free execution over H steps, at least p_min goal progress, and re-entry into a mode-conditioned formation tube — so that the prediction can be scored against ground truth rather than only against downstream reward.
>
> **¶6.** Concretely, each robot builds a K-nearest-neighbour interaction graph from its own state, its LiDAR return, a shared goal, and peer messages. A graph attention encoder produces node embeddings that feed two outputs: a per-mode recovery score over a small template set {keep, line, split}, and a mode-conditioned action residual on top of a shared base action. Labels come from short counterfactual rollouts of a fixed heuristic controller, one per candidate mode, executed in a copy of the simulator during data generation only. At run time the mode with the highest score is executed; an optional quadratic-program projection is available and is reported separately.
>
> **¶7.** We evaluate in a matched 2-D simulator with team sizes from 2 to 24, held-out layout families, held-out team sizes, [NUMBER OF TRAINING SEEDS] independent training seeds, and matched episode seeds across every method. Reference controllers are an RVO2-based ORCA implementation and a decoupled discrete-time CBF quadratic program, both run in the same dynamics with documented tuning budgets, together with a fixed-formation expert, a heuristic mode rule, and a rollout-oracle upper bound. Safety metrics are accumulated over the whole episode, not sampled at termination.
>
> **¶8.** Our contributions are: **(1)** a formulation of formation-mode selection as horizon-H recovery ranking, with an explicitly defined recovery event and a calibration protocol (§3.3, §6.3); **(2)** evidence that rank-preserving supervision distilled from counterfactual rollouts trains a better mode selector than hard best-mode classification at equal capacity and equal selection budget (§4.5, §6.4); **(3)** a matched benchmark with faithful reference controllers, episode-wide safety accounting, released code, seeds, and logs (§5, §6.1). We claim no formal viability or safety guarantee, and we state where the learned estimate fails (§8).

---

# PART 14 — REVISED METHOD SPECIFICATION

## 14.1 Problem formulation — required repairs

Define, in this order: robots `i ∈ {1..N}`; state `x_i = (p_i, v_i) ∈ R⁴`; double-integrator dynamics with `‖v‖ ≤ v_max`, `‖u‖ ≤ u_max`; obstacle set `O`; shared goal `g`; comms graph `G_c` (range `r_c`, loss `ρ`, latency `Δ_c`); interaction graph `G_i` (K-NN over `G_c`); mode set `T = {keep, line, split}`; templates `δ^τ(N, c)` parameterized by the corridor direction; **formation tube** `T_ε^τ = {x : form_rms(x; τ) < ε_form}`; formation error; progress; clearance constraints; switch cost; and the **recovery event**.

**Recovery event (the paper's central definition):**

```
Rec_H(x_k, τ) = 1  ⟺  (i)   min_{h≤H} min-clearance(x_{k+h}) ≥ d_min
                  ∧  (ii)  progress(x_{k+H}) − progress(x_k) ≥ p_min
                  ∧  (iii) ∃ h ≤ H : x_{k+h} ∈ T_ε^τ
                  ∧  (iv)  no irreversible collapse on [k, k+H]
R_H(x,τ) = P( Rec_H(x,τ) = 1 | x_k = x, mode held at τ, π_expert )
```

**Three information regimes must be separated in a boxed remark:**

- **Global state** `x_k` — used only to *write* the ideal problem and to *generate labels*.
- **Label-generation information** — full simulator state, cloning, and the expert controller. Available offline only.
- **Inference information** — per-robot: own kinematics, LiDAR, shared goal, and messages from peers within `r_c`. **Every quantity used at inference must appear in this list or the paper must say it is a privileged input.**

**Symbol table (replaces the current feature appendix as a main-text table):**

| Symbol | Meaning | Dim | Train | Inference | Local/Global |
|---|---|---|---|---|---|
| `p_i, v_i` | pose, velocity | 2,2 | ✓ | ✓ | local |
| `s_i` | LiDAR scan | 36 | ✓ | ✓ | local |
| `g` | shared goal | 2 | ✓ | ✓ | global (broadcast) |
| `N_i` | neighbours within `r_c` | K | ✓ | ✓ | local |
| `p̄_i` | centroid of `N_i ∪ {i}` | 2 | ✓ | ✓ | **local approximation** — currently global; **must be changed** |
| `b_i` | local bottleneck from own scan | 1 | ✓ | ✓ | **local** — currently the simulator's global `b_k`; **must be changed** |
| `κ, χ, m` | scale, split activity, mode | 1,1,3 | ✓ | ✓ | shared latent (communicated) |
| `q(x,τ)` | rollout utility / recovery label | 3 | ✓ | ✗ | global, offline |
| `r̂_τ` | predicted per-mode score | 3 | ✓ | ✓ | graph-level |
| `u_i^{(τ)}` | mode-conditioned action | 2×3 | ✓ | ✓ | per-robot |

**Equation audit — items to fix before resubmission.** `E_form` is defined with global `δ_i^τ` and a global centroid but is used as a node feature at inference (undeclared privilege). `R(x_k;τ)` (Eq. recoverability) mixes `Mean(·)` over heterogeneous quantities with different units and ranges without stating the normalization of each term — the equation as printed is not reproducible from the text; `recoverability.py:56-68` is required to interpret it. The selector key `K_τ` lists ten components in the text but `safety.py:517-532` uses eleven and applies a pre-filter on `score_signal ≥ 0` and a persistence rule (`safety.py:504-515`) that the text does not mention at all. `σ̂` enters both `r̃` and `K_τ`, double-counting. Fix all four or delete the components.

## 14.2 Method section skeleton (§4)

Each subsection: intuition → formal definition → inputs → outputs → training → inference → implementation → limitation.

- **4.1 Local graph observation.** K-NN over communicable peers; node/edge features restricted to the locally observable set; state the frame and the normalization.
- **4.2 Candidate mode representation.** Three templates; corridor direction estimated from the local scan, not from the simulator; lane gap derivation.
- **4.3 Mode-conditioned control policy.** `u_i^{(τ)} = tanh(φ_base(h_i) + 1[τ≠keep]·φ_Δ([h_i‖onehot(τ)]))`. Limitation: the residual is trained under teacher-forced modes and executed under selected modes (exposure bias) — state it.
- **4.4 Counterfactual rollout labelling.** Algorithm 1 below.
- **4.5 Recovery-score prediction and training objective.** Algorithm 2.
- **4.6 Online mode selection.** Algorithm 3 — reduced to `argmax` with a keep tie-break.
- **4.7 Formation geometry update.** Scale, split assignment, smoothing.
- **4.8 Optional safety projection.** Algorithm 5; explicitly labelled *decoupled discrete-time CBF-QP projection with blending*, with the statement: *this provides no formal safety guarantee because the constraints are linearized per pair, non-reciprocal, and the output is blended with the nominal action.*
- **4.9 Complexity and non-guarantees.** `O(NKd)` encoder; `O(|T|)` scoring; QP is `O(m²)` per robot with `m` active constraints. Then an explicit list of what is **not** guaranteed: forward invariance, deadlock freedom, mode agreement across robots, and recovery.

## 14.3 Pseudocode

**Algorithm 1 — Counterfactual rollout dataset generation**
```
Input: scenario pool S, expert π_e, horizon H, rollouts M, modes T
for each episode e with seed z_e:
    x ← reset(S, z_e);  τ_prev ← keep
    while not done:
        for τ ∈ T:
            for m = 1..M:                       # M>1 required for probabilities
                x' ← clone(x)
                y_m ← RolloutRecoveryEvent(x', τ, π_e, H, noise=ξ_m)
            p̂_τ ← (1/M) Σ_m y_m                 # empirical recovery probability
        record( graph(x), {p̂_τ}, {π_e(x,τ)}_τ, τ_prev )
        τ_exec ← argmax_τ p̂_τ  (keep tie-break)
        x ← step(x, π_e(x, τ_exec), τ_exec);  τ_prev ← τ_exec
Output: dataset D
```
Note what changed: **M stochastic rollouts** replace one deterministic rollout, and the label is a probability, not a shaped sum. This is the single change that licenses the paper's title.

**Algorithm 2 — Training**
```
Input: D, model f_θ, epochs E (SAME for every learned method)
for epoch = 1..E:
    for batch B ⊂ D:
        h ← Encoder(node_x, edge_index, edge_attr)
        r̂ ← ScoreHead(pool(h), pool(node_x));  U ← ActionBank(h)
        L_score ← BCE(σ(r̂), p̂)                 # proper scoring rule
        L_rank  ← PairRank(r̂, p̂)
        L_act   ← ½[MSE(U_keep, y_keep) + Σ_τ ω_τ MSE(U^τ, y^τ)],  ω = normalize(p̂)
        L ← mean(L_act, ½(L_score + L_rank));  θ ← AdamW(θ, ∇L)
    if epoch mod I == 0: evaluate on the VALIDATION split (held-out layouts, held-out N)
Select the checkpoint by validation score.  # never by test-distribution rollouts
```

**Algorithm 3 — Online per-robot inference**
```
Input: own state, scan, goal, peer messages, previous mode τ_prev
N_i ← peers with age < t_max and range < r_c
G_i ← KNN graph over N_i ∪ {i};  features from LOCAL quantities only
h ← Encoder(G_i);  r̂ ← ScoreHead(pool_i(h), pool_i(x))
τ_i ← argmax_τ r̂_τ   (tie-break: keep, then τ_prev)
u_i ← ActionBank(h_i)[τ_i]
u_i ← SafetyProject(u_i, neighbours within sensing range)   # optional
publish PeerState(p_i, v_i, τ_i, κ_i, χ_i, subteam_i)
```

**Algorithm 4 — Mode coordination (one round; NEW, currently absent)**
```
Input: τ_i from Alg. 3, peer modes {τ_j} received this cycle
Variant A (independent):  τ_i* ← τ_i
Variant B (majority):     τ_i* ← mode(τ_i, {τ_j});  ties → keep
Variant C (leader):       τ_i* ← τ_{j*}, j* = min-id peer in range (self if none)
Record: agreement_i ← 1[τ_i* == majority({τ_j} ∪ {τ_i})]
```

**Algorithm 5 — Safety correction**
```
if risk(local neighbourhood) < ρ_th: return u
build half-planes  a_ijᵀ u ≥ b_ij  from  h_ij = ‖p_i−p_j‖² − d_safe²
u_safe ← argmin ‖u − u*‖²  s.t. half-planes ∧ ‖u‖ ≤ u_max   (exact 2-D active set)
return (1−β)u + β u_safe,  β = clip((risk−ρ_th)/(1−ρ_th))
# State: blending voids any forward-invariance property the QP alone would have.
```

**Explicit declarations required in §4.9.**
- *Learned:* node/edge encoders, per-mode score, action base and residual.
- *Hand-designed:* the three templates, the corridor estimator, the geometry smoother, the QP, the tie-break rule, and the entire expert controller.
- *Global at training only:* simulator cloning, rollout labels, formation error, bottleneck score.
- *Local at inference:* own kinematics, LiDAR, goal, peer messages. **Any exception must be named.**
- *Not guaranteed:* collision-freedom, deadlock-freedom, mode agreement, recovery, forward invariance.

---

# PART 15 — TABLE AND FIGURE DESIGNS

## 15.1 Metric definitions (precise, replacing the current set)

| Metric | Definition | Change from current |
|---|---|---|
| GoalReached | centroid within `ε_goal` of `g` at any step | make explicit that it is the **centroid** |
| CollisionFree | **no step** in the episode has any pair below `d_rr` or any robot–obstacle below `d_ro` | **was terminal-step only** — critical fix |
| FormOK | `form_rms < ε_form` **at the terminal step**, *and separately* `%time-inside-tube` | disambiguate |
| Success | `GoalReached ∧ CollisionFree ∧ FormOK` | unchanged, but now built on fixed components |
| Collapse | report the three disjuncts separately; do not report the union as a headline | currently confounded with Deadlock |
| Deadlock | ≥ `k_stall` consecutive non-progress steps ∧ ¬GoalReached | unchanged; report `k_stall` |
| Stall | fraction of steps with non-positive centroid progress | unchanged |
| Topology switch | discrete mode changes per step **and** `formation_scale_motion_rate` | must report both |
| Formation error | RMS and max over robots, over time | add max |
| Progress | normalized centroid closure | unchanged |
| Recovery time | steps from tube exit to re-entry (∞ if never) | currently a mis-specified ratio (`environment.py:543-545`) |

Set the collision thresholds to be **physically consistent**: `d_rr = 2r + margin` with the resolver separating to `> d_rr`, and `d_ro = r + R + margin` likewise; and cap `min_scale` so that the commanded spacing at full compression is strictly greater than `d_rr`.

**Metric suite placement.** *Main table:* success, collision-free, form-OK, deadlock, completion time. *Separate plots:* per-N curves, calibration, communication sweeps. *Appendix:* full per-N tables, near-miss and clearance distributions, path efficiency. *Supplement:* per-seed values, per-episode CSVs, trajectory videos.

## 15.2 Table templates

| Table | Rows | Columns | Best-value rule | Statistical markers | Interpretation |
|---|---|---|---|---|---|
| **T1** Environment & training config | parameters | value, source | — | — | reproducibility |
| **T2** Baseline fidelity | 10 baselines | source, official impl., dynamics/obs/objective matched, tuning budget, adaptations, limitations, verdict | — | — | licenses every comparison |
| **T3** Main results | methods | success, coll-free, form-OK, deadlock, time | bold only if CI excludes every other CI | † = paired CI excludes 0 vs. reference; ‡ Holm-corrected | headline |
| **T4** Per-team-size | methods × N | success (mean ± SD) | none — trend only | — | scaling |
| **T5** Unseen layouts | methods | success, coll-free, Δ vs seen | bold w/ CI | † | generalization |
| **T6** Unseen team sizes | methods | as T5 | as T5 | † | generalization |
| **T7** Communication robustness | coordination variants × loss/latency | success, agreement rate, disagreement duration | — | — | H8 |
| **T8** Calibration | predictors | AUROC, AUPRC, Brier, ECE, false-safe@0.5/0.7/0.9, top-1 rank acc. | best per column w/ CI | DeLong CI | H2 headline |
| **T9** Safety analysis | filter variants | episode collisions, near-miss, min clearance, deadlock, time frozen, activation %, mean/max ‖Δu‖, ms | — | † | H6 |
| **T10** Ablation | 17 variants | success, coll-free, form-OK, deadlock, switches | none — report Δ vs Full with CI | † | isolates each component |
| **T11** Runtime & scaling | methods × N | ms/step (model-preloaded), MB, msgs/s, bytes/s | — | — | practicality |

**Caption rules.** Every table caption states: number of seeds; number of episodes; whether episodes are matched; what the bolding rule is; and which metrics are deterministic functions of others.

## 15.3 Figure set

| Fig | Content | Panels | Axes | Question answered | Raw data needed |
|---|---|---|---|---|---|
| 1 | **Teaser** — matched pair, same seed, same layout | 2 (instantaneous-only vs. recovery-aware selection) | metric axes with a scale bar; light background; robot IDs off | why shape choice matters | 2 matched trajectories |
| 2 | **Method** — only retained components | 1 | — | what is learned vs. designed; local vs. global | — |
| 3 | **Counterfactual labelling** — one state, three modes | 3 rollout fans + resulting `p̂` bars | metres | how labels are made | 3×M rollouts |
| 4 | **Per-robot inference** — sensed / received / predicted / published | 1 | — | the decentralization question, answered visually | — |
| 5 | **Success vs N** | 1, lines with 95 % bands | N (2–24) × success | scaling | per-seed per-N |
| 6 | **Generalization** — seen vs unseen layout/N | 2 grouped bars with CIs | — | H7 | split results |
| 7 | **Calibration** — reliability + ROC | 2 | predicted vs empirical; TPR/FPR | H2 headline | calibration set |
| 8 | **Communication** — success and agreement vs loss and latency | 2 | loss %, latency ms | H8 | comms sweep |
| 9 | **Agreement & switching** — agreement rate and switch/scale-motion over time | 2 | time | churn and consistency | per-step logs |
| 10 | **Ablation** — Δsuccess vs Full with CIs | 1 forest plot | Δ success | H1,H3–H6 at a glance | ablation runs |
| 11 | **Failure taxonomy** — 4 representative failures | 4 | metres | honesty; reviewers reward this | selected episodes |

**Figures to delete outright:** the current dark decorative teaser (`figures/teaser/*.png`) — no axes, no scale, `Goal` text overprinting the goal marker, ornamental sunburst rays, unexplained robot indices; and the two 12-column trajectory grids (`all_trajectories.png`, `ablation_trajectories.png`), which at print size convey no readable information and occupy two full-width pages. Replace both with Fig. 11.

**Figure 2 fixes:** remove the column labels "AI front-end encoder" / "AI back-end heads"; remove all `code:` identifiers; fix the text collision at the `X^t, E^t, edge_index` arrow; and — most importantly — the pooling box must not be labelled "local robot graph view" while computing `(1/|V|) Σ_{j∈V}` over the whole team.

---

# PART 16 — DISCUSSION, LIMITATIONS, CONCLUSION

## 16.1 Discussion — what to write (and what the data will probably force you to write)

- **What the experiments show.** State the effect sizes and their intervals before interpreting them. If the topology-agnostic policy remains within the interval of the full model on aggregate success, say so in the *first sentence* of the discussion. Reviewers forgive a small effect; they do not forgive a hidden one.
- **Why counterfactual supervision helps — or does not.** The mechanism to argue: rank-preserving soft targets retain information about *near-ties* between modes, which a hard arg-max label discards; near-ties are exactly the states where a classifier's decision boundary is unstable and produces churn. This predicts, testably, that the benefit concentrates in low-margin states — **report the effect stratified by label margin.** If it does not concentrate there, the mechanism is wrong and should be abandoned rather than defended.
- **When mode adaptation is beneficial.** Expect: in narrow passages at moderate-to-large N, and nowhere else. The aggregate near-null (`−Topology` Δ = −0.003) is consistent with a real but scenario-local effect diluted by three scenarios in which the mode never needs to change. Report the stratified numbers; do not report only the aggregate.
- **Why the aggregate effect is small.** Two structural reasons, both worth stating: (i) every learned method is behaviour-cloned from one shared expert, so the expert is a ceiling — add the fixed-formation expert and the rollout oracle to the tables and the headroom becomes visible; (ii) with a conjunctive success criterion dominated by the collision term, and a collision term dominated by simulator geometry, the metric has low sensitivity to the shape decision.
- **Recovery prediction vs. value estimation.** Meet this objection head-on: the score *is* a policy-evaluation quantity for the expert under a designed reward. What distinguishes it from a critic is (a) it is conditioned on a discrete structural mode held fixed over the horizon, and (b) under the binary-event formulation it has a calibratable meaning. Say this explicitly; a reviewer will otherwise say it for you.
- **Safety–progress trade-off.** Report the filter's activation rate and mean action modification alongside its deadlock cost; the honest framing is a Pareto point, not a strict improvement.
- **Scalability.** Encoder cost is `O(NKd)`, but *performance* degrades sharply with N in the current benchmark. Distinguish computational scalability from behavioural scalability and report both.
- **Communication dependence and template dependence.** The method is bounded by three hand-designed templates and by peer state; both are design commitments, not incidental.
- **Label-generation cost and expert bias.** M×|T|×H simulator steps per training state, and the learner cannot exceed the expert's competence in states where the expert is the label source. Quantify the cost in core-hours.

## 16.2 Limitations (write these as specific sentences, not a generic paragraph)

1. All results are simulation-only in a 2-D double-integrator world; no physical-robot experiment is reported.
2. Robots are homogeneous, holonomic at the planning level, and identical in radius, speed, and acceleration limits.
3. The mode set contains three hand-designed templates; the method cannot invent a shape outside this set.
4. Obstacles are discs of fixed radius; there are no walls, concave geometry, or non-convex clutter.
5. All robots share a single goal broadcast to the team; multi-goal and task-allocated settings are not addressed.
6. **In the configuration that produced the reported tables, mode selection is computed from a team-level pooled graph. Independent per-robot selection is evaluated only in §6.7, and no consensus protocol is used; robots may disagree.**
7. No formal reachability, viability, or forward-invariance guarantee is provided; the recovery score is an empirical estimate.
8. The safety projection blends its output with the nominal action, which removes any guarantee the quadratic program would otherwise provide.
9. Labels depend on a single heuristic rollout policy; a different expert would yield different recovery labels and a different learned ranking.
10. Counterfactual labelling requires a simulator and full state, and is therefore restricted to offline data generation.
11. A non-trivial collision and collapse rate remains at large team sizes; the method does not solve dense-team navigation.
12. Sim-to-real transfer is untested; the ROS 2 node exists but its evaluation is outside the scope of this paper `[REQUIRES NEW EXPERIMENT]` if the claim is retained.

## 16.3 Conclusions

**A. Conservative (current evidence, after Stage-1/2 repairs).**
> We asked whether short-horizon rollout information can be distilled into a useful signal for choosing among formation modes during cluttered multi-robot navigation. We formulated mode selection as a ranking problem over a small template set, supervised by counterfactual rollouts of a shared heuristic controller, and evaluated it on a matched simulator benchmark with [NUMBER OF TRAINING SEEDS] training seeds, matched episode seeds, and faithful reference controllers. Rank-based supervision produced a more stable mode selector than hard best-mode classification, with substantially lower mode churn; on aggregate task success the method performed comparably to a topology-agnostic graph policy, with the benefit concentrated in bottleneck-dominated states. The learned score is a shaped rollout utility, not a formal recoverability certificate, and all evaluation is in simulation. The natural next step is to replace the shaped utility with a calibrated binary recovery probability and to test whether calibration quality predicts control quality.

**B. Strong (all mandatory experiments succeed).**
> We asked whether a graph controller can predict, per candidate formation mode, the probability of short-horizon recovery — collision-free progress with return to a formation tube — and whether predicting it well improves navigation. Defining the recovery event explicitly made the prediction falsifiable: the learned score achieves AUROC [CALIBRATION RESULT] and expected calibration error [CALIBRATION RESULT] against empirical recovery frequency on held-out layouts, outperforming geometric heuristics and a trained value head. Selecting modes by predicted recovery improved conjunctive success over hard best-mode classification by [MEAN ± STANDARD DEVIATION] ([95% CONFIDENCE INTERVAL], paired), and the advantage persisted on unseen layouts and unseen team sizes. Under independent per-robot execution, robots agreed on the selected mode in [PACKET-LOSS RESULT] of steps at 30 % packet loss. We provide no formal viability or safety guarantee, and evaluation remains in simulation; extending the recovery event to heterogeneous teams and validating it on hardware are the next steps.

**Banned words in both:** *proves, guarantees, universally, state-of-the-art, real-world ready, general solution, fully safe.*

---

# PART 17 — REPRODUCIBILITY CHECKLIST

## 17.1 Deficiency table

| Missing item | Why it matters | Where to add | Required value | Recoverable from code? |
|---|---|---|---|---|
| Simulator version / commit | benchmark is bespoke | §5.1 + repo | commit hash + tag | ✓ |
| Environment generator spec | layouts drive every result | §5.1 + Appendix A | obstacle counts, ranges, corridor geometry, **goal placement** | ✓ `environment.py:94-122` |
| Randomized starts | claimed but absent | §5.1 | spawn distribution | ✓ — **must be implemented** |
| Robot dynamics & limits | comparability | Table 1 | present, but state the integrator explicitly | ✓ |
| Node-feature ordering | 68-D vector is unreproducible from the paper's list | Appendix A | exact index map | ✓ `dataset.py:205-224` |
| Edge-feature ordering | same | Appendix A | exact index map | ✓ `dataset.py:256-262` |
| Parameter count per method | capacity fairness | Table 1 | `[REQUIRES AUTHOR VALUE]` | ✓ computable |
| Optimizer settings | AdamW lr 3e-4, wd 1e-5 present; **schedule, grad-clip 1.0, batch 32** missing from the paper | Table 1 | all | ✓ `train.py:324,189` |
| Epoch budgets per method | **300 vs 120 is an unfair-comparison red flag** | Table 1 | must be equalized | ✓ `config.py:45-47` |
| Checkpoint-selection protocol | selection on the test distribution | §5.4 | must move to a held-out validation split | ✓ `train.py:376-424` |
| Rollout-validation config | it is part of model selection | Table 1 | scenarios, N, episodes, top-k, recheck offset | ✓ `config.py:57-67` |
| Number of training states | dataset size never reported | §5.1 | `[REQUIRES AUTHOR VALUE]` — 500 episodes × variable length + hard negatives | ✓ printed at runtime |
| Rollouts per state / horizon | H = 14 given; M = 1 not stated | §4.4 | H, M | ✓ |
| Hard-negative recipe | "perturbations whose amplitude increases with the recoverability deficit" is not a specification | §4.4 or delete | trigger condition, noise scale, count | ✓ `dataset.py:327-344` |
| Score normalization | `tanh(q/mean|q|)` | §4.4 | exact formula | ✓ |
| Loss weights | "coefficient-light" is a claim, not a spec | §4.5 | the exact nesting of means | ✓ `train.py:153-169` |
| Train/val/test split | 90/10 random split of the *same* distribution; no test split | §5.2 | layout-disjoint and N-disjoint splits | ✓ `train.py:28-32` |
| Evaluation seeds | formula given; **starts are not random** | §5.1 | corrected statement | ✓ |
| Training seeds | one | §5.1 | ≥5 | ✓ |
| Baseline tuning budget | none reported | Table 2 | sweep ranges per baseline | ✗ **[REQUIRES NEW EXPERIMENT]** |
| Runtime hardware | "machine-dependent" | §5.1 | CPU/GPU model, threads, and **model preloaded** (currently the checkpoint is re-loaded from disk inside the timed loop, `evaluate.py:42-43`) | ✓ — **must be fixed** |
| Code / data / checkpoints | not released | §5 + footnote | public URL | ✗ |

## 17.2 Repository layout to adopt

```
RVT-Swarm/
  README.md            LICENSE            Dockerfile         environment.yml
  configs/             # one YAML per experiment; every number in the paper maps to one file
  src/
    models/ control/ rollout/ safety/ communication/ metrics/
  baselines/           # orca_rvo2.py  cbf_qp.py  predictive_mode_search.py  expert.py  oracle.py
  scenarios/           # generators + frozen test-split manifests (JSON)
  scripts/
    train.py  evaluate.py  run_ablation.py  run_generalization.py
    run_communication_test.py  run_calibration.py  run_runtime.py  make_tables.py  make_figures.py
  tests/               logs/   results/   figures/   checkpoints/   docs/
```

## 17.3 Command templates

```bash
# Main results (5 training seeds, fixed evaluation seed, matched episodes)
python scripts/train.py    --config configs/main.yaml --train-seeds 0 1 2 3 4 --data-seed 0
python scripts/evaluate.py --config configs/main.yaml --eval-seed 1234 --episodes 25 \
                           --methods expert,heuristic_mode,oracle_mode,gnn_bc,classifier,ours,orca_rvo2,cbf_qp,pred_mode_search
python scripts/make_tables.py --in results/main --out figures/T3.tex --paired-bootstrap 10000

# Ablations (17 variants x 5 seeds)
bash scripts/run_ablation.sh --config configs/ablation.yaml --train-seeds 0 1 2 3 4

# Generalization
python scripts/run_generalization.py --split unseen_layout --config configs/gen.yaml
python scripts/run_generalization.py --split unseen_teamsize --config configs/gen.yaml

# Communication / distributed execution
python scripts/run_communication_test.py --coordination independent,majority,leader,centralized \
       --loss 0 10 30 50 70 90 --latency 0 50 100 200 500

# Recovery-score calibration
python scripts/run_calibration.py --states 20000 --rollouts 8 --horizons 7 14 28 --out results/calib

# Runtime (model preloaded; excludes checkpoint I/O)
python scripts/run_runtime.py --preload --repeats 5 --team-sizes 2 4 8 16 24
```

---

# PART 18 — VENUE STRATEGY

| Venue | Contribution level expected | Experimental strength expected | Hardware needed? | Pages | Novelty bar | P(desk reject **as-is**) | Minimum changes | Recommended positioning |
|---|---|---|---|---|---|---|---|---|
| **IEEE Access** | moderate; breadth tolerated | moderate; multi-seed and honest baselines still required | no | ~13 | low–moderate | **1.0 — resubmission of this article is explicitly prohibited** | n/a | **Do not resubmit.** See §18.2 |
| **IEEE RA-L** | one sharp, well-evidenced idea | high: seeds, CIs, ablations, generalization; hardware optional but common | preferred, not required | 8 | moderate–high | 0.85 | E0–E5 + calibration | Option B, title R1. **Best realistic target** |
| **ICRA** | novelty + rigor | high; reviewers check baselines | often expected | 6–8 | high | 0.9 | E0–E5 + a hardware demo or a strong sim-to-real argument | Option B, with the distributed study |
| **IROS** | slightly more tolerant of system papers | high | helpful | 6–8 | moderate–high | 0.85 | E0–E5 | Option B or A; MAGEC's venue, and a good fit for the ROS 2 study |
| **Autonomous Robots** | deeper study, more analysis | very high; calibration study is a natural fit | valued | 20+ | high | 0.9 | E0–E8 + extended analysis | Option B with the full calibration and communication studies |
| **Robotics and Autonomous Systems** | systems + evaluation | high | optional | 15–20 | moderate | 0.8 | E0–E5 | Option A/D, benchmark-forward framing |
| **Journal of Intelligent & Robotic Systems** | applied contributions | moderate–high | optional | 15–20 | moderate | 0.75 | E0–E4 | Option C/D framing |
| **IEEE Robotics & Automation Magazine / workshops** | — | — | — | — | — | — | — | not appropriate |

**Recommendation: IEEE RA-L (with IROS option) after the Stage-1–3 work.** RA-L rewards exactly the shape of Option B — a single falsifiable claim with a calibration study — and its 8-page limit will force the discipline this manuscript most lacks.

## 18.2 What makes a *genuinely new* article rather than a disguised resubmission

The IEEE Access decision prohibits resubmission of **this article**. That prohibition attaches to the work, not to the title string. Changing the title from *"RVT-Swarm: Recoverability-Aware Topology Control…"* to *"Rollout-Supervised Resilient Formation Reconfiguration…"* and renaming `shield`→`safety filter` — which is what the current `latex/access.tex` does — is **not** a new article, and submitting it to another IEEE venue with substantially the same tables would be reasonably read as a duplicate submission.

A genuinely new article requires at minimum:

1. **A different central scientific question**, with different primary experiments — here, *recovery prediction and its calibration* rather than *topology control performance*.
2. **A regenerated evidence base**: fixed metric semantics (episode-wide), fixed collision geometry, randomized starts and goals — meaning every number in every table changes.
3. **Faithful baselines with matched tuning budgets**, replacing three misnamed proxies.
4. **A statistical protocol that did not exist before**: ≥5 training seeds, decoupled evaluation seeds, paired tests, corrected multiplicity.
5. **At least two experiment classes that do not appear in the rejected manuscript**: the calibration study, and either the generalization splits or the distributed-execution study.
6. **A method that is materially smaller**: heads removed, selector reduced, safety layer demoted.

Meeting 1–6 produces a paper whose question, evidence, and conclusions differ from the rejected one. Meeting only 1 and 6 does not. Be prepared to state the relationship in the cover letter: *"An earlier and substantially different manuscript studying topology-control performance was declined without review at IEEE Access; the present work reformulates the problem as recovery prediction, regenerates all experiments under corrected metrics, and adds calibration and generalization studies that the earlier manuscript did not contain."* Disclosing this is safer than hoping no one notices.

---

# PART 19 — WEEK-BY-WEEK ACTION PLAN

## Stage 1 — Week 1 (no new experiments)

| # | Task | Priority | Effort | Depends on | Output | Acceptance criterion | Section |
|---|---|---|---|---|---|---|---|
| 1.1 | Purge unlicensed terminology: *recoverability, decentralized, resilient, certifiable, viability, shield* | P0 | 0.5 d | — | edited `.tex` | zero occurrences outside a "what we do not claim" paragraph | all |
| 1.2 | Rewrite title + abstract per Part 13 | P0 | 0.5 d | 1.1 | new front matter | no claim without a named experiment | front |
| 1.3 | Cut contributions 4 → 3; map each to a section | P0 | 0.5 d | 1.2 | new list | each has a §-reference | §1 |
| 1.4 | Replace the capability checkmark table with the neutral comparison table | P0 | 0.5 d | — | Table 1 | every column operationally defined; no ours-row ✓ sweep | §2 |
| 1.5 | Rename all baselines honestly; delete unsupported citations from table rows | P0 | 0.5 d | — | Tables 1,3 | no name that the implementation does not earn | §5,6 |
| 1.6 | Fix metric definitions text to match code; add the terminal-vs-episode disclosure | P0 | 0.5 d | — | §5.1 | text and code agree | §5 |
| 1.7 | Recover every missing hyperparameter from the code into Table 1 | P0 | 1 d | — | Table 1 | Part 17 table has no unfilled ✓ rows | Table 1 |
| 1.8 | Remove the uncertainty head, auxiliary head, and 8 of 10 selector tie-breaks from the method description | P1 | 1 d | — | §4 | method figure fits the retained components | §4 |
| 1.9 | Fix the placeholder DOI/date, template residue, and figure text collisions | P1 | 0.5 d | — | clean PDF | no `xxxx` in the PDF | front |
| 1.10 | Redraw the teaser and delete the two trajectory grids | P1 | 1 d | — | Figs 1, 11 | axes, scale bar, light background, readable at print size | §1,6 |

## Stage 2 — Weeks 2–4 (implementation; blocks everything downstream)

| # | Task | Priority | Effort | Depends on | Output | Acceptance criterion | Section |
|---|---|---|---|---|---|---|---|
| 2.1 | **Episode-wide metric accumulation** in `evaluate.py` | **P0** | 1 d | — | corrected evaluator | unit test: an episode with a mid-episode contact reports `CollisionFree = 0` | §5,6 |
| 2.2 | **Fix collision-threshold geometry** (`min_rr`, `min_ro`, resolver margin, `min_scale`) | **P0** | 1 d | — | consistent config | post-resolution separation > threshold; commanded spacing > threshold | §5 |
| 2.3 | Randomize spawn positions and goal placement | P0 | 1 d | 2.2 | new generator | starts differ across seeds (regression test) | §5 |
| 2.4 | Decouple `train_seed` / `data_seed` / `eval_seed` | **P0** | 1 d | — | new seed API | evaluation set identical across training seeds | §5 |
| 2.5 | Equalize epochs and checkpoint-selection budget across learned methods | **P0** | 0.5 d | 2.4 | config | identical E, I, top-k for every learned method | §5 |
| 2.6 | Move checkpoint selection to a **held-out** validation split (unseen layouts + unseen N) | **P0** | 2 d | 2.3 | split manifests | zero overlap between validation and test generators | §5 |
| 2.7 | Add `fixed-formation expert` and `oracle mode selection` baselines | P0 | 1 d | — | 2 baselines | both appear in every table | §6 |
| 2.8 | Wire the real `orca` / `cbf_qp` / `centralized_mpc` into the reported pipeline; document tuning sweeps | P0 | 3 d | 2.1 | fidelity table | Table 2 complete with verdicts | §5 |
| 2.9 | Train 5 seeds × {ours, GNN-BC, classifier, value-head, scalar-recovery} | **P0** | 5 d compute | 2.1–2.6 | checkpoints + logs | 25 runs complete; per-seed metrics logged | §6 |
| 2.10 | Paired-bootstrap / Wilcoxon / Holm reporting pipeline | P0 | 2 d | 2.9 | `make_tables.py` | every cell emits mean ± SD and CI | §6 |
| 2.11 | Per-team-size reporting with CIs | P1 | 1 d | 2.9–2.10 | Table 5, Fig. 5 | bands rendered | §6 |
| 2.12 | Fix runtime measurement (preload the model, exclude I/O) | P1 | 0.5 d | — | Table 11 | ms/step stable across repeats | §6 |
| 2.13 | Convert rollout labels to M-sample binary recovery events | P0 | 3 d | 2.2 | new label generator | labels are probabilities in [0,1] | §4.4 |

## Stage 3 — Weeks 5–8 (validation)

| # | Task | Priority | Effort | Depends on | Output | Acceptance criterion | Section |
|---|---|---|---|---|---|---|---|
| 3.1 | **Calibration study** (Part 10) | **P0** | 5 d | 2.13 | Table 8, Fig. 7 | AUROC ≥ 0.75 (CI lower > 0.70) and ECE ≤ 0.10, beating all heuristics — **or** the title reverts to C1 | §6.3 |
| 3.2 | Unseen-layout and unseen-N generalization | **P0** | 4 d | 2.6, 2.9 | Tables 5,6, Fig. 6 | both splits reported for every method | §6.5 |
| 3.3 | **17 isolated ablation variants × 5 seeds** | **P0** | 8 d compute | 2.9 | Table 10, Fig. 10 | no compound variants remain; forest plot with CIs | §6.4 |
| 3.4 | Per-robot inference path + coordination variants + comms sweep | P1 | 6 d | 2.9 | Table 7, Figs 8–9 | agreement rate reported at every loss level | §6.7 |
| 3.5 | Safety-layer comparison with full instrumentation | P1 | 3 d | 2.1 | Table 9 | activation rate, ‖Δu‖, clearance, deadlock all reported | §6.6 |
| 3.6 | ROS 2 / Gazebo confirmation run (optional but decisive for scope) | P2 | 5 d | 3.4 | qualitative + quantitative appendix | ≥2 team sizes, ≥5 runs each | Appendix |
| 3.7 | Failure taxonomy + Fig. 11 | P1 | 2 d | 2.9 | Fig. 11 | four distinct labelled failure modes | §6.9 |
| 3.8 | Release repository, seeds, logs, checkpoints | P0 | 2 d | all | public URL | a clean clone reproduces Table 3 | §5 |

## Stage 4 — Optional

Physical-robot demonstration (TurtleBot3 ×4, the ROS 2 stack already targets this); heterogeneous speed limits; richer dynamic obstacles; formal analysis of the mode-switching automaton (dwell-time stability is the tractable target, *not* reachability).

**Critical path:** 2.1 → 2.2 → 2.13 → 2.9 → 3.1 / 3.3. Nothing in Stage 3 is meaningful before 2.1 and 2.2 land, because every current number is computed under a broken safety metric.

---

# PART 20 — SPECIAL QUESTIONS AND FINAL READINESS CHECKLIST

## 20.1 The twenty required answers

1. **Why was the paper likely rejected before external review?** Because the first two pages promise a decentralized, recoverability-aware, resilient controller and the first two tables show a 31.5 %-success method beating a self-declared proxy for ORCA by 0.310 in a self-favouring capability matrix. An editor needs no reviewer to see the mismatch between claim strength and evidence strength.

2. **Which visible element most likely harmed editor confidence?** Table 1 — the checkmark positioning table where the proposed method receives ✓ in all seven columns against nine published works. It is the first table, it is unverifiable, and it signals advocacy rather than analysis. The runner-up is the ORCA row of Table 3 (success 0.005).

3. **Is the central novelty understandable from the title and abstract?** No. The submitted title names an undefined property ("recoverability") applied to an undefined mechanism ("topology control"); the abstract lists five module outputs without identifying which one is the contribution. The revised abstract is worse in one respect — "First…, Second…, Third…" enumerates a pipeline rather than stating a finding.

4. **Is the technical advance over a topology-agnostic GNN clear?** No — and the paper's own ablation says there is very little: `−Topology` scores 0.312 against 0.315, and the GNN baseline scores 0.310. The advance is 0.005 in success and negative in formation satisfaction.

5. **Are the current named baselines scientifically fair?** No. Three of the four external names describe implementations that are not those algorithms, by the paper's own admission in §5.2.

6. **Can the paper currently claim superiority over ORCA?** **No.** The evaluated "ORCA" is goal attraction plus repulsion. Even with the RVO2 implementation now in the repository, ORCA optimizes collision-free velocity and has no formation objective, so superiority may be claimed only on jointly-defined task metrics with that asymmetry stated.

7. **Over CBF-QP?** **No.** The evaluated variant is the expert action plus repulsion. The repository's genuine per-robot CBF-QP has never been run into a table.

8. **Over MPC?** **No** — twice over. The evaluated variant was expert + centroid bias, and the current replacement is a beam search over five discrete modes with horizon 1–2, which is not model predictive control of the control input.

9. **Can the paper claim statistical superiority over the GNN baseline?** **No.** One training seed, no interval, a 0.005 margin, and 2.5× the checkpoint-selection budget for the proposed method.

10. **Does the ablation show topology selection is necessary?** **No — it shows the opposite.** Removing it costs 0.003 success and *gains* 0.006 formation satisfaction.

11. **Does the ablation show the safety filter is necessary?** **No.** Removing it costs 0.003 success and 0.002 collision-free; its only clear effect is on collapse (0.430 → 0.468), a metric that is itself largely a function of deadlock.

12. **Does the current recovery score justify the word "recoverability"?** **No.** It is a horizon-averaged, hand-weighted shaped return of a heuristic expert — a value function under a designed reward. There is no set-membership meaning, no probability, no calibration, and no comparison against realized outcomes.

13. **Is the method truly decentralized?** **No.** In the evaluated configuration the whole team is one graph, and mode, score, uncertainty, and context are read from a mean pool over all robots. The ROS 2 node does run per-robot, but it is never evaluated and has no mechanism to resolve disagreement.

14. **Are the absolute success and collision-free rates strong enough for the title?** **No.** Best success 0.315, best collision-free 0.488, best collapse 0.430. No vocabulary containing *resilient*, *safe*, or *robust* is defensible at those levels — and the collision-free figure is not even measuring what the paper says it measures.

15. **What title most accurately describes the current evidence?** *"Rollout-Ranked Mode Selection for Formation Navigation in Clutter: A Simulation Study."* If the calibration study is completed: *"Predicting Short-Horizon Formation Recovery for Mode Selection in Multi-Robot Navigation."*

16. **Which single new experiment most improves prescreen acceptance probability?** **The recovery-score calibration study (Part 10).** It converts the paper's central concept from an unfalsifiable label into a measured quantity, it is cheap relative to retraining, it produces a figure an editor can evaluate in five seconds, and it is the only experiment that makes the title legitimate. *(Strictly, fixing the episode-wide metric is more urgent — but that is a bug fix, not an experiment.)*

17. **Which three experiments are mandatory before resubmission elsewhere?** (i) Full benchmark re-run under corrected episode-wide safety metrics and corrected collision geometry, with faithful baselines; (ii) ≥5 independent training seeds with matched budgets and paired statistics; (iii) the recovery-score calibration study. Held-out generalization is a very close fourth.

18. **Which components should be removed for clarity?** The uncertainty head; the auxiliary head; hard-negative mining; eight of the ten lexicographic tie-break levels; the `compress`/`recover` latent modes the learner never scores; the ROS 2 element of Fig. 3; the capability checkmark table; both 12-column trajectory grids.

19. **Which claim should become the central claim?** *A graph controller can predict, per candidate formation mode, the probability of short-horizon recovery — collision-free progress with return to a formation tube — and this prediction is calibrated and useful for mode selection.*

20. **Best realistic venue after major revision?** **IEEE RA-L**, with IROS as the parallel target. Both reward a single sharp, falsifiable claim with a calibration study, and RA-L's 8-page limit enforces the scope discipline this work needs. Do not resubmit to IEEE Access.

## 20.2 Final prescreen readiness checklist

| Requirement | Current status | Required evidence | Action | Completion criterion | Priority |
|---|---|---|---|---|---|
| Safety metric measures the episode | **FAIL** — terminal step only, verified by execution | episode-wide accumulator + unit test | fix `evaluate.py`, re-run everything | mid-episode contact ⇒ `CollisionFree = 0` | **P0** |
| Collision thresholds physically consistent | **FAIL** — resolver leaves pairs inside the threshold; commanded spacing equals the threshold | corrected config + regression test | fix `config.py`, cap `min_scale` | post-resolution separation > threshold | **P0** |
| Baselines faithful or honestly named | **FAIL** | fidelity table with verdicts | re-run with RVO2 / CBF-QP / rename MPC | Table 2 complete | **P0** |
| ≥5 independent training seeds | **FAIL** — 1 | per-seed results | 25 training runs | mean ± SD + CI in every cell | **P0** |
| Equal training and selection budget | **FAIL** — 300 vs 120 epochs | config diff | equalize | identical E, I, top-k | **P0** |
| Model selection off the test distribution | **FAIL** | held-out split manifests | new validation split | zero generator overlap | **P0** |
| Paired statistics + multiplicity control | **FAIL** — none | bootstrap/Wilcoxon/Holm | reporting pipeline | every comparison has a CI | **P0** |
| Randomized starts and goals | **FAIL** — deterministic, verified | new generator | implement | starts differ across seeds | **P0** |
| Recovery score calibrated | **FAIL** — no calibration | reliability, ECE, Brier, AUROC | run Part 10 | AUROC ≥ 0.75, ECE ≤ 0.10, beats all heuristics | **P0** |
| Decentralization claim evidenced | **FAIL** — centralized in practice | agreement + comms study, or a corrected claim | run Part 11 or delete the word | agreement ≥ 0.9 at 0 % loss | **P0** |
| Isolated (non-compound) ablations | **FAIL** — two variants are the same at the selector | 17-variant table | run Part 8.4 | each row changes exactly one thing | **P0** |
| Held-out generalization axis | **FAIL** — none exists | unseen layout + unseen N | run E4 | both reported for all methods | **P0** |
| ≤3 contributions, each with a named experiment | **FAIL** — 4, two unsupported | new list | rewrite | each cites a results subsection | P1 |
| Terminology licensed by evidence | **FAIL** | terminology pass | rewrite | no banned term without evidence | P1 |
| Neutral related-work table | **FAIL** — self-favouring ✓ matrix | objective columns | rewrite | no ours-row sweep | P1 |
| Metric definitions match code | **FAIL** | text audit | rewrite + fix | text and code agree line by line | P1 |
| Absolute performance supports the vocabulary | **FAIL** — 0.315 success | post-fix results | re-run, then re-word | vocabulary matches the numbers | P1 |
| Runtime measured correctly | **FAIL** — includes checkpoint I/O | preloaded timing | fix | stable across repeats | P1 |
| Figures readable and scientific | **FAIL** | new figure set | redraw | readable at print size; no decorative teaser | P1 |
| Template residue removed | **FAIL** — `xxxx` DOI/date | clean PDF | fix | no placeholders | P1 |
| Reproducibility package released | **FAIL** | public repo + seeds + logs | release | clean clone reproduces Table 3 | P1 |
| Limitations specific and complete | **PARTIAL** | 12-item list | rewrite | every claim has its stated boundary | P2 |
| Safety layer correctly named | **FAIL** — "safety filter" for a blended projection | correct terminology | rewrite | "decoupled discrete-time CBF-QP projection with blending" | P2 |
| ROS 2 claim evidenced or removed | **FAIL** — figure promises, paper delivers nothing | Gazebo results or figure edit | choose one | no unbacked claim in any figure | P2 |

**Bottom line.** Eleven **P0** items currently fail, and two of them (episode-wide safety accounting and collision-threshold geometry) invalidate every number in the paper. The correct sequence is: repair the benchmark, regenerate all evidence, then decide what the paper is about based on what the corrected evidence shows — not before.
