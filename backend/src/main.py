"""Flux Gateway — FastAPI app entrypoint. Wires routers, middleware, lifespan hooks."""

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
from src.api.v1.behavior_rules import router as behavior_rules_router
from src.api.v1.connections import router as connections_router
from src.api.v1.events import router as events_router
from src.api.v1.query import router as query_router
from src.api.v1.rag import router as rag_router
from src.api.v1.sandbox import router as sandbox_router
from src.api.v1.schema_endpoints import router as schema_router
from src.api.v1.usage import router as usage_router
from src.api.v1.webhooks import router as webhooks_router
from src.api.v1.ws import router as ws_router
from src.core.config import settings

logger = get_logger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Inject OWASP-recommended security headers into every response."""

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        response = await call_next(request)
        # Prevent MIME sniffing, clickjacking, and enforce HTTPS
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        # HSTS: tell browsers to only use HTTPS for 1 year
        response.headers["Strict-Transport-Security"] = "max-age=31536000"
        # Block Flash/cross-domain policy files — no legacy plugin support needed
        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
        # Only send origin (not full URL) in referrer to avoid leaking query params
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup/shutdown hook — eagerly init Redis pool, bootstrap dev tenant, tear down on exit."""
    logger.info("flux gateway starting", environment=settings.environment)
    from src.core.redis_client import get_redis
    await get_redis()
    await _bootstrap_dev_tenant()
    yield
    from src.core.redis_client import close_redis
    await close_redis()
    logger.info("flux gateway shutting down")


async def _bootstrap_dev_tenant() -> None:
    """Create default tenant + API key if none exist — for local dev without OIDC."""
    import uuid
    from hashlib import sha256

    from sqlalchemy import select

    from src.db.models import ApiKey, Tenant
    from src.db.session import async_session_factory

    async with async_session_factory() as session:
        result = await session.execute(select(Tenant).limit(1))
        if result.scalar_one_or_none() is not None:
            return

        tenant = Tenant(
            id=uuid.uuid4(),
            name="Dev Tenant",
            slug="dev",
        )
        session.add(tenant)
        await session.flush()

        import secrets
        raw_key = f"sk-{secrets.token_hex(32)}"
        key_hash = sha256(raw_key.encode()).hexdigest()
        api_key = ApiKey(
            tenant_id=tenant.id,
            name="Dev Bootstrap Key",
            key_hash=key_hash,
            key_prefix=raw_key[:10],
        )
        session.add(api_key)
        await session.commit()

        logger.info("dev bootstrap complete", tenant_id=str(tenant.id), api_key=raw_key)
        print(f"\n{'='*60}")
        print(f"  DEV API KEY: {raw_key}")
        print(f"  Tenant ID:   {tenant.id}")
        print("  Paste this key into Settings → API Keys to get started")
        print(f"{'='*60}\n")


app = FastAPI(
    title="Flux Gateway",
    description="Data-to-Agent Gateway — secure B2B SaaS platform",
    version="0.1.0",
    lifespan=lifespan,
)

# NOTE: middleware order matters — outermost runs last on response
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    # TODO: tighten allow_origins for production — currently dev-only
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# All REST routers mounted under /api/v1 — WebSocket lives at root /ws/{tenant_id}
app.include_router(auth_router, prefix="/api/v1")
app.include_router(api_keys_router, prefix="/api/v1")
app.include_router(connections_router, prefix="/api/v1")
app.include_router(schema_router, prefix="/api/v1")
app.include_router(query_router, prefix="/api/v1")
app.include_router(rag_router, prefix="/api/v1")
app.include_router(agent_router, prefix="/api/v1")
app.include_router(sandbox_router, prefix="/api/v1")
app.include_router(events_router, prefix="/api/v1")
app.include_router(webhooks_router, prefix="/api/v1")
app.include_router(behavior_rules_router, prefix="/api/v1")
app.include_router(usage_router, prefix="/api/v1")
# WS router has no prefix — mounts at /ws/{tenant_id} directly
app.include_router(ws_router)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Liveness probe for k8s/load balancers. No DB check — keep it fast."""
    return {"status": "ok", "environment": settings.environment}
