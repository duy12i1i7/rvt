# RVT-FD24 Model Feature Use Audit

## Audit method

The encoder receives all 35 node and 19 edge columns from the approved Phase 4
registry. Values are multiplied by their feature-validity masks and concatenated
with those masks before a typed projection. Candidate-local root blocks also
enter the explicit conditioner. All normalization remains the Phase 4 physical
normalization.

`gradient path` means an applicable observed feature can affect the root through
typed projection and local message passing; architecture tests verify nonzero
gradients for every node type, edge type, message block, conditioner, and head.

## Node features

| Feature | Encoder | Conditioner | Head | Masked correctly | Normalization | Gradient path | Unused/reason |
|---|---|---|---|---|---|---|---|
| node kind one-hot | yes, plus typed dispatch | no | through root | yes | none | typed node projection | used |
| relative position | yes | no | through root | yes | nominal spacing | self or local message edge | used |
| relative velocity | yes | no | through root | yes | maximum speed | peer/obstacle message | used |
| class distance | yes | no | through root | yes | communication/sensing range | local message | used |
| bearing cos/sin | yes | no | through root | yes | unit vector | local message | used |
| committed topology one-hot | yes | no | through root | yes | explicit vocabulary | node projection | used |
| candidate topology one-hot | yes | explicit ID embedding also used | both | yes | explicit vocabulary | root and conditioner | used |
| candidate role offset | yes | own root block yes | both | yes | nominal spacing | node projection/conditioner | used |
| candidate role displacement | yes | yes | both | yes | nominal spacing | root/conditioner | used |
| candidate transition magnitude | yes | yes | both | yes | nominal spacing | root/conditioner | used |
| candidate observation extent | yes | yes | both | yes | sensing range | root/conditioner | used |
| goal vector | yes | no | through root | yes | nominal spacing | root projection | used |
| goal distance | yes | no | through root | yes | nominal spacing | root projection | used |
| self velocity | yes | no | through root | yes | maximum speed | root projection | used |
| local progress | yes | no | through root | yes | nominal spacing | root projection | used |
| decision age | yes | no | through root | yes | decision reference | root projection | used |
| peer message age | yes | no | through root | yes | stale limit | peer-to-root message | used |
| peer role known | yes | no | through root | yes | Boolean | peer-to-root message | used |
| peer topology conflict | yes | no | through root | yes | Boolean | peer-to-root message | used |
| obstacle radius | yes | no | through root | yes | sensing range | obstacle-to-root message | used |
| obstacle confidence | yes | no | through root | yes | probability | obstacle-to-root message | used |
| obstacle age | yes | no | through root | yes | control period | obstacle-to-root message | used |

## Edge features

| Feature | Encoder | Conditioner | Head | Masked correctly | Normalization | Gradient path | Unused/reason |
|---|---|---|---|---|---|---|---|
| edge type one-hot | typed edge projection | no | through root | yes | none | relation-specific projection | used |
| directed relative position | yes | no | through root | yes | nominal spacing | message block | used |
| directed relative velocity | yes | no | through root | yes | maximum speed | message block | used |
| directed distance | yes | no | through root | yes | communication/sensing range | message block | used |
| directed bearing | yes | no | through root | yes | unit vector | message block | used |
| nominal formation relation | yes | implicit candidate local geometry | both | yes | Boolean | message block | used |
| desired pairwise offset | yes | local candidate relation | both | yes | nominal spacing | message block | used |
| local formation residual | yes | local candidate relation | both | yes | nominal spacing | message block | used |
| candidate topology one-hot | yes | explicit ID embedding also used | both | yes | explicit vocabulary | message/root/conditioner | used |

## Non-feature metadata

Observer ID and graph fingerprint preserve output association but never enter a
linear or embedding layer. Candidate ID enters only equality-based vocabulary
lookup. `graph_index` is used solely to validate boundaries; it is not an input
feature. Raw robot array index, obstacle ordering, topology-registry iteration
order, and padding pattern have no model channel.

No accepted Phase 4 tensor feature is accidentally unused in model v1. This is
an architecture connectivity statement, not evidence that every feature will
be statistically useful after future training.
