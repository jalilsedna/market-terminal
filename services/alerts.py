"""Alert rules over recorded history (ROADMAP C5).

The pre-cache warmer snapshots derived signals daily into SQLite (vol/regime per
instrument, macro regime). This is the **research-side** alerting on top of that:
a rule watches one metric of one series and *flags* when a condition holds — e.g.
"GC volatility regime is stressed" or "NQ vol percentile ≥ 90". Flags are surfaced
in the UI and over MCP for Alice; nothing here places or routes an order — the
terminal stays research-only (CLAUDE.md). Evaluation reads the **latest** snapshot
of each series, so an alert reflects the most recent daily reading.

No OpenBB / heavy deps — rules live in `app.db`, so this is unit-tested in CI.
"""

from __future__ import annotations

import uuid
from typing import Any

from app import db

# Metrics we can alert on, mapped to the snapshot value field they read. vol is
# an annualized fraction (0.18 = 18%); percentile is 0–100; score is the macro
# regime score; regime is the categorical level (calm/normal/elevated/stressed
# or risk-on/off).
NUMERIC_METRICS = {"vol", "percentile", "score"}
CATEGORICAL_METRICS = {"regime"}
VALID_METRICS = NUMERIC_METRICS | CATEGORICAL_METRICS

_NUMERIC_OPS: dict[str, Any] = {
    ">": lambda a, b: a > b,
    ">=": lambda a, b: a >= b,
    "<": lambda a, b: a < b,
    "<=": lambda a, b: a <= b,
}
_CATEGORICAL_OPS: dict[str, Any] = {
    "==": lambda a, b: str(a).lower() == str(b).lower(),
    "!=": lambda a, b: str(a).lower() != str(b).lower(),
}


class RuleError(ValueError):
    """Raised when an alert rule is malformed (surfaced to the client as 400)."""


def _auto_label(series: str, metric: str, op: str, threshold: Any) -> str:
    return f"{series} {metric} {op} {threshold}"


def add_rule(
    series: str, metric: str, op: str, threshold: Any, label: str | None = None
) -> dict:
    """Validate and persist a rule. Returns the stored rule dict."""
    series = (series or "").strip()
    metric = (metric or "").strip().lower()
    op = (op or "").strip()
    if not series:
        raise RuleError("series is required (e.g. 'vol:GC', 'regime:macro')")
    if metric not in VALID_METRICS:
        raise RuleError(f"metric must be one of {sorted(VALID_METRICS)}")
    if metric in NUMERIC_METRICS:
        if op not in _NUMERIC_OPS:
            raise RuleError(f"op for {metric} must be one of {sorted(_NUMERIC_OPS)}")
        try:
            threshold = float(threshold)
        except (TypeError, ValueError) as exc:
            raise RuleError(f"threshold for {metric} must be a number") from exc
    else:  # categorical
        if op not in _CATEGORICAL_OPS:
            raise RuleError(f"op for {metric} must be one of {sorted(_CATEGORICAL_OPS)}")
        threshold = str(threshold).strip()
        if not threshold:
            raise RuleError("threshold (a regime level) is required")

    alert_id = uuid.uuid4().hex[:8]
    label = (label or "").strip() or _auto_label(series, metric, op, threshold)
    db.alert_create(alert_id, series, metric, op, threshold, label, enabled=True)
    return {
        "id": alert_id, "series": series, "metric": metric, "op": op,
        "threshold": threshold, "label": label, "enabled": True,
    }


def remove_rule(alert_id: str) -> bool:
    return db.alert_remove(alert_id)


def set_enabled(alert_id: str, enabled: bool) -> bool:
    return db.alert_set_enabled(alert_id, enabled)


def list_rules() -> list[dict]:
    return db.alert_list()


def _evaluate_rule(rule: dict) -> dict:
    """Evaluate one rule against the latest snapshot of its series."""
    out = {**rule, "triggered": False, "current": None, "ts": None, "status": "ok"}
    points = db.history(rule["series"], limit=1)
    if not points:
        out["status"] = "no data yet"
        return out
    latest = points[0]
    value = latest.get("value") or {}
    current = value.get(rule["metric"]) if isinstance(value, dict) else None
    out["ts"] = latest.get("ts")
    out["current"] = current
    if current is None:
        out["status"] = f"metric '{rule['metric']}' not in snapshot"
        return out
    try:
        if rule["metric"] in NUMERIC_METRICS:
            out["triggered"] = _NUMERIC_OPS[rule["op"]](float(current), float(rule["threshold"]))
        else:
            out["triggered"] = _CATEGORICAL_OPS[rule["op"]](current, rule["threshold"])
    except (TypeError, ValueError, KeyError):
        out["status"] = "could not compare"
    return out


def evaluate() -> dict:
    """Evaluate every rule; returns the rules with triggered state + a summary.

    Disabled rules are listed but not counted as triggered. `triggered_count` is
    the badge number the UI/MCP surfaces.
    """
    rules = list_rules()
    evaluated = []
    triggered = 0
    for rule in rules:
        ev = _evaluate_rule(rule)
        if ev["enabled"] and ev["triggered"]:
            triggered += 1
        evaluated.append(ev)
    return {
        "count": len(evaluated),
        "triggered_count": triggered,
        "alerts": evaluated,
        "disclaimer": "Research flags over recorded daily snapshots — not a trade trigger.",
    }
