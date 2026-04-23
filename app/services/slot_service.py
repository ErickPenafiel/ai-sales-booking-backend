from __future__ import annotations

from datetime import date, time, timedelta
from uuid import UUID

from sqlalchemy import Select, and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appointment import Appointment
from app.models.appointment import AppointmentStatus
from app.models.availability import Availability
from app.models.service import Service


class SlotCalculationError(Exception):
    """Raised when slot calculation fails."""


def time_to_minutes(t: time) -> int:
    return t.hour * 60 + t.minute


def minutes_to_time(minutes: int) -> time:
    return time(minutes // 60, minutes % 60)


def times_overlap(
    slot_start: time, slot_end: time, appointment_start: time, appointment_end: time
) -> bool:
    return slot_start < appointment_end and slot_end > appointment_start


async def calculate_available_slots(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    provider_id: UUID,
    service_id: UUID,
    target_date: date,
) -> list[str]:
    """
    Calculate available time slots for a provider/service on a specific date.

    Args:
        session: Database session
        tenant_id: Tenant UUID
        provider_id: Provider UUID
        service_id: Service UUID
        target_date: Date to check availability

    Returns:
        List of available start times as strings (HH:MM format)
    """
    day_of_week = target_date.weekday()

    availability = await session.scalar(
        select(Availability).where(
            Availability.tenant_id == tenant_id,
            Availability.provider_id == provider_id,
            Availability.day_of_week == day_of_week,
            Availability.is_active.is_(True),
        )
    )
    if availability is None:
        return []

    service = await session.scalar(
        select(Service).where(
            Service.id == service_id,
            Service.tenant_id == tenant_id,
        )
    )
    if service is None:
        raise SlotCalculationError("Service not found")

    duration = service.duration_minutes

    appointments_query: Select[tuple[Appointment]] = (
        select(Appointment)
        .where(
            Appointment.tenant_id == tenant_id,
            Appointment.provider_id == provider_id,
            Appointment.date == target_date,
            Appointment.status.in_([
                AppointmentStatus.PENDING_PAYMENT,
                AppointmentStatus.CONFIRMED,
            ]),
        )
    )
    appointments = list(await session.scalars(appointments_query))

    available_slots: list[str] = []
    window_start = time_to_minutes(availability.start_time)
    window_end = time_to_minutes(availability.end_time)

    current = window_start
    while current + duration <= window_end:
        slot_start = minutes_to_time(current)
        slot_end = minutes_to_time(current + duration)

        is_available = True
        for appt in appointments:
            if times_overlap(slot_start, slot_end, appt.start_time, appt.end_time):
                is_available = False
                break

        if is_available:
            available_slots.append(slot_start.strftime("%H:%M"))

        current += duration

    return available_slots


async def get_slots_for_multiple_days(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    provider_id: UUID,
    service_id: UUID,
    start_date: date,
    end_date: date,
) -> dict[str, list[str]]:
    """
    Get available slots for multiple days.

    Args:
        session: Database session
        tenant_id: Tenant UUID
        provider_id: Provider UUID
        service_id: Service UUID
        start_date: Start date (inclusive)
        end_date: End date (inclusive)

    Returns:
        Dictionary mapping date strings to lists of available times
    """
    result: dict[str, list[str]] = {}
    current = start_date

    while current <= end_date:
        slots = await calculate_available_slots(
            session=session,
            tenant_id=tenant_id,
            provider_id=provider_id,
            service_id=service_id,
            target_date=current,
        )
        result[current.isoformat()] = slots
        current += timedelta(days=1)

    return result