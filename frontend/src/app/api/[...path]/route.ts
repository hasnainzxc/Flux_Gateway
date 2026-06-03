// API proxy route — forwards all /api/* requests to backend server
// Used to avoid CORS issues and hide backend URL from client, injects server-side API key
// WARNING: No rate limiting or request validation — backend must enforce auth

import { NextResponse } from "next/server"

const BACKEND_URL = process.env.BACKEND_API_URL || "http://localhost:8000"

// Generic proxy handler — forwards method, body, and query params to backend
async function proxy(method: string, request: Request, pathSegments: string[]) {
  const url = `${BACKEND_URL}/${pathSegments.join("/")}`
  const headers: Record<string, string> = {
    "X-API-Key": process.env.BACKEND_API_KEY || "",
  }
  let body: string | null = null
  if (method !== "GET" && method !== "DELETE") {
    body = await request.text()
    headers["Content-Type"] = "application/json"
  }

  // Forward query params from original request
  const searchParams = new URL(request.url).searchParams
  const fullUrl = searchParams.size > 0 ? `${url}?${searchParams}` : url

  const res = await fetch(fullUrl, { method, headers, body })
  const contentType = res.headers.get("content-type") || ""
  if (contentType.includes("application/json")) {
    const data = await res.json()
    return NextResponse.json(data, { status: res.status })
  }
  const text = await res.text()
  return new NextResponse(text, { status: res.status })
}

export async function GET(
  request: Request,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params
  return proxy("GET", request, path)
}

export async function POST(
  request: Request,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params
  return proxy("POST", request, path)
}

export async function PUT(
  request: Request,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params
  return proxy("PUT", request, path)
}

export async function DELETE(
  request: Request,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params
  return proxy("DELETE", request, path)
}
