#!/usr/bin/env python3
"""Sequentially launch the predeclared target chunk matrix over SSH."""

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
    parser.add_argument("--workers", type=int, required=True)
    parser.add_argument("--chunks", default="2,4,8")
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

    for chunk in [int(value) for value in args.chunks.split(",")]:
        for kind in ("residual", "recoverability"):
            name = f"rb21-chunk-c{chunk}-{kind}"
            output = f"{args.windows_root}\\evidence\\chunk-c{chunk}-{kind}.json"
            observed = remote(
                f"docker image inspect {args.image} --format {{{{.Id}}}}")
            if observed != args.image:
                raise RuntimeError(f"qualified image mismatch: {observed}")
            command = (
                f"docker run -d --name {name} --gpus all "
                "-e OMP_NUM_THREADS=1 -e MKL_NUM_THREADS=1 "
                "-e OPENBLAS_NUM_THREADS=1 -e NUMEXPR_NUM_THREADS=1 "
                f"-e RVT_QUALIFIED_IMAGE_OBSERVED={args.image} "
                f"-v {args.windows_root}:/qualification {args.image} bash -lc "
                f'"cd /opt/rvt && PYTHONPATH=/opt/rvt python '
                "/qualification/run_phase9c_rb21_target_benchmark.py "
                "--root /opt/rvt "
                "--manifest /qualification/rb21_target_benchmark_manifest_v2.json "
                f"--output /qualification/evidence/chunk-c{chunk}-{kind}.json "
                f"--run-id CHUNK_C{chunk}_{kind.upper()} --kind {kind} "
                f"--workers {args.workers} --chunk-size {chunk}\"")
            identifier = remote(command)
            print(f"START C={chunk} kind={kind} image={observed} id={identifier}",
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
                print(f"TICK C={chunk} kind={kind} {stats}", flush=True)
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
            print(f"DONE C={chunk} kind={kind} bytes={length}", flush=True)
            remote(f"docker rm {name} >NUL")


if __name__ == "__main__":
    main()
