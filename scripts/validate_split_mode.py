"""Task 8 — is split mode mechanically feasible, or is it dead weight?

Deterministic (no perturbation), oracle-only, validation + train layouts.
No learned model. Split is not preserved by assumption: if it cannot be shown to
work on a hand-constructed feasible state, it is removed.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from rvt_swarm.config import Config  # noqa: E402
from rvt_swarm.controllers import expert_action  # noqa: E402
from rvt_swarm.environment import SwarmFormationEnv  # noqa: E402
from rvt_swarm.layouts import build_layouts  # noqa: E402
from rvt_swarm.metrics import EpisodeAccumulator  # noqa: E402
from rvt_swarm.regions import regions_for_layout  # noqa: E402
from rvt_swarm.train import git_commit  # noqa: E402

OUT = REPO / "results" / "scenario_headroom_v2"
MODES = {0: "keep", 2: "line", 3: "split"}


def template_geometry_audit(cfg: Config, n: int = 6) -> dict:
    """Numeric audit of the split template itself, independent of any scenario."""
    env = SwarmFormationEnv(cfg)
    env.reset(n, "cluttered", seed=1)
    ec = cfg.env
    rows = {}
    for scale in (1.0, ec.min_formation_scale):
        env.state.formation_scale = scale
        env.state.subteam_ids = env._subteam_assignments()
        off = env.desired_offsets(mode=3, scale=scale)
        lateral = np.abs(off[:, 1])
        d = np.linalg.norm(off[:, None] - off[None, :], axis=-1)
        np.fill_diagonal(d, np.inf)
        spacing = ec.nominal_spacing * scale
        lane_gap = max(ec.nominal_spacing, spacing + ec.min_rr_distance)
        rows[f"scale_{scale:.3f}"] = {
            "formation_scale": scale,
            "lane_gap": lane_gap,
            "lane_offset": lane_gap / 2.0,
            "max_lateral_extent": float(lateral.max()),
            "min_pairwise_commanded": float(d.min()),
            "commanded_clears_rr_bound": bool(d.min() > ec.min_rr_distance),
            # A lane at |y| = lane_gap/2 must clear a central obstacle at y = 0.
            "lane_clears_central_obstacle": bool(lane_gap / 2.0 >= ec.min_ro_distance),
            "lane_clearance_margin_m": float(lane_gap / 2.0 - ec.min_ro_distance),
            "subteam_count": int(len(set(env.state.subteam_ids.tolist()))),
        }
    return rows


def run_fixed_mode(cfg, layout, n, seed, mode, t_max=200):
    """Deterministic episode with the mode pinned; returns metrics + crossing."""
    from dataclasses import replace as dc_replace
    sim_cfg = dc_replace(cfg, env=dc_replace(cfg.env, max_steps=t_max))
    env = SwarmFormationEnv(sim_cfg)
    obs = env.reset(n, "cluttered", seed=seed, layout=layout)
    reg = regions_for_layout(layout, cfg)
    acc = EpisodeAccumulator(formation_tolerance=cfg.env.formation_tolerance, dt=cfg.env.dt)
    done, last, crossed, max_x = False, None, 0, -np.inf
    while not done:
        obs, _, done, last = env.step(expert_action(obs, sim_cfg, mode), mode)
        acc.update(last)
        c = obs["positions"].mean(axis=0)
        max_x = max(max_x, float(c[0]))
        if reg.has_bottleneck and reg.crossed_exit(c):
            crossed = 1
    m = acc.finalize(last)
    m["crossed_bottleneck"] = crossed
    m["max_centroid_x"] = max_x
    m["exit_x"] = reg.exit_x if reg.has_bottleneck else float("nan")
    return m


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    cfg = Config()
    print(f"commit={git_commit()}")

    print("\n=== 1. SPLIT TEMPLATE GEOMETRY AUDIT (scenario-independent) ===")
    audit = template_geometry_audit(cfg)
    for k, v in audit.items():
        print(f"  {k}: lane_gap={v['lane_gap']:.3f} lane_offset={v['lane_offset']:.3f} "
              f"clears_central_obstacle={v['lane_clears_central_obstacle']} "
              f"margin={v['lane_clearance_margin_m']:+.3f} m  "
              f"min_commanded_pair={v['min_pairwise_commanded']:.3f} "
              f"subteams={v['subteam_count']}")

    print("\n=== 2. DETERMINISTIC FIXED-MODE TRAVERSAL (no perturbation) ===")
    rows = []
    fams = ["split_around", "keep_split_merge", "line_corridor"]
    for split in ("train", "val"):
        for lay in [l for l in build_layouts(split) if l.family in fams]:
            for n in (4, 6):
                for mode, name in MODES.items():
                    m = run_fixed_mode(cfg, lay, n, seed=20000400 + n, mode=mode)
                    rows.append({
                        "benchmark_tag": "recovery-event-v2", "git_commit": git_commit(),
                        "layout_id": lay.layout_id, "family": lay.family,
                        "team_size": n, "mode": name,
                        "success": float(m["success"]),
                        "goal_reached": float(m["goal_reached"]),
                        "collision_free": float(m["collision_free"]),
                        "crossed_bottleneck": int(m["crossed_bottleneck"]),
                        "max_centroid_x": round(float(m["max_centroid_x"]), 3),
                        "exit_x": round(float(m["exit_x"]), 3),
                        "deadlock": float(m["deadlock"]),
                        "collapse": float(m["irreversible_collapse"]),
                        "time_in_tube": float(m["time_in_formation_tube"])})
    with (OUT / "split_mode_validation.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=sorted({k for r in rows for k in r}))
        w.writeheader(); w.writerows(rows)

    print(f"{'family':20s}{'N':>3s}{'mode':>7s}{'cross':>7s}{'goal':>6s}{'cf':>6s}"
          f"{'succ':>6s}{'maxX':>8s}{'exitX':>8s}")
    for fam in fams:
        for n in (4, 6):
            for name in MODES.values():
                sub = [r for r in rows if r["family"] == fam and r["team_size"] == n
                       and r["mode"] == name]
                if not sub:
                    continue
                print(f"{fam:20s}{n:3d}{name:>7s}"
                      f"{np.mean([r['crossed_bottleneck'] for r in sub]):7.2f}"
                      f"{np.mean([r['goal_reached'] for r in sub]):6.2f}"
                      f"{np.mean([r['collision_free'] for r in sub]):6.2f}"
                      f"{np.mean([r['success'] for r in sub]):6.2f}"
                      f"{np.mean([r['max_centroid_x'] for r in sub]):8.2f}"
                      f"{np.mean([r['exit_x'] for r in sub]):8.2f}")

    print("\n=== 3. DOES SPLIT EVER STRICTLY BEAT KEEP ON CROSSING? ===")
    wins = beats = ties = 0
    for lay_id in sorted({r["layout_id"] for r in rows}):
        for n in (4, 6):
            k = [r for r in rows if r["layout_id"] == lay_id and r["team_size"] == n
                 and r["mode"] == "keep"]
            s = [r for r in rows if r["layout_id"] == lay_id and r["team_size"] == n
                 and r["mode"] == "split"]
            if not k or not s:
                continue
            if s[0]["crossed_bottleneck"] > k[0]["crossed_bottleneck"]:
                beats += 1
                print(f"  SPLIT BEATS KEEP: {lay_id} N={n} "
                      f"(split crossed, keep max_x={k[0]['max_centroid_x']:.2f} "
                      f"vs exit {k[0]['exit_x']:.2f})")
            elif s[0]["crossed_bottleneck"] < k[0]["crossed_bottleneck"]:
                wins += 1
            else:
                ties += 1
    print(f"  split strictly better: {beats} | keep strictly better: {wins} | tied: {ties}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
