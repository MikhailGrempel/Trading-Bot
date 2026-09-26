"""Real 15-minute trade candles from Kraken's public market API.

Each candle is one time block of trades: open, high, low, close, and volume.
No API key is required. Orders are still paper-only.
"""

from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

CACHE = Path(__file__).resolve().parent / "data" / "kraken_15m.json"
INTERVAL_MINUTES = 15
# Refresh when the saved file is older than one candle.
MAX_CACHE_AGE_SECONDS = INTERVAL_MINUTES * 60
SOURCE = {
    "name": "Kraken public 15-minute candles",
    "url": "https://api.kraken.com/0/public/OHLC",
    "fetched_at": "",
    "stale": False,
}


@dataclass(frozen=True)
class Candle:
    time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

    def __post_init__(self) -> None:
        if min(self.open, self.high, self.low, self.close) <= 0:
            raise ValueError("prices must be positive")
        if self.high < max(self.open, self.close) or self.low > min(self.open, self.close):
            raise ValueError("candle high/low does not contain open and close")


def load_market(pairs: list[str], count: int = 400, refresh: bool = False) -> dict[str, list[Candle]]:
    """Return the latest closed candles, downloading them when the cache is old."""
    if count < 30:
        raise ValueError("need at least 30 candles")
    if not pairs:
        raise ValueError("no pairs to load")

    cached = _read_cache()
    age = _cache_age_seconds(cached)
    fresh = (
        not refresh
        and cached is not None
        and age is not None
        and age <= MAX_CACHE_AGE_SECONDS
        and all(pair in cached["pairs"] for pair in pairs)
    )
    if not fresh:
        try:
            cached = _download(pairs)
            _write_cache(cached)
            SOURCE["stale"] = False
        except OSError as exc:
            if cached is None:
                raise ValueError(f"Could not download Kraken candles: {exc}") from exc
            SOURCE["stale"] = True
    else:
        SOURCE["stale"] = False

    SOURCE["fetched_at"] = cached["fetched_at"]
    return _align(cached, pairs, count)


def _download(pairs: list[str]) -> dict:
    pairs_raw: dict[str, list] = {}
    for pair in pairs:
        pairs_raw[pair] = [_row(item) for item in _fetch_rows(pair)]
    return {
        "source": SOURCE["name"],
        "interval_minutes": INTERVAL_MINUTES,
        "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "pairs": pairs_raw,
    }


def _fetch_rows(pair: str) -> list:
    symbol = _kraken_symbol(pair)
    url = f"{SOURCE['url']}?pair={symbol}&interval={INTERVAL_MINUTES}"
    request = urllib.request.Request(url, headers={"User-Agent": "simplebot/1.0"})
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if payload.get("error"):
        raise OSError(f"{pair}: {', '.join(payload['error'])}")
    result = payload["result"]
    table_name = next(key for key in result if key != "last")
    rows = result[table_name]
    if len(rows) < 31:
        raise OSError(f"{pair}: Kraken returned too few candles")
    # The last row is the candle that is still forming.
    return rows[:-1]


def _kraken_symbol(pair: str) -> str:
    base, quote = pair.split("/")
    if base == "BTC":
        base = "XBT"
    return f"{base}{quote}"


def _row(item: list) -> list:
    when = datetime.fromtimestamp(int(item[0]), timezone.utc)
    open_ = float(item[1])
    high = float(item[2])
    low = float(item[3])
    close = float(item[4])
    volume = float(item[6])
    high = max(high, open_, close)
    low = min(low, open_, close)
    return [when.strftime("%Y-%m-%d %H:%M"), open_, high, low, close, volume]


def _align(cached: dict, pairs: list[str], count: int) -> dict[str, list[Candle]]:
    by_pair: dict[str, dict[str, Candle]] = {}
    for pair in pairs:
        rows = cached["pairs"].get(pair)
        if not rows:
            raise ValueError(f"no Kraken candles for {pair}")
        by_pair[pair] = {row[0]: _candle(row) for row in rows}

    common = set(by_pair[pairs[0]])
    for pair in pairs[1:]:
        common &= set(by_pair[pair])
    times = sorted(common)
    if len(times) < 30:
        raise ValueError("the pairs do not share enough candles")
    times = times[-count:]
    return {pair: [by_pair[pair][stamp] for stamp in times] for pair in pairs}


def _candle(row: list) -> Candle:
    when = datetime.strptime(row[0], "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
    return Candle(when, row[1], row[2], row[3], row[4], row[5])


def _read_cache() -> dict | None:
    if not CACHE.exists():
        return None
    try:
        return json.loads(CACHE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _write_cache(payload: dict) -> None:
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(payload), encoding="utf-8")


def _cache_age_seconds(cached: dict | None) -> float | None:
    if not cached or "fetched_at" not in cached:
        return None
    try:
        fetched = datetime.strptime(cached["fetched_at"], "%Y-%m-%d %H:%M UTC").replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    return (datetime.now(timezone.utc) - fetched).total_seconds()
