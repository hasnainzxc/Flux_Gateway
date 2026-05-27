"use client"

import { useEffect, useState } from "react"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { api } from "@/lib/api"
import { Plus, Key, Copy, Trash2, Check } from "lucide-react"

interface ApiKey {
  id: string
  name: string
  key_prefix: string
  created_at: string
}

export default function ApiKeysPage() {
  const [keys, setKeys] = useState<ApiKey[]>([])
  const [newName, setNewName] = useState("")
  const [copied, setCopied] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const fetchKeys = async () => {
    try {
      const data = await api.getApiKeys()
      setKeys(data as ApiKey[])
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchKeys()
  }, [])

  const handleCreate = async () => {
    if (!newName.trim()) return
    try {
      await api.createApiKey(newName)
      setNewName("")
      fetchKeys()
    } catch (err) {
      console.error(err)
    }
  }

  const handleRevoke = async (id: string) => {
    await api.revokeApiKey(id)
    fetchKeys()
  }

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text)
    setCopied(text)
    setTimeout(() => setCopied(null), 2000)
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">API Keys</h1>
        <p className="text-sm text-muted-foreground">
          Create and manage API keys for programmatic access.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Create API Key</CardTitle>
          <CardDescription>Give it a name to identify its purpose.</CardDescription>
        </CardHeader>
        <CardContent className="flex gap-2">
          <Input
            placeholder="Key name (e.g. production, staging)"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            className="max-w-sm"
          />
          <Button onClick={handleCreate}>
            <Plus className="h-4 w-4 mr-2" />
            Create
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Active Keys</CardTitle>
        </CardHeader>
        <CardContent>
          {keys.length === 0 && !loading && (
            <p className="text-sm text-muted-foreground py-4">No API keys created yet.</p>
          )}
          <div className="space-y-2">
            {keys.map((key) => (
              <div
                key={key.id}
                className="flex items-center gap-3 rounded-md bg-muted/50 px-4 py-3"
              >
                <Key className="h-4 w-4 text-muted-foreground" />
                <div className="flex-1">
                  <p className="text-sm font-medium">{key.name}</p>
                  <p className="text-xs text-muted-foreground">{key.key_prefix}...</p>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => handleCopy(key.key_prefix)}
                >
                  {copied === key.key_prefix ? (
                    <Check className="h-4 w-4 text-emerald-400" />
                  ) : (
                    <Copy className="h-4 w-4" />
                  )}
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => handleRevoke(key.id)}
                >
                  <Trash2 className="h-4 w-4 text-destructive" />
                </Button>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
