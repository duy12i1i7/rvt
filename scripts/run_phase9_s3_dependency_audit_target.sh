#!/usr/bin/env bash
set -euo pipefail

image="sha256:88ecf1aac7cd95b5ba50811950090c13f78362274e5c5cdaeafaafde29a115f4"
data_root="/home/avis/rvt-data"
scratch="$data_root/audit/phase9g-a1s3-staging-dependency"
scripts="/mnt/c/Users/avis/phase9-s3-scripts"
if [[ -e "$scratch" ]]; then
  echo "refusing to overwrite immutable diagnostic namespace: $scratch" >&2
  exit 1
fi
mkdir -p "$scratch"

docker run --rm \
  --network none \
  -e PYTHONPATH=/opt/rvt:/diagnostic \
  -e OMP_NUM_THREADS=1 \
  -e MKL_NUM_THREADS=1 \
  -e OPENBLAS_NUM_THREADS=1 \
  -e NUMEXPR_NUM_THREADS=1 \
  -v "$scripts:/diagnostic:ro" \
  -v "$data_root:/rvt-data:ro" \
  -v "$scratch:/out:rw" \
  -w /opt/rvt \
  "$image" \
  python /diagnostic/audit_phase9_s3_staging_dependency.py \
    --root /opt/rvt \
    --data-root /rvt-data \
    --checkpoint /diagnostic/phase9_s3_staging_checkpoint_v1.json \
    --execution-environment QUALIFIED_PRODUCTION_DOCKER_LINUX_X86_64 \
    --output /out/phase9_s3_staging_dependency_audit_v1.json

chmod -R a-w "$scratch"
sha256sum "$scratch"/*.json
