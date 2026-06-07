"""Device resolution for the Kronos loader — the graceful CUDA→CPU fallback.

Pure (no model load); in CI torch isn't installed, so a 'cuda' request falls
back to CPU via the ImportError path.
"""

from __future__ import annotations

from kronos_layer.client import _resolve_device


def test_cpu_passthrough():
    assert _resolve_device("cpu") == "cpu"


def test_cuda_falls_back_without_torch():
    # No torch in the CI env → cuda is not usable → CPU.
    assert _resolve_device("cuda") == "cpu"
