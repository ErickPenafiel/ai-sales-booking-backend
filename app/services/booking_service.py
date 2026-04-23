from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone, tzinfo
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import Select, and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appointment import Appointment
from app.models.availability import Availability
from app.models.enums import AppointmentStatus
from app.models.provider import Provider
from app.models.service import Service


class BookingConflictError(Exception):
    """Raised when a booking overlaps with an existing active appointment."""


class BookingValidationError(Exception):
    """Raised when booking input does not satisfy domain constraints."""


@dataclass(frozen=True)
class Slot:
    start_at: datetime
    end_at: datetime


class BookingService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_service(
        self,
        *,
        tenant_id: UUID,
        provider_id: UUID,
        name: str,
        duration_minutes: int,
        description: str | None = None,
        price_amount: float = 0.0,
        currency: str = "USD",
    ) -> Service:
        if duration_minutes <= 0:
            raise BookingValidationError("duration_minutes must be greater than 0")

        await self._ensure_provider(tenant_id=tenant_id, provider_id=provider_id)
        service = Service(
            tenant_id=tenant_id,
            provider_id=provider_id,
            name=name,
            description=description,
            duration_minutes=duration_minutes,
            price_amount=price_amount,
            currency=currency,
        )
        self.session.add(service)
        await self.session.flush()
        await self.session.refresh(service)
        return service

    async def create_availability(
        self,
        *,
        tenant_id: UUID,
        provider_id: UUID,
        day_of_week: int,
        start_time: time,
        end_time: time,
        is_active: bool = True,
    ) -> Availability:
        if day_of_week < 0 or day_of_week > 6:
            raise BookingValidationError("day_of_week must be between 0 and 6")
        if start_time >= end_time:
            raise BookingValidationError("start_time must be before end_time")

        await self._ensure_provider(tenant_id=tenant_id, provider_id=provider_id)
        availability = Availability(
            tenant_id=tenant_id,
            provider_id=provider_id,
            day_of_week=day_of_week,
            start_time=start_time,
            end_time=end_time,
            is_active=is_active,
        )
        self.session.add(availability)
        await self.session.flush()
        await self.session.refresh(availability)
        return availability

    async def get_provider_slots_for_date(
        self,
        *,
        tenant_id: UUID,
        provider_id: UUID,
        service_id: UUID | None,
        target_date: date,
        timezone_name: str = "UTC",
        slot_granularity_minutes: int | None = None,
    ) -> list[Slot]:
        if service_id is None:
            service = await self._get_default_service(tenant_id=tenant_id, provider_id=provider_id)
        else:
            service = await self._get_service(tenant_id=tenant_id, service_id=service_id, provider_id=provider_id)
        duration = timedelta(minutes=service.duration_minutes)
        granularity = slot_granularity_minutes or service.duration_minutes
        if granularity <= 0:
            raise BookingValidationError("slot_granularity_minutes must be greater than 0")

        tz = self._get_tz(timezone_name)
        availabilities = await self._get_availabilities(tenant_id=tenant_id, provider_id=provider_id)
        windows = [a for a in availabilities if a.day_of_week == target_date.weekday()]
        if not windows:
            return []

        utc_windows: list[tuple[datetime, datetime]] = []
        for w in windows:
            w_start, w_end = self._local_window_to_utc_naive(
                target_date=target_date,
                start_t=w.start_time,
                end_t=w.end_time,
                tz=tz,
            )
            utc_windows.append((w_start, w_end))

        range_start = min(w[0] for w in utc_windows)
        range_end = max(w[1] for w in utc_windows)
        existing_appointments = await self._get_blocking_appointments(
            tenant_id=tenant_id,
            provider_id=provider_id,
            range_start=range_start,
            range_end=range_end,
        )

        now_utc = datetime.utcnow()
        slots: list[Slot] = []
        step = timedelta(minutes=granularity)
        for w_start, w_end in utc_windows:
            cursor = w_start
            while cursor + duration <= w_end:
                end_cursor = cursor + duration
                if cursor >= now_utc and not self._has_overlap(cursor, end_cursor, existing_appointments):
                    slots.append(Slot(start_at=cursor, end_at=end_cursor))
                cursor += step

        return slots

    async def get_free_hours_for_ai(
        self,
        *,
        tenant_id: UUID,
        provider_name: str,
        service_name: str,
        target_date: date,
        timezone_name: str = "UTC",
    ) -> dict[str, object]:
        """Helper for AI: resolve provider/service by name and return human-friendly slots."""
        provider = await self.session.scalar(
            select(Provider).where(
                Provider.tenant_id == tenant_id,
                Provider.name == provider_name,
            )
        )
        if provider is None:
            raise BookingValidationError("Provider not found for tenant")

        service = await self.session.scalar(
            select(Service).where(
                Service.tenant_id == tenant_id,
                Service.provider_id == provider.id,
                Service.name == service_name,
            )
        )
        if service is None:
            raise BookingValidationError("Service not found for tenant/provider")

        slots = await self.get_provider_slots_for_date(
            tenant_id=tenant_id,
            provider_id=provider.id,
            service_id=service.id,
            target_date=target_date,
            timezone_name=timezone_name,
            slot_granularity_minutes=service.duration_minutes,
        )
        tz = self._get_tz(timezone_name)
        human_slots: list[str] = []
        for s in slots:
            local_start = s.start_at.replace(tzinfo=timezone.utc).astimezone(tz)
            human_slots.append(local_start.strftime("%H:%M"))

        return {
            "provider_name": provider.name,
            "service_name": service.name,
            "date": target_date.isoformat(),
            "timezone": timezone_name,
            "available_slots": human_slots,
            "found_in_qdrant": None,
        }

    async def get_available_slots(
        self,
        *,
        tenant_id: UUID,
        provider_id: UUID,
        service_id: UUID | None,
        start_date: date,
        end_date: date,
        slot_granularity_minutes: int = 15,
        timezone_name: str = "UTC",
    ) -> list[Slot]:
        if end_date < start_date:
            raise BookingValidationError("end_date must be greater than or equal to start_date")
        slots: list[Slot] = []
        current_day = start_date
        while current_day <= end_date:
            day_slots = await self.get_provider_slots_for_date(
                tenant_id=tenant_id,
                provider_id=provider_id,
                service_id=service_id,
                target_date=current_day,
                timezone_name=timezone_name,
                slot_granularity_minutes=slot_granularity_minutes,
            )
            slots.extend(day_slots)
            current_day += timedelta(days=1)
        return slots

    async def reserve_appointment(
        self,
        *,
        tenant_id: UUID,
        provider_id: UUID,
        service_id: UUID,
        customer_name: str,
        customer_phone: str,
        start_at: datetime,
        notes: str | None = None,
    ) -> Appointment:
        service = await self._get_service(tenant_id=tenant_id, service_id=service_id, provider_id=provider_id)
        if start_at.tzinfo is not None:
            start_at = start_at.astimezone(timezone.utc).replace(tzinfo=None)
        end_at = start_at + timedelta(minutes=service.duration_minutes)

        conflict_query: Select[tuple[Appointment]] = select(Appointment).where(
            Appointment.tenant_id == tenant_id,
            Appointment.provider_id == provider_id,
            Appointment.status.in_([
                AppointmentStatus.PENDING_PAYMENT,
                AppointmentStatus.CONFIRMED,
            ]),
            Appointment.start_at < end_at,
            Appointment.end_at > start_at,
        )
        conflict = await self.session.scalar(conflict_query)
        if conflict is not None:
            raise BookingConflictError("Selected slot is no longer available")

        appointment = Appointment(
            tenant_id=tenant_id,
            provider_id=provider_id,
            service_id=service_id,
            customer_name=customer_name,
            customer_phone=customer_phone,
            notes=notes,
            start_at=start_at,
            end_at=end_at,
            total_amount=Decimal(str(service.price_amount)),
            currency=service.currency,
            status=AppointmentStatus.PENDING_PAYMENT,
        )
        self.session.add(appointment)
        await self.session.flush()
        await self.session.refresh(appointment)
        return appointment

    async def _get_service(self, *, tenant_id: UUID, service_id: UUID, provider_id: UUID) -> Service:
        query: Select[tuple[Service]] = select(Service).where(
            Service.id == service_id,
            Service.tenant_id == tenant_id,
            Service.provider_id == provider_id,
        )
        service = await self.session.scalar(query)
        if service is None:
            raise BookingValidationError("Service does not belong to tenant/provider")
        return service

    async def _get_default_service(self, *, tenant_id: UUID, provider_id: UUID) -> Service:
        query: Select[tuple[Service]] = (
            select(Service)
            .where(
                Service.tenant_id == tenant_id,
                Service.provider_id == provider_id,
            )
            .order_by(Service.duration_minutes.asc(), Service.name.asc())
            .limit(1)
        )
        service = await self.session.scalar(query)
        if service is None:
            raise BookingValidationError("No service configured for tenant/provider")
        return service

    async def _ensure_provider(self, *, tenant_id: UUID, provider_id: UUID) -> Provider:
        query: Select[tuple[Provider]] = select(Provider).where(
            Provider.id == provider_id,
            Provider.tenant_id == tenant_id,
        )
        provider = await self.session.scalar(query)
        if provider is None:
            raise BookingValidationError("Provider does not belong to tenant")
        return provider

    async def _get_availabilities(self, *, tenant_id: UUID, provider_id: UUID) -> list[Availability]:
        query: Select[tuple[Availability]] = (
            select(Availability)
            .where(
                Availability.tenant_id == tenant_id,
                Availability.provider_id == provider_id,
                Availability.is_active.is_(True),
            )
            .order_by(Availability.day_of_week.asc(), Availability.start_time.asc())
        )
        rows = await self.session.scalars(query)
        return list(rows)

    async def _get_blocking_appointments(
        self,
        *,
        tenant_id: UUID,
        provider_id: UUID,
        range_start: datetime,
        range_end: datetime,
    ) -> list[Appointment]:
        query: Select[tuple[Appointment]] = select(Appointment).where(
            Appointment.tenant_id == tenant_id,
            Appointment.provider_id == provider_id,
            Appointment.status.in_([
                AppointmentStatus.PENDING_PAYMENT,
                AppointmentStatus.CONFIRMED,
            ]),
            and_(Appointment.start_at < range_end, Appointment.end_at > range_start),
        )
        rows = await self.session.scalars(query)
        return list(rows)

    @staticmethod
    def _has_overlap(slot_start: datetime, slot_end: datetime, appointments: list[Appointment]) -> bool:
        return any(a.start_at < slot_end and a.end_at > slot_start for a in appointments)

    @staticmethod
    def _get_tz(timezone_name: str) -> tzinfo:
        if timezone_name in {"UTC", "Etc/UTC", "Z"}:
            return timezone.utc
        try:
            return ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError as exc:
            fallback_offsets = {
                "America/La_Paz": -4,
                "America/Bogota": -5,
                "America/Lima": -5,
                "America/Mexico_City": -6,
            }
            if timezone_name in fallback_offsets:
                return timezone(timedelta(hours=fallback_offsets[timezone_name]))
            raise BookingValidationError(f"Invalid timezone: {timezone_name}") from exc

    @staticmethod
    def _local_window_to_utc_naive(
        *,
        target_date: date,
        start_t: time,
        end_t: time,
        tz: tzinfo,
    ) -> tuple[datetime, datetime]:
        local_start = datetime.combine(target_date, start_t, tzinfo=tz)
        local_end = datetime.combine(target_date, end_t, tzinfo=tz)
        utc_start = local_start.astimezone(timezone.utc).replace(tzinfo=None)
        utc_end = local_end.astimezone(timezone.utc).replace(tzinfo=None)
        return utc_start, utc_end