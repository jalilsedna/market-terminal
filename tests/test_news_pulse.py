"""News Pulse (ROADMAP H14) — deterministic core + analyst-pass fallback, no network."""

from __future__ import annotations

import pytest


def test_score_sentiment_polarity():
    from services.news_pulse import score_sentiment

    pos = score_sentiment([
        {"title": "Company beats earnings, shares surge", "excerpt": "record growth"},
        {"title": "Analysts upgrade the stock"},
    ])
    assert pos["positive"] >= 3 and pos["lean"] == "up" and pos["score"] >= 2

    neg = score_sentiment([
        {"title": "Stock plunges on guidance cut", "excerpt": "weak demand, lawsuit"},
    ])
    assert neg["negative"] >= 2 and neg["lean"] == "down"

    flat = score_sentiment([{"title": "Company holds annual meeting"}])
    assert flat["lean"] == "neutral" and flat["headline_count"] == 1


def test_blend_directions():
    from services.news_pulse import _blend

    assert _blend("up", "long") == ("up", "high")        # both agree
    assert _blend("up", None) == ("up", "medium")        # news only
    assert _blend("up", "short") == ("neutral", "low")   # conflict cancels
    assert _blend("neutral", None) == ("neutral", "low")


def test_recent_filters_to_24h():
    from datetime import UTC, datetime, timedelta

    from services.news_pulse import _recent

    now = datetime.now(UTC)
    fresh = (now - timedelta(hours=2)).isoformat()
    stale = (now - timedelta(hours=48)).isoformat()
    out = _recent([{"title": "fresh", "date": fresh}, {"title": "stale", "date": stale}])
    titles = [h["title"] for h in out]
    assert "fresh" in titles and "stale" not in titles


def test_requires_symbol():
    from services import news_pulse

    with pytest.raises(ValueError):
        news_pulse.pulse("")


def test_pulse_rule_based_when_no_key(monkeypatch):
    from obb_layer import llm
    from services import analysis, news_pulse, signals
    from services import news as news_svc

    # No LLM key → deterministic path only.
    monkeypatch.setattr(llm, "enabled", lambda: False)
    monkeypatch.setattr(news_pulse.reg, "resolve", lambda s: (_ for _ in ()).throw(ValueError("nt")))
    monkeypatch.setattr(news_pulse.reg, "ensure", lambda *a, **k: (_ for _ in ()).throw(ValueError("nt")))
    monkeypatch.setattr(news_svc, "feed", lambda **kw: {"headlines": [
        {"title": "AAPL beats and raises, shares surge to record", "date": "2026-06-11T12:00:00"},
        {"title": "Analysts upgrade Apple on strong growth", "date": "2026-06-11T11:00:00"},
    ]})
    monkeypatch.setattr(signals, "trade_setup", lambda s: {"bias": "long"})
    monkeypatch.setattr(analysis, "regime", lambda: {"regime": "risk-on"})

    out = news_pulse.pulse("AAPL")
    assert out["engine"] == "rule-based"
    assert out["horizon"] == "24h"
    assert out["news_sentiment"]["lean"] == "up"
    assert out["direction"] == "up" and out["confidence"] == "high"  # news up + tech long
    assert out["errors"] is None


def test_pulse_uses_analyst_when_key_present(monkeypatch):
    from obb_layer import llm
    from services import analysis, news_pulse, signals
    from services import news as news_svc

    monkeypatch.setattr(news_pulse.reg, "resolve", lambda s: (_ for _ in ()).throw(ValueError("nt")))
    monkeypatch.setattr(news_pulse.reg, "ensure", lambda *a, **k: (_ for _ in ()).throw(ValueError("nt")))
    monkeypatch.setattr(news_svc, "feed", lambda **kw: {"headlines": [
        {"title": "NVDA dips after mixed guidance", "date": "2026-06-11T12:00:00"},
    ]})
    monkeypatch.setattr(signals, "trade_setup", lambda s: {"bias": "neutral"})
    monkeypatch.setattr(analysis, "regime", lambda: {"regime": "risk-off"})

    monkeypatch.setattr(llm, "enabled", lambda: True)
    monkeypatch.setattr(llm, "analyze_json", lambda *a, **k: {
        "summary": "Mixed guidance caps upside into a risk-off tape.",
        "direction": "down", "confidence": "medium",
        "catalysts": ["soft guidance"], "caveats": ["broad market rally could lift it"],
    })

    out = news_pulse.pulse("NVDA")
    assert out["engine"] == "llm"
    assert out["direction"] == "down" and out["confidence"] == "medium"
    assert "Mixed guidance" in out["summary"]
    assert out["catalysts"] == ["soft guidance"]
    # The deterministic baseline is always preserved alongside the analyst read.
    assert out["baseline"]["direction"] in ("up", "down", "neutral")


def test_pulse_falls_back_when_analyst_parse_fails(monkeypatch):
    from obb_layer import llm
    from services import analysis, news_pulse, signals
    from services import news as news_svc

    monkeypatch.setattr(news_pulse.reg, "resolve", lambda s: (_ for _ in ()).throw(ValueError("nt")))
    monkeypatch.setattr(news_pulse.reg, "ensure", lambda *a, **k: (_ for _ in ()).throw(ValueError("nt")))
    monkeypatch.setattr(news_svc, "feed", lambda **kw: {"headlines": [
        {"title": "Company misses, stock falls", "date": "2026-06-11T12:00:00"},
    ]})
    monkeypatch.setattr(signals, "trade_setup", lambda s: {"bias": "short"})
    monkeypatch.setattr(analysis, "regime", lambda: {"regime": "risk-off"})
    monkeypatch.setattr(llm, "enabled", lambda: True)
    monkeypatch.setattr(llm, "analyze_json", lambda *a, **k: None)  # parse/LLM failure

    out = news_pulse.pulse("XYZ")
    assert out["engine"] == "rule-based"            # degraded cleanly
    assert out["direction"] == "down"               # baseline (news down + short)
    assert out["errors"] and "analyst" in out["errors"]


def test_llm_extract_json_tolerant():
    from obb_layer.llm import _extract_json

    assert _extract_json('{"a": 1}') == {"a": 1}
    assert _extract_json('```json\n{"a": 2}\n```')["a"] == 2
    assert _extract_json('Here you go: {"a": 3} hope that helps')["a"] == 3
    assert _extract_json("not json") is None
    assert _extract_json("") is None
