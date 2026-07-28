# Baseline Fidelity and Reporting Semantics — v2

Task 4. Corrects how baselines are *named* and how topology-switch metrics are
*attributed*. **No baseline implementation was changed.** Nothing here alters any
method's behaviour or improves RVT-Swarm's ranking.

## 1. The reporting defect

The smoke report showed `orca` with 0.27–1.00 topology switches per episode.
ORCA has no topology mechanism. The switches come from `_heuristic_topology(obs)`
(`baselines.py:40`), which the ORCA wrapper calls to build the **preferred
velocity** it hands to RVO2 (`baselines.py:85-90`), and which the environment
then applies as the active formation mode.

Two things were wrong:

1. **The metric was attributed to the wrong component.** Those switches are the
   heuristic reference generator's, not ORCA's.
2. **The configuration was under-described.** Calling it "ORCA" hides that its
   preferred velocity is produced by the formation expert — which is a *material*
   and *favourable* configuration choice.

## 2. Topology-metric applicability, per method

| Method | Explicitly selects a topology? | Topology only for a nominal reference? | Learned selector? | Topology-switch metric applicable? |
|---|---|---|---|---|
| `fixed_formation_expert` | No — pinned to KEEP | No | No | **N/A** (constant by construction) |
| `adaptive_formation` | **Yes** — `_heuristic_topology` | No | No (hand rule) | **Yes** |
| Formation-aware ORCA (`orca`) | No | **Yes** — only to form the preferred velocity | No | **N/A** |
| `cbf_qp` | No — nominal is KEEP-expert | Yes (KEEP only, never varies) | No | **N/A** |
| Centralized predictive mode search (`centralized_mpc`) | **Yes** — beam search over modes | No | No (exact-model search) | **Yes** |
| `gnn_only` | No — executes KEEP | No | No | **N/A** |
| `instant_cert` | No — executes KEEP | No | No | **N/A** |
| `rvt_swarm` | **Yes** | No | **Yes** | **Yes** |

**Reporting rules now in force**

- Methods marked N/A must print **`N/A`**, never `0` or `0.000`. Zero asserts
  "this method chose not to switch"; N/A states "the quantity is undefined here".
  The smoke report's `0.00` entries for the expert, `gnn_only` and `cbf_qp` were
  wrong in exactly this way, and its non-zero ORCA entries were wrong in the
  opposite way.
- Any table containing a topology column must carry this applicability legend.

## 3. Honest baseline names

| Old name | Corrected name | Why |
|---|---|---|
| ORCA | **Formation-aware ORCA (RVO2)** | preferred velocity comes from the formation expert under a heuristic mode; plain ORCA would use goal-directed preferred velocity with no formation term |
| CBF-QP | **Decoupled discrete-time CBF-QP (KEEP-expert nominal)** | genuine per-robot QP, but non-reciprocal and wrapped around the expert |
| Centralized MPC | **Centralized predictive mode search (exact-model)** | optimises a *mode sequence*, not a control trajectory |
| Adaptive Formation | **Heuristic mode selection (internal)** | internal hand rule, not the published Deng et al. algorithm |
| InstantCert | **Scalar recovery head (internal)** | no certificate, no Lipschitz value function, no reachability |

### Is Formation-aware ORCA favourable or unfavourable to ORCA?

**Favourable on safety, unfavourable on nothing, and materially favourable
overall — this must be stated wherever it is compared.**

- *Favourable:* ORCA receives a preferred velocity that already accounts for
  formation geometry and obstacle context. Plain ORCA has no formation objective
  at all and would score near zero on any formation metric, making the comparison
  meaningless. This configuration gives ORCA its best available showing on
  formation-conditioned metrics.
- *Not unfavourable:* RVO2 still performs its own reciprocal velocity-obstacle
  computation; nothing constrains or degrades it.
- *Consequence:* it is **not** evidence about ORCA-as-published. It is evidence
  about "the formation expert, with ORCA as the collision-avoidance layer". Any
  claim of the form "we outperform ORCA" is not supported by this configuration
  and must not be made.

## 4. Mandatory reference baselines

| Baseline | Status | Role |
|---|---|---|
| `fixed_formation_expert` | **implemented**, mandatory | The shared heuristic controller with topology pinned to KEEP. Every learned method is behaviour-cloned from it, so it is simultaneously the floor and the imitation ceiling. Absent from every pre-audit comparison; its smoke result (1.000 success in open_field N=4, where both learned methods scored ≈0) is the single most informative number produced so far. |
| Rollout oracle | **specified, not yet implemented** | See §5. |

## 5. Rollout oracle — feasibility assessment

**Verdict: implementable as an oracle upper bound, and it must be labelled as
one.** It cannot be a deployable method.

The mode selected at each step would be `argmax_τ rollout_score(env, τ, H, cfg)`
(`recoverability.py:45`). That call **clones the simulator and executes H future
steps** (`recoverability.py:28-42`), so it uses information no robot can have:
privileged full state, and forward simulation of the true dynamics.

Requirements if implemented:

- label it **"rollout oracle (upper bound — uses privileged simulator state)"**
  in every table and caption;
- never place it in the same block as deployable methods;
- state the cost (|T| × H simulator steps per control step);
- do **not** report it as a baseline that RVT-Swarm "beats" or "approaches" —
  it bounds what the *selector* could achieve given a perfect score, and the gap
  between it and RVT-Swarm is the quantity of interest.

It is not implemented in this audit because it is not needed to answer any Task
1–6 question, and adding a module was out of scope.

## 6. What this document does not do

- No baseline implementation was modified.
- No baseline was added or removed to change a ranking.
- No comparative claim is made anywhere in this document.
