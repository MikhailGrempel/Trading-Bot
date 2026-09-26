import { Navigate, Route, Routes } from "react-router-dom"
import { Shell } from "./components/Shell"
import { BotProvider } from "./context/BotContext"
import { Dashboard } from "./pages/Dashboard"
import { History } from "./pages/History"
import { Rules } from "./pages/Rules"
import { Trade } from "./pages/Trade"

export function App() {
  return (
    <BotProvider>
      <Routes>
        <Route element={<Shell />}>
          <Route index element={<Dashboard />} />
          <Route path="trade" element={<Trade />} />
          <Route path="history" element={<History />} />
          <Route path="rules" element={<Rules />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BotProvider>
  )
}
