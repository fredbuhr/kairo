from decimal import Decimal
from typing import Literal
from urllib.parse import urlsplit, unquote

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)

    kairo_env: Literal["development", "test", "production"] = "development"
    kairo_component_registry: str = "/app/config/components.yaml"
    kairo_internal_token: str = "development-only-change-me"
    kairo_operations_token: str = "development-operations-change-me"
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

    keycloak_audience: str = "kairo-core"
    keycloak_client_id: str = "kairo-web"
    keycloak_issuer: str = "http://localhost:8081/realms/kairo"
    keycloak_jwks_url: str = "http://keycloak:8080/realms/kairo/protocol/openid-connect/certs"

    kokoro_tts_url: str = "http://kokoro-tts:8880"
    kokoro_default_voice: str = "ff_siwis"

    @model_validator(mode="after")
    def production_boundary(self) -> "Settings":
        if self.kairo_env != "production":
            return self
        if not self.kairo_auth_enabled:
            raise ValueError("Production requires authentication")
        db = urlsplit(self.database_url)
        secrets = (self.kairo_internal_token, self.kairo_policy_signing_key, self.openbao_token, self.kairo_operations_token, unquote(db.password or ""))
        for value in secrets:
            if len(value) < 32 or any(marker in value.lower() for marker in ("change_me", "change-me", "development", "kairo-dev")):
                raise ValueError("Production requires distinct provisioned secrets of at least 32 characters")
        if len(set(secrets)) != len(secrets):
            raise ValueError("Production secrets must be distinct")
        db = urlsplit(self.database_url)
        if db.username != "kairo_app" or len(unquote(db.password or "")) < 32:
            raise ValueError("Production Core requires the restricted kairo_app SQL identity")
        for value in [self.keycloak_issuer, *self.kairo_cors_origins.split(",")]:
            url = urlsplit(value.strip())
            if url.scheme != "https" or not url.hostname or "*" in value or url.username or url.password:
                raise ValueError("Production issuer and CORS origins must be explicit HTTPS URLs")
        if not self.keycloak_audience or not self.keycloak_client_id:
            raise ValueError("Production requires JWT audience and authorized party")
        return self


settings = Settings()
