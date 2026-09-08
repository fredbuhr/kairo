import uuid
from datetime import UTC, datetime

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import Principal, require_kairo_admin, require_kairo_user
from .db import get_session
from .events import append_audit, enqueue_domain_event
from .models import DeviceRegistration, SecretReference
from .openbao import openbao_client
from .schemas import (
    DeviceRegistrationCreate,
    DeviceRegistrationRead,
    DeviceRegistrationUpdate,
    SecretReferenceCreate,
    SecretReferenceRead,
    SecretReferenceStatusRead,
    SecretReferenceUpdate,
)

router = APIRouter()


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


async def _secret_reference(reference_id: uuid.UUID, session: AsyncSession) -> SecretReference:
    reference = await session.get(SecretReference, reference_id)
    if not reference:
        raise HTTPException(status_code=404, detail="Secret reference not found")
    return reference


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
    principal: Principal = Depends(require_kairo_admin),
    session: AsyncSession = Depends(get_session),
) -> SecretReference:
    # Only metadata and the OpenBao API path are accepted. Secret values are never accepted here.
    correlation_id = uuid.uuid4()
    reference = SecretReference(**body.model_dump())
    session.add(reference)
    await _flush_or_conflict(session, "Secret provider path is already registered")
    await enqueue_domain_event(
        session,
        event_type="secret-reference.created",
        aggregate_type="secret-reference",
        aggregate_id=reference.id,
        correlation_id=correlation_id,
        payload={
            "secret_reference_id": str(reference.id),
            "name": reference.name,
            "provider_path": reference.provider_path,
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
        authority_level=2,
        correlation_id=correlation_id,
        request_json={
            "name": reference.name,
            "provider_path": reference.provider_path,
            "purpose": reference.purpose,
        },
    )
    await session.commit()
    await session.refresh(reference)
    return reference


@router.get("/v1/secret-references", response_model=list[SecretReferenceRead])
async def list_secret_references(
    _principal: Principal = Depends(require_kairo_admin),
    session: AsyncSession = Depends(get_session),
) -> list[SecretReference]:
    result = await session.execute(select(SecretReference).order_by(SecretReference.created_at))
    return list(result.scalars())


@router.get("/v1/secret-references/{reference_id}", response_model=SecretReferenceRead)
async def get_secret_reference(
    reference_id: uuid.UUID,
    _principal: Principal = Depends(require_kairo_admin),
    session: AsyncSession = Depends(get_session),
) -> SecretReference:
    return await _secret_reference(reference_id, session)


@router.get(
    "/v1/secret-references/{reference_id}/status",
    response_model=SecretReferenceStatusRead,
)
async def get_secret_reference_status(
    reference_id: uuid.UUID,
    _principal: Principal = Depends(require_kairo_admin),
    session: AsyncSession = Depends(get_session),
) -> SecretReferenceStatusRead:
    reference = await _secret_reference(reference_id, session)
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


@router.patch("/v1/secret-references/{reference_id}", response_model=SecretReferenceRead)
async def update_secret_reference(
    reference_id: uuid.UUID,
    body: SecretReferenceUpdate,
    principal: Principal = Depends(require_kairo_admin),
    session: AsyncSession = Depends(get_session),
) -> SecretReference:
    reference = await _secret_reference(reference_id, session)
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
        authority_level=2,
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
    principal: Principal = Depends(require_kairo_admin),
    session: AsyncSession = Depends(get_session),
) -> None:
    reference = await _secret_reference(reference_id, session)
    correlation_id = uuid.uuid4()
    await append_audit(
        session,
        actor_type="user",
        actor_id=principal.subject,
        action="secret-reference.delete",
        resource_type="secret-reference",
        resource_id=str(reference.id),
        authority_level=2,
        correlation_id=correlation_id,
        request_json={"provider_path": reference.provider_path},
    )
    await session.delete(reference)
    await session.commit()
