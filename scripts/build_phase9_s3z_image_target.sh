#!/usr/bin/env bash
set -euo pipefail

source_commit="74de65a81f3aa897be326e57de29297f5cc237e4"
old_image="sha256:88ecf1aac7cd95b5ba50811950090c13f78362274e5c5cdaeafaafde29a115f4"
tag="rvt-phase9g-a1s3z:${source_commit:0:8}"
parent_tag="rvt-phase9g-a1s3z-parent:88ecf1aa"
context="/tmp/rvt-phase9g-a1s3z-image-context"

test "$(docker image inspect "$old_image" --format '{{.Id}}')" = "$old_image"
docker tag "$old_image" "$parent_tag"
rm -rf "$context"
git clone --quiet --no-hardlinks /home/avis/rvt "$context"
git -C "$context" checkout --quiet --detach "$source_commit"
test "$(git -C "$context" rev-parse HEAD)" = "$source_commit"
test -z "$(git -C "$context" status --porcelain)"
# The historical Docker ignore pattern matches this tracked evidence file.
# Re-include it for an exact Git tree, then restore .dockerignore in-image.
printf '\n!results/rvt_fd24/phase9g_a1r_preflight_evidence/staging_checkpoint_recheck.json\n' \
  >>"$context/.dockerignore"

docker build --pull=false --no-cache \
  --build-arg "QUALIFIED_BASE_IMAGE=$parent_tag" \
  --build-arg "RVT_SOURCE_COMMIT=$source_commit" \
  --tag "$tag" \
  --file - "$context" <<'DOCKERFILE'
ARG QUALIFIED_BASE_IMAGE=rvt-phase9g-a1s3z-parent:88ecf1aa
FROM ${QUALIFIED_BASE_IMAGE}

USER root
ARG RVT_SOURCE_COMMIT
LABEL org.opencontainers.image.title="RVT-Swarm Phase 9G-A1S3Z generation"
LABEL org.opencontainers.image.revision="${RVT_SOURCE_COMMIT}"
LABEL rvt.phase9g.a1s3z.qualified-parent="sha256:88ecf1aac7cd95b5ba50811950090c13f78362274e5c5cdaeafaafde29a115f4"
ENV RVT_SOURCE_COMMIT="${RVT_SOURCE_COMMIT}"

RUN rm -rf /opt/rvt && mkdir -p /opt/rvt
COPY --chown=root:root . /opt/rvt
RUN test "${RVT_SOURCE_COMMIT}" != "UNSET" \
    && git -C /opt/rvt checkout -- .dockerignore \
    && test "$(git -C /opt/rvt rev-parse HEAD)" = "${RVT_SOURCE_COMMIT}" \
    && test -z "$(git -C /opt/rvt status --porcelain)" \
    && chmod -R go-w /opt/rvt

USER rvt
CMD ["python", "-m", "pytest", "-q"]
DOCKERFILE

image="$(docker image inspect "$tag" --format '{{.Id}}')"
revision="$(docker image inspect "$image" --format '{{index .Config.Labels "org.opencontainers.image.revision"}}')"
parent="$(docker image inspect "$image" --format '{{index .Config.Labels "rvt.phase9g.a1s3z.qualified-parent"}}')"
test "$revision" = "$source_commit"
test "$parent" = "$old_image"
docker run --rm --network none "$image" sh -lc \
  'test "$(git -C /opt/rvt rev-parse HEAD)" = "$RVT_SOURCE_COMMIT" && test -z "$(git -C /opt/rvt status --porcelain)"'
printf '{"image":"%s","parent":"%s","source_commit":"%s","tag":"%s"}\n' \
  "$image" "$parent" "$revision" "$tag"
