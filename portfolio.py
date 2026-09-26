"""Paper wallet and trades.

Buying spends stake currency (USD) and receives the coin.
Selling does the reverse. The fee is taken on both sides.

Nothing here talks to an exchange. The balance is just a number.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class Trade:
    pair: str
    entry_time: datetime
    entry_price: float
    amount: float
    stake: float
    fee_open: float
    high_water: float | None = None
    exit_time: datetime | None = None
    exit_price: float | None = None
    fee_close: float = 0.0
    exit_reason: str | None = None
    profit: float | None = None

    @property
    def is_open(self) -> bool:
        return self.exit_time is None

    def profit_ratio(self) -> float | None:
        if self.profit is None:
            return None
        return self.profit / self.stake


class Portfolio:
    def __init__(self, balance: float, fee_rate: float, slippage_rate: float = 0.0) -> None:
        if balance <= 0:
            raise ValueError("starting balance must be positive")
        if not 0 <= fee_rate < 1:
            raise ValueError("fee must be between 0 and 1")
        if not 0 <= slippage_rate < 1:
            raise ValueError("slippage must be between 0 and 1")
        self.starting_balance = balance
        self.balance = balance
        self.fee_rate = fee_rate
        self.slippage_rate = slippage_rate
        self.open_trades: list[Trade] = []
        self.closed_trades: list[Trade] = []

    def has_open(self, pair: str) -> bool:
        return any(trade.pair == pair for trade in self.open_trades)

    def open_trade(self, pair: str, when: datetime, price: float, stake: float) -> Trade:
        """Buy `pair` at `price`, spending `stake` of the wallet."""
        if stake > self.balance:
            raise ValueError(f"not enough balance to stake {stake}")
        if price <= 0 or stake <= 0:
            raise ValueError("price and stake must be positive")

        fill = price * (1 + self.slippage_rate)
        fee = stake * self.fee_rate
        amount = (stake - fee) / fill
        self.balance -= stake
        trade = Trade(
            pair=pair,
            entry_time=when,
            entry_price=fill,
            amount=amount,
            stake=stake,
            fee_open=fee,
            high_water=fill,
        )
        self.open_trades.append(trade)
        return trade

    def close_trade(self, trade: Trade, when: datetime, price: float, reason: str) -> None:
        """Sell an open trade. Profit is what comes back minus what was spent."""
        if trade not in self.open_trades:
            raise ValueError("trade is not open")
        if price <= 0:
            raise ValueError("price must be positive")

        fill = price * (1 - self.slippage_rate)
        gross = trade.amount * fill
        fee = gross * self.fee_rate
        self.balance += gross - fee
        trade.exit_time = when
        trade.exit_price = fill
        trade.fee_close = fee
        trade.exit_reason = reason
        trade.profit = (gross - fee) - trade.stake
        self.open_trades.remove(trade)
        self.closed_trades.append(trade)

    def unrealized(self, trade: Trade, price: float) -> float:
        """Profit if the open trade were sold at `price` right now (with slippage and fee)."""
        fill = price * (1 - self.slippage_rate)
        gross = trade.amount * fill
        fee = gross * self.fee_rate
        return (gross - fee) - trade.stake

    def equity(self, prices: dict[str, float]) -> float:
        """Cash plus mark-to-market value after a hypothetical sell (slippage and fee)."""
        value = self.balance
        for trade in self.open_trades:
            fill = prices[trade.pair] * (1 - self.slippage_rate)
            value += trade.amount * fill * (1 - self.fee_rate)
        return value
