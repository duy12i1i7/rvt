# Topology Nominal Graph Audit

## 1. Graph meaning

The nominal topology graph describes desired formation constraints. It is
static mission geometry. The dynamic communication graph is range/loss/delay
dependent and may contain different edges. No connectivity claim about one is
inferred from the other.

Rules:

- KEEP: horizontal and vertical square-like grid adjacency;
- COMPACT: horizontal and vertical two-column ladder adjacency;
- LINE: adjacent persistent-rank chain.

All edges provide both directed pairwise offsets by antisymmetry. Graphs are
deterministic and permutation-equivariant when robot identities and their role
metadata are relabelled together.

## 2. Statistics

| N | Topology | Nodes | Edges | Average degree | Maximum degree | Diameter | Connected | Role symmetry |
|---:|---|---:|---:|---:|---:|---:|---|---|
| 5 | KEEP | 5 | 5 | 2.000 | 3 | 3 | Yes | Incomplete final grid row |
| 5 | COMPACT | 5 | 5 | 2.000 | 3 | 3 | Yes | Incomplete final ladder row |
| 5 | LINE | 5 | 4 | 1.600 | 2 | 4 | Yes | Reflection about center rank |
| 6 | KEEP | 6 | 7 | 2.333 | 3 | 3 | Yes | Full 2x3 grid |
| 6 | COMPACT | 6 | 7 | 2.333 | 3 | 3 | Yes | Full 3x2 ladder |
| 6 | LINE | 6 | 5 | 1.667 | 2 | 5 | Yes | Reflection about midpoint |
| 8 | KEEP | 8 | 10 | 2.500 | 4 | 4 | Yes | Incomplete 3x3 grid |
| 8 | COMPACT | 8 | 10 | 2.500 | 3 | 4 | Yes | Full 4x2 ladder |
| 8 | LINE | 8 | 7 | 1.750 | 2 | 7 | Yes | Reflection about midpoint |
| 12 | KEEP | 12 | 17 | 2.833 | 4 | 5 | Yes | Full 3x4 grid |
| 12 | COMPACT | 12 | 16 | 2.667 | 3 | 6 | Yes | Full 6x2 ladder |
| 12 | LINE | 12 | 11 | 1.833 | 2 | 11 | Yes | Reflection about midpoint |
| 16 | KEEP | 16 | 24 | 3.000 | 4 | 6 | Yes | Full 4x4 grid |
| 16 | COMPACT | 16 | 22 | 2.750 | 3 | 8 | Yes | Full 8x2 ladder |
| 16 | LINE | 16 | 15 | 1.875 | 2 | 15 | Yes | Reflection about midpoint |
| 24 | KEEP | 24 | 38 | 3.167 | 4 | 8 | Yes | Incomplete 5x5 grid |
| 24 | COMPACT | 24 | 34 | 2.833 | 3 | 12 | Yes | Full 12x2 ladder |
| 24 | LINE | 24 | 23 | 1.917 | 2 | 23 | Yes | Reflection about midpoint |

Degree is bounded independently of N. No topology uses an all-to-all graph or
one arbitrary k-nearest-neighbour rule. The graph rule follows each template's
lattice structure.
