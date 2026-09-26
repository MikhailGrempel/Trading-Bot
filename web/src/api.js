export async function fetchRun(body) {
  let response
  try {
    response = await fetch("/api/run", {
      method: body ? "POST" : "GET",
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    })
  } catch {
    throw new Error("The page could not reach the bot. Leave python ui.py running.")
  }

  let data = {}
  try {
    data = await response.json()
  } catch {
    data = {}
  }
  if (!response.ok) {
    throw new Error(data.error || "The check failed.")
  }
  return data
}
