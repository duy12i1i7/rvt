# RVT-FD24 Unit of Analysis

## Units

1. **Episode:** one complete mission rollout under one baseline or method.
2. **Decision event:** one valid online COMPACT/LINE selection opportunity.
3. **Robot-candidate sample:** one robot-local ego graph evaluated for one candidate.
4. **Robot-action sample:** one robot-local state with a base action and residual target.
5. **Geometry layout:** one obstacle-map instance identified by a canonical geometry hash.
6. **Initial-condition instance:** one formation pose, velocity, communication seed and disturbance realization.

The primary scientific unit is the paired episode. Layout-level sensitivity is
also reported because episodes sharing geometry are clustered. A decision event
is the unit for recoverability calibration and ranking. Robot-candidate and
robot-action samples are training rows, not independent scientific outcomes.

## Correlation Rules

Robots, timesteps and candidates from one event or episode may be used as
correlated training samples. They cannot be counted as independent episodes,
bootstrap units or hypothesis-test observations. Both candidate labels from one
decision remain paired. All local views from one decision and all timesteps
from one episode belong to exactly one split.

Validation summaries first aggregate robot-candidate rows within a decision,
then decisions within an episode. Episode confidence intervals use the frozen
paired episode key. A layout-cluster bootstrap is a sensitivity analysis, not a
replacement that inflates the episode count. Missing or failed episodes are
handled under the statistical contract rather than silently dropped.
