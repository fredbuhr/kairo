from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    kairo_env: str = "development"
    kairo_component_registry: str = "/app/config/components.yaml"
    kairo_internal_token: str = "development-only-change-me"
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
    litellm_url: str = "http://litellm:4000"
    openbao_addr: str = "http://openbao:8200"
    keycloak_url: str = "http://keycloak:8080"


settings = Settings()
