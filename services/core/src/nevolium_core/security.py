import secrets
from typing import Annotated

from fastapi import Header, HTTPException, status

from .config import settings


async def require_internal_token(
    x_nevolium_internal_token: Annotated[str | None, Header()] = None,
) -> None:
    expected = settings.nevolium_internal_token
    if not x_nevolium_internal_token or not secrets.compare_digest(x_nevolium_internal_token.encode(), expected.encode()):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid internal token")


async def require_operations_token(
    x_nevolium_internal_token: Annotated[str | None, Header()] = None,
) -> None:
    expected = settings.nevolium_operations_token if settings.nevolium_env == "production" else settings.nevolium_internal_token
    if not x_nevolium_internal_token or not secrets.compare_digest(x_nevolium_internal_token.encode(), expected.encode()):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Operations token required")
