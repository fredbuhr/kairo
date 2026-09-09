import hashlib
import re
import uuid
from datetime import UTC, datetime

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import Principal, require_kairo_user
from .automation_models import AutomationDefinition
from .config import settings
from .db import get_session
from .events import append_audit, enqueue_domain_event
from .finance_models import FinanceConnector
from .models import DeviceRegistration, SecretReference
from .openbao import openbao_client
from .schemas import (
    DeviceRegistrationCreate,
    DeviceRegistrationRead,
    DeviceRegistrationUpdate,
    SecretReferenceCreate,
    SecretReferenceProvision,
    SecretReferenceRead,
    SecretReferenceStatusRead,
    SecretReferenceUpdate,
)

router = APIRouter()
_SECRET_FIELD = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,119}$")
_MAX_SECRET_VALUE_BYTES = 16 * 1024
_MAX_SECRET_PAYLOAD_BYTES = 64 * 1024


async def _flush_or_conflict(session: AsyncSession, detail: str) -> None:
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail) from exc


async def _owned_device(
    device_id: uuid.UUID, principal: Principal, session: AsyncSession
) -> DeviceRegistration:
    device = await session.get(DeviceRegistration, device_id)
    if not device or device.keycloak_subject != principal.subject:
        raise HTTPException(status_code=404, detail="Device not found")
    return device


def _managed_secret_path(subject: str, reference_id: uuid.UUID) -> str:
    # Do not expose the raw Keycloak subject in the OpenBao hierarchy. The digest is only a namespace
    # partition, not an authentication token; ownership is still enforced by Core before every read.
    namespace = hashlib.sha256(subject.encode("utf-8")).hexdigest()[:24]
    return f"secret/data/kairo/users/{namespace}/{reference_id}"


async def _owned_secret_reference(
    reference_id: uuid.UUID,
    principal: Principal,
    session: AsyncSession,
) -> SecretReference:
    reference = await session.get(SecretReference, reference_id)
    if not reference or reference.keycloak_subject != principal.subject:
        raise HTTPException(status_code=404, detail="Secret reference not found")
    return reference


async def _secret_reference_usage(
    reference_id: uuid.UUID,
    subject: str,
    session: AsyncSession,
) -> tuple[int, int]:
    automation_count, finance_count = await asyncio.gather(
        session.scalar(
            select(func.count())
            .select_from(AutomationDefinition)
            .where(
                AutomationDefinition.webhook_secret_reference_id == reference_id,
                AutomationDefinition.keycloak_subject == subject,
            )
        ),
        session.scalar(
            select(func.count())
            .select_from(FinanceConnector)
            .where(
                FinanceConnector.secret_reference_id == reference_id,
                FinanceConnector.keycloak_subject == subject,
            )
        ),
    )
    return int(automation_count or 0), int(finance_count or 0)


def _validate_secret_values(values: dict[str, str]) -> None:
    total = 0
    for key, value in values.items():
        if not _SECRET_FIELD.fullmatch(key):
            raise HTTPException(status_code=422, detail=f"Unsupported secret field name: {key}")
        encoded = value.encode("utf-8")
        if len(encoded) > _MAX_SECRET_VALUE_BYTES:
            raise HTTPException(status_code=413, detail=f"Secret field {key} exceeds the KAIRO limit")
        total += len(key.encode("utf-8")) + len(encoded)
    if total > _MAX_SECRET_PAYLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Secret payload exceeds the KAIRO limit")


@router.post(
    "/v1/devices",
    response_model=DeviceRegistrationRead,
    status_code=status.HTTP_201_CREATED,
)
async def register_device(
    body: DeviceRegistrationCreate,
    principal: Principal = Depends(require_kairo_user),
    session: AsyncSession = Depends(get_session),
) -> DeviceRegistration:
    correlation_id = uuid.uuid4()
    device = DeviceRegistration(keycloak_subject=principal.subject, **body.model_dump())
    session.add(device)
    await _flush_or_conflict(session, "Device is already registered for this identity")
    await enqueue_domain_event(
        session,
        event_type="device.registered",
        aggregate_type="device",
        aggregate_id=device.id,
        correlation_id=correlation_id,
        payload={
            "device_id": str(device.id),
            "subject": principal.subject,
            "device_key": device.device_key,
            "platform": device.platform,
        },
    )
    await append_audit(
        session,
        actor_type="user",
        actor_id=principal.subject,
        action="device.register",
        resource_type="device",
        resource_id=str(device.id),
        authority_level=1,
        correlation_id=correlation_id,
        request_json={
            "device_key": device.device_key,
            "name": device.name,
            "platform": device.platform,
            "capabilities": device.capabilities,
            "has_public_key": bool(device.public_key),
        },
    )
    await session.commit()
    await session.refresh(device)
    return device


@router.get("/v1/devices", response_model=list[DeviceRegistrationRead])
async def list_devices(
    principal: Principal = Depends(require_kairo_user),
    session: AsyncSession = Depends(get_session),
) -> list[DeviceRegistration]:
    result = await session.execute(
        select(DeviceRegistration)
        .where(DeviceRegistration.keycloak_subject == principal.subject)
        .order_by(DeviceRegistration.created_at)
    )
    return list(result.scalars())


@router.get("/v1/devices/{device_id}", response_model=DeviceRegistrationRead)
async def get_device(
    device_id: uuid.UUID,
    principal: Principal = Depends(require_kairo_user),
    session: AsyncSession = Depends(get_session),
) -> DeviceRegistration:
    return await _owned_device(device_id, principal, session)


@router.patch("/v1/devices/{device_id}", response_model=DeviceRegistrationRead)
async def update_device(
    device_id: uuid.UUID,
    body: DeviceRegistrationUpdate,
    principal: Principal = Depends(require_kairo_user),
    session: AsyncSession = Depends(get_session),
) -> DeviceRegistration:
    device = await _owned_device(device_id, principal, session)
    changes = body.model_dump(exclude_unset=True)
    for key, value in changes.items():
        setattr(device, key, value)
    device.last_seen_at = datetime.now(UTC)

    correlation_id = uuid.uuid4()
    await enqueue_domain_event(
        session,
        event_type="device.updated",
        aggregate_type="device",
        aggregate_id=device.id,
        correlation_id=correlation_id,
        payload={
            "device_id": str(device.id),
            "subject": principal.subject,
            "changed_fields": sorted(changes),
        },
    )
    await append_audit(
        session,
        actor_type="user",
        actor_id=principal.subject,
        action="device.update",
        resource_type="device",
        resource_id=str(device.id),
        authority_level=1,
        correlation_id=correlation_id,
        request_json={"changed_fields": sorted(changes)},
    )
    await session.commit()
    await session.refresh(device)
    return device


@router.delete("/v1/devices/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_device(
    device_id: uuid.UUID,
    principal: Principal = Depends(require_kairo_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    device = await _owned_device(device_id, principal, session)
    correlation_id = uuid.uuid4()
    await append_audit(
        session,
        actor_type="user",
        actor_id=principal.subject,
        action="device.delete",
        resource_type="device",
        resource_id=str(device.id),
        authority_level=1,
        correlation_id=correlation_id,
        request_json={"device_key": device.device_key},
    )
    await session.delete(device)
    await session.commit()


@router.post(
    "/v1/secret-references",
    response_model=SecretReferenceRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_secret_reference(
    body: SecretReferenceCreate,
    principal: Principal = Depends(require_kairo_user),
    session: AsyncSession = Depends(get_session),
) -> SecretReference:
    reference_id = uuid.uuid4()
    if settings.kairo_auth_enabled and body.provider_path is not None:
        raise HTTPException(
            status_code=400,
            detail="Authenticated SecretReference paths are generated by KAIRO",
        )
    provider_path = body.provider_path or _managed_secret_path(principal.subject, reference_id)
    correlation_id = uuid.uuid4()
    reference = SecretReference(
        id=reference_id,
        keycloak_subject=principal.subject,
        name=body.name,
        provider_path=provider_path,
        purpose=body.purpose,
    )
    session.add(reference)
    await _flush_or_conflict(session, "Secret reference could not be registered")
    await enqueue_domain_event(
        session,
        event_type="secret-reference.created",
        aggregate_type="secret-reference",
        aggregate_id=reference.id,
        correlation_id=correlation_id,
        payload={
            "secret_reference_id": str(reference.id),
            "purpose": reference.purpose,
        },
    )
    await append_audit(
        session,
        actor_type="user",
        actor_id=principal.subject,
        action="secret-reference.create",
        resource_type="secret-reference",
        resource_id=str(reference.id),
        authority_level=1,
        correlation_id=correlation_id,
        request_json={"name": reference.name, "purpose": reference.purpose},
    )
    await session.commit()
    await session.refresh(reference)
    return reference


@router.get("/v1/secret-references", response_model=list[SecretReferenceRead])
async def list_secret_references(
    principal: Principal = Depends(require_kairo_user),
    session: AsyncSession = Depends(get_session),
) -> list[SecretReference]:
    result = await session.execute(
        select(SecretReference)
        .where(SecretReference.keycloak_subject == principal.subject)
        .order_by(SecretReference.created_at)
    )
    return list(result.scalars())


@router.get("/v1/secret-references/{reference_id}", response_model=SecretReferenceRead)
async def get_secret_reference(
    reference_id: uuid.UUID,
    principal: Principal = Depends(require_kairo_user),
    session: AsyncSession = Depends(get_session),
) -> SecretReference:
    return await _owned_secret_reference(reference_id, principal, session)


@router.get(
    "/v1/secret-references/{reference_id}/status",
    response_model=SecretReferenceStatusRead,
)
async def get_secret_reference_status(
    reference_id: uuid.UUID,
    principal: Principal = Depends(require_kairo_user),
    session: AsyncSession = Depends(get_session),
) -> SecretReferenceStatusRead:
    reference = await _owned_secret_reference(reference_id, principal, session)
    try:
        provider_status = await openbao_client.secret_status(reference.provider_path)
    except (httpx.HTTPError, OSError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OpenBao is unavailable or rejected the reference",
        ) from exc
    return SecretReferenceStatusRead(
        reference_id=reference.id,
        exists=provider_status.exists,
        keys=list(provider_status.keys),
        version=provider_status.version,
    )


@router.put(
    "/v1/secret-references/{reference_id}/values",
    response_model=SecretReferenceStatusRead,
)
async def provision_secret_reference(
    reference_id: uuid.UUID,
    body: SecretReferenceProvision,
    principal: Principal = Depends(require_kairo_user),
    session: AsyncSession = Depends(get_session),
) -> SecretReferenceStatusRead:
    reference = await _owned_secret_reference(reference_id, principal, session)
    _validate_secret_values(body.values)
    try:
        provider_status = await openbao_client.write_secret_values(reference.provider_path, body.values)
    except (httpx.HTTPError, OSError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OpenBao is unavailable or rejected secret provisioning",
        ) from exc

    correlation_id = uuid.uuid4()
    keys = sorted(body.values)
    await enqueue_domain_event(
        session,
        event_type="secret-reference.provisioned",
        aggregate_type="secret-reference",
        aggregate_id=reference.id,
        correlation_id=correlation_id,
        payload={
            "secret_reference_id": str(reference.id),
            "keys": keys,
            "version": provider_status.version,
        },
    )
    await append_audit(
        session,
        actor_type="user",
        actor_id=principal.subject,
        action="secret-reference.provision",
        resource_type="secret-reference",
        resource_id=str(reference.id),
        authority_level=1,
        correlation_id=correlation_id,
        request_json={"keys": keys, "field_count": len(keys)},
        result_json={"version": provider_status.version},
    )
    await session.commit()
    return SecretReferenceStatusRead(
        reference_id=reference.id,
        exists=True,
        keys=list(provider_status.keys),
        version=provider_status.version,
    )


@router.delete(
    "/v1/secret-references/{reference_id}/values",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def destroy_secret_reference_values(
    reference_id: uuid.UUID,
    principal: Principal = Depends(require_kairo_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    reference = await _owned_secret_reference(reference_id, principal, session)
    try:
        before = await openbao_client.secret_status(reference.provider_path)
        await openbao_client.destroy_secret_values(reference.provider_path)
    except (httpx.HTTPError, OSError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OpenBao is unavailable or rejected secret destruction",
        ) from exc

    correlation_id = uuid.uuid4()
    await enqueue_domain_event(
        session,
        event_type="secret-reference.values-destroyed",
        aggregate_type="secret-reference",
        aggregate_id=reference.id,
        correlation_id=correlation_id,
        payload={
            "secret_reference_id": str(reference.id),
            "keys": list(before.keys),
            "previous_version": before.version,
            "existed": before.exists,
        },
    )
    await append_audit(
        session,
        actor_type="user",
        actor_id=principal.subject,
        action="secret-reference.values.destroy",
        resource_type="secret-reference",
        resource_id=str(reference.id),
        authority_level=1,
        correlation_id=correlation_id,
        request_json={"explicit_irreversible_action": True},
        result_json={
            "keys": list(before.keys),
            "previous_version": before.version,
            "existed": before.exists,
        },
    )
    await session.commit()


@router.patch("/v1/secret-references/{reference_id}", response_model=SecretReferenceRead)
async def update_secret_reference(
    reference_id: uuid.UUID,
    body: SecretReferenceUpdate,
    principal: Principal = Depends(require_kairo_user),
    session: AsyncSession = Depends(get_session),
) -> SecretReference:
    reference = await _owned_secret_reference(reference_id, principal, session)
    changes = body.model_dump(exclude_unset=True)
    for key, value in changes.items():
        setattr(reference, key, value)

    correlation_id = uuid.uuid4()
    await enqueue_domain_event(
        session,
        event_type="secret-reference.updated",
        aggregate_type="secret-reference",
        aggregate_id=reference.id,
        correlation_id=correlation_id,
        payload={
            "secret_reference_id": str(reference.id),
            "changed_fields": sorted(changes),
        },
    )
    await append_audit(
        session,
        actor_type="user",
        actor_id=principal.subject,
        action="secret-reference.update",
        resource_type="secret-reference",
        resource_id=str(reference.id),
        authority_level=1,
        correlation_id=correlation_id,
        request_json={"changed_fields": sorted(changes)},
    )
    await session.commit()
    await session.refresh(reference)
    return reference


@router.delete(
    "/v1/secret-references/{reference_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_secret_reference(
    reference_id: uuid.UUID,
    principal: Principal = Depends(require_kairo_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    reference = await _owned_secret_reference(reference_id, principal, session)
    automation_count, finance_count = await _secret_reference_usage(
        reference.id,
        principal.subject,
        session,
    )
    if automation_count or finance_count:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Secret reference is still in use",
                "automations": automation_count,
                "finance_connectors": finance_count,
            },
        )

    try:
        provider_status = await openbao_client.secret_status(reference.provider_path)
    except (httpx.HTTPError, OSError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OpenBao is unavailable; KAIRO cannot prove the secret is empty",
        ) from exc
    if provider_status.exists:
        raise HTTPException(
            status_code=409,
            detail="Secret values still exist; destroy them explicitly before removing the reference",
        )

    correlation_id = uuid.uuid4()
    await enqueue_domain_event(
        session,
        event_type="secret-reference.deleted",
        aggregate_type="secret-reference",
        aggregate_id=reference.id,
        correlation_id=correlation_id,
        payload={"secret_reference_id": str(reference.id), "purpose": reference.purpose},
    )
    await append_audit(
        session,
        actor_type="user",
        actor_id=principal.subject,
        action="secret-reference.delete",
        resource_type="secret-reference",
        resource_id=str(reference.id),
        authority_level=1,
        correlation_id=correlation_id,
        request_json={"purpose": reference.purpose, "provider_values_absent": True},
    )
    await session.delete(reference)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Secret reference is still in use") from exc
