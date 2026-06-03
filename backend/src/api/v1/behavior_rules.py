"""Behavior rules CRUD — configure event matching conditions + actions."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import authenticate
from src.db.models.event import BehaviorRule
from src.db.session import get_db

router = APIRouter(prefix="/behavior-rules", tags=["behavior-rules"])


class RuleCreate(BaseModel):
    name: str
    event_type: str
    conditions: dict[str, Any] = {}
    action_type: str
    action_config: dict[str, Any] = {}
    priority: int = 50


class RuleUpdate(BaseModel):
    name: str | None = None
    event_type: str | None = None
    conditions: dict[str, Any] | None = None
    action_type: str | None = None
    action_config: dict[str, Any] | None = None
    priority: int | None = None
    is_active: bool | None = None


@router.get("")
async def list_rules(
    tenant_id: str = Depends(authenticate),
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    result = await session.execute(
        select(BehaviorRule)
        .where(BehaviorRule.tenant_id == tenant_id)
        .order_by(BehaviorRule.priority.desc())
    )
    rules = result.scalars().all()
    return [
        {
            "id": str(r.id),
            "name": r.name,
            "event_type": r.event_type,
            "conditions": r.conditions,
            "action_type": r.action_type,
            "action_config": r.action_config,
            "priority": r.priority,
            "is_active": r.is_active,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rules
    ]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_rule(
    data: RuleCreate,
    tenant_id: str = Depends(authenticate),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    rule = BehaviorRule(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        name=data.name,
        event_type=data.event_type,
        conditions=data.conditions,
        action_type=data.action_type,
        action_config=data.action_config,
        priority=data.priority,
        is_active=True,
    )
    session.add(rule)
    await session.commit()
    await session.refresh(rule)

    return {
        "id": str(rule.id),
        "name": rule.name,
        "event_type": rule.event_type,
        "conditions": rule.conditions,
        "action_type": rule.action_type,
        "action_config": rule.action_config,
        "priority": rule.priority,
        "is_active": rule.is_active,
    }


@router.patch("/{rule_id}")
async def update_rule(
    rule_id: uuid.UUID,
    data: RuleUpdate,
    tenant_id: str = Depends(authenticate),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    result = await session.execute(
        select(BehaviorRule).where(
            BehaviorRule.id == rule_id,
            BehaviorRule.tenant_id == tenant_id,
        )
    )
    rule = result.scalar_one_or_none()
    if rule is None:
        raise HTTPException(status_code=404, detail="Rule not found")

    if data.name is not None:
        rule.name = data.name
    if data.event_type is not None:
        rule.event_type = data.event_type
    if data.conditions is not None:
        rule.conditions = data.conditions
    if data.action_type is not None:
        rule.action_type = data.action_type
    if data.action_config is not None:
        rule.action_config = data.action_config
    if data.priority is not None:
        rule.priority = data.priority
    if data.is_active is not None:
        rule.is_active = data.is_active

    await session.commit()
    await session.refresh(rule)

    return {
        "id": str(rule.id),
        "name": rule.name,
        "event_type": rule.event_type,
        "conditions": rule.conditions,
        "action_type": rule.action_type,
        "action_config": rule.action_config,
        "priority": rule.priority,
        "is_active": rule.is_active,
    }


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule(
    rule_id: uuid.UUID,
    tenant_id: str = Depends(authenticate),
    session: AsyncSession = Depends(get_db),
) -> None:
    result = await session.execute(
        select(BehaviorRule).where(
            BehaviorRule.id == rule_id,
            BehaviorRule.tenant_id == tenant_id,
        )
    )
    rule = result.scalar_one_or_none()
    if rule is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    await session.delete(rule)
    await session.commit()
