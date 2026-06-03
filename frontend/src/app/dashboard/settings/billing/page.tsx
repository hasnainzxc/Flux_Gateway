"use client"

import { useCallback, useEffect, useState } from "react"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import {
  BarChart3,
  TrendingUp,
  Zap,
  Cpu,
  Database,
  FileSearch,
  Webhook,
  Plus,
  Trash2,
} from "lucide-react"
import { api } from "@/lib/api"

interface UsageSummary {
  period_start: string
  period_end: string
  tokens_input: number
  tokens_output: number
  agent_runs: number
  webhook_events: number
  sandbox_executions: number
  rag_queries: number
  storage_bytes: number
}

interface BehaviorRule {
  id: string
  name: string
  event_type: string
  conditions: Record<string, unknown>
  action_type: string
  action_config: Record<string, unknown>
  priority: number
  is_active: boolean
}

function formatNumber(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
  return String(n)
}

function formatBytes(bytes: number): string {
  if (bytes >= 1_073_741_824) return `${(bytes / 1_073_741_824).toFixed(1)} GB`
  if (bytes >= 1_048_576) return `${(bytes / 1_048_576).toFixed(1)} MB`
  if (bytes >= 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${bytes} B`
}

export default function BillingPage() {
  const [usage, setUsage] = useState<UsageSummary | null>(null)
  const [history, setHistory] = useState<UsageSummary[]>([])
  const [rules, setRules] = useState<BehaviorRule[]>([])
  const [loading, setLoading] = useState(true)
  const [ruleDialogOpen, setRuleDialogOpen] = useState(false)
  const [newRule, setNewRule] = useState({
    name: "",
    event_type: "",
    action_type: "agent",
    priority: 50,
  })

  const loadData = useCallback(async () => {
    try {
      const [summary, hist, ruleList] = await Promise.all([
        api.getUsageSummary(),
        api.getUsageHistory(6),
        api.getBehaviorRules(),
      ])
      setUsage(summary as UsageSummary)
      setHistory(hist as UsageSummary[])
      setRules(ruleList as BehaviorRule[])
    } catch {
      // silent
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadData()
  }, [loadData])

  const handleCreateRule = async () => {
    if (!newRule.name || !newRule.event_type) return
    try {
      await api.createBehaviorRule(newRule)
      setNewRule({ name: "", event_type: "", action_type: "agent", priority: 50 })
      setRuleDialogOpen(false)
      await loadData()
    } catch {
      // silent
    }
  }

  const handleDeleteRule = async (id: string) => {
    try {
      await api.deleteBehaviorRule(id)
      setRules((prev) => prev.filter((r) => r.id !== id))
    } catch {
      // silent
    }
  }

  const stats = usage
    ? [
        { label: "Tokens In", value: formatNumber(usage.tokens_input), icon: TrendingUp, color: "text-blue-500" },
        { label: "Tokens Out", value: formatNumber(usage.tokens_output), icon: TrendingUp, color: "text-purple-500" },
        { label: "Agent Runs", value: formatNumber(usage.agent_runs), icon: Zap, color: "text-yellow-500" },
        { label: "Webhook Events", value: formatNumber(usage.webhook_events), icon: Webhook, color: "text-green-500" },
        { label: "Sandbox Execs", value: formatNumber(usage.sandbox_executions), icon: Cpu, color: "text-orange-500" },
        { label: "RAG Queries", value: formatNumber(usage.rag_queries), icon: FileSearch, color: "text-cyan-500" },
        { label: "Storage", value: formatBytes(usage.storage_bytes), icon: Database, color: "text-pink-500" },
      ]
    : []

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Usage & Billing</h1>
        <p className="text-sm text-muted-foreground">
          Monitor resource consumption and configure automation rules.
        </p>
      </div>

      {loading ? (
        <div className="py-12 text-center text-muted-foreground">Loading usage data...</div>
      ) : (
        <>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            {stats.map((stat) => (
              <Card key={stat.label}>
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-sm font-medium">{stat.label}</CardTitle>
                  <stat.icon className={`h-4 w-4 ${stat.color}`} />
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">{stat.value}</div>
                  <p className="text-xs text-muted-foreground">This billing period</p>
                </CardContent>
              </Card>
            ))}
          </div>

          {history.length > 1 && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <BarChart3 className="h-4 w-4" />
                  Usage History
                </CardTitle>
                <CardDescription>Monthly token consumption trend</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex items-end gap-2 h-32">
                  {history.map((h, i) => {
                    const total = h.tokens_input + h.tokens_output
                    const maxTotal = Math.max(...history.map((x) => x.tokens_input + x.tokens_output), 1)
                    const height = Math.max((total / maxTotal) * 100, 4)
                    return (
                      <div key={i} className="flex-1 flex flex-col items-center gap-1">
                        <div
                          className="w-full rounded-t bg-primary/60 transition-all hover:bg-primary"
                          style={{ height: `${height}%` }}
                          title={`${formatNumber(total)} tokens`}
                        />
                        <span className="text-[10px] text-muted-foreground">
                          {new Date(h.period_start).toLocaleDateString("en", { month: "short" })}
                        </span>
                      </div>
                    )
                  })}
                </div>
              </CardContent>
            </Card>
          )}

          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle>Behavior Rules</CardTitle>
                <CardDescription>
                  Define automation rules that trigger agent workflows on webhook events.
                </CardDescription>
              </div>
              <Dialog open={ruleDialogOpen} onOpenChange={setRuleDialogOpen}>
                <DialogTrigger asChild>
                  <Button size="sm">
                    <Plus className="h-3 w-3 mr-1" />
                    Add Rule
                  </Button>
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>Create Behavior Rule</DialogTitle>
                  </DialogHeader>
                  <div className="space-y-4">
                    <div>
                      <label className="text-sm font-medium">Name</label>
                      <Input
                        value={newRule.name}
                        onChange={(e) => setNewRule({ ...newRule, name: e.target.value })}
                        placeholder="Low Inventory Alert"
                      />
                    </div>
                    <div>
                      <label className="text-sm font-medium">Event Type</label>
                      <Input
                        value={newRule.event_type}
                        onChange={(e) => setNewRule({ ...newRule, event_type: e.target.value })}
                        placeholder="inventory.updated"
                      />
                    </div>
                    <div>
                      <label className="text-sm font-medium">Action Type</label>
                      <Input
                        value={newRule.action_type}
                        onChange={(e) => setNewRule({ ...newRule, action_type: e.target.value })}
                        placeholder="agent"
                      />
                    </div>
                    <div>
                      <label className="text-sm font-medium">Priority (1-100)</label>
                      <Input
                        type="number"
                        value={newRule.priority}
                        onChange={(e) =>
                          setNewRule({ ...newRule, priority: Number(e.target.value) })
                        }
                        min={1}
                        max={100}
                      />
                    </div>
                    <Button onClick={handleCreateRule} disabled={!newRule.name || !newRule.event_type}>
                      Create
                    </Button>
                  </div>
                </DialogContent>
              </Dialog>
            </CardHeader>
            <CardContent>
              {rules.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-8 text-center">
                  <Zap className="h-10 w-10 text-muted-foreground mb-3" />
                  <p className="text-sm text-muted-foreground">No behavior rules configured.</p>
                  <p className="text-xs text-muted-foreground mt-1">
                    Create rules to automate workflows based on webhook events.
                  </p>
                </div>
              ) : (
                <div className="space-y-2">
                  {rules.map((rule) => (
                    <div
                      key={rule.id}
                      className="flex items-center justify-between rounded-lg border border-border p-3"
                    >
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium">{rule.name}</span>
                          <Badge variant={rule.is_active ? "default" : "secondary"}>
                            {rule.is_active ? "Active" : "Inactive"}
                          </Badge>
                          <Badge variant="outline">P{rule.priority}</Badge>
                        </div>
                        <div className="flex items-center gap-2 text-xs text-muted-foreground">
                          <span className="font-mono">{rule.event_type}</span>
                          <span>→</span>
                          <span>{rule.action_type}</span>
                        </div>
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleDeleteRule(rule.id)}
                      >
                        <Trash2 className="h-3 w-3 text-red-500" />
                      </Button>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  )
}
