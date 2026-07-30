#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"
REPO_DIR="$(cd "${ROOT_DIR}"/.. && pwd)"
IMAGE="${IMAGE:-rvt-gazebo-novnc:jazzy}"
CONTAINER_NAME="${CONTAINER_NAME:-rvt-gazebo-novnc}"
NOVNC_PORT="${NOVNC_PORT:-6080}"
ROBOT_COUNT="${ROBOT_COUNT:-6}"
SCREEN_GEOMETRY="${SCREEN_GEOMETRY:-2200x1400x24}"

docker build -t "${IMAGE}" "${ROOT_DIR}/deploy/novnc"

if docker ps -a --format '{{.Names}}' | grep -qx "${CONTAINER_NAME}"; then
  docker rm -f "${CONTAINER_NAME}" >/dev/null
fi

docker run -d \
  --name "${CONTAINER_NAME}" \
  -p "${NOVNC_PORT}:6080" \
  -e "ROBOT_COUNT=${ROBOT_COUNT}" \
  -e "SCREEN_GEOMETRY=${SCREEN_GEOMETRY}" \
  -e "WORLD=/work/ros2_ws/src/rvt_swarm_ros/worlds/rvt_cluttered.world" \
  -v "${REPO_DIR}:/work:ro" \
  "${IMAGE}" >/dev/null

echo "Gazebo noVNC container started: ${CONTAINER_NAME}"
echo "Open: http://localhost:${NOVNC_PORT}/vnc.html"
echo "Logs: docker logs -f ${CONTAINER_NAME}"
echo "Stop: docker rm -f ${CONTAINER_NAME}"
