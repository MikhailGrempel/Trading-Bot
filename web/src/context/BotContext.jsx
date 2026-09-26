import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react"
import { fetchRun } from "../api"

const BotContext = createContext(null)

export function BotProvider({ children }) {
  const [payload, setPayload] = useState(null)
  const [error, setError] = useState("")
  const [busy, setBusy] = useState(false)
  const [pending, setPending] = useState("")
  const chain = useRef(Promise.resolve())

  const refresh = useCallback((body) => {
    const job = async () => {
      setBusy(true)
      if (body?.command === "start") setPending("Checking the latest candle…")
      else if (body?.command === "stop") setPending("Stopping…")
      else if (body) setPending("Saving the rules…")
      try {
        const data = await fetchRun(body)
        setPayload(data)
        setError("")
        return true
      } catch (err) {
        setError(err.message || "The check failed.")
        return false
      } finally {
        setPending("")
        setBusy(false)
      }
    }
    const run = chain.current.then(job, job)
    chain.current = run.then(() => undefined, () => undefined)
    return run
  }, [])

  useEffect(() => {
    refresh(null)
    const id = setInterval(() => refresh(null), 20000)
    return () => clearInterval(id)
  }, [refresh])

  const value = {
    payload,
    error,
    busy,
    pending,
    refresh,
    start: () => refresh({ command: "start" }),
    stop: () => refresh({ command: "stop" }),
    saveRules: (draft) => refresh(draft),
  }

  return <BotContext.Provider value={value}>{children}</BotContext.Provider>
}

export function useBot() {
  const value = useContext(BotContext)
  if (!value) throw new Error("useBot must be used inside BotProvider")
  return value
}
