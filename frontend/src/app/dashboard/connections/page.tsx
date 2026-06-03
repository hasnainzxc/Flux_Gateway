// Connections management page — list, add, delete DB connections
// Cards navigate to detail view on click, delete button stops propagation to prevent nav

"use client"

import { useEffect, useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { api } from "@/lib/api"
import { Plus, Plug, Trash2 } from "lucide-react"
import { useRouter } from "next/navigation"

interface Connection {
  id: string
  name: string
  db_type: string
  host: string
  status: string
  created_at: string
}

export default function ConnectionsPage() {
  const [connections, setConnections] = useState<Connection[]>([])
  const [showAdd, setShowAdd] = useState(false)
  const [loading, setLoading] = useState(true)
  const [form, setForm] = useState({ name: "", host: "", port: "5432", database: "", username: "", password: "" })
  const router = useRouter()

  useEffect(() => {
    api.getConnections()
      .then((data) => setConnections(data as Connection[]))
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  // Create connection — hardcoded to PostgreSQL for now, refetch list on success
  // TODO: Add db_type selector, validate port is numeric, show error toast on failure
  const handleAdd = async () => {
    if (!form.name.trim() || !form.host.trim()) return
    const port = parseInt(form.port)
    if (isNaN(port)) return
    try {
      await api.createConnection({
        name: form.name,
        db_type: "postgresql",
        host: form.host,
        port,
        database: form.database,
        username: form.username,
        password: form.password,
      })
      setShowAdd(false)
      const data = await api.getConnections()
      setConnections(data as Connection[])
    } catch (err) {
      console.error(err)
    }
  }

  // Delete connection — no confirmation dialog, optimistic update removes from list
  // TODO: Add confirmation for destructive action
  const handleDelete = async (id: string) => {
    if (!window.confirm("Delete this connection? This cannot be undone.")) return
    await api.deleteConnection(id)
    setConnections((prev) => prev.filter((c) => c.id !== id))
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Connections</h1>
          <p className="text-sm text-muted-foreground">Manage your database connections.</p>
        </div>
        <Button onClick={() => setShowAdd(true)}>
          <Plus className="h-4 w-4" />
          Add Connection
        </Button>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {loading
          ? Array(3)
              .fill(null)
              .map((_, i) => (
                <Card key={i} className="animate-pulse">
                  <CardContent className="h-32" />
                </Card>
              ))
          : connections.map((conn) => (
              <Card
                key={conn.id}
                className="cursor-pointer hover:border-primary/50 transition-colors"
                onClick={() => router.push(`/dashboard/connections/${conn.id}`)}
              >
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-sm font-medium">{conn.name}</CardTitle>
                  <Badge variant={conn.status === "active" ? "success" : "warning"}>
                    {conn.status}
                  </Badge>
                </CardHeader>
                <CardContent>
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Plug className="h-3 w-3" />
                    <span>{conn.db_type}</span>
                    <span className="text-xs">•</span>
                    <span>{conn.host}</span>
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="ml-auto mt-2"
                    onClick={(e) => {
                      e.stopPropagation()
                      handleDelete(conn.id)
                    }}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </CardContent>
              </Card>
            ))}
      </div>

      <Dialog open={showAdd} onOpenChange={setShowAdd}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add PostgreSQL Connection</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <Input placeholder="Connection name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            <Input placeholder="Host" value={form.host} onChange={(e) => setForm({ ...form, host: e.target.value })} />
            <Input placeholder="Port" value={form.port} onChange={(e) => setForm({ ...form, port: e.target.value })} />
            <Input placeholder="Database" value={form.database} onChange={(e) => setForm({ ...form, database: e.target.value })} />
            <Input placeholder="Username" value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} />
            <Input placeholder="Password" type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
            <Button className="w-full" onClick={handleAdd}>Save Connection</Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
