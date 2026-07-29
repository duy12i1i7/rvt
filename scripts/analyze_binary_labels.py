"""Label-quality gate analysis. Reads the V2 labels; trains nothing."""
from __future__ import annotations

import csv
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from rvt_swarm.provenance import stamp  # noqa: E402

OUT = REPO / "results" / "binary_mode_pilot"
N_ROLLOUTS = 4


def main() -> int:
    rows = list(csv.DictReader((OUT / "task_recovery_labels.csv").open()))
    prov = stamp()
    fl, it = float, int

    # ---- pair keep/line by state -----------------------------------------
    by_state = defaultdict(dict)
    meta = {}
    for r in rows:
        by_state[r["state_id"]][r["mode"]] = r
        meta[r["state_id"]] = (r["split"], r["family"], it(r["team_size"]))
    states = {s: v for s, v in by_state.items() if {"keep", "line"} <= set(v)}

    joint_rows, joint_counts = [], defaultdict(Counter)
    near_half = 0
    for sid, v in states.items():
        split, fam, n = meta[sid]
        k, l = it(v["keep"]["task_recovery_label"]), it(v["line"]["task_recovery_label"])
        pk, pl = fl(v["keep"]["empirical_recovery_probability"]), fl(v["line"]["empirical_recovery_probability"])
        cat = ("both_succeed" if k and l else "both_fail" if not k and not l
               else "keep_only" if k else "line_only")
        for key in (("overall", "all"), ("split", split), ("family", fam),
                    ("team_size", str(n)), ("family_x_team", f"{fam}|{n}"),
                    ("family_x_split", f"{fam}|{split}")):
            joint_counts[key][cat] += 1
            joint_counts[key]["total"] += 1
        near_half += int(abs(pk - 0.5) < 0.13) + int(abs(pl - 0.5) < 0.13)
        joint_rows.append({**prov, "state_id": sid, "split": split, "family": fam,
                           "team_size": n, "keep_label": k, "line_label": l,
                           "keep_prob": pk, "line_prob": pl, "joint_outcome": cat,
                           "modes_disagree": int(k != l)})

    with (OUT / "label_joint_outcomes.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=sorted({k for r in joint_rows for k in r}))
        w.writeheader(); w.writerows(joint_rows)

    print(f"unique states with both modes: {len(states)}   label rows: {len(rows)}")
    print(f"total rollouts: {len(rows) * N_ROLLOUTS}   rollouts per state-mode: {N_ROLLOUTS}")

    print(f"\n{'scope':14s}{'key':26s}{'n':>5s}{'both_fail':>10s}{'both_ok':>9s}"
          f"{'keep_only':>10s}{'line_only':>10s}{'disagree':>9s}")
    for (scope, key), c in sorted(joint_counts.items()):
        t = c["total"]
        dis = (c["keep_only"] + c["line_only"]) / t
        print(f"{scope:14s}{key:26s}{t:5d}{c['both_fail']/t:10.3f}{c['both_succeed']/t:9.3f}"
              f"{c['keep_only']/t:10.3f}{c['line_only']/t:10.3f}{dis:9.3f}")

    # ---- family x mode x team size ---------------------------------------
    print(f"\n{'family':18s}{'mode':6s}{'N':>3s}{'split':>7s}{'n':>5s}{'pos_rate':>10s}{'mean_p':>9s}")
    fxmxn = []
    for fam in sorted({r["family"] for r in rows}):
        for mode in ("keep", "line"):
            for n in (4, 6):
                for split in ("train", "val"):
                    sub = [r for r in rows if r["family"] == fam and r["mode"] == mode
                           and it(r["team_size"]) == n and r["split"] == split]
                    if not sub:
                        continue
                    pr = float(np.mean([it(r["task_recovery_label"]) for r in sub]))
                    mp = float(np.mean([fl(r["empirical_recovery_probability"]) for r in sub]))
                    fxmxn.append({**prov, "scope": "family_x_mode_x_team_x_split",
                                  "family": fam, "mode": mode, "team_size": n,
                                  "split": split, "n": len(sub), "positive_rate": pr,
                                  "mean_empirical_probability": mp})
                    print(f"{fam:18s}{mode:6s}{n:3d}{split:>7s}{len(sub):5d}{pr:10.3f}{mp:9.3f}")

    # ---- empirical probability distribution ------------------------------
    print("\nempirical recovery probability distribution (4 rollouts -> 0,.25,.5,.75,1):")
    for mode in ("keep", "line"):
        ps = [fl(r["empirical_recovery_probability"]) for r in rows if r["mode"] == mode]
        c = Counter(round(p, 2) for p in ps)
        tot = len(ps)
        print(f"  {mode:5s} " + "  ".join(f"{v}:{c.get(v,0)/tot:.3f}"
                                          for v in (0.0, 0.25, 0.5, 0.75, 1.0)))
        unst = sum(1 for p in ps if 0.0 < p < 1.0)
        print(f"        unanimous across 4 rollouts: {1-unst/tot:.3f}   "
              f"split-decision: {unst/tot:.3f}   near-0.5 (p==0.5): {c.get(0.5,0)/tot:.3f}")

    # ---- split consistency flags -----------------------------------------
    print("\nsplit consistency (flag if |train-val| positive-rate gap > 0.20):")
    flagged = []
    for fam in sorted({r["family"] for r in rows}):
        for mode in ("keep", "line"):
            tr = [it(r["task_recovery_label"]) for r in rows
                  if r["family"] == fam and r["mode"] == mode and r["split"] == "train"]
            va = [it(r["task_recovery_label"]) for r in rows
                  if r["family"] == fam and r["mode"] == mode and r["split"] == "val"]
            if not tr or not va:
                continue
            gap = abs(np.mean(tr) - np.mean(va))
            mark = "  <-- FLAG" if gap > 0.20 else ""
            if gap > 0.20:
                flagged.append((fam, mode, float(gap)))
            print(f"  {fam:18s}{mode:6s} train={np.mean(tr):.3f} val={np.mean(va):.3f} "
                  f"gap={gap:.3f}{mark}")

    # ---- gates -------------------------------------------------------------
    print("\n=== LABEL GATES ===")
    ok = True
    for mode in ("keep", "line"):
        pr = float(np.mean([it(r["task_recovery_label"]) for r in rows if r["mode"] == mode]))
        g = 0.05 < pr < 0.95
        ok &= g
        print(f"  G1 {mode:5s} global positive rate {pr:.3f}  {'PASS' if g else 'FAIL'}")
    for fam in ("line_corridor", "keep_line_keep"):
        c = joint_counts[("family", fam)]
        t = c["total"]
        dis = (c["keep_only"] + c["line_only"]) / t
        has_line_only = c["line_only"] > 0
        both = all(0 < float(np.mean([it(r["task_recovery_label"]) for r in rows
                   if r["family"] == fam and r["mode"] == m])) < 1 for m in ("keep", "line"))
        g = both and dis >= 0.05 and has_line_only
        ok &= g
        print(f"  G2 {fam:16s} disagree={dis:.3f} line_only={c['line_only']} "
              f"both_classes={both}  {'PASS' if g else 'FAIL'}")
    print(f"  G4 split-consistency flags: {len(flagged)} {flagged if flagged else ''}")
    print(f"\nOVERALL: {'PASS' if ok else 'FAIL'}")

    with (OUT / "label_statistics_detailed.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=sorted({k for r in fxmxn for k in r}))
        w.writeheader(); w.writerows(fxmxn)
    print(f"wrote {OUT/'label_joint_outcomes.csv'} and label_statistics_detailed.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
