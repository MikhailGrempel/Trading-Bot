import { useMemo, useState } from "react"
import { useBot } from "../context/BotContext"
import { money, price, signedMoney, signedPct, tone } from "../format"

export function History() {
  const { payload } = useBot()
  const [pair, setPair] = useState("")
  const [result, setResult] = useState("")
  const [reason, setReason] = useState("")

  const reasons = useMemo(() => {
    const seen = new Map()
    for (const trade of payload.trades) {
      if (trade.reason) seen.set(trade.reason, trade.reason_label || trade.reason)
    }
    return [...seen.entries()]
  }, [payload.trades])

  const closed = payload.trades.filter((trade) => {
    if (pair && trade.pair !== pair) return false
    if (result === "win" && !(trade.profit > 0)) return false
    if (result === "loss" && !(trade.profit < 0)) return false
    if (reason && trade.reason !== reason) return false
    return true
  }).reverse()

  const open = payload.open_trades.filter((trade) => !pair || trade.pair === pair)
  const net = closed.reduce((sum, trade) => sum + Number(trade.profit || 0), 0)
  const wins = closed.filter((trade) => trade.profit > 0).length

  return (
    <>
      <section className="panel filters">
        <label>
          Pair
          <select value={pair} onChange={(event) => setPair(event.target.value)}>
            <option value="">All pairs</option>
            {Object.keys(payload.pairs).map((name) => (
              <option key={name} value={name}>{name}</option>
            ))}
          </select>
        </label>
        <label>
          Result
          <select value={result} onChange={(event) => setResult(event.target.value)}>
            <option value="">All results</option>
            <option value="win">Wins</option>
            <option value="loss">Losses</option>
          </select>
        </label>
        <label>
          Exit
          <select value={reason} onChange={(event) => setReason(event.target.value)}>
            <option value="">All reasons</option>
            {reasons.map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
        </label>
        <div className="filter-sum">
          <span>{closed.length} closed</span>
          <span>{wins} wins</span>
          <span className={tone(net)}>{signedMoney(net)} {payload.currency}</span>
        </div>
      </section>

      <section className="panel">
        <h2>Closed</h2>
        {closed.length ? (
          <div className="table-wrap">
            <table className="ledger">
              <thead>
                <tr>
                  <th>Bought</th>
                  <th>Pair</th>
                  <th className="num">Buy</th>
                  <th>Sold</th>
                  <th className="num">Sell</th>
                  <th className="num">Stake</th>
                  <th className="num">Profit</th>
                  <th>Why it sold</th>
                </tr>
              </thead>
              <tbody>
                {closed.map((trade) => (
                  <tr key={`${trade.pair}-${trade.entry_time}`}>
                    <td>{trade.entry_time}</td>
                    <td>{trade.pair}</td>
                    <td className="num">{price(trade.entry_price)}</td>
                    <td>{trade.exit_time}</td>
                    <td className="num">{price(trade.exit_price)}</td>
                    <td className="num">{money(trade.stake)}</td>
                    <td className={`num ${tone(trade.profit)}`}>
                      {signedMoney(trade.profit)} ({signedPct(trade.profit_pct)})
                    </td>
                    <td>
                      {trade.reason_label}
                      {trade.exit_rsi == null ? "" : ` (RSI ${Number(trade.exit_rsi).toFixed(1)})`}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="muted">No closed trades match this filter.</p>
        )}
      </section>

      <section className="panel">
        <h2>Still open</h2>
        {open.length ? (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Bought</th>
                  <th>Pair</th>
                  <th className="num">Buy</th>
                  <th className="num">Now</th>
                  <th className="num">Stop</th>
                  <th className="num">Target</th>
                  <th className="num">Stake</th>
                  <th className="num">Unrealized</th>
                </tr>
              </thead>
              <tbody>
                {open.map((trade) => (
                  <tr key={`${trade.pair}-${trade.entry_time}`}>
                    <td>{trade.entry_time}</td>
                    <td>{trade.pair}</td>
                    <td className="num">{price(trade.entry_price)}</td>
                    <td className="num">{price(trade.last_price)}</td>
                    <td className="num">{price(trade.stop_price)}</td>
                    <td className="num">{price(trade.target_price)}</td>
                    <td className="num">{money(trade.stake)}</td>
                    <td className={`num ${tone(trade.unrealized)}`}>
                      {signedMoney(trade.unrealized)} ({signedPct(trade.unrealized_pct)})
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="muted">No open trades{pair ? ` on ${pair}` : ""}.</p>
        )}
      </section>
    </>
  )
}
