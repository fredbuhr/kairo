from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    temporal_address: str = "temporal:7233"
    temporal_namespace: str = "default"
    temporal_task_queue: str = "kairo-default"
    kairo_core_url: str = "http://kairo-core:8000"
    kairo_internal_token: str = "development-only-change-me"
    litellm_url: str = "http://litellm:4000"
    nats_url: str = "nats://nats:4222"


settings = Settings()
