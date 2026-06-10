"""cache — response cache (SPEC.md §6).

Mandatory infra, not an optimization. Cache by (endpoint, params) with
per-data-type TTLs: intraday/quote ~minutes, EOD ~daily, COT ~weekly, macro
series ~daily. Free providers throttle, so this must be wired in during Phase 0.
"""

from __future__ import annotations

# Per-data-type TTLs in seconds. Referenced by the cache implementation and the
# obb_layer wrappers so freshness policy lives in one place.
TTL_SECONDS = {
    "intraday": 60,
    "quote": 60,
    "news": 15 * 60,
    "eod": 24 * 60 * 60,
    "cot": 7 * 24 * 60 * 60,
    "macro": 24 * 60 * 60,
    # FMP fundamentals (ROADMAP H): statements/ratios change quarterly, profiles
    # rarely, estimates/calendars more often. Cached hard because Starter is
    # rate-capped.
    "profile": 7 * 24 * 60 * 60,
    "fundamentals": 24 * 60 * 60,
    "estimates": 12 * 60 * 60,
    "calendar": 6 * 60 * 60,
}
