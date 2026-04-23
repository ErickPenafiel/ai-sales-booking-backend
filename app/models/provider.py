from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import String, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.appointment import Appointment
    from app.models.availability import Availability
    from app.models.service import Service
    from app.models.tenant import Tenant


class Provider(Base, TimestampMixin):
    __tablename__ = "providers"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("tenants.tenant_id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    kind: Mapped[str] = mapped_column(String(60), nullable=False)
    config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    tenant: Mapped["Tenant"] = relationship(back_populates="providers")
    services: Mapped[list["Service"]] = relationship(back_populates="provider")
    availabilities: Mapped[list["Availability"]] = relationship(back_populates="provider")
    appointments: Mapped[list["Appointment"]] = relationship(back_populates="provider")
