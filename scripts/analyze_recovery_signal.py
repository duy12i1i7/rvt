"""Task 5 analysis — score quality against realised recovery outcomes."""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
OUT = REPO / "results" / "method_audit"

PREDICTORS = [
    ("score_adjusted", +1, "learned score (uncertainty-adjusted)"),
    ("score_raw", +1, "learned score (raw head)"),
    ("topology_logit", +1, "topology classifier logit"),
    ("rollout_utility", +1, "raw counterfactual rollout utility"),
    ("min_clearance", +1, "minimum clearance"),
    ("formation_error", -1, "formation error (negated)"),
    ("distance_to_goal", -1, "distance to goal (negated)"),
    ("instantaneous_risk", -1, "instantaneous collision risk (negated)"),
]


def auroc(y, s):
    y = np.asarray(y); s = np.asarray(s, dtype=float)
    if len(np.unique(y)) < 2:
        return float("nan")
    order = np.argsort(s)
    ranks = np.empty(len(s), float)
    ranks[order] = np.arange(1, len(s) + 1)
    # average ranks for ties
    _, inv, cnt = np.unique(s, return_inverse=True, return_counts=True)
    sums = np.zeros(len(cnt)); np.add.at(sums, inv, ranks)
    ranks = (sums / cnt)[inv]
    n1, n0 = y.sum(), len(y) - y.sum()
    return float((ranks[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def auprc(y, s):
    y = np.asarray(y); s = np.asarray(s, float)
    if y.sum() == 0:
        return float("nan")
    order = np.argsort(-s); y = y[order]
    tp = np.cumsum(y); prec = tp / np.arange(1, len(y) + 1); rec = tp / y.sum()
    return float(np.sum(np.diff(np.concatenate([[0], rec])) * prec))


def brier(y, p):
    return float(np.mean((np.asarray(p, float) - np.asarray(y, float)) ** 2))


def ece(y, p, bins=10):
    y = np.asarray(y, float); p = np.clip(np.asarray(p, float), 0, 1)
    edges = np.quantile(p, np.linspace(0, 1, bins + 1))
    edges[0], edges[-1] = -np.inf, np.inf
    tot = 0.0
    for i in range(bins):
        m = (p > edges[i]) & (p <= edges[i + 1])
        if m.sum():
            tot += m.mean() * abs(y[m].mean() - p[m].mean())
    return float(tot)


def kendall_tau(a, b):
    a = np.asarray(a, float); b = np.asarray(b, float)
    n = len(a)
    if n < 2:
        return float("nan")
    c = d = 0
    for i in range(n):
        for j in range(i + 1, n):
            s = np.sign(a[i] - a[j]) * np.sign(b[i] - b[j])
            if s > 0: c += 1
            elif s < 0: d += 1
    return float((c - d) / max(c + d, 1))


def main():
    rows = list(csv.DictReader((OUT / "recovery_signal_predictions.csv").open()))
    y = np.array([int(r["recovered"]) for r in rows])
    emp = np.array([float(r["empirical_recovery_rate"]) for r in rows])
    print(f"rows={len(rows)}  states={len(rows)//3}  positive rate={y.mean():.3f}")
    print(f"\n{'predictor':44s}{'AUROC':>8s}{'AUPRC':>8s}{'Brier':>8s}{'ECE':>8s}"
          f"{'FalseSafe':>11s}{'FalseUnrec':>12s}")
    results = []
    for key, sign, label in PREDICTORS:
        s = sign * np.array([float(r[key]) for r in rows])
        a, ap = auroc(y, s), auprc(y, s)
        # sigmoid-map to a probability for Brier/ECE (scores are not probabilities)
        z = (s - s.mean()) / max(s.std(), 1e-9)
        p = 1.0 / (1.0 + np.exp(-z))
        thr = np.median(s)
        pred_pos = s >= thr
        fs = float(((pred_pos) & (y == 0)).sum() / max((y == 0).sum(), 1))
        fu = float(((~pred_pos) & (y == 1)).sum() / max((y == 1).sum(), 1))
        print(f"{label:44s}{a:8.3f}{ap:8.3f}{brier(y,p):8.3f}{ece(y,p):8.3f}{fs:11.3f}{fu:12.3f}")
        results.append({"predictor": key, "label": label, "auroc": a, "auprc": ap,
                        "brier": brier(y, p), "ece": ece(y, p),
                        "false_safe_rate": fs, "false_unrecoverable_rate": fu})

    # per-state mode ranking
    states = {}
    for r in rows:
        states.setdefault((r["scenario"], r["team_size"], r["episode_seed"], r["step"]), []).append(r)
    print(f"\n{'predictor':44s}{'top1_acc':>10s}{'pair_acc':>10s}{'kendall':>10s}{'states':>8s}")
    for key, sign, label in PREDICTORS:
        top1 = pair = pair_n = 0; taus = []; n = 0
        for _, group in states.items():
            if len(group) < 2:
                continue
            e = np.array([float(g["empirical_recovery_rate"]) for g in group])
            s = sign * np.array([float(g[key]) for g in group])
            if e.max() == e.min():
                continue
            n += 1
            top1 += int(e[int(np.argmax(s))] == e.max())
            for i in range(len(group)):
                for j in range(i + 1, len(group)):
                    if e[i] != e[j]:
                        pair_n += 1
                        pair += int(np.sign(s[i] - s[j]) == np.sign(e[i] - e[j]))
            taus.append(kendall_tau(s, e))
        t1 = top1 / max(n, 1); pa = pair / max(pair_n, 1); kt = float(np.nanmean(taus)) if taus else float("nan")
        print(f"{label:44s}{t1:10.3f}{pa:10.3f}{kt:10.3f}{n:8d}")
        for r in results:
            if r["predictor"] == key:
                r.update(top1_accuracy=t1, pairwise_accuracy=pa, kendall_tau=kt,
                         discriminative_states=n)

    print("\nreliability (learned adjusted score, 5 equal-mass bins):")
    s = np.array([float(r["score_adjusted"]) for r in rows])
    q = np.quantile(s, np.linspace(0, 1, 6)); q[0], q[-1] = -np.inf, np.inf
    for i in range(5):
        m = (s > q[i]) & (s <= q[i + 1])
        if m.sum():
            print(f"  bin {i+1}: score[{q[i]:+.3f},{q[i+1]:+.3f}] n={m.sum():4d} "
                  f"mean_score={s[m].mean():+.3f}  empirical_recovery={emp[m].mean():.3f}")

    with (OUT / "recovery_signal_metrics.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=sorted({k for r in results for k in r}))
        w.writeheader(); w.writerows(results)
    print(f"\nwrote {OUT/'recovery_signal_metrics.csv'}")


if __name__ == "__main__":
    main()
