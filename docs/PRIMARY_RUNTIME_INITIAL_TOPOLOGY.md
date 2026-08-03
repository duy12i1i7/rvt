# Primary Runtime Initial Topology

## Contract

The primary scientific runtime initializes in COMPACT by default. LINE is
permitted only when a scenario explicitly declares a narrow start and the
mission-setup geometry check confirms that LINE is a physically valid initial
condition. KEEP is not a valid primary online initial topology.

The structured initialization API returns:

- `ADMITTED` with COMPACT when no topology is requested or COMPACT is requested;
- `ADMITTED` with LINE only after both narrow-start declaration and physical validity;
- `UNSUPPORTED_INITIAL_TOPOLOGY` for undeclared LINE or KEEP;
- `UNKNOWN_TOPOLOGY` for an unregistered ID.

## Role Placement

Mission setup constructs persistent robot roles once, then places each role at
the selected topology template offset and nominal spacing from the immutable
registry. The primary runtime receives the matching robot-local role view. It
does not infer an initial topology from joint runtime state and does not rename
KEEP geometry as COMPACT.

Initial perturbations and scenario transforms must continue to pass the frozen
physical-validity and initial-condition checks. A narrow-start declaration is
metadata, not permission to bypass those checks.

## KEEP Baselines

An always-KEEP episode is created through the existing fixed-topology runtime,
where KEEP is bound before execution and cannot change online. It remains an
open-space nominal reference and controller qualification topology. Its result
must not be pooled as an online initialization or transition result for the
primary COMPACT/LINE method.
