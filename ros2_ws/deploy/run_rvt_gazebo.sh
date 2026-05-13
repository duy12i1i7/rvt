#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"
REPO_DIR="$(cd "${ROOT_DIR}"/.. && pwd)"

if [[ ! -d "${REPO_DIR}/.venv" ]]; then
  echo "Missing ${REPO_DIR}/.venv. Run deploy/setup_jazzy.sh first." >&2
  exit 1
fi

source "${REPO_DIR}/.venv/bin/activate"
source /opt/ros/jazzy/setup.bash
source "${ROOT_DIR}/install/setup.bash"

export TURTLEBOT3_MODEL=waffle_pi

ros2 launch rvt_swarm_ros multi_turtlebot3_rvt.launch.py \
  robot_count:=4 \
  repo_root:="${REPO_DIR}" \
  ckpt_dir:="${REPO_DIR}/results" \
  goal_x:=4.0 \
  goal_y:=0.0 \
  "$@"

