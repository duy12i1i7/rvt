# Phase 6 Open Translation Report

The frozen translation matrix contains 180 episodes: six team sizes, three
forced topologies, two geometrically equivalent headings and five predeclared
seeds. All initial conditions were valid without resampling. Every heading cell
achieved collision-free rate, goal-reaching rate and final Metric V3 dwell rate
of 1.00, with no deadlock, numerical failure, infeasible projection or solver
failure.

The topology origin was displaced by 3.6 m. Every episode completed the goal
and dwell condition at 4.80 s. Across the matrix, the largest final formation
error was 0.0088 m, largest final goal-origin error was 0.0783 m, and minimum
robot-robot center distance was 0.6768 m. Heading 0 and heading pi/3 therefore
both pass; no controller quantity depends on a privileged world axis.

`CF`, `Goal`, `Dwell` and `Dead` are rates. `Efinal` and `Gerr` are the worst
values among the five seeds; `dmin` is the minimum center distance. `Sat` and
`Proj` are mean percentages of controller calls and are equal here because the
only intervention was physical acceleration-bound projection during initial
translation. Exact episode values are in
`results/phase6_forced_topology/open_translation/episodes.{json,csv}`.

| N | Topology | Heading | n | CF | Goal | Dwell | Dead | Efinal (m) | Gerr (m) | dmin (m) | Sat (%) | Proj (%) | done (s) | lat (ms) |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 5 | KEEP | 0.0000 | 5 | 1.00 | 1.00 | 1.00 | 0.00 | 0.0018 | 0.0764 | 0.8150 | 1.00 | 1.00 | 4.80 | 0.483 |
| 5 | KEEP | 1.0472 | 5 | 1.00 | 1.00 | 1.00 | 0.00 | 0.0025 | 0.0774 | 0.7702 | 1.05 | 1.05 | 4.80 | 0.483 |
| 5 | COMPACT | 0.0000 | 5 | 1.00 | 1.00 | 1.00 | 0.00 | 0.0019 | 0.0767 | 0.7187 | 1.05 | 1.05 | 4.80 | 0.479 |
| 5 | COMPACT | 1.0472 | 5 | 1.00 | 1.00 | 1.00 | 0.00 | 0.0023 | 0.0779 | 0.8036 | 1.05 | 1.05 | 4.80 | 0.477 |
| 5 | LINE | 0.0000 | 5 | 1.00 | 1.00 | 1.00 | 0.00 | 0.0037 | 0.0771 | 0.7712 | 1.00 | 1.00 | 4.80 | 0.474 |
| 5 | LINE | 1.0472 | 5 | 1.00 | 1.00 | 1.00 | 0.00 | 0.0030 | 0.0783 | 0.8122 | 1.00 | 1.00 | 4.80 | 0.476 |
| 6 | KEEP | 0.0000 | 5 | 1.00 | 1.00 | 1.00 | 0.00 | 0.0014 | 0.0763 | 0.7918 | 1.08 | 1.08 | 4.80 | 0.548 |
| 6 | KEEP | 1.0472 | 5 | 1.00 | 1.00 | 1.00 | 0.00 | 0.0016 | 0.0770 | 0.7735 | 1.08 | 1.08 | 4.80 | 0.548 |
| 6 | COMPACT | 0.0000 | 5 | 1.00 | 1.00 | 1.00 | 0.00 | 0.0022 | 0.0756 | 0.7694 | 1.08 | 1.08 | 4.80 | 0.546 |
| 6 | COMPACT | 1.0472 | 5 | 1.00 | 1.00 | 1.00 | 0.00 | 0.0020 | 0.0766 | 0.7624 | 0.96 | 0.96 | 4.80 | 0.550 |
| 6 | LINE | 0.0000 | 5 | 1.00 | 1.00 | 1.00 | 0.00 | 0.0038 | 0.0760 | 0.7629 | 1.12 | 1.12 | 4.80 | 0.520 |
| 6 | LINE | 1.0472 | 5 | 1.00 | 1.00 | 1.00 | 0.00 | 0.0052 | 0.0770 | 0.7617 | 1.12 | 1.12 | 4.80 | 0.523 |
| 8 | KEEP | 0.0000 | 5 | 1.00 | 1.00 | 1.00 | 0.00 | 0.0032 | 0.0764 | 0.6923 | 0.97 | 0.97 | 4.80 | 0.710 |
| 8 | KEEP | 1.0472 | 5 | 1.00 | 1.00 | 1.00 | 0.00 | 0.0025 | 0.0758 | 0.7476 | 0.94 | 0.94 | 4.80 | 0.705 |
| 8 | COMPACT | 0.0000 | 5 | 1.00 | 1.00 | 1.00 | 0.00 | 0.0035 | 0.0761 | 0.7556 | 0.84 | 0.84 | 4.80 | 0.702 |
| 8 | COMPACT | 1.0472 | 5 | 1.00 | 1.00 | 1.00 | 0.00 | 0.0041 | 0.0768 | 0.7264 | 0.88 | 0.88 | 4.80 | 0.709 |
| 8 | LINE | 0.0000 | 5 | 1.00 | 1.00 | 1.00 | 0.00 | 0.0040 | 0.0757 | 0.7323 | 0.97 | 0.97 | 4.80 | 0.599 |
| 8 | LINE | 1.0472 | 5 | 1.00 | 1.00 | 1.00 | 0.00 | 0.0043 | 0.0762 | 0.7266 | 1.06 | 1.06 | 4.80 | 0.598 |
| 12 | KEEP | 0.0000 | 5 | 1.00 | 1.00 | 1.00 | 0.00 | 0.0040 | 0.0761 | 0.7132 | 0.85 | 0.85 | 4.80 | 1.072 |
| 12 | KEEP | 1.0472 | 5 | 1.00 | 1.00 | 1.00 | 0.00 | 0.0026 | 0.0754 | 0.7376 | 1.00 | 1.00 | 4.80 | 1.078 |
| 12 | COMPACT | 0.0000 | 5 | 1.00 | 1.00 | 1.00 | 0.00 | 0.0079 | 0.0756 | 0.7236 | 0.83 | 0.83 | 4.80 | 0.999 |
| 12 | COMPACT | 1.0472 | 5 | 1.00 | 1.00 | 1.00 | 0.00 | 0.0088 | 0.0748 | 0.7312 | 0.90 | 0.90 | 4.80 | 1.010 |
| 12 | LINE | 0.0000 | 5 | 1.00 | 1.00 | 1.00 | 0.00 | 0.0071 | 0.0760 | 0.7464 | 0.92 | 0.92 | 4.80 | 0.751 |
| 12 | LINE | 1.0472 | 5 | 1.00 | 1.00 | 1.00 | 0.00 | 0.0075 | 0.0750 | 0.7590 | 0.98 | 0.98 | 4.80 | 0.748 |
| 16 | KEEP | 0.0000 | 5 | 1.00 | 1.00 | 1.00 | 0.00 | 0.0052 | 0.0753 | 0.7288 | 0.80 | 0.80 | 4.80 | 1.513 |
| 16 | KEEP | 1.0472 | 5 | 1.00 | 1.00 | 1.00 | 0.00 | 0.0066 | 0.0751 | 0.7201 | 0.88 | 0.88 | 4.80 | 1.497 |
| 16 | COMPACT | 0.0000 | 5 | 1.00 | 1.00 | 1.00 | 0.00 | 0.0077 | 0.0748 | 0.7182 | 0.81 | 0.81 | 4.80 | 1.212 |
| 16 | COMPACT | 1.0472 | 5 | 1.00 | 1.00 | 1.00 | 0.00 | 0.0056 | 0.0747 | 0.7341 | 0.81 | 0.81 | 4.80 | 1.209 |
| 16 | LINE | 0.0000 | 5 | 1.00 | 1.00 | 1.00 | 0.00 | 0.0073 | 0.0749 | 0.7443 | 0.81 | 0.81 | 4.80 | 0.859 |
| 16 | LINE | 1.0472 | 5 | 1.00 | 1.00 | 1.00 | 0.00 | 0.0083 | 0.0744 | 0.7872 | 0.84 | 0.84 | 4.80 | 0.860 |
| 24 | KEEP | 0.0000 | 5 | 1.00 | 1.00 | 1.00 | 0.00 | 0.0077 | 0.0754 | 0.7627 | 1.02 | 1.02 | 4.80 | 2.394 |
| 24 | KEEP | 1.0472 | 5 | 1.00 | 1.00 | 1.00 | 0.00 | 0.0057 | 0.0761 | 0.7417 | 1.07 | 1.07 | 4.80 | 2.391 |
| 24 | COMPACT | 0.0000 | 5 | 1.00 | 1.00 | 1.00 | 0.00 | 0.0048 | 0.0755 | 0.7289 | 0.99 | 0.99 | 4.80 | 1.562 |
| 24 | COMPACT | 1.0472 | 5 | 1.00 | 1.00 | 1.00 | 0.00 | 0.0067 | 0.0757 | 0.6768 | 1.05 | 1.05 | 4.80 | 1.554 |
| 24 | LINE | 0.0000 | 5 | 1.00 | 1.00 | 1.00 | 0.00 | 0.0066 | 0.0754 | 0.7371 | 0.97 | 0.97 | 4.80 | 1.092 |
| 24 | LINE | 1.0472 | 5 | 1.00 | 1.00 | 1.00 | 0.00 | 0.0080 | 0.0757 | 0.7200 | 1.05 | 1.05 | 4.80 | 1.028 |

The evaluator computes goal-origin error centrally only after each local action
has been produced. That offline metric is not an input to any controller call.
These results qualify fixed-topology open-space translation, not online
topology transitions or corridor passage.
