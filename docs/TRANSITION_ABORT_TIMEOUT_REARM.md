# Transition Abort, Timeout, and Rearm

Timeouts are physical-time consequences of communication period, causal round
bounds, message freshness, configured commitment time, recovery dwell, and
rearm inactivity.  Raw control-step constants are not source parameters.

Intent, score, readiness, and confirmation time out when their causal phase
cannot finish with fresh complete membership evidence.  Execution and dwell
time out when target stability cannot be established without safety or
numerical failure.  Temporary disconnection follows the configured policy:
retain source and abort before commitment.

A precommit abort retains source topology, records exactly one cause, clears the
active candidate, creates no mode epoch, and enters an inactive rearm hold.  A
committed emergency abort records the committed target and failure cause; it
does not silently reverse.  Rearm requires configured inactive seconds,
evidence disappearance, stable topology, and no active conflict.  Repeated or
duplicate evidence during hold cannot restart the lifecycle.
