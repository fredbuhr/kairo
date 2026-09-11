"""Bounded keyset pages; list response bodies remain backwards compatible."""
import base64
from datetime import datetime
import json
from typing import Annotated, Any
import uuid

from fastapi import HTTPException, Query, Response
from sqlalchemy import tuple_

PageLimit = Annotated[int, Query(ge=1, le=200)]
PageCursor = Annotated[str | None, Query(max_length=2048)]


def encode_cursor(values: list[Any]) -> str:
    return base64.urlsafe_b64encode(json.dumps(values, default=str, separators=(",", ":")).encode()).decode().rstrip("=")


def decode_cursor(value: str, length: int) -> list:
    try:
        if len(value) > 2048:
            raise ValueError()
        result = json.loads(base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True))
        if not isinstance(result, list) or len(result) != length:
            raise ValueError()
        return result
    except (ValueError, TypeError, UnicodeError) as exc:
        raise HTTPException(422, "Invalid page cursor") from exc


async def page_rows(session, statement, model, *, limit: int = 100, cursor: str | None = None,
                    response: Response | None = None, descending: bool = False,
                    key_name: str = "created_at") -> list:
    if not 1 <= limit <= 200:
        raise HTTPException(422, "Page limit must be between 1 and 200")
    key = getattr(model, key_name)
    if cursor:
        try:
            field, direction, value, raw_id = decode_cursor(cursor, 4)
            if field != key_name or direction != descending:
                raise ValueError()
            value = datetime.fromisoformat(value) if key_name == "created_at" else (int(value) if key_name == "generation" else str(value))
            if isinstance(value, datetime) and value.tzinfo is None:
                raise ValueError()
            identity = uuid.UUID(raw_id)
        except (ValueError, TypeError, AttributeError, OverflowError) as exc:
            raise HTTPException(422, "Invalid page cursor") from exc
        boundary = tuple_(key, model.id)
        statement = statement.where(boundary < (value, identity) if descending else boundary > (value, identity))
    order = (key.desc(), model.id.desc()) if descending else (key.asc(), model.id.asc())
    rows = list((await session.execute(statement.order_by(None).order_by(*order).limit(limit + 1))).scalars())
    more = len(rows) > limit
    rows = rows[:limit]
    if response is not None:
        response.headers["X-Nevolium-Next-Cursor"] = encode_cursor([
            key_name, descending, getattr(rows[-1], key_name), rows[-1].id
        ]) if more else ""
    return rows
