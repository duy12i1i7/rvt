# RVT-FD24 Team-Size Experiment Contract

**Study A, zero-shot N=24:** train and select checkpoints using
`N={5,6,8,12,16}`. Freeze the selected checkpoint before evaluating N=24.
Neither N=24 labels, validation outcomes nor diagnostics may choose that
checkpoint.

**Study B, in-distribution N=24:** train a separate configuration on
`N={5,6,8,12,16,24}` with the same layout split, architecture, tuning cap and
model-seed count. Study B checkpoints cannot support a zero-shot claim.

Interpolation within Study A sizes is reported separately from N=24
extrapolation. Study B reports N=24 in-distribution performance and the change
on smaller sizes. H6 requires N=24 improvement without more than 0.03 absolute
pooled smaller-size task-success degradation.

Primary Study A train and validation manifests report 20 and 10 layouts per
size respectively. Final evaluation has 10 layouts for each of all six sizes.
Episodes remain paired by layout, team size and seed across methods. Mechanical
construction through N=24 does not imply learned generalization beyond these
declared sizes.
