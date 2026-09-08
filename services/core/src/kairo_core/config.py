from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    kairo_env: str = "development"
    kairo_component_registry: str = "/app/config/components.yaml"
    database_url: str = "postgresql+asyncpg://kairo:kairo@postgres:5432/kairo"
    nats_url: str = "nats://nats:4222"
    temporal_address: str = "temporal:7233"
    seaweed_s3_endpoint: str = "http://seaweedfs:8333"
    litellm_url: str = "http://litellm:4000"
    openbao_addr: str = "http://openbao:8200"
    keycloak_url: str = "http://keycloak:8080"


settings = Settings()
