"""Open-loop V3 recoverability predictor study -- offline training machinery.

This package exists to EXECUTE the frozen
``OPEN_LOOP_V3_RECOVERABILITY_PREDICTOR_PREREGISTRATION_V1``. It defines no
scientific semantics of its own: the target, the loss, the Brier metric, the
event weighting, the row identity and the model architecture all live in already
frozen modules, and everything here calls them rather than restating them.

It is deliberately OUTSIDE ``rvt_swarm.decentralized`` and ``rvt_swarm.fd24``.
Those two packages are the deployable robot-local path and are policed by
``rvt_swarm/decentralized/guards.py``; this package is offline orchestration that
reads whole datasets and constructs optimizers, which is exactly the kind of
code that must never become reachable from a control loop.
``tests/test_stage5b_offline_isolation.py`` asserts that no module in either
deployable package imports this one, so the separation is enforced rather than
merely intended.

Nothing here authorizes scientific training. See :mod:`authorization`.
"""

OPEN_LOOP_V3_PACKAGE_ROLE = "OFFLINE_TRAINING_ORCHESTRATION"
DEPLOYABLE = False
