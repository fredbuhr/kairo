# Nevolium infrastructure

`compose.yaml` is the integrated development topology. It intentionally declares the broad platform early so dependencies are visible before feature implementation.

## Core services

PostgreSQL/pgvector, Neo4j, Valkey, NATS, SeaweedFS, Temporal, OpenBao, Keycloak, LiteLLM, Activepieces, SearXNG, Ollama, ntfy, ClickHouse/Langfuse and LiveKit are part of the default topology together with Nevolium Core/Worker/Realtime/Web.

## Profiles

- `finance`: rotki, Actual Budget, Hummingbot;
- `home`: Home Assistant;
- `dev-agent`: OpenHands;
- `gpu`: vLLM;
- `remote`: Headscale.

Profiles are not architectural deferrals: the components and contracts exist now, but services with security/hardware/specialist footprints are not forced onto every developer machine.

## Development bootstrap

```bash
make bootstrap
# edit .env and replace CHANGE_ME values
make config
make up
```

Use `make all` only on a machine that is intentionally prepared for every specialist profile.

## Production caveats

The development stack uses localhost bindings and development modes for several services. Production work must add pinned image digests, TLS, separate least-privilege DB roles, OpenBao unseal/storage, Keycloak realm configuration, gVisor where supported, encrypted off-host restic backups, and a private exposure model.
