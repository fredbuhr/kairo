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

    @staticmethod
    def _normalized_path(provider_path: str) -> str:
        normalized = provider_path.strip().lstrip("/")
        if normalized.startswith("v1/"):
            normalized = normalized[3:]
        if not normalized:
            raise ValueError("OpenBao provider path cannot be empty")
        return normalized

    async def health(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                response = await client.get(f"{self.base_url}/v1/sys/health")
            # 200 is active; 429 is a healthy standby. Sealed/uninitialized nodes are not ready.
            return response.status_code in {200, 429}
        except (httpx.HTTPError, OSError):
            return False

    async def secret_status(self, provider_path: str) -> SecretStatus:
        normalized = self._normalized_path(provider_path)
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

    async def write_secret_values(
        self,
        provider_path: str,
        values: dict[str, str],
    ) -> SecretStatus:
        """Write one owned KV-v2 secret without returning any secret value.

        Callers must enforce ownership before reaching this method. The returned object exposes only
        key names/version metadata so secret material cannot accidentally flow into API responses,
        audit records, Temporal payloads or NATS events.
        """
        normalized = self._normalized_path(provider_path)
        if not values:
            raise ValueError("OpenBao secret values cannot be empty")
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.post(
                f"{self.base_url}/v1/{normalized}",
                headers={**self._headers(), "Content-Type": "application/json"},
                json={"data": values},
            )
        response.raise_for_status()
        version: int | None = None
        try:
            payload: dict[str, Any] = response.json()
            data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
            version_raw = data.get("version") if isinstance(data, dict) else None
            version = int(version_raw) if version_raw is not None else None
        except (ValueError, TypeError):
            version = None
        return SecretStatus(exists=True, keys=tuple(sorted(values)), version=version)

    async def read_secret_value(self, provider_path: str, key: str) -> str:
        """Internal-only value resolver for adapters.

        This method must never be returned by a public API, persisted in PostgreSQL, emitted to NATS,
        or placed in audit records. Callers receive one requested field only.
        """
        normalized = self._normalized_path(provider_path)
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
