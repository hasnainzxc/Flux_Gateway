"""Behavior rule engine — match event payloads against tenant-defined conditions."""

from __future__ import annotations

import operator
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from src.db.models.event import BehaviorRule

logger = get_logger(__name__)

# Supported comparison operators for rule conditions
OPERATORS = {
    "eq": operator.eq,
    "ne": operator.ne,
    "gt": operator.gt,
    "gte": operator.ge,
    "lt": operator.lt,
    "lte": operator.le,
    "contains": lambda a, b: b in a,
    "not_contains": lambda a, b: b not in a,
    "in": lambda a, b: a in b,
    "starts_with": lambda a, b: str(a).startswith(str(b)),
}


def _resolve_path(payload: dict[str, Any], path: str) -> Any:
    """Walk nested dict using dot-notation path (e.g., 'user.email'). Returns None if missing."""
    # Split "user.address.city" -> ["user", "address", "city"], traverse each level
    parts = path.split(".")
    current: Any = payload
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None  # hit a non-dict — path doesn't exist
    return current


def evaluate_conditions(conditions: dict[str, Any], payload: dict[str, Any]) -> bool:
    """
    Check if payload matches all conditions. Supports:
    - Direct equality: {"field": "value"}
    - Operator dict: {"field": {"gt": 10, "lt": 100}}
    Empty conditions = always match (wildcard rule).
    """
    if not conditions:
        return True

    for field_path, rule in conditions.items():
        value = _resolve_path(payload, field_path)
        if isinstance(rule, dict):
            # Operator-based comparison
            for op_name, expected in rule.items():
                op_fn = OPERATORS.get(op_name)
                if op_fn is None or not op_fn(value, expected):
                    return False
        else:
            # Direct equality
            if value != rule:
                return False
    return True


async def match_rules(
    session: AsyncSession,
    tenant_id: str,
    event_type: str,
    payload: dict[str, Any],
) -> list[BehaviorRule]:
    """
    Fetch active rules for tenant+event_type, evaluate each against payload.
    Returns matched rules sorted by priority (highest first).
    """
    result = await session.execute(
        select(BehaviorRule)
        .where(
            BehaviorRule.tenant_id == tenant_id,
            BehaviorRule.event_type == event_type,
            BehaviorRule.is_active.is_(True),
        )
        .order_by(BehaviorRule.priority.desc())
    )
    rules = list(result.scalars().all())

    matched: list[BehaviorRule] = []
    for rule in rules:
        if evaluate_conditions(rule.conditions, payload):
            matched.append(rule)
            logger.info(
                "rule_matched",
                rule_id=str(rule.id),
                rule_name=rule.name,
                tenant_id=tenant_id,
            )
    return matched
