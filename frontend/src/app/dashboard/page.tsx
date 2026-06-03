"use client"

import { useCallback, useEffect, useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Database, FileText, Plug, Zap, TrendingUp, Webhook, Cpu } from "lucide-react"
import { api } from "@/lib/api"

interface UsageSummary {
  tokens_input: number
  tokens_output: number
  agent_runs: number
  webhook_events: number
  sandbox_executions: number
  rag_queries: number
  storage_bytes: number
}

function formatNumber(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
  return String(n)
}

export default function DashboardPage() {
  const [usage, setUsage] = useState<UsageSummary | null>(null)
  const [connCount, setConnCount] = useState(0)
  const [docCount, setDocCount] = useState(0)

  const loadStats = useCallback(async () => {
    try {
      const [summary, connections, documents] = await Promise.all([
        api.getUsageSummary().catch(() => null),
        api.getConnections().catch(() => []),
        api.getDocuments().catch(() => []),
      ])
      if (summary) setUsage(summary as UsageSummary)
      setConnCount((connections as unknown[]).length)
      setDocCount((documents as unknown[]).length)
    } catch {
      // silent
    }
  }, [])

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadStats()
  }, [loadStats])

  const totalTokens = usage ? usage.tokens_input + usage.tokens_output : 0

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
        <p className="text-sm text-muted-foreground">
          Welcome to Flux Gateway — your Data-to-Agent platform.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Agent Runs</CardTitle>
            <Zap className="h-4 w-4 text-yellow-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{usage ? formatNumber(usage.agent_runs) : "—"}</div>
            <p className="text-xs text-muted-foreground">Runs this month</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Documents</CardTitle>
            <FileText className="h-4 w-4 text-cyan-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{docCount || "—"}</div>
            <p className="text-xs text-muted-foreground">RAG documents uploaded</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Connections</CardTitle>
            <Plug className="h-4 w-4 text-green-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{connCount || "—"}</div>
            <p className="text-xs text-muted-foreground">Active DB connections</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Token Usage</CardTitle>
            <TrendingUp className="h-4 w-4 text-purple-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{usage ? formatNumber(totalTokens) : "—"}</div>
            <p className="text-xs text-muted-foreground">Tokens consumed this month</p>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Webhook Events</CardTitle>
            <Webhook className="h-4 w-4 text-blue-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{usage ? formatNumber(usage.webhook_events) : "—"}</div>
            <p className="text-xs text-muted-foreground">Events processed</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Sandbox Execs</CardTitle>
            <Cpu className="h-4 w-4 text-orange-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{usage ? formatNumber(usage.sandbox_executions) : "—"}</div>
            <p className="text-xs text-muted-foreground">SQL validations</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">RAG Queries</CardTitle>
            <Database className="h-4 w-4 text-pink-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{usage ? formatNumber(usage.rag_queries) : "—"}</div>
            <p className="text-xs text-muted-foreground">Knowledge base queries</p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Getting Started</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <div className="flex items-center gap-3 rounded-md border border-border p-3">
            <span className="flex h-6 w-6 items-center justify-center rounded-full bg-primary/10 text-xs font-medium text-primary">
              1
            </span>
            <span className="text-sm">Add a database connection</span>
          </div>
          <div className="flex items-center gap-3 rounded-md border border-border p-3">
            <span className="flex h-6 w-6 items-center justify-center rounded-full bg-primary/10 text-xs font-medium text-primary">
              2
            </span>
            <span className="text-sm">Reflect the schema</span>
          </div>
          <div className="flex items-center gap-3 rounded-md border border-border p-3">
            <span className="flex h-6 w-6 items-center justify-center rounded-full bg-primary/10 text-xs font-medium text-primary">
              3
            </span>
            <span className="text-sm">Upload documents for RAG</span>
          </div>
          <div className="flex items-center gap-3 rounded-md border border-border p-3">
            <span className="flex h-6 w-6 items-center justify-center rounded-full bg-primary/10 text-xs font-medium text-primary">
              4
            </span>
            <span className="text-sm">Ask questions in Chat</span>
          </div>
          <div className="flex items-center gap-3 rounded-md border border-border p-3">
            <span className="flex h-6 w-6 items-center justify-center rounded-full bg-primary/10 text-xs font-medium text-primary">
              5
            </span>
            <span className="text-sm">Configure webhooks for automation</span>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
