// Connection detail page — displays reflected schema (tables + columns) for a single connection
// Allows triggering schema reflection, shows PK indicators and data types

"use client"

import { useCallback, useEffect, useState } from "react"
import { useParams } from "next/navigation"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { api } from "@/lib/api"
import { RefreshCw, Key, Hash } from "lucide-react"

export default function ConnectionDetailPage() {
  // useParams returns string | string[] — normalize to string, fallback to "unknown" if missing
  const params: Record<string, string | string[] | undefined> = useParams()
  const id = String(params.id ?? "unknown")
  const [schema, setSchema] = useState<unknown>(null)
  const [loading, setLoading] = useState(true)

  const fetchSchema = useCallback(async () => {
    setLoading(true)
    try {
      const data = await api.getSchema(id)
      setSchema(data)
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }, [id])

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchSchema()
  }, [fetchSchema])

  const schemaData = schema as Record<string, unknown> | null

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Schema Explorer</h1>
          <p className="text-sm text-muted-foreground">Connection: {id}</p>
        </div>
        <Button onClick={() => api.reflectSchema(id).then(fetchSchema)} disabled={loading}>
          <RefreshCw className={`h-4 w-4 mr-2 ${loading ? "animate-spin" : ""}`} />
          Reflect Schema
        </Button>
      </div>

      {!schemaData && !loading && (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12 text-center">
            <p className="text-muted-foreground">No schema reflected yet.</p>
            <Button className="mt-4" onClick={() => api.reflectSchema(id).then(fetchSchema)}>
              Reflect Now
            </Button>
          </CardContent>
        </Card>
      )}

      {schemaData?.tables ? (
        <div className="space-y-4">
          {(Array.isArray(schemaData.tables) ? schemaData.tables as Array<Record<string, unknown>> : []).map((table: Record<string, unknown>, i: number) => (
            <Card key={i}>
              <CardHeader className="pb-2">
                <CardTitle className="text-base font-mono">{table.name as string}</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {(Array.isArray(table.columns) ? table.columns as Array<Record<string, unknown>> : []).map((col: Record<string, unknown>, j: number) => (
                    <div
                      key={j}
                      className="flex items-center gap-2 rounded-md bg-muted/50 px-3 py-1.5 text-sm"
                    >
                      {col.is_primary_key ? (
                        <Key className="h-3 w-3 text-amber-400" />
                      ) : (
                        <Hash className="h-3 w-3 text-muted-foreground" />
                      )}
                      <span className="font-medium">{col.name as string}</span>
                      <Badge variant="secondary" className="ml-auto text-xs">
                        {col.data_type as string}
                      </Badge>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : null}
    </div>
  )
}
