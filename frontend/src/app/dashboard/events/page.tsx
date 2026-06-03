"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Activity, RefreshCw, Wifi, WifiOff, AlertCircle, CheckCircle2, Clock, Zap } from "lucide-react"
import { wsClient } from "@/lib/ws"
import { api } from "@/lib/api"

interface Event {
  id: string
  event_type: string
  payload: Record<string, unknown>
  matched_rules: string[]
  priority: number
  status: string
  agent_run_id: string | null
  result: Record<string, unknown> | null
  error_message: string | null
  created_at: string
  completed_at: string | null
}

const statusConfig: Record<string, { icon: typeof Activity; color: string }> = {
  queued: { icon: Clock, color: "text-yellow-500" },
  processing: { icon: RefreshCw, color: "text-blue-500" },
  completed: { icon: CheckCircle2, color: "text-green-500" },
  failed: { icon: AlertCircle, color: "text-red-500" },
}

export default function EventsPage() {
  const [events, setEvents] = useState<Event[]>([])
  const [connected, setConnected] = useState(false)
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState<string>("all")
  const eventsEndRef = useRef<HTMLDivElement>(null)

  const loadEvents = useCallback(async () => {
    try {
      const params: { status?: string } = {}
      if (filter !== "all") params.status = filter
      const data = await api.getEvents({ page: 1, page_size: 50, ...params })
      setEvents(data.events as Event[])
    } catch {
      // silent fail
    } finally {
      setLoading(false)
    }
  }, [filter])

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadEvents()
  }, [loadEvents])

  useEffect(() => {
    const tenantId = localStorage.getItem("flux_tenant_id") || "default"
    wsClient.connect(tenantId)

    const unsub1 = wsClient.on("connected", () => setConnected(true))
    const unsub2 = wsClient.on("event", (msg: unknown) => {
      const data = msg as { data: { event_id: string; status: string; result?: Record<string, unknown>; completed_at?: string } }
      setEvents((prev) => {
        const idx = prev.findIndex((e) => e.id === data.data.event_id)
        if (idx >= 0) {
          const updated = [...prev]
          updated[idx] = { ...updated[idx], status: data.data.status, result: data.data.result ?? updated[idx].result, completed_at: data.data.completed_at ?? updated[idx].completed_at }
          return updated
        }
        return prev
      })
    })
    const unsub3 = wsClient.on("agent_status", (msg: unknown) => {
      const data = msg as { data: { run_id: string; status: string } }
      setEvents((prev) =>
        prev.map((e) =>
          e.agent_run_id === data.data.run_id
            ? { ...e, status: data.data.status }
            : e
        )
      )
    })

    return () => {
      unsub1()
      unsub2()
      unsub3()
      wsClient.disconnect()
    }
  }, [])

  useEffect(() => {
    eventsEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [events])

  const filtered = filter === "all" ? events : events.filter((e) => e.status === filter)

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Events</h1>
          <p className="text-sm text-muted-foreground">
            Real-time webhook events and agent execution feed.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant={connected ? "default" : "secondary"} className="gap-1">
            {connected ? <Wifi className="h-3 w-3" /> : <WifiOff className="h-3 w-3" />}
            {connected ? "Live" : "Disconnected"}
          </Badge>
          <Button variant="outline" size="sm" onClick={loadEvents}>
            <RefreshCw className="h-3 w-3 mr-1" />
            Refresh
          </Button>
        </div>
      </div>

      <div className="flex gap-2">
        {["all", "queued", "processing", "completed", "failed"].map((s) => (
          <Button
            key={s}
            variant={filter === s ? "default" : "outline"}
            size="sm"
            onClick={() => setFilter(s)}
          >
            {s.charAt(0).toUpperCase() + s.slice(1)}
          </Button>
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Activity className="h-4 w-4" />
            Event Feed
            <Badge variant="secondary">{filtered.length}</Badge>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : filtered.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <Zap className="h-12 w-12 text-muted-foreground mb-4" />
              <p className="text-muted-foreground">No events yet.</p>
              <p className="text-xs text-muted-foreground mt-1">
                Connect webhooks from Odoo, HubSpot, or Stripe to see live events.
              </p>
            </div>
          ) : (
            <div className="space-y-2 max-h-[600px] overflow-y-auto">
              {filtered.map((event) => {
                const cfg = statusConfig[event.status] || statusConfig.queued
                const StatusIcon = cfg.icon
                return (
                  <div
                    key={event.id}
                    className="flex items-start gap-3 rounded-lg border border-border p-3 transition-colors hover:bg-accent/50"
                  >
                    <StatusIcon className={`h-4 w-4 mt-0.5 shrink-0 ${cfg.color}`} />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium truncate">
                          {event.event_type}
                        </span>
                        <Badge variant="outline" className="text-xs shrink-0">
                          {event.status}
                        </Badge>
                        {event.priority > 50 && (
                          <Badge variant="default" className="text-xs shrink-0 bg-orange-500">
                            P{event.priority}
                          </Badge>
                        )}
                      </div>
                      {event.matched_rules.length > 0 && (
                        <div className="flex gap-1 mt-1 flex-wrap">
                          {event.matched_rules.map((r) => (
                            <Badge key={r} variant="secondary" className="text-xs">
                              {r}
                            </Badge>
                          ))}
                        </div>
                      )}
                      {event.error_message && (
                        <p className="text-xs text-red-500 mt-1 truncate">
                          {event.error_message}
                        </p>
                      )}
                      <p className="text-xs text-muted-foreground mt-1">
                        {event.created_at ? new Date(event.created_at).toLocaleString() : ""}
                      </p>
                    </div>
                  </div>
                )
              })}
              <div ref={eventsEndRef} />
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
