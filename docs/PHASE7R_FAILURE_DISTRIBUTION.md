# Phase 7R Failure Distribution

The frozen Phase 7 matrix contains 144 episodes and 97 projection-abort episodes. Every failing action was rejected before that action was integrated. The complete per-episode matrix is in `results/phase7_transition_execution_repair/failure_matrix.json`.

| source | target | N | episodes | aborts | success |
|---|---|---|---|---|---|
| 0 | 2 | 12 | 4 | 4 | 0 |
| 0 | 2 | 16 | 4 | 4 | 0 |
| 0 | 2 | 24 | 4 | 4 | 0 |
| 0 | 2 | 5 | 4 | 0 | 4 |
| 0 | 2 | 6 | 4 | 1 | 3 |
| 0 | 2 | 8 | 4 | 3 | 1 |
| 0 | 5 | 12 | 4 | 4 | 0 |
| 0 | 5 | 16 | 4 | 4 | 0 |
| 0 | 5 | 24 | 4 | 4 | 0 |
| 0 | 5 | 5 | 4 | 4 | 0 |
| 0 | 5 | 6 | 4 | 4 | 0 |
| 0 | 5 | 8 | 4 | 4 | 0 |
| 2 | 0 | 12 | 4 | 4 | 0 |
| 2 | 0 | 16 | 4 | 4 | 0 |
| 2 | 0 | 24 | 4 | 4 | 0 |
| 2 | 0 | 5 | 4 | 4 | 0 |
| 2 | 0 | 6 | 4 | 0 | 4 |
| 2 | 0 | 8 | 4 | 4 | 0 |
| 2 | 5 | 12 | 4 | 0 | 4 |
| 2 | 5 | 16 | 4 | 0 | 4 |
| 2 | 5 | 24 | 4 | 0 | 4 |
| 2 | 5 | 5 | 4 | 0 | 4 |
| 2 | 5 | 6 | 4 | 0 | 4 |
| 2 | 5 | 8 | 4 | 0 | 4 |
| 5 | 0 | 12 | 4 | 4 | 0 |
| 5 | 0 | 16 | 4 | 0 | 4 |
| 5 | 0 | 24 | 4 | 4 | 0 |
| 5 | 0 | 5 | 4 | 4 | 0 |
| 5 | 0 | 6 | 4 | 4 | 0 |
| 5 | 0 | 8 | 4 | 4 | 0 |
| 5 | 2 | 12 | 4 | 4 | 0 |
| 5 | 2 | 16 | 4 | 4 | 0 |
| 5 | 2 | 24 | 4 | 4 | 0 |
| 5 | 2 | 5 | 4 | 1 | 3 |
| 5 | 2 | 6 | 4 | 0 | 4 |
| 5 | 2 | 8 | 4 | 4 | 0 |

## Concentration checks

| width class | episodes | aborts | success |
|---|---|---|---|
| narrowing | 72 | 57 | 15 |
| widening | 72 | 40 | 32 |

| fixture | episodes | aborts | success |
|---|---|---|---|
| bounded_source_perturbation | 36 | 25 | 11 |
| exact_source | 36 | 24 | 12 |
| rotated_mission | 36 | 24 | 12 |
| translated_mission | 36 | 24 | 12 |

First-abort role concentration, parity, N growth, graph degree, initial perturbation and rotation are serialized in `failure_distribution_summary.json`. All open-space episodes use the frozen path graph, so this matrix cannot attribute variation to graph family. No pooled count is used as a support claim.
