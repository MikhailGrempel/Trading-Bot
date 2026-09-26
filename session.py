"""Run the paper bot once and return the numbers the page needs.

The command line and the web page both call `execute` so they share one loop.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from bot import Bot
from market import SOURCE, Candle, load_market
from strategy import RsiStrategy

SKIP_LABELS = {
    "max_open_trades": "max open trades already reached",
    "not_enough_balance": "not enough cash",
    "pair_already_open": "that pair was already open",
    "entry_and_exit_on_same_candle": "buy and sell signal on the same candle",
    "cooldown": "cooldown after a recent exit on that pair",
    "circuit_breaker": "portfolio circuit breaker (new entries paused)",
}

REASON_LABELS = {
    "rsi_oversold": "RSI oversold",
    "rsi_overbought": "RSI overbought",
    "stoploss": "Stop",
    "trailing_stop": "Trailing stop",
    "roi": "Target",
}


def load_config(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        config = json.load(handle)

    required = [
        "stake_currency",
        "dry_run_wallet",
        "stake_amount",
        "max_open_trades",
        "fee",
        "pairs",
        "candles",
        "rsi_entry",
        "rsi_exit",
        "rsi_period",
        "stoploss",
        "minimal_roi",
    ]
    missing = [key for key in required if key not in config]
    if missing:
        raise ValueError(f"config is missing: {', '.join(missing)}")
    if not config["pairs"]:
        raise ValueError("config pairs is empty")
    return config


def apply_form(base: dict, form: dict) -> dict:
    """Copy the file config and replace the fields the page is allowed to edit."""
    config = dict(base)
    config["rsi_entry"] = _number(form, "rsi_entry", config["rsi_entry"])
    config["rsi_exit"] = _number(form, "rsi_exit", config["rsi_exit"])
    config["stake_amount"] = _number(form, "stake_amount", config["stake_amount"])
    config["max_open_trades"] = int(_number(form, "max_open_trades", config["max_open_trades"]))
    if "stop_percent" in form:
        config["stoploss"] = -abs(_number(form, "stop_percent", 0)) / 100
    if "target_percent" in form:
        config["minimal_roi"] = abs(_number(form, "target_percent", 0)) / 100
    return config


def strategy_from_config(config: dict) -> RsiStrategy:
    return RsiStrategy(
        rsi_entry=float(config["rsi_entry"]),
        rsi_exit=float(config["rsi_exit"]),
        rsi_period=int(config["rsi_period"]),
        stoploss=float(config["stoploss"]),
        minimal_roi=float(config["minimal_roi"]),
        trend_period=int(config.get("trend_period", 50)),
        confirm_upturn=bool(config.get("confirm_upturn", True)),
        trailing_stop=bool(config.get("trailing_stop", False)),
        trailing_stop_positive=float(config.get("trailing_stop_positive", 0.02)),
        trailing_stop_positive_offset=float(config.get("trailing_stop_positive_offset", 0.02)),
    )


def bot_from_config(config: dict, strategy: RsiStrategy | None = None) -> Bot:
    if strategy is None:
        strategy = strategy_from_config(config)
    max_stake = config.get("max_stake")
    return Bot(
        strategy,
        starting_balance=float(config["dry_run_wallet"]),
        stake_amount=float(config["stake_amount"]),
        max_open_trades=int(config["max_open_trades"]),
        fee=float(config["fee"]),
        stake_type=str(config.get("stake_type", "fixed")),
        tradable_balance_ratio=float(config.get("tradable_balance_ratio", 1.0)),
        min_stake=float(config.get("min_stake", 0.0)),
        max_stake=float(max_stake) if max_stake is not None else None,
        cooldown_candles=int(config.get("cooldown_candles", 0)),
        cooldown_after=str(config.get("cooldown_after", "stop")),
        max_consecutive_losses=int(config.get("max_consecutive_losses", 0)),
        max_drawdown=float(config.get("max_drawdown", 0.0)),
        slippage=float(config.get("slippage", 0.0)),
    )


def execute(config: dict) -> tuple[Bot, dict[str, list[Candle]]]:
    bot = bot_from_config(config)
    data = load_market(list(config["pairs"]), count=int(config["candles"]))
    bot.run(data)
    return bot, data


def to_payload(bot: Bot, data: dict[str, list[Candle]], config: dict) -> dict:
    portfolio = bot.portfolio
    last_prices = {pair: candles[-1].close for pair, candles in data.items()}
    equity = portfolio.equity(last_prices)
    profit = equity - portfolio.starting_balance
    closed = portfolio.closed_trades
    wins = sum(1 for trade in closed if (trade.profit or 0) > 0)

    entry_rsi: dict[tuple[str, str], float | None] = {}
    exit_rsi: dict[tuple[str, str], float | None] = {}
    markers = []
    for event in bot.events:
        stamp = _clock(event["time"])
        markers.append(
            {
                "pair": event["pair"],
                "action": event["action"],
                "time": stamp,
                "price": event["price"],
                "reason": event["reason"],
            }
        )
        key = (event["pair"], stamp)
        if event["action"] == "ENTER":
            entry_rsi[key] = event.get("rsi")
        else:
            exit_rsi[key] = event.get("rsi")

    trades = []
    for trade in closed:
        entry_at = _clock(trade.entry_time)
        exit_at = _clock(trade.exit_time) if trade.exit_time else ""
        trades.append(
            {
                "pair": trade.pair,
                "entry_time": entry_at,
                "exit_time": exit_at,
                "entry_price": trade.entry_price,
                "exit_price": trade.exit_price,
                "stake": trade.stake,
                "profit": trade.profit,
                "profit_pct": (trade.profit or 0) / trade.stake,
                "reason": trade.exit_reason,
                "reason_label": REASON_LABELS.get(trade.exit_reason or "", trade.exit_reason),
                "entry_rsi": entry_rsi.get((trade.pair, entry_at)),
                "exit_rsi": exit_rsi.get((trade.pair, exit_at)),
            }
        )

    reasons: dict[str, int] = {}
    for trade in closed:
        name = trade.exit_reason or "unknown"
        reasons[name] = reasons.get(name, 0) + 1

    open_trades = []
    for trade in portfolio.open_trades:
        last = last_prices[trade.pair]
        unrealized = portfolio.unrealized(trade, last)
        open_trades.append(
            {
                "pair": trade.pair,
                "entry_time": _clock(trade.entry_time),
                "entry_price": trade.entry_price,
                "amount": trade.amount,
                "stake": trade.stake,
                "last_price": last,
                "stop_price": trade.entry_price * (1 + bot.strategy.stoploss),
                "target_price": trade.entry_price * (1 + bot.strategy.minimal_roi),
                "unrealized": unrealized,
                "unrealized_pct": unrealized / trade.stake,
            }
        )

    pairs = {}
    for pair, candles in data.items():
        rows = bot.strategy.prepare(candles)
        pairs[pair] = {
            "time": [_clock(candle.time) for candle in candles],
            "open": [candle.open for candle in candles],
            "high": [candle.high for candle in candles],
            "low": [candle.low for candle in candles],
            "close": [candle.close for candle in candles],
            "volume": [candle.volume for candle in candles],
            "rsi": [row["rsi"] for row in rows],
        }

    return {
        "currency": config["stake_currency"],
        "rules": {
            "rsi_entry": float(config["rsi_entry"]),
            "rsi_exit": float(config["rsi_exit"]),
            "stop_percent": abs(float(config["stoploss"])) * 100,
            "target_percent": float(config["minimal_roi"]) * 100,
            "stake_amount": float(config["stake_amount"]),
            "max_open_trades": int(config["max_open_trades"]),
            "fee_percent": float(config["fee"]) * 100,
            "slippage_percent": float(config.get("slippage", 0.0)) * 100,
            "stake_type": str(config.get("stake_type", "fixed")),
            "wallet": float(config["dry_run_wallet"]),
        },
        "summary": {
            "starting_balance": portfolio.starting_balance,
            "equity": equity,
            "profit": profit,
            "profit_pct": profit / portfolio.starting_balance,
            "closed": len(closed),
            "wins": wins,
            "losses": len(closed) - wins,
            "open": len(portfolio.open_trades),
        },
        "circuit": {
            "entries_blocked": bot.entries_blocked,
            "block_reason": bot.block_reason,
            "peak_equity": bot.peak_equity,
            "consecutive_losses": bot.consecutive_losses,
            "drawdown_pct": (bot.peak_equity - equity) / bot.peak_equity
            if bot.peak_equity > 0
            else 0.0,
            "max_drawdown_pct": float(config.get("max_drawdown", 0.0)),
            "max_consecutive_losses": int(config.get("max_consecutive_losses", 0)),
        },
        "trades": trades,
        "open_trades": open_trades,
        "markers": markers,
        "pairs": pairs,
        "skips": [
            {"count": count, "label": SKIP_LABELS.get(key, key)}
            for key, count in bot.skips.most_common()
        ],
        "exit_reasons": [
            {"reason": reason, "label": REASON_LABELS.get(reason, reason), "count": count}
            for reason, count in sorted(reasons.items())
        ],
        "notes": _notes(bot, reasons, profit),
        "source": SOURCE["name"] + (" (saved copy)" if SOURCE["stale"] else ""),
        "range": {
            "start": _clock(next(iter(data.values()))[0].time),
            "end": _clock(next(iter(data.values()))[-1].time),
        },
    }


def _notes(bot: Bot, reasons: dict[str, int], profit: float) -> list[str]:
    if not bot.portfolio.closed_trades and not bot.portfolio.open_trades:
        return ["No trades. A buy needs a signal, a free slot, and enough cash at the same time."]

    notes = []
    if bot.entries_blocked:
        reason = bot.block_reason or "unknown"
        notes.append(
            f"New entries are paused ({reason}). Open trades can still exit. "
            "Press Start in the live UI to reset the circuit breaker."
        )
    if "stoploss" not in reasons:
        notes.append(
            f"Stop {bot.strategy.stoploss * 100:.1f}% was checked on every open trade. "
            "Price did not fall that far before another sell rule."
        )
    if "roi" not in reasons:
        notes.append(
            f"Target +{bot.strategy.minimal_roi * 100:.1f}% was checked on every open trade. "
            "Price did not rise that far before another sell rule."
        )
    if set(reasons) == {"rsi_overbought"} and profit < 0:
        notes.append(
            "This run lost money. RSI went under the buy level while price was still falling, "
            "so the buy was early. RSI later went over the sell level before price got back to the buy."
        )
    return notes


def _number(form: dict, key: str, default: float) -> float:
    if key not in form or form[key] == "":
        return float(default)
    labels = {
        "rsi_entry": "RSI buy",
        "rsi_exit": "RSI sell",
        "stop_percent": "Stop",
        "target_percent": "Target",
        "stake_amount": "Stake",
        "max_open_trades": "Max open trades",
    }
    try:
        return float(form[key])
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{labels.get(key, key)} must be a number") from exc


def _clock(when: datetime) -> str:
    return when.strftime("%Y-%m-%d %H:%M")
