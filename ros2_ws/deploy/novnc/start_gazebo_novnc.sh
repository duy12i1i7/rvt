#!/usr/bin/env bash
set -euo pipefail

export DISPLAY="${DISPLAY:-:99}"
export LIBGL_ALWAYS_SOFTWARE="${LIBGL_ALWAYS_SOFTWARE:-1}"
export QT_X11_NO_MITSHM="${QT_X11_NO_MITSHM:-1}"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/tmp/runtime-root}"
mkdir -p "${XDG_RUNTIME_DIR}"
chmod 700 "${XDG_RUNTIME_DIR}"

SCREEN_GEOMETRY="${SCREEN_GEOMETRY:-2200x1400x24}"
NOVNC_PORT="${NOVNC_PORT:-6080}"
VNC_PORT="${VNC_PORT:-5900}"
ROBOT_COUNT="${ROBOT_COUNT:-6}"
WORLD="${WORLD:-/work/ros2_ws/src/rvt_swarm_ros/worlds/rvt_cluttered.world}"

set +u
source /opt/ros/jazzy/setup.bash
set -u

NAV2_TB3_SHARE="$(ros2 pkg prefix nav2_minimal_tb3_sim)/share/nav2_minimal_tb3_sim"
export GZ_SIM_RESOURCE_PATH="${GZ_SIM_RESOURCE_PATH:-}"
export GZ_SIM_RESOURCE_PATH="${NAV2_TB3_SHARE}/models:${NAV2_TB3_SHARE}:$(dirname "${WORLD}"):${GZ_SIM_RESOURCE_PATH}"
export TURTLEBOT3_MODEL=waffle_pi

Xvfb "${DISPLAY}" -screen 0 "${SCREEN_GEOMETRY}" -ac +extension GLX +render -noreset &
XVFB_PID=$!
sleep 1

fluxbox >/tmp/fluxbox.log 2>&1 &
x11vnc -display "${DISPLAY}" -forever -shared -nopw -listen 127.0.0.1 -rfbport "${VNC_PORT}" >/tmp/x11vnc.log 2>&1 &
websockify --web=/usr/share/novnc/ "0.0.0.0:${NOVNC_PORT}" "127.0.0.1:${VNC_PORT}" >/tmp/websockify.log 2>&1 &

echo "noVNC ready on port ${NOVNC_PORT}"
echo "World: ${WORLD}"

gz sim -r -v2 "${WORLD}" >/tmp/gz_sim.log 2>&1 &
GZ_PID=$!

sleep "${SPAWN_DELAY_SEC:-12}"

MODEL_XACRO="${NAV2_TB3_SHARE}/urdf/gz_waffle.sdf.xacro"
start_x=(-17.8 -13.4 -7.5 -1.2 6.0 15.6 18.0 -20.0)
start_y=(-1.1 -2.0 -0.7 -1.7 2.9 3.6 2.2 -0.4)
start_yaw=(0.11 0.15 0.14 0.22 0.02 -0.08 0.18 0.10)
body_colors=(
  "0.02 0.16 0.78 1"
  "0.02 0.55 0.18 1"
  "0.82 0.04 0.05 1"
  "0.95 0.78 0.04 1"
  "0.55 0.08 0.85 1"
  "0.02 0.55 0.72 1"
  "0.90 0.35 0.04 1"
  "0.18 0.18 0.20 1"
)
max_count="${#start_x[@]}"
if (( ROBOT_COUNT > max_count )); then
  echo "ROBOT_COUNT=${ROBOT_COUNT} exceeds built-in layout ${max_count}; using ${max_count}."
  ROBOT_COUNT="${max_count}"
fi

for ((idx=0; idx<ROBOT_COUNT; idx++)); do
  name="tb3_${idx}"
  sdf="/tmp/${name}.sdf"
  xacro "namespace:=${name}" "${MODEL_XACRO}" > "${sdf}"
  sed -i "s#package://nav2_minimal_tb3_sim#file://${NAV2_TB3_SHARE}#g" "${sdf}"
  body_color="${body_colors[$((idx % ${#body_colors[@]}))]}"
  sed -i "0,/<diffuse>1 1 1<\\/diffuse>/s//<diffuse>${body_color}<\\/diffuse>/" "${sdf}"
  sed -i "0,/<diffuse>1 1 1<\\/diffuse>/s//<diffuse>0.02 0.02 0.025 1<\\/diffuse>/" "${sdf}"
  sed -i "s/<diffuse>1 1 1<\\/diffuse>/<diffuse>0.01 0.01 0.012 1<\\/diffuse>/g" "${sdf}"
  ros2 run ros_gz_sim create \
    -name "${name}" \
    -file "${sdf}" \
    -x "${start_x[$idx]}" \
    -y "${start_y[$idx]}" \
    -z 0.01 \
    -Y "${start_yaw[$idx]}" || true
done

echo "Gazebo scene is running. Open http://localhost:${NOVNC_PORT}/vnc.html"

trap 'kill ${GZ_PID} ${XVFB_PID} 2>/dev/null || true' INT TERM
wait "${GZ_PID}"
