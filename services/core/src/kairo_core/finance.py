from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import Principal, require_kairo_user
from .db import get_session
from .events import append_audit, enqueue_domain_event
from .finance_models import (
    FinanceAccount,
    FinancePosition,
    FinanceSource,
    FinanceTransactionProposal,
)
from .ownership import require_owned_project
from .security import require_internal_token


router = APIRouter(tags=["finance"])

_KEY_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._:-]*$")
_BLOCKED_SECRET_KEYS = {
    "private_key",
    "privatekey",
    "seed",
    "seed_phrase",
    "seedphrase",
    "mnemonic",
    "password",
    "passphrase",
    "api_key",
    "apikey",
    "secret_key",
    "secretkey",
    "access_token",
    "accesstoken",
    "refresh_token",
    "refreshtoken",
}


def _normalized_json_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")


def _reject_secret_like_json(value: Any, *, label: str) -> None:
    """Reject credential-like material before it can enter finance snapshot/proposal JSON.

    Finance adapters may expose rich metadata, but wallet private keys, seed phrases and provider
    credentials are never legitimate portfolio facts. Public addresses remain allowed.
    """
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = _normalized_json_key(str(key))
            if normalized in _BLOCKED_SECRET_KEYS:
                raise ValueError(f"{label} contains forbidden secret-like field: {key}")
            _reject_secret_like_json(child, label=label)
    elif isinstance(value, list):
        for child in value:
            _reject_secret_like_json(child, label=label)


def _require_finite(value: Decimal, *, label: str) -> Decimal:
    if not value.is_finite():
        raise ValueError(f"{label} must be finite")
    return value


class FinanceSourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    key: str
    provider: str
    source_type: str
    external_account_ref: str
    display_name: str
    status: str
    metadata_json: dict[str, Any]
    last_sync_at: datetime | None
    last_error: str | None
    created_at: datetime
    updated_at: datetime


class FinanceAccountRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source_id: uuid.UUID
    external_id: str
    label: str
    account_type: str
    network: str | None
    public_address: str | None
    metadata_json: dict[str, Any]
    observed_at: datetime
    created_at: datetime
    updated_at: datetime


class FinancePositionRead(BaseModel):
    id: uuid.UUID
    source_id: uuid.UUID
    source_key: str
    source_provider: str
    source_display_name: str
    account_id: uuid.UUID
    account_external_id: str
    account_label: str
    account_type: str
    network: str | None
    public_address: str | None
    asset_key: str
    symbol: str
    name: str | None
    asset_type: str
    quantity: Decimal
    unit_price_usd: Decimal | None
    value_usd: Decimal
    cost_basis_usd: Decimal | None
    unrealized_pnl_usd: Decimal | None
    metadata: dict[str, Any]
    observed_at: datetime


class FinancePortfolioRead(BaseModel):
    generated_at: datetime
    currency: Literal["USD"] = "USD"
    total_value_usd: Decimal
    total_cost_basis_usd: Decimal | None
    total_unrealized_pnl_usd: Decimal | None
    sources: list[FinanceSourceRead]
    accounts: list[FinanceAccountRead]
    positions: list[FinancePositionRead]


class FinanceSourceSnapshot(BaseModel):
    key: str = Field(min_length=1, max_length=160)
    provider: str = Field(min_length=1, max_length=64)
    source_type: str = Field(default="portfolio", min_length=1, max_length=64)
    external_account_ref: str = Field(min_length=1, max_length=320)
    display_name: str = Field(min_length=1, max_length=240)
    status: str = Field(default="connected", min_length=1, max_length=32)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def normalize(self) -> "FinanceSourceSnapshot":
        self.key = self.key.strip().lower()
        self.provider = self.provider.strip().lower()
        self.source_type = self.source_type.strip().lower()
        self.external_account_ref = self.external_account_ref.strip()
        self.display_name = self.display_name.strip()
        self.status = self.status.strip().lower()
        if not _KEY_PATTERN.fullmatch(self.key):
            raise ValueError("finance source key contains unsupported characters")
        if not _KEY_PATTERN.fullmatch(self.provider):
            raise ValueError("finance provider contains unsupported characters")
        if not _KEY_PATTERN.fullmatch(self.source_type):
            raise ValueError("finance source_type contains unsupported characters")
        _reject_secret_like_json(self.metadata, label="finance source metadata")
        return self


class FinanceAccountSnapshot(BaseModel):
    external_id: str = Field(min_length=1, max_length=320)
    label: str = Field(min_length=1, max_length=240)
    account_type: str = Field(min_length=1, max_length=64)
    network: str | None = Field(default=None, max_length=120)
    public_address: str | None = Field(default=None, max_length=512)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def normalize(self) -> "FinanceAccountSnapshot":
        self.external_id = self.external_id.strip()
        self.label = self.label.strip()
        self.account_type = self.account_type.strip().lower()
        self.network = self.network.strip().lower() if self.network else None
        self.public_address = self.public_address.strip() if self.public_address else None
        if not _KEY_PATTERN.fullmatch(self.account_type):
            raise ValueError("finance account_type contains unsupported characters")
        if self.network and not _KEY_PATTERN.fullmatch(self.network):
            raise ValueError("finance network contains unsupported characters")
        _reject_secret_like_json(self.metadata, label="finance account metadata")
        return self


class FinancePositionSnapshot(BaseModel):
    account_external_id: str = Field(min_length=1, max_length=320)
    asset_key: str = Field(min_length=1, max_length=240)
    symbol: str = Field(min_length=1, max_length=64)
    name: str | None = Field(default=None, max_length=240)
    asset_type: str = Field(default="crypto", min_length=1, max_length=64)
    quantity: Decimal
    unit_price_usd: Decimal | None = None
    value_usd: Decimal
    cost_basis_usd: Decimal | None = None
    unrealized_pnl_usd: Decimal | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def normalize(self) -> "FinancePositionSnapshot":
        self.account_external_id = self.account_external_id.strip()
        self.asset_key = self.asset_key.strip().lower()
        self.symbol = self.symbol.strip().upper()
        self.name = self.name.strip() if self.name else None
        self.asset_type = self.asset_type.strip().lower()
        if not _KEY_PATTERN.fullmatch(self.asset_key):
            raise ValueError("finance asset_key contains unsupported characters")
        if not _KEY_PATTERN.fullmatch(self.asset_type):
            raise ValueError("finance asset_type contains unsupported characters")
        self.quantity = _require_finite(self.quantity, label="quantity")
        self.value_usd = _require_finite(self.value_usd, label="value_usd")
        if self.unit_price_usd is not None:
            self.unit_price_usd = _require_finite(self.unit_price_usd, label="unit_price_usd")
            if self.unit_price_usd < 0:
                raise ValueError("unit_price_usd cannot be negative")
        if self.cost_basis_usd is not None:
            self.cost_basis_usd = _require_finite(self.cost_basis_usd, label="cost_basis_usd")
        if self.unrealized_pnl_usd is not None:
            self.unrealized_pnl_usd = _require_finite(
                self.unrealized_pnl_usd,
                label="unrealized_pnl_usd",
            )
        _reject_secret_like_json(self.metadata, label="finance position metadata")
        return self


class FinanceSnapshotIngest(BaseModel):
    owner_subject: str = Field(min_length=1, max_length=240)
    source: FinanceSourceSnapshot
    accounts: list[FinanceAccountSnapshot] = Field(default_factory=list, max_length=2000)
    positions: list[FinancePositionSnapshot] = Field(default_factory=list, max_length=10000)
    replace_missing: bool = True

    @model_validator(mode="after")
    def validate_snapshot(self) -> "FinanceSnapshotIngest":
        self.owner_subject = self.owner_subject.strip()
        account_ids = [account.external_id for account in self.accounts]
        if len(account_ids) != len(set(account_ids)):
            raise ValueError("finance snapshot contains duplicate account external ids")
        account_set = set(account_ids)
        seen_positions: set[tuple[str, str]] = set()
        for position in self.positions:
            if position.account_external_id not in account_set:
                raise ValueError("finance position references an account absent from the snapshot")
            key = (position.account_external_id, position.asset_key)
            if key in seen_positions:
                raise ValueError("finance snapshot contains duplicate account/asset positions")
            seen_positions.add(key)
        return self


class FinanceSnapshotRead(BaseModel):
    source: FinanceSourceRead
    received_accounts: int
    received_positions: int
    removed_accounts: int
    removed_positions: int
    observed_at: datetime


class FinanceTransactionProposalCreate(BaseModel):
    project_id: uuid.UUID | None = None
    from_account_id: uuid.UUID
    kind: Literal["crypto_transfer"] = "crypto_transfer"
    network: str = Field(min_length=1, max_length=120)
    asset_key: str = Field(min_length=1, max_length=240)
    symbol: str = Field(min_length=1, max_length=64)
    amount: Decimal
    destination: str = Field(min_length=1, max_length=512)
    memo: str | None = Field(default=None, max_length=4000)
    estimated_fee_asset: str | None = Field(default=None, max_length=240)
    estimated_fee_amount: Decimal | None = None
    simulation: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def normalize(self) -> "FinanceTransactionProposalCreate":
        self.network = self.network.strip().lower()
        self.asset_key = self.asset_key.strip().lower()
        self.symbol = self.symbol.strip().upper()
        self.destination = self.destination.strip()
        self.memo = self.memo.strip() if self.memo else None
        self.estimated_fee_asset = (
            self.estimated_fee_asset.strip().lower() if self.estimated_fee_asset else None
        )
        if not _KEY_PATTERN.fullmatch(self.network):
            raise ValueError("transaction network contains unsupported characters")
        if not _KEY_PATTERN.fullmatch(self.asset_key):
            raise ValueError("transaction asset_key contains unsupported characters")
        self.amount = _require_finite(self.amount, label="amount")
        if self.amount <= 0:
            raise ValueError("transaction amount must be positive")
        if self.estimated_fee_amount is not None:
            self.estimated_fee_amount = _require_finite(
                self.estimated_fee_amount,
                label="estimated_fee_amount",
            )
            if self.estimated_fee_amount < 0:
                raise ValueError("estimated_fee_amount cannot be negative")
        _reject_secret_like_json(self.simulation, label="transaction simulation")
        return self


class FinanceTransactionProposalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID | None
    from_account_id: uuid.UUID | None
    kind: str
    network: str
    asset_key: str
    symbol: str
    amount: Decimal
    destination: str
    memo: str | None
    estimated_fee_asset: str | None
    estimated_fee_amount: Decimal | None
    simulation_json: dict[str, Any]
    status: str
    created_by: str
    created_at: datetime
    updated_at: datetime
    signing_required: Literal[True] = True
    signing_boundary: Literal["external_isolated_signer"] = "external_isolated_signer"


async def _owned_source(
    session: AsyncSession,
    source_id: uuid.UUID,
    principal: Principal,
) -> FinanceSource:
    source = await session.get(FinanceSource, source_id)
    if source is None or source.keycloak_subject != principal.subject:
        raise HTTPException(status_code=404, detail="Finance source not found")
    return source


async def _owned_account(
    session: AsyncSession,
    account_id: uuid.UUID,
    principal: Principal,
) -> tuple[FinanceAccount, FinanceSource]:
    row = await session.execute(
        select(FinanceAccount, FinanceSource)
        .join(FinanceSource, FinanceSource.id == FinanceAccount.source_id)
        .where(
            FinanceAccount.id == account_id,
            FinanceSource.keycloak_subject == principal.subject,
        )
    )
    found = row.first()
    if found is None:
        raise HTTPException(status_code=404, detail="Finance account not found")
    return found[0], found[1]


@router.get("/v1/finance/sources", response_model=list[FinanceSourceRead])
async def list_finance_sources(
    principal: Principal = Depends(require_kairo_user),
    session: AsyncSession = Depends(get_session),
) -> list[FinanceSource]:
    rows = await session.execute(
        select(FinanceSource)
        .where(FinanceSource.keycloak_subject == principal.subject)
        .order_by(FinanceSource.display_name, FinanceSource.key)
    )
    return list(rows.scalars())


@router.get("/v1/finance/portfolio", response_model=FinancePortfolioRead)
async def finance_portfolio(
    source_id: uuid.UUID | None = None,
    principal: Principal = Depends(require_kairo_user),
    session: AsyncSession = Depends(get_session),
) -> FinancePortfolioRead:
    if source_id is not None:
        await _owned_source(session, source_id, principal)

    source_statement = select(FinanceSource).where(
        FinanceSource.keycloak_subject == principal.subject
    )
    if source_id is not None:
        source_statement = source_statement.where(FinanceSource.id == source_id)
    source_rows = await session.execute(source_statement.order_by(FinanceSource.display_name))
    sources = list(source_rows.scalars())
    source_ids = [source.id for source in sources]

    if not source_ids:
        return FinancePortfolioRead(
            generated_at=datetime.now(UTC),
            total_value_usd=Decimal("0"),
            total_cost_basis_usd=None,
            total_unrealized_pnl_usd=None,
            sources=[],
            accounts=[],
            positions=[],
        )

    account_rows = await session.execute(
        select(FinanceAccount)
        .where(FinanceAccount.source_id.in_(source_ids))
        .order_by(FinanceAccount.label, FinanceAccount.external_id)
    )
    accounts = list(account_rows.scalars())

    rows = await session.execute(
        select(FinancePosition, FinanceAccount, FinanceSource)
        .join(FinanceAccount, FinanceAccount.id == FinancePosition.account_id)
        .join(FinanceSource, FinanceSource.id == FinanceAccount.source_id)
        .where(FinanceSource.keycloak_subject == principal.subject)
        .where(FinanceSource.id.in_(source_ids))
        .order_by(FinancePosition.value_usd.desc(), FinancePosition.symbol)
    )
    positions: list[FinancePositionRead] = []
    total_value = Decimal("0")
    total_cost_basis = Decimal("0")
    total_pnl = Decimal("0")
    has_cost_basis = False
    has_pnl = False
    for position, account, source in rows:
        value = Decimal(position.value_usd)
        total_value += value
        if position.cost_basis_usd is not None:
            total_cost_basis += Decimal(position.cost_basis_usd)
            has_cost_basis = True
        if position.unrealized_pnl_usd is not None:
            total_pnl += Decimal(position.unrealized_pnl_usd)
            has_pnl = True
        positions.append(
            FinancePositionRead(
                id=position.id,
                source_id=source.id,
                source_key=source.key,
                source_provider=source.provider,
                source_display_name=source.display_name,
                account_id=account.id,
                account_external_id=account.external_id,
                account_label=account.label,
                account_type=account.account_type,
                network=account.network,
                public_address=account.public_address,
                asset_key=position.asset_key,
                symbol=position.symbol,
                name=position.name,
                asset_type=position.asset_type,
                quantity=Decimal(position.quantity),
                unit_price_usd=(
                    Decimal(position.unit_price_usd)
                    if position.unit_price_usd is not None
                    else None
                ),
                value_usd=value,
                cost_basis_usd=(
                    Decimal(position.cost_basis_usd)
                    if position.cost_basis_usd is not None
                    else None
                ),
                unrealized_pnl_usd=(
                    Decimal(position.unrealized_pnl_usd)
                    if position.unrealized_pnl_usd is not None
                    else None
                ),
                metadata=dict(position.metadata_json or {}),
                observed_at=position.observed_at,
            )
        )

    return FinancePortfolioRead(
        generated_at=datetime.now(UTC),
        total_value_usd=total_value,
        total_cost_basis_usd=total_cost_basis if has_cost_basis else None,
        total_unrealized_pnl_usd=total_pnl if has_pnl else None,
        sources=[FinanceSourceRead.model_validate(source) for source in sources],
        accounts=[FinanceAccountRead.model_validate(account) for account in accounts],
        positions=positions,
    )


@router.post(
    "/internal/v1/finance/snapshot",
    response_model=FinanceSnapshotRead,
    dependencies=[Depends(require_internal_token)],
)
async def ingest_finance_snapshot(
    body: FinanceSnapshotIngest,
    session: AsyncSession = Depends(get_session),
) -> FinanceSnapshotRead:
    source = await session.scalar(
        select(FinanceSource)
        .where(
            FinanceSource.keycloak_subject == body.owner_subject,
            FinanceSource.key == body.source.key,
        )
        .with_for_update()
    )
    if source is None:
        account_binding = await session.scalar(
            select(FinanceSource).where(
                FinanceSource.keycloak_subject == body.owner_subject,
                FinanceSource.provider == body.source.provider,
                FinanceSource.external_account_ref == body.source.external_account_ref,
            )
        )
        if account_binding is not None:
            raise HTTPException(
                status_code=409,
                detail="Finance account is already bound to another source key",
            )
        source = FinanceSource(
            keycloak_subject=body.owner_subject,
            key=body.source.key,
            provider=body.source.provider,
            source_type=body.source.source_type,
            external_account_ref=body.source.external_account_ref,
            display_name=body.source.display_name,
            status=body.source.status,
            metadata_json=body.source.metadata,
        )
        session.add(source)
        await session.flush()
    elif (
        source.provider != body.source.provider
        or source.external_account_ref != body.source.external_account_ref
    ):
        raise HTTPException(
            status_code=409,
            detail="Finance source key cannot be rebound to another external account",
        )

    observed_at = datetime.now(UTC)
    source.source_type = body.source.source_type
    source.display_name = body.source.display_name
    source.status = body.source.status
    source.metadata_json = body.source.metadata
    source.last_sync_at = observed_at
    source.last_error = None

    existing_account_rows = await session.execute(
        select(FinanceAccount).where(FinanceAccount.source_id == source.id)
    )
    existing_accounts = {account.external_id: account for account in existing_account_rows.scalars()}
    accounts_by_external: dict[str, FinanceAccount] = {}
    for item in body.accounts:
        account = existing_accounts.get(item.external_id)
        if account is None:
            account = FinanceAccount(
                id=uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    f"kairo:finance-account:{source.id}:{item.external_id}",
                ),
                source_id=source.id,
                external_id=item.external_id,
                label=item.label,
                account_type=item.account_type,
                network=item.network,
                public_address=item.public_address,
                metadata_json=item.metadata,
                observed_at=observed_at,
            )
            session.add(account)
        else:
            account.label = item.label
            account.account_type = item.account_type
            account.network = item.network
            account.public_address = item.public_address
            account.metadata_json = item.metadata
            account.observed_at = observed_at
        accounts_by_external[item.external_id] = account
    await session.flush()

    account_ids = [account.id for account in accounts_by_external.values()]
    existing_positions: dict[tuple[uuid.UUID, str], FinancePosition] = {}
    if account_ids:
        position_rows = await session.execute(
            select(FinancePosition).where(FinancePosition.account_id.in_(account_ids))
        )
        existing_positions = {
            (position.account_id, position.asset_key): position
            for position in position_rows.scalars()
        }

    incoming_assets_by_account: dict[uuid.UUID, set[str]] = {
        account.id: set() for account in accounts_by_external.values()
    }
    for item in body.positions:
        account = accounts_by_external[item.account_external_id]
        incoming_assets_by_account[account.id].add(item.asset_key)
        position = existing_positions.get((account.id, item.asset_key))
        if position is None:
            position = FinancePosition(
                id=uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    f"kairo:finance-position:{account.id}:{item.asset_key}",
                ),
                account_id=account.id,
                asset_key=item.asset_key,
                symbol=item.symbol,
                name=item.name,
                asset_type=item.asset_type,
                quantity=item.quantity,
                unit_price_usd=item.unit_price_usd,
                value_usd=item.value_usd,
                cost_basis_usd=item.cost_basis_usd,
                unrealized_pnl_usd=item.unrealized_pnl_usd,
                metadata_json=item.metadata,
                observed_at=observed_at,
            )
            session.add(position)
        else:
            position.symbol = item.symbol
            position.name = item.name
            position.asset_type = item.asset_type
            position.quantity = item.quantity
            position.unit_price_usd = item.unit_price_usd
            position.value_usd = item.value_usd
            position.cost_basis_usd = item.cost_basis_usd
            position.unrealized_pnl_usd = item.unrealized_pnl_usd
            position.metadata_json = item.metadata
            position.observed_at = observed_at

    removed_positions = 0
    removed_accounts = 0
    if body.replace_missing:
        for account in accounts_by_external.values():
            kept_assets = incoming_assets_by_account[account.id]
            statement = delete(FinancePosition).where(FinancePosition.account_id == account.id)
            if kept_assets:
                statement = statement.where(~FinancePosition.asset_key.in_(kept_assets))
            result = await session.execute(statement)
            removed_positions += int(result.rowcount or 0)

        incoming_account_external_ids = set(accounts_by_external)
        missing_accounts = [
            account
            for external_id, account in existing_accounts.items()
            if external_id not in incoming_account_external_ids
        ]
        if missing_accounts:
            missing_ids = [account.id for account in missing_accounts]
            cascaded_positions = await session.scalar(
                select(func.count())
                .select_from(FinancePosition)
                .where(FinancePosition.account_id.in_(missing_ids))
            )
            removed_positions += int(cascaded_positions or 0)
            result = await session.execute(
                delete(FinanceAccount).where(FinanceAccount.id.in_(missing_ids))
            )
            removed_accounts = int(result.rowcount or 0)

    correlation_id = uuid.uuid4()
    await enqueue_domain_event(
        session,
        event_type="finance.source.synced",
        aggregate_type="finance_source",
        aggregate_id=source.id,
        correlation_id=correlation_id,
        payload={
            "finance_source_id": str(source.id),
            "provider": source.provider,
            "account_count": len(body.accounts),
            "position_count": len(body.positions),
            "removed_accounts": removed_accounts,
            "removed_positions": removed_positions,
            "observed_at": observed_at.isoformat(),
        },
    )
    await append_audit(
        session,
        actor_type="connector",
        actor_id=f"finance:{source.provider}",
        action="finance.snapshot.ingest",
        resource_type="finance_source",
        resource_id=str(source.id),
        authority_level=1,
        correlation_id=correlation_id,
        request_json={
            "owner_subject": body.owner_subject,
            "source_key": source.key,
            "provider": source.provider,
            "account_count": len(body.accounts),
            "position_count": len(body.positions),
            "replace_missing": body.replace_missing,
        },
        result_json={
            "removed_accounts": removed_accounts,
            "removed_positions": removed_positions,
        },
    )
    await session.commit()
    await session.refresh(source)
    return FinanceSnapshotRead(
        source=FinanceSourceRead.model_validate(source),
        received_accounts=len(body.accounts),
        received_positions=len(body.positions),
        removed_accounts=removed_accounts,
        removed_positions=removed_positions,
        observed_at=observed_at,
    )


@router.get(
    "/v1/finance/transaction-proposals",
    response_model=list[FinanceTransactionProposalRead],
)
async def list_finance_transaction_proposals(
    proposal_status: str | None = None,
    principal: Principal = Depends(require_kairo_user),
    session: AsyncSession = Depends(get_session),
) -> list[FinanceTransactionProposalRead]:
    statement = (
        select(FinanceTransactionProposal)
        .where(FinanceTransactionProposal.keycloak_subject == principal.subject)
        .order_by(FinanceTransactionProposal.created_at.desc())
    )
    if proposal_status:
        statement = statement.where(FinanceTransactionProposal.status == proposal_status)
    rows = await session.execute(statement)
    return [
        FinanceTransactionProposalRead.model_validate(proposal)
        for proposal in rows.scalars()
    ]


@router.post(
    "/v1/finance/transaction-proposals",
    response_model=FinanceTransactionProposalRead,
    status_code=201,
)
async def create_finance_transaction_proposal(
    body: FinanceTransactionProposalCreate,
    principal: Principal = Depends(require_kairo_user),
    session: AsyncSession = Depends(get_session),
) -> FinanceTransactionProposalRead:
    account, _source = await _owned_account(session, body.from_account_id, principal)
    if body.project_id is not None:
        await require_owned_project(session, body.project_id, principal.subject)
    if account.network and body.network != account.network:
        raise HTTPException(
            status_code=409,
            detail="Transaction proposal network does not match the selected finance account",
        )

    observed_position = await session.scalar(
        select(FinancePosition).where(
            FinancePosition.account_id == account.id,
            FinancePosition.asset_key == body.asset_key,
        )
    )
    if observed_position is None:
        raise HTTPException(
            status_code=409,
            detail="Transaction asset is not present in the latest observed account snapshot",
        )
    if observed_position.symbol != body.symbol:
        raise HTTPException(
            status_code=409,
            detail="Transaction symbol does not match the observed finance position",
        )

    proposal = FinanceTransactionProposal(
        keycloak_subject=principal.subject,
        project_id=body.project_id,
        from_account_id=account.id,
        kind=body.kind,
        network=body.network,
        asset_key=observed_position.asset_key,
        symbol=observed_position.symbol,
        amount=body.amount,
        destination=body.destination,
        memo=body.memo,
        estimated_fee_asset=body.estimated_fee_asset,
        estimated_fee_amount=body.estimated_fee_amount,
        simulation_json={
            **body.simulation,
            "observed_position_id": str(observed_position.id),
            "observed_at": observed_position.observed_at.isoformat(),
        },
        status="draft",
        created_by="user",
    )
    session.add(proposal)
    await session.flush()

    correlation_id = uuid.uuid4()
    await enqueue_domain_event(
        session,
        event_type="finance.transaction.proposal.created",
        aggregate_type="finance_transaction_proposal",
        aggregate_id=proposal.id,
        correlation_id=correlation_id,
        payload={
            "proposal_id": str(proposal.id),
            "from_account_id": str(account.id),
            "network": proposal.network,
            "asset_key": proposal.asset_key,
            "status": proposal.status,
            "signing_boundary": "external_isolated_signer",
        },
    )
    await append_audit(
        session,
        actor_type="user",
        actor_id=principal.subject,
        action="finance.transaction.proposal.create",
        resource_type="finance_transaction_proposal",
        resource_id=str(proposal.id),
        authority_level=1,
        correlation_id=correlation_id,
        request_json={
            "project_id": str(body.project_id) if body.project_id else None,
            "from_account_id": str(account.id),
            "network": body.network,
            "asset_key": observed_position.asset_key,
            "symbol": observed_position.symbol,
            "amount": str(body.amount),
            "destination": body.destination,
            "observed_position_id": str(observed_position.id),
        },
        result_json={
            "status": "draft",
            "signing_required": True,
            "signing_boundary": "external_isolated_signer",
        },
    )
    await session.commit()
    await session.refresh(proposal)
    return FinanceTransactionProposalRead.model_validate(proposal)
