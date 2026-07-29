# Baseline Fidelity and Reference Semantics — v3

Supersedes `BASELINE_FIDELITY_V2.md`. Adds the fixed-mode references and the
rollout oracle used in scenario qualification, and sorts every reference into one
of three classes that must never be mixed in a table.

**No baseline implementation was changed to affect any ranking.**

## 1. Three classes, kept visually separate in every table

| Class | Meaning | May be compared against the method? |
|---|---|---|
| **Deployable** | runs from information a robot could actually have | **Yes** |
| **Oracle upper bound** | uses privileged state and/or forward simulation | **No** — reports headroom, never a competitor |
| **Internal diagnostic** | a probe, not a method | **No** |

## 2. The references

### Deployable

| Name | What it is | Topology metric |
|---|---|---|
| `fixed_formation_expert` | shared heuristic controller, mode pinned to KEEP. The imitation target of every learned method, so it is both floor and ceiling for behaviour cloning. **Mandatory in every table.** | **N/A** |
| Formation-aware ORCA (RVO2) | genuine reciprocal velocity obstacles; **preferred velocity supplied by the formation expert** under a heuristic mode | **N/A** |
| Decoupled discrete-time CBF-QP | exact per-robot 2-D QP over CBF half-planes, KEEP-expert nominal, non-reciprocal | **N/A** |
| Heuristic mode selection | `_heuristic_topology` + expert; a hand rule, not the published Deng et al. algorithm | **Yes** |
| `gnn_topology_agnostic` | shared encoder, action head only | **N/A** |
| `direct_topology_classifier` | action bank + hard best-mode CE; the natural comparison for a ranking head | **Yes** |
| `rvt_simple_rank` | simplified model (Task 1) | **Yes** |
| `rvt_full_legacy` | the five-head legacy model, unchanged | **Yes** |

### Fixed-mode references (deployable, and new in v3)

`always_keep`, `always_line`, `always_split` — the expert with the mode pinned for
the whole episode. They are deployable (no privileged information) and they
bracket what any selector can achieve without switching.

`always_keep` is the **decisive** comparison for this line of work: the Method
Audit found it achieves top-1 mode accuracy 0.827 against realised rollout
outcomes, so any selector must beat it to justify existing.

### Oracle upper bounds — never deployable

| Name | Privileged information used |
|---|---|
| `best_fixed_mode` (per episode) | the outcome of every mode on **that** episode, chosen after the fact |
| `rollout_oracle` (per decision) | clones the simulator and forward-simulates `H` steps for every candidate mode, every replan step |

Reporting rules, binding:

- always labelled **"oracle upper bound — privileged simulator state"**;
- never placed in the same table block as deployable methods;
- **never** described as a method the proposed approach "beats" or "approaches";
- the quantity of interest is the **gap** between them and a deployable selector,
  which is the headroom available to be won.

### Internal diagnostic

`instant_cert` (scalar recovery head) — retained for continuity with the legacy
results; not a method and not a published algorithm.

## 3. Topology-metric applicability

Unchanged from v2 and still binding: methods with no explicit topology selector
report **`N/A`**, never `0`. Zero asserts "chose not to switch"; N/A states the
quantity is undefined. This applies to `fixed_formation_expert`, ORCA, CBF-QP,
`gnn_topology_agnostic`, and the fixed-mode references — for the fixed-mode
references the switch count is *trivially* zero by construction, which is
information-free and must be shown as `N/A (fixed by construction)`.

## 4. Formation-aware ORCA — the favourability statement, restated

Its preferred velocity comes from the formation expert. That is **materially
favourable** to ORCA on formation-conditioned metrics, because plain ORCA has no
formation objective and would score near zero on them. Consequently:

> No claim of the form "we outperform ORCA" is supported by this configuration.
> It measures *the formation expert with ORCA as its collision-avoidance layer.*

## 5. What v3 changes relative to v2

1. Adds the three fixed-mode references as first-class deployable baselines.
2. Adds the two oracle upper bounds, with explicit non-competitor rules.
3. Introduces the three-class separation.
4. Registers the new model variants from Task 1.
5. Extends the N/A rule to fixed-mode references, whose zero switch count is
   information-free.

Nothing was re-implemented, re-tuned, or removed.
