import { useEffect, useRef, useState } from "react"
import { BarChart, CandlestickChart, LineChart } from "echarts/charts"
import {
  AxisPointerComponent,
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  MarkLineComponent,
  MarkPointComponent,
  TooltipComponent,
} from "echarts/components"
import * as echarts from "echarts/core"
import { CanvasRenderer } from "echarts/renderers"
import { price } from "../format"

echarts.use([
  CandlestickChart,
  BarChart,
  LineChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  DataZoomComponent,
  MarkLineComponent,
  MarkPointComponent,
  AxisPointerComponent,
  CanvasRenderer,
])

const RANGES = [
  { span: 48, label: "12 hours" },
  { span: 96, label: "1 day" },
  { span: 288, label: "3 days" },
  { span: 672, label: "1 week" },
  { span: 0, label: "All" },
]

const UP = "#3dd68c"
const DOWN = "#ff6b81"
const AXIS = "#93a0b5"
const LINE = "#263044"
const INK = "#e7edf6"

export function PriceChart({ series, pair, markers, openTrades, rules, startedAt }) {
  const elRef = useRef(null)
  const chartRef = useRef(null)
  const zoomRef = useRef(null)
  const programmedRef = useRef(null)
  const customRef = useRef(false)
  const dataRef = useRef({})
  const [span, setSpan] = useState(288)
  const [custom, setCustom] = useState(false)
  const [caption, setCaption] = useState("")

  dataRef.current = { series, pair, markers, openTrades, rules, startedAt, span }

  useEffect(() => {
    const chart = echarts.init(elRef.current)
    chartRef.current = chart
    const onZoom = (event) => {
      const change = event.batch && event.batch[0] ? event.batch[0] : event
      if (change.start == null || change.end == null) return
      const programmed = programmedRef.current
      const same = programmed
        && Math.abs(change.start - programmed.start) < 0.05
        && Math.abs(change.end - programmed.end) < 0.05
      zoomRef.current = { start: change.start, end: change.end }
      if (!same) {
        programmedRef.current = null
        customRef.current = true
        setCustom(true)
      }
      setCaption(captionFor(dataRef.current, zoomRef.current))
    }
    chart.on("datazoom", onZoom)
    const observer = new ResizeObserver(() => chart.resize())
    observer.observe(elRef.current)
    return () => {
      observer.disconnect()
      chart.dispose()
      chartRef.current = null
    }
  }, [])

  useEffect(() => {
    customRef.current = false
    zoomRef.current = null
    setCustom(false)
  }, [pair])

  useEffect(() => {
    const chart = chartRef.current
    if (!chart || !series?.close?.length) return
    const view = viewFor(series.close.length, span, customRef.current, zoomRef.current)
    zoomRef.current = view
    programmedRef.current = view
    chart.setOption(optionFor(dataRef.current, view), true)
    chart.resize()
    setCaption(captionFor(dataRef.current, view))
  }, [series, pair, markers, openTrades, rules, span])

  function pickSpan(next) {
    customRef.current = false
    zoomRef.current = null
    setCustom(false)
    setSpan(next)
    if (next === span) {
      const chart = chartRef.current
      if (!chart || !series?.close?.length) return
      const view = viewFor(series.close.length, next, false, null)
      zoomRef.current = view
      programmedRef.current = view
      chart.setOption(optionFor(dataRef.current, view), true)
      setCaption(captionFor(dataRef.current, view))
    }
  }

  return (
    <section className="panel chart-panel">
      <div className="panel-head">
        <h2>Price</h2>
        <div className="seg" role="group" aria-label="Time range">
          {RANGES.map((range) => {
            const pressed = !custom && span === range.span
            return (
              <button
                key={range.label}
                type="button"
                aria-pressed={pressed}
                onClick={() => pickSpan(range.span)}
              >
                {range.label}
              </button>
            )
          })}
        </div>
      </div>
      <div ref={elRef} className="chart" role="img" aria-label={`Candlestick chart for ${pair}`} />
      <p className="caption">{caption}</p>
    </section>
  )
}

function viewFor(total, span, custom, zoom) {
  if (custom && zoom) return zoom
  if (!span || span >= total) return { start: 0, end: 100 }
  return { start: Math.max(0, (1 - span / total) * 100), end: 100 }
}

function captionFor(data, view) {
  const { series, pair, startedAt } = data
  if (!series?.time?.length) return ""
  const total = series.time.length
  const from = Math.max(0, Math.min(total - 1, Math.round((view.start / 100) * (total - 1))))
  const to = Math.max(from, Math.min(total - 1, Math.round((view.end / 100) * (total - 1))))
  return `${pair} from ${series.time[from]} to ${series.time[to]} UTC. Triangles are buys and sells after ${startedAt} UTC. Scroll to zoom. Drag the candles to move.`
}

function optionFor(data, view) {
  const { series, pair, markers, openTrades, rules } = data
  const candles = series.open.map((open, index) => [
    open,
    series.close[index],
    series.low[index],
    series.high[index],
  ])
  const volume = series.volume.map((value, index) => ({
    value,
    itemStyle: { color: series.close[index] >= series.open[index] ? UP : DOWN },
  }))
  const markPoint = (markers || [])
    .filter((mark) => mark.pair === pair && series.time.includes(mark.time))
    .map((mark) => {
      const buy = mark.action === "ENTER"
      return {
        name: buy ? "Buy" : "Sell",
        coord: [mark.time, mark.price],
        symbol: "triangle",
        symbolSize: 12,
        symbolRotate: buy ? 0 : 180,
        symbolOffset: buy ? [0, 14] : [0, -14],
        itemStyle: { color: buy ? UP : DOWN },
        label: { show: false },
      }
    })
  const lastClose = series.close[series.close.length - 1]
  const lastColor = lastClose >= series.open[series.open.length - 1] ? UP : DOWN
  const markLine = [
    {
      yAxis: lastClose,
      lineStyle: { color: lastColor, type: "dotted" },
      label: {
        formatter: price(lastClose),
        color: "#062116",
        backgroundColor: lastColor,
        padding: [2, 4],
        borderRadius: 2,
      },
    },
  ]
  for (const trade of openTrades || []) {
    if (trade.pair !== pair) continue
    markLine.push(
      { yAxis: trade.entry_price, lineStyle: { color: UP, type: "dashed" }, label: { formatter: `Entry ${price(trade.entry_price)}`, color: AXIS } },
      { yAxis: trade.stop_price, lineStyle: { color: DOWN, type: "dashed" }, label: { formatter: `Stop ${price(trade.stop_price)}`, color: AXIS } },
      { yAxis: trade.target_price, lineStyle: { color: "#8eb6ff", type: "dashed" }, label: { formatter: `Target ${price(trade.target_price)}`, color: AXIS } },
    )
  }

  return {
    animation: false,
    backgroundColor: "transparent",
    textStyle: { color: AXIS, fontFamily: "Segoe UI, sans-serif" },
    legend: { top: 0, data: ["Price", "Volume", "RSI"], textStyle: { color: AXIS } },
    axisPointer: { link: [{ xAxisIndex: "all" }] },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "cross" },
      backgroundColor: "#1a2130",
      borderColor: LINE,
      textStyle: { color: INK },
      formatter: (items) => {
        const time = items[0].axisValue
        const lines = [time]
        const candle = items.find((item) => item.seriesName === "Price")
        if (candle && Array.isArray(candle.data)) {
          const values = candle.data.length >= 5 ? candle.data.slice(1) : candle.data
          lines.push(`Open ${price(values[0])}`)
          lines.push(`High ${price(values[3])}`)
          lines.push(`Low ${price(values[2])}`)
          lines.push(`Close ${price(values[1])}`)
        }
        const bar = items.find((item) => item.seriesName === "Volume")
        if (bar) {
          const amount = bar.data && bar.data.value != null ? bar.data.value : bar.value
          lines.push(`Volume ${Number(amount).toFixed(2)}`)
        }
        const rsi = items.find((item) => item.seriesName === "RSI")
        if (rsi && rsi.data != null && rsi.data !== "-") lines.push(`RSI ${Number(rsi.data).toFixed(1)}`)
        return lines.join("<br>")
      },
    },
    grid: [
      { left: 12, right: 72, top: 36, height: "48%" },
      { left: 12, right: 72, top: "62%", height: "10%" },
      { left: 12, right: 72, top: "76%", height: "12%" },
    ],
    xAxis: [0, 1, 2].map((gridIndex) => ({
      type: "category",
      data: series.time,
      gridIndex,
      boundaryGap: true,
      axisLine: { lineStyle: { color: LINE } },
      axisLabel: { show: gridIndex === 2, color: AXIS },
      axisTick: { show: gridIndex === 2 },
      splitLine: { show: false },
    })),
    yAxis: [
      { scale: true, gridIndex: 0, position: "right", axisLabel: { color: AXIS }, splitLine: { lineStyle: { color: LINE } } },
      { scale: true, gridIndex: 1, position: "right", splitNumber: 2, axisLabel: { show: false }, splitLine: { show: false } },
      { min: 0, max: 100, gridIndex: 2, position: "right", splitNumber: 2, axisLabel: { color: AXIS }, splitLine: { lineStyle: { color: LINE } } },
    ],
    dataZoom: [
      {
        type: "inside",
        xAxisIndex: [0, 1, 2],
        start: view.start,
        end: view.end,
        zoomOnMouseWheel: true,
        moveOnMouseMove: true,
        moveOnMouseWheel: false,
      },
      {
        type: "slider",
        xAxisIndex: [0, 1, 2],
        bottom: 8,
        height: 18,
        start: view.start,
        end: view.end,
        fillerColor: "rgba(142, 182, 255, 0.15)",
        borderColor: LINE,
        textStyle: { color: AXIS },
        handleStyle: { color: "#8eb6ff" },
      },
    ],
    series: [
      {
        name: "Price",
        type: "candlestick",
        data: candles,
        xAxisIndex: 0,
        yAxisIndex: 0,
        itemStyle: { color: UP, color0: DOWN, borderColor: UP, borderColor0: DOWN },
        markPoint: { data: markPoint },
        markLine: { symbol: "none", data: markLine, silent: true },
      },
      { name: "Volume", type: "bar", data: volume, xAxisIndex: 1, yAxisIndex: 1 },
      {
        name: "RSI",
        type: "line",
        data: series.rsi,
        xAxisIndex: 2,
        yAxisIndex: 2,
        showSymbol: false,
        connectNulls: false,
        lineStyle: { width: 1.4, color: "#8eb6ff" },
        markLine: {
          symbol: "none",
          silent: true,
          data: [
            { yAxis: rules.rsi_exit, label: { formatter: `sell ${rules.rsi_exit}`, color: AXIS }, lineStyle: { color: LINE } },
            { yAxis: rules.rsi_entry, label: { formatter: `buy ${rules.rsi_entry}`, color: AXIS }, lineStyle: { color: LINE } },
          ],
        },
      },
    ],
  }
}
