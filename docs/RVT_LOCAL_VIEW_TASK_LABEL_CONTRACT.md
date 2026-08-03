# RVT Local-View Task-Label Contract

Schema `rvt-local-view-task-label/v1` associates one task-level,
candidate-specific counterfactual outcome with several robot-local ego graphs
from the same decision event. The label is global offline supervision; the
input remains one robot's local view. Shared labels do not make robot rows
statistically independent.

Every recoverability row records episode ID, decision-event ID, robot ID,
candidate topology, ego-graph schema, feature hash, source topology, team size,
scenario family, layout hash, split, rollout-config hash, binary label, joint
outcome, timestamp, message condition and source commit. KEEP is rejected from
the primary candidate field.

All robot/candidate views from one decision event remain in one split. Grouped
validation statistics aggregate candidates and robots within the event before
episode aggregation. Calibration resampling, uncertainty and confidence
intervals use event/episode groups, not rows. Batching may mix groups for
optimization but must retain group IDs and cannot leak one group across split
or distributed validation workers.
