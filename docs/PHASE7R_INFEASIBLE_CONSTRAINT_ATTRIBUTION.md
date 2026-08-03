# Phase 7R Infeasible Constraint Attribution

Primary family: **peer safety versus the physical acceleration disk**. For every abort, a two-item irreducible set consisting of the acceleration disk and one peer half-space is already empty. Obstacle constraints, stale messages, equalities, tracking requirements and transition-progress requirements are absent from these local optimization problems.

Diagnostic candidate pass counts out of 97: `{'zero_acceleration': 0, 'maximum_admissible_braking': 0, 'goal_term_removed': 0, 'formation_term_removed': 0, 'transition_displacement_term_removed': 0, 'obstacle_term_only': 0, 'phase6_declared_infeasible_fallback': 0}`. Removing controller terms cannot make a constraint set nonempty because those terms affect only the projection objective. Phase 6 defines an explicit bounded infeasible fallback, not a certified safety-preserving hold for an impossible set.
