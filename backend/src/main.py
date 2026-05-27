from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from structlog import get_logger

from src.api.v1.agent import router as agent_router
from src.api.v1.api_keys import router as api_keys_router
from src.api.v1.auth import router as auth_router
from src.api.v1.connections import router as connections_router
from src.api.v1.query import router as query_router
from src.api.v1.rag import router as rag_router
from src.api.v1.sandbox import router as sandbox_router
from src.api.v1.schema_endpoints import router as schema_router
from src.core.config import settings

logger = get_logger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Any) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Strict-Transport-Security"] = "max-age=31536000"
        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("flux gateway starting", environment=settings.environment)
    yield
    logger.info("flux gateway shutting down")


app = FastAPI(
    title="Flux Gateway",
    description="Data-to-Agent Gateway — secure B2B SaaS platform",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api/v1")
app.include_router(api_keys_router, prefix="/api/v1")
app.include_router(connections_router, prefix="/api/v1")
app.include_router(schema_router, prefix="/api/v1")
app.include_router(query_router, prefix="/api/v1")
app.include_router(rag_router, prefix="/api/v1")
app.include_router(agent_router, prefix="/api/v1")
app.include_router(sandbox_router, prefix="/api/v1")


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "environment": settings.environment}
