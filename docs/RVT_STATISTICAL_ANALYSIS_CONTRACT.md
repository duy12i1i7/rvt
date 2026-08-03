# RVT Statistical Analysis Contract

Schema: `rvt-statistical-analysis/v1`.

The pairing key is split, family, layout hash, team size, initial-condition
seed, communication seed, dynamic-obstacle seed and evaluation seed. Binary
paired outcomes use a 10,000-resample paired bootstrap 95% interval and McNemar
test (exact when fewer than 25 discordant pairs). Continuous outcomes use the
same paired bootstrap and a 10,000-sign-flip paired permutation test; Wilcoxon
signed-rank is used when ties invalidate permutation assumptions.

Holm correction at familywise alpha 0.05 covers these six primary comparisons:

1. full base method versus local geometric selector;
2. full base method versus direct classifier;
3. full base method versus strongest fixed deployable baseline;
4. online full method versus always COMPACT;
5. online full method versus always LINE;
6. decentralized full method versus centralized diagnostic reference.

The bootstrap unit is the paired episode, with a layout-cluster sensitivity
analysis. Failed episodes remain paired as task failures and horizon completion
times. Only predeclared invalid geometry may be excluded, with reasons
published. Results are shown per seed and as an equal-weight three-seed
aggregate. Report absolute/relative paired effects and intervals; robot rows and
timesteps are never independent hypothesis-test units.
