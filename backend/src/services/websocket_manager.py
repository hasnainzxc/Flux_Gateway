from __future__ import annotations

import json
from collections import defaultdict

from fastapi import WebSocket
from structlog import get_logger

logger = get_logger(__name__)


class ConnectionManager:
    def __init__(self) -> None:
        self._tenants: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, websocket: WebSocket, tenant_id: str) -> None:
        await websocket.accept()
        self._tenants[tenant_id].add(websocket)
        logger.info("ws_connected", tenant_id=tenant_id, total=len(self._tenants[tenant_id]))

    def disconnect(self, websocket: WebSocket, tenant_id: str) -> None:
        self._tenants[tenant_id].discard(websocket)
        if not self._tenants[tenant_id]:
            del self._tenants[tenant_id]
        logger.info("ws_disconnected", tenant_id=tenant_id)

    async def broadcast(self, tenant_id: str, message: dict) -> None:
        dead: list[WebSocket] = []
        payload = json.dumps(message)
        for ws in self._tenants.get(tenant_id, set()):
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._tenants[tenant_id].discard(ws)

    async def send_event_update(self, tenant_id: str, event: dict) -> None:
        await self.broadcast(tenant_id, {"type": "event", "data": event})

    async def send_agent_status(
        self, tenant_id: str, run_id: str, status: str, data: dict | None = None
    ) -> None:
        await self.broadcast(tenant_id, {
            "type": "agent_status",
            "data": {"run_id": run_id, "status": status, **(data or {})},
        })

    def tenant_count(self, tenant_id: str) -> int:
        return len(self._tenants.get(tenant_id, set()))

    def total_connections(self) -> int:
        return sum(len(conns) for conns in self._tenants.values())


manager = ConnectionManager()
