# Phase 7R Local Projection Forensics

All 97 first abort-causing calls were reconstructed from robot-local inputs only. Classification counts: `{'B_independently_infeasible': 97}`. Production and the independent minimum-norm half-space oracle agree in every case.

Every case contains a peer half-space whose required normal acceleration exceeds the 0.6 m/s^2 acceleration-disk support. Across irreducible conflicts the required values span 0.628996 to 7.057448 m/s^2. The production fallback is bounded and explicit, but Phase 6 does not claim it satisfies an empty set; dual residuals are unavailable from the exact active-set implementation.

The full inequalities, normals, offsets, peer states, proposed/projected actions, residuals and oracle proofs are serialized in `local_projection_forensics.json`.
