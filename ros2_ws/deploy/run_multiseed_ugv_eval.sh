#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"
REPO_DIR="$(cd "${ROOT_DIR}"/.. && pwd)"

METHODS="${METHODS:-rvt_swarm adaptive_formation cbf_qp orca centralized_mpc}"
SEEDS="${SEEDS:-0 1 2 3 4}"
LOG_DIR="${LOG_DIR:-${REPO_DIR}/results/gazebo_runs}"
SUMMARY_JSON="${SUMMARY_JSON:-${LOG_DIR}/aggregate_summary.json}"
REFERENCE_METHOD="${REFERENCE_METHOD:-rvt_swarm}"

mkdir -p "${LOG_DIR}"

echo "Running multi-seed Gazebo evaluation"
echo "  methods:   ${METHODS}"
echo "  seeds:     ${SEEDS}"
echo "  log_dir:   ${LOG_DIR}"
echo "  reference: ${REFERENCE_METHOD}"
echo

for method in ${METHODS}; do
  for seed in ${SEEDS}; do
    run_name="${method}_seed${seed}"
    echo "=== ${run_name} ==="
    RUN_NAME="${run_name}" \
    METHOD="${method}" \
    SPAWN_SEED="${seed}" \
    LOG_DIR="${LOG_DIR}" \
    "${ROOT_DIR}/deploy/run_small_ugv_experiment.sh"
  done
done

echo
echo "Aggregating results into ${SUMMARY_JSON}"
"${ROOT_DIR}/deploy/aggregate_gazebo_runs.py" \
  --log-dir "${LOG_DIR}" \
  --reference "${REFERENCE_METHOD}" \
  --out "${SUMMARY_JSON}"
