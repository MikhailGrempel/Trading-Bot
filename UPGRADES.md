# Strategy and engine upgrades (dev branch)

This document summarizes improvements beyond the original RSI-only bot.

## Strategy (`strategy.py`)

- **Trend filter** (`trend_period`): only buy when price is above its moving average.
- **RSI recovery** (`confirm_upturn`): wait for RSI to turn back up through the entry level instead of buying straight into a fall.
- **Trailing stop** (`trailing_stop`, `trailing_stop_positive`, `trailing_stop_positive_offset`): lock in profit as price rises.

## Risk and sizing (`bot.py`, `config.json`)

- **Percent stake** (`stake_type`, `tradable_balance_ratio`, `min_stake`, `max_stake`).
- **Cooldown** after an exit on a pair (`cooldown_candles`, `cooldown_after`).
- **Circuit breakers**: `max_consecutive_losses`, `max_drawdown` (new entries paused; open trades still exit). Press **Start** in the live UI to reset.

## Realism

- **Slippage** (`slippage`): buys fill slightly above the candle price, sells slightly below; applied in `portfolio.py` and in equity marks.
- **Fees** unchanged: still charged on both sides.

## Tests

Run `python run.py check` — rule tests cover fees, stops, trailing stop logic helpers, cooldown, sizing, slippage, and circuit breakers.

## UI

Dashboard shows slippage and circuit status when using `python ui.py`. After editing `web/src`, run `npm run build` in `web/` so the built app in `web/dist/` updates.
