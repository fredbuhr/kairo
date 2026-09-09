from __future__ import annotations

import asyncio
import re
import uuid
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Literal
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import Principal, require_kairo_user
from .config import settings
from .db import get_session
from .events import append_audit, enqueue_domain_event
from .finance import (
    FinanceAccountSnapshot,
    FinancePositionSnapshot,
    FinanceSnapshotIngest,
    FinanceSourceSnapshot,
    ingest_finance_snapshot,
)
from .finance_models import FinanceConnector
from .models import Project, SecretReference, Task, WorkflowExecution
from .openbao import openbao_client
from .security import require_internal_token
from .workflows import run_task


router = APIRouter(tags=["finance-connectors"])

_KEY_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._:-]*$")
_SECRET_KEY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
_TERMINAL_TASK_STATUSES = {"completed", "failed", "cancelled", "done", "archived"}


class FinanceConnectorCreate(BaseModel):
    project_id: uuid.UUID
    key: str = Field(min_length=1, max_length=160)
    provider: Literal["rotki"] = "rotki"
    display_name: str = Field(min_length=1, max_length=240)
    secret_reference_id: uuid.UUID
    username_secret_key: str = Field(default="username", min_length=1, max_length=120)
    password_secret_key: str = Field(default="password", min_length=1, max_length=120)
    source_key: str | None = Field(default=None, min_length=1, max_length=160)
    refresh_remote: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def normalize(self) -> "FinanceConnectorCreate":
        self.key = self.key.strip().lower()
        self.display_name = self.display_name.strip()
        self.username_secret_key = self.username_secret_key.strip()
        self.password_secret_key = self.password_secret_key.strip()
        self.source_key = (self.source_key or f"rotki.{self.key}").strip().lower()
        if not _KEY_PATTERN.fullmatch(self.key):
            raise ValueError("finance connector key contains unsupported characters")
        if not _KEY_PATTERN.fullmatch(self.source_key):
            raise ValueError("finance connector source_key contains unsupported characters")
        if not _SECRET_KEY_PATTERN.fullmatch(self.username_secret_key):
            raise ValueError("username secret key contains unsupported characters")
        if not _SECRET_KEY_PATTERN.fullmatch(self.password_secret_key):
            raise ValueError("password secret key contains unsupported characters")
        return self


class FinanceConnectorUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=240)
    enabled: bool | None = None
    secret_reference_id: uuid.UUID | None = None
    username_secret_key: str | None = Field(default=None, min_length=1, max_length=120)
    password_secret_key: str | None = Field(default=None, min_length=1, max_length=120)
    refresh_remote: bool | None = None
    metadata: dict[str, Any] | None = None

    @model_validator(mode="after")
    def normalize(self) -> "FinanceConnectorUpdate":
        if self.display_name is not None:
            self.display_name = self.display_name.strip()
        for field_name in ("username_secret_key", "password_secret_key"):
            value = getattr(self, field_name)
            if value is not None:
                value = value.strip()
                if not _SECRET_KEY_PATTERN.fullmatch(value):
                    raise ValueError(f"{field_name} contains unsupported characters")
                setattr(self, field_name, value)
        return self


class FinanceConnectorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    key: str
    provider: str
    display_name: str
    enabled: bool
    secret_reference_id: uuid.UUID
    username_secret_key: str
    password_secret_key: str
    source_key: str
    refresh_remote: bool
    metadata_json: dict[str, Any]
    last_sync_at: datetime | None
    last_error: str | None
    created_at: datetime
    updated_at: datetime


class FinanceConnectorSyncRead(BaseModel):
    connector: FinanceConnectorRead
    task_id: uuid.UUID
    workflow_execution_id: uuid.UUID | None
    workflow_status: str | None


class InternalFinanceConnectorSync(BaseModel):
    task_id: uuid.UUID
    workflow_execution_id: uuid.UUID


class InternalFinanceConnectorSyncResult(BaseModel):
    connector_id: uuid.UUID
    source_id: uuid.UUID
    account_count: int
    position_count: int
    observed_at: datetime
    provider: Literal["rotki"] = "rotki"
    scope: Literal["blockchain_balances"] = "blockchain_balances"


class RotkiContractError(RuntimeError):
    pass


def _action_result(payload: Any, *, context: str) -> Any:
    if not isinstance(payload, dict):
        raise RotkiContractError(f"Rotki {context} returned a non-object response")
    if "result" not in payload:
        raise RotkiContractError(f"Rotki {context} response has no result field")
    result = payload.get("result")
    if result is None:
        message = str(payload.get("message") or f"Rotki {context} failed")
        raise RotkiContractError(message[:1000])
    return result


def _decimal(value: Any, *, context: str) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise RotkiContractError(f"Rotki {context} is not numeric") from exc
    if not parsed.is_finite():
        raise RotkiContractError(f"Rotki {context} is not finite")
    return parsed


def _rotki_symbol(asset_identifier: str) -> str:
    """Preserve Rotki identity when no asset-mapping endpoint is involved.

    Common Rotki identifiers (BTC/ETH/etc.) are already symbols. CAIP-like/token identifiers may be
    longer; in that case the UI receives a visibly truncated identifier while the exact identifier
    remains the canonical `asset_key` and in metadata. We never invent a ticker.
    """
    if len(asset_identifier) <= 64:
        return asset_identifier.upper()
    return asset_identifier[:61] + "..."


def _sum_protocol_map(value: Any, *, context: str) -> tuple[Decimal, Decimal, list[str]]:
    if not isinstance(value, dict):
        raise RotkiContractError(f"Rotki {context} protocol map is invalid")
    amount = Decimal("0")
    usd_value = Decimal("0")
    labels: list[str] = []
    for label, raw_balance in value.items():
        if not isinstance(raw_balance, dict):
            raise RotkiContractError(f"Rotki {context}.{label} balance is invalid")
        amount += _decimal(raw_balance.get("amount"), context=f"{context}.{label}.amount")
        usd_value += _decimal(raw_balance.get("value"), context=f"{context}.{label}.value")
        labels.append(str(label))
    return amount, usd_value, labels


def _position(
    *,
    account_external_id: str,
    asset_identifier: str,
    amount: Decimal,
    usd_value: Decimal,
    network: str,
    liability: bool,
    metadata: dict[str, Any],
) -> FinancePositionSnapshot | None:
    if amount == 0 and usd_value == 0:
        return None
    quantity = -abs(amount) if liability else amount
    value = -abs(usd_value) if liability else usd_value
    unit_price = None
    if amount != 0:
        unit_price = abs(usd_value / amount)
    asset_key = f"liability:{asset_identifier}" if liability else asset_identifier
    return FinancePositionSnapshot(
        account_external_id=account_external_id,
        asset_key=asset_key,
        symbol=_rotki_symbol(asset_identifier),
        name=None,
        asset_type="liability" if liability else "crypto",
        quantity=quantity,
        unit_price_usd=unit_price,
        value_usd=value,
        cost_basis_usd=None,
        unrealized_pnl_usd=None,
        metadata={
            "rotki_asset_identifier": asset_identifier,
            "rotki_network": network,
            "rotki_liability": liability,
            **metadata,
        },
    )


def _normalize_rotki_blockchain_balances(
    result: Any,
) -> tuple[list[FinanceAccountSnapshot], list[FinancePositionSnapshot], dict[str, Any]]:
    if not isinstance(result, dict):
        raise RotkiContractError("Rotki blockchain balances result is not an object")
    per_account = result.get("per_account")
    if per_account is None:
        per_account = result.get("perAccount")
    if not isinstance(per_account, dict):
        raise RotkiContractError("Rotki blockchain balances result has no valid per_account map")

    accounts: list[FinanceAccountSnapshot] = []
    positions: list[FinancePositionSnapshot] = []

    for raw_chain, raw_accounts in per_account.items():
        chain = str(raw_chain).strip().lower()
        if not chain or not isinstance(raw_accounts, dict):
            continue

        if "standalone" in raw_accounts or "xpubs" in raw_accounts:
            standalone = raw_accounts.get("standalone") or {}
            if isinstance(standalone, dict):
                for address, raw_balance in standalone.items():
                    if not isinstance(raw_balance, dict):
                        continue
                    external_id = f"{chain}:address:{address}"
                    accounts.append(
                        FinanceAccountSnapshot(
                            external_id=external_id,
                            label=f"{chain.upper()} · {str(address)[:10]}…",
                            account_type="wallet",
                            network=chain,
                            public_address=str(address),
                            metadata={"rotki_kind": "standalone"},
                        )
                    )
                    balance_amount = _decimal(raw_balance.get("amount"), context=f"{chain}.{address}.amount")
                    balance_value = _decimal(raw_balance.get("value"), context=f"{chain}.{address}.value")
                    item = _position(
                        account_external_id=external_id,
                        asset_identifier=chain.upper(),
                        amount=balance_amount,
                        usd_value=balance_value,
                        network=chain,
                        liability=False,
                        metadata={"rotki_balance_kind": "standalone"},
                    )
                    if item is not None:
                        positions.append(item)

            xpubs = raw_accounts.get("xpubs") or []
            if isinstance(xpubs, list):
                for index, xpub_entry in enumerate(xpubs):
                    if not isinstance(xpub_entry, dict):
                        continue
                    xpub = str(xpub_entry.get("xpub") or "")
                    derivation = xpub_entry.get("derivation_path")
                    if derivation is None:
                        derivation = xpub_entry.get("derivationPath")
                    external_id = f"{chain}:xpub:{index}:{str(derivation or 'root')}"
                    address_balances = xpub_entry.get("addresses") or {}
                    amount = Decimal("0")
                    usd_value = Decimal("0")
                    address_count = 0
                    if isinstance(address_balances, dict):
                        for address, raw_balance in address_balances.items():
                            if not isinstance(raw_balance, dict):
                                continue
                            amount += _decimal(raw_balance.get("amount"), context=f"{chain}.xpub.{address}.amount")
                            usd_value += _decimal(raw_balance.get("value"), context=f"{chain}.xpub.{address}.value")
                            address_count += 1
                    accounts.append(
                        FinanceAccountSnapshot(
                            external_id=external_id,
                            label=f"{chain.upper()} xpub {index + 1}",
                            account_type="xpub",
                            network=chain,
                            public_address=None,
                            metadata={
                                "rotki_kind": "xpub",
                                "derivation_path": derivation,
                                "address_count": address_count,
                                "xpub_present": bool(xpub),
                            },
                        )
                    )
                    item = _position(
                        account_external_id=external_id,
                        asset_identifier=chain.upper(),
                        amount=amount,
                        usd_value=usd_value,
                        network=chain,
                        liability=False,
                        metadata={"rotki_balance_kind": "xpub"},
                    )
                    if item is not None:
                        positions.append(item)
            continue

        for address, raw_sheet in raw_accounts.items():
            if not isinstance(raw_sheet, dict):
                continue
            external_id = f"{chain}:address:{address}"
            accounts.append(
                FinanceAccountSnapshot(
                    external_id=external_id,
                    label=f"{chain.upper()} · {str(address)[:10]}…",
                    account_type="wallet",
                    network=chain,
                    public_address=str(address),
                    metadata={"rotki_kind": "balance_sheet"},
                )
            )
            for category, liability in (("assets", False), ("liabilities", True)):
                raw_assets = raw_sheet.get(category) or {}
                if not isinstance(raw_assets, dict):
                    continue
                for asset_identifier, protocol_map in raw_assets.items():
                    amount, usd_value, labels = _sum_protocol_map(
                        protocol_map,
                        context=f"{chain}.{address}.{category}.{asset_identifier}",
                    )
                    item = _position(
                        account_external_id=external_id,
                        asset_identifier=str(asset_identifier),
                        amount=amount,
                        usd_value=usd_value,
                        network=chain,
                        liability=liability,
                        metadata={"rotki_balance_labels": labels, "rotki_category": category},
                    )
                    if item is not None:
                        positions.append(item)

    refresh_meta = result.get("last_refresh_ts")
    if refresh_meta is None:
        refresh_meta = result.get("lastRefreshTs")
    metadata = {
        "adapter": "rotki-api-v1",
        "scope": "blockchain_balances",
        "rotki_last_refresh_ts": refresh_meta if isinstance(refresh_meta, dict) else {},
        "account_count": len(accounts),
        "position_count": len(positions),
    }
    return accounts, positions, metadata


async def _rotki_json(
    client: httpx.AsyncClient,
    method: str,
    path: str,
    *,
    json_body: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> Any:
    try:
        response = await client.request(method, path, json=json_body, params=params)
    except httpx.HTTPError as exc:
        raise RotkiContractError(f"Rotki request failed at {path}: {exc}") from exc
    try:
        payload = response.json()
    except ValueError as exc:
        raise RotkiContractError(
            f"Rotki {path} returned HTTP {response.status_code} with non-JSON body"
        ) from exc
    if response.status_code >= 400:
        message = payload.get("message") if isinstance(payload, dict) else None
        raise RotkiContractError(
            f"Rotki {path} returned HTTP {response.status_code}: {message or 'request rejected'}"
        )
    return payload


async def _wait_rotki_task(client: httpx.AsyncClient, task_id: int, *, timeout_seconds: int = 120) -> Any:
    deadline = asyncio.get_running_loop().time() + timeout_seconds
    while asyncio.get_running_loop().time() < deadline:
        status_payload = await _rotki_json(client, "GET", "tasks")
        task_status = _action_result(status_payload, context="tasks")
        completed = task_status.get("completed") if isinstance(task_status, dict) else None
        if isinstance(completed, list) and task_id in completed:
            result_payload = await _rotki_json(client, "GET", f"tasks/{task_id}")
            wrapper = _action_result(result_payload, context=f"task {task_id}")
            if not isinstance(wrapper, dict):
                raise RotkiContractError(f"Rotki task {task_id} result wrapper is invalid")
            outcome = wrapper.get("outcome")
            if not isinstance(outcome, dict):
                raise RotkiContractError(f"Rotki task {task_id} has no outcome")
            result = outcome.get("result")
            if result is None:
                raise RotkiContractError(str(outcome.get("message") or f"Rotki task {task_id} failed")[:1000])
            return result
        await asyncio.sleep(0.4)
    raise RotkiContractError(f"Rotki task {task_id} did not complete within {timeout_seconds}s")


async def _rotki_login_and_balances(
    *,
    username: str,
    password: str,
    refresh_remote: bool,
) -> Any:
    base_url = settings.rotki_url.rstrip("/") + "/"
    timeout = httpx.Timeout(connect=5.0, read=35.0, write=15.0, pool=5.0)
    async with httpx.AsyncClient(base_url=base_url, timeout=timeout) as client:
        await _rotki_json(
            client,
            "POST",
            f"users/{quote(username, safe='')}/authenticate",
            json_body={"password": password},
        )

        users_payload = await _rotki_json(client, "GET", "users")
        users = _action_result(users_payload, context="users")
        logged_in = isinstance(users, dict) and users.get(username) == "loggedin"
        if not logged_in:
            login_payload = await _rotki_json(
                client,
                "POST",
                f"users/{quote(username, safe='')}",
                json_body={"password": password, "async_query": True, "sync_approval": "no"},
            )
            pending = _action_result(login_payload, context="login")
            try:
                task_id = int(pending["task_id"])
            except (KeyError, TypeError, ValueError) as exc:
                raise RotkiContractError("Rotki login did not return an async task id") from exc
            await _wait_rotki_task(client, task_id, timeout_seconds=120)

        if refresh_remote:
            refresh_payload = await _rotki_json(
                client,
                "POST",
                "balances/blockchains",
                json_body={"async_query": True},
            )
            pending = _action_result(refresh_payload, context="blockchain balance refresh")
            try:
                task_id = int(pending["task_id"])
            except (KeyError, TypeError, ValueError) as exc:
                raise RotkiContractError("Rotki balance refresh did not return an async task id") from exc
            refreshed = await _wait_rotki_task(client, task_id, timeout_seconds=180)
            if isinstance(refreshed, dict) and ("per_account" in refreshed or "perAccount" in refreshed):
                return refreshed

        cached_payload = await _rotki_json(
            client,
            "GET",
            "balances/blockchains",
            params={"only_cache": "true"},
        )
        return _action_result(cached_payload, context="cached blockchain balances")


async def _project_owned(
    project_id: uuid.UUID,
    principal: Principal,
    session: AsyncSession,
) -> Project:
    project = await session.scalar(
        select(Project).where(
            Project.id == project_id,
            Project.keycloak_subject == principal.subject,
        )
    )
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


async def _owned_connector(
    connector_id: uuid.UUID,
    principal: Principal,
    session: AsyncSession,
    *,
    lock: bool = False,
) -> FinanceConnector:
    statement = select(FinanceConnector).where(
        FinanceConnector.id == connector_id,
        FinanceConnector.keycloak_subject == principal.subject,
    )
    if lock:
        statement = statement.with_for_update()
    connector = await session.scalar(statement)
    if connector is None:
        raise HTTPException(status_code=404, detail="Finance connector not found")
    return connector


async def _secret_reference(
    reference_id: uuid.UUID,
    owner_subject: str,
    session: AsyncSession,
) -> SecretReference:
    reference = await session.scalar(
        select(SecretReference).where(
            SecretReference.id == reference_id,
            SecretReference.keycloak_subject == owner_subject,
        )
    )
    if reference is None:
        raise HTTPException(status_code=404, detail="Secret reference not found")
    return reference


async def _validate_secret_binding(
    reference_id: uuid.UUID,
    username_key: str,
    password_key: str,
    owner_subject: str,
    session: AsyncSession,
) -> None:
    reference = await _secret_reference(reference_id, owner_subject, session)
    try:
        provider_status = await openbao_client.secret_status(reference.provider_path)
    except (httpx.HTTPError, OSError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OpenBao is unavailable or rejected the Finance connector secret reference",
        ) from exc
    if not provider_status.exists:
        raise HTTPException(status_code=409, detail="Finance connector secret does not exist")
    missing = [key for key in (username_key, password_key) if key not in provider_status.keys]
    if missing:
        raise HTTPException(
            status_code=409,
            detail={"message": "Finance connector secret keys are missing", "keys": missing},
        )


@router.post("/v1/finance/connectors", response_model=FinanceConnectorRead, status_code=201)
async def create_finance_connector(
    body: FinanceConnectorCreate,
    principal: Principal = Depends(require_kairo_user),
    session: AsyncSession = Depends(get_session),
) -> FinanceConnector:
    await _project_owned(body.project_id, principal, session)
    await _secret_reference(body.secret_reference_id, principal.subject, session)

    connector = FinanceConnector(
        keycloak_subject=principal.subject,
        project_id=body.project_id,
        key=body.key,
        provider=body.provider,
        display_name=body.display_name,
        enabled=False,
        secret_reference_id=body.secret_reference_id,
        username_secret_key=body.username_secret_key,
        password_secret_key=body.password_secret_key,
        source_key=body.source_key,
        refresh_remote=body.refresh_remote,
        metadata_json=body.metadata,
    )
    session.add(connector)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=409,
            detail="Finance connector key or source key already exists for this user",
        ) from exc

    correlation_id = uuid.uuid4()
    await enqueue_domain_event(
        session,
        event_type="finance.connector.created",
        aggregate_type="finance_connector",
        aggregate_id=connector.id,
        correlation_id=correlation_id,
        payload={
            "finance_connector_id": str(connector.id),
            "provider": connector.provider,
            "source_key": connector.source_key,
            "enabled": False,
        },
    )
    await append_audit(
        session,
        actor_type="user",
        actor_id=principal.subject,
        action="finance.connector.create",
        resource_type="finance_connector",
        resource_id=str(connector.id),
        authority_level=1,
        correlation_id=correlation_id,
        request_json={
            "project_id": str(connector.project_id),
            "key": connector.key,
            "provider": connector.provider,
            "secret_reference_id": str(connector.secret_reference_id),
            "username_secret_key": connector.username_secret_key,
            "password_secret_key": connector.password_secret_key,
            "source_key": connector.source_key,
            "refresh_remote": connector.refresh_remote,
        },
    )
    await session.commit()
    await session.refresh(connector)
    return connector


@router.get("/v1/finance/connectors", response_model=list[FinanceConnectorRead])
async def list_finance_connectors(
    principal: Principal = Depends(require_kairo_user),
    session: AsyncSession = Depends(get_session),
) -> list[FinanceConnector]:
    rows = await session.execute(
        select(FinanceConnector)
        .where(FinanceConnector.keycloak_subject == principal.subject)
        .order_by(FinanceConnector.created_at.desc())
    )
    return list(rows.scalars())


@router.patch("/v1/finance/connectors/{connector_id}", response_model=FinanceConnectorRead)
async def update_finance_connector(
    connector_id: uuid.UUID,
    body: FinanceConnectorUpdate,
    principal: Principal = Depends(require_kairo_user),
    session: AsyncSession = Depends(get_session),
) -> FinanceConnector:
    connector = await _owned_connector(connector_id, principal, session, lock=True)
    fields = body.model_fields_set
    if not fields:
        return connector

    reference_id = body.secret_reference_id if body.secret_reference_id is not None else connector.secret_reference_id
    username_key = body.username_secret_key if body.username_secret_key is not None else connector.username_secret_key
    password_key = body.password_secret_key if body.password_secret_key is not None else connector.password_secret_key
    await _secret_reference(reference_id, principal.subject, session)

    if body.enabled is True or (
        connector.enabled
        and bool(fields & {"secret_reference_id", "username_secret_key", "password_secret_key"})
    ):
        await _validate_secret_binding(
            reference_id,
            username_key,
            password_key,
            principal.subject,
            session,
        )

    if "display_name" in fields and body.display_name is not None:
        connector.display_name = body.display_name
    if "enabled" in fields and body.enabled is not None:
        connector.enabled = body.enabled
    if "secret_reference_id" in fields and body.secret_reference_id is not None:
        connector.secret_reference_id = body.secret_reference_id
    if "username_secret_key" in fields and body.username_secret_key is not None:
        connector.username_secret_key = body.username_secret_key
    if "password_secret_key" in fields and body.password_secret_key is not None:
        connector.password_secret_key = body.password_secret_key
    if "refresh_remote" in fields and body.refresh_remote is not None:
        connector.refresh_remote = body.refresh_remote
    if "metadata" in fields and body.metadata is not None:
        connector.metadata_json = body.metadata

    correlation_id = uuid.uuid4()
    await enqueue_domain_event(
        session,
        event_type="finance.connector.updated",
        aggregate_type="finance_connector",
        aggregate_id=connector.id,
        correlation_id=correlation_id,
        payload={
            "finance_connector_id": str(connector.id),
            "enabled": connector.enabled,
            "changed_fields": sorted(fields),
        },
    )
    await append_audit(
        session,
        actor_type="user",
        actor_id=principal.subject,
        action="finance.connector.update",
        resource_type="finance_connector",
        resource_id=str(connector.id),
        authority_level=1,
        correlation_id=correlation_id,
        request_json={"changed_fields": sorted(fields)},
    )
    await session.commit()
    await session.refresh(connector)
    return connector


@router.post("/v1/finance/connectors/{connector_id}/sync", response_model=FinanceConnectorSyncRead, status_code=202)
async def sync_finance_connector(
    connector_id: uuid.UUID,
    principal: Principal = Depends(require_kairo_user),
    session: AsyncSession = Depends(get_session),
) -> FinanceConnectorSyncRead:
    connector = await _owned_connector(connector_id, principal, session)
    if not connector.enabled:
        raise HTTPException(status_code=409, detail="Finance connector is disabled")

    owner_ref = f"kairo.finance.connector:{connector.id}"
    existing_rows = await session.execute(
        select(Task)
        .where(
            Task.project_id == connector.project_id,
            Task.owner_ref == owner_ref,
            ~Task.status.in_(_TERMINAL_TASK_STATUSES),
        )
        .order_by(Task.created_at.desc())
        .limit(1)
    )
    task = existing_rows.scalar_one_or_none()
    if task is None:
        task = Task(
            project_id=connector.project_id,
            title=f"Synchroniser Finance · {connector.display_name}",
            description="Lecture Rotki vers le read model Finance KAIRO",
            status="todo",
            owner_type="agent",
            owner_ref=owner_ref,
            authority_ceiling=1,
            budget_usd=Decimal("0"),
            input={
                "capability": "finance.sync.rotki",
                "finance_connector_id": str(connector.id),
                "authority_level": 1,
                "estimated_cost_usd": "0",
                "policy_scope": {
                    "finance_connector_id": str(connector.id),
                    "provider": connector.provider,
                    "operation": "read_portfolio",
                },
            },
        )
        session.add(task)
        await session.flush()
        correlation_id = uuid.uuid4()
        await enqueue_domain_event(
            session,
            event_type="finance.connector.sync.requested",
            aggregate_type="finance_connector",
            aggregate_id=connector.id,
            correlation_id=correlation_id,
            payload={
                "finance_connector_id": str(connector.id),
                "task_id": str(task.id),
                "provider": connector.provider,
            },
        )
        await append_audit(
            session,
            actor_type="user",
            actor_id=principal.subject,
            action="finance.connector.sync.request",
            resource_type="finance_connector",
            resource_id=str(connector.id),
            authority_level=1,
            correlation_id=correlation_id,
            request_json={"task_id": str(task.id), "provider": connector.provider},
        )
        await session.commit()

    run = await run_task(task.id, session)
    await session.refresh(connector)
    return FinanceConnectorSyncRead(
        connector=FinanceConnectorRead.model_validate(connector),
        task_id=task.id,
        workflow_execution_id=run.workflow_execution_id,
        workflow_status=run.status,
    )


@router.post(
    "/internal/v1/finance-connectors/{connector_id}/sync",
    response_model=InternalFinanceConnectorSyncResult,
    dependencies=[Depends(require_internal_token)],
)
async def internal_sync_finance_connector(
    connector_id: uuid.UUID,
    body: InternalFinanceConnectorSync,
    session: AsyncSession = Depends(get_session),
) -> InternalFinanceConnectorSyncResult:
    connector = await session.get(FinanceConnector, connector_id, with_for_update=True)
    if connector is None:
        raise HTTPException(status_code=404, detail="Finance connector not found")
    if not connector.enabled:
        raise HTTPException(status_code=409, detail="Finance connector is disabled")
    if connector.provider != "rotki":
        raise HTTPException(status_code=409, detail="Unsupported Finance connector provider")

    task = await session.get(Task, body.task_id)
    execution = await session.get(WorkflowExecution, body.workflow_execution_id)
    task_input = task.input if task is not None and isinstance(task.input, dict) else {}
    if (
        task is None
        or execution is None
        or execution.task_id != task.id
        or task.project_id != connector.project_id
        or str(task_input.get("capability") or "") != "finance.sync.rotki"
        or str(task_input.get("finance_connector_id") or "") != str(connector.id)
    ):
        raise HTTPException(status_code=409, detail="Finance connector Task binding is invalid")

    reference = await _secret_reference(
        connector.secret_reference_id,
        connector.keycloak_subject,
        session,
    )
    try:
        username, password = await asyncio.gather(
            openbao_client.read_secret_value(reference.provider_path, connector.username_secret_key),
            openbao_client.read_secret_value(reference.provider_path, connector.password_secret_key),
        )
        raw_balances = await _rotki_login_and_balances(
            username=username,
            password=password,
            refresh_remote=connector.refresh_remote,
        )
        accounts, positions, adapter_metadata = _normalize_rotki_blockchain_balances(raw_balances)
        snapshot = FinanceSnapshotIngest(
            owner_subject=connector.keycloak_subject,
            source=FinanceSourceSnapshot(
                key=connector.source_key,
                provider="rotki",
                source_type="portfolio",
                external_account_ref=str(connector.id),
                display_name=connector.display_name,
                status="connected",
                metadata={"finance_connector_id": str(connector.id), **adapter_metadata},
            ),
            accounts=accounts,
            positions=positions,
            replace_missing=True,
        )
        ingested = await ingest_finance_snapshot(snapshot, session)
    except HTTPException:
        raise
    except (httpx.HTTPError, OSError, ValueError, KeyError, RotkiContractError) as exc:
        connector.last_error = str(exc)[:4000]
        correlation_id = execution.correlation_id
        await enqueue_domain_event(
            session,
            event_type="finance.connector.sync.failed",
            aggregate_type="finance_connector",
            aggregate_id=connector.id,
            correlation_id=correlation_id,
            payload={
                "finance_connector_id": str(connector.id),
                "task_id": str(task.id),
                "provider": connector.provider,
                "error": connector.last_error,
            },
        )
        await append_audit(
            session,
            actor_type="connector",
            actor_id="finance:rotki",
            action="finance.connector.sync.fail",
            resource_type="finance_connector",
            resource_id=str(connector.id),
            authority_level=1,
            correlation_id=correlation_id,
            result_json={"error": connector.last_error, "task_id": str(task.id)},
        )
        await session.commit()
        raise HTTPException(status_code=502, detail="Rotki Finance synchronization failed") from exc

    connector.last_sync_at = ingested.observed_at
    connector.last_error = None
    correlation_id = execution.correlation_id
    await enqueue_domain_event(
        session,
        event_type="finance.connector.sync.completed",
        aggregate_type="finance_connector",
        aggregate_id=connector.id,
        correlation_id=correlation_id,
        payload={
            "finance_connector_id": str(connector.id),
            "source_id": str(ingested.source.id),
            "task_id": str(task.id),
            "account_count": ingested.received_accounts,
            "position_count": ingested.received_positions,
        },
    )
    await append_audit(
        session,
        actor_type="connector",
        actor_id="finance:rotki",
        action="finance.connector.sync.complete",
        resource_type="finance_connector",
        resource_id=str(connector.id),
        authority_level=1,
        correlation_id=correlation_id,
        result_json={
            "source_id": str(ingested.source.id),
            "account_count": ingested.received_accounts,
            "position_count": ingested.received_positions,
            "task_id": str(task.id),
        },
    )
    await session.commit()
    await session.refresh(connector)
    return InternalFinanceConnectorSyncResult(
        connector_id=connector.id,
        source_id=ingested.source.id,
        account_count=ingested.received_accounts,
        position_count=ingested.received_positions,
        observed_at=ingested.observed_at,
    )
