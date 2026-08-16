"""Phase 9D-H1R -- Recoverability source-acquisition protocol V2.

Phase 9D-R2 proved that every dropped V1 candidate pair was dropped because the
scheduled source event never became a realized source state: the V1 slots were
fixed fractions of the *nominal* family horizon and the source trajectory
usually terminated first. Nothing about the candidate branch, Target V4, pair
reconciliation or the frozen aggregation was implicated.

This package is the prospective repair of the *acquisition* stage only. It
enumerates the realized source-state universe, applies a candidate-blind
deterministic selection rule, and binds a V2 event identity. It contains no
candidate execution, no label, no authorization and no official generation.
"""

from .acquisition_v2 import (  # noqa: F401
    DEFAULT_K,
    DESIGN_PILOT_STUDY,
    FIRST_K_ELIGIBLE,
    FIXED_SOURCE_TIME_STRIDE,
    MINIMUM_SPACING_CONTROL_STEPS,
    REALIZED_LEGACY_STAGE_ONLY,
    REALIZED_TRAJECTORY_UNIFORM_K,
    SOURCE_ACQUISITION_SCHEMA_VERSION,
    SOURCE_EVENT_IDENTITY_SCHEMA_VERSION,
    AcquisitionError,
    RealizedSourceState,
    SourceStateUniverse,
    acquisition_protocol_v2,
    acquisition_protocol_v2_sha256,
    enumerate_realized_source_universe,
    recoverability_source_event_id_v2,
    select,
    select_first_k_eligible,
    select_fixed_source_time_stride,
    select_realized_legacy_stage_only,
    select_realized_trajectory_uniform_k,
)
from .exclusion import (  # noqa: F401
    DesignPilotReuseError,
    assert_not_design_pilot_identity,
    design_pilot_identity,
    load_exclusion_set,
)
