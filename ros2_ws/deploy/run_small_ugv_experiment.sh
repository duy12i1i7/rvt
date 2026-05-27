#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"
REPO_DIR="$(cd "${ROOT_DIR}"/.. && pwd)"

if [[ ! -d "${REPO_DIR}/.venv" ]]; then
  echo "Missing ${REPO_DIR}/.venv. Run deploy/setup_jazzy.sh first." >&2
  exit 1
fi

if [[ ! -f "${REPO_DIR}/results/rvt_swarm.pt" ]]; then
  echo "Missing checkpoint ${REPO_DIR}/results/rvt_swarm.pt." >&2
  exit 1
fi

source "${REPO_DIR}/.venv/bin/activate"
set +u
source /opt/ros/jazzy/setup.bash
source "${ROOT_DIR}/install/setup.bash"
set -u

export TURTLEBOT3_MODEL=waffle_pi

RUN_NAME="${RUN_NAME:-ugv_small_$(date +%Y%m%d_%H%M%S)}"
LOG_DIR="${LOG_DIR:-${REPO_DIR}/results/gazebo_runs}"
ROBOT_COUNT="${ROBOT_COUNT:-2}"
GOAL_X="${GOAL_X:-4.0}"
GOAL_Y="${GOAL_Y:-0.0}"
METHOD="${METHOD:-rvt_swarm}"
TIMEOUT_SEC="${TIMEOUT_SEC:-90}"
GAZEBO_GUI="${GAZEBO_GUI:-false}"
SPAWN_SEED="${SPAWN_SEED:-0}"
SPAWN_JITTER="${SPAWN_JITTER:-0.10}"
LIGHTWEIGHT_MODE="${LIGHTWEIGHT_MODE:-true}"

mkdir -p "${LOG_DIR}"

echo "Running small RVT UGV experiment"
echo "  run_name:    ${RUN_NAME}"
echo "  log_dir:     ${LOG_DIR}"
echo "  method:      ${METHOD}"
echo "  robot_count: ${ROBOT_COUNT}"
echo "  goal:        (${GOAL_X}, ${GOAL_Y})"
echo "  timeout:     ${TIMEOUT_SEC}s"
echo "  spawn_seed:  ${SPAWN_SEED}"
echo "  jitter:      ${SPAWN_JITTER}"
echo "  lightweight: ${LIGHTWEIGHT_MODE}"

ros2 launch rvt_swarm_ros multi_turtlebot3_rvt.launch.py \
  robot_count:="${ROBOT_COUNT}" \
  repo_root:="${REPO_DIR}" \
  ckpt_dir:="${REPO_DIR}/results" \
  goal_x:="${GOAL_X}" \
  goal_y:="${GOAL_Y}" \
  method:="${METHOD}" \
  gazebo_gui:="${GAZEBO_GUI}" \
  enable_monitor:=true \
  timeout_sec:="${TIMEOUT_SEC}" \
  log_dir:="${LOG_DIR}" \
  run_name:="${RUN_NAME}" \
  spawn_seed:="${SPAWN_SEED}" \
  spawn_jitter:="${SPAWN_JITTER}" \
  lightweight_mode:="${LIGHTWEIGHT_MODE}"

echo
echo "Expected summary:"
echo "  ${LOG_DIR}/${RUN_NAME}.json"
echo "Expected trace:"
echo "  ${LOG_DIR}/${RUN_NAME}.csv"
