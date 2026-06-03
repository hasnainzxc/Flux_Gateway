// Settings page — theme toggle, link to API keys management, placeholder for model selection

"use client"

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { useTheme } from "@/components/theme-provider"
import { Sun, Moon } from "lucide-react"
import Link from "next/link"

export default function SettingsPage() {
  const { theme, setTheme } = useTheme()

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
        <p className="text-sm text-muted-foreground">Manage your deployment preferences.</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Appearance</CardTitle>
          <CardDescription>Toggle between dark and light mode.</CardDescription>
        </CardHeader>
        <CardContent className="flex items-center gap-3">
          <Button
            variant={theme === "dark" ? "default" : "outline"}
            onClick={() => setTheme("dark")}
          >
            <Moon className="h-4 w-4 mr-2" />
            Dark
          </Button>
          <Button
            variant={theme === "light" ? "default" : "outline"}
            onClick={() => setTheme("light")}
          >
            <Sun className="h-4 w-4 mr-2" />
            Light
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>API Keys</CardTitle>
          <CardDescription>Create and manage your API keys for SDK access.</CardDescription>
        </CardHeader>
        <CardContent>
          <Link href="/dashboard/settings/api">
            <Button variant="outline">Manage API Keys</Button>
          </Link>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Default Model</CardTitle>
          <CardDescription>Set the default LLM model for agent queries.</CardDescription>
        </CardHeader>
        <CardContent>
          <Input placeholder="gpt-4o-mini" disabled className="max-w-xs" />
          <p className="mt-2 text-xs text-muted-foreground">
            Model selection will be available in a future update.
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
