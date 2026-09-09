from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    kairo_env: str = "development"
    kairo_component_registry: str = "/app/config/components.yaml"
    kairo_internal_token: str = "development-only-change-me"
    kairo_policy_signing_key: str = "development-policy-signing-change-me"
    kairo_cors_origins: str = "http://localhost:5173"
    kairo_auth_enabled: bool = True
    asset_max_bytes: int = 25 * 1024 * 1024

    database_url: str = "postgresql+asyncpg://kairo:kairo@postgres:5432/kairo"
    nats_url: str = "nats://nats:4222"
    nats_domain_stream: str = "KAIRO_DOMAIN"
    # JetStream is transport retention, not canonical history. Seven days gives consumers time to
    # recover while keeping account-erasure semantics bounded; production may shorten this but must
    # not make the stream effectively infinite without revisiting ADR-044/045/046/047.
    nats_domain_retention_seconds: int = 7 * 24 * 60 * 60
    outbox_batch_size: int = 100
    outbox_poll_interval_seconds: float = 0.5
    outbox_retry_interval_seconds: float = 2.0

    temporal_address: str = "temporal:7233"
    temporal_namespace: str = "default"
    temporal_task_queue: str = "kairo-default"

    seaweed_s3_endpoint: str = "http://seaweedfs:8333"
    seaweed_filer_endpoint: str = "http://seaweedfs:8888"

    litellm_url: str = "http://litellm:4000"

    openbao_addr: str = "http://openbao:8200"
    openbao_token: str = "development-only-change-me"

    keycloak_url: str = "http://keycloak:8080"
    keycloak_realm: str = "kairo"
    keycloak_client_id: str = "kairo-web"
    keycloak_issuer: str = "http://localhost:8081/realms/kairo"
    keycloak_jwks_url: str = "http://keycloak:8080/realms/kairo/protocol/openid-connect/certs"
    # Optional confidential workload identity for the future account-erasure state machine. It must
    # be a dedicated least-privilege Keycloak service account; never reuse the bootstrap realm admin
    # or the public Web/Desktop client. Leaving the secret empty disables management operations.
    keycloak_management_client_id: str = "kairo-identity-manager"
    keycloak_management_client_secret: str = ""

    activepieces_url: str = "http://activepieces:80"
    # Provider origins are deployment-owned rather than user-supplied so connector credentials
    # cannot turn KAIRO Core into an arbitrary HTTP client. Rotki's current API base is /api/1/.
    rotki_url: str = "http://rotki:80/api/1"

    kokoro_tts_url: str = "http://kokoro-tts:8880"
    kokoro_default_voice: str = "ff_siwis"


settings = Settings()
