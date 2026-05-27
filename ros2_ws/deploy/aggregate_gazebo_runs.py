#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List

import numpy as np


DEFAULT_METRICS = [
    "success",
    "goal_reached",
    "collision_free",
    "form_ok",
    "form_rms",
    "rr_collision",
    "ro_collision",
    "deadlock",
    "recoverability_proxy",
]


def _load_runs(log_dir: Path) -> List[dict]:
    runs: List[dict] = []
    for path in sorted(log_dir.glob("*.json")):
        try:
            with path.open("r", encoding="utf-8") as f:
                payload = json.load(f)
        except Exception:
            continue
        payload["_path"] = str(path)
        runs.append(payload)
    return runs


def _ci95(values: np.ndarray) -> tuple[float, float]:
    if values.size == 0:
        return float("nan"), float("nan")
    if values.size == 1:
        v = float(values[0])
        return v, v
    mean = float(np.mean(values))
    std = float(np.std(values, ddof=1))
    half_width = 1.96 * std / max(np.sqrt(values.size), 1e-6)
    return mean - half_width, mean + half_width


def _permutation_pvalue(a: np.ndarray, b: np.ndarray, draws: int, seed: int) -> float:
    if a.size == 0 or b.size == 0:
        return float("nan")
    rng = np.random.default_rng(seed)
    pooled = np.concatenate([a, b])
    n_a = a.size
    obs = abs(float(np.mean(a) - np.mean(b)))
    count = 0
    for _ in range(draws):
        perm = rng.permutation(pooled)
        diff = abs(float(np.mean(perm[:n_a]) - np.mean(perm[n_a:])))
        if diff >= obs:
            count += 1
    return (count + 1) / (draws + 1)


def aggregate(log_dir: Path, metrics: List[str], reference: str, draws: int, seed: int) -> dict:
    grouped: Dict[str, List[dict]] = {}
    for run in _load_runs(log_dir):
        method = str(run.get("method") or run.get("metrics", {}).get("method") or "unknown")
        grouped.setdefault(method, []).append(run)

    report: dict = {"log_dir": str(log_dir), "methods": {}}
    for method, runs in sorted(grouped.items()):
        method_entry = {
            "n_runs": len(runs),
            "runs": [Path(run["_path"]).name for run in runs],
            "metrics": {},
        }
        for metric in metrics:
            values = np.asarray(
                [float(run.get("metrics", {}).get(metric, np.nan)) for run in runs],
                dtype=np.float64,
            )
            values = values[np.isfinite(values)]
            if values.size == 0:
                continue
            ci_low, ci_high = _ci95(values)
            method_entry["metrics"][metric] = {
                "mean": float(np.mean(values)),
                "std": float(np.std(values, ddof=1)) if values.size > 1 else 0.0,
                "ci95_low": float(ci_low),
                "ci95_high": float(ci_high),
                "n": int(values.size),
            }
        report["methods"][method] = method_entry

    if reference in report["methods"]:
        ref_runs = grouped[reference]
        ref_success = np.asarray(
            [float(run.get("metrics", {}).get("success", np.nan)) for run in ref_runs],
            dtype=np.float64,
        )
        ref_success = ref_success[np.isfinite(ref_success)]
        for method, runs in grouped.items():
            if method == reference:
                continue
            method_success = np.asarray(
                [float(run.get("metrics", {}).get("success", np.nan)) for run in runs],
                dtype=np.float64,
            )
            method_success = method_success[np.isfinite(method_success)]
            if ref_success.size == 0 or method_success.size == 0:
                continue
            report["methods"][method]["vs_reference"] = {
                "reference": reference,
                "success_mean_delta": float(np.mean(ref_success) - np.mean(method_success)),
                "success_permutation_pvalue": float(
                    _permutation_pvalue(ref_success, method_success, draws=draws, seed=seed)
                ),
            }

    return report


def _print_summary(report: dict) -> None:
    print(f"log_dir: {report['log_dir']}")
    print()
    for method, entry in sorted(report["methods"].items()):
        print(f"{method}  (n={entry['n_runs']})")
        for metric, stats in sorted(entry["metrics"].items()):
            print(
                f"  {metric:20s} mean={stats['mean']:.4f}  std={stats['std']:.4f}  "
                f"95%CI=[{stats['ci95_low']:.4f}, {stats['ci95_high']:.4f}]"
            )
        if "vs_reference" in entry:
            cmp = entry["vs_reference"]
            print(
                f"  vs {cmp['reference']}: delta_success={cmp['success_mean_delta']:.4f}, "
                f"permutation_p={cmp['success_permutation_pvalue']:.4f}"
            )
        print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Aggregate Gazebo RVT swarm run summaries.")
    parser.add_argument("--log-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--reference", default="rvt_swarm")
    parser.add_argument("--metrics", nargs="*", default=DEFAULT_METRICS)
    parser.add_argument("--permutation-draws", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    report = aggregate(
        log_dir=args.log_dir.expanduser().resolve(),
        metrics=list(args.metrics),
        reference=args.reference,
        draws=args.permutation_draws,
        seed=args.seed,
    )
    _print_summary(report)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)


if __name__ == "__main__":
    main()
