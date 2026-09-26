import { money, price, signedMoney, signedPct, STATE_LABELS, tone } from "../format"

export function PositionList({ payload, selected, onSelect }) {
  const byPair = {}
  for (const trade of payload.open_trades) byPair[trade.pair] = trade
  const decisions = payload.live?.decisions || []

  return (
    <div className="book">
      {Object.keys(payload.pairs).map((pair) => {
        const series = payload.pairs[pair]
        const last = series.close[series.close.length - 1]
        const trade = byPair[pair]
        const choice = decisions.find((item) => item.pair === pair)
        const active = pair === selected
        const className = [
          "book-card",
          active ? "selected" : "",
          trade ? "open" : "",
          trade ? tone(trade.unrealized) : "",
        ].filter(Boolean).join(" ")
        const body = (
          <>
            <span className="book-top">
              <strong>{pair}</strong>
              <em className={`state ${choice?.state || "wait"}`}>{STATE_LABELS[choice?.state] || "Waiting"}</em>
            </span>
            <span className="book-price">{price(trade ? trade.last_price : last)}</span>
            {trade ? (
              <span className={tone(trade.unrealized)}>
                {signedMoney(trade.unrealized)} {payload.currency} ({signedPct(trade.unrealized_pct)})
              </span>
            ) : (
              <span className="muted">Flat · stake {money(payload.rules.stake_amount)}</span>
            )}
          </>
        )
        if (!onSelect) {
          return (
            <div key={pair} className={className}>
              {body}
            </div>
          )
        }
        return (
          <button key={pair} type="button" className={className} aria-pressed={active} onClick={() => onSelect(pair)}>
            {body}
          </button>
        )
      })}
    </div>
  )
}

export function PositionDetail({ payload, pair }) {
  const trade = payload.open_trades.find((item) => item.pair === pair)
  const choice = (payload.live?.decisions || []).find((item) => item.pair === pair)
  const series = payload.pairs[pair]
  const last = series.close[series.close.length - 1]
  const rsi = choice?.rsi

  return (
    <section className="panel detail">
      <h2>{pair}</h2>
      <dl>
        <div>
          <dt>Last</dt>
          <dd>{price(last)} {payload.currency}</dd>
        </div>
        <div>
          <dt>RSI</dt>
          <dd>{rsi == null ? "—" : Number(rsi).toFixed(1)}</dd>
        </div>
        <div>
          <dt>Signal</dt>
          <dd>{choice ? STATE_LABELS[choice.state] || choice.state : "—"}</dd>
        </div>
      </dl>
      {trade ? (
        <dl className="detail-trade">
          <div>
            <dt>Bought</dt>
            <dd>{trade.entry_time} UTC at {price(trade.entry_price)}</dd>
          </div>
          <div>
            <dt>Unrealized</dt>
            <dd className={tone(trade.unrealized)}>
              {signedMoney(trade.unrealized)} {payload.currency} ({signedPct(trade.unrealized_pct)})
            </dd>
          </div>
          <div>
            <dt>Stop</dt>
            <dd>{price(trade.stop_price)}</dd>
          </div>
          <div>
            <dt>Target</dt>
            <dd>{price(trade.target_price)}</dd>
          </div>
          <div>
            <dt>Stake</dt>
            <dd>{money(trade.stake)} {payload.currency}</dd>
          </div>
        </dl>
      ) : (
        <p className="muted">No open trade on this pair.</p>
      )}
      {choice ? <p className="decision">{choice.text}</p> : null}
    </section>
  )
}
