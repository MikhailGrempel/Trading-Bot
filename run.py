"""Run the paper bot in the terminal.

    python run.py
    python run.py check

For the browser page, use python ui.py instead.
This replays real Kraken 15-minute candles. It does not send an order.
"""

from __future__ import annotations

import sys
from pathlib import Path

from checks import run_checks
from report import render
from session import execute, load_config

ROOT = Path(__file__).resolve().parent


def main() -> None:
    command = sys.argv[1] if len(sys.argv) > 1 else "backtest"
    if command == "check":
        run_checks()
        return
    if command != "backtest":
        print("Usage: python run.py [backtest|check]")
        raise SystemExit(1)

    try:
        config = load_config(ROOT / "config.json")
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    bot, data = execute(config)

    print("Simple paper bot")
    print("No real order is sent. Prices are Kraken's public 15-minute candles.")
    print(
        f"Rules: buy when RSI < {config['rsi_entry']}, "
        f"sell when RSI > {config['rsi_exit']}, "
        f"stop {config['stoploss'] * 100:.1f}%, "
        f"target {config['minimal_roi'] * 100:.1f}%"
    )
    print(
        f"Wallet {config['dry_run_wallet']:.0f} {config['stake_currency']}, "
        f"stake {config['stake_amount']:.0f}, "
        f"max open trades {config['max_open_trades']}, "
        f"fee {config['fee'] * 100:.2f}% per order, "
        f"slippage {float(config.get('slippage', 0)) * 100:.3f}% each fill"
    )
    stake_type = config.get("stake_type", "fixed")
    if stake_type == "percent":
        print(
            f"Stake {config['stake_amount']:.1f}% of tradable balance "
            f"(min {config.get('min_stake', 0)}, max {config.get('max_stake', '—')})"
        )
    print(f"Pairs: {', '.join(config['pairs'])}")
    stop_price = 100 * (1 + config["stoploss"])
    target_price = 100 * (1 + config["minimal_roi"])
    print()
    print("How a sell price is chosen after a buy at 100:")
    print(f"  price falls through {stop_price:.0f} -> sell at {stop_price:.0f} (stop)")
    print(f"  price rises through {target_price:.0f} -> sell at {target_price:.0f} (target)")
    print("  if one candle hits both, the stop is used")
    print("  if RSI says sell, the bot sells at the next candle's open")
    print("  the fee is charged on the buy and again on the sell")
    if float(config.get("slippage", 0)) > 0:
        print("  slippage makes buys slightly worse and sells slightly worse than the candle price")
    print()

    print(render(bot, data, config["stake_currency"]))
    print()
    print("What the loop did on every new candle")
    print("1. Read candles that were already closed.")
    print("2. Compute RSI from those closes.")
    print("3. Sell an open trade if the stop, the target, or RSI said so.")
    print("4. Buy a pair if RSI said so, the pair was flat, a slot was free, and cash was enough.")


if __name__ == "__main__":
    main()
