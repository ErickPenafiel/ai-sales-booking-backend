from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.appointment import Appointment
    from app.models.availability import Availability
    from app.models.chat_message import ChatMessage
    from app.models.customer import Customer
    from app.models.knowledge_asset import KnowledgeAsset
    from app.models.payment import Payment
    from app.models.resource import Resource
    from app.models.service import Service


class Tenant(Base, TimestampMixin):
    __tablename__ = "tenants"

    # tenant_id is the partition key used across all tenant-scoped tables.
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), nullable=False, unique=True, index=True)
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    resources: Mapped[list["Resource"]] = relationship(back_populates="tenant")
    services: Mapped[list["Service"]] = relationship(back_populates="tenant")
    availabilities: Mapped[list["Availability"]] = relationship(back_populates="tenant")
    appointments: Mapped[list["Appointment"]] = relationship(back_populates="tenant")
    payments: Mapped[list["Payment"]] = relationship(back_populates="tenant")
    media: Mapped[list["Media"]] = relationship(back_populates="tenant")
    customers: Mapped[list["Customer"]] = relationship(back_populates="tenant")
    chat_messages: Mapped[list["ChatMessage"]] = relationship(back_populates="tenant")
    providers: Mapped[list["Provider"]] = relationship(back_populates="tenant", cascade="all, delete-orphan")
    knowledge_assets: Mapped[list["KnowledgeAsset"]] = relationship(back_populates="tenant", cascade="all, delete-orphan")
