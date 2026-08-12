#!/usr/bin/env bash
set -euo pipefail

run_id="phase9g-a1r-study-a-train-validation-recoverability-continuation-20260812T061720Z"
data_root="/home/avis/rvt-data"
staging="$data_root/staging/study_a_zero_shot-train-recoverability"
validation="$data_root/staging/study_a_zero_shot-validation-recoverability"
audit="$data_root/audit/$run_id/continuation_stop_audit.json"

test -z "$(docker ps -aq --filter name=phase9g-a1r)"
test "$(stat -c '%a' "$staging")" = "555"
test "$(stat -c '%a' "$staging/recoverability")" = "555"
test "$(find "$staging/recoverability" -maxdepth 1 -name 'event-*.json' | wc -l)" -eq 210
test "$(find "$staging/recoverability" -maxdepth 1 -name 'event-*.json' -perm /222 | wc -l)" -eq 0
test "$(find "$staging" -name '*.partial' | wc -l)" -eq 0
test ! -e "$validation"

printf '{"audit_file_sha256":"%s","candidate_pair_transactions":210,"partial_files":0,"phase_containers":0,"staging_mode":"555","status":"PASS","validation_staging_exists":false}\n' \
  "$(sha256sum "$audit" | cut -d' ' -f1)"
