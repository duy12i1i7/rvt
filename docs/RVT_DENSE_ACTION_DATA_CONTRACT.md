# RVT Dense Action Data Contract

Dense action rows may come from stable COMPACT, stable LINE, both transition
directions, obstacle interaction, local safety intervention, bounded recovery
and communication-degraded observations where control remains valid.

Each row stores the robot-local ego graph, candidate or committed topology,
base action, expert action, clipped residual target, projected base action,
safety metadata, persistent role, team size, family, layout hash, split,
episode ID, timestep, source commit and all configuration hashes. World-frame
acceleration and `dt=0.15 s` are explicit.

Phase 9 caps dense rows at 250,000 train and 50,000 validation samples, no more
than 64 retained timesteps per episode and minimum temporal spacing 0.45 s
(three control steps). Exact local feature/action duplicates are suppressed.
Episode groups cannot cross splits. Family/team cells receive uniform maximum
budgets before the audit; intervention states are reported, not silently
oversampled.

Dense action rows and recoverability rows may have different temporal density,
but reference the same immutable split and experiment-protocol hashes. Final
test rows are prohibited from training datasets.
