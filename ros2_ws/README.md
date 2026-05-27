# RVT-Swarm ROS 2 / Gazebo Integration

This workspace wraps the existing RVT-Swarm runtime for `ROS 2 + Gazebo Sim`.
It keeps the learned controller, graph construction, topology selector, and
shield unchanged. The ROS layer only replaces the simulator-facing pieces:
odometry, LiDAR, peer-state exchange, and `cmd_vel` output.

## Layout

- `src/rvt_swarm_msgs`: lightweight custom interfaces for peer-state sharing
- `src/rvt_swarm_ros`: runtime node, formation/context adapter, Gazebo Sim launch,
  and a cluttered TurtleBot3 world

## Target robot

The launch files use `TurtleBot3 Waffle Pi`. It is a practical starting point:
- official ROS 2 and Gazebo support is mature
- LiDAR and odometry are already wired in the standard stack
- differential-drive control is simple enough to bridge from the 2D RVT action
  output to `cmd_vel`

## Prerequisites

- ROS 2 Jazzy
- `ros_gz_sim`
- `ros_gz_bridge`
- `turtlebot3_description`
- `turtlebot3_gazebo`
- `nav2_minimal_tb3_sim`
- `xacro`
- Python dependencies from the repo root:

```bash
cd /path/to/rvt
pip install -r requirements.txt
```

## Build

Use `--symlink-install`. The node resolves the repo root from the source tree,
so a regular copy-install is not the intended workflow for this scaffold.
Build the ROS workspace with the system Python from `/opt/ros/jazzy`, not with
the project `.venv` activated. The `.venv` is only for runtime dependencies
such as `torch`.

```bash
cd /path/to/rvt
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
deactivate

cd /path/to/rvt/ros2_ws
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install
source install/setup.bash
```

## Launch

The launch file spawns multiple TurtleBot3 robots in a cluttered world and
runs one RVT agent per robot.

```bash
cd /path/to/rvt/ros2_ws
source /opt/ros/jazzy/setup.bash
source install/setup.bash
export TURTLEBOT3_MODEL=waffle_pi
ros2 launch rvt_swarm_ros multi_turtlebot3_rvt.launch.py
```

If you see build errors such as `ModuleNotFoundError: No module named 'em'`,
it usually means `colcon` was invoked while `.venv` was still active. Deactivate
the virtual environment and build again.

Important arguments:

- `robot_count`: number of robots to spawn
- `method`: controller to run; supports `rvt_swarm` plus the current
  baseline names from `rvt_swarm.baselines`
- `repo_root`: absolute path to this repo
- `ckpt_dir`: directory containing `rvt_swarm.pt`
- `goal_x`, `goal_y`: shared goal for the swarm
- `spawn_seed`: random seed for spawn jitter
- `spawn_jitter`: per-robot spawn perturbation in meters
- `lightweight_mode`: when `true`, bridge only `odom`, `scan`, and `cmd_vel`,
  and skip `robot_state_publisher`

Example:

```bash
ros2 launch rvt_swarm_ros multi_turtlebot3_rvt.launch.py \
  robot_count:=4 \
  method:=rvt_swarm \
  repo_root:=/path/to/rvt \
  ckpt_dir:=/path/to/rvt/results \
  goal_x:=4.0 goal_y:=0.0 \
  spawn_seed:=0 spawn_jitter:=0.10 \
  lightweight_mode:=true
```

Additional experiment arguments:

- `enable_monitor`: start a swarm-level experiment monitor
- `timeout_sec`: stop the monitor after this many seconds
- `log_dir`: directory for JSON summary and CSV trace
- `run_name`: filename stem for the monitor outputs

Example with logging:

```bash
ros2 launch rvt_swarm_ros multi_turtlebot3_rvt.launch.py \
  robot_count:=2 \
  repo_root:=/path/to/rvt \
  ckpt_dir:=/path/to/rvt/results \
  goal_x:=4.0 goal_y:=0.0 \
  enable_monitor:=true \
  timeout_sec:=90 \
  log_dir:=/path/to/rvt/results/gazebo_runs \
  run_name:=ugv_small_trial
```

## Small UGV experiment

For a repeatable two-robot TurtleBot3 run with automatic logging, use:

```bash
cd /path/to/rvt/ros2_ws
./deploy/run_small_ugv_experiment.sh
```

Useful environment overrides:

- `METHOD=rvt_swarm`
- `SPAWN_SEED=0`
- `SPAWN_JITTER=0.10`
- `RUN_NAME=my_trial`
- `TIMEOUT_SEC=90`
- `LIGHTWEIGHT_MODE=true`

This script:

- launches a 2-robot RVT trial in the cluttered Gazebo world
- runs a swarm-level monitor alongside the agents
- writes a JSON summary and CSV time series under `results/gazebo_runs`

By default it enables `LIGHTWEIGHT_MODE=true`, which is the recommended path
for constrained remote machines because it removes nonessential Gazebo bridges
and skips `robot_state_publisher`.

The monitor reuses the simulator-side thresholds for:

- goal reached
- formation RMS / `FormOK`
- robot-robot collision
- robot-obstacle collision
- deadlock and irreversible collapse proxies

This keeps the Gazebo-side metrics close in meaning to the paper
benchmark, even though the physics stack is now ROS 2 + Gazebo Sim.

## Multi-seed evaluation and statistics

For repeated runs with seed variation, use:

```bash
cd /path/to/rvt/ros2_ws
METHODS="rvt_swarm adaptive_formation cbf_qp_like orca_like centralized_mpc" \
SEEDS="0 1 2 3 4" \
./deploy/run_multiseed_ugv_eval.sh
```

This script:

- runs one logged Gazebo trial per `(method, seed)` pair
- writes per-run JSON and CSV artifacts to `results/gazebo_runs`
- aggregates run summaries into `results/gazebo_runs/aggregate_summary.json`

The aggregator reports, per metric and per method:

- mean
- standard deviation
- 95% confidence interval
- permutation-test p-value on success rate versus the reference method

## Current scope

This integration is a realistic simulation bridge, not a production hardware
stack. The following parts are intentionally approximate:

- obstacle tracks are clustered from LiDAR instead of coming from a dedicated
  tracker
- bottleneck/progress context is estimated from local scan geometry and peer
  state
- the RVT acceleration output is projected into a differential-drive command
  with a heading controller

These approximations are enough for Gazebo bring-up and architecture testing.

## Current Jazzy status

The ROS layer now does the following:

- launches `ros_gz_sim` instead of `gazebo_ros`
- spawns one RVT agent per robot
- bridges namespaced `odom`, `scan`, `imu`, `joint_states`, `tf`, and `cmd_vel`
- uses the namespaced TurtleBot3 Gazebo Sim model from
  `nav2_minimal_tb3_sim`
- loads the RVT checkpoint from the repository root
- injects the repository `.venv` into the ROS node at runtime so the agent can
  import `torch` even when ROS uses the system Python

Validated smoke test on `100.86.40.33`:

- Gazebo Sim server starts
- multiple TurtleBot3 entities spawn
- RVT agents start without import errors
- Gazebo publishers and subscribers exist on `/tb3_0/odom`,
  `/tb3_0/scan`, and `/tb3_0/cmd_vel`
- ROS side receives `/tb3_0/odom` and `/tb3_0/scan`
- the RVT agent publishes `/tb3_0/cmd_vel`
- the optional monitor writes swarm-level JSON/CSV summaries for small
  UGV trials

For longer experiments, a machine with working GUI / OpenGL support is still
preferred because Gazebo Sim renders the lidar sensor through Ogre2.
