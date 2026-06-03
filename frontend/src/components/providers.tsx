// Global providers wrapper — React Query (5min stale, 1 retry), Toaster (bottom-right), ErrorBoundary, TooltipProvider
// Wraps entire app in layout.tsx, "use client" needed for context providers

"use client"
import * as React from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { Toaster } from "sonner"
import { ErrorBoundary } from "@/components/error-boundary"
import { TooltipProvider } from "@/components/ui/tooltip"

// 5min stale time prevents excessive refetches, retry:1 handles transient network blips
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
})

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <TooltipProvider>
          {children}
          <Toaster
            position="bottom-right"
            toastOptions={{
              style: {
                background: "hsl(var(--card))",
                border: "1px solid hsl(var(--border))",
                color: "hsl(var(--card-foreground))",
              },
            }}
          />
        </TooltipProvider>
      </QueryClientProvider>
    </ErrorBoundary>
  )
}
