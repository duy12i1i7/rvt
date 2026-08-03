# Transition Command Discontinuity Audit

The Phase 7 executor replaces source role offsets with target role offsets in one control step. Source, midpoint and target offsets were inspected offline for every robot without changing commitment. Initial proposed-action jump norms range from 0.145994 to 2.119087 m/s^2. First-step projections remain feasible, while 97 trajectories later lose peer/action feasibility.

**Conclusion B: immediate target switching is a primary cause.** The generic profile removes 45 of 97 original aborts. It is not the only limitation: the remaining failures coincide with unsafe or marginal straight role paths.
