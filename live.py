"""Trade forward, one new candle at a time.

The first time this runs, the wallet is flat and the past chart is left alone.
After that, each candle that closes is a chance to buy or sell by the rules.
The wallet is saved in data/paper_state.json, so a restart continues the same trades.
"""

from __future__ import annotations

import json
import threading
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from bot import Bot
from market import SOURCE, Candle, load_market
from portfolio import Trade
from session import apply_form, bot_from_config, to_payload

ROOT = Path(__file__).resolve().parent
STATE_PATH = ROOT / "data" / "paper_state.json"
LOCK = threading.Lock()


def advance(bot: Bot, data: dict[str, list[Candle]], last_fill_time: datetime) -> datetime:
    """Apply the rules to fill-candles that opened after `last_fill_time`.

    Candle i is the fill. The signal is the last candle before it, which has
    already closed. Candles at or before `last_fill_time` are not traded.
    """
    pairs = list(data)
    if not pairs:
        raise ValueError("no pairs to trade")
    stamps = [candle.time for candle in data[pairs[0]]]
    for pair in pairs[1:]:
        if [candle.time for candle in data[pair]] != stamps:
            raise ValueError("every pair needs the same candles")

    new_last = last_fill_time
    for index, stamp in enumerate(stamps):
        if stamp <= last_fill_time:
            continue
        new_last = stamp
        if index < bot.strategy.warmup:
            continue
        signals = {}
        for pair in pairs:
            closed = data[pair][:index]
            signals[pair] = bot.strategy.prepare(closed)[-1]
        fill = {pair: data[pair][index] for pair in pairs}
        bot._on_candle(pairs, signals, fill)
    return new_last


def trading_gate(running: bool, command: str | None, last_fill: datetime, latest: datetime) -> tuple[bool, datetime, bool]:
    """Decide whether this check may buy or sell.

    Stop pauses new buys and sells. Start after a stop begins at the latest
    candle, so candles that closed during the pause are left alone.
    """
    if command == "stop":
        return False, last_fill, False
    if command == "start":
        if not running:
            return True, latest, False
        return True, last_fill, True
    if running:
        return True, last_fill, True
    return False, last_fill, False


def step(base: dict, form: dict | None = None) -> dict:
    """Load the wallet, trade any new closed candles, and return the page payload."""
    with LOCK:
        form = dict(form or {})
        command = form.pop("command", None)
        if command not in (None, "", "start", "stop"):
            raise ValueError("command must be start or stop")
        state = _read_state()
        config = _config_for(base, state, form)
        data = _fresh_market(config)
        bot = _bot(config)
        latest = next(iter(data.values()))[-1].time
        if state is None:
            state = {
                "started_at": _clock(datetime.now(timezone.utc)),
                "last_fill_time": _clock(latest),
                "starting_balance": bot.portfolio.starting_balance,
                "running": False,
            }
            acted = 0
        else:
            _restore(bot, state)
            if command == "start":
                bot.reset_circuit()
            running, last_fill, should_trade = trading_gate(
                bool(state.get("running", True)),
                command or None,
                _parse(state["last_fill_time"]),
                latest,
            )
            acted = 0
            if should_trade:
                before = len(bot.events)
                last_fill = advance(bot, data, last_fill)
                acted = len(bot.events) - before
            state["running"] = running
            state["last_fill_time"] = _clock(last_fill)

        if command == "start":
            state["running"] = True
        elif command == "stop":
            state["running"] = False
        _write_state(bot, state, config)
        return _payload(bot, data, config, state, acted)


def _fresh_market(config: dict) -> dict[str, list[Candle]]:
    """Download again once the next candle should have closed."""
    pairs = list(config["pairs"])
    count = int(config["candles"])
    data = load_market(pairs, count=count)
    latest = next(iter(data.values()))[-1].time
    if datetime.now(timezone.utc) >= latest + timedelta(minutes=30):
        data = load_market(pairs, count=count, refresh=True)
    return data


def _config_for(base: dict, state: dict | None, form: dict) -> dict:
    if form:
        return apply_form(base, form)
    if state and state.get("rules"):
        return apply_form(base, state["rules"])
    return dict(base)


def _bot(config: dict) -> Bot:
    return bot_from_config(config)


def _restore(bot: Bot, state: dict) -> None:
    portfolio = bot.portfolio
    portfolio.starting_balance = float(state["starting_balance"])
    portfolio.balance = float(state["balance"])
    portfolio.open_trades = [_trade(item) for item in state["open_trades"]]
    portfolio.closed_trades = [_trade(item) for item in state["closed_trades"]]
    bot.events = [_event(item) for item in state["events"]]
    bot.skips = Counter(state.get("skips", {}))
    bot.cooldown_until = {
        pair: _parse(stamp) for pair, stamp in state.get("cooldown_until", {}).items()
    }
    bot.peak_equity = float(state.get("peak_equity", bot.portfolio.starting_balance))
    bot.consecutive_losses = int(state.get("consecutive_losses", 0))
    bot.entries_blocked = bool(state.get("entries_blocked", False))
    bot.block_reason = state.get("block_reason")


def _payload(bot: Bot, data: dict[str, list[Candle]], config: dict, state: dict, acted: int) -> dict:
    payload = to_payload(bot, data, config)
    running = bool(state.get("running", True))
    choices = _decisions(bot, data, running)
    latest = next(iter(data.values()))[-1].time
    nxt = latest + timedelta(minutes=30)
    now = datetime.now(timezone.utc)
    if not running:
        when = "Stopped. Prices keep updating. Press Start to buy and sell again. Coins already open stay open."
    elif now >= nxt:
        when = "The next candle has closed. This check applies the rule to it."
    else:
        when = f"The bot buys or sells when the next candle closes, at {_clock(nxt)} UTC."
    payload["rules"]["wallet"] = bot.portfolio.starting_balance
    payload["notes"] = [choice["text"] for choice in choices]
    payload["notes"].append(
        "Triangles on the chart are buys and sells this bot placed after "
        + state["started_at"]
        + " UTC. Older candles are only there so you can see the price."
    )
    if acted:
        payload["notes"].insert(0, f"The bot just acted on {acted} new fill{'s' if acted != 1 else ''}.")
    payload["live"] = {
        "started_at": state["started_at"],
        "last_candle": _clock(latest),
        "next_check": _clock(nxt),
        "acted": acted,
        "running": running,
        "decisions": choices,
        "status": (
            f"Watching since {state['started_at']} UTC. "
            f"Latest closed candle {_clock(latest)} UTC. "
            + when
        ),
        "source_fetched_at": SOURCE.get("fetched_at", ""),
    }
    return payload


def _decisions(bot: Bot, data: dict[str, list[Candle]], running: bool) -> list[dict]:
    choices = []
    for pair, candles in data.items():
        row = bot.strategy.prepare(candles)[-1]
        rsi_value = row.get("rsi")
        holding = next((trade for trade in bot.portfolio.open_trades if trade.pair == pair), None)
        if rsi_value is None:
            text = f"{pair}: RSI is not ready yet."
            kind = "wait"
        elif holding is not None:
            text = (
                f"{pair} is open, bought at {_price(holding.entry_price)}. "
                f"The next candle sells if RSI is above {bot.strategy.rsi_exit:g}, "
                "or if price hits the stop or the target."
            )
            kind = "holding"
        else:
            entry = bot.strategy.entry_reason(row)
            exit_now = bot.strategy.exit_reason(row)
            rsi_text = f"RSI is {rsi_value:.1f}"
            if entry and exit_now:
                text = f"{pair}: {rsi_text}. That is both a buy and a sell, so the bot waits."
                kind = "wait"
            elif entry and bot.entries_blocked:
                text = (
                    f"{pair}: {rsi_text}, which is a buy, but new entries are paused "
                    f"({bot.block_reason or 'circuit breaker'}). Press Start to reset."
                )
                kind = "wait"
            elif entry and len(bot.portfolio.open_trades) >= bot.max_open_trades:
                text = f"{pair}: {rsi_text}, which is a buy, but the trade slots are full."
                kind = "wait"
            elif entry and bot.portfolio.balance < bot.entry_stake():
                text = f"{pair}: {rsi_text}, which is a buy, but cash is below the stake."
                kind = "wait"
            elif entry:
                text = (
                    f"{pair}: {rsi_text}, below {bot.strategy.rsi_entry:g}. "
                    + (
                        "The bot buys at the open of the next candle."
                        if running
                        else "Press Start and the bot can buy at the open of the next candle."
                    )
                )
                kind = "buy_next"
            else:
                text = (
                    f"{pair}: {rsi_text}. "
                    f"The bot buys when RSI goes below {bot.strategy.rsi_entry:g}."
                )
                kind = "wait"
        if holding is not None and not running and rsi_value is not None:
            text = (
                f"{pair} is open, bought at {_price(holding.entry_price)}. "
                "The bot is stopped, so it will not sell until you press Start."
            )
            kind = "holding"
        choices.append({"pair": pair, "rsi": rsi_value, "state": kind, "text": text})
    return choices


def _write_state(bot: Bot, state: dict, config: dict) -> None:
    portfolio = bot.portfolio
    payload = {
        "started_at": state["started_at"],
        "last_fill_time": state["last_fill_time"],
        "running": bool(state.get("running", True)),
        "starting_balance": portfolio.starting_balance,
        "balance": portfolio.balance,
        "open_trades": [_trade_out(trade) for trade in portfolio.open_trades],
        "closed_trades": [_trade_out(trade) for trade in portfolio.closed_trades],
        "events": [_event_out(event) for event in bot.events],
        "skips": dict(bot.skips),
        "cooldown_until": {pair: _clock(when) for pair, when in bot.cooldown_until.items()},
        "peak_equity": bot.peak_equity,
        "consecutive_losses": bot.consecutive_losses,
        "entries_blocked": bot.entries_blocked,
        "block_reason": bot.block_reason,
        "rules": {
            "rsi_entry": config["rsi_entry"],
            "rsi_exit": config["rsi_exit"],
            "stop_percent": abs(float(config["stoploss"])) * 100,
            "target_percent": float(config["minimal_roi"]) * 100,
            "stake_amount": config["stake_amount"],
            "max_open_trades": config["max_open_trades"],
        },
    }
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = STATE_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload), encoding="utf-8")
    temporary.replace(STATE_PATH)


def _read_state() -> dict | None:
    if not STATE_PATH.exists():
        return None
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        backup = STATE_PATH.with_suffix(".corrupt.json")
        try:
            STATE_PATH.replace(backup)
        except OSError:
            pass
        return None


def _trade(item: dict) -> Trade:
    return Trade(
        pair=item["pair"],
        entry_time=_parse(item["entry_time"]),
        entry_price=float(item["entry_price"]),
        amount=float(item["amount"]),
        stake=float(item["stake"]),
        fee_open=float(item["fee_open"]),
        high_water=float(item["high_water"]) if item.get("high_water") is not None else None,
        exit_time=_parse(item["exit_time"]) if item.get("exit_time") else None,
        exit_price=float(item["exit_price"]) if item.get("exit_price") is not None else None,
        fee_close=float(item.get("fee_close") or 0),
        exit_reason=item.get("exit_reason"),
        profit=float(item["profit"]) if item.get("profit") is not None else None,
    )


def _trade_out(trade: Trade) -> dict:
    return {
        "pair": trade.pair,
        "entry_time": _clock(trade.entry_time),
        "entry_price": trade.entry_price,
        "amount": trade.amount,
        "stake": trade.stake,
        "fee_open": trade.fee_open,
        "high_water": trade.high_water,
        "exit_time": _clock(trade.exit_time) if trade.exit_time else None,
        "exit_price": trade.exit_price,
        "fee_close": trade.fee_close,
        "exit_reason": trade.exit_reason,
        "profit": trade.profit,
    }


def _event(item: dict) -> dict:
    event = dict(item)
    event["time"] = _parse(item["time"])
    return event


def _event_out(event: dict) -> dict:
    item = dict(event)
    item["time"] = _clock(event["time"])
    return item


def _clock(when: datetime) -> str:
    return when.strftime("%Y-%m-%d %H:%M")


def _parse(stamp: str) -> datetime:
    return datetime.strptime(stamp, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)


def _price(value: float) -> str:
    return f"{value:.2f}" if value >= 100 else f"{value:.4f}"
