#!/usr/bin/env bash
set -euo pipefail

run_id="phase9g-a1r-study-a-train-validation-recoverability-continuation-20260812T061720Z"
data_root="/home/avis/rvt-data"
staging="$data_root/staging/study_a_zero_shot-train-recoverability"
audit="$data_root/audit/$run_id/train-attempt-1"
container="phase9g-a1r-recoverability-train"

test "$(docker inspect --format '{{.State.Running}}' "$container")" == "false"
docker inspect "$container" > "$audit/container-inspect-after-failure.json"
docker logs "$container" > "$audit/container-stdout-after-failure.log" \
  2> "$audit/container-stderr-after-failure.log" || true
docker rm "$container" >/dev/null

find "$staging/recoverability" -maxdepth 1 -name 'event-*.json' -exec chmod 0444 {} +
chmod 0555 "$staging/recoverability" "$staging"
test "$(find "$staging" -name '*.partial' | wc -l)" -eq 0
test "$(find "$staging/recoverability" -maxdepth 1 -name 'event-*.json' | wc -l)" -eq 210
test "$(find "$staging/recoverability" -maxdepth 1 -name 'event-*.json' -perm /222 | wc -l)" -eq 0
stat -c '%A %U %G %n' "$staging" "$staging/recoverability"
