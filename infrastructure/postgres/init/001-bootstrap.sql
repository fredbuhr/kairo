-- Development bootstrap only. Production uses managed migrations and separate least-privilege roles.

SELECT 'CREATE DATABASE keycloak'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'keycloak')\gexec

SELECT 'CREATE DATABASE activepieces'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'activepieces')\gexec

SELECT 'CREATE DATABASE langfuse'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'langfuse')\gexec

SELECT 'CREATE DATABASE litellm'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'litellm')\gexec

-- Mem0 is a derived projection, so it gets a separate database rather than writing its vector
-- tables into KAIRO's canonical schema. The entire database may be dropped and rebuilt from Core.
SELECT 'CREATE DATABASE mem0'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'mem0')\gexec

\connect kairo
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

\connect mem0
CREATE EXTENSION IF NOT EXISTS vector;
