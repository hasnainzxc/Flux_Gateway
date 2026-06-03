// Webhooks config page — create, toggle, delete webhook endpoints for ingesting external events
// Shows generated ingest URL with copy button, displays secret once on creation (cannot be retrieved again)

"use client"

import { useCallback, useEffect, useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
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
import { Webhook, Plus, Trash2, Copy, Eye, EyeOff } from "lucide-react"
import { api } from "@/lib/api"

interface WebhookConfig {
  id: string
  name: string
  hook_id: string
  source: string
  is_active: boolean
  has_secret: boolean
  created_at: string
}

export default function WebhooksPage() {
  const [webhooks, setWebhooks] = useState<WebhookConfig[]>([])
  const [loading, setLoading] = useState(true)
  const [createOpen, setCreateOpen] = useState(false)
  const [newName, setNewName] = useState("")
  const [newSource, setNewSource] = useState("")
  const [createdSecret, setCreatedSecret] = useState<string | null>(null)
  const [showSecret, setShowSecret] = useState(false)

  const loadWebhooks = useCallback(async () => {
    try {
      const data = await api.getWebhooks()
      setWebhooks(data as WebhookConfig[])
    } catch {
      // silent
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadWebhooks()
  }, [loadWebhooks])

  const handleCreate = async () => {
    if (!newName || !newSource) return
    try {
      const result = await api.createWebhook({ name: newName, source: newSource }) as { secret: string }
      setCreatedSecret(result.secret)
      setNewName("")
      setNewSource("")
      await loadWebhooks()
    } catch {
      // silent
    }
  }

  const handleDelete = async (id: string) => {
    try {
      await api.deleteWebhook(id)
      setWebhooks((prev) => prev.filter((w) => w.id !== id))
    } catch {
      // silent
    }
  }

  const handleToggle = async (id: string, isActive: boolean) => {
    try {
      await api.updateWebhook(id, { is_active: !isActive })
      setWebhooks((prev) =>
        prev.map((w) => (w.id === id ? { ...w, is_active: !isActive } : w))
      )
    } catch {
      // silent
    }
  }

  // Copy to clipboard — no visual feedback, TODO: add toast confirmation
  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text)
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Webhooks</h1>
          <p className="text-sm text-muted-foreground">
            Configure webhook endpoints to receive events from external systems.
          </p>
        </div>

        <Dialog open={createOpen} onOpenChange={setCreateOpen}>
          <DialogTrigger asChild>
            <Button>
              <Plus className="h-4 w-4 mr-2" />
              New Webhook
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Create Webhook</DialogTitle>
            </DialogHeader>
            {createdSecret ? (
              <div className="space-y-4">
                <div className="rounded-lg border border-green-500/50 bg-green-500/10 p-4">
                  <p className="text-sm font-medium text-green-500">Webhook created!</p>
                  <p className="text-xs text-muted-foreground mt-1">
                    Save this secret — it won&apos;t be shown again.
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <code className="flex-1 rounded bg-muted px-3 py-2 text-xs font-mono">
                    {showSecret ? createdSecret : "•".repeat(32)}
                  </code>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setShowSecret(!showSecret)}
                  >
                    {showSecret ? <EyeOff className="h-3 w-3" /> : <Eye className="h-3 w-3" />}
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => copyToClipboard(createdSecret)}
                  >
                    <Copy className="h-3 w-3" />
                  </Button>
                </div>
                <Button onClick={() => { setCreatedSecret(null); setCreateOpen(false) }}>
                  Done
                </Button>
              </div>
            ) : (
              <div className="space-y-4">
                <div>
                  <label className="text-sm font-medium">Name</label>
                  <Input
                    value={newName}
                    onChange={(e) => setNewName(e.target.value)}
                    placeholder="Production Webhook"
                  />
                </div>
                <div>
                  <label className="text-sm font-medium">Source</label>
                  <Input
                    value={newSource}
                    onChange={(e) => setNewSource(e.target.value)}
                    placeholder="odoo, hubspot, stripe..."
                  />
                </div>
                <Button onClick={handleCreate} disabled={!newName || !newSource}>
                  Create
                </Button>
              </div>
            )}
          </DialogContent>
        </Dialog>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Webhook className="h-4 w-4" />
            Webhook Endpoints
          </CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="py-8 text-center text-muted-foreground">Loading...</div>
          ) : webhooks.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <Webhook className="h-12 w-12 text-muted-foreground mb-4" />
              <p className="text-muted-foreground">No webhooks configured.</p>
              <p className="text-xs text-muted-foreground mt-1">
                Create a webhook to start receiving events from external systems.
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {webhooks.map((hook) => (
                <div
                  key={hook.id}
                  className="flex items-center justify-between rounded-lg border border-border p-4"
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium">{hook.name}</span>
                      <Badge variant={hook.is_active ? "default" : "secondary"}>
                        {hook.is_active ? "Active" : "Inactive"}
                      </Badge>
                      <Badge variant="outline">{hook.source}</Badge>
                    </div>
                    <div className="flex items-center gap-2">
                      <code className="text-xs text-muted-foreground font-mono">
                        POST /api/v1/webhooks/ingest/{hook.hook_id}
                      </code>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() =>
                          copyToClipboard(
                            `${window.location.origin}/api/v1/webhooks/ingest/${hook.hook_id}`
                          )
                        }
                      >
                        <Copy className="h-3 w-3" />
                      </Button>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleToggle(hook.id, hook.is_active)}
                    >
                      {hook.is_active ? "Disable" : "Enable"}
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleDelete(hook.id)}
                    >
                      <Trash2 className="h-3 w-3 text-red-500" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
