"""Strategies decide when to buy and sell. They do not place orders.

This matches the Freqtrade idea:

- prepare()           -> populate_indicators
- entry_reason()      -> populate_entry_trend
- exit_reason()       -> populate_exit_trend
- stoploss            -> stoploss
- minimal_roi         -> minimal_roi

The bot applies the stop and the target. The strategy only reads candles.
"""

from __future__ import annotations

from market import Candle
from indicators import rsi, sma


class RsiStrategy:
    """Buy a pullback inside an uptrend, sell after a rise.

    The entry has three parts, all of which must agree:

    1. Trend filter  - price is above its long moving average (`trend_period`).
      Only long in an uptrend, so the bot stops buying into a falling market.
    2. RSI oversold   - RSI dipped below `rsi_entry` (default 30) recently.
    3. RSI recovery   - RSI has turned back up through `rsi_entry`.
      This waits for the dip to stop instead of catching a falling knife.

    Set `trend_period=0` to drop the trend filter and `confirm_upturn=False`
    to buy the moment RSI is below `rsi_entry`. Those two switches reproduce
    the original "buy when RSI < 30" behaviour for an apples-to-apples test.

    Exit: RSI above `rsi_exit` (default 70). The bot also applies the stop
    (`stoploss`) and the target (`minimal_roi`) as price moves from the buy.
    """

    def __init__(
        self,
        rsi_entry: float = 30,
        rsi_exit: float = 70,
        rsi_period: int = 14,
        stoploss: float = -0.10,
        minimal_roi: float = 0.02,
        trend_period: int = 50,
        confirm_upturn: bool = True,
        trailing_stop: bool = False,
        trailing_stop_positive: float = 0.02,
        trailing_stop_positive_offset: float = 0.02,
    ) -> None:
        if not 0 < rsi_entry < rsi_exit < 100:
            raise ValueError("need 0 < rsi_entry < rsi_exit < 100")
        if rsi_period < 2:
            raise ValueError("rsi_period must be >= 2")
        if stoploss >= 0:
            raise ValueError("stoploss must be negative, for example -0.10")
        if minimal_roi <= 0:
            raise ValueError("minimal_roi must be positive, for example 0.02")
        if trend_period < 0:
            raise ValueError("trend_period must be >= 0 (0 turns the filter off)")
        if trailing_stop:
            if not 0 < trailing_stop_positive < 1:
                raise ValueError("trailing_stop_positive must be between 0 and 1")
            if trailing_stop_positive_offset < 0:
                raise ValueError("trailing_stop_positive_offset must be >= 0")

        self.rsi_entry = rsi_entry
        self.rsi_exit = rsi_exit
        self.rsi_period = rsi_period
        self.stoploss = stoploss
        self.minimal_roi = minimal_roi
        self.trend_period = trend_period
        self.confirm_upturn = confirm_upturn
        # Trailing stop: once price is up by `offset`, a stop rides `positive`
        # below the highest price seen, so profit is protected as price climbs.
        self.trailing_stop = trailing_stop
        self.trailing_stop_positive = trailing_stop_positive
        self.trailing_stop_positive_offset = trailing_stop_positive_offset
        # Need enough closed candles for RSI and for the trend average.
        self.warmup = max(rsi_period + 1, trend_period)

    def prepare(self, candles: list[Candle]) -> list[dict]:
        closes = [candle.close for candle in candles]
        rsi_values = rsi(closes, self.rsi_period)
        trend_values = (
            sma(closes, self.trend_period)
            if self.trend_period > 0
            else [None] * len(closes)
        )
        rows: list[dict] = []
        previous_rsi: float | None = None
        for candle, rsi_value, trend_value in zip(candles, rsi_values, trend_values):
            rows.append(
                {
                    "time": candle.time,
                    "open": candle.open,
                    "high": candle.high,
                    "low": candle.low,
                    "close": candle.close,
                    "volume": candle.volume,
                    "rsi": rsi_value,
                    "rsi_prev": previous_rsi,
                    "sma": trend_value,
                }
            )
            previous_rsi = rsi_value
        return rows

    def entry_reason(self, row: dict) -> str | None:
        value = row["rsi"]
        if value is None:
            return None

        # 1) Trend filter: only buy while price holds above the long average.
        if self.trend_period > 0:
            trend = row.get("sma")
            if trend is None or row["close"] < trend:
                return None

        # 2) + 3) RSI oversold, then turning back up through the entry line.
        if self.confirm_upturn:
            previous = row.get("rsi_prev")
            if previous is not None and previous < self.rsi_entry <= value:
                return "rsi_recovery"
            return None

        if value < self.rsi_entry:
            return "rsi_oversold"
        return None

    def exit_reason(self, row: dict) -> str | None:
        value = row["rsi"]
        if value is not None and value > self.rsi_exit:
            return "rsi_overbought"
        return None
