import math
import random
from typing import Tuple

import numpy as np
import torch


def set_seed(seed: int) -> None:
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


def pairwise_dist(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    diff = a[:, None, :] - b[None, :, :]
    return np.linalg.norm(diff, axis=-1)


def angle_to(vec: np.ndarray) -> float:
    return math.atan2(vec[1], vec[0])


def unit(vec: np.ndarray, eps: float = 1e-8) -> np.ndarray:
    n = np.linalg.norm(vec)
    if n < eps:
        return np.zeros_like(vec)
    return vec / n


def torch_device(name: str) -> torch.device:
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
    n = np.linalg.norm(x)
    if n <= limit:
        return x
    return x / max(n, 1e-8) * limit


def heading_features(v: np.ndarray) -> Tuple[float, float]:
    ang = angle_to(v) if np.linalg.norm(v) > 1e-8 else 0.0
    return math.cos(ang), math.sin(ang)


def clip01(value: float) -> float:
    return float(np.clip(value, 0.0, 1.0))


def normalized_mean(values) -> float:
    arr = np.asarray(list(values), dtype=np.float32)
    if arr.size == 0:
        return 0.0
    return float(arr.mean())


def standardize_np(values: np.ndarray) -> np.ndarray:
    arr = np.asarray(values, dtype=np.float32)
    return ((arr - arr.mean()) / max(float(arr.std()), 1e-6)).astype(np.float32)


def score_dispersion_tensor(scores: torch.Tensor) -> torch.Tensor:
    return scores.detach().std(dim=-1, keepdim=True, unbiased=False).clamp_min(1e-6)


def uncertainty_adjusted_scores(scores: torch.Tensor, uncertainty: torch.Tensor) -> torch.Tensor:
    return scores - uncertainty * score_dispersion_tensor(scores)
