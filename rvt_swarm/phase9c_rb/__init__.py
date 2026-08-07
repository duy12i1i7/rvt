"""Phase 9C-RB — executable scenario-to-runtime binding.

This package translates the frozen Phase 8E executable scientific protocol into
running code. It introduces **no** scientific semantics of its own: every value
it uses is either read from the compiled layout execution specification, read
from `executable_scientific_protocol_v1.json`, or derived by a formula that
document states explicitly.

The package is additive. It does not modify the historical KEEP/LINE closed-loop
runtime, the Phase 6 controller, the Phase 6 safety projection, the Phase 7
transition protocol, Metric V3, or any Phase 8/9B artifact.

Locality boundary
-----------------
`world`, `dynamics`, `channel` and `session` hold complete simulator state --
that is their job, and the protocol explicitly permits it ("the global simulator
may maintain complete world state"). Robot-local input is constructed in exactly
one place, `observation.build_robot_view`, and nothing downstream of it ever
receives a global object. `tests/test_phase9c_runtime_information_boundary.py`
demonstrates that with mutation interventions rather than by inspection.
"""

from __future__ import annotations

SCHEMA_VERSION = "rvt-scenario-runtime-binding/v1"
EXECUTION_PROTOCOL_SCHEMA_VERSION = "rvt-phase9-execution-protocol/v1"
CANARY_SCHEMA_VERSION = "rvt-phase9c-runtime-binding-canary/v1"
