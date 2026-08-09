# Phase 9C-RB21 Windows/WSL/Docker Operational Qualification

## Verdict

**B. Container/operational configuration changes scientific semantics.**

The Windows host, WSL2, Docker Desktop, Linux-native storage, immutable source
layout, and pinned CPU image were established successfully. The exact
previously qualified Python 3.9.6 / PyTorch 2.8.0 / NumPy 2.0.2 stack still
fails three scientific-semantic tests on Linux/amd64:

- two FD24 batch/candidate isolation comparisons exceed the frozen absolute
  tolerance of `1e-7`;
- Linux recompilation of frozen layout `train-f2-01` changes one binary64
  `heading_radians` value and therefore changes the layout self-hash.

Phase 15 requires zero failures and explicitly requires a Verdict B stop when
Docker changes scientific semantics. No scientific implementation, tolerance,
rounding rule, layout, model, protocol, controller, or evaluator was changed to
force a pass. Phases 16 through 35 were not executed.

No official generation or training ran.

## Remote Access

| Check | Result |
|---|---|
| ICMP | reachable |
| TCP 22 | open |
| TCP 3389 | open |
| TCP 5985 / 5986 | closed or filtered |
| Mechanism used | interactive SSH PTY |
| Authentication | succeeded |
| Credential persisted | no |

The Windows account is a local Administrator. No firewall or remote-access
configuration was changed.

## Windows Host

| Field | Observed |
|---|---|
| Hostname | `AVIS` |
| OS | Microsoft Windows 11 Pro `10.0.26200.8875` |
| Architecture | x64 |
| CPU | Intel Core Ultra 9 285K |
| Physical / logical cores | 24 / 24 |
| RAM | 68,053,331,968 bytes |
| System volume | NTFS, 3,999,702,970,368 bytes |
| Free system-volume space | 2,994,896,723,968 bytes |
| NVMe | Samsung SSD 990 PRO with Heatsink 4TB |
| GPU | NVIDIA RTX 5000 Ada, 32,760 MiB, driver 536.96 |
| Hypervisor | present |
| Virtualization-based security | running |

The active default route is through `Ethernet 2` to `192.168.88.1`. The
qualification address is the Tailscale address `100.71.102.9`.

## WSL2

| Field | Observed |
|---|---|
| WSL version | `2.7.10.0` |
| WSL kernel | `6.18.33.2-microsoft-standard-WSL2` |
| Default distribution | `Ubuntu-24.04` |
| Distribution release | Ubuntu 24.04.4 LTS |
| Distribution version/state | WSL2 / running |
| CPUs exposed | 24 |
| Memory exposed | 33,323,384,832 bytes |
| Swap | 8,589,934,592 bytes |
| Linux filesystem | ext4 |
| Linux volume available | 1,024,412,991,488 bytes |

No `.wslconfig` override existed, so no arbitrary CPU or memory limits were
introduced.

## Docker

| Field | Observed |
|---|---|
| Docker Desktop | `4.80.0.232116` |
| Client / Engine | `29.6.1` / `29.6.1` |
| API | `1.55` |
| Container OS / architecture | Linux / amd64 |
| Storage driver | overlayfs |
| CPUs / memory | 24 / 33,323,384,832 bytes |
| Docker root | `/var/lib/docker` |
| WSL integration | enabled for Ubuntu-24.04 |

The existing `lab-khai`, `lab-nhat`, and `lab-gpu-manager` containers
were preserved. A controlled Docker Desktop restart restored them under their
existing restart policies.

Public image pulls use a credential-free Docker config at
`/home/avis/.docker-rvt-public`. No registry credential was added. Linux
container execution passed with the official Ubuntu 24.04 and hello-world
images.

## Filesystem

All high-I/O project and data paths are on the WSL ext4 filesystem:

- project: `/home/avis/rvt`;
- staging: `/home/avis/rvt-data/staging`;
- final: `/home/avis/rvt-data/final`;
- temporary: `/home/avis/rvt-data/temp`;
- audit/log: `/home/avis/rvt-data/audit`.

No `/mnt/c` or Windows user-directory bind mount was selected for scientific
generation.

## Repository

The public remote was inspected rather than guessed:
`https://github.com/duy12i1i7/rvt.git`.

The remote did not advertise the required evidence commit. A clean incremental
Git bundle was transferred, its SHA-256 matched at both ends, and the target
checked out:

`b8c60b8d7d744b8d8c4ee069bde58e05dc6e3e1b`

detached with an initially empty `git status --porcelain`. Historical commit
and tree objects required by the scope guards were verified in the target
clone.

## Dependency Decision

The current `requirements.txt` resolves to newer, previously unqualified
versions, including PyTorch 2.11 and NumPy 2.4.4. That probe was rejected as an
upgrade path. The semantic probe instead pins the versions from the
previously passing host:

- Python 3.9.6;
- PyTorch 2.8.0 CPU;
- NumPy 2.0.2;
- Matplotlib 3.9.4;
- pytest 8.4.2;
- Pillow 11.3.0;
- the complete transitive closure in
  `docker/generation/requirements.lock.txt`;
- local `third_party/Python-RVO2`.

This version match is important: it proves the remaining failures are not
caused by casually modernizing the stack.

## Generation Image

The headless semantic probe image is not a qualified production image.

| Field | Value |
|---|---|
| Probe tag | `rvt-generation:rb21-qualified-stack-probe` |
| Image ID / local RepoDigest | `sha256:695acb7a54004b32116820ac2e4b325dde5a73e1b63a9a163688a1366c61ff2b` |
| Image manifest | `sha256:30d429a7802bf81215c42c9b6aa68100fa86f0850fe805adf414f0bbe4fd13aa` |
| Base image | Python 3.9.6 slim bullseye, digest `4115592f...bcd7c` |
| Container distribution | Debian 11 bullseye |
| Source label | `b8c60b8d7d744b8d8c4ee069bde58e05dc6e3e1b` |
| Source path | `/opt/rvt`, root-owned, worker read-only |
| Writable data | `/rvt-data/*` only |

Default nested thread environment values are all one:
`OMP_NUM_THREADS`, `MKL_NUM_THREADS`, `OPENBLAS_NUM_THREADS`, and
`NUMEXPR_NUM_THREADS`. The existing `ThreadSettings` helper sets both
PyTorch compute and interop threads to one.

Some guard tests intentionally write temporary Python fixtures. `rvt-test`
copies the immutable checkout into an ephemeral worker-owned directory for
tests only. The production source remains root-owned and non-writable.

## Test Results

The exact critical suite passed:

`359 passed, 0 failed in 61.45 s`

The complete suite in the exact pinned Linux image produced:

`2967 passed, 3 failed, 0 xfailed, 0 xpassed in 341.78 s`

The same two relevant test files pass on the previous macOS/arm64 host:

`9 passed, 0 failed`

The earlier upgraded-stack probe produced 38 failures. Thirty-five were
operational test-checkout permission effects and disappeared when tests used
the ephemeral writable checkout. The three semantic failures remained under
the exact previously qualified versions.

## Semantic Mismatches

### FD24 Batch Isolation

`test_adding_unrelated_ego_graphs_cannot_change_target_output` observed an
absolute difference of `1.043081283569336e-07`, above the frozen `1e-7`
tolerance.

`test_parallel_candidate_evaluation_does_not_mix_candidates` observed an
absolute difference of `1.1175870895385742e-07`, also above the frozen
tolerance.

### Layout Compilation

For `train-f2-01`:

| Field | Frozen artifact | Linux recompilation |
|---|---:|---:|
| `heading_radians` | `0.032866494018365604` | `0.0328664940183656` |
| layout self-hash | `1eacd9d6...48542c` | `2e978e2b...098d1` |

The one-binary64-value difference is sufficient to change canonical JSON and
the scientific layout identity. Changing a rounding rule, replacing persisted
values, loosening the test, or changing the compiler would be a scientific
semantic repair and is prohibited in this qualification.

Because semantic equality is already false, a host/container semantic digest,
worker scaling, chunk scaling, timeout selection, capacity projection, H4
classification, and production preflight cannot produce authorization.

## Authorization

| Scope | Status |
|---|---|
| RECOVERABILITY_GENERATION | NOT_AUTHORIZED_SEMANTIC_GATE_FAILED |
| RESIDUAL_V2_GENERATION | NOT_AUTHORIZED_SEMANTIC_GATE_FAILED |
| STUDY_A_TRAIN_VALIDATION | NOT_AUTHORIZED_SEMANTIC_GATE_FAILED |
| STUDY_A_N24_ZERO_SHOT | SEALED_NOT_AUTHORIZED |
| STUDY_B | NOT_AUTHORIZED |
| FINAL_TEST | SEALED_NOT_AUTHORIZED |

No official command plan was prepared or executed.

## Isolation

- final-test accesses: 0;
- Study A N24 accesses: 0;
- official recoverability rows: 0;
- official residual rows: 0;
- official scientific shards: 0;
- checkpoints: 0;
- optimizer states: 0;
- training operations: 0.

## Evidence

Canonical target record:
`results/rvt_fd24/rb21_windows_docker_generation_readiness_v1.json`.

Its canonical self-hash is:

`90689f48419bcc738cb6ba37427951bd250629419cf7504464dd6f718f12b1b8`

The target is technically capable, but it is not the official Phase-9
generation environment under the frozen exact-semantics contract. Any next
step requires an explicit scientific decision about cross-platform numeric
semantics; this operational task does not make that decision.
