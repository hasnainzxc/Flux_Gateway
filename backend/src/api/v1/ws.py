"""WebSocket endpoint for real-time event/agent status streaming."""

from __future__ import annotations

import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from structlog import get_logger

from src.db.session import get_db
from src.services.websocket_manager import manager

logger = get_logger(__name__)

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/{tenant_id}")
async def websocket_endpoint(websocket: WebSocket, tenant_id: str, token: str = "") -> None:
    # WS auth: token passed as query param (WS can't use Authorization header easily)
    if not token:
        await websocket.close(code=4001, reason="Missing authentication token")
        return

    from hashlib import sha256

    from sqlalchemy import select

    from src.db.models import ApiKey

    # Only API key auth supported for WS — JWT not implemented here
    key_hash = sha256(token.encode()).hexdigest()

    async for session in get_db():
        result = await session.execute(
            select(ApiKey).where(
                ApiKey.key_hash == key_hash,
                ApiKey.is_active.is_(True),
            )
        )
        api_key = result.scalar_one_or_none()

        # Verify key exists AND belongs to the tenant in the URL path
        if api_key is None or str(api_key.tenant_id) != tenant_id:
            await websocket.close(code=4003, reason="Invalid or unauthorized token")
            return
        break

    # Register connection in manager — enables broadcast to this tenant
    await manager.connect(websocket, tenant_id)

    try:
        # Send connection confirmation
        await websocket.send_text(json.dumps({
            "type": "connected",
            "data": {"tenant_id": tenant_id, "message": "WebSocket connected to Flux Gateway"},
        }))

        # Keep-alive loop — respond to pings, ignore other messages
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
            except json.JSONDecodeError:
                pass  # silently ignore malformed messages

    except WebSocketDisconnect:
        manager.disconnect(websocket, tenant_id)
    except Exception:
        logger.exception("ws_error", tenant_id=tenant_id)
        manager.disconnect(websocket, tenant_id)
