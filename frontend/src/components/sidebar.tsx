// Sidebar navigation — collapsible with icon-only mode, highlights active route
// Uses pathname matching for active state, persists collapse state in component (not localStorage)

"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { cn } from "@/lib/utils"
import {
  LayoutDashboard,
  Plug,
  Database,
  MessageSquare,
  FileText,
  Activity,
  Settings,
  ChevronLeft,
  Webhook,
} from "lucide-react"
import { useState } from "react"

// Nav items — order defines sidebar layout, icons from lucide-react
const navItems = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/dashboard/connections", label: "Connections", icon: Plug },
  { href: "/dashboard/schema", label: "Schema", icon: Database },
  { href: "/dashboard/chat", label: "Chat", icon: MessageSquare },
  { href: "/dashboard/docs", label: "Documents", icon: FileText },
  { href: "/dashboard/events", label: "Events", icon: Activity },
  { href: "/dashboard/events/webhooks", label: "Webhooks", icon: Webhook },
  { href: "/dashboard/settings", label: "Settings", icon: Settings },
]

export function Sidebar() {
  const pathname = usePathname()
  const [collapsed, setCollapsed] = useState(false)

  return (
    <aside
      className={cn(
        "flex flex-col border-r border-border bg-card transition-all duration-300",
        collapsed ? "w-16" : "w-56"
      )}
    >
      <div className="flex h-14 items-center gap-2 border-b border-border px-4">
        {!collapsed && (
          <span className="text-sm font-semibold tracking-tight">
            Flux Gateway
          </span>
        )}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="ml-auto rounded-md p-1.5 hover:bg-accent transition-colors"
        >
          <ChevronLeft
            className={cn(
              "h-4 w-4 transition-transform",
              collapsed && "rotate-180"
            )}
          />
        </button>
      </div>
      <nav className="flex-1 space-y-1 p-2">
        {navItems.map((item) => {
          // Active if exact match OR sub-route (but not root /dashboard matching /dashboard/settings)
          const isActive =
            pathname === item.href ||
            (item.href !== "/dashboard" && pathname.startsWith(item.href))
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                isActive
                  ? "bg-primary/10 text-primary"
                  : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
              )}
              title={collapsed ? item.label : undefined}
            >
              <item.icon className="h-4 w-4 shrink-0" />
              {!collapsed && <span>{item.label}</span>}
            </Link>
          )
        })}
      </nav>
      <div className="border-t border-border p-2">
        {!collapsed && (
          <div className="rounded-md bg-muted/50 px-3 py-2 text-xs text-muted-foreground">
            v0.1.0-alpha
          </div>
        )}
      </div>
    </aside>
  )
}
