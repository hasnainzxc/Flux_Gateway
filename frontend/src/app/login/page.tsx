"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { api, isAuthenticated } from "@/lib/api"
import { toast } from "@/lib/toast"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"

const schema = z.object({
  key: z.string().min(1, "API key is required"),
})

type FormValues = z.infer<typeof schema>

export default function LoginPage() {
  const router = useRouter()
  const [loading, setLoading] = useState(false)

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
  })

  useEffect(() => {
    if (isAuthenticated()) {
      router.replace("/dashboard")
    }
  }, [router])

  const onSubmit = async (data: FormValues) => {
    setLoading(true)
    try {
      await api.validateApiKey(data.key)
      localStorage.setItem("flux_api_key", data.key)
      router.push("/dashboard")
    } catch {
      toast.error("Invalid API key")
    } finally {
      setLoading(false)
    }
  }

  const handleSso = () => {
    api.login()
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <CardTitle className="text-2xl font-bold tracking-tight">Flux Gateway</CardTitle>
          <CardDescription>Sign in to access your dashboard</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="api-key">Sign in with API Key</Label>
              <Input
                id="api-key"
                type="password"
                placeholder="Enter your API key"
                {...register("key")}
                autoComplete="off"
              />
              {errors.key && (
                <p className="text-sm text-destructive">{errors.key.message}</p>
              )}
            </div>
            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? "Verifying..." : "Verify & Sign In"}
            </Button>
          </form>

          <div className="relative">
            <div className="absolute inset-0 flex items-center">
              <span className="w-full border-t border-border" />
            </div>
            <div className="relative flex justify-center text-xs uppercase">
              <span className="bg-card px-2 text-muted-foreground">Or continue with</span>
            </div>
          </div>

          <Button variant="outline" className="w-full" onClick={handleSso}>
            Sign in with SSO (OIDC)
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}
