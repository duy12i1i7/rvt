"""Episode visualization → GIFs and time-series plots for paper figures.

Premium dark-themed rendering with:
  • Directional triangle robots with heading indicators
  • Simulated LiDAR fan overlay per robot
  • Gradient-alpha trails
  • Obstacle danger-zone halos
  • Real-time metrics overlay (step, collisions, formation RMS)
  • Formation edges
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

from .baselines import historical_baseline, is_baseline_method
from .config import Config, TOPOLOGY_ACTIONS
from .environment import SwarmFormationEnv
from .policy_runtime import infer_learned_action, is_learned_method, load_learned_model
from .utils import torch_device, pairwise_dist, unit

try:
    import torch
except ImportError:
    torch = None

try:
    from PIL import Image
except ImportError:
    Image = None


# ── Premium color palette (from template) ────────────────────────────
ROBOT_COLORS = [
    '#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4',
    '#FFEAA7', '#DDA0DD', '#98D8C8', '#F7DC6F',
    '#BB8FCE', '#85C1E9', '#F8C471', '#82E0AA',
    '#F1948A', '#AED6F1', '#D5DBDB', '#A3E4D7',
]
BG_COLOR = '#1a1a2e'
GRID_COLOR = '#16213e'
OBSTACLE_COLOR = '#e74c3c'
DANGER_ZONE_COLOR = '#e74c3c'
GOAL_COLOR = '#f39c12'
TRAIL_ALPHA = 0.45
LIDAR_COLOR = '#4ecdc4'
LIDAR_ALPHA = 0.08
LIDAR_RANGE = 3.0       # Visual LiDAR range (m)
LIDAR_FOV = np.radians(270)  # 270° field of view
LIDAR_NUM_RAYS = 36      # Number of rays to draw
METHOD_PLOT_COLORS = ['#2E86DE', '#E67E22', '#16A085', '#8E44AD', '#C0392B', '#2C3E50']


# ── Helper: heading from velocity ─────────────────────────────────────
def _heading_from_velocity(vel: np.ndarray, prev_heading: float = 0.0) -> float:
    """Estimate heading angle from velocity vector, with fallback."""
    speed = np.linalg.norm(vel)
    if speed > 0.02:
        return float(np.arctan2(vel[1], vel[0]))
    return prev_heading


# ── Draw a robot as directional triangle (from template) ──────────────
def _draw_robot(ax, x, y, theta, color, size=0.2, alpha=1.0):
    """Draw robot as a filled triangle pointing in heading direction."""
    dx = size * np.cos(theta)
    dy = size * np.sin(theta)
    perp_x = size * 0.5 * np.cos(theta + np.pi / 2)
    perp_y = size * 0.5 * np.sin(theta + np.pi / 2)
    tri = plt.Polygon(
        [
            [x + dx, y + dy],                       # nose
            [x - dx / 2 + perp_x, y - dy / 2 + perp_y],  # left
            [x - dx / 2 - perp_x, y - dy / 2 - perp_y],  # right
        ],
        closed=True, fc=color, ec='white', linewidth=0.8, alpha=alpha, zorder=5,
    )
    ax.add_patch(tri)


# ── LiDAR fan from real scan data ──────────────────────────────────────
def _draw_lidar_fan(ax, x, y, theta, scan_data, cfg):
    """Draw a LiDAR sensing fan using actual scan distances.

    scan_data: 1D array of *normalized* distances (0–1), one per ray.
    Each value is range_hit / lidar_range; 1.0 = max range (no hit).
    """
    num_rays = len(scan_data)
    half_fov = cfg.env.lidar_fov / 2
    angles = np.linspace(theta - half_fov, theta + half_fov, num_rays)
    fan_points = [(x, y)]
    for angle, d_norm in zip(angles, scan_data):
        r = float(d_norm) * cfg.env.lidar_range
        fan_points.append((x + r * np.cos(angle), y + r * np.sin(angle)))
    fan_points.append((x, y))
    fan = plt.Polygon(fan_points, closed=True, fc=LIDAR_COLOR,
                      ec='none', alpha=LIDAR_ALPHA, zorder=1)
    ax.add_patch(fan)


def _ray_circle_hit(ox, oy, d, cx, cy, r) -> Optional[float]:
    """Ray-circle intersection. Returns distance or None."""
    fx = ox - cx
    fy = oy - cy
    a = d[0] ** 2 + d[1] ** 2
    b = 2.0 * (fx * d[0] + fy * d[1])
    c = fx ** 2 + fy ** 2 - r ** 2
    disc = b ** 2 - 4 * a * c
    if disc < 0:
        return None
    disc_sqrt = np.sqrt(disc)
    t1 = (-b - disc_sqrt) / (2 * a)
    if t1 >= 0:
        return float(t1)
    t2 = (-b + disc_sqrt) / (2 * a)
    if t2 >= 0:
        return float(t2)
    return None


# ── Dark-themed axis setup (from template) ────────────────────────────
def _setup_dark_ax(ax, title, xlim, ylim):
    """Configure an axis with dark theme."""
    ax.set_facecolor(BG_COLOR)
    ax.set_xlim(xlim)
    ax.set_ylim(ylim)
    ax.set_aspect('equal')
    ax.grid(True, color=GRID_COLOR, linewidth=0.3, alpha=0.5)
    ax.set_title(title, color='white', fontsize=10, fontweight='bold', pad=8)
    ax.tick_params(colors='#888888', labelsize=6)
    for spine in ax.spines.values():
        spine.set_color('#333333')


def _metric_series(frames: List[Dict], key: str, default: float = np.nan) -> np.ndarray:
    """Extract a per-frame scalar series from recorded metrics."""
    values = []
    for frame in frames:
        metrics = frame.get("metrics", {})
        values.append(float(metrics.get(key, default)))
    return np.asarray(values, dtype=np.float32)


def _setup_metric_ax(ax: plt.Axes, title: str, ylabel: str) -> None:
    """Configure a clean light-themed metrics axis."""
    ax.set_title(title, fontsize=10, fontweight='bold')
    ax.set_ylabel(ylabel, fontsize=9)
    ax.grid(True, color='#D9DEE7', linewidth=0.7, alpha=0.8)
    ax.set_facecolor('white')
    for spine in ax.spines.values():
        spine.set_color('#C9CFDA')
    ax.tick_params(labelsize=8)


def _formation_error_profiles(frames: List[Dict]) -> Tuple[np.ndarray, np.ndarray]:
    """Aggregate mean and max agent-wise formation error magnitudes per frame."""
    mean_error = []
    max_error = []
    for frame in frames:
        formation_error = np.asarray(frame.get("formation_error", []), dtype=np.float32)
        if formation_error.size == 0:
            mean_error.append(np.nan)
            max_error.append(np.nan)
            continue
        norms = np.linalg.norm(formation_error, axis=1)
        mean_error.append(float(np.mean(norms)))
        max_error.append(float(np.max(norms)))
    return np.asarray(mean_error, dtype=np.float32), np.asarray(max_error, dtype=np.float32)


def save_episode_metric_plot(
    frames: List[Dict],
    out_path: str,
    cfg: Config,
    method: str,
    n_agents: int,
) -> str:
    """Save per-step episode metrics for the exact rollout used to render a GIF."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    steps = np.asarray([frame["step"] for frame in frames], dtype=np.int32)
    topology_action = np.asarray(
        [float(frame.get("topology_action", frame.get("topology_mode", 0))) for frame in frames],
        dtype=np.float32,
    )
    topology_switches = _metric_series(frames, "topology_switches", default=0.0)
    goal_distance = _metric_series(frames, "goal_distance", default=0.0)
    goal_progress = _metric_series(frames, "goal_progress", default=0.0)
    bottleneck = _metric_series(frames, "bottleneck", default=0.0)
    form_rms = _metric_series(frames, "form_rms", default=0.0)
    mean_form_error, max_form_error = _formation_error_profiles(frames)
    recoverability = _metric_series(frames, "recoverability_proxy", default=0.0)
    rr_collision = _metric_series(frames, "rr_collision", default=0.0)
    ro_collision = _metric_series(frames, "ro_collision", default=0.0)
    stall_rate = _metric_series(frames, "stall_rate", default=0.0)
    deadlock = _metric_series(frames, "deadlock", default=0.0)

    fig, axes = plt.subplots(2, 2, figsize=(13, 8), sharex=True)
    fig.patch.set_facecolor('white')
    scenario = frames[0].get("scenario", "episode") if frames else "episode"
    fig.suptitle(
        f"{method} | {scenario} | n={n_agents} | episode metrics over time",
        fontsize=13,
        fontweight='bold',
    )

    ax = axes[0, 0]
    _setup_metric_ax(ax, "Goal Tracking", "distance (m)")
    ax.plot(steps, goal_distance, color='#2E86DE', linewidth=2.2, label='goal_distance')
    ax_top = ax.twinx()
    ax_top.plot(steps, goal_progress, color='#16A085', linewidth=1.8, linestyle='--', label='goal_progress')
    ax_top.plot(steps, bottleneck, color='#7F8C8D', linewidth=1.6, linestyle=':', label='bottleneck')
    ax_top.set_ylabel("normalized score", fontsize=9)
    ax_top.tick_params(labelsize=8)
    ax_top.set_ylim(-0.05, 1.05)
    handles, labels = ax.get_legend_handles_labels()
    handles_top, labels_top = ax_top.get_legend_handles_labels()
    ax.legend(handles + handles_top, labels + labels_top, loc='upper right', fontsize=8)

    ax = axes[0, 1]
    _setup_metric_ax(ax, "Formation Error Trajectory", "distance (m)")
    ax.plot(steps, form_rms, color='#E67E22', linewidth=2.4, label='form_rms')
    ax.plot(steps, mean_form_error, color='#8E44AD', linewidth=1.9, label='mean_agent_error')
    ax.plot(steps, max_form_error, color='#C0392B', linewidth=1.9, linestyle='-.', label='max_agent_error')
    ax.axhline(
        cfg.env.formation_tolerance,
        color='#C0392B',
        linewidth=1.6,
        linestyle='--',
        label='formation_tolerance',
    )
    ax.legend(loc='upper right', fontsize=8)

    ax = axes[1, 0]
    _setup_metric_ax(ax, "Safety and Recoverability", "score / rate")
    ax.plot(steps, rr_collision, color='#C0392B', linewidth=1.8, label='rr_collision')
    ax.plot(steps, ro_collision, color='#8E44AD', linewidth=1.8, label='ro_collision')
    ax.plot(steps, recoverability, color='#16A085', linewidth=2.0, label='recoverability_proxy')
    ax.set_ylim(min(-0.35, float(np.nanmin(recoverability)) - 0.05), 1.05)
    ax.legend(loc='lower right', fontsize=8)

    ax = axes[1, 1]
    _setup_metric_ax(ax, "Liveness and Topology", "liveness")
    ax.plot(steps, stall_rate, color='#2C3E50', linewidth=2.0, label='stall_rate')
    ax.plot(steps, deadlock, color='#C0392B', linewidth=1.8, linestyle='--', label='deadlock')
    ax.set_ylim(-0.05, 1.05)
    ax_top = ax.twinx()
    ax_top.step(steps, topology_action, where='post', color='#8E44AD', linewidth=1.8, label='topology_action')
    ax_top.plot(steps, topology_switches, color='#F39C12', linewidth=1.8, linestyle='-.', label='topology_switches')
    ax_top.set_ylabel("topology", fontsize=9)
    ax_top.tick_params(labelsize=8)
    ax_top.set_ylim(-0.3, max(4.5, float(np.nanmax(topology_switches)) + 0.6))
    handles, labels = ax.get_legend_handles_labels()
    handles_top, labels_top = ax_top.get_legend_handles_labels()
    ax.legend(handles + handles_top, labels + labels_top, loc='upper right', fontsize=8)

    for ax in axes[1, :]:
        ax.set_xlabel("step", fontsize=9)

    fig.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(out_path, dpi=180, bbox_inches='tight')
    plt.close(fig)
    print(f"  Metrics plot saved: {out_path}")
    return str(out_path)


def save_comparison_metric_plot(
    all_frames: Dict[str, List[Dict]],
    out_path: str,
    cfg: Config,
    n_agents: int,
    scenario: str,
) -> str:
    """Save a side-by-side time-series comparison for the rollout group used in a comparison GIF."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    fig, axes = plt.subplots(2, 2, figsize=(13, 8), sharex=False)
    fig.patch.set_facecolor('white')
    fig.suptitle(
        f"Comparison metrics | {scenario} | n={n_agents}",
        fontsize=13,
        fontweight='bold',
    )

    ax_goal = axes[0, 0]
    _setup_metric_ax(ax_goal, "Goal Distance", "distance (m)")

    ax_form = axes[0, 1]
    _setup_metric_ax(ax_form, "Formation RMS", "distance (m)")
    ax_form.axhline(
        cfg.env.formation_tolerance,
        color='#C0392B',
        linewidth=1.4,
        linestyle='--',
        label='formation_tolerance',
    )

    ax_form_mean = axes[1, 0]
    _setup_metric_ax(ax_form_mean, "Mean Agent Formation Error", "distance (m)")

    ax_form_max = axes[1, 1]
    _setup_metric_ax(ax_form_max, "Max Agent Formation Error", "distance (m)")

    for idx, (method, frames) in enumerate(all_frames.items()):
        color = METHOD_PLOT_COLORS[idx % len(METHOD_PLOT_COLORS)]
        steps = np.asarray([frame["step"] for frame in frames], dtype=np.int32)
        goal_distance = _metric_series(frames, "goal_distance", default=0.0)
        form_rms = _metric_series(frames, "form_rms", default=0.0)
        mean_form_error, max_form_error = _formation_error_profiles(frames)

        ax_goal.plot(steps, goal_distance, color=color, linewidth=2.0, label=method)
        ax_form.plot(steps, form_rms, color=color, linewidth=2.0, label=method)
        ax_form_mean.plot(steps, mean_form_error, color=color, linewidth=2.0, label=method)
        ax_form_max.plot(steps, max_form_error, color=color, linewidth=2.0, label=method)

    for ax in axes[1, :]:
        ax.set_xlabel("step", fontsize=9)

    for ax in axes.flat:
        ax.legend(loc='best', fontsize=8)

    fig.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(out_path, dpi=180, bbox_inches='tight')
    plt.close(fig)
    print(f"  Comparison metrics plot saved: {out_path}")
    return str(out_path)


# ═══════════════════════════════════════════════════════════════════════
# Record episode — captures velocities for heading computation
# ═══════════════════════════════════════════════════════════════════════

def record_episode(
    method: str,
    cfg: Config,
    n_agents: int,
    scenario: str,
    ckpt_dir: str = "results",
    seed: int = 0,
) -> List[Dict]:
    """Run one episode and record per-step state for rendering."""
    np.random.seed(seed)
    env = SwarmFormationEnv(cfg)
    obs = env.reset(n_agents, scenario, seed=seed)
    device = torch_device(cfg.train.device) if torch is not None else "cpu"

    model = None
    if is_learned_method(method) and torch is not None:
        model = load_learned_model(method, cfg, ckpt_dir, device)

    frames: List[Dict] = []
    done = False
    steps = 0
    prev_topo = 0
    # Track cumulative collision counts for overlay
    cum_rr = 0
    cum_ro = 0

    while not done and steps < cfg.env.max_steps:
        current_metrics = env.compute_metrics()
        # Record current state (include velocities for heading)
        frame = {
            "positions": obs["positions"].copy(),
            "velocities": obs["velocities"].copy(),
            "goal": obs["goal"].copy(),
            "obstacles": obs["obstacles"].copy(),
            "lidar_scans": obs["lidar_scans"].copy(),
            "topology_mode": obs["topology_mode"],
            "formation_error": obs["formation_error"].copy(),
            "scenario": scenario,
            "step": steps,
            "cum_rr": cum_rr,
            "cum_ro": cum_ro,
            "metrics": current_metrics.copy(),
        }

        # Compute action
        if is_baseline_method(method):
            actions, topo = historical_baseline(method, obs, cfg)
        else:
            runtime = infer_learned_action(method, obs, cfg, model, prev_topo)
            actions = runtime["actions"]
            topo = runtime["topology"]

        frame["topology_action"] = topo
        frames.append(frame)

        prev_topo = topo
        obs, _, done, info = env.step(actions, topo)
        steps += 1

        # Accumulate collisions
        cum_rr += int(info.get("rr_collision", 0) > 0)
        cum_ro += int(info.get("ro_collision", 0) > 0)

    # Capture final frame
    final_metrics = env.compute_metrics()
    frames.append({
        "positions": obs["positions"].copy(),
        "velocities": obs["velocities"].copy(),
        "goal": obs["goal"].copy(),
        "obstacles": obs["obstacles"].copy(),
        "lidar_scans": obs["lidar_scans"].copy(),
        "topology_mode": obs["topology_mode"],
        "formation_error": obs["formation_error"].copy(),
        "scenario": scenario,
        "step": steps,
        "topology_action": prev_topo,
        "cum_rr": cum_rr,
        "cum_ro": cum_ro,
        "metrics": final_metrics.copy(),
    })
    return frames


# ═══════════════════════════════════════════════════════════════════════
# render_frame — premium dark theme with LiDAR, directional robots
# ═══════════════════════════════════════════════════════════════════════

def render_frame(
    frame: Dict,
    trails: List[np.ndarray],
    headings: List[float],
    ax: plt.Axes,
    cfg: Config,
    method: str,
    n_agents: int,
) -> None:
    """Render a single frame onto the axes (dark-themed, with LiDAR)."""
    ax.clear()
    ws = cfg.env.world_size * 0.55
    _setup_dark_ax(ax, "", (-ws, ws), (-ws, ws))

    pos = frame["positions"]
    vel = frame.get("velocities", np.zeros_like(pos))
    obs_radius = cfg.env.obstacle_radius
    obstacles = frame["obstacles"]

    # ── Goal ──
    goal = frame["goal"]
    goal_circle = plt.Circle(goal, cfg.env.goal_tolerance, fc=GOAL_COLOR,
                             ec='white', alpha=0.18, linewidth=0.8, zorder=1)
    ax.add_patch(goal_circle)
    ax.plot(*goal, marker='*', color=GOAL_COLOR, markersize=16, zorder=6,
            markeredgecolor='white', markeredgewidth=0.5)
    ax.annotate('Goal', goal, color=GOAL_COLOR, fontsize=7, ha='center',
                va='bottom', xytext=(0, 10), textcoords='offset points',
                fontweight='bold')

    # ── Obstacles with danger-zone halos ──
    for o in obstacles:
        # Danger zone ring
        danger = plt.Circle(o, obs_radius + cfg.env.min_ro_distance, fc='none',
                            ec=DANGER_ZONE_COLOR, linewidth=0.5, alpha=0.25,
                            linestyle='--', zorder=2)
        ax.add_patch(danger)
        # Obstacle body
        circ = plt.Circle(o, obs_radius, fc=OBSTACLE_COLOR, ec='white',
                          linewidth=0.6, alpha=0.7, zorder=3)
        ax.add_patch(circ)

    # ── Gradient-alpha trails ──
    for i, trail in enumerate(trails):
        if len(trail) < 2:
            continue
        color = ROBOT_COLORS[i % len(ROBOT_COLORS)]
        t = np.array(trail)
        n_seg = len(t) - 1
        # Only draw last 80 segments for performance
        seg_start = max(0, n_seg - 80)
        for j in range(seg_start, n_seg):
            alpha = 0.05 + TRAIL_ALPHA * (j - seg_start) / max(1, n_seg - seg_start - 1)
            ax.plot(t[j:j+2, 0], t[j:j+2, 1], '-', color=color,
                    alpha=alpha, linewidth=1.3, zorder=2)

    # ── Formation edges ──
    for i in range(n_agents):
        for j in range(i + 1, n_agents):
            d = np.linalg.norm(pos[i] - pos[j])
            if d < cfg.env.sensing_radius * 0.6:
                ax.plot([pos[i, 0], pos[j, 0]], [pos[i, 1], pos[j, 1]],
                        '--', color='#ffffff', alpha=0.15, linewidth=0.6, zorder=3)

    # ── LiDAR fans + Directional robots ──
    lidar_scans = frame.get("lidar_scans", None)
    for i in range(n_agents):
        color = ROBOT_COLORS[i % len(ROBOT_COLORS)]
        theta = _heading_from_velocity(vel[i], headings[i])
        headings[i] = theta  # update for next frame

        # LiDAR fan (from real scan data)
        if lidar_scans is not None:
            _draw_lidar_fan(ax, pos[i, 0], pos[i, 1], theta, lidar_scans[i], cfg)

        # Robot body (triangle)
        _draw_robot(ax, pos[i, 0], pos[i, 1], theta, color, size=0.22)

        # Tiny robot index label
        ax.text(pos[i, 0], pos[i, 1] - 0.32, str(i), color='white',
                fontsize=5, ha='center', va='top', fontweight='bold', zorder=7)

    # ── Metrics overlay ──
    topo_name = TOPOLOGY_ACTIONS.get(frame.get("topology_action", 0), "keep")
    cum_rr = frame.get("cum_rr", 0)
    cum_ro = frame.get("cum_ro", 0)

    # Compute current formation RMS
    fe = frame["formation_error"]
    form_rms = float(np.sqrt(np.mean(np.sum(fe ** 2, axis=1)))) if fe.shape[0] > 0 else 0.0

    # Title bar
    title = f"{method}  |  {frame['scenario']}  |  n={n_agents}  |  topo={topo_name}"
    ax.set_title(title, color='white', fontsize=9, fontweight='bold', pad=8)

    # On-screen HUD
    coll_color = '#ff6b6b' if (cum_rr + cum_ro) > 0 else '#4ecdc4'
    ax.text(0.02, 0.97, f"Step {frame['step']}", transform=ax.transAxes,
            color='white', fontsize=8, va='top', fontfamily='monospace', zorder=10)
    ax.text(0.02, 0.92, f"Col: {cum_rr}rr  {cum_ro}ro",
            transform=ax.transAxes, color=coll_color, fontsize=7,
            va='top', fontfamily='monospace', zorder=10)
    ax.text(0.02, 0.87, f"Form: {form_rms:.2f}m",
            transform=ax.transAxes, color='#f39c12', fontsize=7,
            va='top', fontfamily='monospace', zorder=10)


# ═══════════════════════════════════════════════════════════════════════
# save_gif
# ═══════════════════════════════════════════════════════════════════════

def save_gif(
    frames: List[Dict],
    out_path: str,
    cfg: Config,
    method: str,
    n_agents: int,
    fps: int = 8,
    dpi: int = 100,
) -> str:
    """Render frames and save as GIF."""
    if Image is None:
        raise ImportError("Pillow is required for GIF generation: pip install Pillow")

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(1, 1, figsize=(7, 7), dpi=dpi)
    fig.patch.set_facecolor(BG_COLOR)

    trails = [[] for _ in range(n_agents)]
    headings = [0.0] * n_agents  # persistent heading state
    images = []

    for frame in frames:
        for i in range(n_agents):
            trails[i].append(frame["positions"][i].copy())
        render_frame(frame, trails, headings, ax, cfg, method, n_agents)
        fig.canvas.draw()
        buf = np.asarray(fig.canvas.buffer_rgba())[:, :, :3].copy()
        images.append(Image.fromarray(buf))

    plt.close(fig)

    duration_ms = int(1000 / fps)
    images[0].save(
        str(out_path),
        save_all=True,
        append_images=images[1:],
        duration=duration_ms,
        loop=0,
        optimize=True,
    )
    print(f"  GIF saved: {out_path} ({len(images)} frames, {fps} fps)")
    return str(out_path)


# ═══════════════════════════════════════════════════════════════════════
# visualize_methods — generate per-method GIFs
# ═══════════════════════════════════════════════════════════════════════

def visualize_methods(
    methods: List[str],
    cfg: Config,
    ckpt_dir: str = "results",
    out_dir: str = "results/gifs",
    scenarios: Optional[List[str]] = None,
    team_sizes: Optional[List[int]] = None,
    seed: int = 42,
    fps: int = 8,
) -> Tuple[List[str], List[str]]:
    """Generate GIFs and per-episode metrics plots for selected methods/scenarios/team sizes."""
    scenarios = scenarios or ["open_field", "narrow_passage"]
    team_sizes = team_sizes or list(cfg.env.team_sizes)
    gif_paths = []
    plot_paths = []
    metrics_dir = Path(out_dir) / "metrics"

    for method in methods:
        for scenario in scenarios:
            for n in team_sizes:
                print(f"  Recording {method} | {scenario} | n={n} ...")
                frames = record_episode(method, cfg, n, scenario, ckpt_dir, seed)
                fname = f"{method}_{scenario}_n{n}.gif"
                path = save_gif(frames, str(Path(out_dir) / fname), cfg, method, n, fps)
                gif_paths.append(path)
                plot_name = f"{method}_{scenario}_n{n}_metrics.png"
                plot_paths.append(
                    save_episode_metric_plot(
                        frames,
                        str(metrics_dir / plot_name),
                        cfg,
                        method,
                        n,
                    )
                )

    return gif_paths, plot_paths


# ═══════════════════════════════════════════════════════════════════════
# save_comparison_gif — side-by-side multi-method comparison
# ═══════════════════════════════════════════════════════════════════════

def save_comparison_gif(
    all_frames: Dict[str, List[Dict]],
    out_path: str,
    cfg: Config,
    n_agents: int,
    scenario: str,
    fps: int = 8,
    dpi: int = 100,
) -> str:
    """Render side-by-side comparison GIF of multiple methods."""
    if Image is None:
        raise ImportError("Pillow is required for GIF generation: pip install Pillow")

    methods = list(all_frames.keys())
    n_methods = len(methods)
    cols = min(n_methods, 4)
    rows = (n_methods + cols - 1) // cols

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    fig, axes = plt.subplots(rows, cols, figsize=(5.5 * cols, 5.5 * rows), dpi=dpi)
    fig.patch.set_facecolor(BG_COLOR)
    if rows == 1 and cols == 1:
        axes = np.array([[axes]])
    elif rows == 1:
        axes = axes[np.newaxis, :]
    elif cols == 1:
        axes = axes[:, np.newaxis]

    # Hide unused axes
    for r in range(rows):
        for c in range(cols):
            idx = r * cols + c
            if idx >= n_methods:
                axes[r, c].set_visible(False)

    # Find max step count across all methods
    max_steps = max(len(f) for f in all_frames.values())

    # Per-method trails + headings
    all_trails = {m: [[] for _ in range(n_agents)] for m in methods}
    all_headings = {m: [0.0] * n_agents for m in methods}
    images = []

    for step_idx in range(max_steps):
        for m_idx, method in enumerate(methods):
            r, c = divmod(m_idx, cols)
            ax = axes[r, c]
            frames = all_frames[method]
            frame = frames[min(step_idx, len(frames) - 1)]
            trails = all_trails[method]
            if step_idx < len(frames):
                for i in range(n_agents):
                    trails[i].append(frame["positions"][i].copy())
            render_frame(frame, trails, all_headings[method], ax, cfg, method, n_agents)

        fig.suptitle(
            f"Comparison  |  {scenario}  |  n={n_agents}  |  step {step_idx}",
            fontsize=12, fontweight="bold", color='white', y=0.995,
        )
        fig.tight_layout(rect=[0, 0, 1, 0.97])
        fig.canvas.draw()
        buf = np.asarray(fig.canvas.buffer_rgba())[:, :, :3].copy()
        images.append(Image.fromarray(buf))

    plt.close(fig)

    duration_ms = int(1000 / fps)
    images[0].save(
        str(out_path),
        save_all=True,
        append_images=images[1:],
        duration=duration_ms,
        loop=0,
        optimize=True,
    )
    print(f"  Comparison GIF saved: {out_path} ({len(images)} frames, {n_methods} methods)")
    return str(out_path)


# ═══════════════════════════════════════════════════════════════════════
# visualize_comparisons — generate grouped comparison GIFs
# ═══════════════════════════════════════════════════════════════════════

def visualize_comparisons(
    method_groups: Optional[List[List[str]]] = None,
    cfg: Config = None,
    ckpt_dir: str = "results",
    out_dir: str = "results/gifs",
    scenarios: Optional[List[str]] = None,
    team_sizes: Optional[List[int]] = None,
    seed: int = 42,
    fps: int = 8,
) -> Tuple[List[str], List[str]]:
    """Generate comparison GIFs and grouped metrics plots."""
    if cfg is None:
        cfg = Config()
    scenarios = scenarios or ["open_field", "narrow_passage"]
    team_sizes = team_sizes or list(cfg.env.team_sizes)
    if method_groups is None:
        method_groups = [
            ["gnn_only", "instant_cert", "rvt_swarm"],
            ["rvt_swarm", "adaptive_formation", "cbf_qp", "orca"],
        ]

    gif_paths = []
    plot_paths = []
    metrics_dir = Path(out_dir) / "metrics"
    for group in method_groups:
        group_name = "_vs_".join(group[:3])
        if len(group) > 3:
            group_name += f"_+{len(group) - 3}"
        for scenario in scenarios:
            for n in team_sizes:
                effective = list(group)
                if len(effective) < 2:
                    continue

                print(f"  Comparison: {' vs '.join(effective)} | {scenario} | n={n}")
                all_frames = {}
                for method in effective:
                    all_frames[method] = record_episode(method, cfg, n, scenario, ckpt_dir, seed)

                fname = f"compare_{group_name}_{scenario}_n{n}.gif"
                path = save_comparison_gif(all_frames, str(Path(out_dir) / fname), cfg, n, scenario, fps)
                gif_paths.append(path)
                plot_name = f"compare_{group_name}_{scenario}_n{n}_metrics.png"
                plot_paths.append(
                    save_comparison_metric_plot(
                        all_frames,
                        str(metrics_dir / plot_name),
                        cfg,
                        n,
                        scenario,
                    )
                )

    return gif_paths, plot_paths
