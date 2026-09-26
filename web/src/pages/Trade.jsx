import { useEffect, useState } from "react"
import { PriceChart } from "../components/Chart"
import { PositionDetail, PositionList } from "../components/Positions"
import { useBot } from "../context/BotContext"

const PAIR_KEY = "paper-pair"

export function Trade() {
  const { payload } = useBot()
  const pairs = Object.keys(payload.pairs)
  const [stored, setStored] = useState(() => {
    try {
      return sessionStorage.getItem(PAIR_KEY) || ""
    } catch {
      return ""
    }
  })
  const selected = pairs.includes(stored) ? stored : pairs[0]

  useEffect(() => {
    if (!selected) return
    try {
      sessionStorage.setItem(PAIR_KEY, selected)
    } catch {
      /* the chart still works if storage is blocked */
    }
  }, [selected])

  function choose(pair) {
    setStored(pair)
  }

  const series = payload.pairs[selected]

  return (
    <>
      <PositionList payload={payload} selected={selected} onSelect={choose} />
      <div className="trade-layout">
        <PriceChart
          series={series}
          pair={selected}
          markers={payload.markers}
          openTrades={payload.open_trades}
          rules={payload.rules}
          startedAt={payload.live.started_at}
        />
        <PositionDetail payload={payload} pair={selected} />
      </div>
    </>
  )
}
