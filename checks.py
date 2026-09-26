"""Small checks for the trading rules.

Run with: python run.py check
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

from bot import Bot
from live import advance, trading_gate
from indicators import rsi, sma
from market import Candle
from portfolio import Portfolio


class RuleStrategy:
    """Test double. Entry and exit are plain functions of the latest close."""

    def __init__(self, entry, exit, stoploss=-0.10, roi=0.10, warmup=1, spy=None) -> None:
        self._entry = entry
        self._exit = exit
        self.stoploss = stoploss
        self.minimal_roi = roi
        self.warmup = warmup
        self.spy = spy

    def prepare(self, candles: list[Candle]) -> list[dict]:
        rows = []
        for candle in candles:
            if self.spy is not None:
                self.spy(candle)
            rows.append(
                {
                    "time": candle.time,
                    "open": candle.open,
                    "high": candle.high,
                    "low": candle.low,
                    "close": candle.close,
                    "rsi": None,
                }
            )
        return rows

    def entry_reason(self, row: dict) -> str | None:
        return self._entry(row)

    def exit_reason(self, row: dict) -> str | None:
        return self._exit(row)


def run_checks() -> None:
    _check_sma()
    _check_rsi_direction()
    _check_fee_round_trip()
    _check_entry_uses_next_candle_open()
    _check_strategy_cannot_see_the_fill_candle()
    _check_stoploss_fills_at_the_stop_price()
    _check_stop_wins_when_stop_and_target_are_both_inside_one_candle()
    _check_gap_through_stop_fills_at_the_open()
    _check_roi_fills_at_the_target()
    _check_exit_signal_sells_at_the_next_open()
    _check_max_open_trades()
    _check_one_trade_per_pair()
    _check_collision_does_not_open()
    _check_not_enough_cash()
    _check_forward_ignores_history()
    _check_forward_stands_still_when_no_new_candle()
    _check_stop_then_start_skips_the_pause()
    _check_cooldown_blocks_reentry_after_stop()
    _check_percent_stake_from_balance()
    print("checks passed")


def _check_sma() -> None:
    values = sma([1, 2, 3, 4, 5], 3)
    assert values[:2] == [None, None]
    assert values[2:] == [2, 3, 4]


def _check_rsi_direction() -> None:
    falling = rsi([100 - i for i in range(40)], 14)
    rising = rsi([100 + i for i in range(40)], 14)
    assert falling[-1] == 0
    assert rising[-1] == 100


def _check_fee_round_trip() -> None:
    portfolio = Portfolio(1000, fee_rate=0.001)
    trade = portfolio.open_trade("BTC/USD", _time(0), price=50, stake=100)
    portfolio.close_trade(trade, _time(1), price=50, reason="test")
    # Buy fee and sell fee. 100 * 0.001, then the coins are sold for 99.9.
    assert math.isclose(trade.profit, -0.1999, abs_tol=1e-9)
    assert math.isclose(portfolio.balance, 999.8001, abs_tol=1e-9)


def _check_entry_uses_next_candle_open() -> None:
    strategy = RuleStrategy(
        entry=lambda row: "enter" if row["close"] == 100 else None,
        exit=lambda row: None,
        stoploss=-0.50,
        roi=0.50,
    )
    data = {
        "BTC/USD": [
            _candle(0, 100, 100, 100, 100),
            _candle(1, 110, 111, 109, 110),
        ]
    }
    bot = _bot(strategy)
    bot.run(data)
    assert len(bot.portfolio.open_trades) == 1
    assert bot.portfolio.open_trades[0].entry_price == 110


def _check_strategy_cannot_see_the_fill_candle() -> None:
    seen: list[float] = []
    strategy = RuleStrategy(
        entry=lambda row: "enter" if row["close"] == 100 else None,
        exit=lambda row: None,
        stoploss=-0.50,
        roi=0.50,
        spy=lambda candle: seen.append(candle.close),
    )
    data = {"BTC/USD": [_candle(0, 100, 100, 100, 100), _candle(1, 100, 999, 100, 999)]}
    _bot(strategy).run(data)
    assert 999 not in seen


def _check_stoploss_fills_at_the_stop_price() -> None:
    bot = _run_one(
        candles=[_candle(0, 100, 100, 100, 100), _candle(1, 100, 101, 80, 90)],
        stoploss=-0.10,
        roi=0.50,
    )
    trade = bot.portfolio.closed_trades[0]
    assert trade.exit_reason == "stoploss"
    assert trade.exit_price == 90
    assert trade.profit == -10


def _check_stop_wins_when_stop_and_target_are_both_inside_one_candle() -> None:
    bot = _run_one(
        candles=[_candle(0, 100, 100, 100, 100), _candle(1, 100, 130, 80, 100)],
        stoploss=-0.10,
        roi=0.05,
    )
    trade = bot.portfolio.closed_trades[0]
    assert trade.exit_reason == "stoploss"
    assert trade.exit_price == 90


def _check_gap_through_stop_fills_at_the_open() -> None:
    bot = _run_one(
        candles=[
            _candle(0, 100, 100, 100, 100),
            _candle(1, 100, 100, 100, 100),
            _candle(2, 70, 75, 60, 72),
        ],
        stoploss=-0.10,
        roi=0.50,
    )
    trade = bot.portfolio.closed_trades[0]
    assert trade.exit_reason == "stoploss"
    assert trade.exit_price == 70


def _check_roi_fills_at_the_target() -> None:
    bot = _run_one(
        candles=[_candle(0, 100, 100, 100, 100), _candle(1, 100, 130, 99, 120)],
        stoploss=-0.10,
        roi=0.05,
    )
    trade = bot.portfolio.closed_trades[0]
    assert trade.exit_reason == "roi"
    assert trade.exit_price == 105
    assert trade.profit == 5


def _check_exit_signal_sells_at_the_next_open() -> None:
    strategy = RuleStrategy(
        entry=lambda row: "enter" if row["close"] < 100 else None,
        exit=lambda row: "exit_signal" if row["close"] > 100 else None,
        stoploss=-0.50,
        roi=0.50,
    )
    data = {
        "BTC/USD": [
            _candle(0, 90, 90, 90, 90),
            _candle(1, 95, 102, 94, 101),
            _candle(2, 110, 112, 108, 111),
        ]
    }
    bot = _bot(strategy, stake=100, balance=1000, fee=0)
    bot.run(data)
    trade = bot.portfolio.closed_trades[0]
    assert trade.entry_price == 95
    assert trade.exit_reason == "exit_signal"
    assert trade.exit_price == 110


def _check_max_open_trades() -> None:
    strategy = RuleStrategy(
        entry=lambda row: "enter" if row["close"] == 10 else None,
        exit=lambda row: None,
        stoploss=-0.50,
        roi=0.50,
    )
    data = {
        "BTC/USD": [_candle(0, 10, 10, 10, 10), _candle(1, 10, 10, 10, 10)],
        "ETH/USD": [_candle(0, 10, 10, 10, 10), _candle(1, 11, 11, 11, 11)],
        "SOL/USD": [_candle(0, 10, 10, 10, 10), _candle(1, 12, 12, 12, 12)],
    }
    bot = _bot(strategy, max_open_trades=1)
    bot.run(data)
    assert len(bot.portfolio.open_trades) == 1
    assert bot.portfolio.open_trades[0].pair == "BTC/USD"
    assert bot.skips["max_open_trades"] == 2


def _check_one_trade_per_pair() -> None:
    strategy = RuleStrategy(
        entry=lambda row: "enter",
        exit=lambda row: None,
        stoploss=-0.50,
        roi=0.50,
    )
    data = {"BTC/USD": [_candle(0, 10, 10, 10, 10), _candle(1, 10, 10, 10, 10), _candle(2, 10, 10, 10, 10)]}
    bot = _bot(strategy, max_open_trades=3)
    bot.run(data)
    assert len(bot.portfolio.open_trades) == 1
    assert bot.skips["pair_already_open"] >= 1


def _check_collision_does_not_open() -> None:
    strategy = RuleStrategy(
        entry=lambda row: "enter" if row["close"] == 50 else None,
        exit=lambda row: "exit" if row["close"] == 50 else None,
    )
    data = {"BTC/USD": [_candle(0, 50, 50, 50, 50), _candle(1, 50, 50, 50, 50)]}
    bot = _bot(strategy)
    bot.run(data)
    assert bot.portfolio.open_trades == []
    assert bot.portfolio.closed_trades == []
    assert bot.skips["entry_and_exit_on_same_candle"] == 1


def _check_not_enough_cash() -> None:
    strategy = RuleStrategy(
        entry=lambda row: "enter" if row["close"] == 10 else None,
        exit=lambda row: None,
        stoploss=-0.50,
        roi=0.50,
    )
    data = {
        "BTC/USD": [_candle(0, 10, 10, 10, 10), _candle(1, 10, 10, 10, 10)],
        "ETH/USD": [_candle(0, 10, 10, 10, 10), _candle(1, 11, 11, 11, 11)],
    }
    bot = _bot(strategy, balance=100, stake=80, max_open_trades=3)
    bot.run(data)
    assert len(bot.portfolio.open_trades) == 1
    assert math.isclose(bot.portfolio.balance, 20)
    assert bot.skips["not_enough_balance"] == 1


def _check_forward_ignores_history() -> None:
    strategy = RuleStrategy(
        entry=lambda row: "enter" if row["close"] == 100 else None,
        exit=lambda row: None,
        stoploss=-0.50,
        roi=0.50,
    )
    data = {
        "BTC/USD": [
            _candle(0, 100, 100, 100, 100),
            _candle(1, 101, 101, 101, 101),
            _candle(2, 100, 100, 100, 100),
            _candle(3, 110, 111, 109, 110),
        ]
    }
    bot = _bot(strategy)
    new_last = advance(bot, data, _time(2))
    assert new_last == _time(3)
    assert len(bot.portfolio.open_trades) == 1
    assert bot.portfolio.open_trades[0].entry_price == 110
    assert bot.portfolio.open_trades[0].entry_time == _time(3)


def _check_stop_then_start_skips_the_pause() -> None:
    last = _time(2)
    latest = _time(5)
    running, fill, trade = trading_gate(True, "stop", last, latest)
    assert running is False and fill == last and trade is False
    running, fill, trade = trading_gate(False, None, last, latest)
    assert running is False and fill == last and trade is False
    running, fill, trade = trading_gate(False, "start", last, latest)
    assert running is True and fill == latest and trade is False
    running, fill, trade = trading_gate(True, None, latest, latest)
    assert running is True and fill == latest and trade is True


def _check_cooldown_blocks_reentry_after_stop() -> None:
    strategy = RuleStrategy(
        entry=lambda row: "enter" if row["close"] == 100 else None,
        exit=lambda row: None,
        stoploss=-0.10,
        roi=0.50,
    )
    data = {
        "BTC/USD": [
            _candle(0, 100, 100, 100, 100),
            _candle(1, 100, 101, 80, 90),
            _candle(2, 100, 100, 100, 100),
            _candle(3, 100, 100, 100, 100),
            _candle(4, 100, 100, 100, 100),
        ]
    }
    bot = _bot(strategy, stake=100, balance=1000, fee=0, cooldown_candles=3, cooldown_after="stop")
    bot.run(data)
    assert len(bot.portfolio.closed_trades) == 1
    assert bot.skips["cooldown"] >= 1


def _check_percent_stake_from_balance() -> None:
    strategy = RuleStrategy(
        entry=lambda row: "enter" if row["close"] == 10 else None,
        exit=lambda row: None,
        stoploss=-0.50,
        roi=0.50,
    )
    data = {"BTC/USD": [_candle(0, 10, 10, 10, 10), _candle(1, 20, 20, 20, 20)]}
    bot = _bot(
        strategy,
        balance=1000,
        stake=10,
        fee=0,
        stake_type="percent",
        tradable_balance_ratio=1.0,
        min_stake=0,
        max_stake=500,
    )
    bot.run(data)
    assert len(bot.portfolio.open_trades) == 1
    assert math.isclose(bot.portfolio.open_trades[0].stake, 100.0, abs_tol=1e-9)


def _check_forward_stands_still_when_no_new_candle() -> None:
    strategy = RuleStrategy(
        entry=lambda row: "enter",
        exit=lambda row: None,
        stoploss=-0.50,
        roi=0.50,
    )
    data = {"BTC/USD": [_candle(0, 100, 100, 100, 100), _candle(1, 110, 110, 110, 110)]}
    bot = _bot(strategy)
    new_last = advance(bot, data, _time(1))
    assert new_last == _time(1)
    assert bot.portfolio.open_trades == []


def _run_one(candles: list[Candle], stoploss: float, roi: float) -> Bot:
    strategy = RuleStrategy(
        entry=lambda row: "enter" if row["close"] == 100 else None,
        exit=lambda row: None,
        stoploss=stoploss,
        roi=roi,
    )
    bot = _bot(strategy, stake=100, balance=1000, fee=0)
    bot.run({"BTC/USD": candles})
    assert len(bot.portfolio.closed_trades) == 1
    return bot


def _bot(strategy, balance=1000, stake=30, max_open_trades=3, fee=0.0, **kwargs) -> Bot:
    return Bot(strategy, balance, stake, max_open_trades, fee, **kwargs)


def _time(index: int) -> datetime:
    return datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=15 * index)


def _candle(index: int, open_: float, high: float, low: float, close: float) -> Candle:
    return Candle(_time(index), open_, high, low, close, volume=1)
