ARG BASE_IMAGE=public.ecr.aws/docker/library/python:3.9.6-slim-bullseye@sha256:4115592fd02679fb3d9e8c513cae33ad3fdd64747b64d32b504419d7118bcd7c
FROM ${BASE_IMAGE}

ARG RVT_SOURCE_COMMIT=UNSET
ARG REQUIREMENTS_FILE=requirements.lock.txt

LABEL org.opencontainers.image.title="RVT-Swarm headless generation"
LABEL org.opencontainers.image.source="https://github.com/duy12i1i7/rvt"
LABEL org.opencontainers.image.revision="${RVT_SOURCE_COMMIT}"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=0 \
    PYTHONPATH=/opt/rvt \
    MPLBACKEND=Agg \
    OMP_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 \
    MKL_CBWR=COMPATIBLE \
    OPENBLAS_NUM_THREADS=1 \
    NUMEXPR_NUM_THREADS=1 \
    RVT_FD24_NUMERICAL_EXECUTION_PROFILE=FD24_NUMERICAL_EXECUTION_PROFILE_V1

ARG DEBIAN_FRONTEND=noninteractive

# Phase 9G-V2I reproducibility repair. The three package pins below are
# unchanged; they simply stopped resolving because the live bullseye mirrors
# roll forward (ca-certificates moved to 20250419~deb12u1~deb11u1). They are
# retrieved unaltered from an immutable Debian snapshot instead, so the image
# is defined by immutable references rather than rolling repository state.
ARG DEBIAN_SNAPSHOT=20260220T214329Z

RUN printf 'deb [check-valid-until=no] https://snapshot.debian.org/archive/debian/%s bullseye main\ndeb [check-valid-until=no] https://snapshot.debian.org/archive/debian-security/%s bullseye-security main\ndeb [check-valid-until=no] https://snapshot.debian.org/archive/debian/%s bullseye-updates main\n' \
        "${DEBIAN_SNAPSHOT}" "${DEBIAN_SNAPSHOT}" "${DEBIAN_SNAPSHOT}" \
        > /etc/apt/sources.list \
    && apt-get -o Acquire::Check-Valid-Until=false update \
    && apt-get install --yes --no-install-recommends \
        build-essential=12.9 \
        ca-certificates=20230311+deb12u1~deb11u1 \
        git=1:2.30.2-1+deb11u5 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/rvt

COPY requirements.txt ./
COPY docker/generation/requirements.lock.txt ./requirements.lock.txt
COPY third_party/Python-RVO2 ./third_party/Python-RVO2

RUN if [ "${REQUIREMENTS_FILE}" = "requirements.txt" ]; then \
        sed \
            -e '/^\.\/third_party\/Python-RVO2$/d' \
            -e 's#https://download.pytorch.org/whl/cu124#https://download.pytorch.org/whl/cpu#' \
            requirements.txt > /tmp/requirements.install.txt; \
    else \
        cp "${REQUIREMENTS_FILE}" /tmp/requirements.install.txt; \
    fi \
    && python -m pip install --no-cache-dir pip==26.0.1 \
    && python -m pip install --no-cache-dir -r /tmp/requirements.install.txt \
    && python -m pip install --no-cache-dir --no-build-isolation ./third_party/Python-RVO2 \
    && rm /tmp/requirements.install.txt

COPY . /opt/rvt
COPY docker/generation/run-tests.sh /usr/local/bin/rvt-test

RUN test "${RVT_SOURCE_COMMIT}" != "UNSET" \
    && test "$(git rev-parse HEAD)" = "${RVT_SOURCE_COMMIT}" \
    && chmod 0755 /usr/local/bin/rvt-test \
    && useradd --create-home --shell /bin/bash rvt \
    && mkdir -p /rvt-data/staging /rvt-data/final /rvt-data/temp /rvt-data/audit \
    && chown -R rvt:rvt /rvt-data \
    && chown -R root:root /opt/rvt \
    && chmod -R go-w /opt/rvt

USER rvt

CMD ["python", "-m", "pytest", "-q"]
