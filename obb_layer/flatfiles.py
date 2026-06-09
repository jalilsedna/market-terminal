"""Massive.com (ex-Polygon) Flat Files — S3 bulk historical data.

Flat Files are an S3-compatible bucket of compressed daily CSVs: one
`day_aggs_v1` file per trading day holds **every** US stock's OHLCV (~300 KB
gzipped). That makes a whole-market scan one cheap download instead of thousands
of REST calls — the basis for the Movers screener (`services/movers.py`).

OpenBB's `polygon` provider is REST-only (no flat-file support), so this is the
sanctioned "OpenBB lacks it → we extend it here" path (CLAUDE.md). `boto3` is
imported lazily inside `_client()` so the pure parser (`parse_day_aggs`) — and
anything importing this module — works without the dependency or credentials
(keeps the CI unit tests light).
"""

from __future__ import annotations

import csv
import gzip
import io
from datetime import UTC, datetime

from config import get_settings

DAY_AGGS_PREFIX = "us_stocks_sip/day_aggs_v1/"


def _client():
    """An S3 client pointed at the Massive Flat Files endpoint (signature v4)."""
    import boto3  # noqa: PLC0415 — lazy: only needed when actually fetching
    from botocore.config import Config  # noqa: PLC0415

    s = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=s.massive_s3_endpoint,
        aws_access_key_id=s.massive_s3_access_key,
        aws_secret_access_key=s.massive_s3_secret_key,
        config=Config(signature_version="s3v4"),
    )


def parse_day_aggs(raw: bytes) -> dict[str, dict]:
    """Parse a gzip `day_aggs_v1` CSV into {ticker: {open,high,low,close,volume,
    transactions}}. Rows with missing/garbage numerics are skipped. Pure — no S3,
    no deps beyond the stdlib — so it's unit-tested in CI."""
    text = gzip.decompress(raw).decode("utf-8")
    out: dict[str, dict] = {}
    for row in csv.DictReader(io.StringIO(text)):
        ticker = (row.get("ticker") or "").strip()
        if not ticker:
            continue
        try:
            out[ticker] = {
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": float(row["volume"]),
                "transactions": int(row.get("transactions") or 0),
            }
        except (KeyError, ValueError, TypeError):
            continue  # one bad row must not sink the whole file
    return out


def date_from_key(key: str) -> str:
    """'…/2026/06/2026-06-08.csv.gz' → '2026-06-08'."""
    return key.rsplit("/", 1)[-1].split(".", 1)[0]


def _month_prefixes(n_months: int = 2) -> list[str]:
    """The S3 prefixes for the current + previous month(s), newest first. Files
    are laid out as `…/day_aggs_v1/YYYY/MM/`, so listing month folders is far
    cheaper than scanning the whole prefix."""
    today = datetime.now(UTC).date()
    y, m = today.year, today.month
    prefixes = []
    for _ in range(max(1, n_months)):
        prefixes.append(f"{DAY_AGGS_PREFIX}{y:04d}/{m:02d}/")
        m -= 1
        if m == 0:
            m, y = 12, y - 1
    return prefixes


def latest_day_agg_keys(count: int = 2) -> list[str]:
    """The `count` most recent day-aggregate object keys (oldest→newest). Looks
    at this month and last month so it still works in the first days of a month."""
    client = _client()
    bucket = get_settings().massive_s3_bucket
    keys: list[str] = []
    for prefix in _month_prefixes(2):
        resp = client.list_objects_v2(Bucket=bucket, Prefix=prefix)
        keys.extend(obj["Key"] for obj in resp.get("Contents", []) if obj["Key"].endswith(".csv.gz"))
    keys.sort()  # lexical sort == chronological (YYYY-MM-DD filenames)
    return keys[-count:]


def fetch_day_aggs(key: str) -> dict[str, dict]:
    """Download + parse one day-aggregate file into {ticker: row}."""
    client = _client()
    obj = client.get_object(Bucket=get_settings().massive_s3_bucket, Key=key)
    return parse_day_aggs(obj["Body"].read())
