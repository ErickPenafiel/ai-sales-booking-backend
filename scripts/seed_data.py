from __future__ import annotations

import asyncio
from datetime import date, datetime, time, timedelta, timezone, tzinfo
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from pathlib import Path
import sys
import os

# Allow running as: python scripts/seed_data.py
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.appointment import Appointment
from app.models.availability import Availability
from app.models.enums import AppointmentStatus
from app.models.resource import Resource
from app.models.service import Service
from app.models.tenant import Tenant

load_dotenv(override=True)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/ai_sales",
)


def build_session_local() -> async_sessionmaker[AsyncSession]:
    """Create an async session factory using the runtime DATABASE_URL from .env."""
    engine = create_async_engine(DATABASE_URL, pool_pre_ping=True)
    return async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


TENANT_SLUG = "clinica-dental-sucre"
TENANT_NAME = "Clinica Dental Sucre"


def get_local_tz() -> tzinfo:
    try:
        return ZoneInfo("America/La_Paz")
    except ZoneInfoNotFoundError:
        # Windows environments without tzdata package
        return timezone(timedelta(hours=-4))


LOCAL_TZ = get_local_tz()


def to_utc_naive(local_date: date, local_time: time) -> datetime:
    """Convert local datetime in LOCAL_TZ to naive UTC for DB storage."""
    local_dt = datetime.combine(local_date, local_time, tzinfo=LOCAL_TZ)
    return local_dt.astimezone(timezone.utc).replace(tzinfo=None)


async def get_or_create_tenant(session) -> Tenant:
    tenant = await session.scalar(select(Tenant).where(Tenant.slug == TENANT_SLUG))
    if tenant is None:
        tenant = Tenant(
            name=TENANT_NAME,
            slug=TENANT_SLUG,
            contact_email="recepcion@clinicasucre.example",
        )
        session.add(tenant)
        await session.flush()
    return tenant


async def get_or_create_resource(session, *, tenant_id, name: str, kind: str = "doctor") -> Resource:
    resource = await session.scalar(
        select(Resource).where(
            Resource.tenant_id == tenant_id,
            Resource.name == name,
        )
    )
    if resource is None:
        resource = Resource(
            tenant_id=tenant_id,
            name=name,
            kind=kind,
            resource_metadata={"timezone": "America/La_Paz"},
        )
        session.add(resource)
        await session.flush()
    return resource


async def ensure_weekday_availability(session, *, tenant_id, resource_id) -> None:
    # Monday-Friday: 08:00-12:00 and 14:00-18:00
    blocks = [
        (time(8, 0), time(12, 0)),
        (time(14, 0), time(18, 0)),
    ]
    for day_of_week in range(0, 5):
        for start_t, end_t in blocks:
            existing = await session.scalar(
                select(Availability).where(
                    Availability.tenant_id == tenant_id,
                    Availability.resource_id == resource_id,
                    Availability.day_of_week == day_of_week,
                    Availability.start_time == start_t,
                    Availability.end_time == end_t,
                )
            )
            if existing is None:
                session.add(
                    Availability(
                        tenant_id=tenant_id,
                        resource_id=resource_id,
                        day_of_week=day_of_week,
                        start_time=start_t,
                        end_time=end_t,
                        is_active=True,
                    )
                )


async def get_or_create_service(
    session,
    *,
    tenant_id,
    resource_id,
    name: str,
    duration_minutes: int,
) -> Service:
    service = await session.scalar(
        select(Service).where(
            Service.tenant_id == tenant_id,
            Service.resource_id == resource_id,
            Service.name == name,
        )
    )
    if service is None:
        service = Service(
            tenant_id=tenant_id,
            resource_id=resource_id,
            name=name,
            duration_minutes=duration_minutes,
            price_amount=0,
            currency="USD",
        )
        session.add(service)
        await session.flush()
    return service


async def ensure_demo_appointments(
    session,
    *,
    tenant_id,
    resource,
    consulta_service: Service,
    limpieza_service: Service,
) -> None:
    today = date.today()

    # Existing bookings for testing slot subtraction:
    # - 08:30 (Consulta, 30m)
    # - 15:00 (Limpieza, 60m)
    samples = [
        ("Paciente Demo 1", "+59170000001", consulta_service, time(8, 30)),
        ("Paciente Demo 2", "+59170000002", limpieza_service, time(15, 0)),
    ]

    for customer_name, customer_phone, service, local_start_t in samples:
        start_at = to_utc_naive(today, local_start_t)
        end_at = start_at + timedelta(minutes=service.duration_minutes)

        exists = await session.scalar(
            select(Appointment).where(
                Appointment.tenant_id == tenant_id,
                Appointment.resource_id == resource.id,
                Appointment.customer_phone == customer_phone,
                Appointment.start_at == start_at,
            )
        )
        if exists is None:
            session.add(
                Appointment(
                    tenant_id=tenant_id,
                    resource_id=resource.id,
                    service_id=service.id,
                    customer_name=customer_name,
                    customer_phone=customer_phone,
                    start_at=start_at,
                    end_at=end_at,
                    total_amount=0,
                    currency="USD",
                    status=AppointmentStatus.CONFIRMED,
                )
            )


async def ensure_bulk_appointments(
    session,
    *,
    tenant_id,
    resources: list[Resource],
    service_by_resource: dict[str, Service],
    target_count: int = 120,
) -> int:
    """Populate at least `target_count` confirmed appointments for load/perf testing."""
    existing_count = await session.scalar(
        select(func.count()).select_from(Appointment).where(Appointment.tenant_id == tenant_id)
    )
    # SQLAlchemy count shortcut above may not work in all versions/drivers; safe fallback below.
    if existing_count is None:
        rows = await session.scalars(select(Appointment.id).where(Appointment.tenant_id == tenant_id))
        existing_count = len(list(rows))

    if existing_count >= target_count:
        return 0

    created = 0
    remaining = target_count - existing_count
    start_day = date.today() - timedelta(days=20)
    slot_times = [time(8, 0), time(8, 30), time(9, 0), time(9, 30), time(10, 0), time(10, 30), time(14, 0), time(14, 30)]

    day_cursor = 0
    while created < remaining:
        day = start_day + timedelta(days=day_cursor)
        day_cursor += 1
        if day.weekday() >= 5:  # skip weekends
            continue

        for res in resources:
            service = service_by_resource[str(res.id)]
            for slot_t in slot_times:
                if created >= remaining:
                    break

                idx = existing_count + created + 1
                customer_phone = f"+59179{idx:06d}"
                customer_name = f"Paciente Seed {idx:03d}"
                start_at = to_utc_naive(day, slot_t)
                end_at = start_at + timedelta(minutes=service.duration_minutes)

                exists = await session.scalar(
                    select(Appointment).where(
                        Appointment.tenant_id == tenant_id,
                        Appointment.resource_id == res.id,
                        Appointment.customer_phone == customer_phone,
                        Appointment.start_at == start_at,
                    )
                )
                if exists is not None:
                    continue

                session.add(
                    Appointment(
                        tenant_id=tenant_id,
                        resource_id=res.id,
                        service_id=service.id,
                        customer_name=customer_name,
                        customer_phone=customer_phone,
                        start_at=start_at,
                        end_at=end_at,
                        total_amount=0,
                        currency="USD",
                        status=AppointmentStatus.CONFIRMED,
                    )
                )
                created += 1

    return created


async def main() -> None:
    SessionLocal = build_session_local()
    async with SessionLocal() as session:
        tenant = await get_or_create_tenant(session)

        dr_penafiel = await get_or_create_resource(
            session,
            tenant_id=tenant.tenant_id,
            name="Dr. Penafiel",
        )
        dra_yrene = await get_or_create_resource(
            session,
            tenant_id=tenant.tenant_id,
            name="Dra. Yrene",
        )

        await ensure_weekday_availability(session, tenant_id=tenant.tenant_id, resource_id=dr_penafiel.id)
        await ensure_weekday_availability(session, tenant_id=tenant.tenant_id, resource_id=dra_yrene.id)

        consulta_dr = await get_or_create_service(
            session,
            tenant_id=tenant.tenant_id,
            resource_id=dr_penafiel.id,
            name="Consulta",
            duration_minutes=30,
        )
        limpieza_dr = await get_or_create_service(
            session,
            tenant_id=tenant.tenant_id,
            resource_id=dr_penafiel.id,
            name="Limpieza",
            duration_minutes=60,
        )
        await get_or_create_service(
            session,
            tenant_id=tenant.tenant_id,
            resource_id=dr_penafiel.id,
            name="Cirugia",
            duration_minutes=120,
        )

        # Also create same 3 services for Dra. Yrene to keep parity.
        consulta_yrene = await get_or_create_service(
            session,
            tenant_id=tenant.tenant_id,
            resource_id=dra_yrene.id,
            name="Consulta",
            duration_minutes=30,
        )
        await get_or_create_service(
            session,
            tenant_id=tenant.tenant_id,
            resource_id=dra_yrene.id,
            name="Limpieza",
            duration_minutes=60,
        )
        await get_or_create_service(
            session,
            tenant_id=tenant.tenant_id,
            resource_id=dra_yrene.id,
            name="Cirugia",
            duration_minutes=120,
        )

        await ensure_demo_appointments(
            session,
            tenant_id=tenant.tenant_id,
            resource=dr_penafiel,
            consulta_service=consulta_dr,
            limpieza_service=limpieza_dr,
        )

        service_map = {
            str(dr_penafiel.id): consulta_dr,
            str(dra_yrene.id): consulta_yrene,
        }
        bulk_target = int(os.getenv("SEED_APPOINTMENTS_TARGET", "120"))
        created_bulk = await ensure_bulk_appointments(
            session,
            tenant_id=tenant.tenant_id,
            resources=[dr_penafiel, dra_yrene],
            service_by_resource=service_map,
            target_count=bulk_target,
        )

        await session.commit()

        print("Seed data complete")
        print("tenant_id:", tenant.tenant_id)
        print("resource Dr. Penafiel:", dr_penafiel.id)
        print("resource Dra. Yrene:", dra_yrene.id)
        print("service Limpieza Dr. Penafiel:", limpieza_dr.id)
        print("bulk_appointments_created:", created_bulk)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as exc:  # noqa: BLE001
        print("Seed failed. Check DATABASE_URL and DB availability.")
        print("DATABASE_URL:", DATABASE_URL)
        print("Error:", repr(exc))
        raise
