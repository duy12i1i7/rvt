#!/usr/bin/env bash
set -euo pipefail

image="sha256:8e26da918841eb146529bbb4ff95f3a55acf9793dcbc534f44dce0700d183a90"
source_commit="848e8b352a91e95af777ebbeccd5fbb43d53777e"
scratch="/home/avis/rvt-data/audit/phase9g-a1s3z-qualification-v3"

if [[ -e "$scratch" ]]; then
  echo "refusing to overwrite immutable A1S3Z audit namespace: $scratch" >&2
  exit 1
fi
mkdir -p "$scratch"

common=(
  docker run --rm --network none
  -e PYTHONPATH=/opt/rvt
  -e OMP_NUM_THREADS=1
  -e MKL_NUM_THREADS=1
  -e OPENBLAS_NUM_THREADS=1
  -e NUMEXPR_NUM_THREADS=1
  --mount "type=bind,src=$scratch,dst=/out"
  -w /opt/rvt
  "$image"
)

test "$(docker image inspect "$image" --format '{{.Id}}')" = "$image"
test "$(docker image inspect "$image" --format '{{index .Config.Labels "org.opencontainers.image.revision"}}')" = "$source_commit"
"${common[@]}" sh -lc \
  'test "$(git rev-parse HEAD)" = "$RVT_SOURCE_COMMIT" && test -z "$(git status --porcelain)"'

"${common[@]}" python scripts/audit_phase9_s3z_centerline.py \
  --root /opt/rvt \
  --execution-environment QUALIFIED_A1S3Z_PRODUCTION_DOCKER_LINUX_X86_64 \
  --output /out/phase9_s3_centerline_population_requalification_docker_v1.json

"${common[@]}" python scripts/audit_phase9_s3z_existing_data.py \
  --root /opt/rvt \
  --checkpoint /opt/rvt/results/rvt_fd24/phase9_s3_staging_checkpoint_v1.json \
  --previous-dependency /opt/rvt/results/rvt_fd24/phase9_s3_staging_dependency_audit_v1.json \
  --execution-environment QUALIFIED_A1S3Z_PRODUCTION_DOCKER_LINUX_X86_64 \
  --output /out/phase9_s3_existing_data_requalification_docker_v2.json

"${common[@]}" sh -lc \
  'pytest -q tests/test_phase9_s3z_centerline.py tests/test_phase9_s3r_scientific_stop.py tests/test_phase9_s3_scientific_closure.py tests/test_phase9c_candidate_execution.py tests/test_phase9c_candidate_clone_isolation.py tests/test_phase9c_matched_initial_state.py tests/test_phase9c_snapshot_future_equivalence.py tests/test_phase9g0r_official_binding.py tests/test_phase9g0r_scientific_addendum.py tests/test_phase9c_rb20_detached_reproduction.py > /out/focused-tests.log 2>&1'

chmod -R a-w "$scratch"
sha256sum "$scratch"/*.json "$scratch"/*.log
