# Phase 9 Correlated-Sample Grouping

The frozen hierarchy is:

`layout_group -> episode_group -> decision_event_group -> candidate_pair_group -> robot-candidate record`

The authoritative manifest proves that source, event and candidate jobs have
unique semantic IDs and that no planned job uses the final-test split. Study,
split and layout hash are inherited from one canonical dataset cell, so no
planned episode or event crosses a split.

No recoverability record was emitted. Record-level grouping completeness,
calibration aggregation and loader batching are therefore not scientifically
evaluated. The fail-closed record validator rejects missing `episode_group`,
`decision_event_group`, `layout_group` or `candidate_pair_group` fields.

