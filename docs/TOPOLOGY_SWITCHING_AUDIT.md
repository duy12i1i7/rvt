# Topology Switching Audit (Task 3)

Are the switches useful adaptations or selector chattering?

Raw data: [`../results/method_audit/topology_switching.csv`](../results/method_audit/topology_switching.csv)
Script: `scripts/audit_safety_and_topology.py` · Benchmark tag: `benchmark-protocol-v2-smoke`

**Validation split only** (open_field + narrow_passage, N ∈ {5, 11}, 8 episodes
per cell = 32 episodes, 3 606 control steps). Dwell and hysteresis grids were
**predeclared in the script**. No final-test data was used.

Model: `checkpoints/method_audit/rvt_swarm.pt`, 30 epochs, validation-selected.

---

## 1. The answer is neither

The audit was designed to distinguish *useful adaptation* from *chattering*. The
trained model does neither:

```
switches 0 over 3606 steps (rate 0.000)
dwell mean=nan  median=nan  p10=nan
reversal within 1/2/5/10 steps: 0.000 / 0.000 / 0.000 / 0.000
switches while filter active: 0.000
transition matrix: {}
```

**The trained model never switches topology on any validation episode.** Every
downstream diagnostic the task asked for — dwell-time distribution, transition
matrix, reversal rates, progress/formation/risk deltas around switches, tie-break
attribution, uncertainty attribution — is undefined, because the sample is empty.
They are reported as such rather than fabricated.

### This contradicts the smoke benchmark, and the smoke number was the artifact

| | smoke model (6 epochs) | audit model (30 epochs) |
|---|---|---|
| Switches per 120-step episode, narrow passage | 12.7 – 14.0 | **0.00** |

A 6-epoch score head emits near-arbitrary per-mode scores, so the selector churns.
A 30-epoch score head consistently ranks `keep` highest, and the selector's
persistence rule (`safety.py:504-511`) then holds it there. Smoke anomaly 8.2.2 is
retired as a model-maturity artifact.

## 2. Selector variants (predeclared grid)

| Variant | Success | Coll-free | Goal | Time-in-tube | Switches | Deadlock |
|---|---|---|---|---|---|---|
| 1. fixed topology (always KEEP) | **0.312** | **0.750** | **0.406** | **0.447** | 0.00 | **0.062** |
| 2. argmax topology logits | **0.312** | **0.750** | **0.406** | **0.447** | 0.00 | **0.062** |
| 3. argmax score | 0.250 | 0.750 | 0.375 | 0.428 | 0.09 | 0.094 |
| 4. lexicographic (shipped) | **0.312** | **0.750** | **0.406** | **0.447** | 0.00 | **0.062** |
| 5. min dwell 3 / 5 / 10 | 0.312 | 0.750 | 0.406 | 0.447 | 0.00 | 0.062 |
| 6. hysteresis 0.05 / 0.10 / 0.25 | 0.312 | 0.750 | 0.406 | 0.447 | 0.00 | 0.062 |
| 7. no uncertainty adjustment | **0.312** | **0.750** | **0.406** | **0.447** | 0.03 | **0.062** |

**Fixed topology is indistinguishable from the shipped selector on every metric.**
So are the logit argmax, all three dwell settings, and all three hysteresis
settings — because none of them ever fires.

The only variant that differs is **argmax-score**, which bypasses the persistence
rule and the `score ≥ 0` pre-filter: it produces 0.09 switches/episode and is
*worse* (success 0.250 vs 0.312, deadlock 0.094 vs 0.062). Note this is a
1–2 episode difference on 32 episodes and should not be over-read; what it does
show is that the switches the learned ranking *would* make are not beneficial.

Dwell and hysteresis are therefore **untestable at this scale**: they can only
suppress switches, and there are none to suppress. No value is selected from
either grid.

## 3. Decision rules applied

| Rule | Applies? | Consequence |
|---|---|---|
| "If switching does not produce measurable local improvement, remove topology switching as a primary contribution" | **Yes** — zero switches; the only switching variant is worse | **Remove topology switching as a primary contribution** |
| "If fixed topology performs comparably, do not keep *Topology Control* in the title" | **Yes** — fixed topology is *identical*, not merely comparable | **"Topology Control" cannot appear in the title** |
| "If most switches reverse rapidly, classify the selector as chattering" | Not applicable — no switches with a trained model | The smoke run's churn was an undertrained-model artifact, not a selector property |
| "If uncertainty adjustment causes instability and lacks calibration, remove it" | **Yes** — it is uncalibrated (Task 5, ECE 0.19) and disabling it slightly *improves* ranking (Task 5: top-1 0.840 vs 0.827, Kendall 0.631 vs 0.596) | **Remove the uncertainty head** |

## 4. What this does and does not establish

**Establishes:** on these validation scenarios, at this scale, with this training
budget and one seed, the topology-selection mechanism is **inert** — it neither
helps nor hurts, because it never acts. A method whose named contribution never
activates cannot claim that contribution.

**Does not establish** that mode switching is useless in principle. Three
possibilities remain open, and the audit cannot separate them:

1. `keep` genuinely *is* the best mode almost always in these scenarios — which
   Task 5 partly supports: **always-keep achieves top-1 mode accuracy 0.827**
   against the empirical rollout outcomes, so switching has little headroom here.
2. The scenarios are too easy or too small (N ∈ {5, 11}; the smoke run's harder
   N=8 narrow-passage cells are a different regime).
3. The persistence rule plus the `score ≥ 0` pre-filter suppress switches that the
   learned ranking would otherwise make — supported by argmax-score producing
   0.09 switches/episode where the shipped selector produces 0.

**[REQUIRES NEW EXPERIMENT]** to separate these: a scenario family where the
rollout oracle demonstrably prefers `line`/`split` over `keep` on a substantial
fraction of states. If no such family exists in this benchmark, the mode set
itself is the problem, not the selector.

## 5. Limitations

One model seed, 32 validation episodes, two scenario families, N ∈ {5, 11}. A
difference of one episode is 0.031, so every non-zero gap in §2 is within noise.
The zero-switch result is not a noise-level claim — it is exactly zero across
3 606 steps — but it is specific to this model and these scenarios.
