"""
CRUD API endpoints for Appointments.
"""

from datetime import date, time, datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.appointment import AppointmentStatus
from app.services import crud_service
from app.api.v1.endpoints.crud_shared import model_to_dict

router = APIRouter()


def _parse_date(date_str: str) -> date:
    """Parse date string (YYYY-MM-DD) to date object."""
    return datetime.strptime(date_str, "%Y-%m-%d").date()


def _parse_time(time_str: str) -> time:
    """Parse time string (HH:MM or HH:MM:SS) to time object."""
    if len(time_str) == 5:
        return datetime.strptime(time_str, "%H:%M").time()
    return datetime.strptime(time_str, "%H:%M:%S").time()


class AppointmentCreate(BaseModel):
    provider_id: UUID
    service_id: UUID
    customer_name: str = Field(..., min_length=1, max_length=120)
    customer_phone: str = Field(..., min_length=1, max_length=32)
    date: str  # YYYY-MM-DD
    start_time: str  # HH:MM
    end_time: str  # HH:MM
    notes: str | None = Field(None, max_length=500)
    total_amount: float = 0.0
    currency: str = Field("USD", min_length=3, max_length=3)
    status: AppointmentStatus = AppointmentStatus.PENDING_PAYMENT


class AppointmentUpdate(BaseModel):
    customer_name: str | None = None
    customer_phone: str | None = None
    date: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    notes: str | None = None
    status: AppointmentStatus | None = None
    total_amount: float | None = None


@router.post("/tenants/{tenant_id}/appointments", status_code=201)
async def create_appointment(
    tenant_id: UUID, data: AppointmentCreate, db: AsyncSession = Depends(get_db)
):
    try:
        appointment = await crud_service.create_appointment(
            db,
            tenant_id=tenant_id,
            provider_id=data.provider_id,
            service_id=data.service_id,
            customer_name=data.customer_name,
            customer_phone=data.customer_phone,
            date=_parse_date(data.date),
            start_time=_parse_time(data.start_time),
            end_time=_parse_time(data.end_time),
            notes=data.notes,
            total_amount=data.total_amount,
            currency=data.currency,
            status=data.status,
        )
        return model_to_dict(appointment)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/appointments/{appointment_id}")
async def get_appointment(appointment_id: UUID, db: AsyncSession = Depends(get_db)):
    appointment = await crud_service.get_appointment(db, appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    return model_to_dict(appointment)


@router.get("/tenants/{tenant_id}/appointments")
async def list_appointments(
    tenant_id: UUID,
    provider_id: UUID | None = Query(None),
    customer_phone: str | None = Query(None),
    status: AppointmentStatus | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    """List appointments for a tenant with optional filters."""
    parsed_date_from = _parse_date(date_from) if date_from else None
    parsed_date_to = _parse_date(date_to) if date_to else None

    appointments = await crud_service.list_appointments(
        db,
        tenant_id=tenant_id,
        provider_id=provider_id,
        customer_phone=customer_phone,
        status=status,
        date_from=parsed_date_from,
        date_to=parsed_date_to,
        skip=skip,
        limit=limit,
    )
    return [model_to_dict(a) for a in appointments]


@router.put("/appointments/{appointment_id}")
async def update_appointment(
    appointment_id: UUID,
    data: AppointmentUpdate,
    db: AsyncSession = Depends(get_db),
):
    try:
        update_data = data.model_dump(exclude_unset=True)
        if "date" in update_data and update_data["date"]:
            update_data["date"] = _parse_date(update_data["date"])
        if "start_time" in update_data and update_data["start_time"]:
            update_data["start_time"] = _parse_time(update_data["start_time"])
        if "end_time" in update_data and update_data["end_time"]:
            update_data["end_time"] = _parse_time(update_data["end_time"])

        appointment = await crud_service.update_appointment(
            db, appointment_id, **update_data
        )
        if not appointment:
            raise HTTPException(status_code=404, detail="Appointment not found")
        return model_to_dict(appointment)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/appointments/{appointment_id}/cancel")
async def cancel_appointment(appointment_id: UUID, db: AsyncSession = Depends(get_db)):
    appointment = await crud_service.update_appointment(
        db, appointment_id, status=AppointmentStatus.CANCELLED
    )
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    return model_to_dict(appointment)


@router.delete("/appointments/{appointment_id}", status_code=204)
async def delete_appointment(appointment_id: UUID, db: AsyncSession = Depends(get_db)):
    deleted = await crud_service.delete_appointment(db, appointment_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Appointment not found")