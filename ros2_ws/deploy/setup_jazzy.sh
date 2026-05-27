#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"
REPO_DIR="$(cd "${ROOT_DIR}"/.. && pwd)"

if [[ ! -f /opt/ros/jazzy/setup.bash ]]; then
  echo "ROS 2 Jazzy was not found at /opt/ros/jazzy." >&2
  exit 1
fi

set +u
source /opt/ros/jazzy/setup.bash
set -u

cd "${REPO_DIR}"
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install "numpy>=1.24" "matplotlib>=3.8" "pillow>=10"
python3 -m pip install --index-url https://download.pytorch.org/whl/cpu "torch>=2.2"
deactivate

cd "${ROOT_DIR}"
colcon build --symlink-install --packages-select rvt_swarm_msgs rvt_swarm_ros

echo
echo "Jazzy workspace setup complete."
echo "Next:"
echo "  source ${REPO_DIR}/.venv/bin/activate"
echo "  source /opt/ros/jazzy/setup.bash"
echo "  source ${ROOT_DIR}/install/setup.bash"
