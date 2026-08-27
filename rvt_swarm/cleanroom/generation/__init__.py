"""RVT_CLEANROOM_GENERATOR_V1 -- the clean-room dataset authorization layer.

The historical V3 generation stack is a CLOSED pilot authority: DATASET_IDS,
AUTHORIZED_DATASETS, AUTHORIZED_STUDY_SPLITS, the DatasetBudgetSpec registry and
the V3 layout registry are each hard-authorized for the pilot datasets and admit
no new role. Rather than patch any of that, this package is a NEW authorization
layer that CALLS the unchanged scientific core.

    SCIENTIFIC GENERATION CORE   (untouched)
        phase8.scenario geometry, phase8.seeds namespaces,
        phase9b.identity.derive_generation_seed, Target-V4, replica law,
        invalidity semantics, row/event binding
                    |
                    v
    CLEAN-ROOM DATASET AUTHORITY LAYER   (this package)
        roles, study/split, budget (read from the frozen V4 composition),
        layout-role registry, identity, seed ledger

No module here redefines a scientific formula. Every scientific quantity is
obtained by calling the frozen core.
"""
