import { describe, it, expect, beforeEach } from "vitest"

// Auth utilities from lib/api.ts — pure functions using localStorage
import { isAuthenticated, clearAuth, getJwtToken } from "@/lib/api"

describe("auth utilities", () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it("isAuthenticated returns false when no keys", () => {
    expect(isAuthenticated()).toBe(false)
  })

  it("isAuthenticated returns true with api key", () => {
    localStorage.setItem("flux_api_key", "sk-test123")
    expect(isAuthenticated()).toBe(true)
  })

  it("isAuthenticated returns true with jwt token", () => {
    localStorage.setItem("flux_jwt_token", "eyJ.test.token")
    expect(isAuthenticated()).toBe(true)
  })

  it("clearAuth removes all auth keys", () => {
    localStorage.setItem("flux_api_key", "sk-test")
    localStorage.setItem("flux_jwt_token", "jwt-test")
    localStorage.setItem("flux_tenant_id", "tenant-1")
    clearAuth()
    expect(localStorage.getItem("flux_api_key")).toBeNull()
    expect(localStorage.getItem("flux_jwt_token")).toBeNull()
    expect(localStorage.getItem("flux_tenant_id")).toBeNull()
  })
})
