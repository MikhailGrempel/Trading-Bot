"""The trading loop.

Read `run` from top to bottom. Each pass is one new candle:

1. Look only at candles that have already closed.
2. Ask the strategy whether to enter or exit.
3. Close open trades that hit a stop, a target, or an exit signal.
4. Open new trades when a slot and cash are free.

Orders stay inside a paper wallet. No exchange is contacted.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta

from market import INTERVAL_MINUTES, Candle
from portfolio import Portfolio, Trade

_STOP_COOLDOWN_REASONS = frozenset({"stoploss", "trailing_stop"})


class Bot:
    def __init__(
        self,
        strategy,
        starting_balance: float,
        stake_amount: float,
        max_open_trades: int,
        fee: float,
        stake_type: str = "fixed",
        tradable_balance_ratio: float = 1.0,
        min_stake: float = 0.0,
        max_stake: float | None = None,
        cooldown_candles: int = 0,
        cooldown_after: str = "stop",
    ) -> None:
        if max_open_trades < 1:
            raise ValueError("max_open_trades must be >= 1")
        if stake_type not in ("fixed", "percent"):
            raise ValueError("stake_type must be 'fixed' or 'percent'")
        if not 0 < tradable_balance_ratio <= 1:
            raise ValueError("tradable_balance_ratio must be between 0 and 1")
        if min_stake < 0:
            raise ValueError("min_stake must be >= 0")
        if cooldown_candles < 0:
            raise ValueError("cooldown_candles must be >= 0")
        if cooldown_after not in ("stop", "any"):
            raise ValueError("cooldown_after must be 'stop' or 'any'")

        if stake_type == "fixed":
            if stake_amount <= 0:
                raise ValueError("stake_amount must be positive")
            if stake_amount > starting_balance:
                raise ValueError("stake_amount is larger than the wallet")
        else:
            if not 0 < stake_amount <= 100:
                raise ValueError("stake_amount must be a percent between 0 and 100")

        cap = max_stake if max_stake is not None else starting_balance
        if cap < min_stake:
            raise ValueError("max_stake must be >= min_stake")

        self.strategy = strategy
        self.stake_amount = stake_amount
        self.stake_type = stake_type
        self.tradable_balance_ratio = tradable_balance_ratio
        self.min_stake = min_stake
        self.max_stake = cap
        self.cooldown_candles = cooldown_candles
        self.cooldown_after = cooldown_after
        self.max_open_trades = max_open_trades
        self.portfolio = Portfolio(starting_balance, fee)
        self.events: list[dict] = []
        self.skips: Counter[str] = Counter()
        self.cooldown_until: dict[str, datetime] = {}

    def run(self, data: dict[str, list[Candle]]) -> None:
        pairs = list(data)
        if not pairs:
            raise ValueError("no pairs to trade")

        length = len(data[pairs[0]])
        for pair in pairs[1:]:
            if len(data[pair]) != length:
                raise ValueError("every pair needs the same number of candles")

        warmup = self.strategy.warmup
        if warmup < 1 or warmup >= length:
            raise ValueError("not enough candles for the strategy warmup")

        # Candle i is the one that just opened. The strategy may only see
        # candles[:i], which are already closed. That blocks lookahead.
        for i in range(warmup, length):
            signals = {}
            for pair in pairs:
                closed = data[pair][:i]
                rows = self.strategy.prepare(closed)
                signals[pair] = rows[-1]
            fill = {pair: data[pair][i] for pair in pairs}
            self._on_candle(pairs, signals, fill)

    def _on_candle(self, pairs: list[str], signals: dict[str, dict], fill: dict[str, Candle]) -> None:
        closed_this_candle: set[str] = set()

        for trade in list(self.portfolio.open_trades):
            decision = self._exit_decision(trade, signals[trade.pair], fill[trade.pair], allow_signal=True)
            if decision is None:
                self._track_peak(trade, fill[trade.pair])
                continue
            reason, price = decision
            self._close(trade, fill[trade.pair], price, reason, signals[trade.pair])
            closed_this_candle.add(trade.pair)

        for pair in pairs:
            self._try_entry(pair, signals[pair], fill[pair], closed_this_candle)

    def _try_entry(self, pair: str, row: dict, candle: Candle, closed_this_candle: set[str]) -> None:
        entry = self.strategy.entry_reason(row)
        if entry is None:
            return
        if self.strategy.exit_reason(row) is not None:
            self.skips["entry_and_exit_on_same_candle"] += 1
            return
        if pair in closed_this_candle or self.portfolio.has_open(pair):
            self.skips["pair_already_open"] += 1
            return
        if len(self.portfolio.open_trades) >= self.max_open_trades:
            self.skips["max_open_trades"] += 1
            return
        until = self.cooldown_until.get(pair)
        if until is not None and candle.time < until:
            self.skips["cooldown"] += 1
            return

        stake = self.entry_stake()
        if stake <= 0 or self.portfolio.balance < stake:
            self.skips["not_enough_balance"] += 1
            return

        trade = self.portfolio.open_trade(pair, candle.time, candle.open, stake)
        self.events.append(
            {
                "time": candle.time,
                "action": "ENTER",
                "pair": pair,
                "price": candle.open,
                "stake": stake,
                "reason": entry,
                "rsi": row.get("rsi"),
            }
        )

        # The buy fills at the open. The rest of this candle can still hit
        # the stop or the target. The exit signal waits for a later candle.
        decision = self._exit_decision(trade, row, candle, allow_signal=False)
        if decision is not None:
            reason, price = decision
            self._close(trade, candle, price, reason, row)
        else:
            self._track_peak(trade, candle)

    def _track_peak(self, trade: Trade, candle: Candle) -> None:
        """Remember the highest price seen since entry, for the trailing stop.

        Updated after the exit check, so the trailing level used on any candle
        reflects only candles that closed before it. No lookahead.
        """
        peak = trade.high_water if trade.high_water is not None else trade.entry_price
        if candle.high > peak:
            trade.high_water = candle.high

    def _effective_stop(self, trade: Trade) -> tuple[float, str]:
        """The stop price in force now: the fixed stop, or a higher trailing stop."""
        stop = trade.entry_price * (1 + self.strategy.stoploss)
        reason = "stoploss"
        if getattr(self.strategy, "trailing_stop", False):
            peak = trade.high_water if trade.high_water is not None else trade.entry_price
            activation = trade.entry_price * (1 + self.strategy.trailing_stop_positive_offset)
            if peak >= activation:
                trailing = peak * (1 - self.strategy.trailing_stop_positive)
                if trailing > stop:
                    stop, reason = trailing, "trailing_stop"
        return stop, reason

    def _exit_decision(
        self,
        trade: Trade,
        row: dict,
        candle: Candle,
        allow_signal: bool,
    ) -> tuple[str, float] | None:
        """Decide whether this candle sells an open long.

        The open is the first price of the candle, so gaps are checked first.
        After that, a strategy exit sells at the open.
        If neither happens, a resting stop or target can fill later in the candle.
        When both the stop and the target sit inside the same candle, the stop wins.
        """
        stop, stop_reason = self._effective_stop(trade)
        target = trade.entry_price * (1 + self.strategy.minimal_roi)

        if candle.open <= stop:
            return stop_reason, candle.open
        if candle.open >= target:
            return "roi", candle.open

        if allow_signal:
            reason = self.strategy.exit_reason(row)
            if reason is not None:
                return reason, candle.open

        hit_stop = candle.low <= stop
        hit_target = candle.high >= target
        if hit_stop:
            return stop_reason, stop
        if hit_target:
            return "roi", target
        return None

    def entry_stake(self) -> float:
        """Stake for the next buy: fixed USD or a percent of tradable cash."""
        tradable = self.portfolio.balance * self.tradable_balance_ratio
        if self.stake_type == "fixed":
            return min(self.stake_amount, self.max_stake)
        stake = tradable * (self.stake_amount / 100.0)
        return max(self.min_stake, min(stake, self.max_stake, tradable))

    def _set_cooldown(self, pair: str, when: datetime, reason: str) -> None:
        if self.cooldown_candles <= 0:
            return
        if self.cooldown_after == "any" or reason in _STOP_COOLDOWN_REASONS:
            delta = timedelta(minutes=INTERVAL_MINUTES * self.cooldown_candles)
            self.cooldown_until[pair] = when + delta

    def _close(self, trade: Trade, candle: Candle, price: float, reason: str, row: dict) -> None:
        self.portfolio.close_trade(trade, candle.time, price, reason)
        self._set_cooldown(trade.pair, candle.time, reason)
        self.events.append(
            {
                "time": candle.time,
                "action": "EXIT",
                "pair": trade.pair,
                "price": price,
                "stake": trade.stake,
                "profit": trade.profit,
                "reason": reason,
                "rsi": row.get("rsi"),
            }
        )
