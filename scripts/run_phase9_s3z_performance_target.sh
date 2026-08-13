#!/usr/bin/env bash
set -euo pipefail

image="sha256:c2f8734403f6422c10e04531529458e7826c175cbec0933c5b7d936cebedf39f"
source_commit="20bfa1bfdc311f67075327418595441b101bc8de"
scratch="/home/avis/rvt-data/audit/phase9g-a1s3z-performance-v1"
if [[ -e "$scratch" ]]; then
  echo "refusing to overwrite immutable A1S3Z performance namespace" >&2
  exit 1
fi
mkdir -p "$scratch"

docker run --rm --network none \
  -e PYTHONPATH=/opt/rvt:/diagnostic \
  -e OMP_NUM_THREADS=1 \
  -e MKL_NUM_THREADS=1 \
  -e OPENBLAS_NUM_THREADS=1 \
  -e NUMEXPR_NUM_THREADS=1 \
  -v /mnt/c/Users/avis/run_phase9_s3z_performance.py:/diagnostic/run_phase9_s3z_performance.py:ro \
  -v /mnt/c/Users/avis/phase9_s3z_performance_manifest_v1.json:/diagnostic/manifest.json:ro \
  -v "$scratch:/out:rw" \
  -w /opt/rvt \
  "$image" \
  python /diagnostic/run_phase9_s3z_performance.py \
    --root /opt/rvt \
    --manifest /diagnostic/manifest.json \
    --output /out/phase9_s3z_performance_result_v1.json \
    --image "$image" \
    --source-commit "$source_commit"

chmod -R a-w "$scratch"
sha256sum "$scratch"/*.json
