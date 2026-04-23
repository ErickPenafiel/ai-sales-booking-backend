from __future__ import annotations

from datetime import date, time, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Enum, ForeignKey, Index, Numeric, String, Date, Time
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import AppointmentStatus

if TYPE_CHECKING:
    from app.models.payment import Payment
    from app.models.provider import Provider
    from app.models.service import Service
    from app.models.tenant import Tenant


class Appointment(Base, TimestampMixin):
    __tablename__ = "appointments"
    __table_args__ = (
        Index("ix_appointments_tenant_provider_date", "tenant_id", "provider_id", "date"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tenants.tenant_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("providers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    service_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("services.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    start_time: Mapped[time] = mapped_column(Time(timezone=False), nullable=False)
    end_time: Mapped[time] = mapped_column(Time(timezone=False), nullable=False)

    customer_name: Mapped[str] = mapped_column(String(120), nullable=False)
    customer_phone: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    total_amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    status: Mapped[AppointmentStatus] = mapped_column(
        Enum(AppointmentStatus, name="appointment_status"),
        nullable=False,
        default=AppointmentStatus.PENDING_PAYMENT,
    )

    @property
    def start_at(self) -> datetime:
        return datetime.combine(self.date, self.start_time)

    @property
    def end_at(self) -> datetime:
        return datetime.combine(self.date, self.end_time)

    tenant: Mapped["Tenant"] = relationship(back_populates="appointments")
    provider: Mapped["Provider"] = relationship(back_populates="appointments")
    service: Mapped["Service"] = relationship(back_populates="appointments")
    payments: Mapped[list["Payment"]] = relationship(back_populates="appointment")