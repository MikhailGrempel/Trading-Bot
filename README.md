# Simple paper trading bot

A small spot bot you can read in one sitting. It follows the same idea as Freqtrade, and it never sends an order to an exchange.

Freqtrade is still the full project. This folder does not change it.

## Start

You need Python 3.10 or newer. There is nothing to install.

Open a terminal in this folder and run:

```text
python ui.py
```

Leave that window open. In a browser, go to:

```text
http://127.0.0.1:8765
```

The app has four pages: Dashboard, Trade, History, and Rules. Press Start to let the paper wallet buy and sell when a new 15-minute candle closes. Press Stop to pause. Coins already open stay open while it is stopped. On Rules, a change is saved when you leave the field. Nothing is sent to an exchange.

To print a text log instead of opening the page:

```text
python run.py
python run.py check
```

`check` runs the rule tests (fees, stop, target, one trade per pair, and so on). Change the numbers in `config.json` and run again.

To work on the pages, leave `python ui.py` running and in a second terminal run `cd web`, then `npm install` and `npm run dev`. That opens http://127.0.0.1:5173. After you change the pages, run `npm run build` in `web` so `python ui.py` serves the new UI.

Read the code in this order: `web/src` (the pages), `ui.py` (the server), `bot.py` (the loop), `strategy.py`, `portfolio.py`.

## How a trade happens

Each pair is a list of candles. A candle is open, high, low, close, and volume for 15 minutes.

On every new candle the bot does four things, in this order. The code is `bot.py`, method `run`.

1. It gives the strategy only candles that have already closed. The candle that just opened is hidden, so the strategy cannot peek at the future.
2. The strategy computes RSI plus an optional trend filter. By default it buys a pullback in an uptrend when RSI turns back up; RSI over 70 is a sell. That logic is `strategy.py`.
3. For each open trade it sells if one of these is true:
   - price fell through the stop (`stoploss`, for example -10%)
   - price rose through the target (`minimal_roi`, for example +2%)
   - RSI says sell
4. It buys only when all of these are true:
   - RSI says buy
   - the same candle does not also say sell
   - that pair is not already open
   - open trades are still under `max_open_trades`
   - the wallet still has `stake_amount` cash

The buy fills at the open of the new candle. The stop and the target are measured from that buy price.

Example, buy at 100:

- the candle falls to 80 and the stop is -10% → sell at 90, not at 80
- the candle rises to 130 and the target is +2% → sell at 102, not at 130
- the candle touches both → sell at 90

The fee (default 0.1%) is taken on the buy and again on the sell. A trade that is sold at the same price it was bought is a small loss, because both fees are paid.

Prices come from Kraken's public 15-minute candles (real trades). The bot still does not send an order. A stop or a target prints only when price actually reaches it.

## Where the money is

`portfolio.py` is the wallet.

- Buy: cash goes down by the stake. The fee is removed, and the rest buys the coin.
- Sell: coins are sold, the fee is removed, and the rest returns to cash.
- Profit = cash received - stake spent.

The ending equity is cash plus any coins still held.

## Map to Freqtrade

| This bot | Freqtrade |
| --- | --- |
| `strategy.prepare` | `populate_indicators` |
| `strategy.entry_reason` | `populate_entry_trend` |
| `strategy.exit_reason` | `populate_exit_trend` |
| `stoploss` | `stoploss` |
| `minimal_roi` | `minimal_roi` |
| `max_open_trades`, `stake_amount` | same config names |
| `dry_run_wallet` | dry-run wallet |
| `bot.run` | the loop inside `freqtrade trade` |

Freqtrade also does live orders, futures, leverage, pairlists, Telegram, and a web UI. Those are left out here on purpose.

## Change the rules

Edit `config.json`:

- `rsi_entry` / `rsi_exit`: when RSI buys and sells
- `trend_period` / `confirm_upturn`: uptrend filter and RSI recovery entry (`trend_period` 0 turns the filter off)
- `stoploss`: a negative number, such as `-0.10` for -10%
- `minimal_roi`: a positive number, such as `0.02` for +2%
- `trailing_stop`, `trailing_stop_positive`, `trailing_stop_positive_offset`: optional trailing stop after a profit threshold
- `stake_type`: `fixed` or `percent`; `stake_amount` is USD or percent of tradable balance
- `tradable_balance_ratio`, `min_stake`, `max_stake`: sizing limits
- `cooldown_candles`, `cooldown_after`: pause re-entry on a pair after an exit (`stop` or `any`)
- `max_consecutive_losses`, `max_drawdown`: portfolio circuit breakers (0 disables)
- `max_open_trades`: how many positions can be open at once
- `fee`: fraction taken on each order (`0.001` is 0.1%)
- `slippage`: fraction worse on each fill (`0.0005` is 0.05% on buy and sell)

To use a different signal, copy `RsiStrategy` in `strategy.py` and change `entry_reason` and `exit_reason`. Keep the stop and the target on the strategy. The bot will apply them.

This is a learning tool. The candles are real Kraken trades. A profit on this replay is not a prediction of the next trade.
