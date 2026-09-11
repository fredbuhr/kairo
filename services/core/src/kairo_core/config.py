from decimal import Decimal

from pydantic import Field
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
    database_pool_size: int = Field(default=5, ge=1, le=50)
    database_max_overflow: int = Field(default=5, ge=0, le=50)
    database_pool_timeout: float = Field(default=10, gt=0, le=60)
    kairo_model_global_concurrency: int = Field(default=8, ge=1, le=256)
    kairo_model_owner_concurrency: int = Field(default=2, ge=1, le=64)
    kairo_model_global_daily_budget_usd: Decimal = Field(default=Decimal("50"), ge=0)
    kairo_model_owner_daily_budget_usd: Decimal = Field(default=Decimal("10"), ge=0)
    kairo_work_global_concurrency: int = Field(default=4, ge=1, le=128)
    kairo_work_owner_concurrency: int = Field(default=1, ge=1, le=16)
    kairo_work_max_pending: int = Field(default=1000, ge=1, le=10000)
    kairo_work_owner_max_pending: int = Field(default=100, ge=1, le=1000)
    outbox_max_pending: int = Field(default=10000, ge=100, le=100000)
    outbox_payload_max_bytes: int = Field(default=65536, ge=1024, le=1048576)
    outbox_retention_days: int = Field(default=30, ge=1, le=365)
    maintenance_batch_size: int = Field(default=500, ge=1, le=1000)
    nats_domain_max_age_seconds: int = Field(default=1209600, ge=60, le=31536000)
    nats_domain_max_bytes: int = Field(default=268435456, ge=1048576)
    nats_url: str = "nats://nats:4222"
    nats_domain_stream: str = "KAIRO_DOMAIN"
    outbox_batch_size: int = Field(default=20, ge=1, le=20)
    outbox_poll_interval_seconds: float = 0.5
    outbox_retry_interval_seconds: float = 2.0

    temporal_address: str = "temporal:7233"
    temporal_namespace: str = "default"
    temporal_task_queue: str = "kairo-default"

    seaweed_filer_endpoint: str = "http://seaweedfs:8888"

    openbao_addr: str = "http://openbao:8200"
    openbao_token: str = "development-only-change-me"

    keycloak_client_id: str = "kairo-web"
    keycloak_issuer: str = "http://localhost:8081/realms/kairo"
    keycloak_jwks_url: str = "http://keycloak:8080/realms/kairo/protocol/openid-connect/certs"

    kokoro_tts_url: str = "http://kokoro-tts:8880"
    kokoro_default_voice: str = "ff_siwis"


settings = Settings()
