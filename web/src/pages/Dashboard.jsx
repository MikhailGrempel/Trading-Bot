import { Link } from "react-router-dom"
import { PositionList } from "../components/Positions"
import { useBot } from "../context/BotContext"
import { money, price, reasonLabel, signedMoney, signedPct, STATE_LABELS, tone, winRate } from "../format"

export function Dashboard() {
  const { payload } = useBot()
  const { summary, rules, currency, live } = payload
  const unrealized = payload.open_trades.reduce((sum, trade) => sum + trade.unrealized, 0)
  const recent = [...payload.trades].reverse().slice(0, 6)
  const activity = [...payload.markers].reverse().slice(0, 8)

  return (
    <>
      <section className="stats">
        <Stat label="Equity" value={`${money(summary.equity)} ${currency}`} hint={`Started ${money(summary.starting_balance)}`} />
        <Stat
          label="Profit"
          value={`${signedMoney(summary.profit)} ${currency}`}
          hint={signedPct(summary.profit_pct)}
          tone={tone(summary.profit)}
        />
        <Stat
          label="Win rate"
          value={winRate(summary)}
          hint={`${summary.closed} closed · ${summary.wins} wins · ${summary.losses} losses`}
        />
        <Stat
          label="Open"
          value={String(summary.open)}
          hint={summary.open ? `${signedMoney(unrealized)} ${currency} unrealized` : `Max ${rules.max_open_trades}`}
          tone={summary.open ? tone(unrealized) : ""}
        />
      </section>

      <div className="split">
        <section className="panel">
          <div className="panel-head">
            <h2>Open book</h2>
            <Link to="/trade">Chart</Link>
          </div>
          <PositionList payload={payload} />
        </section>
        <section className="panel">
          <h2>Session</h2>
          <dl className="facts">
            <div>
              <dt>State</dt>
              <dd>{live.running ? "Running" : "Stopped"}</dd>
            </div>
            <div>
              <dt>Watching since</dt>
              <dd>{live.started_at} UTC</dd>
            </div>
            <div>
              <dt>Latest candle</dt>
              <dd>{live.last_candle} UTC</dd>
            </div>
            <div>
              <dt>Next check</dt>
              <dd>{live.next_check} UTC</dd>
            </div>
            <div>
              <dt>Wallet</dt>
              <dd>{money(rules.wallet)} {currency}</dd>
            </div>
            <div>
              <dt>Fee</dt>
              <dd>{rules.fee_percent.toFixed(2)}% each side</dd>
            </div>
          </dl>
          <p className="muted">{live.status}</p>
        </section>
      </div>

      <div className="split">
        <section className="panel">
          <h2>By pair</h2>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Pair</th>
                  <th className="num">Closed</th>
                  <th className="num">Wins</th>
                  <th className="num">Closed profit</th>
                  <th className="num">Unrealized</th>
                </tr>
              </thead>
              <tbody>
                {pairRows(payload).map((row) => (
                  <tr key={row.pair}>
                    <td>{row.pair}</td>
                    <td className="num">{row.closed}</td>
                    <td className="num">{row.wins}</td>
                    <td className={`num ${tone(row.profit)}`}>{signedMoney(row.profit)}</td>
                    <td className={`num ${tone(row.unrealized)}`}>{row.open ? signedMoney(row.unrealized) : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
        <div className="stack">
          <section className="panel">
            <h2>Why it sold</h2>
            {payload.exit_reasons.length ? (
              <ReasonBars rows={payload.exit_reasons} />
            ) : (
              <p className="muted">No closed trades yet.</p>
            )}
          </section>
          <section className="panel">
            <h2>Signals that did not trade</h2>
            {payload.skips.length ? (
              <ul className="plain">
                {payload.skips.map((skip) => (
                  <li key={skip.label}>{skip.count} · {skip.label}</li>
                ))}
              </ul>
            ) : (
              <p className="muted">None yet.</p>
            )}
          </section>
        </div>
      </div>

      <div className="split">
        <section className="panel">
          <div className="panel-head">
            <h2>Recent closes</h2>
            <Link to="/history">All trades</Link>
          </div>
          {recent.length ? (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Sold</th>
                    <th>Pair</th>
                    <th className="num">Profit</th>
                    <th>Why</th>
                  </tr>
                </thead>
                <tbody>
                  {recent.map((trade) => (
                    <tr key={`${trade.pair}-${trade.entry_time}`}>
                      <td>{trade.exit_time}</td>
                      <td>{trade.pair}</td>
                      <td className={`num ${tone(trade.profit)}`}>
                        {signedMoney(trade.profit)} ({signedPct(trade.profit_pct)})
                      </td>
                      <td>{trade.reason_label}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="muted">No closed trades yet. A row appears here when the bot sells.</p>
          )}
        </section>
        <section className="panel">
          <h2>Fills</h2>
          {activity.length ? (
            <ul className="feed">
              {activity.map((mark) => {
                const buy = mark.action === "ENTER"
                return (
                  <li key={`${mark.pair}-${mark.time}-${mark.action}`}>
                    <span className={buy ? "up" : "down"}>{buy ? "Buy" : "Sell"}</span>
                    <span>{mark.pair}</span>
                    <span className="num">{price(mark.price)}</span>
                    <span className="muted">{mark.time}</span>
                    <span className="muted">{reasonLabel(mark.reason)}</span>
                  </li>
                )
              })}
            </ul>
          ) : (
            <p className="muted">No fills yet. Triangles show on the Trade chart after the bot acts.</p>
          )}
        </section>
      </div>

      <section className="panel">
        <h2>Right now</h2>
        <ul className="signals">
          {(live.decisions || []).map((choice) => (
            <li key={choice.pair}>
              <span className={`state ${choice.state}`}>{STATE_LABELS[choice.state] || choice.state}</span>
              <span>{choice.text}</span>
            </li>
          ))}
        </ul>
        {payload.notes.filter((note) => !(live.decisions || []).some((choice) => choice.text === note)).map((note) => (
          <p key={note} className="muted">{note}</p>
        ))}
      </section>
    </>
  )
}

function Stat({ label, value, hint, tone: toneClass }) {
  return (
    <article className="stat">
      <span>{label}</span>
      <strong className={toneClass || ""}>{value}</strong>
      {hint ? <em>{hint}</em> : null}
    </article>
  )
}

function ReasonBars({ rows }) {
  const max = Math.max(...rows.map((row) => row.count), 1)
  return (
    <ul className="bars">
      {rows.map((row) => (
        <li key={row.reason}>
          <span>{row.label}</span>
          <span className="track"><span style={{ width: `${(row.count / max) * 100}%` }} /></span>
          <span className="num">{row.count}</span>
        </li>
      ))}
    </ul>
  )
}

function pairRows(payload) {
  const rows = {}
  for (const pair of Object.keys(payload.pairs)) {
    rows[pair] = { pair, closed: 0, wins: 0, profit: 0, unrealized: 0, open: false }
  }
  for (const trade of payload.trades) {
    const row = rows[trade.pair]
    if (!row) continue
    row.closed += 1
    row.profit += Number(trade.profit) || 0
    if (trade.profit > 0) row.wins += 1
  }
  for (const trade of payload.open_trades) {
    const row = rows[trade.pair]
    if (!row) continue
    row.unrealized += Number(trade.unrealized) || 0
    row.open = true
  }
  return Object.values(rows)
}
