# RVT Random-Seed and Reproducibility Contract

Schema `rvt-seed-namespaces/v1` uses deterministic SHA-256-to-uint32 derivation.
Root seeds and exclusive roles are:

| namespace | root | role |
|---|---:|---|
| layout_generation | 8101 | geometry parameters |
| split | 8102 | split membership |
| initial_condition | 8103 | formation pose/velocity |
| communication | 8104 | delay/loss/disconnection |
| dynamic_obstacle | 8105 | moving obstacle path realization |
| counterfactual_rollout | 8106 | matched candidate disturbance |
| data_sampling | 8107 | row/event subsampling |
| model_initialization | 8108 | model parameters |
| training_dataloader | 8109 | batch ordering |
| evaluation | 8110 | paired evaluation realization |

A derived seed hashes schema, namespace, root, split and semantic identity. One
seed value has one role. Model/dataloader seeds cannot alter layout membership.
Candidate counterfactuals share disturbance identity. Paired baselines share
initial, communication, dynamic and evaluation seeds.

Train/validation seeds and derivation are immutable. Final episode seeds are
stored only as commitments until one-time authorization; normal derivation
rejects `split=final_test`. There is no repeated resampling until success.
Commands, commits, namespace schema and derived seed identities are recorded in
future provenance.
