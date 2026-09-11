"""Verify real database privileges before accepting production traffic."""
from sqlalchemy import text
from .db import engine


async def verify_database_role() -> None:
    async with engine.connect() as conn:
        safe = await conn.scalar(text("""
            SELECT current_user = 'kairo_app' AND NOT rolsuper AND NOT rolcreatedb
              AND NOT rolcreaterole AND NOT rolreplication AND NOT rolbypassrls
              AND NOT has_schema_privilege(current_user, 'public', 'CREATE')
              AND NOT has_database_privilege(current_user, current_database(), 'CREATE')
            FROM pg_roles WHERE rolname = current_user
        """))
        if not safe:
            raise RuntimeError('Production refuses an overprivileged Core SQL identity')
