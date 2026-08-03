# RVT Residual-Action Target V1

Schema: `rvt-residual-action-target/v1`.

The authoritative expert is **Option B: frozen counterfactual robot-local action
search**, ID `B_FROZEN_COUNTERFACTUAL_LOCAL_ACTION_SEARCH_V1`. It uses exactly
the sampled robot's permitted local information and the same local safety
compatibility check, but may evaluate a fixed offline candidate lattice. It is
not a centralized joint-action expert.

For robot `i`, `u_base_i` is the frozen Phase 6 projected robot-local action.
The expert selects the best locally feasible candidate within the Phase 5
residual envelope and physical acceleration disk. Its frozen normalized utility
is:

`progress + 0.50*clearance - 0.25*formation_error - 0.05*action_deviation`.

All terms use frozen local SI normalizers. Infeasible, safety-incompatible or
non-local candidates are ineligible. Ties prefer lower action deviation, then a
canonical action order.

The target is

`Delta_u = clip_to_residual_bounds(u_expert - u_base)`.

It is a two-component world-frame acceleration at `dt=0.15 s`. Each residual
component is bounded by 0.25 of the frozen 0.6 m/s2 maximum acceleration,
therefore `[-0.15,0.15] m/s2`. The expert action must also remain inside the
physical acceleration disk. Centralized experts may be reported only as
diagnostic upper references.
