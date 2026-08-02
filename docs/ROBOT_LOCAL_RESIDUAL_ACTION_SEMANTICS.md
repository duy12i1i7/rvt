# Robot-Local Residual Action Semantics

The primary FD24 action output is a correction to a verified future base
controller action, not a replacement controller:

```text
raw_i_tau in R^2
Delta_u_i_tau = limit * tanh(raw_i_tau)
future_u_i = future_base_u_i(tau) + Delta_u_i_tau
```

Phase 5 implements only `Delta_u_i_tau`. It does not compute, combine, clip,
project, or execute `future_u_i` in closed loop.

The two dimensions come from the named planar mission-frame acceleration action
contract. Limits are derived from immutable model fractions and physical
maximum acceleration. With current defaults:

| Component | Fraction | SI limit |
|---|---:|---:|
| mission longitudinal acceleration | 0.25 | 0.15 m/s^2 |
| mission lateral acceleration | 0.25 | 0.15 m/s^2 |

Zero raw output maps exactly to zero residual. Positive and negative outputs
approach their per-dimension limits smoothly and cannot exceed them. The mapping
is differentiable and has no hidden scale.

Each ego graph produces only its observer robot's two-component residual. Peer
states influence local evidence through permitted message passing but never
create peer actions. No output is proportional to team size.

`DirectLocalActionAblationHead` is a separate, explicitly named full-action
ablation interface. It consumes the same conditioned local representation and
is not present in the primary model or current runtime.
