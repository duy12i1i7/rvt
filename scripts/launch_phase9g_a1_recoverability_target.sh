#!/usr/bin/env bash
set -euo pipefail

run_id="phase9g-a1-study-a-train-validation-recoverability-20260812T042359Z"
data_root="/home/avis/rvt-data"
audit_root="${data_root}/audit/${run_id}"
deploy_root="${audit_root}/deploy"
activation="${data_root}/authorization/phase9g_a1_recoverability_command_activation_v1.json"

if find "${data_root}/staging" -type f -print -quit | grep -q .; then
    echo "official staging was not empty before first launch" >&2
    exit 1
fi

nohup env PYTHONPATH=/home/avis/rvt python3 \
    "${deploy_root}/scripts/monitor_phase9g_a1_recoverability.py" \
    --root /home/avis/rvt \
    --data-root "${data_root}" \
    --run-id "${run_id}" \
    --output "${audit_root}/progress.json" \
    --interval-seconds 30 \
    >"${audit_root}/monitor.stdout.log" \
    2>"${audit_root}/monitor.stderr.log" &
echo "$!" >"${audit_root}/monitor.pid"

nohup env PYTHONPATH=/home/avis/rvt python3 \
    "${deploy_root}/scripts/run_phase9g_a1_authorized_command.py" \
    --activation "${activation}" \
    --command-id study_a_zero_shot-train-recoverability \
    --data-root "${data_root}" \
    --status-output \
        "${audit_root}/study_a_zero_shot-train-recoverability.lifecycle.json" \
    >"${audit_root}/train-launcher.stdout.log" \
    2>"${audit_root}/train-launcher.stderr.log" &
echo "$!" >"${audit_root}/train-launcher.pid"

sleep 3
printf 'MONITOR_PID=%s\n' "$(cat "${audit_root}/monitor.pid")"
printf 'TRAIN_PID=%s\n' "$(cat "${audit_root}/train-launcher.pid")"
docker ps --filter name=phase9g-a1-recoverability-train \
    --format 'CONTAINER={{.Names}} {{.Image}} {{.Status}}'
printf 'STAGING_FILES=%s\n' "$(find "${data_root}/staging" -type f | wc -l)"
