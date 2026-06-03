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
    if not token:
        await websocket.close(code=4001, reason="Missing authentication token")
        return

    from hashlib import sha256

    from sqlalchemy import select

    from src.db.models import ApiKey

    key_hash = sha256(token.encode()).hexdigest()

    async for session in get_db():
        result = await session.execute(
            select(ApiKey).where(
                ApiKey.key_hash == key_hash,
                ApiKey.is_active.is_(True),
            )
        )
        api_key = result.scalar_one_or_none()

        if api_key is None or str(api_key.tenant_id) != tenant_id:
            await websocket.close(code=4003, reason="Invalid or unauthorized token")
            return
        break

    await manager.connect(websocket, tenant_id)

    try:
        await websocket.send_text(json.dumps({
            "type": "connected",
            "data": {"tenant_id": tenant_id, "message": "WebSocket connected to Flux Gateway"},
        }))

        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
            except json.JSONDecodeError:
                pass

    except WebSocketDisconnect:
        manager.disconnect(websocket, tenant_id)
    except Exception:
        logger.exception("ws_error", tenant_id=tenant_id)
        manager.disconnect(websocket, tenant_id)
