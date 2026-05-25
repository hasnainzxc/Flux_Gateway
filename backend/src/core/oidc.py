from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from fastapi import HTTPException, status

from src.core.config import settings


class OIDCConfig:
    def __init__(self) -> None:
        self._discovery: dict[str, Any] | None = None

    async def _fetch_discovery(self) -> dict[str, Any]:
        if self._discovery is not None:
            return self._discovery
        url = f"{settings.oidc_issuer}/.well-known/openid-configuration"
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            response.raise_for_status()
            self._discovery = response.json()
            return self._discovery

    async def get_authorization_endpoint(self) -> str:
        discovery = await self._fetch_discovery()
        return str(discovery["authorization_endpoint"])

    async def get_token_endpoint(self) -> str:
        discovery = await self._fetch_discovery()
        return str(discovery["token_endpoint"])

    async def get_jwks_uri(self) -> str:
        discovery = await self._fetch_discovery()
        return str(discovery["jwks_uri"])

    async def get_userinfo_endpoint(self) -> str:
        discovery = await self._fetch_discovery()
        return str(discovery["userinfo_endpoint"])


oidc_config = OIDCConfig()


def create_access_token(tenant_id: str, user_id: str, email: str) -> str:
    from jose import jwt

    payload = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "email": email,
        "exp": datetime.now(UTC) + timedelta(hours=24),
        "iat": datetime.now(UTC),
    }
    return str(jwt.encode(payload, settings.secret_key, algorithm="HS256"))


def decode_access_token(token: str) -> dict[str, Any]:
    from jose import JWTError, jwt

    try:
        result: dict[str, Any] = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        return result
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from None


async def exchange_code_for_tokens(code: str, redirect_uri: str) -> dict[str, Any]:
    token_endpoint = await oidc_config.get_token_endpoint()
    async with httpx.AsyncClient() as client:
        response = await client.post(
            token_endpoint,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "client_id": settings.oidc_client_id,
                "client_secret": settings.oidc_client_secret,
            },
        )
        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Failed to exchange authorization code",
            )
        result: dict[str, Any] = response.json()
        return result


async def get_userinfo(access_token: str) -> dict[str, Any]:
    userinfo_endpoint = await oidc_config.get_userinfo_endpoint()
    async with httpx.AsyncClient() as client:
        response = await client.get(
            userinfo_endpoint,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        response.raise_for_status()
        result: dict[str, Any] = response.json()
        return result
