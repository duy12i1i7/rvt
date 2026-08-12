#!/usr/bin/env bash
set -euo pipefail

run_id="phase9g-a1-study-a-train-validation-recoverability-20260812T042359Z"
data_root="/home/avis/rvt-data"
audit_root="${data_root}/audit/${run_id}"
deploy_root="${audit_root}/deploy"
activation="${data_root}/authorization/phase9g_a1_recoverability_command_activation_v1.json"
lifecycle="${audit_root}/study_a_zero_shot-train-recoverability.lifecycle.json"
attempt_root="${audit_root}/attempts/train-attempt-001"

state="$(python3 - "${lifecycle}" <<'PY'
import json
import sys

print(json.load(open(sys.argv[1], encoding="ascii"))["state"])
PY
)"
if [[ "${state}" != "FAILED" ]]; then
    echo "resume requires one preserved FAILED lifecycle" >&2
    exit 1
fi
if docker ps -a --format '{{.Names}}' | grep -qx \
    phase9g-a1-recoverability-train; then
    echo "prior train container still exists" >&2
    exit 1
fi
if [[ -e "${attempt_root}" ]]; then
    echo "attempt archive already exists" >&2
    exit 1
fi

mkdir -p "${attempt_root}"
cp "${lifecycle}" "${attempt_root}/lifecycle.json"
cp "${audit_root}/study_a_zero_shot-train-recoverability.stderr.log" \
    "${attempt_root}/stderr.log"
cp "${audit_root}/study_a_zero_shot-train-recoverability.stdout.jsonl" \
    "${attempt_root}/stdout.jsonl"
cp "${audit_root}/progress.json" "${attempt_root}/progress.json"

if [[ "$(git -C /home/avis/rvt rev-parse HEAD)" != \
    "6bcfc0e26c4b327ba63f2844eaa02d30d56903ba" ]]; then
    echo "target evidence checkout changed before resume" >&2
    exit 1
fi
if [[ -n "$(git -C /home/avis/rvt status --porcelain)" ]]; then
    echo "target evidence checkout is dirty before resume" >&2
    exit 1
fi
image="$(docker image inspect \
    sha256:88ecf1aac7cd95b5ba50811950090c13f78362274e5c5cdaeafaafde29a115f4 \
    --format '{{.Id}}')"
if [[ "${image}" != \
    "sha256:88ecf1aac7cd95b5ba50811950090c13f78362274e5c5cdaeafaafde29a115f4" ]]; then
    echo "production image changed before resume" >&2
    exit 1
fi
if find "${data_root}/staging" -name '*.partial' -print -quit | grep -q .; then
    echo "partial writer file remains before resume" >&2
    exit 1
fi

nohup env PYTHONPATH=/home/avis/rvt python3 \
    "${deploy_root}/scripts/monitor_phase9g_a1_recoverability.py" \
    --root /home/avis/rvt \
    --data-root "${data_root}" \
    --run-id "${run_id}" \
    --output "${audit_root}/progress.json" \
    --interval-seconds 30 \
    >"${audit_root}/monitor-resume.stdout.log" \
    2>"${audit_root}/monitor-resume.stderr.log" &
echo "$!" >"${audit_root}/monitor.pid"

nohup env PYTHONPATH=/home/avis/rvt python3 \
    "${deploy_root}/scripts/run_phase9g_a1_authorized_command.py" \
    --activation "${activation}" \
    --command-id study_a_zero_shot-train-recoverability \
    --data-root "${data_root}" \
    --status-output "${lifecycle}" \
    >"${audit_root}/train-resume-launcher.stdout.log" \
    2>"${audit_root}/train-resume-launcher.stderr.log" &
echo "$!" >"${audit_root}/train-launcher.pid"

sleep 3
docker ps --filter name=phase9g-a1-recoverability-train \
    --format 'CONTAINER={{.Names}} {{.Image}} {{.Status}}'
printf 'DURABLE_EVENTS_BEFORE_RESUME=%s\n' \
    "$(find "${data_root}/staging/study_a_zero_shot-train-recoverability" \
        -name 'event-*.json' | wc -l)"
