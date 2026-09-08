from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from .config import settings


@dataclass(frozen=True, slots=True)
class SecretStatus:
    exists: bool
    keys: tuple[str, ...] = ()
    version: int | None = None


class OpenBaoClient:
    def __init__(self) -> None:
        self.base_url = settings.openbao_addr.rstrip("/")
        self.token = settings.openbao_token

    def _headers(self) -> dict[str, str]:
        return {"X-Vault-Token": self.token, "Accept": "application/json"}

    async def health(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                response = await client.get(f"{self.base_url}/v1/sys/health")
            return response.status_code in {200, 429, 472, 473, 501, 503}
        except (httpx.HTTPError, OSError):
            return False

    async def secret_status(self, provider_path: str) -> SecretStatus:
        normalized = provider_path.strip().lstrip("/")
        if normalized.startswith("v1/"):
            normalized = normalized[3:]
        if not normalized:
            raise ValueError("OpenBao provider path cannot be empty")

        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.get(
                f"{self.base_url}/v1/{normalized}", headers=self._headers()
            )
        if response.status_code == 404:
            return SecretStatus(exists=False)
        response.raise_for_status()
        payload: dict[str, Any] = response.json()
        wrapper = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        secret_data = wrapper.get("data") if isinstance(wrapper.get("data"), dict) else wrapper
        metadata = wrapper.get("metadata") if isinstance(wrapper.get("metadata"), dict) else {}
        keys = tuple(sorted(str(key) for key in secret_data.keys())) if isinstance(secret_data, dict) else ()
        version_raw = metadata.get("version") if isinstance(metadata, dict) else None
        try:
            version = int(version_raw) if version_raw is not None else None
        except (TypeError, ValueError):
            version = None
        return SecretStatus(exists=True, keys=keys, version=version)

    async def read_secret_value(self, provider_path: str, key: str) -> str:
        """Internal-only value resolver for future adapters.

        This method must never be returned by a public API, persisted in PostgreSQL, emitted to NATS,
        or placed in audit records. Callers receive one requested field only.
        """
        normalized = provider_path.strip().lstrip("/")
        if normalized.startswith("v1/"):
            normalized = normalized[3:]
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.get(
                f"{self.base_url}/v1/{normalized}", headers=self._headers()
            )
        response.raise_for_status()
        payload = response.json()
        wrapper = payload.get("data") or {}
        secret_data = wrapper.get("data") if isinstance(wrapper, dict) and isinstance(wrapper.get("data"), dict) else wrapper
        if not isinstance(secret_data, dict) or key not in secret_data:
            raise KeyError(key)
        value = secret_data[key]
        if not isinstance(value, str):
            return str(value)
        return value


openbao_client = OpenBaoClient()
