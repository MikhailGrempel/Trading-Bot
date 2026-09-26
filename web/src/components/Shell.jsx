import { NavLink, Outlet, useLocation } from "react-router-dom"
import { money, tone } from "../format"
import { useBot } from "../context/BotContext"

const LINKS = [
  { to: "/", label: "Dashboard", end: true, icon: "grid" },
  { to: "/trade", label: "Trade", icon: "chart" },
  { to: "/history", label: "History", icon: "list" },
  { to: "/rules", label: "Rules", icon: "sliders" },
]

const TITLES = {
  "/": "Dashboard",
  "/trade": "Trade",
  "/history": "History",
  "/rules": "Rules",
}

export function Shell() {
  const { payload, error, busy, pending, start, stop, refresh } = useBot()
  const { pathname } = useLocation()
  const running = Boolean(payload?.live?.running)
  const title = TITLES[pathname] || "Paper bot"

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="mark" aria-hidden="true" />
          <div>
            <strong>Paper bot</strong>
            <em>Spot · 15m</em>
          </div>
        </div>
        <nav className="nav" aria-label="Pages">
          {LINKS.map((link) => (
            <NavLink key={link.to} to={link.to} end={link.end}>
              <Icon name={link.icon} />
              {link.label}
            </NavLink>
          ))}
        </nav>
        <p className="side-foot">{payload?.source || "Kraken public candles"}</p>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <div className="top-title">
            <h1>{title}</h1>
            <p>{pending || shortStatus(payload)}</p>
          </div>
          {payload ? (
            <div className="top-equity">
              <span>Equity</span>
              <strong className={tone(payload.summary.profit)}>
                {money(payload.summary.equity)} {payload.currency}
              </strong>
            </div>
          ) : null}
          <div className="top-actions">
            <span className={running ? "pill live" : "pill off"}>{running ? "Running" : "Stopped"}</span>
            <button type="button" className={running ? "ghost" : "primary"} onClick={start} disabled={busy}>
              Start
            </button>
            <button type="button" className={running ? "danger" : "ghost"} onClick={stop} disabled={busy || !payload}>
              Stop
            </button>
          </div>
        </header>
        {error && payload ? <p className="banner error">{error}</p> : null}
        <div className="page">
          {payload ? (
            <Outlet />
          ) : (
            <div className="empty">
              <p>{error || "Loading the paper wallet…"}</p>
              {error ? (
                <button type="button" className="primary" onClick={() => refresh(null)}>
                  Try again
                </button>
              ) : null}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function shortStatus(payload) {
  if (!payload?.live) return "Loading the paper wallet…"
  if (!payload.live.running) return "Stopped. Open coins stay open."
  return `Next candle ${payload.live.next_check} UTC`
}

function Icon({ name }) {
  const common = {
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "1.7",
    strokeLinecap: "round",
    strokeLinejoin: "round",
    "aria-hidden": true,
  }
  if (name === "grid") {
    return (
      <svg {...common}>
        <rect x="3" y="3" width="7" height="7" />
        <rect x="14" y="3" width="7" height="7" />
        <rect x="3" y="14" width="7" height="7" />
        <rect x="14" y="14" width="7" height="7" />
      </svg>
    )
  }
  if (name === "chart") {
    return (
      <svg {...common}>
        <path d="M4 19V5M4 19h16" />
        <path d="M7 15l3.5-4 3 2.5L18 7" />
      </svg>
    )
  }
  if (name === "list") {
    return (
      <svg {...common}>
        <path d="M8 6h12M8 12h12M8 18h12" />
        <path d="M4 6h.01M4 12h.01M4 18h.01" />
      </svg>
    )
  }
  return (
    <svg {...common}>
      <path d="M4 7h16M4 12h10M4 17h16" />
      <circle cx="8" cy="7" r="1.6" fill="currentColor" stroke="none" />
      <circle cx="16" cy="12" r="1.6" fill="currentColor" stroke="none" />
      <circle cx="10" cy="17" r="1.6" fill="currentColor" stroke="none" />
    </svg>
  )
}
