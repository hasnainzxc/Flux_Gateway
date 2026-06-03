// WebSocket client for real-time event streaming — auto-reconnects on disconnect with 3s backoff
// Subscribe to event types via on(), returns unsubscribe fn for cleanup in useEffect

type EventHandler = (data: unknown) => void

// Singleton WS client — manages connection lifecycle, message routing, and reconnection
class WsClient {
  private ws: WebSocket | null = null
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private handlers: Map<string, Set<EventHandler>> = new Map()
  private url: string = ""
  private _tenantId: string = ""

  // Connect to WS server — tenant ID scopes the connection, API key passed as query param
  // onmessage routes by msg.type to registered handlers, onclose triggers auto-reconnect
  connect(tenantId: string) {
    this._tenantId = tenantId
    const apiKey =
      typeof window !== "undefined"
        ? localStorage.getItem("flux_api_key") || ""
        : ""
    // NOTE: API key in URL query param is acceptable for MVP; migrate to WS subprotocol auth for production
    const wsBase = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000"
    this.url = `${wsBase}/ws/${tenantId}?token=${apiKey}`
    this.ws = new WebSocket(this.url)

    this.ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)
        const handlers = this.handlers.get(msg.type) || new Set()
        handlers.forEach((h) => h(msg))
      } catch {
        // Ignore malformed messages — don't crash on bad server data
      }
    }

    this.ws.onclose = (event) => {
      if (!event.wasClean) this.scheduleReconnect()
    }
  }

  // Auto-reconnect with 3s delay — guard prevents multiple timers, only reconnects if tenant still set
  private scheduleReconnect() {
    if (this.reconnectTimer) return
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null
      if (this._tenantId) this.connect(this._tenantId)
    }, 3000)
  }

  // Subscribe to event type — returns unsubscribe fn, use in useEffect cleanup
  on(type: string, handler: EventHandler) {
    if (!this.handlers.has(type)) {
      this.handlers.set(type, new Set())
    }
    this.handlers.get(type)!.add(handler)
    return () => {
      this.handlers.get(type)?.delete(handler)
    }
  }

  // Clean shutdown — clears reconnect timer and closes socket (prevents auto-reconnect)
  disconnect() {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
    this.ws?.close()
    this.ws = null
  }
}

export const wsClient = new WsClient()
