# Epoch Churn Qualification (Task 5-7)

Fixture B, N = 6, 5 seeds, geometric event-triggered policy.

## Predeclared targets vs measured

| target | required | measured | verdict |
|---|---|---|---|
| successful epochs per traversal | exactly 2 | **2** (1 K→L, 1 L→K) | **PASS** |
| failed / retry epochs | ≤ 1 | ~1.4 | marginal |
| no-op epochs | 0 | **4.6** | **FAIL** |
| median total epochs | ≤ 3 | **8** | **FAIL** |

## Progression

| stage | epochs/episode | no-ops | protocol bytes/episode |
|---|---|---|---|
| Task 4R baseline | 16.2 | 13.4 | 100 685 |
| + no-op guard (post-score) | 16.2 | 13.4 | 77 107 |
| + passage latch | 15.6 | 12.8 | 74 746 |
| + narrowed entry reasons | 8.6 | 5.8 | 41 880 |
| + local no-op pre-arm check | **8.0** | **4.6** | **37 726** |

**Protocol traffic is down 63 %** (100 685 → 37 726 bytes/episode) and the
successful-transition count is now exactly the ideal 2. On the open-field
fixture the policy now opens **0 epochs**, so unnecessary transitions in open
space are eliminated entirely.

## Why the count target still fails

The residual epochs are **genuine disagreements, not churn**. An epoch opens
when *any* robot arms; the pre-arm check only prevents a robot from proposing
what it already holds. When one robot's clearance is tight and another's is not,
the first legitimately arms, the epoch runs, consensus resolves to no change,
and the no-op guard skips confirmation.

Eliminating these would need a local quorum before arming — a protocol change
requiring peer trigger counts, with its own predeclaration. It is **not**
attempted here, because tuning the trigger further to hit a churn number after
seeing the results is exactly the practice this project forbids.

Reported as a **FAIL against the predeclared target**, not rationalised away.
