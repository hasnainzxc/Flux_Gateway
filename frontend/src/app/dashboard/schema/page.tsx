// Global schema explorer placeholder — currently directs users to per-connection schema view
// TODO: Aggregate all connection schemas into unified view

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

export default function SchemaPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Schema Explorer</h1>
        <p className="text-sm text-muted-foreground">
          Global view of all reflected schemas.
        </p>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>All Schemas</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            Select a connection from the Connections page to explore its schema.
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
