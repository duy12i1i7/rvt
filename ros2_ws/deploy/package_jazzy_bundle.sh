#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")"/../.. && pwd)"
BUNDLE_ROOT="${REPO_DIR}/deploy"
STAGING_DIR="${BUNDLE_ROOT}/rvt_swarm_ros2_jazzy_bundle"
ARCHIVE_PATH="${BUNDLE_ROOT}/rvt_swarm_ros2_jazzy_bundle.tar.gz"
CKPT_SOURCE="${REPO_DIR}/results/rvt_swarm.pt"

if [[ ! -f "${CKPT_SOURCE}" ]]; then
  CKPT_SOURCE="$(find "${REPO_DIR}" -path '*/results/rvt_swarm.pt' -type f | head -n 1 || true)"
fi

if [[ -z "${CKPT_SOURCE}" || ! -f "${CKPT_SOURCE}" ]]; then
  echo "Unable to locate rvt_swarm.pt under ${REPO_DIR}." >&2
  exit 1
fi

rm -rf "${STAGING_DIR}"
mkdir -p "${STAGING_DIR}"

cp "${REPO_DIR}/requirements.txt" "${STAGING_DIR}/requirements.txt"
mkdir -p "${STAGING_DIR}/results"
cp "${CKPT_SOURCE}" "${STAGING_DIR}/results/rvt_swarm.pt"

cp -R "${REPO_DIR}/rvt_swarm" "${STAGING_DIR}/rvt_swarm"
mkdir -p "${STAGING_DIR}/ros2_ws/src"
cp "${REPO_DIR}/ros2_ws/README.md" "${STAGING_DIR}/ros2_ws/README.md"
cp "${REPO_DIR}/ros2_ws/.gitignore" "${STAGING_DIR}/ros2_ws/.gitignore"
cp -R "${REPO_DIR}/ros2_ws/src/rvt_swarm_msgs" "${STAGING_DIR}/ros2_ws/src/rvt_swarm_msgs"
cp -R "${REPO_DIR}/ros2_ws/src/rvt_swarm_ros" "${STAGING_DIR}/ros2_ws/src/rvt_swarm_ros"
mkdir -p "${STAGING_DIR}/ros2_ws/deploy"
cp "${REPO_DIR}/ros2_ws/deploy/setup_jazzy.sh" "${STAGING_DIR}/ros2_ws/deploy/setup_jazzy.sh"
cp "${REPO_DIR}/ros2_ws/deploy/run_rvt_gazebo.sh" "${STAGING_DIR}/ros2_ws/deploy/run_rvt_gazebo.sh"

find "${STAGING_DIR}" -type d -name '__pycache__' -prune -exec rm -rf {} +
find "${STAGING_DIR}" -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete

chmod +x "${STAGING_DIR}/ros2_ws/deploy/setup_jazzy.sh"
chmod +x "${STAGING_DIR}/ros2_ws/deploy/run_rvt_gazebo.sh"

cat > "${STAGING_DIR}/README.md" <<'EOF'
# RVT-Swarm ROS 2 Jazzy Bundle

This bundle contains the minimum source tree needed to run the RVT-Swarm
Gazebo Sim integration on another ROS 2 Jazzy machine.

Contents:
- `requirements.txt`
- `results/rvt_swarm.pt`
- `rvt_swarm/`
- `ros2_ws/`

Quick start:
1. Extract the archive.
2. Run `ros2_ws/deploy/setup_jazzy.sh`.
3. Run `ros2_ws/deploy/run_rvt_gazebo.sh`.
EOF

mkdir -p "${BUNDLE_ROOT}"
rm -f "${ARCHIVE_PATH}"
tar czf "${ARCHIVE_PATH}" -C "${BUNDLE_ROOT}" "$(basename "${STAGING_DIR}")"

echo "Created bundle:"
echo "  ${ARCHIVE_PATH}"
