# Phase 8 Experiment Protocol Report

## Frozen Identity

- approved mechanical source: `d24a0f674c1e75df293e4524f020acc49d4e2f35`;
- online scope: `rvt-online-topology-scope/v1`, hash `bc65ec533c895a9ad82ef277e89998c772db3403d4177ec04d9dce375f0c7684`;
- experiment protocol: `rvt-experiment-protocol/v1`;
- protocol manifest hash: `0bb68dd56ef0837f83c44dcf5281498f8c0ea934b00bbb9b3d3f298264d32147`;
- scenario families: 10;
- candidates and graph: `(COMPACT,LINE)`, `COMPACT <-> LINE`;
- KEEP disposition: fixed baseline and historical diagnostic only.

## Splits

Train has 20 layouts, validation 10 and sealed final test 10. Train contains two
variants per family; validation and final contain one per family. Geometry and
canonical parameter hashes are disjoint across all splits.

| split | count | manifest SHA-256 |
|---|---:|---|
| train | 20 | `a2a7257ae09d244f21224bd89b18ba32f7cd1457627f54d3b898cc83be2e9a35` |
| validation | 10 | `cff73ce294f16f557af783fbabee20cd89a2f929878f7b80122265f481c58d7f` |
| final test, sealed | 10 | `e225a3114dfb2d74e8a691f24484898de1481a6f8f243bcc3eabbfba5aff8d0f` |

Permitted final metadata only: each F1-F10 has one layout; each
`N={5,6,8,12,16,24}` has 10 layout cells. No geometry parameter, seed or
headroom detail is exposed here. Successful final-test runtime accesses: 0.

Train diagnostic headroom is 1 COMPACT-only, 6 LINE-only, 7 both-success, 2
both-fail and 4 reconfiguration-required layouts. Validation is respectively
1, 3, 3, 1 and 2. These are frozen diagnostic-policy assignments, not learned
labels.

## Targets and Learning Protocol

Recoverability V4 is candidate-specific all-success task recovery over complete
matched rollouts. Collision, deadlock, commitment, transition execution, Metric
V3 dwell, goal, protocol, safety projection, numerical validity and irreversible
progress are all required. Deterministic cases use one replica; stochastic F8/F9
use three matched replicas with all-success aggregation.

Residual expert choice is Option B,
`B_FROZEN_COUNTERFACTUAL_LOCAL_ACTION_SEARCH_V1`: a fixed robot-local action
search using normalized progress, clearance, formation error and action
deviation. Targets are clipped world-frame acceleration differences within
`[-0.15,0.15] m/s2` per component.

Loss is BCE-with-logits plus Smooth L1 residual, residual-magnitude regularizer
and initially disabled local consistency. No class weighting is permitted before
the label audit. AdamW search is capped at 12 configurations, 50,000 steps and
three model seeds. Checkpoints are validation-selected lexicographically after a
collision constraint; training loss and zero-shot N24 are ineligible selectors.

Study A trains on `N={5,6,8,12,16}` and evaluates frozen checkpoints zero-shot
at N24. Study B separately includes N24 and cannot support a zero-shot claim.

## Baselines, Metrics and Statistics

The frozen baseline set contains three fixed baselines/references, six
deployable selector/full-method configurations and three non-deployable
diagnostic references. Comparable learned baselines receive matched data,
capacity, seeds, steps, tuning and checkpoint opportunities.

Primary episode metrics are task success, collision-free status, final dwell,
required transition sequence, deadlock and completion time. Recoverability,
control, communication and scaling metrics are secondary declared families.
Paired episode bootstrap uses 10,000 resamples and 95% intervals; McNemar and
paired permutation/Wilcoxon tests use Holm correction across six primary
comparisons.

Practical gates require H1 gain 0.08, H2 gain 0.10, collision degradation at
most 0.01, centralized retention at least 0.85, at most 500,000 bytes per robot
per transition, inference within 15 ms, positive effect in at least two of three
seeds and no family/N contributing over half the gain.

## Tiny Diagnostic

The fixed train/validation budget used 8 decisions, 16 candidate traces and 16
action targets. Each candidate produced 4 positive and 4 negative labels; all
four joint categories occurred twice. Invalid/unstable/matching failures were
zero. Residual targets were 16/16 finite and safety-compatible, 12/16 non-zero
and 4/16 saturated. Both candidates, both committed topologies, both transition
directions and five roles were represented.

This validates target plumbing and numerical non-vacuity only. It is not a full
dataset, trained-model result or scenario-performance claim.

## Acceptance Gates

P8-G1 through P8-G11 pass: questions/hypotheses, scenario coverage, split
disjointness, final-test sealing, target semantics, local residual expert,
non-vacuity, loss/tuning/checkpoint freeze, provenance, baseline fairness and
episode-level statistics are executable and versioned. P8-G12 passes with no
full dataset, model training, DAgger or final-test result.

The implementation adds 63 Phase 8 tests to the approved 1,889-test baseline.
Final clean-checkout audit: 1,952 passed; the pre-existing PyTorch warning is
unchanged.

## Phase 9 Conditions

Phase 9 may generate only train/validation data under the exact protocol hash.
It must run the full label audit before class weighting or training, preserve
Study A's N24 exclusion, pass residual-target validity at full diagnostic scale,
and keep final-test access at zero. A failed non-vacuity/provenance gate blocks
training and does not authorize mechanical or scenario retuning.

## Verdict

**C. The scientific protocol is frozen and valid; proceed to Phase 9 dataset
generation and label audit.**
