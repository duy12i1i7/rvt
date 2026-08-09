#!/usr/bin/env python3
"""Sequentially launch the predeclared target scaling matrix over SSH."""

from __future__ import annotations

import argparse
import subprocess
import time


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--control-socket", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--windows-root", required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--workers", default="2,4,6,8,12,16")
    parser.add_argument("--poll-seconds", type=int, default=30)
    args = parser.parse_args()

    def remote(command: str, *, check: bool = True) -> str:
        result = subprocess.run(
            ["ssh", "-S", args.control_socket, args.target, command],
            text=True, capture_output=True, check=False)
        if check and result.returncode != 0:
            raise RuntimeError(
                f"remote command failed ({result.returncode}): {result.stderr.strip()}")
        return result.stdout.strip()

    expected = args.image
    for workers in [int(value) for value in args.workers.split(",")]:
        for kind in ("residual", "recoverability"):
            name = f"rb21-worker-w{workers}-{kind}"
            output = f"{args.windows_root}\\evidence\\worker-w{workers}-{kind}.json"
            status = remote(
                f'docker inspect {name} --format "{{{{.State.Status}}}} '
                f'{{{{.State.ExitCode}}}}"', check=False)
            if not status:
                observed = remote(
                    f"docker image inspect {expected} --format {{{{.Id}}}}")
                if observed != expected:
                    raise RuntimeError(f"qualified image mismatch: {observed}")
                command = (
                    f"docker run -d --name {name} --gpus all "
                    "-e OMP_NUM_THREADS=1 -e MKL_NUM_THREADS=1 "
                    "-e OPENBLAS_NUM_THREADS=1 -e NUMEXPR_NUM_THREADS=1 "
                    f"-e RVT_QUALIFIED_IMAGE_OBSERVED={expected} "
                    f"-v {args.windows_root}:/qualification {expected} bash -lc "
                    f'"cd /opt/rvt && PYTHONPATH=/opt/rvt python '
                    "/qualification/run_phase9c_rb21_target_benchmark.py "
                    "--root /opt/rvt "
                    "--manifest /qualification/rb21_target_benchmark_manifest_v2.json "
                    f"--output /qualification/evidence/worker-w{workers}-{kind}.json "
                    f"--run-id WORKER_W{workers}_{kind.upper()} --kind {kind} "
                    f'--workers {workers} --chunk-size 1"')
                identifier = remote(command)
                print(f"START W={workers} kind={kind} image={observed} id={identifier}",
                      flush=True)
            while True:
                status = remote(
                    f'docker inspect {name} --format "{{{{.State.Status}}}} '
                    f'{{{{.State.ExitCode}}}}"')
                state, exit_code = status.split()
                if state != "running":
                    break
                stats = remote(
                    f'docker stats --no-stream {name} --format "{{{{.CPUPerc}}}} '
                    f'{{{{.MemUsage}}}}"', check=False)
                print(f"TICK W={workers} kind={kind} {stats}", flush=True)
                time.sleep(args.poll_seconds)
            if state != "exited" or exit_code != "0":
                logs = remote(f"docker logs {name}", check=False)
                raise RuntimeError(
                    f"{name} ended as {state}/{exit_code}: {logs[-2000:]}")
            length = remote(
                "powershell -NoProfile -Command "
                f'"(Get-Item \'{output}\').Length"')
            if int(length) <= 0:
                raise RuntimeError(f"{name} emitted an empty artifact")
            print(f"DONE W={workers} kind={kind} bytes={length}", flush=True)
            remote(f"docker rm {name} >NUL")


if __name__ == "__main__":
    main()
