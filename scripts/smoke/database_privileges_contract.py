"""Real PostgreSQL proof for provisioning, migrations, Core DML and cross-engine denials."""
import asyncio
import importlib.util
import os
from pathlib import Path
import secrets
import subprocess
import sys
from urllib.parse import urlsplit
from unittest.mock import patch

import asyncpg
from sqlalchemy.ext.asyncio import create_async_engine
from nevolium_core.production import verify_database_role
from nevolium_core import production

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('provision',ROOT/'scripts/ops/provision_database.py')
provision=importlib.util.module_from_spec(spec);spec.loader.exec_module(provision)


async def main():
    source=urlsplit(os.environ['DATABASE_URL'])
    env={'POSTGRES_USER':source.username,'POSTGRES_PASSWORD':source.password}
    for key,_ in provision.ROLES.values(): env[key]=secrets.token_hex(32)
    host=source.hostname;port=source.port or 5432
    await provision.provision(env,host,port)
    def url(role,db):
        password=env[provision.ROLES[role][0]]
        return f'postgresql+asyncpg://{role}:{password}@{host}:{port}/{db}'
    procenv={**os.environ,'NEVOLIUM_MIGRATION_DATABASE_URL':url('nevolium_migrator','nevolium')}
    result=subprocess.run([sys.executable,'-m','alembic','upgrade','head'],cwd=ROOT/'services/core',env=procenv,capture_output=True,text=True)
    assert result.returncode==0, 'restricted canonical migration failed; output withheld'
    previous=await asyncpg.connect(host=host,port=port,user=source.username,password=source.password,database='nevolium')
    await previous.execute('CREATE TABLE d03_legacy_serial (id serial PRIMARY KEY)')
    await previous.close()
    # Repeat after tables exist: exercise safe dev-schema ownership transition/idempotency.
    await provision.provision(env,host,port)
    migration=await asyncpg.connect(url('nevolium_migrator','nevolium').replace('+asyncpg',''))
    await migration.execute('CREATE TABLE d03_privilege_proof (id integer PRIMARY KEY)')
    await migration.close()
    app=await asyncpg.connect(url('nevolium_app','nevolium').replace('+asyncpg',''))
    try:
        await app.execute('INSERT INTO d03_privilege_proof VALUES (1)')
        assert await app.fetchval('SELECT count(*) FROM d03_privilege_proof')==1
        await app.execute('UPDATE d03_privilege_proof SET id=2')
        await app.execute('DELETE FROM d03_privilege_proof')
        await app.fetch('SELECT id FROM projects LIMIT 1')
        for sql in ['CREATE TABLE forbidden(id int)','DROP TABLE d03_privilege_proof','TRUNCATE d03_privilege_proof','CREATE DATABASE forbidden','SELECT * FROM alembic_version']:
            try: await app.execute(sql)
            except asyncpg.InsufficientPrivilegeError: pass
            else: raise AssertionError('forbidden DDL accepted')
    finally: await app.close()
    for role,db in [('nevolium_app','mem0'),('mem0_app','nevolium'),('keycloak_app','nevolium'),('temporal_app','nevolium')]:
        try: conn=await asyncpg.connect(url(role,db).replace('+asyncpg',''))
        except asyncpg.InvalidAuthorizationSpecificationError: pass
        except asyncpg.InsufficientPrivilegeError: pass
        else:
            await conn.close();raise AssertionError('cross-engine SQL connection accepted')
    engine=create_async_engine(url('nevolium_app','nevolium'))
    try:
        with patch.object(production,'engine',engine): await verify_database_role()
    finally: await engine.dispose()
    unsafe=create_async_engine(os.environ['DATABASE_URL'])
    try:
        with patch.object(production,'engine',unsafe):
            try: await verify_database_role()
            except RuntimeError: pass
            else: raise AssertionError('superuser passed runtime boundary')
    finally: await unsafe.dispose()
    print('PASS: real restricted migrations, runtime DML, DDL/cross-engine denials and startup privilege gate')


if __name__=='__main__': asyncio.run(main())
