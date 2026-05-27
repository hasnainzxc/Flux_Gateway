const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

export class ApiError extends Error {
  status: number
  body: unknown

  constructor(status: number, body: unknown) {
    super(`API Error ${status}`)
    this.status = status
    this.body = body
  }
}

let globalApiKey: string | null = null

export function setApiKey(key: string | null) {
  globalApiKey = key
}

function getApiKey(): string {
  if (typeof window !== "undefined") {
    return localStorage.getItem("flux_api_key") || ""
  }
  return globalApiKey || ""
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const apiKey = getApiKey()
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(apiKey ? { "X-API-Key": apiKey } : {}),
      ...options?.headers,
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
}

export const api = {
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

  getSchema: (connectionId: string) =>
    request(`/api/v1/connections/${connectionId}/schema`),
  reflectSchema: (connectionId: string) =>
    request(`/api/v1/connections/${connectionId}/reflect`, {
      method: "POST",
    }),

  query: (prompt: string, options?: { connection_id?: string }) =>
    request<{
      answer: string
      citations: unknown[]
      tokens_used: number
      latency_ms: number
    }>("/api/v1/agent/query", {
      method: "POST",
      body: JSON.stringify({
        user_query: prompt,
        ...options,
      }),
    }),

  getDocuments: () => request<unknown[]>("/api/v1/rag/documents"),
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
}
