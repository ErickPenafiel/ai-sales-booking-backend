from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.appointment import AppointmentCreate, AppointmentRead, AvailabilityQuery, AvailableSlot, SlotsResponse
from app.schemas.payment import PaymentIntentResponse
from app.services import slot_service

router = APIRouter(prefix="/appointments", tags=["appointments"])


@router.post("/availability", response_model=SlotsResponse)
async def list_available_slots(payload: AvailabilityQuery, db: AsyncSession = Depends(get_db)) -> SlotsResponse:
    slots_by_date = await slot_service.get_slots_for_multiple_days(
        session=db,
        tenant_id=payload.tenant_id,
        provider_id=payload.provider_id,
        service_id=payload.service_id,
        start_date=payload.start_date,
        end_date=payload.end_date,
    )
    return SlotsResponse(slots=slots_by_date)


@router.post("", response_model=AppointmentRead, status_code=status.HTTP_201_CREATED)
async def create_appointment(payload: AppointmentCreate, db: AsyncSession = Depends(get_db)) -> AppointmentRead:
    from datetime import time as time_cls
    from app.services import crud_service
    from app.services.slot_service import times_overlap

    try:
        start_time = time_cls.fromisoformat(payload.start_time)
        end_time = time_cls.fromisoformat(payload.end_time)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid time format. Use HH:MM") from exc

    existing_slots = await slot_service.calculate_available_slots(
        session=db,
        tenant_id=payload.tenant_id,
        provider_id=payload.provider_id,
        service_id=payload.service_id,
        target_date=payload.date,
    )

    if payload.start_time not in existing_slots:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Slot at {payload.start_time} is no longer available"
        )

    appointment = await crud_service.create_appointment(
        db,
        tenant_id=payload.tenant_id,
        provider_id=payload.provider_id,
        service_id=payload.service_id,
        customer_name=payload.customer_name,
        customer_phone=payload.customer_phone,
        date=payload.date,
        start_time=start_time,
        end_time=end_time,
        notes=payload.notes,
    )
    await db.commit()

    return AppointmentRead.model_validate(appointment)


@router.get("/{appointment_id}/payment-intent", response_model=PaymentIntentResponse)
async def get_payment_intent(appointment_id: UUID, db: AsyncSession = Depends(get_db)) -> PaymentIntentResponse:
    from app.services import crud_service

    appointment = await crud_service.get_appointment(db, appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    return PaymentIntentResponse(
        client_secret="mock_client_secret_" + str(appointment_id),
        payment_intent_id="mock_pi_" + str(appointment_id),
    )