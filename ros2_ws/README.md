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
- `repo_root`: absolute path to this repo
- `ckpt_dir`: directory containing `rvt_swarm.pt`
- `goal_x`, `goal_y`: shared goal for the swarm

Example:

```bash
ros2 launch rvt_swarm_ros multi_turtlebot3_rvt.launch.py \
  robot_count:=4 \
  repo_root:=/path/to/rvt \
  ckpt_dir:=/path/to/rvt/results \
  goal_x:=4.0 goal_y:=0.0
```

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

For longer experiments, a machine with working GUI / OpenGL support is still
preferred because Gazebo Sim renders the lidar sensor through Ogre2.
