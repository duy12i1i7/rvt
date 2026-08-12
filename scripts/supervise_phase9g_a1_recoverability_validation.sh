#!/usr/bin/env bash
set -euo pipefail

run_id="phase9g-a1-study-a-train-validation-recoverability-20260812T042359Z"
data_root="/home/avis/rvt-data"
audit_root="${data_root}/audit/${run_id}"
deploy_root="${audit_root}/deploy"
activation="${data_root}/authorization/phase9g_a1_recoverability_command_activation_v1.json"
train_lifecycle="${audit_root}/study_a_zero_shot-train-recoverability.lifecycle.json"
validation_lifecycle="${audit_root}/study_a_zero_shot-validation-recoverability.lifecycle.json"

while true; do
    state="$({ python3 - "${train_lifecycle}" <<'PY'
import json
import sys

try:
    print(json.load(open(sys.argv[1], encoding="ascii"))["state"])
except (FileNotFoundError, KeyError, ValueError):
    print("UNAVAILABLE")
PY
    } 2>/dev/null)"
    case "${state}" in
        COMPLETE)
            break
            ;;
        FAILED)
            echo "train lifecycle failed; validation remains blocked" >&2
            exit 1
            ;;
        *)
            sleep 30
            ;;
    esac
done

if [[ -e "${validation_lifecycle}" ]]; then
    echo "validation lifecycle already exists; refusing duplicate launch" >&2
    exit 1
fi

nohup env PYTHONPATH=/home/avis/rvt python3 \
    "${deploy_root}/scripts/run_phase9g_a1_authorized_command.py" \
    --activation "${activation}" \
    --command-id study_a_zero_shot-validation-recoverability \
    --data-root "${data_root}" \
    --status-output "${validation_lifecycle}" \
    >"${audit_root}/validation-launcher.stdout.log" \
    2>"${audit_root}/validation-launcher.stderr.log" &
echo "$!" >"${audit_root}/validation-launcher.pid"
echo "validation launched after completed train lifecycle"
