"""Single-writer exclusivity for checkpoint directories (Task 6).

The method audit lost a set of checkpoints when four concurrent training
processes wrote to one directory (see
`checkpoints/invalid_concurrent_writers/README.md`). Consistency check 11
verified schema and freshness but not exclusivity, so the corruption was silent.

This module makes the failure loud: a writer claims a directory with an
`O_EXCL` lock file carrying its PID and a unique token, and every checkpoint is
stamped with that token so a mixed directory is detectable after the fact.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Dict, Optional

LOCK_NAME = ".writer.lock"


class CheckpointWriterConflict(RuntimeError):
    """Raised when a second process tries to write into a claimed directory."""


class CheckpointWriterLock:
    """Exclusive claim on a checkpoint directory.

    `O_CREAT | O_EXCL` is atomic on POSIX, so exactly one process can create the
    lock file. A stale lock (dead PID) is reclaimed; a live one is an error.
    """

    def __init__(self, directory, stale_after_s: float = 24 * 3600):
        self.directory = Path(directory)
        self.lock_path = self.directory / LOCK_NAME
        self.stale_after_s = stale_after_s
        self.token = uuid.uuid4().hex[:16]
        self._acquired = False

    @staticmethod
    def _pid_alive(pid: int) -> bool:
        try:
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False
        except PermissionError:
            return True

    def read_lock(self) -> Optional[Dict]:
        if not self.lock_path.exists():
            return None
        try:
            return json.loads(self.lock_path.read_text())
        except Exception:
            return {"pid": -1, "token": "unreadable", "time": 0.0}

    def acquire(self) -> "CheckpointWriterLock":
        self.directory.mkdir(parents=True, exist_ok=True)
        existing = self.read_lock()
        if existing is not None:
            pid = int(existing.get("pid", -1))
            age = time.time() - float(existing.get("time", 0.0))
            if self._pid_alive(pid) and pid != os.getpid():
                raise CheckpointWriterConflict(
                    f"{self.directory} is already claimed by live pid {pid} "
                    f"(token {existing.get('token')}). Concurrent writers corrupted "
                    f"the method-audit checkpoints; refusing to repeat it."
                )
            if age <= self.stale_after_s and pid == os.getpid():
                self._acquired = True
                self.token = str(existing.get("token", self.token))
                return self
            self.lock_path.unlink(missing_ok=True)   # stale: reclaim
        fd = os.open(str(self.lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        try:
            os.write(fd, json.dumps(
                {"pid": os.getpid(), "token": self.token, "time": time.time()}
            ).encode())
        finally:
            os.close(fd)
        self._acquired = True
        return self

    def release(self) -> None:
        if self._acquired and self.lock_path.exists():
            info = self.read_lock() or {}
            if str(info.get("token")) == self.token:
                self.lock_path.unlink(missing_ok=True)
        self._acquired = False

    def __enter__(self) -> "CheckpointWriterLock":
        return self.acquire()

    def __exit__(self, *exc) -> None:
        self.release()


def verify_single_writer(directory) -> Dict[str, object]:
    """Post-hoc check: every checkpoint in the directory shares one writer token."""
    import torch

    directory = Path(directory)
    tokens, files = {}, sorted(directory.glob("*.pt"))
    for p in files:
        try:
            state = torch.load(p, map_location="cpu", weights_only=False)
            tokens[p.name] = str(state.get("writer_token", "missing"))
        except Exception:
            tokens[p.name] = "unreadable"
    distinct = {t for t in tokens.values() if t not in ("missing", "unreadable")}
    return {
        "directory": str(directory),
        "n_checkpoints": len(files),
        "tokens": tokens,
        "distinct_tokens": sorted(distinct),
        "single_writer": len(distinct) <= 1,
    }
