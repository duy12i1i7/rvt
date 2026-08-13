#!/usr/bin/env bash
set -euo pipefail

image="sha256:c2f8734403f6422c10e04531529458e7826c175cbec0933c5b7d936cebedf39f"
scratch="/home/avis/rvt-data/audit/phase9g-a1s3z-full-suite-v1"
if [[ -e "$scratch" ]]; then
  echo "refusing to overwrite immutable A1S3Z full-suite namespace" >&2
  exit 1
fi
mkdir -p "$scratch"
docker run --rm --network none \
  -e PYTHONPATH=/opt/rvt \
  -e OMP_NUM_THREADS=1 \
  -e MKL_NUM_THREADS=1 \
  -e OPENBLAS_NUM_THREADS=1 \
  -e NUMEXPR_NUM_THREADS=1 \
  -v "$scratch:/out:rw" \
  -w /opt/rvt \
  "$image" \
  sh -lc 'pytest -q > /out/full-suite.log 2>&1'
chmod -R a-w "$scratch"
tail -5 "$scratch/full-suite.log"
sha256sum "$scratch/full-suite.log"
