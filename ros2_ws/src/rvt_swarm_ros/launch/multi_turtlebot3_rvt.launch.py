from __future__ import annotations

import random
from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import AppendEnvironmentVariable, DeclareLaunchArgument, EmitEvent, IncludeLaunchDescription, OpaqueFunction, RegisterEventHandler, SetEnvironmentVariable
from launch.event_handlers import OnProcessExit
from launch.events import Shutdown
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import Command, FindExecutable, LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def _spawn_swarm(
    context,
    pkg_share: Path,
    nav2_tb3_share: Path,
    urdf_path: Path,
    repo_root,
    ckpt_dir,
    goal_x,
    goal_y,
    method,
    world_path,
    log_dir,
    run_name,
    timeout_sec,
    spawn_seed,
    spawn_jitter,
):
    count = max(1, int(LaunchConfiguration("robot_count").perform(context)))
    names = [f"tb3_{i}" for i in range(count)]
    start_x = [-3.0, -3.0, -2.2, -2.2, -1.4, -1.4, -0.6, -0.6]
    start_y = [-0.8, 0.8, -0.8, 0.8, -0.8, 0.8, -0.8, 0.8]
    if count > len(start_x):
        raise RuntimeError(f"robot_count={count} exceeds the built-in spawn layout ({len(start_x)} robots).")
    rng = random.Random(int(spawn_seed.perform(context)))
    jitter = max(0.0, float(spawn_jitter.perform(context)))

    entities = []
    robot_description = urdf_path.read_text()
    model_sdf_xacro = nav2_tb3_share / "urdf" / "gz_waffle.sdf.xacro"
    bridge_cfg = str(pkg_share / "config" / "turtlebot3_waffle_pi_rvt_bridge.yaml")
    for idx, name in enumerate(names):
        spawn_x = start_x[idx] + (rng.uniform(-jitter, jitter) if jitter > 0.0 else 0.0)
        spawn_y = start_y[idx] + (rng.uniform(-jitter, jitter) if jitter > 0.0 else 0.0)
        entities.extend(
            [
                Node(
                    package="robot_state_publisher",
                    executable="robot_state_publisher",
                    namespace=name,
                    name="robot_state_publisher",
                    output="screen",
                    parameters=[{"use_sim_time": True, "robot_description": robot_description, "frame_prefix": f"{name}/"}],
                ),
                Node(
                    package="ros_gz_bridge",
                    executable="parameter_bridge",
                    output="screen",
                    namespace=name,
                    parameters=[{"config_file": bridge_cfg, "expand_gz_topic_names": True, "use_sim_time": True}],
                ),
                Node(
                    package="ros_gz_sim",
                    executable="create",
                    output="screen",
                    namespace=name,
                    arguments=[
                        "-name",
                        name,
                        "-string",
                        Command([FindExecutable(name="xacro"), " ", "namespace:=", name, " ", str(model_sdf_xacro)]),
                        "-x",
                        str(spawn_x),
                        "-y",
                        str(spawn_y),
                        "-z",
                        "0.01",
                    ],
                ),
                Node(
                    package="rvt_swarm_ros",
                    executable="rvt_agent",
                    namespace=name,
                    output="screen",
                    parameters=[
                        str(pkg_share / "config" / "swarm_params.yaml"),
                        {
                            "use_sim_time": True,
                            "repo_root": repo_root,
                            "ckpt_dir": ckpt_dir,
                            "method": method,
                            "robot_name": name,
                            "robot_id": idx,
                            "team_members": names,
                            "goal_x": goal_x,
                            "goal_y": goal_y,
                        },
                    ],
                ),
            ]
        )
    if LaunchConfiguration("enable_monitor").perform(context).lower() in {"true", "1", "yes"}:
        monitor = Node(
            package="rvt_swarm_ros",
            executable="swarm_monitor",
            name="swarm_monitor",
            output="screen",
            parameters=[
                {
                    "use_sim_time": True,
                    "repo_root": repo_root,
                    "team_members": names,
                    "method": method,
                    "goal_x": ParameterValue(goal_x, value_type=float),
                    "goal_y": ParameterValue(goal_y, value_type=float),
                    "timeout_sec": ParameterValue(timeout_sec, value_type=float),
                    "world_path": world_path,
                    "log_dir": log_dir,
                    "run_name": run_name,
                }
            ],
        )
        entities.append(monitor)
        entities.append(
            RegisterEventHandler(
                OnProcessExit(
                    target_action=monitor,
                    on_exit=[EmitEvent(event=Shutdown(reason="swarm monitor completed"))],
                )
            )
        )
    return entities


def generate_launch_description() -> LaunchDescription:
    pkg_share = Path(get_package_share_directory("rvt_swarm_ros"))
    turtlebot_share = Path(get_package_share_directory("turtlebot3_description"))
    nav2_tb3_share = Path(get_package_share_directory("nav2_minimal_tb3_sim"))
    ros_gz_sim_share = Path(get_package_share_directory("ros_gz_sim"))

    repo_root = LaunchConfiguration("repo_root")
    ckpt_dir = LaunchConfiguration("ckpt_dir")
    goal_x = LaunchConfiguration("goal_x")
    goal_y = LaunchConfiguration("goal_y")
    method = LaunchConfiguration("method")
    robot_count = LaunchConfiguration("robot_count")
    turtlebot_model = LaunchConfiguration("turtlebot_model")
    gazebo_gui = LaunchConfiguration("gazebo_gui")
    enable_monitor = LaunchConfiguration("enable_monitor")
    timeout_sec = LaunchConfiguration("timeout_sec")
    log_dir = LaunchConfiguration("log_dir")
    run_name = LaunchConfiguration("run_name")
    spawn_seed = LaunchConfiguration("spawn_seed")
    spawn_jitter = LaunchConfiguration("spawn_jitter")

    world = pkg_share / "worlds" / "rvt_cluttered.world"
    urdf = turtlebot_share / "urdf" / "turtlebot3_waffle_pi.urdf"

    launch_entities = [
        DeclareLaunchArgument("repo_root", default_value=str(Path(__file__).resolve().parents[4])),
        DeclareLaunchArgument("ckpt_dir", default_value=str(Path(__file__).resolve().parents[4] / "results")),
        DeclareLaunchArgument("goal_x", default_value="4.0"),
        DeclareLaunchArgument("goal_y", default_value="0.0"),
        DeclareLaunchArgument("method", default_value="rvt_swarm"),
        DeclareLaunchArgument("robot_count", default_value="4"),
        DeclareLaunchArgument("turtlebot_model", default_value="waffle_pi"),
        DeclareLaunchArgument("gazebo_gui", default_value="false"),
        DeclareLaunchArgument("enable_monitor", default_value="true"),
        DeclareLaunchArgument("timeout_sec", default_value="90.0"),
        DeclareLaunchArgument("log_dir", default_value=str(Path(__file__).resolve().parents[4] / "results" / "gazebo_runs")),
        DeclareLaunchArgument("run_name", default_value=""),
        DeclareLaunchArgument("spawn_seed", default_value="0"),
        DeclareLaunchArgument("spawn_jitter", default_value="0.10"),
        SetEnvironmentVariable("TURTLEBOT3_MODEL", turtlebot_model),
        SetEnvironmentVariable("RVT_SWARM_REPO", repo_root),
        AppendEnvironmentVariable("GZ_SIM_RESOURCE_PATH", str(nav2_tb3_share / "models")),
        AppendEnvironmentVariable("GZ_SIM_RESOURCE_PATH", str(nav2_tb3_share.parent.resolve())),
        AppendEnvironmentVariable("GZ_SIM_RESOURCE_PATH", str(pkg_share / "worlds")),
        Node(
            package="ros_gz_bridge",
            executable="parameter_bridge",
            name="clock_bridge",
            output="screen",
            arguments=["/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock"],
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(str(ros_gz_sim_share / "launch" / "gz_sim.launch.py")),
            launch_arguments={"gz_args": f"-r -s -v2 {world}", "on_exit_shutdown": "true"}.items(),
        ),
    ]
    launch_entities.append(
        OpaqueFunction(
            function=lambda context: (
                [
                    IncludeLaunchDescription(
                        PythonLaunchDescriptionSource(str(ros_gz_sim_share / "launch" / "gz_sim.launch.py")),
                        launch_arguments={"gz_args": "-g -v2", "on_exit_shutdown": "true"}.items(),
                    )
                ]
                if LaunchConfiguration("gazebo_gui").perform(context).lower() in {"true", "1", "yes"}
                else []
            )
        )
    )

    launch_entities.append(
        OpaqueFunction(
            function=lambda context: _spawn_swarm(
                context,
                pkg_share,
                nav2_tb3_share,
                urdf,
                repo_root,
                ckpt_dir,
                goal_x,
                goal_y,
                method,
                str(world),
                log_dir,
                run_name,
                timeout_sec,
                spawn_seed,
                spawn_jitter,
            )
        )
    )

    return LaunchDescription(launch_entities)
