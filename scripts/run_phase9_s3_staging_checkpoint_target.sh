#!/usr/bin/env bash
set -euo pipefail

scratch=/tmp/rvt-a1s3
rm -rf "$scratch"
mkdir -p "$scratch/results/rvt_fd24"
cp /mnt/c/Users/avis/phase9g_a1r_continuation_stop_audit_v1.json \
  /mnt/c/Users/avis/phase9g_a1r_staging_checkpoint_v1.json \
  "$scratch/results/rvt_fd24/"
python3 /mnt/c/Users/avis/build_phase9_s3_staging_checkpoint.py \
  --root "$scratch" \
  --data-root /home/avis/rvt-data \
  --output /mnt/c/Users/avis/phase9_s3_staging_checkpoint_v1.json
