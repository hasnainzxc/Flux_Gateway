// API client for Flux Gateway backend — wraps fetch with auth headers and error handling
// All methods return typed responses, errors throw ApiError with status + body

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

// Custom error class for API failures — includes HTTP status and response body
export class ApiError extends Error {
  status: number
  body: unknown

  constructor(status: number, body: unknown) {
    super(`API Error ${status}`)
    this.status = status
    this.body = body
  }
}

// API key storage — client-side uses localStorage (set during auth), server-side uses global var
let globalApiKey: string | null = null

// Set API key for server-side requests (SSR/SSG contexts)
export function setApiKey(key: string | null) {
  globalApiKey = key
}

// Retrieve API key — prefers localStorage on client, falls back to global var on server
function getApiKey(): string {
  if (typeof window !== "undefined") {
    return localStorage.getItem("flux_api_key") || ""
  }
  return globalApiKey || ""
}

// Retrieve JWT token from localStorage (set during OIDC login)
export function getJwtToken(): string {
  if (typeof window !== "undefined") {
    return localStorage.getItem("flux_jwt_token") || ""
  }
  return ""
}

// Check if user is authenticated — has either API key or JWT token
export function isAuthenticated(): boolean {
  if (typeof window === "undefined") return false
  return !!(localStorage.getItem("flux_api_key") || localStorage.getItem("flux_jwt_token"))
}

// Clear all auth-related localStorage keys
export function clearAuth(): void {
  if (typeof window !== "undefined") {
    localStorage.removeItem("flux_api_key")
    localStorage.removeItem("flux_jwt_token")
    localStorage.removeItem("flux_tenant_id")
  }
}

// Generic request wrapper — injects auth header (API key or JWT), parses JSON or text errors
// Throws ApiError on non-2xx responses with status code and body for debugging
async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const apiKey = getApiKey()
  const jwtToken = getJwtToken()
  const authHeaders: Record<string, string> = {}
  if (apiKey) {
    authHeaders["X-API-Key"] = apiKey
  } else if (jwtToken) {
    authHeaders["Authorization"] = `Bearer ${jwtToken}`
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...authHeaders,
      ...options?.headers,
    },
  })

  if (!res.ok) {
    // Try JSON first, fall back to plain text for non-JSON error responses
    let body: unknown
    try {
      body = await res.json()
    } catch {
      body = await res.text()
    }
    throw new ApiError(res.status, body)
  }

  const contentType = res.headers.get("content-type")
  if (!contentType || !contentType.includes("application/json")) return null as T
  return res.json()
}

// API methods organized by resource — all return Promises, errors throw ApiError
export const api = {
  // === Connections ===
  getConnections: () => request<unknown[]>("/api/v1/connections"),
  createConnection: (data: unknown) =>
    request("/api/v1/connections", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  deleteConnection: (id: string) =>
    request(`/api/v1/connections/${id}`, { method: "DELETE" }),
  testConnection: (id: string) =>
    request(`/api/v1/connections/${id}/test`, { method: "POST" }),

  // === Schema ===
  // Fetch cached schema for a connection, or trigger reflection to rebuild from DB
  getSchema: (connectionId: string) =>
    request(`/api/v1/connections/${connectionId}/schema`),
  reflectSchema: (connectionId: string) =>
    request(`/api/v1/connections/${connectionId}/reflect`, {
      method: "POST",
    }),

  // === Agent Query ===
  // Send NL query to agent — returns answer, citations (for RAG), token count, and latency
  // Optional connection_id scopes query to specific DB
  query: (prompt: string, options?: { connection_id?: string }) =>
    request<{
      answer: string
      citations: unknown[]
      tokens_used: number
      latency_ms: number
    }>("/api/v1/agent/query", {
      method: "POST",
      body: JSON.stringify({
        prompt: prompt,
        ...options,
      }),
    }),

  // === RAG Documents ===
  getDocuments: async () => {
    const data = await request<{ documents: unknown[]; total: number }>("/api/v1/rag/documents")
    return data.documents
  },
  // Upload uses FormData (multipart) instead of JSON — bypasses request() wrapper
  uploadDocument: async (file: File) => {
    const apiKey = getApiKey()
    const formData = new FormData()
    formData.append("file", file)
    const res = await fetch(`${API_BASE}/api/v1/rag/documents`, {
      method: "POST",
      headers: apiKey ? { "X-API-Key": apiKey } : {},
      body: formData,
    })
    if (!res.ok) throw new ApiError(res.status, await res.json().catch(() => res.text()))
    const contentType = res.headers.get("content-type")
    if (!contentType || !contentType.includes("application/json")) return null
    return res.json()
  },
  deleteDocument: (id: string) =>
    request(`/api/v1/rag/documents/${id}`, { method: "DELETE" }),
  searchDocuments: (query: string, topK = 10) =>
    request("/api/v1/rag/search", {
      method: "POST",
      body: JSON.stringify({ query, top_k: topK }),
    }),
  askRag: (query: string, topK = 10) =>
    request("/api/v1/rag/ask", {
      method: "POST",
      body: JSON.stringify({ query, top_k: topK }),
    }),

  getApiKeys: () => request<unknown[]>("/api/v1/api-keys"),
  createApiKey: (name: string) =>
    request("/api/v1/api-keys", {
      method: "POST",
      body: JSON.stringify({ name }),
    }),
  revokeApiKey: (id: string) =>
    request(`/api/v1/api-keys/${id}`, { method: "DELETE" }),

  // Validate an API key by testing it against a lightweight endpoint
  // Returns the response data if valid, throws ApiError if invalid
  validateApiKey: async (key: string) => {
    const res = await fetch(`${API_BASE}/api/v1/api-keys`, {
      headers: {
        "Content-Type": "application/json",
        "X-API-Key": key,
      },
    })
    if (!res.ok) {
      let body: unknown
      try {
        body = await res.json()
      } catch {
        body = await res.text()
      }
      throw new ApiError(res.status, body)
    }
    return res.json()
  },

  // Redirect to backend OIDC login flow
  login: () => {
    window.location.href = `${API_BASE}/api/v1/auth/login`
  },

  // Create API key with explicit auth header (used during onboarding with JWT)
  createApiKeyWithAuth: (name: string, authToken: string) =>
    request("/api/v1/api-keys", {
      method: "POST",
      headers: { Authorization: `Bearer ${authToken}` },
      body: JSON.stringify({ name }),
    }),

  // === Events ===
  // Paginated event list with optional filters — builds query string manually to handle sparse params
  getEvents: (params?: { page?: number; page_size?: number; status?: string; event_type?: string }) => {
    const qs = new URLSearchParams()
    if (params?.page) qs.set("page", String(params.page))
    if (params?.page_size) qs.set("page_size", String(params.page_size))
    if (params?.status) qs.set("status", params.status)
    if (params?.event_type) qs.set("event_type", params.event_type)
    return request<{ events: unknown[]; total: number; page: number; page_size: number }>(
      `/api/v1/events?${qs.toString()}`
    )
  },
  getEvent: (id: string) => request<unknown>(`/api/v1/events/${id}`),
  retryEvent: (id: string) =>
    request(`/api/v1/events/${id}/retry`, { method: "POST" }),

  getWebhooks: () => request<unknown[]>("/api/v1/webhooks"),
  createWebhook: (data: { name: string; source: string }) =>
    request("/api/v1/webhooks", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  updateWebhook: (id: string, data: { name?: string; source?: string; is_active?: boolean }) =>
    request(`/api/v1/webhooks/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
  deleteWebhook: (id: string) =>
    request(`/api/v1/webhooks/${id}`, { method: "DELETE" }),

  // === Behavior Rules ===
  // Automation rules that trigger agent workflows on webhook events
  // Priority: lower number = higher priority (1-100 range)
  getBehaviorRules: () => request<unknown[]>("/api/v1/behavior-rules"),
  createBehaviorRule: (data: {
    name: string
    event_type: string
    conditions?: Record<string, unknown>
    action_type: string
    action_config?: Record<string, unknown>
    priority?: number
  }) =>
    request("/api/v1/behavior-rules", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  updateBehaviorRule: (id: string, data: Record<string, unknown>) =>
    request(`/api/v1/behavior-rules/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
  deleteBehaviorRule: (id: string) =>
    request(`/api/v1/behavior-rules/${id}`, { method: "DELETE" }),

  getUsageSummary: () => request<unknown>("/api/v1/usage/summary"),
  getUsageHistory: (months?: number) =>
    request<unknown[]>(`/api/v1/usage/history${months ? `?months=${months}` : ""}`),
}
