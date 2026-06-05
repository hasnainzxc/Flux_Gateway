"use client"

import * as React from "react"
import { useTheme } from "@/components/theme-provider"
import { Moon, Sun, LogOut } from "lucide-react"
import { Button } from "@/components/ui/button"
import { clearAuth } from "@/lib/api"
import { useRouter } from "next/navigation"

function ThemeToggle() {
  const { theme, setTheme } = useTheme()
  const [mounted, setMounted] = React.useState(false)

  React.useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setMounted(true)
  }, [])

  if (!mounted) {
    return (
      <Button variant="ghost" size="icon" disabled>
        <span className="h-4 w-4" />
      </Button>
    )
  }

  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
    >
      {theme === "dark" ? (
        <Sun className="h-4 w-4" />
      ) : (
        <Moon className="h-4 w-4" />
      )}
    </Button>
  )
}

function LogoutButton() {
  const router = useRouter()
  const [tenantId, setTenantId] = React.useState<string | null>(null)

  React.useEffect(() => {
    if (typeof window !== "undefined") {
      setTenantId(localStorage.getItem("flux_tenant_id"))
    }
  }, [])

  const handleLogout = () => {
    clearAuth()
    router.replace("/login")
  }

  if (typeof window === "undefined") return null

  return (
    <div className="flex items-center gap-3">
      {tenantId && (
        <span className="text-xs text-muted-foreground">
          Tenant: {tenantId.slice(0, 8)}...
        </span>
      )}
      <Button variant="ghost" size="icon" onClick={handleLogout}>
        <LogOut className="h-4 w-4" />
      </Button>
    </div>
  )
}

export function Header() {
  return (
    <header className="flex h-14 items-center gap-4 border-b border-border bg-card px-6">
      <div className="flex-1" />
      <LogoutButton />
      <ThemeToggle />
    </header>
  )
}
