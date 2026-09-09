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

    activepieces_url: str = "http://activepieces:80"

    kokoro_tts_url: str = "http://kokoro-tts:8880"
    kokoro_default_voice: str = "ff_siwis"


settings = Settings()
