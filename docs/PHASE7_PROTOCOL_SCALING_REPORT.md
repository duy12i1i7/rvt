# Phase 7 Protocol Scaling Report

Timing uses `perf_counter` around the actual Python implementation.  Values
below are median / p95 / p99 seconds for path-graph diagnostics.  Serialization
and ingestion sample actual framed messages; readiness and controller values
are per robot call.  Metric V3 remains offline.

| N / D | serialize | ingest | readiness | controller | Metric V3 | communication latency | bytes |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 5 / 4 | 1.10e-5 / 1.53e-5 / 2.69e-5 | 5.08e-6 / 9.44e-6 / 1.37e-5 | 5.32e-4 / 6.42e-4 / 6.70e-4 | 4.23e-4 / 5.01e-4 / 5.65e-4 | 1.90e-5 / 1.97e-5 / 2.41e-5 | 2.4 s | 77,454 |
| 8 / 7 | 1.15e-5 / 1.41e-5 / 2.18e-5 | 5.46e-6 / 7.86e-6 / 1.16e-5 | 7.45e-4 / 7.83e-4 / 8.04e-4 | 6.80e-4 / 7.39e-4 / 8.04e-4 | 2.04e-5 / 2.58e-5 / 2.59e-5 | 4.2 s | 264,528 |
| 12 / 11 | 1.14e-5 / 1.38e-5 / 2.15e-5 | 5.38e-6 / 6.54e-6 / 1.05e-5 | 9.31e-4 / 1.01e-3 / 1.05e-3 | 1.02e-3 / 1.11e-3 / 1.18e-3 | 2.17e-5 / 2.63e-5 / 2.72e-5 | 6.6 s | 932,922 |
| 16 / 15 | 1.07e-5 / 1.26e-5 / 1.85e-5 | 5.04e-6 / 6.42e-6 / 1.10e-5 | 1.08e-3 / 1.18e-3 / 1.20e-3 | 1.28e-3 / 1.42e-3 / 1.46e-3 | 2.21e-5 / 2.63e-5 / 2.65e-5 | 9.0 s | 2,234,028 |
| 24 / 23 | 1.09e-5 / 1.37e-5 / 2.17e-5 | 5.17e-6 / 9.63e-6 / 1.20e-5 | 1.50e-3 / 1.59e-3 / 1.60e-3 | 1.67e-3 / 2.37e-3 / 2.48e-3 | 2.43e-5 / 3.04e-5 / 3.06e-5 | 13.8 s | 7,982,488 |

Event processing median rises from 0.284 ms at N5 to 0.755 ms at N24.
Readiness cost grows with local records; wire cost grows strongly with both N
and diameter because duplicate-suppressed origin records are retransmitted for
bounded-round flooding.  At N24, changing path D=23 to complete D=1 reduces the
same diagnostic from 7,982,488 to 29,203 bytes and communication latency from
13.8 to 0.6 seconds.

Only the N5 KEEP->LINE path cell has a completed total-transition latency in
this scaling arm: 7.95 seconds.  N>=8 cells abort during controller execution,
so no completion latency is fabricated.  Peak process resident memory during
the complete qualification was 243,974,144 bytes.

These are Python simulator measurements with synthetic scores.  They are not a
claim of full real-time RVT learned inference.  Full records are in
`results/phase7_transition_protocol/protocol_scaling.json`.
