# Phase 4 Ego Graph Scaling Report

## Scope and method

This is a graph-construction microbenchmark only. It did not step an
environment, score mission success, train a model, access a final-test layout,
or qualify any topology in closed loop.

Platform: Apple M4 Pro arm64, Python 3.9.6, PyTorch 2.8.0. Each cell constructs
one COMPACT-conditioned V2 graph for every robot, warms the path, then reports
the median of 12 sequential simulator passes. Obstacles vary from zero to three
by robot, averaging 1.2 for N=5, 1.167 for N=6, and 1.5 otherwise.

Communication patterns are:

- `path`: sparse path-like neighbours;
- `ring`: exactly two peers per robot;
- `bounded`: at most four cyclic geometric peers;
- `complete`: every other robot, diagnostic stress only.

All peer positions are within the configured communication range. Construction
includes tensor materialization. Serialization and batching are measured after
construction. Latencies are machine-specific engineering measurements, not a
scientific performance claim.

`avg deg` is directed edges divided by nodes. `max inc` is the maximum total
directed edge incidence at a root. `graph B` and `serial B` are per-graph
averages; `batch B` is the disjoint batch for all N robot graphs.

## Results

| N | Pattern | Graphs/step | Peer avg | Obs avg | Edge avg | Avg deg | Max inc | ms/robot | Total ms | Graph B | Batch B | Serial B |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 5 | path | 5 | 1.600 | 1.200 | 5.600 | 1.474 | 10 | 1.3580 | 6.7901 | 1,371 | 7,352 | 4,882 |
| 5 | ring | 5 | 2.000 | 1.200 | 6.400 | 1.524 | 10 | 1.5525 | 7.7624 | 1,541 | 8,248 | 5,310 |
| 5 | bounded | 5 | 4.000 | 1.200 | 10.400 | 1.677 | 14 | 2.6836 | 13.4179 | 2,389 | 12,728 | 7,547 |
| 5 | complete | 5 | 4.000 | 1.200 | 10.400 | 1.677 | 14 | 2.6933 | 13.4667 | 2,389 | 12,728 | 7,547 |
| 6 | path | 6 | 1.667 | 1.167 | 5.667 | 1.478 | 10 | 1.4735 | 8.8410 | 1,385 | 8,912 | 4,846 |
| 6 | ring | 6 | 2.000 | 1.167 | 6.333 | 1.520 | 10 | 1.7061 | 10.2367 | 1,527 | 9,808 | 5,202 |
| 6 | bounded | 6 | 4.000 | 1.167 | 10.333 | 1.676 | 14 | 2.9039 | 17.4232 | 2,375 | 15,184 | 7,410 |
| 6 | complete | 6 | 5.000 | 1.167 | 12.333 | 1.721 | 16 | 3.5477 | 21.2864 | 2,799 | 17,872 | 8,476 |
| 8 | path | 8 | 1.750 | 1.500 | 6.500 | 1.529 | 10 | 1.7623 | 14.0987 | 1,562 | 13,376 | 5,280 |
| 8 | ring | 8 | 2.000 | 1.500 | 7.000 | 1.556 | 10 | 1.9379 | 15.5028 | 1,668 | 14,272 | 5,547 |
| 8 | bounded | 8 | 4.000 | 1.500 | 11.000 | 1.692 | 14 | 3.3739 | 26.9909 | 2,516 | 21,440 | 7,765 |
| 8 | complete | 8 | 7.000 | 1.500 | 17.000 | 1.789 | 20 | 5.4027 | 43.2219 | 3,788 | 32,192 | 10,963 |
| 12 | path | 12 | 1.833 | 1.500 | 6.667 | 1.538 | 10 | 2.2647 | 27.1763 | 1,597 | 20,512 | 5,364 |
| 12 | ring | 12 | 2.000 | 1.500 | 7.000 | 1.556 | 10 | 2.4059 | 28.8705 | 1,668 | 21,408 | 5,542 |
| 12 | bounded | 12 | 4.000 | 1.500 | 11.000 | 1.692 | 14 | 4.2146 | 50.5748 | 2,516 | 32,160 | 7,769 |
| 12 | complete | 12 | 11.000 | 1.500 | 25.000 | 1.852 | 28 | 10.5894 | 127.0732 | 5,484 | 69,792 | 15,251 |
| 16 | path | 16 | 1.875 | 1.500 | 6.750 | 1.543 | 10 | 2.7981 | 44.7700 | 1,615 | 27,648 | 5,406 |
| 16 | ring | 16 | 2.000 | 1.500 | 7.000 | 1.556 | 10 | 2.9197 | 46.7157 | 1,668 | 28,544 | 5,540 |
| 16 | bounded | 16 | 4.000 | 1.500 | 11.000 | 1.692 | 14 | 5.1282 | 82.0507 | 2,516 | 42,880 | 7,772 |
| 16 | complete | 16 | 15.000 | 1.500 | 33.000 | 1.886 | 36 | 17.2425 | 275.8797 | 7,180 | 121,728 | 19,496 |
| 24 | path | 24 | 1.917 | 1.500 | 6.833 | 1.547 | 10 | 3.8046 | 91.3102 | 1,633 | 41,920 | 5,486 |
| 24 | ring | 24 | 2.000 | 1.500 | 7.000 | 1.556 | 10 | 3.9584 | 95.0009 | 1,668 | 42,816 | 5,575 |
| 24 | bounded | 24 | 4.000 | 1.500 | 11.000 | 1.692 | 14 | 6.9510 | 166.8230 | 2,516 | 64,320 | 7,812 |
| 24 | complete | 24 | 23.000 | 1.500 | 49.000 | 1.922 | 52 | 35.4728 | 851.3467 | 10,572 | 268,608 | 28,044 |

## Interpretation

Sparse and ring graph sizes remain bounded as N increases because a robot
stores only its own local degree. The sequential simulator total grows with N
because it constructs N independent graphs. The bounded-degree N=24 case has
four peer nodes, 1.5 obstacle nodes, 11 edges, 2,516 bytes per graph, and 6.951
ms construction per robot on this platform.

The complete stress case grows with N as expected. At N=24 it has 23 peer nodes
per graph, 49 average edges including obstacles, 10,572 tensor bytes per graph,
and 35.4728 ms construction per robot. It completed without a fixed-size
failure, but it is not the default deployment assumption and provides no
scientific N=24 validity claim.
