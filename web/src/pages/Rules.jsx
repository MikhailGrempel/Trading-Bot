import { useEffect, useRef, useState } from "react"
import { useBot } from "../context/BotContext"
import { money, rulesDraft, sameRules } from "../format"

const FIELDS = [
  { name: "rsi_entry", label: "RSI buy below", min: 1, max: 98, step: "any" },
  { name: "rsi_exit", label: "RSI sell above", min: 2, max: 99, step: "any" },
  { name: "stop_percent", label: "Stop, percent below the buy", min: 0.1, max: 50, step: "any" },
  { name: "target_percent", label: "Target, percent above the buy", min: 0.1, max: 50, step: "any" },
  { name: "stake_amount", label: "Stake per buy, USD", min: 1, max: 1000, step: "any" },
  { name: "max_open_trades", label: "Max open trades", min: 1, max: 10, step: 1 },
]

export function Rules() {
  const { payload, saveRules } = useBot()
  const [draft, setDraft] = useState(() => rulesDraft(payload.rules))
  const [dirty, setDirty] = useState(false)
  const [hint, setHint] = useState("")
  const draftRef = useRef(draft)
  draftRef.current = draft

  useEffect(() => {
    if (dirty) return
    const next = rulesDraft(payload.rules)
    draftRef.current = next
    setDraft(next)
  }, [payload, dirty])

  function onChange(event) {
    const next = { ...draftRef.current, [event.target.name]: event.target.value }
    draftRef.current = next
    setDraft(next)
    setDirty(true)
    setHint("")
  }

  async function onBlur(event) {
    if (!event.target.name) return
    const next = { ...draftRef.current, [event.target.name]: event.target.value }
    draftRef.current = next
    setDraft(next)
    if (sameRules(next, payload.rules)) {
      setDirty(false)
      return
    }
    setHint("Saving…")
    const ok = await saveRules(next)
    if (ok) {
      setDirty(false)
      setHint("Saved.")
    } else {
      setHint("Could not save.")
    }
  }

  const { rules, currency } = payload

  return (
    <div className="rules-layout">
      <section className="panel">
        <h2>Strategy</h2>
        <form>
          {FIELDS.map((field) => (
            <label key={field.name}>
              {field.label}
              <input
                name={field.name}
                type="number"
                min={field.min}
                max={field.max}
                step={field.step}
                value={draft[field.name]}
                onChange={onChange}
                onBlur={onBlur}
              />
            </label>
          ))}
          <p className="hint">{hint || "Leave a field to save it."}</p>
        </form>
        <p className="muted">
          Paper wallet {money(rules.wallet)} {currency}. Fee {rules.fee_percent.toFixed(2)}% on the buy and again on the sell.
          The fee and the starting wallet stay in config.json.
        </p>
      </section>
      <div className="stack">
        <section className="panel">
          <h2>Each new candle</h2>
          <ol className="steps">
            <li>Wait until the current 15-minute candle closes.</li>
            <li>Read RSI from the candle that just closed.</li>
            <li>Sell an open coin if the stop, the target, or RSI says so.</li>
            <li>Buy if RSI says so, the pair is flat, a slot is free, and cash covers the stake.</li>
          </ol>
        </section>
        <section className="panel">
          <h2>How a fill is priced</h2>
          <p>
            The buy fills at the open of the new candle. The stop and the target are measured from that buy price.
            If the candle touches both, the stop wins.
          </p>
          <p className="muted">
            Example, buy at 100 with a 10% stop and a 2% target: a low of 80 sells at 90, a high of 130 sells at 102,
            and a candle that touches both sells at 90. Both fees are paid, so a round trip at the same price is a small loss.
          </p>
          <p className="muted">
            Prices are Kraken's public 15-minute candles. Nothing is sent to an exchange.
            Watching since {payload.live.started_at} UTC. Candles in view run from {payload.range.start} to {payload.range.end} UTC.
          </p>
        </section>
      </div>
    </div>
  )
}
