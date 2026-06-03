"""WebSocket connection manager — tracks active connections per tenant, broadcasts updates."""

from __future__ import annotations

import json
from collections import defaultdict

from fastapi import WebSocket
from structlog import get_logger

logger = get_logger(__name__)


class ConnectionManager:
    """
    Manages WebSocket connections grouped by tenant.
    Supports broadcast to all connections for a tenant (e.g., event updates, agent status).
    Auto-cleans dead connections on send failure.
    """

    def __init__(self) -> None:
        # tenant_id -> set of active WebSocket connections
        self._tenants: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, websocket: WebSocket, tenant_id: str) -> None:
        """Accept WebSocket handshake + register connection for tenant."""
        await websocket.accept()
        self._tenants[tenant_id].add(websocket)
        logger.info("ws_connected", tenant_id=tenant_id, total=len(self._tenants[tenant_id]))

    def disconnect(self, websocket: WebSocket, tenant_id: str) -> None:
        """Remove WebSocket from tenant's connection set. Cleans up empty sets."""
        self._tenants[tenant_id].discard(websocket)
        if not self._tenants[tenant_id]:
            del self._tenants[tenant_id]
        logger.info("ws_disconnected", tenant_id=tenant_id)

    async def broadcast(self, tenant_id: str, message: dict) -> None:
        """Send message to all active connections for tenant. Removes dead connections."""
        dead: list[WebSocket] = []
        payload = json.dumps(message)
        for ws in self._tenants.get(tenant_id, set()):
            try:
                await ws.send_text(payload)
            except Exception:
                # Connection died mid-send — mark for cleanup
                dead.append(ws)
        # Clean up dead connections after iteration (can't modify set during iteration)
        for ws in dead:
            self._tenants[tenant_id].discard(ws)

    async def send_event_update(self, tenant_id: str, event: dict) -> None:
        """Broadcast event update to all tenant connections."""
        await self.broadcast(tenant_id, {"type": "event", "data": event})

    async def send_agent_status(
        self, tenant_id: str, run_id: str, status: str, data: dict | None = None
    ) -> None:
        """Broadcast agent run status (started/completed/failed) to tenant."""
        await self.broadcast(tenant_id, {
            "type": "agent_status",
            "data": {"run_id": run_id, "status": status, **(data or {})},
        })

    def tenant_count(self, tenant_id: str) -> int:
        """Active connection count for tenant."""
        return len(self._tenants.get(tenant_id, set()))

    def total_connections(self) -> int:
        """Total active connections across all tenants."""
        return sum(len(conns) for conns in self._tenants.values())


# Singleton — imported by ws.py + workers
manager = ConnectionManager()
