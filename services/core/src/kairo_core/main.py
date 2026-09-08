from fastapi import FastAPI

from . import __version__
from .components import load_component_registry
from .config import settings

app = FastAPI(title="KAIRO Core", version=__version__)


@app.get("/health")
async def health() -> dict[str, str]:
    return {
        "service": "kairo-core",
        "status": "ok",
        "version": __version__,
        "environment": settings.kairo_env,
    }


@app.get("/v1/system/components")
async def components() -> dict:
    """Expose the selected component registry; implementation status comes later."""
    return load_component_registry()


@app.get("/v1/system/architecture")
async def architecture() -> dict[str, object]:
    return {
        "canonical_state": "postgresql",
        "canonical_objects": "seaweedfs",
        "durable_execution": "temporal",
        "event_bus": "nats-jetstream",
        "derived_context_graph": "graphiti-neo4j",
        "derived_memory": "mem0",
        "model_gateway": "litellm",
        "policy_default": "deny",
    }
