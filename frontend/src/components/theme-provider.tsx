// Theme provider — manages dark/light mode via context, persists to localStorage
// Defaults to dark theme, respects system preference if no stored value

"use client"

import * as React from "react"

type Theme = "dark" | "light"

// Determine initial theme — SSR returns dark, client checks localStorage then system preference
function getInitialTheme(): Theme {
  if (typeof window === "undefined") return "dark"
  const stored = localStorage.getItem("flux_theme") as Theme | null
  if (stored === "dark" || stored === "light") return stored
  if (window.matchMedia("(prefers-color-scheme: light)").matches) return "light"
  return "dark"
}

const ThemeContext = React.createContext<{
  theme: Theme
  setTheme: (t: Theme) => void
}>({
  theme: "dark",
  setTheme: () => {},
})

export function useTheme() {
  return React.useContext(ThemeContext)
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setTheme] = React.useState<Theme>(getInitialTheme)

  // Apply theme class to <html> and persist — drives Tailwind dark: variants
  React.useEffect(() => {
    const root = document.documentElement
    root.classList.remove("light", "dark")
    root.classList.add(theme)
    localStorage.setItem("flux_theme", theme)
  }, [theme])

  return (
    <ThemeContext.Provider value={{ theme, setTheme }}>
      {children}
    </ThemeContext.Provider>
  )
}
