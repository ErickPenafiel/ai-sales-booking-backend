"""
Comprehensive CRUD services for all database models.
Provides create, read, update, delete operations with proper validation.
"""

from __future__ import annotations

import logging
from datetime import date, time
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tenant import Tenant
from app.models.resource import Resource
from app.models.customer import Customer
from app.models.service import Service
from app.models.availability import Availability
from app.models.appointment import Appointment, AppointmentStatus
from app.models.payment import Payment, PaymentStatus
from app.models.media import Media
from app.models.chat_message import ChatMessage, ChatRole

logger = logging.getLogger(__name__)


# ============================================================================
# TENANT CRUD
# ============================================================================

async def create_tenant(
    session: AsyncSession,
    *,
    name: str,
    slug: str,
    contact_email: str | None = None,
) -> Tenant:
    """Create a new tenant."""
    tenant = Tenant(
        tenant_id=uuid4(),
        name=name.strip(),
        slug=slug.strip().lower(),
        contact_email=contact_email.strip() if contact_email else None,
    )
    session.add(tenant)
    await session.flush()
    logger.info("Created tenant id=%s name=%s", tenant.tenant_id, tenant.name)
    return tenant


async def get_tenant(session: AsyncSession, tenant_id: UUID) -> Tenant | None:
    """Get tenant by ID."""
    result = await session.execute(select(Tenant).where(Tenant.tenant_id == tenant_id))
    return result.scalar_one_or_none()


async def get_tenant_by_slug(session: AsyncSession, slug: str) -> Tenant | None:
    """Get tenant by slug."""
    result = await session.execute(select(Tenant).where(Tenant.slug == slug.lower()))
    return result.scalar_one_or_none()


async def list_tenants(
    session: AsyncSession,
    *,
    skip: int = 0,
    limit: int = 100,
) -> list[Tenant]:
    """List all tenants with pagination."""
    result = await session.execute(
        select(Tenant).order_by(Tenant.created_at.desc()).offset(skip).limit(limit)
    )
    return list(result.scalars().all())


async def update_tenant(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    name: str | None = None,
    slug: str | None = None,
    contact_email: str | None = None,
) -> Tenant | None:
    """Update tenant fields."""
    tenant = await get_tenant(session, tenant_id)
    if not tenant:
        return None
    
    if name is not None:
        tenant.name = name.strip()
    if slug is not None:
        tenant.slug = slug.strip().lower()
    if contact_email is not None:
        tenant.contact_email = contact_email.strip() if contact_email else None
    
    await session.flush()
    logger.info("Updated tenant id=%s", tenant.tenant_id)
    return tenant


async def delete_tenant(session: AsyncSession, tenant_id: UUID) -> bool:
    """Delete tenant and all related resources (CASCADE)."""
    tenant = await get_tenant(session, tenant_id)
    if not tenant:
        return False
    
    await session.delete(tenant)
    await session.flush()
    logger.info("Deleted tenant id=%s", tenant_id)
    return True


# ============================================================================
# RESOURCE CRUD
# ============================================================================

async def create_resource(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    name: str,
    kind: str,
    metadata: dict[str, Any] | None = None,
) -> Resource:
    """Create a new resource."""
    # Validate tenant exists
    tenant = await get_tenant(session, tenant_id)
    if not tenant:
        raise ValueError(f"Tenant {tenant_id} not found")
    
    resource = Resource(
        id=uuid4(),
        tenant_id=tenant_id,
        name=name.strip(),
        kind=kind.strip(),
        resource_metadata=metadata or {},
    )
    session.add(resource)
    await session.flush()
    logger.info("Created resource id=%s name=%s tenant=%s", resource.id, resource.name, tenant_id)
    return resource


async def get_resource(session: AsyncSession, resource_id: UUID) -> Resource | None:
    """Get resource by ID."""
    result = await session.execute(select(Resource).where(Resource.id == resource_id))
    return result.scalar_one_or_none()


async def list_resources(
    session: AsyncSession,
    *,
    tenant_id: UUID | None = None,
    kind: str | None = None,
    skip: int = 0,
    limit: int = 100,
) -> list[Resource]:
    """List resources with optional filters."""
    query = select(Resource)
    if tenant_id:
        query = query.where(Resource.tenant_id == tenant_id)
    if kind:
        query = query.where(Resource.kind == kind)
    
    result = await session.execute(
        query.order_by(Resource.name.asc()).offset(skip).limit(limit)
    )
    return list(result.scalars().all())


async def update_resource(
    session: AsyncSession,
    resource_id: UUID,
    *,
    name: str | None = None,
    kind: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Resource | None:
    """Update resource fields."""
    resource = await get_resource(session, resource_id)
    if not resource:
        return None
    
    if name is not None:
        resource.name = name.strip()
    if kind is not None:
        resource.kind = kind.strip()
    if metadata is not None:
        resource.resource_metadata = metadata
    
    await session.flush()
    logger.info("Updated resource id=%s", resource.id)
    return resource


async def delete_resource(session: AsyncSession, resource_id: UUID) -> bool:
    """Delete resource (CASCADE will remove services, availabilities, appointments)."""
    resource = await get_resource(session, resource_id)
    if not resource:
        return False
    
    await session.delete(resource)
    await session.flush()
    logger.info("Deleted resource id=%s", resource_id)
    return True


# ============================================================================
# CUSTOMER CRUD
# ============================================================================

async def create_customer(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    phone_number: str,
    name: str | None = None,
) -> Customer:
    """Create a new customer."""
    # Check uniqueness of phone per tenant
    existing = await get_customer_by_phone(session, tenant_id, phone_number)
    if existing:
        raise ValueError(f"Customer with phone {phone_number} already exists for tenant {tenant_id}")
    
    customer = Customer(
        id=uuid4(),
        tenant_id=tenant_id,
        phone_number=phone_number.strip(),
        name=name.strip() if name else None,
    )
    session.add(customer)
    await session.flush()
    logger.info("Created customer id=%s phone=%s tenant=%s", customer.id, customer.phone_number, tenant_id)
    return customer


async def get_customer(session: AsyncSession, customer_id: UUID) -> Customer | None:
    """Get customer by ID."""
    result = await session.execute(select(Customer).where(Customer.id == customer_id))
    return result.scalar_one_or_none()


async def get_customer_by_phone(
    session: AsyncSession, tenant_id: UUID, phone_number: str
) -> Customer | None:
    """Get customer by phone number within a tenant."""
    result = await session.execute(
        select(Customer).where(
            Customer.tenant_id == tenant_id,
            Customer.phone_number == phone_number.strip(),
        )
    )
    return result.scalar_one_or_none()


async def list_customers(
    session: AsyncSession,
    *,
    tenant_id: UUID | None = None,
    skip: int = 0,
    limit: int = 100,
) -> list[Customer]:
    """List customers with optional tenant filter."""
    query = select(Customer)
    if tenant_id:
        query = query.where(Customer.tenant_id == tenant_id)
    
    result = await session.execute(
        query.order_by(Customer.created_at.desc()).offset(skip).limit(limit)
    )
    return list(result.scalars().all())


async def update_customer(
    session: AsyncSession,
    customer_id: UUID,
    *,
    name: str | None = None,
    phone_number: str | None = None,
) -> Customer | None:
    """Update customer fields."""
    customer = await get_customer(session, customer_id)
    if not customer:
        return None
    
    if name is not None:
        customer.name = name.strip()
    if phone_number is not None:
        # Check phone uniqueness
        if phone_number.strip() != customer.phone_number:
            existing = await get_customer_by_phone(
                session, customer.tenant_id, phone_number
            )
            if existing and existing.id != customer_id:
                raise ValueError(
                    f"Phone number {phone_number} already in use by customer {existing.id}"
                )
        customer.phone_number = phone_number.strip()
    
    await session.flush()
    logger.info("Updated customer id=%s", customer.id)
    return customer


async def delete_customer(session: AsyncSession, customer_id: UUID) -> bool:
    """Delete customer (CASCADE will remove chat messages)."""
    customer = await get_customer(session, customer_id)
    if not customer:
        return False
    
    await session.delete(customer)
    await session.flush()
    logger.info("Deleted customer id=%s", customer_id)
    return True


# ============================================================================
# SERVICE CRUD
# ============================================================================

async def create_service(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    provider_id: UUID,
    name: str,
    description: str | None = None,
    duration_minutes: int,
    price_amount: float = 0.0,
    currency: str = "USD",
) -> Service:
    """Create a new service."""
    from app.models.provider import Provider
    
    tenant = await get_tenant(session, tenant_id)
    if not tenant:
        raise ValueError(f"Tenant {tenant_id} not found")
    
    provider = await get_provider(session, provider_id)
    if not provider:
        raise ValueError(f"Provider {provider_id} not found")
    if provider.tenant_id != tenant_id:
        raise ValueError(f"Provider {provider_id} does not belong to tenant {tenant_id}")
    
    if duration_minutes <= 0:
        raise ValueError("duration_minutes must be positive")
    if price_amount < 0:
        raise ValueError("price_amount cannot be negative")
    
    service = Service(
        id=uuid4(),
        tenant_id=tenant_id,
        provider_id=provider_id,
        name=name.strip(),
        description=description.strip() if description else None,
        duration_minutes=duration_minutes,
        price_amount=price_amount,
        currency=currency.upper(),
    )
    session.add(service)
    await session.flush()
    logger.info("Created service id=%s name=%s provider=%s", service.id, service.name, provider_id)
    return service


async def get_service(session: AsyncSession, service_id: UUID) -> Service | None:
    """Get service by ID."""
    result = await session.execute(select(Service).where(Service.id == service_id))
    return result.scalar_one_or_none()


async def list_services(
    session: AsyncSession,
    *,
    tenant_id: UUID | None = None,
    provider_id: UUID | None = None,
    skip: int = 0,
    limit: int = 100,
) -> list[Service]:
    """List services with optional filters."""
    query = select(Service)
    if tenant_id:
        query = query.where(Service.tenant_id == tenant_id)
    if provider_id:
        query = query.where(Service.provider_id == provider_id)
    
    result = await session.execute(
        query.order_by(Service.name.asc()).offset(skip).limit(limit)
    )
    return list(result.scalars().all())


async def update_service(
    session: AsyncSession,
    service_id: UUID,
    *,
    name: str | None = None,
    description: str | None = None,
    duration_minutes: int | None = None,
    price_amount: float | None = None,
    currency: str | None = None,
) -> Service | None:
    """Update service fields."""
    service = await get_service(session, service_id)
    if not service:
        return None
    
    if name is not None:
        service.name = name.strip()
    if description is not None:
        service.description = description.strip() if description else None
    if duration_minutes is not None:
        if duration_minutes <= 0:
            raise ValueError("duration_minutes must be positive")
        service.duration_minutes = duration_minutes
    if price_amount is not None:
        if price_amount < 0:
            raise ValueError("price_amount cannot be negative")
        service.price_amount = price_amount
    if currency is not None:
        service.currency = currency.upper()
    
    await session.flush()
    logger.info("Updated service id=%s", service.id)
    return service


async def delete_service(session: AsyncSession, service_id: UUID) -> bool:
    """Delete service (will fail if appointments exist due to RESTRICT)."""
    service = await get_service(session, service_id)
    if not service:
        return False
    
    try:
        await session.delete(service)
        await session.flush()
        logger.info("Deleted service id=%s", service_id)
        return True
    except Exception as exc:
        logger.warning("Cannot delete service id=%s: %s", service_id, exc)
        raise ValueError("Cannot delete service with existing appointments") from exc


# ============================================================================
# AVAILABILITY CRUD
# ============================================================================

async def create_availability(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    provider_id: UUID,
    day_of_week: int,
    start_time: time,
    end_time: time,
    is_active: bool = True,
) -> Availability:
    """Create an availability window."""
    from app.models.provider import Provider
    
    if not (0 <= day_of_week <= 6):
        raise ValueError("day_of_week must be between 0 and 6")
    if start_time >= end_time:
        raise ValueError("start_time must be before end_time")
    
    provider = await get_provider(session, provider_id)
    if not provider or provider.tenant_id != tenant_id:
        raise ValueError(f"Provider {provider_id} does not belong to tenant {tenant_id}")
    
    availability = Availability(
        id=uuid4(),
        tenant_id=tenant_id,
        provider_id=provider_id,
        day_of_week=day_of_week,
        start_time=start_time,
        end_time=end_time,
        is_active=is_active,
    )
    session.add(availability)
    await session.flush()
    logger.info(
        "Created availability id=%s provider=%s day=%d time=%s-%s",
        availability.id, provider_id, day_of_week, start_time, end_time,
    )
    return availability


async def get_availability(session: AsyncSession, availability_id: UUID) -> Availability | None:
    """Get availability by ID."""
    result = await session.execute(
        select(Availability).where(Availability.id == availability_id)
    )
    return result.scalar_one_or_none()


async def list_availabilities(
    session: AsyncSession,
    *,
    tenant_id: UUID | None = None,
    provider_id: UUID | None = None,
    day_of_week: int | None = None,
    is_active: bool | None = None,
    skip: int = 0,
    limit: int = 100,
) -> list[Availability]:
    """List availability windows with optional filters."""
    query = select(Availability)
    if tenant_id:
        query = query.where(Availability.tenant_id == tenant_id)
    if provider_id:
        query = query.where(Availability.provider_id == provider_id)
    if day_of_week is not None:
        query = query.where(Availability.day_of_week == day_of_week)
    if is_active is not None:
        query = query.where(Availability.is_active == is_active)
    
    result = await session.execute(
        query.order_by(Availability.day_of_week, Availability.start_time)
        .offset(skip)
        .limit(limit)
    )
    return list(result.scalars().all())


async def update_availability(
    session: AsyncSession,
    availability_id: UUID,
    *,
    day_of_week: int | None = None,
    start_time: time | None = None,
    end_time: time | None = None,
    is_active: bool | None = None,
) -> Availability | None:
    """Update availability window."""
    availability = await get_availability(session, availability_id)
    if not availability:
        return None
    
    if day_of_week is not None:
        if not (0 <= day_of_week <= 6):
            raise ValueError("day_of_week must be between 0 and 6")
        availability.day_of_week = day_of_week
    
    # Validate time window if both are provided
    new_start = start_time or availability.start_time
    new_end = end_time or availability.end_time
    if start_time is not None or end_time is not None:
        if new_start >= new_end:
            raise ValueError("start_time must be before end_time")
    
    if start_time is not None:
        availability.start_time = start_time
    if end_time is not None:
        availability.end_time = end_time
    if is_active is not None:
        availability.is_active = is_active
    
    await session.flush()
    logger.info("Updated availability id=%s", availability.id)
    return availability


async def delete_availability(session: AsyncSession, availability_id: UUID) -> bool:
    """Delete availability window."""
    availability = await get_availability(session, availability_id)
    if not availability:
        return False
    
    await session.delete(availability)
    await session.flush()
    logger.info("Deleted availability id=%s", availability_id)
    return True


# ============================================================================
# APPOINTMENT CRUD
# ============================================================================

async def create_appointment(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    provider_id: UUID,
    service_id: UUID,
    customer_name: str,
    customer_phone: str,
    date: date,
    start_time: time,
    end_time: time,
    notes: str | None = None,
    total_amount: float = 0.0,
    currency: str = "USD",
    status: AppointmentStatus = AppointmentStatus.PENDING_PAYMENT,
) -> Appointment:
    """Create an appointment."""
    from app.models.provider import Provider
    
    provider = await get_provider(session, provider_id)
    if not provider or provider.tenant_id != tenant_id:
        raise ValueError(f"Provider {provider_id} does not belong to tenant {tenant_id}")
    
    service = await get_service(session, service_id)
    if not service or service.tenant_id != tenant_id:
        raise ValueError(f"Service {service_id} does not belong to tenant {tenant_id}")
    
    appointment = Appointment(
        id=uuid4(),
        tenant_id=tenant_id,
        provider_id=provider_id,
        service_id=service_id,
        customer_name=customer_name.strip(),
        customer_phone=customer_phone.strip(),
        date=date,
        start_time=start_time,
        end_time=end_time,
        notes=notes.strip() if notes else None,
        total_amount=total_amount,
        currency=currency.upper(),
        status=status,
    )
    session.add(appointment)
    await session.flush()
    logger.info(
        "Created appointment id=%s provider=%s customer=%s",
        appointment.id, provider_id, customer_name,
    )
    return appointment


async def get_appointment(session: AsyncSession, appointment_id: UUID) -> Appointment | None:
    """Get appointment by ID."""
    result = await session.execute(
        select(Appointment).where(Appointment.id == appointment_id)
    )
    return result.scalar_one_or_none()


async def list_appointments(
    session: AsyncSession,
    *,
    tenant_id: UUID | None = None,
    provider_id: UUID | None = None,
    customer_phone: str | None = None,
    status: AppointmentStatus | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    skip: int = 0,
    limit: int = 100,
) -> list[Appointment]:
    """List appointments with optional filters."""
    query = select(Appointment)
    if tenant_id:
        query = query.where(Appointment.tenant_id == tenant_id)
    if provider_id:
        query = query.where(Appointment.provider_id == provider_id)
    if customer_phone:
        query = query.where(Appointment.customer_phone == customer_phone.strip())
    if status:
        query = query.where(Appointment.status == status)
    if date_from:
        query = query.where(Appointment.date >= date_from)
    if date_to:
        query = query.where(Appointment.date <= date_to)
    
    result = await session.execute(
        query.order_by(Appointment.date.desc(), Appointment.start_time.desc()).offset(skip).limit(limit)
    )
    return list(result.scalars().all())


async def update_appointment(
    session: AsyncSession,
    appointment_id: UUID,
    *,
    customer_name: str | None = None,
    customer_phone: str | None = None,
    date: date | None = None,
    start_time: time | None = None,
    end_time: time | None = None,
    notes: str | None = None,
    status: AppointmentStatus | None = None,
    total_amount: float | None = None,
) -> Appointment | None:
    """Update appointment fields."""
    appointment = await get_appointment(session, appointment_id)
    if not appointment:
        return None
    
    if customer_name is not None:
        appointment.customer_name = customer_name.strip()
    if customer_phone is not None:
        appointment.customer_phone = customer_phone.strip()
    if date is not None:
        appointment.date = date
    if start_time is not None:
        appointment.start_time = start_time
    if end_time is not None:
        appointment.end_time = end_time
    if notes is not None:
        appointment.notes = notes.strip() if notes else None
    if status is not None:
        appointment.status = status
    if total_amount is not None:
        appointment.total_amount = total_amount
    
    await session.flush()
    logger.info("Updated appointment id=%s", appointment.id)
    return appointment


async def cancel_appointment(
    session: AsyncSession, appointment_id: UUID
) -> Appointment | None:
    """Cancel an appointment."""
    return await update_appointment(
        session, appointment_id, status=AppointmentStatus.CANCELLED
    )


async def delete_appointment(session: AsyncSession, appointment_id: UUID) -> bool:
    """Delete appointment."""
    appointment = await get_appointment(session, appointment_id)
    if not appointment:
        return False
    
    await session.delete(appointment)
    await session.flush()
    logger.info("Deleted appointment id=%s", appointment_id)
    return True


# ============================================================================
# PAYMENT CRUD
# ============================================================================

async def create_payment(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    appointment_id: UUID,
    provider: str = "mock",
    external_intent_id: str,
    payment_link: str,
    amount: float,
    currency: str = "USD",
    status: PaymentStatus = PaymentStatus.PENDING,
    provider_payload: dict[str, Any] | None = None,
) -> Payment:
    """Create a payment record."""
    # Validate foreign keys
    appointment = await get_appointment(session, appointment_id)
    if not appointment or appointment.tenant_id != tenant_id:
        raise ValueError(f"Appointment {appointment_id} does not belong to tenant {tenant_id}")
    
    payment = Payment(
        id=uuid4(),
        tenant_id=tenant_id,
        appointment_id=appointment_id,
        provider=provider.strip(),
        external_intent_id=external_intent_id.strip(),
        payment_link=payment_link.strip(),
        amount=amount,
        currency=currency.upper(),
        status=status,
        provider_payload=provider_payload,
    )
    session.add(payment)
    await session.flush()
    logger.info(
        "Created payment id=%s appointment=%s amount=%s",
        payment.id, appointment_id, amount,
    )
    return payment


async def get_payment(session: AsyncSession, payment_id: UUID) -> Payment | None:
    """Get payment by ID."""
    result = await session.execute(select(Payment).where(Payment.id == payment_id))
    return result.scalar_one_or_none()


async def get_payment_by_external_id(
    session: AsyncSession, external_intent_id: str
) -> Payment | None:
    """Get payment by external intent ID."""
    result = await session.execute(
        select(Payment).where(Payment.external_intent_id == external_intent_id.strip())
    )
    return result.scalar_one_or_none()


async def list_payments(
    session: AsyncSession,
    *,
    tenant_id: UUID | None = None,
    appointment_id: UUID | None = None,
    status: PaymentStatus | None = None,
    skip: int = 0,
    limit: int = 100,
) -> list[Payment]:
    """List payments with optional filters."""
    query = select(Payment)
    if tenant_id:
        query = query.where(Payment.tenant_id == tenant_id)
    if appointment_id:
        query = query.where(Payment.appointment_id == appointment_id)
    if status:
        query = query.where(Payment.status == status)
    
    result = await session.execute(
        query.order_by(Payment.created_at.desc()).offset(skip).limit(limit)
    )
    return list(result.scalars().all())


async def update_payment_status(
    session: AsyncSession,
    payment_id: UUID,
    *,
    status: PaymentStatus,
    paid_at: Any | None = None,
) -> Payment | None:
    """Update payment status."""
    payment = await get_payment(session, payment_id)
    if not payment:
        return None
    
    payment.status = status
    if paid_at is not None:
        payment.paid_at = paid_at
    
    await session.flush()
    logger.info("Updated payment status id=%s status=%s", payment.id, status)
    return payment


async def delete_payment(session: AsyncSession, payment_id: UUID) -> bool:
    """Delete payment."""
    payment = await get_payment(session, payment_id)
    if not payment:
        return False
    
    await session.delete(payment)
    await session.flush()
    logger.info("Deleted payment id=%s", payment_id)
    return True


# ============================================================================
# MEDIA CRUD
# ============================================================================

async def create_media(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    filename: str,
    path: str,
    content_type: str | None = None,
    description: str | None = None,
) -> Media:
    """Create a media record."""
    media = Media(
        id=uuid4(),
        tenant_id=tenant_id,
        filename=filename.strip(),
        path=path.strip(),
        content_type=content_type.strip() if content_type else None,
        description=description.strip() if description else None,
    )
    session.add(media)
    await session.flush()
    logger.info("Created media id=%s filename=%s", media.id, media.filename)
    return media


async def get_media(session: AsyncSession, media_id: UUID) -> Media | None:
    """Get media by ID."""
    result = await session.execute(select(Media).where(Media.id == media_id))
    return result.scalar_one_or_none()


async def list_media(
    session: AsyncSession,
    *,
    tenant_id: UUID | None = None,
    skip: int = 0,
    limit: int = 100,
) -> list[Media]:
    """List media files with optional tenant filter."""
    query = select(Media)
    if tenant_id:
        query = query.where(Media.tenant_id == tenant_id)
    
    result = await session.execute(
        query.order_by(Media.created_at.desc()).offset(skip).limit(limit)
    )
    return list(result.scalars().all())


async def update_media(
    session: AsyncSession,
    media_id: UUID,
    *,
    description: str | None = None,
) -> Media | None:
    """Update media description."""
    media = await get_media(session, media_id)
    if not media:
        return None
    
    if description is not None:
        media.description = description.strip() if description else None
    
    await session.flush()
    return media


async def delete_media(session: AsyncSession, media_id: UUID) -> bool:
    """Delete media."""
    media = await get_media(session, media_id)
    if not media:
        return False
    
    await session.delete(media)
    await session.flush()
    logger.info("Deleted media id=%s", media_id)
    return True


# ============================================================================
# PROVIDERS CRUD (per-tenant providers)
# ============================================================================


async def create_provider(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    name: str,
    kind: str,
    config: dict | None = None,
) -> "Provider":
    from app.models.provider import Provider

    provider = Provider(
        id=uuid4(),
        tenant_id=tenant_id,
        name=name.strip(),
        kind=kind.strip(),
        config=config or {},
    )
    session.add(provider)
    await session.flush()
    logger.info("Created provider id=%s name=%s tenant=%s", provider.id, provider.name, tenant_id)
    return provider


async def get_provider(session: AsyncSession, provider_id: UUID):
    from app.models.provider import Provider

    result = await session.execute(select(Provider).where(Provider.id == provider_id))
    return result.scalar_one_or_none()


async def list_providers(session: AsyncSession, *, tenant_id: UUID | None = None):
    from app.models.provider import Provider

    query = select(Provider)
    if tenant_id:
        query = query.where(Provider.tenant_id == tenant_id)
    result = await session.execute(query.order_by(Provider.name.asc()))
    return list(result.scalars().all())


async def update_provider(session: AsyncSession, provider_id: UUID, *, name: str | None = None, kind: str | None = None, config: dict | None = None):
    provider = await get_provider(session, provider_id)
    if not provider:
        return None
    if name is not None:
        provider.name = name.strip()
    if kind is not None:
        provider.kind = kind.strip()
    if config is not None:
        provider.config = config
    await session.flush()
    return provider


async def delete_provider(session: AsyncSession, provider_id: UUID) -> bool:
    provider = await get_provider(session, provider_id)
    if not provider:
        return False
    await session.delete(provider)
    await session.flush()
    logger.info("Deleted provider id=%s", provider_id)
    return True


# ============================================================================
# CHAT MESSAGE CRUD
# ============================================================================

async def create_chat_message(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    customer_id: UUID,
    role: ChatRole,
    content: str,
) -> ChatMessage:
    """Create a chat message."""
    message = ChatMessage(
        id=uuid4(),
        tenant_id=tenant_id,
        customer_id=customer_id,
        role=role,
        content=content.strip(),
    )
    session.add(message)
    await session.flush()
    return message


async def get_chat_messages(
    session: AsyncSession,
    customer_id: UUID,
    *,
    limit: int = 50,
) -> list[ChatMessage]:
    """Get recent chat messages for a customer."""
    result = await session.execute(
        select(ChatMessage)
        .where(ChatMessage.customer_id == customer_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(limit)
    )
    messages = list(result.scalars().all())
    messages.reverse()  # Return in chronological order
    return messages


async def delete_chat_messages(
    session: AsyncSession, customer_id: UUID
) -> int:
    """Delete all chat messages for a customer."""
    result = await session.execute(
        select(ChatMessage).where(ChatMessage.customer_id == customer_id)
    )
    messages = list(result.scalars().all())
    for msg in messages:
        await session.delete(msg)
    await session.flush()
    return len(messages)


# ============================================================================
# STATISTICS / HELPERS
# ============================================================================

async def count_tenants(session: AsyncSession) -> int:
    """Count total tenants."""
    result = await session.execute(select(func.count()).select_from(Tenant))
    return result.scalar() or 0


async def count_appointments(
    session: AsyncSession,
    tenant_id: UUID | None = None,
    status: AppointmentStatus | None = None,
) -> int:
    """Count appointments with optional filters."""
    query = select(func.count()).select_from(Appointment)
    if tenant_id:
        query = query.where(Appointment.tenant_id == tenant_id)
    if status:
        query = query.where(Appointment.status == status)
    
    result = await session.execute(query)
    return result.scalar() or 0


async def count_customers(
    session: AsyncSession, tenant_id: UUID | None = None
) -> int:
    """Count customers with optional tenant filter."""
    query = select(func.count()).select_from(Customer)
    if tenant_id:
        query = query.where(Customer.tenant_id == tenant_id)
    
    result = await session.execute(query)
    return result.scalar() or 0
