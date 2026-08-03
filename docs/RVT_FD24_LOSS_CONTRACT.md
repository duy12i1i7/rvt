# RVT-FD24 Loss Contract

Schema: `rvt-fd24-loss/v1`.

`L = lambda_rec*L_rec + lambda_res*L_res + lambda_mag*L_mag + lambda_consistency*L_consistency`.

- `L_rec`: binary cross-entropy with logits, no class weighting, focal term or oversampling before the label audit.
- `L_res`: Smooth L1 on valid expert residual components with beta `0.05 m/s2`.
- `L_mag`: mean absolute bounded residual prediction, discouraging unnecessary action without forcing zero.
- `L_consistency`: disabled initially; a later enabled variant may compare only predeclared local equivariant transforms.

Recoverability is averaged equally over COMPACT/LINE and robots within one
decision, then over decision events. Residual and magnitude terms average action
components, robot rows within an episode, then episodes. Larger N and events
with more local rows therefore receive no automatic extra scientific weight.
Invalid rollout rows are masked and counted, never relabelled. Residual loss is
masked unless the local expert and safety compatibility are valid.

The only loss-weight choices are:

1. `(lambda_rec,lambda_res,lambda_mag,lambda_consistency)=(1.0,0.5,0.01,0.0)`;
2. `(1.0,1.0,0.05,0.0)`.

Validation chooses within the predeclared hyperparameter cap. Final test cannot
choose a loss or weight.
