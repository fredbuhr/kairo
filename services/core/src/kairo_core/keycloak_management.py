from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote

import httpx

from .config import settings


@dataclass(frozen=True, slots=True)
class KeycloakManagedIdentity:
    subject: str
    exists: bool
    enabled: bool | None = None


class KeycloakManagementNotConfigured(RuntimeError):
    pass


class KeycloakIdentityManager:
    """Bounded Keycloak Admin REST adapter for the future account-erasure state machine.

    The adapter deliberately identifies a user by the authenticated Keycloak `sub`, which is also the
    Admin REST user id. It never searches by username/email and never accepts an arbitrary realm,
    Keycloak origin or target user id from a browser request.

    No public route calls the mutating methods yet. They exist as a provider boundary for a future
    durable account-freeze/erasure orchestrator that can preserve reconciliation state across stores.
    """

    def __init__(self) -> None:
        self.base_url = settings.keycloak_url.rstrip("/")
        self.realm = settings.keycloak_realm
        self.client_id = settings.keycloak_management_client_id
        self.client_secret = settings.keycloak_management_client_secret

    @property
    def configured(self) -> bool:
        return bool(self.client_id.strip() and self.client_secret.strip())

    def _require_configured(self) -> None:
        if not self.configured:
            raise KeycloakManagementNotConfigured(
                "Dedicated Keycloak management service account is not configured"
            )
        if self.client_id == settings.keycloak_client_id:
            raise KeycloakManagementNotConfigured(
                "Keycloak management must not reuse the public Web/Desktop client"
            )

    async def _access_token(self) -> str:
        self._require_configured()
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.post(
                f"{self.base_url}/realms/{quote(self.realm, safe='')}/protocol/openid-connect/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
                headers={"Accept": "application/json"},
            )
        response.raise_for_status()
        payload = response.json()
        token = payload.get("access_token") if isinstance(payload, dict) else None
        if not isinstance(token, str) or not token.strip():
            raise RuntimeError("Keycloak management client did not return an access token")
        return token

    def _user_url(self, subject: str) -> str:
        normalized = subject.strip()
        if not normalized or len(normalized) > 255:
            raise ValueError("Keycloak subject is empty or too long")
        return (
            f"{self.base_url}/admin/realms/{quote(self.realm, safe='')}/users/"
            f"{quote(normalized, safe='')}"
        )

    async def get_identity(self, subject: str) -> KeycloakManagedIdentity:
        token = await self._access_token()
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.get(
                self._user_url(subject),
                headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            )
        if response.status_code == 404:
            return KeycloakManagedIdentity(subject=subject, exists=False, enabled=None)
        response.raise_for_status()
        payload = response.json()
        returned_id = str(payload.get("id") or "") if isinstance(payload, dict) else ""
        if returned_id != subject:
            raise RuntimeError("Keycloak Admin REST returned a different user identity")
        enabled = payload.get("enabled") if isinstance(payload, dict) else None
        if not isinstance(enabled, bool):
            raise RuntimeError("Keycloak user representation has no boolean enabled state")
        return KeycloakManagedIdentity(subject=subject, exists=True, enabled=enabled)

    async def disable_identity(self, subject: str) -> KeycloakManagedIdentity:
        """Disable new authentication for one exact Keycloak subject.

        Disabling the identity is not sufficient to freeze KAIRO on its own because already-issued
        access tokens can remain valid until expiry. A future erasure orchestrator must first persist
        and enforce a local KAIRO write freeze, then call this adapter.
        """

        current = await self.get_identity(subject)
        if not current.exists or current.enabled is False:
            return current
        token = await self._access_token()
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.put(
                self._user_url(subject),
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                json={"enabled": False},
            )
        response.raise_for_status()
        verified = await self.get_identity(subject)
        if not verified.exists or verified.enabled is not False:
            raise RuntimeError("Keycloak identity disable could not be verified")
        return verified

    async def delete_identity(self, subject: str) -> KeycloakManagedIdentity:
        """Delete one exact Keycloak user idempotently.

        This method is intentionally not routed publicly. It may only be wired after KAIRO has a
        replay-safe destructive account ledger, an enforced write freeze and restore-after-erasure
        tombstone semantics. Deleting identity first would destroy the caller's recovery path.
        """

        current = await self.get_identity(subject)
        if not current.exists:
            return current
        token = await self._access_token()
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.delete(
                self._user_url(subject),
                headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            )
        if response.status_code not in {204, 404}:
            response.raise_for_status()
        verified = await self.get_identity(subject)
        if verified.exists:
            raise RuntimeError("Keycloak identity deletion could not be verified")
        return verified


keycloak_identity_manager = KeycloakIdentityManager()
