# Local Safety Claim Boundary

The Phase 6 projection is a constraint-based local action filter and is
empirically evaluated local collision mitigation. It does not establish
unconditional whole-swarm safety or formal collision avoidance.

Its interpretation depends on:

- locally observable threats being represented by the accepted sensor/message
  primitives;
- message and observation ages being bounded and correctly reported;
- peer acceleration not exceeding the immutable platform bound;
- obstacle relative velocity being correct over one control period;
- action execution matching the documented semi-implicit dynamics;
- sufficient local constraint feasibility;
- a shared frame and synchronized physical units.

Threats outside sensing/communication range, packet loss beyond the stale-data
contract, adversarial unmodelled acceleration, occlusion, actuator error and
multi-step deadlock are outside the guarantee. Simultaneous independent local
projections can also be mutually conservative or infeasible.

An intervention means only that the proposed local action violated at least one
declared local constraint or the physical acceleration bound. No intervention
does not certify global free space. An infeasible fallback is a declared
best-effort local response, never evidence that all constraints were satisfied.
