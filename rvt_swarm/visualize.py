"""Episode visualization → GIF for paper figures."""
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
from .utils import torch_device

try:
    import torch
except ImportError:
    torch = None

try:
    from PIL import Image
except ImportError:
    Image = None


ROBOT_COLORS = plt.cm.Set2.colors
OBSTACLE_COLOR = "#8B0000"
GOAL_COLOR = "#228B22"
TRAIL_ALPHA = 0.15


def _batch_from_obs(obs: Dict, cfg: Config, device):
    node_x, edge_index, edge_attr = build_graph(obs, cfg)
    return {
        "node_x": node_x.to(device),
        "edge_index": edge_index.to(device),
        "edge_attr": edge_attr.to(device),
        "batch_index": torch.zeros(node_x.shape[0], dtype=torch.long, device=device),
    }


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

    while not done and steps < cfg.env.max_steps:
        # Record current state
        frame = {
            "positions": obs["positions"].copy(),
            "goal": obs["goal"].copy(),
            "obstacles": obs["obstacles"].copy(),
            "topology_mode": obs["topology_mode"],
            "formation_error": obs["formation_error"].copy(),
            "scenario": scenario,
            "step": steps,
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

    # Capture final frame
    frames.append({
        "positions": obs["positions"].copy(),
        "goal": obs["goal"].copy(),
        "obstacles": obs["obstacles"].copy(),
        "topology_mode": obs["topology_mode"],
        "formation_error": obs["formation_error"].copy(),
        "scenario": scenario,
        "step": steps,
        "topology_action": prev_topo,
    })
    return frames


def render_frame(
    frame: Dict,
    trails: List[np.ndarray],
    ax: plt.Axes,
    cfg: Config,
    method: str,
    n_agents: int,
) -> None:
    """Render a single frame onto the axes."""
    ax.clear()
    ws = cfg.env.world_size * 0.55
    ax.set_xlim(-ws, ws)
    ax.set_ylim(-ws, ws)
    ax.set_aspect("equal")
    ax.set_facecolor("#F5F5F5")
    ax.grid(True, alpha=0.2)

    # Goal
    goal = frame["goal"]
    goal_circle = plt.Circle(goal, cfg.env.goal_tolerance, color=GOAL_COLOR, alpha=0.25, zorder=1)
    ax.add_patch(goal_circle)
    ax.plot(*goal, marker="*", color=GOAL_COLOR, markersize=14, zorder=5)

    # Obstacles
    for o in frame["obstacles"]:
        circ = plt.Circle(o, cfg.env.obstacle_radius, color=OBSTACLE_COLOR, alpha=0.45, zorder=2)
        ax.add_patch(circ)

    # Trails
    for i, trail in enumerate(trails):
        if len(trail) < 2:
            continue
        t = np.array(trail)
        color = ROBOT_COLORS[i % len(ROBOT_COLORS)]
        ax.plot(t[:, 0], t[:, 1], color=color, alpha=TRAIL_ALPHA, linewidth=1.0, zorder=2)

    # Formation edges (connect neighbors)
    pos = frame["positions"]
    for i in range(n_agents):
        for j in range(i + 1, n_agents):
            d = np.linalg.norm(pos[i] - pos[j])
            if d < cfg.env.sensing_radius * 0.6:
                ax.plot(
                    [pos[i, 0], pos[j, 0]], [pos[i, 1], pos[j, 1]],
                    color="#AAAAAA", alpha=0.3, linewidth=0.6, zorder=2,
                )

    # Robots
    for i in range(n_agents):
        color = ROBOT_COLORS[i % len(ROBOT_COLORS)]
        circ = plt.Circle(pos[i], cfg.env.robot_radius, color=color, alpha=0.85, zorder=4)
        ax.add_patch(circ)
        # Formation error arrow
        fe = frame["formation_error"][i]
        if np.linalg.norm(fe) > 0.05:
            ax.annotate(
                "", xy=pos[i] + fe * 0.5, xytext=pos[i],
                arrowprops=dict(arrowstyle="->", color=color, alpha=0.5, lw=0.8),
                zorder=3,
            )

    # Labels
    topo_name = TOPOLOGY_ACTIONS.get(frame.get("topology_action", 0), "keep")
    title = f"{method}  |  step {frame['step']}  |  {frame['scenario']}  |  n={n_agents}  |  topo={topo_name}"
    ax.set_title(title, fontsize=9, fontweight="bold")
    ax.tick_params(labelsize=6)


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

    fig, ax = plt.subplots(1, 1, figsize=(6, 6), dpi=dpi)
    trails = [[] for _ in range(n_agents)]
    images = []

    for frame in frames:
        for i in range(n_agents):
            trails[i].append(frame["positions"][i].copy())
        render_frame(frame, trails, ax, cfg, method, n_agents)
        fig.canvas.draw()
        w, h = fig.canvas.get_width_height()
        buf = np.frombuffer(fig.canvas.tostring_rgb(), dtype=np.uint8).reshape(h, w, 3)
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
                if method == "centralized_mpc" and n != 4:
                    continue
                print(f"  Recording {method} | {scenario} | n={n} ...")
                frames = record_episode(method, cfg, n, scenario, ckpt_dir, seed)
                fname = f"{method}_{scenario}_n{n}.gif"
                path = save_gif(frames, str(Path(out_dir) / fname), cfg, method, n, fps)
                gif_paths.append(path)

    return gif_paths


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

    # Per-method trails
    all_trails = {m: [[] for _ in range(n_agents)] for m in methods}
    images = []

    for step_idx in range(max_steps):
        for m_idx, method in enumerate(methods):
            r, c = divmod(m_idx, cols)
            ax = axes[r, c]
            frames = all_frames[method]
            # Clamp to last frame if this method ended earlier
            frame = frames[min(step_idx, len(frames) - 1)]
            trails = all_trails[method]
            if step_idx < len(frames):
                for i in range(n_agents):
                    trails[i].append(frame["positions"][i].copy())
            render_frame(frame, trails, ax, cfg, method, n_agents)

        fig.suptitle(
            f"Comparison  |  {scenario}  |  n={n_agents}  |  step {step_idx}",
            fontsize=12, fontweight="bold", y=0.995,
        )
        fig.tight_layout(rect=[0, 0, 1, 0.97])
        fig.canvas.draw()
        w, h = fig.canvas.get_width_height()
        buf = np.frombuffer(fig.canvas.tostring_rgb(), dtype=np.uint8).reshape(h, w, 3)
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
    """Generate comparison GIFs grouping methods side-by-side.

    Default groups:
      1) Learned: gnn_only vs instant_cert vs rvt_swarm
      2) All:     rvt_swarm vs centralized_mpc vs adaptive_formation vs cbf_qp_like
    """
    if cfg is None:
        cfg = Config()
    scenarios = scenarios or ["open_field", "narrow_passage"]
    team_sizes = team_sizes or [4, 8]
    if method_groups is None:
        method_groups = [
            ["gnn_only", "instant_cert", "rvt_swarm"],
            ["rvt_swarm", "centralized_mpc", "adaptive_formation", "cbf_qp_like"],
        ]

    gif_paths = []
    for group in method_groups:
        group_name = "_vs_".join(group[:3])
        if len(group) > 3:
            group_name += f"_+{len(group) - 3}"
        for scenario in scenarios:
            for n in team_sizes:
                # Skip if any method in group can't run this size
                effective = [m for m in group if not (m == "centralized_mpc" and n != 4)]
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
