import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from .db import get_session
from .events import append_audit, enqueue_domain_event
from .models import DeviceRegistration, SecretReference
from .schemas import (
    DeviceRegistrationCreate,
    DeviceRegistrationRead,
    DeviceRegistrationUpdate,
    SecretReferenceCreate,
    SecretReferenceRead,
    SecretReferenceUpdate,
)

router = APIRouter()


async def _commit_or_conflict(session: AsyncSession, detail: str) -> None:
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail) from exc


@router.post(
    "/v1/devices",
    response_model=DeviceRegistrationRead,
    status_code=status.HTTP_201_CREATED,
)
async def register_device(
    body: DeviceRegistrationCreate,
    session: AsyncSession = Depends(get_session),
) -> DeviceRegistration:
    correlation_id = uuid.uuid4()
    device = DeviceRegistration(**body.model_dump())
    session.add(device)
    await session.flush()
    await enqueue_domain_event(
        session,
        event_type="device.registered",
        aggregate_type="device",
        aggregate_id=device.id,
        correlation_id=correlation_id,
        payload={
            "device_id": str(device.id),
            "subject": device.keycloak_subject,
            "device_key": device.device_key,
            "platform": device.platform,
        },
    )
    await append_audit(
        session,
        actor_type="user",
        actor_id=device.keycloak_subject,
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
    await _commit_or_conflict(session, "Device is already registered for this subject")
    await session.refresh(device)
    return device


@router.get("/v1/devices", response_model=list[DeviceRegistrationRead])
async def list_devices(
    keycloak_subject: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> list[DeviceRegistration]:
    statement = select(DeviceRegistration).order_by(DeviceRegistration.created_at)
    if keycloak_subject:
        statement = statement.where(DeviceRegistration.keycloak_subject == keycloak_subject)
    result = await session.execute(statement)
    return list(result.scalars())


@router.get("/v1/devices/{device_id}", response_model=DeviceRegistrationRead)
async def get_device(
    device_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> DeviceRegistration:
    device = await session.get(DeviceRegistration, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return device


@router.patch("/v1/devices/{device_id}", response_model=DeviceRegistrationRead)
async def update_device(
    device_id: uuid.UUID,
    body: DeviceRegistrationUpdate,
    session: AsyncSession = Depends(get_session),
) -> DeviceRegistration:
    device = await session.get(DeviceRegistration, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

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
            "subject": device.keycloak_subject,
            "changed_fields": sorted(changes),
        },
    )
    await append_audit(
        session,
        actor_type="user",
        actor_id=device.keycloak_subject,
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
    session: AsyncSession = Depends(get_session),
) -> None:
    device = await session.get(DeviceRegistration, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    correlation_id = uuid.uuid4()
    subject = device.keycloak_subject
    await append_audit(
        session,
        actor_type="user",
        actor_id=subject,
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
    session: AsyncSession = Depends(get_session),
) -> SecretReference:
    # This endpoint intentionally accepts only a provider path and metadata. Secret values are never
    # accepted by this contract and therefore cannot accidentally enter PostgreSQL or the audit log.
    correlation_id = uuid.uuid4()
    reference = SecretReference(**body.model_dump())
    session.add(reference)
    await session.flush()
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
        actor_type="system",
        actor_id="resource-api",
        action="secret-reference.create",
        resource_type="secret-reference",
        resource_id=str(reference.id),
        authority_level=1,
        correlation_id=correlation_id,
        request_json={
            "name": reference.name,
            "provider_path": reference.provider_path,
            "purpose": reference.purpose,
        },
    )
    await _commit_or_conflict(session, "Secret provider path is already registered")
    await session.refresh(reference)
    return reference


@router.get("/v1/secret-references", response_model=list[SecretReferenceRead])
async def list_secret_references(
    session: AsyncSession = Depends(get_session),
) -> list[SecretReference]:
    result = await session.execute(select(SecretReference).order_by(SecretReference.created_at))
    return list(result.scalars())


@router.get("/v1/secret-references/{reference_id}", response_model=SecretReferenceRead)
async def get_secret_reference(
    reference_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> SecretReference:
    reference = await session.get(SecretReference, reference_id)
    if not reference:
        raise HTTPException(status_code=404, detail="Secret reference not found")
    return reference


@router.patch("/v1/secret-references/{reference_id}", response_model=SecretReferenceRead)
async def update_secret_reference(
    reference_id: uuid.UUID,
    body: SecretReferenceUpdate,
    session: AsyncSession = Depends(get_session),
) -> SecretReference:
    reference = await session.get(SecretReference, reference_id)
    if not reference:
        raise HTTPException(status_code=404, detail="Secret reference not found")

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
        actor_type="system",
        actor_id="resource-api",
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
    session: AsyncSession = Depends(get_session),
) -> None:
    reference = await session.get(SecretReference, reference_id)
    if not reference:
        raise HTTPException(status_code=404, detail="Secret reference not found")

    correlation_id = uuid.uuid4()
    await append_audit(
        session,
        actor_type="system",
        actor_id="resource-api",
        action="secret-reference.delete",
        resource_type="secret-reference",
        resource_id=str(reference.id),
        authority_level=1,
        correlation_id=correlation_id,
        request_json={"provider_path": reference.provider_path},
    )
    await session.delete(reference)
    await session.commit()
