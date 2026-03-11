"""Episode visualization → GIF for paper figures.

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
from typing import Dict, List, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

from .baselines import historical_baseline
from .config import Config, TOPOLOGY_ACTIONS
from .dataset import build_graph
from .environment import SwarmFormationEnv
from .safety import choose_counterfactual_topology, simple_recover_shield
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


# ── Simulated LiDAR fan for visualization ─────────────────────────────
def _draw_lidar_fan(ax, x, y, theta, obstacles, obs_radius, cfg):
    """Draw a LiDAR-like sensing fan around a robot.

    Casts rays and clips them against circular obstacles so the fan
    appears to 'stop' at detected surfaces.
    """
    half_fov = LIDAR_FOV / 2
    angles = np.linspace(theta - half_fov, theta + half_fov, LIDAR_NUM_RAYS)
    fan_points = [(x, y)]
    for angle in angles:
        ray_dir = np.array([np.cos(angle), np.sin(angle)])
        r = LIDAR_RANGE
        # Check obstacles
        for o in obstacles:
            hit = _ray_circle_hit(x, y, ray_dir, o[0], o[1], obs_radius)
            if hit is not None and hit < r:
                r = hit
        fan_points.append((x + r * ray_dir[0], y + r * ray_dir[1]))
    fan_points.append((x, y))  # close the polygon
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


# ═══════════════════════════════════════════════════════════════════════
# Batch helper
# ═══════════════════════════════════════════════════════════════════════

def _batch_from_obs(obs: Dict, cfg: Config, device):
    node_x, edge_index, edge_attr = build_graph(obs, cfg)
    return {
        "node_x": node_x.to(device),
        "edge_index": edge_index.to(device),
        "edge_attr": edge_attr.to(device),
        "batch_index": torch.zeros(node_x.shape[0], dtype=torch.long, device=device),
    }


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
    obs = env.reset(n_agents, scenario)
    device = torch_device(cfg.train.device) if torch is not None else "cpu"

    model = None
    if method in ["rvt_swarm", "gnn_only", "instant_cert"] and torch is not None:
        from .models import build_model
        model = build_model(
            method, cfg.train.hidden_dim, cfg.train.message_passes,
            getattr(cfg.train, "aux_gradient_scale", 0.3),
        ).to(device)
        ckpt = torch.load(Path(ckpt_dir) / f"{method}.pt", map_location=device, weights_only=False)
        model.load_state_dict(ckpt["model"])
        model.eval()

    frames: List[Dict] = []
    done = False
    steps = 0
    prev_topo = 0
    # Track cumulative collision counts for overlay
    cum_rr = 0
    cum_ro = 0

    while not done and steps < cfg.env.max_steps:
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
        }

        # Compute action
        if method in ["adaptive_formation", "cbf_qp_like", "orca_like", "centralized_mpc"]:
            actions, topo = historical_baseline(method, obs, cfg)
        else:
            batch = _batch_from_obs(obs, cfg, device)
            with torch.no_grad():
                out = model(batch)
            actions = out["actions"].cpu().numpy() * cfg.env.max_accel
            topo = 0
            recover = None
            if out["topology_logits"] is not None:
                topo = choose_counterfactual_topology(
                    obs, out["topology_logits"], out["recoverability_scores"],
                    cfg, prev_topo, out.get("uncertainty"),
                )
            if out["recoverability"] is not None:
                recover = float(out["recoverability"].squeeze().cpu().item())
            if method in ["rvt_swarm", "instant_cert"]:
                actions = simple_recover_shield(actions, obs, cfg, recover, topo)

        frame["topology_action"] = topo
        frames.append(frame)

        prev_topo = topo
        obs, _, done, info = env.step(actions, topo)
        steps += 1

        # Accumulate collisions
        cum_rr += int(info.get("rr_collision", 0) > 0)
        cum_ro += int(info.get("ro_collision", 0) > 0)

    # Capture final frame
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
) -> List[str]:
    """Generate GIFs for selected methods/scenarios/team sizes."""
    scenarios = scenarios or ["open_field", "narrow_passage"]
    team_sizes = team_sizes or [4, 8]
    gif_paths = []

    for method in methods:
        for scenario in scenarios:
            for n in team_sizes:
                print(f"  Recording {method} | {scenario} | n={n} ...")
                frames = record_episode(method, cfg, n, scenario, ckpt_dir, seed)
                fname = f"{method}_{scenario}_n{n}.gif"
                path = save_gif(frames, str(Path(out_dir) / fname), cfg, method, n, fps)
                gif_paths.append(path)

    return gif_paths


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
) -> List[str]:
    """Generate comparison GIFs grouping methods side-by-side."""
    if cfg is None:
        cfg = Config()
    scenarios = scenarios or ["open_field", "narrow_passage"]
    team_sizes = team_sizes or [4, 8]
    if method_groups is None:
        method_groups = [
            ["gnn_only", "instant_cert", "rvt_swarm"],
            ["rvt_swarm", "adaptive_formation", "cbf_qp_like", "orca_like"],
        ]

    gif_paths = []
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

    return gif_paths
