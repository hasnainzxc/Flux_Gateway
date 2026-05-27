import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"

export default function BillingPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Billing</h1>
        <p className="text-sm text-muted-foreground">Usage and billing will be available post-MVP.</p>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Usage Overview</CardTitle>
          <CardDescription>Token consumption and plan details.</CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground py-8 text-center">
            Billing features coming in a future release.
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
