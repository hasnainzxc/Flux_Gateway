// Utility for merging Tailwind classes — combines clsx (conditional classes) with twMerge (dedup/conflict resolution)
// Usage: cn("px-4", isActive && "bg-primary", className)

import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
