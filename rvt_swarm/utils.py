from __future__ import annotations

import math
import os
import random
from contextlib import contextmanager
from typing import Iterator, Tuple

import numpy as np


_CHILD_THREAD_ENV_VARS = (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "BLIS_NUM_THREADS",
)


def set_seed(seed: int) -> None:
    import torch

    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False
    try:
        torch.use_deterministic_algorithms(True, warn_only=True)
    except Exception:
        pass


@contextmanager
def limit_child_threads(enabled: bool) -> Iterator[None]:
    if not enabled:
        yield
        return
    previous = {name: os.environ.get(name) for name in _CHILD_THREAD_ENV_VARS}
    try:
        for name in _CHILD_THREAD_ENV_VARS:
            os.environ[name] = "1"
        yield
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def configure_worker_runtime() -> None:
    for name in _CHILD_THREAD_ENV_VARS:
        os.environ[name] = "1"

    try:
        import torch
    except Exception:
        return

    try:
        torch.set_num_threads(1)
    except Exception:
        pass
    try:
        torch.set_num_interop_threads(1)
    except Exception:
        pass


def pairwise_dist(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    diff = a[:, None, :] - b[None, :, :]
    return np.linalg.norm(diff, axis=-1)


def angle_to(vec: np.ndarray) -> float:
    return math.atan2(vec[1], vec[0])


def vec_norm(vec: np.ndarray) -> float:
    return float(math.hypot(float(vec[0]), float(vec[1])))

def unit(vec: np.ndarray, eps: float = 1e-8) -> np.ndarray:
    n = vec_norm(vec)
    if n < eps:
        return np.zeros_like(vec)
    return vec / n


def torch_device(name: str) -> torch.device:
    import torch

    name = (name or "auto").lower()
    if name == "auto":
        if torch.cuda.is_available():
            return torch.device("cuda")
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return torch.device("mps")
        return torch.device("cpu")
    if name == "cuda":
        if torch.cuda.is_available():
            return torch.device("cuda")
        print("[warn] CUDA requested but not available. Falling back to CPU.")
        return torch.device("cpu")
    if name == "mps":
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return torch.device("mps")
        print("[warn] MPS requested but not available. Falling back to CPU.")
        return torch.device("cpu")
    return torch.device("cpu")


def soft_clip(x: np.ndarray, limit: float) -> np.ndarray:
    n = vec_norm(x)
    if n <= limit:
        return x
    return x / max(n, 1e-8) * limit


def heading_features(v: np.ndarray) -> Tuple[float, float]:
    ang = angle_to(v) if vec_norm(v) > 1e-8 else 0.0
    return math.cos(ang), math.sin(ang)


def clip01(value: float) -> float:
    v = float(value)
    if math.isnan(v):
        return v
    if v <= 0.0:
        return 0.0
    if v >= 1.0:
        return 1.0
    return v


def normalized_mean(values) -> float:
    arr = np.asarray(list(values), dtype=np.float32)
    if arr.size == 0:
        return 0.0
    return float(arr.mean())


def score_dispersion_tensor(scores: torch.Tensor) -> torch.Tensor:
    return scores.detach().std(dim=-1, keepdim=True, unbiased=False).clamp_min(1e-6)


def uncertainty_adjusted_scores(scores: torch.Tensor, uncertainty: torch.Tensor) -> torch.Tensor:
    return scores - uncertainty * score_dispersion_tensor(scores)
