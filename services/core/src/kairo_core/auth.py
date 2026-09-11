from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

from .config import settings

_bearer = HTTPBearer(auto_error=False)
_jwks_client = PyJWKClient(settings.keycloak_jwks_url, cache_keys=True, lifespan=300, timeout=5)


@dataclass(frozen=True, slots=True)
class Principal:
    subject: str
    username: str | None
    email: str | None
    roles: frozenset[str]
    claims: dict[str, Any]

    def has_role(self, role: str) -> bool:
        return role in self.roles


def _decode_token(token: str) -> Principal:
    if len(token) > 16384:
        raise jwt.InvalidTokenError("Oversized token")
    signing_key = _jwks_client.get_signing_key_from_jwt(token)
    claims = jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        issuer=settings.keycloak_issuer,
        audience=settings.keycloak_audience,
        options={"require": ["exp", "iat", "sub", "iss", "aud", "azp", "typ"]},
    )

    authorized_party = claims.get("azp")
    if authorized_party != settings.keycloak_client_id:
        raise jwt.InvalidTokenError("Token was issued to another Keycloak client")

    if claims.get("typ") != "Bearer" or not isinstance(claims["sub"], str) or not claims["sub"].strip():
        raise jwt.InvalidTokenError("An access token with a nonempty subject is required")
    realm_access = claims.get("realm_access", {})
    if not isinstance(realm_access, dict):
        raise jwt.InvalidTokenError("Invalid role claims")
    role_values = realm_access.get("roles", [])
    if not isinstance(role_values, list) or any(not isinstance(role, str) for role in role_values):
        raise jwt.InvalidTokenError("Invalid role claims")
    roles = frozenset(role_values)
    return Principal(
        subject=str(claims["sub"]),
        username=str(claims.get("preferred_username")) if claims.get("preferred_username") else None,
        email=str(claims.get("email")) if claims.get("email") else None,
        roles=roles,
        claims=dict(claims),
    )


async def require_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> Principal:
    if not settings.kairo_auth_enabled:
        return Principal(
            subject="development-user",
            username="development-user",
            email=None,
            roles=frozenset({"kairo-user"}),
            claims={"auth_mode": "disabled"},
        )

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        return await asyncio.to_thread(_decode_token, credentials.credentials)
    except (jwt.PyJWTError, OSError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or unverifiable Keycloak token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


async def require_kairo_user(principal: Principal = Depends(require_principal)) -> Principal:
    if settings.kairo_auth_enabled and not (
        principal.has_role("kairo-user") or principal.has_role("kairo-admin")
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="KAIRO user role required")
    return principal


async def require_kairo_admin(principal: Principal = Depends(require_principal)) -> Principal:
    if settings.kairo_auth_enabled and not principal.has_role("kairo-admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="KAIRO admin role required")
    return principal
