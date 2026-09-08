from pathlib import Path
from typing import Any

import yaml

from .config import settings


def load_component_registry() -> dict[str, Any]:
    path = Path(settings.kairo_component_registry)
    if not path.exists():
        return {"version": 1, "components": [], "warning": f"registry not found: {path}"}
    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    payload.setdefault("components", [])
    return payload
