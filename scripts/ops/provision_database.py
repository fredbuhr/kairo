#!/usr/bin/env python3
"""Explicit SQL provisioning/rotation, run with services stopped and a verified backup.

Uses existing admin credentials; never emits passwords or SQL. No canonical data is deleted.
Migrations use kairo_migrator; runtime KAIRO gets DML only. Each engine owns only its own DB.
"""
import argparse
import asyncio
import os

import asyncpg
from dotenv import dotenv_values

ROLES = {
    "kairo_migrator": ("KAIRO_MIGRATOR_PASSWORD", ["kairo"]),
    "kairo_app": ("KAIRO_DATABASE_PASSWORD", []),
    "mem0_app": ("MEM0_DATABASE_PASSWORD", ["mem0"]),
    "keycloak_app": ("KEYCLOAK_DATABASE_PASSWORD", ["keycloak"]),
    "temporal_app": ("TEMPORAL_DATABASE_PASSWORD", ["temporal", "temporal_visibility"]),
    "litellm_app": ("LITELLM_DATABASE_PASSWORD", ["litellm"]),
    "langfuse_app": ("LANGFUSE_DATABASE_PASSWORD", ["langfuse"]),
    "activepieces_app": ("ACTIVEPIECES_DATABASE_PASSWORD", ["activepieces"]),
}


def literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def ident(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


async def provision(env: dict, host: str, port: int) -> None:
    for key, _ in ROLES.values():
        value = env.get(key, "")
        if len(value) < 32 or "change" in value.lower():
            raise ValueError(f"Provision a strong {key} before SQL setup")
    passwords = [env[key] for key, _ in ROLES.values()]
    if len(set(passwords)) != len(passwords) or env['POSTGRES_PASSWORD'] in passwords:
        raise ValueError("Each database identity requires a distinct password")
    args = dict(host=host, port=port, user=env['POSTGRES_USER'], password=env['POSTGRES_PASSWORD'])
    admin = await asyncpg.connect(**args, database='postgres')
    try:
        # All identities must exist before granting runtime access to the first database.
        for role in ROLES:
            if not await admin.fetchval('SELECT 1 FROM pg_roles WHERE rolname=$1', role):
                await admin.execute(f'CREATE ROLE {role}')
        for role, (key, databases) in ROLES.items():
            if not await admin.fetchval('SELECT 1 FROM pg_roles WHERE rolname=$1', role):
                await admin.execute(f'CREATE ROLE {role}')
            await admin.execute(f'ALTER ROLE {role} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS NOINHERIT PASSWORD {literal(env[key])}')
            memberships = await admin.fetch('SELECT r.rolname FROM pg_auth_members m JOIN pg_roles r ON r.oid=m.roleid JOIN pg_roles u ON u.oid=m.member WHERE u.rolname=$1', role)
            for member in memberships:
                await admin.execute(f'REVOKE {ident(member["rolname"])} FROM {role}')
            for db in databases:
                if not await admin.fetchval('SELECT 1 FROM pg_database WHERE datname=$1', db):
                    await admin.execute(f'CREATE DATABASE {db} OWNER {role}')
                await admin.execute(f'ALTER DATABASE {db} OWNER TO {role}')
                await admin.execute(f'REVOKE ALL ON DATABASE {db} FROM PUBLIC')
                conn = await asyncpg.connect(**args, database=db)
                try:
                    await conn.execute('REVOKE ALL ON SCHEMA public FROM PUBLIC')
                    await conn.execute(f'ALTER SCHEMA public OWNER TO {role}')
                    if db in {'kairo', 'mem0'}:
                        await conn.execute('CREATE EXTENSION IF NOT EXISTS vector')
                    if db == 'kairo':
                        await conn.execute('CREATE EXTENSION IF NOT EXISTS pgcrypto')
                    # Upgrade existing development schemas without REASSIGN OWNED (which also
                    # changes shared database ownership). Exclude extension-managed objects.
                    rows = await conn.fetch("SELECT c.relname, c.relkind FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind IN ('r','p','S','v','m') AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.objid=c.oid AND d.deptype='e')")
                    for row in rows:
                        kind = {'S':'SEQUENCE','v':'VIEW','m':'MATERIALIZED VIEW'}.get(row['relkind'], 'TABLE')
                        await conn.execute(f'ALTER {kind} public.{ident(row["relname"])} OWNER TO {role}')
                    if db == 'kairo':
                        await conn.execute('GRANT CONNECT ON DATABASE kairo TO kairo_app')
                        await conn.execute('GRANT USAGE ON SCHEMA public TO kairo_app')
                        await conn.execute('GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO kairo_app')
                        await conn.execute('GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO kairo_app')
                        await conn.execute('ALTER DEFAULT PRIVILEGES FOR ROLE kairo_migrator IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO kairo_app')
                        await conn.execute('ALTER DEFAULT PRIVILEGES FOR ROLE kairo_migrator IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO kairo_app')
                finally:
                    await conn.close()
        # Restrict default utility databases too; no service needs cross-engine connections.
        await admin.execute('REVOKE CONNECT ON DATABASE postgres FROM PUBLIC')
        await admin.execute('REVOKE CONNECT ON DATABASE template1 FROM PUBLIC')
    finally:
        await admin.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file', required=True)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=5432)
    args = parser.parse_args()
    env = {**dotenv_values(args.env_file), **os.environ}
    try:
        asyncio.run(provision(env, args.host, args.port))
    except Exception as exc:
        raise SystemExit(f'SQL provisioning failed ({type(exc).__name__}); credentials/SQL withheld') from None
    print('SQL identities provisioned; run canonical migrations before starting Core')


if __name__ == '__main__':
    main()
