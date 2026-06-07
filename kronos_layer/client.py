"""Lazy, cached loader for the Kronos predictor.

This is where torch + the Kronos model code actually get imported — lazily, so
nothing else in the terminal pulls torch. The predictor (tokenizer + model) is
loaded once and cached, mirroring `obb_layer.client.get_obb`.

Kronos ships as a repo (it exposes a `model` package), not a stable PyPI
package, so `_import_kronos` tries the common locations and raises an actionable
error if the forecasting stack isn't installed on this host.
"""

from __future__ import annotations

from functools import lru_cache

# model variant -> (model repo, tokenizer repo) on the Hugging Face Hub.
# `base` is the chosen v1 model; `large` is not open-sourced.
_MODELS: dict[str, tuple[str, str]] = {
    "mini": ("NeoQuasar/Kronos-mini", "NeoQuasar/Kronos-Tokenizer-2k"),
    "small": ("NeoQuasar/Kronos-small", "NeoQuasar/Kronos-Tokenizer-base"),
    "base": ("NeoQuasar/Kronos-base", "NeoQuasar/Kronos-Tokenizer-base"),
}

_INSTALL_HINT = (
    "Kronos is not importable. Install the forecasting stack on this host:\n"
    "  pip install torch huggingface_hub\n"
    "  git clone https://github.com/shiyu-coder/Kronos\n"
    "  pip install -r Kronos/requirements.txt\n"
    "  # put Kronos/ on PYTHONPATH (it exposes the `model` package)\n"
    "See docs/kronos-integration.md."
)


def _import_kronos():
    """Return (Kronos, KronosTokenizer, KronosPredictor) from whichever layout is
    installed, or raise with install instructions."""
    for module in ("kronos", "model"):
        try:
            mod = __import__(module, fromlist=["Kronos", "KronosTokenizer", "KronosPredictor"])
            return mod.Kronos, mod.KronosTokenizer, mod.KronosPredictor
        except ImportError:
            continue
    raise ImportError(_INSTALL_HINT)


@lru_cache(maxsize=4)
def get_predictor(model: str | None = None, device: str | None = None):
    """Load (once) and return a KronosPredictor for `model` on `device`.

    Defaults come from settings (`kronos_model`, `kronos_device`). Cached so the
    weights load a single time per process.
    """
    from config import get_settings

    settings = get_settings()
    model = model or settings.kronos_model
    device = device or settings.kronos_device
    if model not in _MODELS:
        raise ValueError(f"unknown kronos_model {model!r}; choose from {list(_MODELS)}")

    Kronos, KronosTokenizer, KronosPredictor = _import_kronos()
    model_repo, tokenizer_repo = _MODELS[model]
    tokenizer = KronosTokenizer.from_pretrained(tokenizer_repo)
    net = Kronos.from_pretrained(model_repo)
    # KronosPredictor signature is (model, tokenizer, device=..., max_context=512)
    # in current releases; max_context 512 matches small/base.
    return KronosPredictor(net, tokenizer, device=device, max_context=512)
