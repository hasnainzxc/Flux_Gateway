"""OIDC login flow — redirect to provider, handle callback, mint JWT, auto-provision tenant."""

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
    """Redirect user to OIDC provider's authorization page."""
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
    """
    OIDC callback — exchange code for tokens, fetch userinfo, auto-provision tenant+user
    on first login, mint our own JWT for subsequent API calls.
    """
    token_response = await exchange_code_for_tokens(code, redirect_uri)
    # Some providers put ID token in "id_token", others in "access_token"
    id_token = token_response["access_token"]

    # Fetch user profile from OIDC provider — email + sub are guaranteed by spec
    userinfo = await get_userinfo(id_token)
    email = userinfo["email"]
    oidc_sub = userinfo["sub"]  # unique subject identifier from provider
    display_name = userinfo.get("name", email)

    # Check if user already exists by OIDC subject — prevents duplicate accounts
    result = await session.execute(select(User).where(User.oidc_sub == oidc_sub))
    user = result.scalar_one_or_none()

    if user is None:
        # JIT provisioning — first login auto-creates tenant + user
        # TODO: slug collision possible if two users share email prefix
        tenant = Tenant(
            name=display_name,
            slug=email.split("@")[0],  # derive slug from email local part
        )
        session.add(tenant)
        await session.flush()  # flush to get tenant.id before creating user

        user = User(
            tenant_id=tenant.id,
            email=email,
            oidc_sub=oidc_sub,
            display_name=display_name,
            role="admin",  # first user in tenant is always admin
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
    else:
        # Existing user — just commit (no-op, but keeps session clean)
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
