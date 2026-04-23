from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import Enum, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import PaymentStatus

if TYPE_CHECKING:
    from app.models.appointment import Appointment
    from app.models.tenant import Tenant


class Payment(Base, TimestampMixin):
    __tablename__ = "payments"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tenants.tenant_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    appointment_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("appointments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(30), nullable=False, default="mock")
    external_intent_id: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    payment_link: Mapped[str] = mapped_column(String(600), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus, name="payment_status"),
        nullable=False,
        default=PaymentStatus.PENDING,
    )
    paid_at: Mapped[datetime | None] = mapped_column(nullable=True)
    provider_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    tenant: Mapped["Tenant"] = relationship(back_populates="payments")
    appointment: Mapped["Appointment"] = relationship(back_populates="payments")
