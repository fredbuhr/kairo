from decimal import Decimal
from typing import Literal
from urllib.parse import urlsplit, unquote

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", hide_input_in_errors=True)

    kairo_env: Literal["development", "test", "production"] = "development"
    temporal_address: str = "temporal:7233"
    temporal_namespace: str = "default"
    temporal_task_queue: str = "kairo-default"
    kairo_worker_max_concurrent_activities: int = Field(default=16, ge=2, le=256)
    kairo_worker_max_concurrent_workflow_tasks: int = Field(default=8, ge=2, le=64)
    kairo_work_global_concurrency: int = Field(default=4, ge=1, le=128)
    kairo_document_max_concurrent: int = Field(default=1, ge=1, le=16)
    kairo_document_max_source_bytes: int = Field(default=26214400, ge=1, le=104857600)
    kairo_document_max_text_chars: int = Field(default=1000000, ge=1, le=10000000)
    kairo_document_parse_timeout_seconds: float = Field(default=180, gt=0, le=420)
    kairo_core_url: str = "http://kairo-core:8000"
    kairo_internal_token: str = "development-only-change-me"
    database_url: str = "postgresql+asyncpg://kairo:kairo@postgres:5432/kairo"
    # Empty means: derive a sibling `mem0` database from DATABASE_URL. Deployments may override
    # this when the derived vector store uses different credentials or a different PostgreSQL host.
    mem0_database_url: str = ""
    litellm_url: str = "http://litellm:4000"
    litellm_master_key: str = ""
    kairo_model_max_output_tokens: int = Field(default=4096, ge=1, le=32768)
    kairo_news_model: str = "smart"
    kairo_news_model_estimated_cost_usd: Decimal = Field(default=Decimal("0.01"), gt=0, le=Decimal("999999.999999"))
    kairo_semantic_router_model: str = "local-fast"
    kairo_semantic_router_estimated_cost_usd: Decimal = Decimal("0.002")
    searxng_url: str = "http://searxng:8080"
    nats_url: str = "nats://nats:4222"
    nats_domain_stream: str = "KAIRO_DOMAIN"
    neo4j_uri: str = "bolt://neo4j:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = ""
    kairo_memory_projector_mode: str = "auto"

    @model_validator(mode="after")
    def validate_execution_limits(self) -> "Settings":
        if self.kairo_document_max_concurrent >= self.kairo_worker_max_concurrent_activities:
            raise ValueError("Document concurrency must be lower than the Worker activity limit")
        if self.kairo_work_global_concurrency >= self.kairo_worker_max_concurrent_activities:
            raise ValueError("Global heavy-work concurrency must leave free Worker activity slots")
        if self.kairo_env == "production":
            for value in (self.kairo_internal_token, self.litellm_master_key):
                if len(value) < 32 or any(marker in value.lower() for marker in ("change_me", "change-me", "development", "kairo-dev")):
                    raise ValueError("Production Worker requires provisioned secrets")
            db = urlsplit(self.mem0_database_url)
            if db.username != "mem0_app" or db.path != "/mem0" or len(unquote(db.password or "")) < 32:
                raise ValueError("Production Worker requires an explicit restricted Mem0 SQL identity")
            if self.kairo_memory_projector_mode != "real":
                raise ValueError("Production cannot silently use stub memory projections")
        return self


settings = Settings()
