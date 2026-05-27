type EventHandler = (data: unknown) => void

class WsClient {
  private ws: WebSocket | null = null
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private handlers: Map<string, Set<EventHandler>> = new Map()
  private url: string = ""

  connect(tenantId: string) {
    const apiKey =
      typeof window !== "undefined"
        ? localStorage.getItem("flux_api_key") || ""
        : ""
    this.url = `ws://localhost:8000/ws/${tenantId}?token=${apiKey}`
    this.ws = new WebSocket(this.url)

    this.ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)
        const handlers = this.handlers.get(msg.type) || new Set()
        handlers.forEach((h) => h(msg))
      } catch {
        // Ignore malformed messages
      }
    }

    this.ws.onclose = () => {
      this.scheduleReconnect()
    }
  }

  private scheduleReconnect() {
    if (this.reconnectTimer) return
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null
      if (this.url) this.connect(this.url)
    }, 3000)
  }

  on(type: string, handler: EventHandler) {
    if (!this.handlers.has(type)) {
      this.handlers.set(type, new Set())
    }
    this.handlers.get(type)!.add(handler)
    return () => {
      this.handlers.get(type)?.delete(handler)
    }
  }

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
