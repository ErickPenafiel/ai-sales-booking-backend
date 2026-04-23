from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class AvailabilityCreate(BaseModel):
    tenant_id: UUID
    day_of_week: int = Field(ge=0, le=6)
    start_time: time
    end_time: time
    is_active: bool = True


class AvailabilityRead(BaseModel):
    id: UUID
    tenant_id: UUID
    resource_id: UUID
    day_of_week: int
    start_time: time
    end_time: time
    is_active: bool


class ServiceCreate(BaseModel):
    tenant_id: UUID
    resource_id: UUID
    name: str = Field(min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    duration_minutes: int = Field(gt=0, le=720)
    price_amount: Decimal = Decimal("0")
    currency: str = Field(default="USD", min_length=3, max_length=3)


class ServiceRead(BaseModel):
    id: UUID
    tenant_id: UUID
    resource_id: UUID
    name: str
    description: str | None
    duration_minutes: int
    price_amount: Decimal
    currency: str


class SlotRead(BaseModel):
    start_at: datetime
    end_at: datetime


class SlotsResponse(BaseModel):
    date: date
    resource_id: UUID
    service_id: UUID
    timezone: str
    slots: list[SlotRead]
