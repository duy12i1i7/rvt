"""Step 6 — diagnostic trajectory and time-series plots for the smoke benchmark.

Selects one representative episode per category, re-runs it with tracing enabled
(episodes are deterministic given the seed), and renders:

  * a trajectory panel: paths, obstacle geometry, starts, goal, robot radius,
    collision boundary, formation mode over time, collision timestamps and
    safety-filter activation points;
  * a time-series panel: minimum clearance, formation RMS error, progress,
    selected topology, filter activation, collision flags.

Diagnostic only. No comparative claim is made or implied.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.patches import Circle  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from rvt_swarm.evaluate import run_policy_episode  # noqa: E402
from scripts.run_smoke_protocol_v2 import smoke_config  # noqa: E402

OUT = REPO / "results" / "smoke_protocol_v2"
FIG = OUT / "figures"
TOPOLOGY_NAMES = {0: "keep", 1: "compress", 2: "line", 3: "split", 4: "recover"}


def load_rows():
    with (OUT / "per_episode.csv").open() as fh:
        return list(csv.DictReader(fh))


def pick_episodes(rows):
    """One representative episode per required category."""
    fl = lambda r, k: float(r[k])  # noqa: E731
    picks = {}

    def first(pred, label):
        for r in rows:
            if pred(r):
                picks[label] = r
                return

    first(lambda r: fl(r, "success") == 1.0 and fl(r, "collision_free") == 1.0,
          "1_successful")
    first(lambda r: fl(r, "robot_robot_collision_steps") > 0
          and fl(r, "robot_obstacle_collision_steps") == 0, "2_robot_robot_collision")
    first(lambda r: fl(r, "robot_obstacle_collision_steps") > 0, "3_robot_obstacle_collision")
    first(lambda r: fl(r, "deadlock") == 1.0 or fl(r, "irreversible_collapse") == 1.0,
          "4_deadlock_or_collapse")
    first(lambda r: fl(r, "topology_switches") >= 3, "5_topology_switching")
    return picks


def rerun(row):
    cfg = smoke_config()
    return run_policy_episode(
        row["method"], cfg, int(row["team_size"]), row["scenario"],
        ckpt_dir=str(REPO / "checkpoints" / "smoke_protocol_v2"),
        seed=int(row["episode_seed"]), trace=True,
    ), cfg


def plot_trajectory(label, row, out, cfg):
    trace = out["trace"]
    init = out["initial_obs"]
    pos = np.stack([t["positions"] for t in trace])          # (T, N, 2)
    obstacles = trace[0]["obstacles"]
    goal = trace[0]["goal"]
    n = pos.shape[1]
    r_robot, r_obs = cfg.env.robot_radius, cfg.env.obstacle_radius

    fig = plt.figure(figsize=(13, 6.5))
    gs = fig.add_gridspec(2, 2, width_ratios=[2.4, 1.0], height_ratios=[6, 1], hspace=0.28)
    ax = fig.add_subplot(gs[0, 0])

    for o in obstacles:
        ax.add_patch(Circle(o, r_obs, color="#c0392b", alpha=0.35, zorder=1))
        ax.add_patch(Circle(o, cfg.env.min_ro_distance, fill=False, ls=":",
                            ec="#c0392b", lw=0.8, zorder=1))
    cmap = plt.get_cmap("viridis")
    for i in range(n):
        ax.plot(pos[:, i, 0], pos[:, i, 1], lw=1.4, color=cmap(i / max(n - 1, 1)),
                zorder=3, alpha=0.9)
        ax.add_patch(Circle(init["positions"][i], r_robot, fc="none", ec="k",
                            lw=1.0, zorder=4))
        ax.add_patch(Circle(pos[-1, i], r_robot, fc=cmap(i / max(n - 1, 1)),
                            ec="k", lw=0.6, alpha=0.85, zorder=5))
    ax.scatter(init["positions"][:, 0], init["positions"][:, 1], marker="s", s=22,
               c="k", zorder=6, label="start")
    ax.scatter([goal[0]], [goal[1]], marker="*", s=340, c="#27ae60",
               edgecolors="k", zorder=7, label="goal")
    ax.add_patch(Circle(goal, cfg.env.goal_tolerance, fill=False, ec="#27ae60",
                        ls="--", lw=1.0, zorder=2))

    coll = [k for k, t in enumerate(trace) if t["collision_free"] < 0.5]
    if coll:
        cp = pos[coll].reshape(-1, 2)
        ax.scatter(cp[:, 0], cp[:, 1], marker="x", s=26, c="#e74c3c", lw=1.1,
                   zorder=8, label=f"collision ({len(coll)} steps)")
    filt = [k for k, t in enumerate(trace) if t["shield_activated"] > 0.5]
    if filt:
        fp = pos[filt].reshape(-1, 2)
        ax.scatter(fp[:, 0], fp[:, 1], marker="^", s=16, facecolors="none",
                   edgecolors="#2980b9", lw=0.7, zorder=8,
                   label=f"safety filter ({len(filt)} steps)")

    ax.set_aspect("equal")
    ax.set_xlabel("x [m]")
    ax.set_ylabel("y [m]")
    ax.legend(loc="upper left", fontsize=7, framealpha=0.9)
    ax.set_title(
        f"{label}  |  {row['method']} · {row['scenario']} · N={row['team_size']} · "
        f"seed={row['episode_seed']}\n"
        f"success={float(row['success']):.0f}  episode collision-free="
        f"{float(row['collision_free']):.0f}  (terminal="
        f"{float(row['collision_free_terminal']):.0f})  "
        f"collapse={float(row['irreversible_collapse']):.0f}  "
        f"topology switches={float(row['topology_switches']):.0f}",
        fontsize=9)

    # formation mode over time
    axm = fig.add_subplot(gs[1, 0])
    modes = np.array([t["topology_mode"] for t in trace])
    axm.imshow(modes[None, :], aspect="auto", cmap="tab10", vmin=0, vmax=9,
               extent=[0, len(modes), 0, 1])
    axm.set_yticks([])
    axm.set_xlabel("control step")
    axm.set_title("formation mode over time  "
                  + "  ".join(f"{v}={TOPOLOGY_NAMES[v]}" for v in sorted(set(modes.tolist()))),
                  fontsize=7)

    # legend/info panel
    axi = fig.add_subplot(gs[:, 1])
    axi.axis("off")
    info = [
        "GEOMETRY",
        f"  robot radius        {r_robot:.2f} m  (solid outline)",
        f"  obstacle radius     {r_obs:.2f} m  (filled)",
        f"  RR collision bound  {cfg.env.min_rr_distance:.2f} m",
        f"  RO collision bound  {cfg.env.min_ro_distance:.2f} m  (dotted)",
        f"  goal tolerance      {cfg.env.goal_tolerance:.2f} m  (dashed)",
        "",
        "EPISODE",
        f"  control steps       {len(trace)}",
        f"  collision steps RR  {float(row['robot_robot_collision_steps']):.0f}",
        f"  collision steps RO  {float(row['robot_obstacle_collision_steps']):.0f}",
        f"  min RR clearance    {float(row['min_rr_clearance']):.3f} m",
        f"  min RO clearance    {float(row['min_ro_clearance']):.3f} m",
        f"  time in tube        {float(row['time_in_formation_tube']):.3f}",
        f"  deadlock (latch)    {float(row['deadlock']):.0f}",
        f"  collapse (latch)    {float(row['irreversible_collapse']):.0f}",
        f"  filter activations  {float(row['safety_filter_activations']):.0f}",
        "",
        "COLLISION TIMESTAMPS (step)",
        "  " + (", ".join(str(c) for c in coll[:14]) + ("…" if len(coll) > 14 else "")
               if coll else "  none"),
    ]
    axi.text(0, 1, "\n".join(info), va="top", ha="left", family="monospace", fontsize=7.5)

    path = FIG / f"trajectory_{label}.png"
    fig.savefig(path, dpi=145, bbox_inches="tight")
    plt.close(fig)
    return path


def plot_timeseries(label, row, out, cfg):
    trace = out["trace"]
    steps = np.arange(1, len(trace) + 1)
    g = lambda k: np.array([t[k] for t in trace])  # noqa: E731

    fig, axes = plt.subplots(6, 1, figsize=(10, 11), sharex=True)
    fig.suptitle(f"{label}  |  {row['method']} · {row['scenario']} · "
                 f"N={row['team_size']} · seed={row['episode_seed']}", fontsize=10)

    axes[0].plot(steps, g("min_rr_clearance"), label="robot–robot", lw=1.2)
    axes[0].plot(steps, g("min_ro_clearance"), label="robot–obstacle", lw=1.2)
    axes[0].axhline(cfg.env.min_rr_distance, color="#c0392b", ls="--", lw=0.9,
                    label=f"RR bound {cfg.env.min_rr_distance}")
    axes[0].axhline(cfg.env.min_ro_distance, color="#e67e22", ls=":", lw=0.9,
                    label=f"RO bound {cfg.env.min_ro_distance}")
    axes[0].set_ylabel("min clearance [m]"); axes[0].legend(fontsize=6, ncol=2)

    axes[1].plot(steps, g("form_rms"), lw=1.2, color="#8e44ad")
    axes[1].axhline(cfg.env.formation_tolerance, color="k", ls="--", lw=0.9,
                    label=f"tube {cfg.env.formation_tolerance}")
    axes[1].set_ylabel("formation RMS [m]"); axes[1].legend(fontsize=6)

    axes[2].plot(steps, g("goal_progress"), lw=1.2, color="#16a085")
    axes[2].set_ylabel("normalised progress")

    axes[3].step(steps, g("selected_topology"), where="post", lw=1.2, color="#2c3e50")
    axes[3].set_yticks(sorted(TOPOLOGY_NAMES))
    axes[3].set_yticklabels([TOPOLOGY_NAMES[v] for v in sorted(TOPOLOGY_NAMES)], fontsize=7)
    axes[3].set_ylabel("selected topology")

    axes[4].step(steps, g("shield_activated"), where="post", lw=1.2, color="#2980b9")
    axes[4].set_ylabel("safety filter"); axes[4].set_ylim(-0.1, 1.1)
    axes[4].set_yticks([0, 1]); axes[4].set_yticklabels(["idle", "active"], fontsize=7)

    axes[5].step(steps, 1.0 - g("collision_free"), where="post", lw=1.2,
                 color="#c0392b", label="any collision")
    axes[5].step(steps, g("rr_collision"), where="post", lw=0.9, ls="--", label="RR density")
    axes[5].step(steps, g("ro_collision"), where="post", lw=0.9, ls=":", label="RO density")
    axes[5].set_ylabel("collision flags"); axes[5].set_xlabel("control step")
    axes[5].legend(fontsize=6)

    for ax in axes:
        ax.grid(alpha=0.25)
    fig.tight_layout(rect=[0, 0, 1, 0.98])
    path = FIG / f"timeseries_{label}.png"
    fig.savefig(path, dpi=145, bbox_inches="tight")
    plt.close(fig)
    return path


def main() -> int:
    FIG.mkdir(parents=True, exist_ok=True)
    rows = load_rows()
    picks = pick_episodes(rows)
    required = ["1_successful", "2_robot_robot_collision", "3_robot_obstacle_collision",
                "4_deadlock_or_collapse", "5_topology_switching"]
    for label in required:
        if label not in picks:
            print(f"[note] no episode found for category '{label}' in this smoke run")
    for label, row in sorted(picks.items()):
        out, cfg = rerun(row)
        t = plot_trajectory(label, row, out, cfg)
        s = plot_timeseries(label, row, out, cfg)
        print(f"{label:28s} {row['method']:22s} {row['scenario']:15s} N={row['team_size']:>2s} "
              f"seed={row['episode_seed']}")
        print(f"    {t.relative_to(REPO)}")
        print(f"    {s.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
