#!/usr/bin/env bash
set -euo pipefail

run_id="phase9g-a1r-study-a-train-validation-recoverability-continuation-20260812T061720Z"
data_root="/home/avis/rvt-data"
split="${1:-train}"
container="phase9g-a1r-recoverability-${split}"
attempt="$data_root/audit/$run_id/${split}-attempt-1"
status="$attempt/${split}-continuation-status.json"
staging="$data_root/staging/study_a_zero_shot-${split}-recoverability/recoverability"

docker inspect \
  --format 'container={{.Name}} running={{.State.Running}} status={{.State.Status}} exit={{.State.ExitCode}} started={{.State.StartedAt}} finished={{.State.FinishedAt}}' \
  "$container"
if [[ "$(docker inspect --format '{{.State.Running}}' "$container")" == "true" ]]; then
  docker stats --no-stream \
    --format 'resources cpu={{.CPUPerc}} memory={{.MemUsage}} pids={{.PIDs}}' \
    "$container"
fi
python3 - "$status" "$staging" "$attempt/${split}-operational-telemetry.jsonl" <<'PY'
import json
import sys
from pathlib import Path

status_path = Path(sys.argv[1])
staging = Path(sys.argv[2])
telemetry_path = Path(sys.argv[3])
result = {
    "durable_transactions": len(tuple(staging.glob("event-*.json"))),
    "partial_files": len(tuple(staging.glob("*.partial"))),
}
if status_path.exists():
    status = json.loads(status_path.read_text(encoding="ascii"))
    for key in (
        "state",
        "completed_event_identities_reused",
        "unresolved_event_identities_scheduled",
        "events_completed_this_continuation",
        "candidate_aggregates_completed_this_continuation",
        "replicas_completed_this_continuation",
        "maximum_atomic_unit_wall_seconds",
        "official_transactions_written_this_continuation",
        "duplicate_replays_this_continuation",
        "failure_class",
        "failure_message",
        "updated_at_utc",
    ):
        if key in status:
            result[key] = status[key]
if telemetry_path.exists() and telemetry_path.stat().st_size:
    last = telemetry_path.read_text(encoding="ascii").splitlines()[-1]
    telemetry = json.loads(last)
    result["last_event_id"] = telemetry["decision_event_id"]
    result["last_reconciliation_wall_seconds"] = telemetry[
        "candidate_pair_reconciliation_wall_seconds"
    ]
    result["last_candidate_wall_seconds"] = [
        item["wall_seconds"] for item in telemetry["candidate_units"]
    ]
print(json.dumps(result, sort_keys=True))
PY
