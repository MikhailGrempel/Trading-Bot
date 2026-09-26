export const REASON_LABELS = {
  rsi_oversold: "RSI oversold",
  rsi_overbought: "RSI overbought",
  stoploss: "Stop",
  roi: "Target",
}

export const STATE_LABELS = {
  wait: "Waiting",
  holding: "Open",
  buy_next: "Buy next",
}

export function reasonLabel(reason) {
  if (!reason) return ""
  return REASON_LABELS[reason] || reason
}

export function money(value) {
  const number = Number(value)
  if (!Number.isFinite(number)) return "—"
  return number.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

export function signedMoney(value) {
  const number = Number(value)
  if (!Number.isFinite(number)) return "—"
  const body = Math.abs(number).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  if (number > 0) return `+${body}`
  if (number < 0) return `-${body}`
  return body
}

export function signedPct(value) {
  const number = Number(value) * 100
  if (!Number.isFinite(number)) return "—"
  const body = Math.abs(number).toFixed(2)
  if (number > 0) return `+${body}%`
  if (number < 0) return `-${body}%`
  return `${body}%`
}

export function price(value) {
  const number = Number(value)
  if (!Number.isFinite(number)) return "—"
  const digits = number >= 100 ? 2 : 4
  return number.toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits })
}

export function tone(value) {
  const number = Number(value)
  if (number < 0) return "down"
  if (number > 0) return "up"
  return ""
}

export function winRate(summary) {
  if (!summary.closed) return "—"
  return `${((summary.wins / summary.closed) * 100).toFixed(1)}%`
}

export function rulesDraft(rules) {
  return {
    rsi_entry: String(rules.rsi_entry),
    rsi_exit: String(rules.rsi_exit),
    stop_percent: String(rules.stop_percent),
    target_percent: String(rules.target_percent),
    stake_amount: String(rules.stake_amount),
    max_open_trades: String(rules.max_open_trades),
  }
}

export function sameRules(draft, rules) {
  const current = rulesDraft(rules)
  return Object.keys(current).every((key) => String(draft[key]) === current[key])
}
