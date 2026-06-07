"""kronos_layer — the ONLY module that imports torch / Kronos.

Mirrors the rule that `obb_layer/` is the only place that imports `openbb`: all
forecasting-model access funnels through here, so the rest of the terminal never
takes a torch dependency. By design the model runs in a SEPARATE forecasting
service (see docs/kronos-integration.md); this package is the shared library
that service — and the E1 evaluation harness — build on.

Heavy imports (torch, the Kronos model code) happen lazily inside
`client.get_predictor`, so importing this package (e.g. for the pure
`forecast._summarize_paths` helper, which the test suite exercises) does not
require torch to be installed.
"""

from __future__ import annotations

from kronos_layer.types import DISCLAIMER, ForecastResult

__all__ = ["ForecastResult", "DISCLAIMER"]
