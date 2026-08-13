#!/usr/bin/env bash
set -euo pipefail

image="sha256:8e26da918841eb146529bbb4ff95f3a55acf9793dcbc534f44dce0700d183a90"
scratch="/home/avis/rvt-data/audit/phase9g-a1s3z-full-suite-v3"
if [[ -e "$scratch" ]]; then
  echo "refusing to overwrite immutable A1S3Z full-suite namespace" >&2
  exit 1
fi
mkdir -p "$scratch"
docker run --rm --network none \
  --user root \
  -e PYTHONPATH=/opt/rvt \
  -e OMP_NUM_THREADS=1 \
  -e MKL_NUM_THREADS=1 \
  -e OPENBLAS_NUM_THREADS=1 \
  -e NUMEXPR_NUM_THREADS=1 \
  -v "$scratch:/out:rw" \
  -w /opt/rvt \
  "$image" \
  sh -lc 'cp -a /opt/rvt /tmp/rvt-test && chown -R rvt:rvt /tmp/rvt-test && cd /tmp/rvt-test && su -s /bin/sh rvt -c "PYTHONPATH=/tmp/rvt-test pytest -q" > /out/full-suite.log 2>&1'
docker run --rm --user root -v "$scratch:/out:rw" "$image" \
  chmod -R a-w /out
chmod a-w "$scratch"
tail -5 "$scratch/full-suite.log"
sha256sum "$scratch/full-suite.log"
