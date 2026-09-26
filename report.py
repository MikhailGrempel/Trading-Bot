"""Turn the paper trades into a short text report."""

from __future__ import annotations

from datetime import datetime

from bot import Bot
from market import Candle


def render(bot: Bot, data: dict[str, list[Candle]], stake_currency: str) -> str:
    lines: list[str] = []
    if not bot.events:
        lines.append("No trades. The strategy never had a free slot, cash, and a buy signal together.")
    else:
        lines.append("Trades (paper only, no exchange order was sent)")
        for event in bot.events:
            lines.append(_format_event(event, stake_currency))

    last_prices = {pair: candles[-1].close for pair, candles in data.items()}
    portfolio = bot.portfolio
    equity = portfolio.equity(last_prices)
    profit = equity - portfolio.starting_balance
    closed = portfolio.closed_trades
    wins = sum(1 for trade in closed if (trade.profit or 0) > 0)
    losses = sum(1 for trade in closed if (trade.profit or 0) <= 0)

    lines.append("")
    lines.append("Result")
    lines.append(f"Closed trades: {len(closed)}  (wins {wins}, losses {losses})")
    lines.append(f"Still open:    {len(portfolio.open_trades)}")
    lines.append(f"Start balance: {_money(portfolio.starting_balance)} {stake_currency}")
    lines.append(f"End equity:    {_money(equity)} {stake_currency}")
    lines.append(
        f"Profit:        {_signed_money(profit)} {stake_currency} ({_signed_pct(profit / portfolio.starting_balance)})"
    )

    if portfolio.open_trades:
        lines.append("")
        lines.append("Open positions, marked at the last close")
        for trade in portfolio.open_trades:
            mark = portfolio.unrealized(trade, last_prices[trade.pair])
            lines.append(
                f"  {trade.pair}  entry {_price(trade.entry_price)}  "
                f"now {_price(last_prices[trade.pair])}  "
                f"unrealized {_signed_money(mark)} {stake_currency}"
            )

    if bot.skips:
        lines.append("")
        lines.append("Buy signals that did not become trades")
        labels = {
            "max_open_trades": "max open trades already reached",
            "not_enough_balance": "not enough cash",
            "pair_already_open": "that pair was already open",
            "entry_and_exit_on_same_candle": "buy and sell signal on the same candle",
            "cooldown": "cooldown after a recent exit on that pair",
        }
        for key, count in bot.skips.most_common():
            lines.append(f"  {count:4d}  {labels.get(key, key)}")

    reasons: dict[str, int] = {}
    for trade in closed:
        reasons[trade.exit_reason or "unknown"] = reasons.get(trade.exit_reason or "unknown", 0) + 1
    if reasons:
        lines.append("")
        lines.append("Why trades were closed")
        for reason, count in sorted(reasons.items()):
            lines.append(f"  {count:4d}  {reason}")

    lines.extend(_rules_that_did_not_fire(bot, reasons))
    if set(reasons) == {"rsi_overbought"} and profit < 0:
        lines.append("")
        lines.append(
            "This run lost money. RSI went under 30 while price was still falling, "
            "so the buy was early. RSI later went over 70 before price got back to the buy. "
            "The wallet is following those rules."
        )
    return "\n".join(lines)


def _rules_that_did_not_fire(bot: Bot, reasons: dict[str, int]) -> list[str]:
    """The stop and the target are checked even when another rule sells first."""
    if not bot.portfolio.closed_trades and not bot.portfolio.open_trades:
        return []

    lines = [""]
    stop = bot.strategy.stoploss * 100
    target = bot.strategy.minimal_roi * 100
    if "stoploss" not in reasons:
        lines.append(
            f"Stop {stop:.1f}% was checked on every open trade. "
            "Price did not fall that far before another sell rule."
        )
    if "roi" not in reasons:
        lines.append(
            f"Target +{target:.1f}% was checked on every open trade. "
            "Price did not rise that far before another sell rule."
        )
    return lines if len(lines) > 1 else []


def _format_event(event: dict, stake_currency: str) -> str:
    when = _clock(event["time"])
    pair = f"{event['pair']:<8}"
    price = _price(event["price"])
    rsi = event.get("rsi")
    rsi_text = f"  rsi {rsi:5.1f}" if isinstance(rsi, float) else ""

    if event["action"] == "ENTER":
        return (
            f"{when}  ENTER  {pair}  price {price}  "
            f"stake {_money(event['stake'])} {stake_currency}{rsi_text}  "
            f"reason {event['reason']}"
        )

    profit = event["profit"]
    ratio = profit / event["stake"]
    return (
        f"{when}  EXIT   {pair}  price {price}  "
        f"profit {_signed_money(profit)} {stake_currency} ({_signed_pct(ratio)}){rsi_text}  "
        f"reason {event['reason']}"
    )


def _clock(when: datetime) -> str:
    return when.strftime("%Y-%m-%d %H:%M")


def _price(value: float) -> str:
    if value >= 100:
        return f"{value:.2f}"
    return f"{value:.4f}"


def _money(value: float) -> str:
    return f"{value:.2f}"


def _signed_money(value: float) -> str:
    return f"{value:+.2f}"


def _signed_pct(value: float) -> str:
    return f"{value * 100:+.2f}%"
