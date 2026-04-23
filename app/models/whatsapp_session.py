from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID
import secrets

from sqlalchemy import String, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.tenant import Tenant


class WhatsAppSession(Base, TimestampMixin):
    __tablename__ = "whatsapp_sessions"

    session_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tenants.tenant_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    webhook_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    @staticmethod
    def generate_webhook_key() -> str:
        return secrets.token_urlsafe(32)