# RVT-Swarm paper blueprint

## Core claim
RVT-Swarm is a decentralized swarm formation controller that reasons jointly over
control, safety, and **recoverability-aware topology adaptation**.

## Main novelty
1. Recoverability field on local interaction graphs.
2. Counterfactual topology selection under recoverability constraints.
3. Progress-preserving safety intervention instead of purely instantaneous collision avoidance.

## Recommended ablations
- no recoverability head
- no topology head
- greedy topology without counterfactual scoring
- no safety shield
- fixed formation only

## Main comparisons
- GNN only imitation policy
- instantaneous safety certificate controller
- adaptive formation heuristic
- CBF-QP-like safety filter
- ORCA-like reactive avoidance
