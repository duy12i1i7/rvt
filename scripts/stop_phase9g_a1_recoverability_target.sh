#!/usr/bin/env bash
set -euo pipefail

run_id="phase9g-a1-study-a-train-validation-recoverability-20260812T042359Z"
data_root="/home/avis/rvt-data"
audit_root="${data_root}/audit/${run_id}"
lifecycle="${audit_root}/study_a_zero_shot-train-recoverability.lifecycle.json"
attempt_root="${audit_root}/attempts/train-attempt-002"

state="$(python3 - "${lifecycle}" <<'PY'
import json
import sys

print(json.load(open(sys.argv[1], encoding="ascii"))["state"])
PY
)"
if [[ "${state}" != "FAILED" ]]; then
    echo "operational stop requires the second FAILED lifecycle" >&2
    exit 1
fi
if docker ps -a --format '{{.Names}}' | grep -qx \
    phase9g-a1-recoverability-train; then
    echo "train container remains present at operational stop" >&2
    exit 1
fi
if [[ -e "${attempt_root}" ]]; then
    echo "second attempt archive already exists" >&2
    exit 1
fi

mkdir -p "${attempt_root}"
cp "${lifecycle}" "${attempt_root}/lifecycle.json"
cp "${audit_root}/study_a_zero_shot-train-recoverability.stderr.log" \
    "${attempt_root}/stderr.log"
cp "${audit_root}/study_a_zero_shot-train-recoverability.stdout.jsonl" \
    "${attempt_root}/stdout.jsonl"
cp "${audit_root}/progress.json" "${attempt_root}/progress.json"

for staging in \
    "${data_root}/staging/study_a_zero_shot-train-recoverability" \
    "${data_root}/staging/study_a_zero_shot-validation-recoverability"; do
    if [[ ! -e "${staging}" ]]; then
        continue
    fi
    find "${staging}" -type f -exec chmod 0444 {} +
    find "${staging}" -depth -type d -exec chmod 0555 {} +
done

printf 'ARCHIVED_ATTEMPTS=%s\n' \
    "$(find "${audit_root}/attempts" -mindepth 1 -maxdepth 1 -type d | wc -l)"
printf 'DURABLE_TRAIN_EVENTS=%s\n' \
    "$(find "${data_root}/staging/study_a_zero_shot-train-recoverability" \
        -name 'event-*.json' | wc -l)"
printf 'DURABLE_VALIDATION_EVENTS=%s\n' \
    "$(find "${data_root}/staging/study_a_zero_shot-validation-recoverability" \
        -name 'event-*.json' 2>/dev/null | wc -l)"
