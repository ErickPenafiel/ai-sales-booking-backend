from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.config import (
    AvailabilityCreate,
    AvailabilityRead,
    ServiceCreate,
    ServiceRead,
    SlotRead,
    SlotsResponse,
)
from app.services.booking_service import BookingService, BookingValidationError

router = APIRouter(prefix="/config", tags=["config"])


@router.post("/resources/{resource_id}/availability", response_model=AvailabilityRead, status_code=status.HTTP_201_CREATED)
async def create_resource_availability(
    resource_id: UUID,
    payload: AvailabilityCreate,
    db: AsyncSession = Depends(get_db),
) -> AvailabilityRead:
    service = BookingService(db)
    try:
        availability = await service.create_availability(
            tenant_id=payload.tenant_id,
            resource_id=resource_id,
            day_of_week=payload.day_of_week,
            start_time=payload.start_time,
            end_time=payload.end_time,
            is_active=payload.is_active,
        )
    except BookingValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    await db.commit()
    return AvailabilityRead(
        id=availability.id,
        tenant_id=availability.tenant_id,
        resource_id=availability.resource_id,
        day_of_week=availability.day_of_week,
        start_time=availability.start_time,
        end_time=availability.end_time,
        is_active=availability.is_active,
    )


@router.post("/services", response_model=ServiceRead, status_code=status.HTTP_201_CREATED)
async def create_service(payload: ServiceCreate, db: AsyncSession = Depends(get_db)) -> ServiceRead:
    service = BookingService(db)
    try:
        created = await service.create_service(
            tenant_id=payload.tenant_id,
            resource_id=payload.resource_id,
            name=payload.name,
            description=payload.description,
            duration_minutes=payload.duration_minutes,
            price_amount=float(payload.price_amount),
            currency=payload.currency.upper(),
        )
    except BookingValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    await db.commit()
    return ServiceRead(
        id=created.id,
        tenant_id=created.tenant_id,
        resource_id=created.resource_id,
        name=created.name,
        description=created.description,
        duration_minutes=created.duration_minutes,
        price_amount=created.price_amount,
        currency=created.currency,
    )


@router.get("/resources/{resource_id}/slots", response_model=SlotsResponse)
async def get_resource_slots(
    resource_id: UUID,
    tenant_id: UUID = Query(...),
    service_id: UUID = Query(...),
    date_value: date = Query(..., alias="date"),
    timezone_name: str = Query("America/La_Paz", alias="timezone"),
    db: AsyncSession = Depends(get_db),
) -> SlotsResponse:
    service = BookingService(db)
    try:
        slots = await service.get_resource_slots_for_date(
            tenant_id=tenant_id,
            resource_id=resource_id,
            service_id=service_id,
            target_date=date_value,
            timezone_name=timezone_name,
        )
    except BookingValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return SlotsResponse(
        date=date_value,
        resource_id=resource_id,
        service_id=service_id,
        timezone=timezone_name,
        slots=[SlotRead(start_at=s.start_at, end_at=s.end_at) for s in slots],
    )
