# RVT Practical-Significance Gates

Schema: `rvt-practical-significance/v1`.

| gate | threshold | rationale |
|---|---:|---|
| H1 absolute success gain | >= 0.08 | exceeds expected paired baseline variation and changes at least 8 per 100 missions |
| H2 headroom-family gain | >= 0.10 | online transitions must recover at least 10 per 100 otherwise-mechanically differentiated missions |
| collision-free degradation | <= 0.01 | safety permits at most one additional collision per 100 episodes |
| centralized performance retained | >= 0.85 | decentralization must preserve most diagnostic opportunity |
| communication | <= 500,000 bytes/robot/transition | bounded against N24 path-protocol scaling and deployable logging budget |
| local inference latency | <= 0.10 of 0.15 s control period (15 ms) | preserves 90% of the control cycle for sensing/control/communication |
| seed consistency | positive effect in >=2 of 3 seeds | prevents one initialization from carrying the claim |
| concentration | no family or N contributes >0.50 of aggregate gain | prevents a one-cell claim |

H6 additionally limits pooled smaller-size degradation to 0.03 absolute.
Thresholds are evaluated with paired episodes and 95% intervals; the point
estimate must meet the practical gate and the corrected statistical test must
support direction. They were chosen from mission relevance, control period,
existing mechanical communication scaling and expected episode counts, not
learned or final-test results.
