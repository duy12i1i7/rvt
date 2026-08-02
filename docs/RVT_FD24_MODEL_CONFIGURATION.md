# RVT-FD24 Model Configuration

`FD24ModelConfig` is frozen, hashable through canonical JSON, independent of
`TrainingConfig`, and versioned as `rvt-fd24-model-config/v1`.

| Field | Meaning | Valid range | Source | Relevance | Default rationale |
|---|---|---|---|---|---|
| `schema_version` | configuration contract | exact version | architecture | runtime/checkpoint | explicit rejection of unknown configs |
| `hidden_dimension` | node, edge, root, and head width | positive integer | model hyperparameter frozen before training | both | 96 reuses approved local V1 compute scale |
| `message_passing_blocks` | local propagation depth | positive integer | model hyperparameter | both | 3 reuses approved local V1 depth |
| `candidate_embedding_dimension` | explicit topology embedding width | positive integer | standard design choice | both | 16 is lightweight relative to hidden width |
| `activation` | nonlinear activation | `relu` only in v1 | standard design choice | both | repository convention |
| `normalization` | hidden normalization | `layer_norm` only | locality constraint | both | per-node statistics, no graph mixing |
| `dropout_probability` | training regularization | finite `[0,1)` | model hyperparameter | training/eval mode | 0 for deterministic isolation |
| `attention_leaky_relu_slope` | attention-score negative slope | finite `(0,1]` | model hyperparameter | both | 0.2 reuses approved local V1 design |
| `residual_limit_fractions_of_maximum_acceleration` | per-action residual fractions | one finite `(0,1]` value per action component | frozen model/controller interface | runtime/checkpoint | `(0.25,0.25)`, explicit bounded correction |
| `numerical_dtype` | tensor precision | `float32` only | compute constraint | both | matches V2 tensors and deployment |
| `diagnostic_embedding_enabled` | permits hidden output | Boolean | diagnostic policy | runtime diagnostics | false prevents accidental exposure |

`action_dimension` is derived from
`ROBOT_LOCAL_ACTION_COMPONENTS`, currently two. SI residual limits are derived
by multiplying each configured fraction by the immutable physical maximum
acceleration. Neither action width nor any layer width depends on N.

Learning rate, optimizer, epochs, batch size, weight decay, data split, labels,
and scenario choices are deliberately absent. Future training configuration
must remain separate and cannot enter deployable model construction.
