#!/usr/bin/env bash
set -euo pipefail

run_id="phase9g-a1r-study-a-train-validation-recoverability-continuation-20260812T061720Z"
data_root="/home/avis/rvt-data"
staging="$data_root/staging/study_a_zero_shot-train-recoverability"
audit="$data_root/audit/$run_id"
container="phase9g-a1r-recoverability-train"
image="sha256:88ecf1aac7cd95b5ba50811950090c13f78362274e5c5cdaeafaafde29a115f4"

test "$(find "$staging/recoverability" -maxdepth 1 -name 'event-*.json' | wc -l)" -eq 127
test "$(find "$staging" -name '*.partial' | wc -l)" -eq 0
test -z "$(docker ps -a --filter "name=^/${container}$" --format '{{.Names}}')"
mkdir -p "$audit/train-attempt-1"
test -z "$(find "$audit/train-attempt-1" -mindepth 1 -print -quit)"

# Existing files remain immutable; only the two directories admit new transactions.
chmod u+w "$staging" "$staging/recoverability"
test "$(find "$staging/recoverability" -maxdepth 1 -name 'event-*.json' -perm /222 | wc -l)" -eq 0

docker run -d \
  --name "$container" \
  --network none \
  -e PYTHONPATH=/opt/rvt \
  -e RVT_SOURCE_COMMIT=8cf64481cd17b2c44f7007d3722a8110e53cae46 \
  -e OMP_NUM_THREADS=1 \
  -e MKL_NUM_THREADS=1 \
  -e OPENBLAS_NUM_THREADS=1 \
  -e NUMEXPR_NUM_THREADS=1 \
  -v "$data_root:/rvt-data:rw" \
  -v "$audit/deploy:/continuation:ro" \
  -w /opt/rvt \
  "$image" \
  python /continuation/scripts/run_phase9g_a1r_recoverability_continuation.py \
    --root /opt/rvt \
    --split train \
    --writer-root /rvt-data/staging/study_a_zero_shot-train-recoverability \
    --audit-root "/rvt-data/audit/$run_id/train-attempt-1" \
    --source-commit 8cf64481cd17b2c44f7007d3722a8110e53cae46 \
    --docker-image "$image" \
    --job-manifest-sha256 801fe4e2bd694da0dda7c310226906e59d9bc5435d657fab2e3f132432aa2dc3 \
    --scientific-addendum-sha256 523d865cf04b7a5bd2a9cec8cb9a105fd5ef1f1476f6acec34e8cd47cf0dcad0 \
    --generation-provenance-root 452ea2d37b8a9b09db88f337423bc6ee9261863ca22fe609293fa11e2acb486c \
    --authorization-scope /rvt-data/authorization/phase9g_a1_authorization_scope_study_a_zero_shot-train-recoverability_v1.json \
    --authorization-scope-sha256 77319fcfd8822f56763ed09b7e9c71c3dcc851ea810165d301acacc2388d773a \
    --operational-amendment /continuation/results/rvt_fd24/phase9g_a1r_operational_contract_amendment_v1.json \
    --operational-amendment-sha256 1821badc6b09c2417a3fff98bb2f97673a69cdeff002b9ac1a64fac927d806e8 \
    --authorization-continuation /continuation/results/rvt_fd24/phase9g_a1r_authorization_continuation_v1.json \
    --authorization-continuation-sha256 fc83e2ff0671edba662852d68515bd28cba31cfb214e728afaa857a0f7164e9a \
    --run-identity /continuation/results/rvt_fd24/phase9g_a1r_continuation_run_identity_v1.json \
    --run-identity-sha256 98be39bf8653ea683aa6a948bb9419deb5c64b67c1e15a5b7215807a5b43f129 \
    --minimum-checkpoint /continuation/results/rvt_fd24/phase9g_a1r_staging_checkpoint_v1.json \
    --workers 12 \
    --numeric-threads 1 \
    --chunk-size 1 \
    --infrastructure-timeout-seconds 243
