"""Sandbox execution endpoint — validate SQL or run code in Docker isolation."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from src.api.deps import require_tenant
from src.core.security_middleware import check_rate_limit
from src.services.sandbox import sandbox_service

router = APIRouter(prefix="/sandbox", tags=["sandbox"])


class SandboxExecuteRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=50000)
    language: str = Field(default="python", pattern="^(python)$")
    schema_graph: dict | None = Field(default=None)

    model_config = {"extra": "forbid"}


class SandboxExecuteResponse(BaseModel):
    passed: bool
    errors: list[str] = []
    output: str = ""

    model_config = {"extra": "allow"}


@router.post("/execute", response_model=SandboxExecuteResponse)
async def sandbox_execute(
    payload: SandboxExecuteRequest,
    request: Request,
    tenant_id: str = Depends(require_tenant),
) -> SandboxExecuteResponse:
    await check_rate_limit(tenant_id)

    # If schema provided, validate SQL against it (DDL/injection checks).
    # Otherwise, execute code in sandboxed Docker container.
    if payload.schema_graph:
        result = await sandbox_service.validate_sql(
            tenant_id, payload.code, payload.schema_graph
        )
    else:
        result = await sandbox_service.execute_code(
            tenant_id, payload.code, payload.language
        )

    return SandboxExecuteResponse(
        passed=result.passed,
        errors=result.errors,
        output=result.stdout,
    )
