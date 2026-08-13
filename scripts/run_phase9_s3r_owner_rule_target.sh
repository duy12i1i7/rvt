#!/usr/bin/env bash
set -euo pipefail

image="sha256:88ecf1aac7cd95b5ba50811950090c13f78362274e5c5cdaeafaafde29a115f4"
scratch="/home/avis/rvt-data/audit/phase9g-a1s3r-owner-rule-v1"
scripts="/mnt/c/Users/avis/phase9-s3r-scripts"
if [[ -e "$scratch" ]]; then
  echo "refusing to overwrite immutable S3R audit namespace: $scratch" >&2
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
  -v "$scratch:/out:rw" \
  -w /opt/rvt \
  "$image" \
  python /diagnostic/audit_phase9_s3r_owner_rule.py \
    --root /opt/rvt \
    --execution-environment QUALIFIED_PRODUCTION_DOCKER_LINUX_X86_64 \
    --output /out/phase9_s3r_owner_rule_audit_docker_v1.json

chmod -R a-w "$scratch"
sha256sum "$scratch"/*.json
