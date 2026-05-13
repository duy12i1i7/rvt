from setuptools import find_packages, setup

package_name = "rvt_swarm_ros"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{package_name}"]),
        (f"share/{package_name}", ["package.xml"]),
        (f"share/{package_name}/launch", ["launch/multi_turtlebot3_rvt.launch.py"]),
        (f"share/{package_name}/worlds", ["worlds/rvt_cluttered.world"]),
        (f"share/{package_name}/config", ["config/swarm_params.yaml", "config/turtlebot3_waffle_pi_rvt_bridge.yaml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="RVT-Swarm Authors",
    maintainer_email="tuan.dotrong@hust.edu.vn",
    description="ROS 2 and Gazebo runtime layer for RVT-Swarm.",
    license="MIT",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "rvt_agent = rvt_swarm_ros.agent_node:main",
        ],
    },
)
