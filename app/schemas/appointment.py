from __future__ import annotations

from datetime import date, time
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import AppointmentStatus


class AvailableSlot(BaseModel):
    start_time: str  # HH:MM format
    end_time: str  # HH:MM format


class AppointmentCreate(BaseModel):
    tenant_id: UUID
    provider_id: UUID
    service_id: UUID
    customer_name: str = Field(min_length=2, max_length=120)
    customer_phone: str = Field(min_length=6, max_length=32)
    date: date
    start_time: str  # HH:MM format
    end_time: str  # HH:MM format
    notes: str | None = Field(default=None, max_length=500)


class AppointmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    provider_id: UUID
    service_id: UUID
    date: date
    start_time: str  # HH:MM format
    end_time: str  # HH:MM format
    customer_name: str
    customer_phone: str
    total_amount: Decimal
    currency: str
    status: AppointmentStatus


class AvailabilityQuery(BaseModel):
    tenant_id: UUID
    provider_id: UUID
    service_id: UUID
    start_date: date
    end_date: date
    timezone: str = Field(default="UTC")


class SlotsResponse(BaseModel):
    slots: dict[str, list[str]]  # date -> ["HH:MM", "HH:MM", ...]