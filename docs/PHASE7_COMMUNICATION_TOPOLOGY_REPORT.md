# Phase 7 Communication Topology Report

The matrix covers path, ring, star, bounded-degree geometric, sparse random
connected, complete, and temporary-disconnection graphs for N in
{5, 8, 12, 16, 24}: 35 cells.

For every one of the 30 continuously connected cells:

- graph diameter equals the configured `D_max`;
- `k_intent = k_score = k_ready = k_confirm = D_max` under zero message delay;
- intent, distributed-min score, all-ready, and confirmation agreement succeed;
- no partial commitment occurs.

All five temporary-disconnection cells lose one causal round at the declared
cut, report incomplete readiness membership, retain the source topology, create
zero mode epochs, and record `temporary_disconnection_exceeded_round_contract`.
No component is reported as whole-team success.

| N | path D / bytes | ring D / bytes | star D / bytes | bounded D / bytes | sparse D / bytes | complete D / bytes |
|---:|---:|---:|---:|---:|---:|---:|
| 5 | 4 / 77,454 | 2 / 27,029 | 2 / 25,486 | 2 / 27,029 | 3 / 58,247 | 1 / 7,910 |
| 8 | 7 / 264,528 | 4 / 123,488 | 2 / 32,920 | 2 / 47,680 | 4 / 136,832 | 1 / 9,995 |
| 12 | 11 / 932,922 | 6 / 418,682 | 2 / 50,108 | 3 / 176,879 | 5 / 360,321 | 1 / 14,797 |
| 16 | 15 / 2,234,028 | 8 / 947,942 | 2 / 67,298 | 4 / 417,482 | 6 / 835,300 | 1 / 19,603 |
| 24 | 23 / 7,982,488 | 12 / 3,264,254 | 2 / 101,620 | 6 / 1,501,232 | 7 / 1,972,652 | 1 / 29,203 |

Transition execution succeeds for all six connected N5 cells in this matrix.
At N>=8, the protocol agreements still pass but the unchanged controller/safety
stack aborts KEEP->LINE on projection infeasibility.  Agreement correctness and
physical transition success are therefore reported separately.

The complete cell records, including component behavior, timeout, latency and
actual serialized bytes, are in
`results/phase7_transition_protocol/communication_topology_matrix.json`.

P7-G4 and P7-G9 pass under their declared connected contract.
