# Phase 9C-RB21P Cross-Platform Numerical Portability

## Verdict

**C. Cross-platform numerical portability is closed without changing frozen
scientific semantics; the new Docker image is qualified to resume RB21-TARGET
performance benchmarking.**

This verdict authorizes only the next performance-qualification phase. It does
not authorize official generation, training, Study A N24, or final-test access.
No performance benchmark was run in RB21P.

## Identity

| Field | Value |
|---|---|
| RB21 audit base | `b8c60b8d7d744b8d8c4ee069bde58e05dc6e3e1b` |
| Blocked source | `96f1811888b5a462dceb905fa74022b78c2988b4` |
| Portability mechanism | `47ea1ff2e2d048f62c5cc3ba327c81688685f243` |
| Image source repair | `8bfabd48969f1fa1e13a0a268a6df1cb366e90cc` |
| CUDA audit code | `b91f1ad716f0901f9788642879c5016163bc3234` |
| Target diagnostic evidence | `24117553f101a27b137254d59a4882978e493931` |
| Branch | `research/rvt-rb21-cross-platform-portability-v1` |
| Blocked image | `sha256:c730e0726e8d1d9dba781ded3205c5c22131bb35461cbca4f5633e977b4ae0f9` |
| New image | `sha256:30e6dea61d67eb255e814996cf737140a3b47eac62fb74ecf303df58e280138b` |
| Dockerfile SHA-256 | `7bc931e328cd61dd9fe814986db494a58b0cc09b993df5803d5e318b627a68a7` |

The failed RB21 artifact and image remain preserved. The blocked commit is
tagged `rvt-rb21-target-portability-block-v1`. The `b8c60b8..96f181` audit
classified four operational files, two documents, one artifact, and one test;
it found zero scientific-runtime changes.

## Original Failures

The two PyTorch failures were float32 batch-shape reduction-order effects:

| Test | Single | Batched | Error | ULPs | Limit |
|---|---:|---:|---:|---:|---:|
| unrelated ego graphs | `-0.12159138917922974` | `-0.12159128487110138` | `1.043081283569336e-7` | 14 | `1e-7` |
| parallel candidate | `-0.11600999534130096` | `-0.11600988358259201` | `1.1175870895385742e-7` | 15 | `1e-7` |

The first unrelated-batch divergence on Linux was
`candidate.local_metadata.linear`. The failing candidate also first diverged
there; other candidate cases showed earlier typed-node-projection differences.
The behavior is consistent with platform-dependent CPU BLAS batched reduction
order, not cross-example edges or a model-state mutation.

The third failure was `train-f2-01.heading_radians`:

- source start: `(-6.0, -0.19727)`;
- source goal: `(6.0, 0.19727)`;
- `dx=12.0`, `dy=0.39454`, `hypot=12.006484156971183`;
- direction: `(0.9994599454023001, 0.032860577238251955)`;
- formula: `atan2(direction_y, direction_x)`;
- reference: `0x1.0d3e089e2d8bfp-5`;
- Linux: `0x1.0d3e089e2d8bep-5`;
- distance: exactly one binary64 ULP.

## Model Numerics

The predeclared profile matrix tested baseline, interop control, deterministic
algorithms, MKLDNN disablement, matmul precision, `MKL_CBWR`, and ATen CPU
capability. Only `MKL_CBWR=COMPATIBLE` passed both frozen isolation guards;
changing interop threads from 1 to the container default 24 retained the pass.
`ATEN_CPU_CAPABILITY=default` passed batch isolation but still failed candidate
isolation.

The selected profile is:

`FD24_NUMERICAL_EXECUTION_PROFILE_V1 = {MKL_CBWR=COMPATIBLE}`

Under the final image, maximum final-logit differences were:

| Case | Maximum absolute difference |
|---|---:|
| unrelated batch | `3.725290298461914e-8` |
| candidate 0 | `2.9802322387695312e-8` |
| candidate 1 | `3.725290298461914e-8` |
| candidate 2 | `8.195638656616211e-8` |

All remain below the unchanged `1e-7` contract. Model implementation code,
architecture, parameter shapes, 272,227 parameter count, 66 state-dict keys,
features, heads, targets, and tolerance are unchanged. No model implementation
repair was needed.

## Numeric Environments

The reference is macOS 26.5 arm64, Python 3.9.6/Clang 17, NumPy 2.0.2 with
Accelerate BLAS/LAPACK, and PyTorch 2.8.0 without MKL/MKLDNN/CUDA. PyTorch used
8 intraop and 12 interop threads; matmul precision was `highest` and
deterministic algorithms were disabled.

Windows native has Python 3.12.10/MSC 19.43 but no PyTorch or NumPy and is not
the scientific runtime. WSL Ubuntu 24.04 has Python 3.12.3/GCC 13.3 but no
PyTorch or NumPy and is also not the scientific runtime.

The qualified container is Debian 11 amd64, Python 3.9.6/GCC 10.2.1, glibc
2.31, NumPy 2.0.2 with scipy-openblas 0.3.27, and PyTorch 2.8.0+cpu with MKL
2024.2, MKLDNN 3.7.1, OpenMP 4.5, and AVX2 dispatch. Thread environment values
are one; PyTorch reports one intraop and 24 interop threads. Matmul precision is
`highest`; deterministic algorithms are disabled.

## Layout Authority

The frozen contracts establish both frozen source primitives and the committed,
canonically self-hashed compiled execution specification. Official runtime
binding consumes the latter. It now rejects a bad self-hash or a split/layout
identity mismatch before construction.

No Phase-9 runtime component reads `heading_radians`. It is a compiled cache
field; recomputing it through platform libm is unnecessary for generation.
The portability mechanism therefore loads and verifies the committed compiled
artifact. It does not round, special-case `train-f2-01`, alter source geometry,
or admit a second Linux identity.

Across all 30 train/validation layouts:

- authoritative self-hashes verified: 30/30;
- authoritative runtime identities resolved exactly: 30/30;
- physical projections matched fresh compilation: 30/30;
- fresh compiler documents matched directly: 29/30;
- nonmatching physical scalar count: 0.

The sole fresh-document mismatch remains the recorded one-ULP unused heading
cache. Representative source episodes and the full RB20 replay prove unchanged
physical and label semantics.

## Semantic Replay

Reference and target produced the same replay canonical hash:

`8a2b50fad6de75a2cee5ca97959b3d2570cbfdb096ae9f69457e1480fdae5c85`

| Scope | Count | Mismatches |
|---|---:|---:|
| source episodes | 4 | 0 |
| recoverability rollouts | 14 | 0 |
| residual candidate evaluations | 36 | 0 |
| scientific identities | all checked | 0 |
| Target V4 and label semantics | all checked | 0 |

The checked identities include layout hashes, graph fingerprints, scientific
row IDs, candidate evaluation IDs, snapshots, robot views, matched streams,
selector results, NO_ELIGIBLE_ACTION, and WORLD residual targets.

Recoverability labels come from the qualified simulator plus Target V4.
Residual V2 labels come from the qualified counterfactual expert, frozen
utilities, selector, and target builder. Neither label path calls a learned
recoverability or residual model.

## GPU Audit

| Field | Observed |
|---|---|
| Exact model | `NVIDIA RTX 5000 Ada Generation` |
| UUID | `GPU-262a5f7e-fa85-a213-98ed-2761941b4e9a` |
| VRAM | 32,760 MiB |
| PCI | `00000000:02:00.0` |
| Driver | 536.96 |
| Driver-exposed CUDA | 12.2 |
| Compute capability | 8.9 |
| Windows mode | WDDM |
| Windows / WSL nvidia-smi | 536.96 / 535.98.01 |

Docker registers the NVIDIA runtime and can expose the GPU. `nvidia-smi`
succeeds inside the candidate generation image. That image intentionally has
PyTorch 2.8.0+cpu, so `torch.cuda.is_available()` is false, device count is
zero, device name/capability are null, and `torch.version.cuda` is null.

An existing observational CUDA 11.8/PyTorch 2.1.2 container reports one device,
the exact GPU name, and capability `(8, 9)`. A test-only FD24 forward comparison
reported maximum CPU/CUDA differences of `5.960464477539063e-8` for the logit,
zero for probability, and `2.421438694000244e-8` for residual output. Parameter
count, state keys, and state values were unchanged. Bit identity was not
required, and this result is not authority for CPU portability.

No driver, CUDA installation, scientific execution path, or frozen CPU test
was changed for the GPU audit.

## CPU/GPU Boundary

| Component | Current execution |
|---|---|
| source simulator | CPU, Python/NumPy |
| Phase-6 controller | CPU, Python/NumPy |
| local safety projection | CPU, Python/NumPy |
| transition protocol | CPU, Python |
| Target V4 | CPU, Python |
| recoverability counterfactual generation | CPU qualified simulator + Target V4 |
| Residual Expert V2 generation | CPU expert, utilities, selector, target builder |
| ego-graph construction | CPU; creates CPU tensors |
| FD24 forward in candidate image | CPU |
| FD24 CUDA forward | test-only diagnostic when explicitly transferred |
| future training | CUDA-capable, not run or qualified in RB21P |

GPU availability therefore does not imply faster Phase-9 label generation.
RB21-TARGET must begin with `PROFILE_CPU_GENERATION`. A later
`PROFILE_GPU_ASSISTED_GENERATION` is admissible only for already permitted
components and only with an identical `SCIENTIFIC_SEMANTIC_DIGEST`.

## Tests

| Environment | Result |
|---|---|
| reference host full suite | 2,984 passed, 0 failed, 1 warning, 389.07 s |
| target final-image full suite | 2,978 passed, 0 failed, 0 xfailed, 342.73 s |
| target scope/isolation/layout smoke | 99 passed, 0 failed, 0.69 s |

An intermediate image run produced eight Git-history scope-guard failures
because its LF checkout borrowed objects through a Windows Git alternates path
that was invalid inside Linux. Materializing the full object database fixed the
operational checkout defect; the same source and Dockerfile then passed all
2,978 tests. No test expectation or scientific code changed for that repair.

## Provenance And Isolation

The portability artifact is
`results/rvt_fd24/rb21_cross_platform_numeric_portability_v1.json`, self-hash:

`0330c25a436a42422d8f8d07ae3426c930628f32bcd2a0d58ca8204874290900`

The additive requalification root is
`results/rvt_fd24/rb21_portability_requalification_v1.json`, self-hash:

`fcc218e4bc88546240789043aa9e160d1fa39b82701637ebd6af19f2f8dcc176`

RB19, RB20, the failed RB21 artifact, and all historical layout artifacts are
unchanged. Isolation counts are all zero: Study A N24 accesses, final-test
accesses, official rows, scientific shards, checkpoints, optimizer states,
training operations, and performance benchmarks.

## Resume Decision

RB21-TARGET performance qualification may resume on image
`sha256:30e6dea61d67eb255e814996cf737140a3b47eac62fb74ecf303df58e280138b`.
RB21P stops here. It does not run performance qualification or authorize data
generation.
