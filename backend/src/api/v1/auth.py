from __future__ import annotations

from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.oidc import (
    create_access_token,
    exchange_code_for_tokens,
    get_userinfo,
    oidc_config,
)
from src.db.models import Tenant, User
from src.db.session import get_db

router = APIRouter(prefix="/auth", tags=["auth"])


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    tenant_id: str
    email: str
    display_name: str


@router.get("/login")
async def login(
    redirect_uri: str = Query(..., description="Frontend callback URL"),
) -> RedirectResponse:
    auth_endpoint = await oidc_config.get_authorization_endpoint()
    params = {
        "client_id": settings.oidc_client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "scope": "openid email profile",
    }
    return RedirectResponse(f"{auth_endpoint}?{urlencode(params)}")


@router.get("/callback", response_model=AuthResponse)
async def callback(
    code: str = Query(...),
    redirect_uri: str = Query(...),
    session: AsyncSession = Depends(get_db),
) -> AuthResponse:
    token_response = await exchange_code_for_tokens(code, redirect_uri)
    id_token = token_response["access_token"]

    userinfo = await get_userinfo(id_token)
    email = userinfo["email"]
    oidc_sub = userinfo["sub"]
    display_name = userinfo.get("name", email)

    result = await session.execute(select(User).where(User.oidc_sub == oidc_sub))
    user = result.scalar_one_or_none()

    if user is None:
        tenant = Tenant(
            name=display_name,
            slug=email.split("@")[0],
        )
        session.add(tenant)
        await session.flush()

        user = User(
            tenant_id=tenant.id,
            email=email,
            oidc_sub=oidc_sub,
            display_name=display_name,
            role="admin",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
    else:
        await session.commit()

    jwt_token = create_access_token(
        tenant_id=str(user.tenant_id),
        user_id=str(user.id),
        email=user.email,
    )

    return AuthResponse(
        access_token=jwt_token,
        user_id=str(user.id),
        tenant_id=str(user.tenant_id),
        email=user.email,
        display_name=user.display_name,
    )
