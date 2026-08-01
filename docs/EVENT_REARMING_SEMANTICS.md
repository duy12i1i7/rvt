# Event Re-arming Semantics (Task G4)

## The defect

`REARM_OPEN_STEPS = 25` was a raw step count with no derivation — its comment
said only "long enough", computing nothing from passage length, speed or
formation extent.

## The repair

Re-arming is gated by a **physical lifecycle condition** plus a dwell specified
in **seconds**:

1. the previous lifecycle is `COMPLETE`;
2. the trigger evidence has returned to a non-active state (own clearance has
   reopened past `recovery_clearance`);
3. that non-active state persists for `rearm_inactive_seconds`;
4. no active commitment or epoch remains.

```
rearm_inactive_steps = ceil(rearm_inactive_seconds / control_period)
                     = ceil(3.75 / 0.15) = 25
```

The step count is **derived, never configured**. At `dt = 0.075` it becomes 50
steps and the time-domain behaviour is unchanged — asserted in
`test_parameter_scaling.py`.

The duration is a protocol assumption about how far apart two physically
distinct bottlenecks must be, not a value copied from one corridor's traversal.
