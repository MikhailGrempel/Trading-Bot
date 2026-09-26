"""Small technical indicators.

RSI and SMA are written out in full so you can see the math.
No pandas and no TA-Lib.
"""

from __future__ import annotations


def sma(values: list[float], period: int) -> list[float | None]:
    """Simple moving average. The first `period - 1` values are None."""
    if period < 1:
        raise ValueError("period must be >= 1")

    out: list[float | None] = [None] * len(values)
    if len(values) < period:
        return out

    window = sum(values[:period])
    out[period - 1] = window / period
    for i in range(period, len(values)):
        window += values[i] - values[i - period]
        out[i] = window / period
    return out


def rsi(values: list[float], period: int = 14) -> list[float | None]:
    """Wilder's RSI.

    0 means price only fell. 100 means price only rose.
    Values below 30 are a common 'oversold' buy zone.
    Values above 70 are a common 'overbought' sell zone.
    """
    if period < 1:
        raise ValueError("period must be >= 1")

    out: list[float | None] = [None] * len(values)
    if len(values) <= period:
        return out

    gains: list[float] = []
    losses: list[float] = []
    for i in range(1, len(values)):
        change = values[i] - values[i - 1]
        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    out[period] = _rsi_value(avg_gain, avg_loss)

    for i in range(period, len(gains)):
        avg_gain = ((avg_gain * (period - 1)) + gains[i]) / period
        avg_loss = ((avg_loss * (period - 1)) + losses[i]) / period
        out[i + 1] = _rsi_value(avg_gain, avg_loss)
    return out


def _rsi_value(avg_gain: float, avg_loss: float) -> float:
    if avg_loss == 0:
        return 100.0
    if avg_gain == 0:
        return 0.0
    relative_strength = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + relative_strength))
