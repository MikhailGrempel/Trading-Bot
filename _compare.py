"""Fair before/after backtest on ONE identical set of candles.

Downloads the market once, then replays several strategy variants over
exactly the same candles so the only difference is the strategy itself.
"""

from __future__ import annotations

from market import load_market
from session import bot_from_config, load_config, strategy_from_config
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def run_variant(data, cfg, overrides: dict | None = None):
    run_cfg = dict(cfg)
    if overrides:
        run_cfg.update(overrides)
    strategy = strategy_from_config(run_cfg)
    bot = bot_from_config(run_cfg, strategy)
    bot.run(data)
    closed = bot.portfolio.closed_trades
    last = {p: c[-1].close for p, c in data.items()}
    equity = bot.portfolio.equity(last)
    profit = equity - bot.portfolio.starting_balance
    wins = sum(1 for t in closed if (t.profit or 0) > 0)
    n = len(closed)
    gross_win = sum(t.profit for t in closed if (t.profit or 0) > 0)
    gross_loss = -sum(t.profit for t in closed if (t.profit or 0) <= 0)
    pf = (gross_win / gross_loss) if gross_loss > 0 else float("inf")
    return {
        "profit": profit,
        "pct": profit / bot.portfolio.starting_balance * 100,
        "trades": n,
        "wins": wins,
        "winrate": (wins / n * 100) if n else 0.0,
        "open": len(bot.portfolio.open_trades),
        "pf": pf,
    }


def main():
    cfg = load_config(ROOT / "config.json")
    data = load_market(list(cfg["pairs"]), count=int(cfg["candles"]))
    rng_start = next(iter(data.values()))[0].time
    rng_end = next(iter(data.values()))[-1].time
    print(f"Data: {cfg['pairs']}  candles={len(next(iter(data.values())))}")
    print(f"Range: {rng_start:%Y-%m-%d %H:%M} -> {rng_end:%Y-%m-%d %H:%M} UTC")
    print(f"Wallet {cfg['dry_run_wallet']}  stake {cfg['stake_amount']}  "
          f"max_open {cfg['max_open_trades']}  fee {cfg['fee']*100:.2f}%")
    print()

    variants = [
        (
            "BEFORE  fixed stake, no cooldown",
            {
                "stake_type": "fixed",
                "stake_amount": 30,
                "tradable_balance_ratio": 1.0,
                "cooldown_candles": 0,
            },
        ),
        ("AFTER   percent stake + cooldown (shipped)", {}),
    ]

    header = f"{'Variant':<44} {'P/L%':>8} {'Trades':>7} {'Win%':>7} {'PF':>6}"
    print(header)
    print("-" * len(header))
    for name, overrides in variants:
        r = run_variant(data, cfg, overrides or None)
        pf = "inf" if r["pf"] == float("inf") else f"{r['pf']:.2f}"
        print(f"{name:<44} {r['pct']:>+7.2f}% {r['trades']:>7} "
              f"{r['winrate']:>6.0f}% {pf:>6}")


if __name__ == "__main__":
    main()
