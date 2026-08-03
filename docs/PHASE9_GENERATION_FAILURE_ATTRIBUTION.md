# Phase 9 Generation Failure Attribution

## Confirmed Primary Cause

`PHASE8_SCENARIO_TO_ACTIVE_RUNTIME_BINDING_ABSENT`

Classification: infrastructure generation implementation failure.

Evidence:

1. The canonical `S1_ALWAYS_COMPACT` job failed before simulator step 0 with
   `AttributeError: 'ScenarioLayout' object has no attribute 'start_center'`.
2. The legacy environment requires `start_center`, `goal` and
   `obstacle_array`; Phase 8 defines metric-valued centers, typed obstacle
   primitives, centerlines and dynamic paths.
3. The full closed-loop decentralized runtime declares only KEEP and LINE. It
   does not admit the approved COMPACT/LINE candidate scope.
4. The qualified Phase 7 transition entrypoint accepts open-space fixtures,
   not a Phase 8 layout, cloned source state, communication state, disturbance
   state or dynamic-obstacle state.
5. No executable binding exists for any of the six frozen S0-S5 source class
   names.

The permitted identical infrastructure retry produced the same failure. No
replacement job or seed was generated. This is not a semantic task failure.

Implementing the missing pieces would define new geometry compilation, source
policy schedules, perturbation semantics and closed-loop integration. That is
outside a local canary defect repair and cannot be inferred from observed
labels.

